#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Persisted registry for MCP prestart tools.

A prestart tool will be invoked automatically before LLM reasoning. This
module tracks per-server tool selections and their parameter templates.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, Mapping

_lock = threading.RLock()
_prestart: Dict[int, Dict[str, Dict[str, Any]]] = {}
_data_file = os.path.join(os.path.dirname(__file__), "data", "mcp_prestart_tools.json")


def _ensure_loaded() -> None:
    """Lazy-load data from disk."""
    global _prestart
    with _lock:
        if _prestart:
            return
        if not os.path.exists(_data_file):
            _prestart = {}
            return
        try:
            with open(_data_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            loaded: Dict[int, Dict[str, Dict[str, Any]]] = {}
            for sid, tools in (raw or {}).items():
                try:
                    server_id = int(sid)
                except Exception:
                    continue
                if not isinstance(tools, Mapping):
                    continue
                normalized: Dict[str, Dict[str, Any]] = {}
                for name, cfg in tools.items():
                    if not name:
                        continue
                    params = cfg.get("params", {}) if isinstance(cfg, Mapping) else {}
                    include_history = cfg.get("include_history", True) if isinstance(cfg, Mapping) else True
                    allow_function_call = cfg.get("allow_function_call", False) if isinstance(cfg, Mapping) else False
                    normalized[str(name)] = {
                        "params": params if isinstance(params, Mapping) else {},
                        "include_history": include_history,
                        "allow_function_call": allow_function_call
                    }
                if normalized:
                    loaded[server_id] = normalized
            _prestart = loaded
        except Exception:
            _prestart = {}


def _save_locked() -> None:
    os.makedirs(os.path.dirname(_data_file), exist_ok=True)
    with open(_data_file, "w", encoding="utf-8") as f:
        to_dump: Dict[str, Dict[str, Any]] = {}
        for sid, tools in _prestart.items():
            if not tools:
                continue
            to_dump[str(sid)] = tools
        json.dump(to_dump, f, ensure_ascii=False, indent=4)


def get_all() -> Dict[int, Dict[str, Dict[str, Any]]]:
    """Return a copy of all prestart entries."""
    _ensure_loaded()
    with _lock:
        return {sid: dict(tools) for sid, tools in _prestart.items()}


def get_server_map(server_id: int) -> Dict[str, Dict[str, Any]]:
    """Return the prestart mapping for a single server."""
    _ensure_loaded()
    with _lock:
        return dict(_prestart.get(server_id, {}))


def set_prestart(server_id: int, tool_name: str, params: Dict[str, Any], include_history: bool = True, allow_function_call: bool = False) -> None:
    """Enable prestart for a tool with parameter template and options."""
    if not tool_name:
        return
    _ensure_loaded()
    with _lock:
        server_map = _prestart.setdefault(int(server_id), {})
        server_map[str(tool_name)] = {
            "params": params or {},
            "include_history": include_history,
            "allow_function_call": allow_function_call
        }
        _save_locked()


def remove_prestart(server_id: int, tool_name: str) -> None:
    """Disable prestart for a tool."""
    if not tool_name:
        return
    _ensure_loaded()
    with _lock:
        server_map = _prestart.get(int(server_id))
        if not server_map:
            return
        if tool_name in server_map:
            del server_map[tool_name]
            if not server_map:
                del _prestart[int(server_id)]
        _save_locked()


def is_prestart(server_id: int, tool_name: str) -> bool:
    """Check whether a tool is marked for prestart."""
    _ensure_loaded()
    with _lock:
        return tool_name in _prestart.get(int(server_id), {})

