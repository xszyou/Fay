#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Shared registry for MCP tool availability and enablement state.

This module keeps an in-memory snapshot of tools reported by each MCP server.
It exposes a simple API so different components (service UI, LLM pipeline,
background clients) can publish updates and read the latest view without
re-querying the servers on every request.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, List, Optional

ToolEntry = Dict[str, Any]

_lock = threading.RLock()
_server_tools: Dict[int, Dict[str, ToolEntry]] = {}
_aggregated_cache: List[ToolEntry] = []
_aggregated_cache_timestamp: float = 0.0


def _clone_entry(entry: ToolEntry) -> ToolEntry:
    """Return a shallow copy so callers cannot mutate the registry state."""
    clone = dict(entry)
    clone["inputSchema"] = dict(entry.get("inputSchema") or {})
    return clone


def _rebuild_cache_locked() -> None:
    """Recompute the aggregated enabled+available tool cache."""
    global _aggregated_cache, _aggregated_cache_timestamp
    aggregated: Dict[str, ToolEntry] = {}
    for tools in _server_tools.values():
        for name, entry in tools.items():
            if not entry.get("available"):
                continue
            if not entry.get("enabled", True):
                continue
            cached = aggregated.get(name)
            if cached and cached.get("last_checked", 0.0) >= entry.get("last_checked", 0.0):
                continue
            aggregated[name] = _clone_entry(entry)
    _aggregated_cache = sorted(aggregated.values(), key=lambda item: item["name"])
    _aggregated_cache_timestamp = time.time()


def set_server_tools(
    server_id: int,
    tools: Optional[List[Dict[str, Any]]],
    enabled_lookup: Optional[Callable[[str], bool]] = None,
) -> None:
    """
    Publish the latest tool list reported by a server.

    Args:
        server_id: ID of the server that provided the tool list.
        tools: Iterable of tool definitions (dict-like) returned by MCP.
        enabled_lookup: Optional callback used to hydrate the enabled flag from
            persisted state managed elsewhere (e.g. UI selections).
    """
    now = time.time()
    normalized_tools = tools or []
    with _lock:
        server_map = _server_tools.setdefault(server_id, {})

        # Mark existing entries unavailable; they will be re-enabled if present.
        for entry in server_map.values():
            entry["available"] = False

        for raw_tool in normalized_tools:
            name = str((raw_tool or {}).get("name", "")).strip()
            if not name:
                continue
            entry = server_map.get(
                name,
                {
                    "name": name,
                    "description": "",
                    "inputSchema": {},
                    "available": False,
                    "enabled": True,
                    "server_id": server_id,
                    "last_checked": 0.0,
                },
            )
            entry["description"] = str(raw_tool.get("description") or "")
            input_schema = raw_tool.get("inputSchema")
            entry["inputSchema"] = dict(input_schema) if isinstance(input_schema, dict) else {}
            entry["available"] = True
            entry["server_id"] = server_id
            entry["last_checked"] = now

            if "enabled" in raw_tool:
                entry["enabled"] = bool(raw_tool["enabled"])
            elif enabled_lookup:
                try:
                    entry["enabled"] = bool(enabled_lookup(name))
                except Exception:
                    entry.setdefault("enabled", True)
            else:
                entry.setdefault("enabled", True)

            server_map[name] = entry

        _rebuild_cache_locked()


def remove_server(server_id: int) -> None:
    """Completely remove cached data for a server."""
    with _lock:
        if server_id in _server_tools:
            del _server_tools[server_id]
            _rebuild_cache_locked()


def update_tool_enabled(server_id: int, tool_name: str, enabled: bool) -> None:
    """Update the enabled flag for a specific tool and rebuild cache."""
    with _lock:
        server_map = _server_tools.get(server_id)
        if not server_map:
            return
        entry = server_map.get(tool_name)
        if not entry:
            return
        entry["enabled"] = bool(enabled)
        entry["last_checked"] = time.time()
        _rebuild_cache_locked()


def mark_all_unavailable(server_id: int) -> None:
    """Mark every tool from the given server as unavailable (e.g., on disconnect)."""
    with _lock:
        server_map = _server_tools.get(server_id)
        if not server_map:
            return
        for entry in server_map.values():
            entry["available"] = False
            entry["last_checked"] = time.time()
        _rebuild_cache_locked()


def get_server_tools(
    server_id: int,
    *,
    include_disabled: bool = True,
    include_unavailable: bool = False,
) -> List[ToolEntry]:
    """Return the current tool snapshot for a server."""
    with _lock:
        server_map = _server_tools.get(server_id, {})
        results: List[ToolEntry] = []
        for entry in server_map.values():
            if not include_unavailable and not entry.get("available"):
                continue
            if not include_disabled and not entry.get("enabled", True):
                continue
            results.append(_clone_entry(entry))
        results.sort(key=lambda item: item["name"])
        return results


def get_enabled_tools() -> List[ToolEntry]:
    """Return enabled, currently available tools aggregated across servers."""
    with _lock:
        return [_clone_entry(entry) for entry in _aggregated_cache]


def get_all_tools(include_disabled: bool = True) -> List[ToolEntry]:
    """Return all cached tools regardless of availability."""
    with _lock:
        results: List[ToolEntry] = []
        for tools in _server_tools.values():
            for entry in tools.values():
                if not include_disabled and not entry.get("enabled", True):
                    continue
                results.append(_clone_entry(entry))
        results.sort(key=lambda item: (item["server_id"], item["name"]))
        return results


def get_cache_timestamp() -> float:
    """Expose the timestamp of the last aggregated cache refresh."""
    with _lock:
        return _aggregated_cache_timestamp


def reset() -> None:
    """
    Reset all cached data. Intended for unit tests to ensure a clean slate.
    """
    global _server_tools, _aggregated_cache, _aggregated_cache_timestamp
    with _lock:
        _server_tools = {}
        _aggregated_cache = []
        _aggregated_cache_timestamp = 0.0
