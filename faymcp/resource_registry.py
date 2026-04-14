#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Shared registry for MCP resource content.

Stores resource text read from MCP servers so the LLM pipeline can inject
them into the system prompt without re-querying the servers on every request.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

_lock = threading.RLock()

# server_id -> list of {"uri": ..., "name": ..., "description": ..., "text": ...}
_server_resources: Dict[int, List[Dict[str, Any]]] = {}


def set_server_resources(server_id: int, resources: List[Dict[str, Any]]) -> None:
    with _lock:
        _server_resources[server_id] = list(resources)


def get_server_resources(server_id: int) -> List[Dict[str, Any]]:
    with _lock:
        return list(_server_resources.get(server_id, []))


def get_all_resources() -> List[Dict[str, Any]]:
    with _lock:
        result: List[Dict[str, Any]] = []
        for resources in _server_resources.values():
            result.extend(resources)
        return result


def clear_server_resources(server_id: int) -> None:
    with _lock:
        _server_resources.pop(server_id, None)
