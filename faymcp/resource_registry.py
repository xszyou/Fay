#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Shared registry for MCP resource content.

Stores resource text read from MCP servers so the LLM pipeline can inject
them into the system prompt without re-querying the servers on every request.

Each resource entry:
  {
      "uri": str,
      "name": str,
      "description": str,
      "text": str,
      "server_id": int,
      "server_name": str,
      "enabled": bool,       # 是否注入到 prompt
  }
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List

_lock = threading.RLock()

# server_id -> list of resource entries
_server_resources: Dict[int, List[Dict[str, Any]]] = {}

# 持久化文件路径
_STATES_FILE = os.path.join(os.path.dirname(__file__), "data", "mcp_resource_states.json")


def _load_states() -> Dict[str, Dict[str, bool]]:
    """Load persisted resource enabled/disabled states. {server_id_str: {uri: bool}}"""
    try:
        if os.path.exists(_STATES_FILE):
            with open(_STATES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_states() -> None:
    """Persist current resource enabled/disabled states."""
    states: Dict[str, Dict[str, bool]] = {}
    for sid, resources in _server_resources.items():
        uri_states = {}
        for res in resources:
            uri_states[res["uri"]] = res.get("enabled", True)
        if uri_states:
            states[str(sid)] = uri_states
    try:
        os.makedirs(os.path.dirname(_STATES_FILE), exist_ok=True)
        with open(_STATES_FILE, "w", encoding="utf-8") as f:
            json.dump(states, f, ensure_ascii=False, indent=4)
    except Exception:
        pass


def set_server_resources(
    server_id: int,
    resources: List[Dict[str, Any]],
    server_name: str = "",
) -> None:
    """Cache resources for a server, restoring persisted enabled states."""
    saved_states = _load_states().get(str(server_id), {})
    entries: List[Dict[str, Any]] = []
    for res in resources:
        uri = res.get("uri", "")
        entry = dict(res)
        entry["server_id"] = server_id
        entry["server_name"] = server_name
        # 恢复持久化的启用状态，默认启用
        entry["enabled"] = saved_states.get(uri, True)
        entries.append(entry)
    with _lock:
        _server_resources[server_id] = entries


def get_server_resources(server_id: int) -> List[Dict[str, Any]]:
    with _lock:
        return list(_server_resources.get(server_id, []))


def get_all_resources() -> List[Dict[str, Any]]:
    with _lock:
        result: List[Dict[str, Any]] = []
        for resources in _server_resources.values():
            result.extend(resources)
        return result


def get_enabled_resources() -> List[Dict[str, Any]]:
    """Return only resources that are enabled for prompt injection."""
    with _lock:
        result: List[Dict[str, Any]] = []
        for resources in _server_resources.values():
            for res in resources:
                if res.get("enabled", True):
                    result.append(res)
        return result


def set_resource_enabled(server_id: int, uri: str, enabled: bool) -> bool:
    """Toggle a single resource's enabled state. Returns True if found."""
    with _lock:
        resources = _server_resources.get(server_id, [])
        for res in resources:
            if res.get("uri") == uri:
                res["enabled"] = enabled
                _save_states()
                return True
    return False


def clear_server_resources(server_id: int) -> None:
    with _lock:
        _server_resources.pop(server_id, None)
