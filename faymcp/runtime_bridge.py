#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Helpers for accessing MCP runtime state from in-process callers.

This avoids loopback HTTP calls when the LLM pipeline and MCP service are
running in the same Python process.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from faymcp import prestart_registry, tool_registry


def get_enabled_tools() -> List[Dict[str, Any]]:
    """Return enabled, currently available MCP tools."""
    try:
        return tool_registry.get_enabled_tools() or []
    except Exception:
        return []


def list_runnable_prestart_tools() -> List[Dict[str, Any]]:
    """Return runnable prestart tools without going through the Flask API."""
    try:
        from faymcp import mcp_service
    except Exception:
        return []

    try:
        configs = prestart_registry.get_all()
    except Exception:
        return []

    runnable: List[Dict[str, Any]] = []
    for server in getattr(mcp_service, "mcp_servers", []) or []:
        if not isinstance(server, dict):
            continue
        if server.get("status") != "online":
            continue

        server_id = server.get("id")
        if not server_id:
            continue

        try:
            server_id = int(server_id)
        except Exception:
            continue

        tool_map = configs.get(server_id, {})
        if not isinstance(tool_map, dict) or not tool_map:
            continue

        snapshot = tool_registry.get_server_tools(
            server_id,
            include_disabled=True,
            include_unavailable=False,
        )
        available = {
            tool.get("name"): tool
            for tool in (snapshot or [])
            if isinstance(tool, dict) and tool.get("name")
        }

        for tool_name, cfg in tool_map.items():
            if tool_name not in available:
                continue
            cfg = cfg if isinstance(cfg, dict) else {}
            params = cfg.get("params")
            runnable.append(
                {
                    "server_id": server_id,
                    "server_name": server.get("name", f"Server {server_id}"),
                    "tool": tool_name,
                    "params": params if isinstance(params, dict) else {},
                    "include_history": cfg.get("include_history", True),
                    "allow_function_call": cfg.get("allow_function_call", False),
                }
            )

    return runnable


def call_tool(
    server_id: int,
    tool_name: str,
    params: Optional[Dict[str, Any]] = None,
    *,
    skip_enabled_check: bool = False,
) -> Tuple[bool, Any]:
    """Call an MCP tool through the in-process service."""
    try:
        from faymcp import mcp_service
    except Exception as exc:
        return False, str(exc)

    return mcp_service.call_mcp_tool(
        server_id,
        tool_name,
        params or {},
        skip_enabled_check=skip_enabled_check,
    )
