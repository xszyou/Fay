"""Focused MCP checks; run with python -m unittest test.test_mcp_streamable_http -v.

Only FAY_MCP_LIVE=1 enables the anonymous public documentation lookup.
"""
from contextlib import contextmanager, ExitStack
import importlib
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

from mcp.server.fastmcp import FastMCP
import uvicorn

from faymcp import mcp_client, tool_registry, resource_registry, prestart_registry

QUESTION = "How does Python asyncio.wait_for handle a timeout?"
SOURCE = "https://docs.python.org/3/library/asyncio-task.html"


def documentation_server():
    server = FastMCP("public-documentation", stateless_http=True, json_response=True)

    @server.tool()
    def lookup(question: str) -> str:
        if question != QUESTION:
            raise ValueError("Only the public documentation question is expected")
        return f"asyncio.wait_for cancels the task on timeout. Source: {SOURCE}"

    return server


@contextmanager
def loopback_server(transport="streamable_http"):
    """Run the SDK server on an OS-assigned loopback port and audit requests."""
    server = documentation_server()
    app = server.sse_app() if transport == "sse" else server.streamable_http_app()
    requests = []
    unavailable = threading.Event()

    async def audited(scope, receive, send):
        if scope["type"] == "http":
            entry = {"headers": dict(scope["headers"]), "body": b""}
            requests.append(entry)
            if unavailable.is_set():
                await send({"type": "http.response.start", "status": 503, "headers": []})
                await send({"type": "http.response.body", "body": b"unavailable"})
                return

            async def capture():
                message = await receive()
                entry["body"] += message.get("body", b"")
                return message

            await app(scope, capture, send)
        else:
            await app(scope, receive, send)

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        runner = uvicorn.Server(uvicorn.Config(audited, log_level="error"))
        thread = threading.Thread(target=runner.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 5
            while not runner.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(0.01)
            if not runner.started:
                raise RuntimeError("Loopback MCP server did not start")
            path = "/sse" if transport == "sse" else "/mcp"
            yield f"http://127.0.0.1:{port}{path}", requests, unavailable
        finally:
            runner.should_exit = True
            thread.join(timeout=5)


@contextmanager
def isolated_service():
    """Use real Fay routes/client; replace only UI logging and persisted state."""
    log = types.ModuleType("utils.util")
    log.log = lambda *args, **kwargs: None
    with patch.dict(sys.modules, {"utils.util": log}):
        service = importlib.import_module("faymcp.mcp_service")
    with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
        for name, value in (("mcp_servers", []), ("mcp_clients", {}), ("mcp_tool_states", {}),
                            ("util", log), ("MCP_DATA_FILE", f"{directory}/servers.json"),
                            ("MCP_TOOL_STATES_FILE", f"{directory}/tools.json")):
            stack.enter_context(patch.object(service, name, value))
        stack.enter_context(patch.object(resource_registry, "_STATES_FILE", f"{directory}/resources.json"))
        stack.enter_context(patch.object(prestart_registry, "_data_file", f"{directory}/prestart.json"))
        stack.enter_context(patch.object(prestart_registry, "_prestart", {}))
        clients = []
        original = service.McpClient

        def tracked(*args, **kwargs):
            client = original(*args, **kwargs)
            clients.append(client)
            return client

        stack.enter_context(patch.object(service, "McpClient", tracked))
        try:
            yield service, service.app.test_client()
        finally:
            for client in clients:
                close_client(client)
                if client.server_id is not None:
                    tool_registry.remove_server(client.server_id)
                    resource_registry.clear_server_resources(client.server_id)


def close_client(client):
    client.disconnect()
    client.event_loop.call_soon_threadsafe(client.event_loop.stop)
    client._loop_thread.join(timeout=5)
    client.event_loop.close()


class StreamableHttpTests(unittest.TestCase):
    def test_management_workflow_and_scoped_permission(self):
        with loopback_server() as (url, requests, unavailable), isolated_service() as (service, api):
            page = api.get("/Page3").get_data(as_text=True)
            self.assertEqual(page.count('<option value="streamable_http">'), 2)
            response = api.post("/api/mcp/servers", json={
                "name": "Public docs", "transport": "streamable_http", "ip": url,
            })
            self.assertEqual(response.status_code, 201)
            server = response.json["server"]
            sid = server["id"]
            self.assertFalse(server["autostart"])
            # Editing must retain the remote URL/key configuration.
            response = api.put(f"/api/mcp/servers/{sid}", json={
                "transport": "streamable_http", "ip": url, "key": "",
            })
            self.assertTrue(response.json["success"])
            response = api.post(f"/api/mcp/servers/{sid}/connect")
            self.assertTrue(response.json["success"], response.json)
            self.assertEqual(service.mcp_clients[sid].transport, "streamable_http")
            tools = api.get(f"/api/mcp/servers/{sid}/tools").json["tools"]
            self.assertEqual([tool["name"] for tool in tools], ["lookup"])
            payload = {"method": "lookup", "params": {"question": QUESTION}}
            response = api.post(f"/api/mcp/servers/{sid}/call", json=payload)
            self.assertTrue(response.json["success"])
            self.assertIn(SOURCE, json.dumps(response.json["result"]))
            bodies = [json.loads(r["body"]) for r in requests if r["body"]]
            self.assertIn("initialize", [body["method"] for body in bodies])
            calls = [body for body in bodies if body["method"] == "tools/call"]
            self.assertEqual(calls[0]["params"], {"name": "lookup", "arguments": {"question": QUESTION}})
            count = len(calls)
            api.post(f"/api/mcp/servers/{sid}/tools/lookup/toggle", json={"enabled": False})
            response = api.post(f"/api/mcp/servers/{sid}/call", json=payload)
            self.assertFalse(response.json["success"])
            self.assertIn("禁用", response.json["error"])
            self.assertEqual(sum(b'"tools/call"' in r["body"] for r in requests), count)
            other = api.post(f"/api/mcp/servers/{sid + 1}/call", json=payload)
            self.assertFalse(other.json["success"])
            api.post(f"/api/mcp/servers/{sid}/tools/lookup/toggle", json={"enabled": True})
            unavailable.set()
            service.mcp_clients[sid].call_timeout_seconds = 1
            response = api.post(f"/api/mcp/servers/{sid}/call", json=payload)
            self.assertFalse(response.json["success"])
            self.assertIn("error", response.json)
            for request in requests:
                self.assertEqual(request["headers"].get(b"user-agent"), b"Fay-MCP/1.0")
                self.assertFalse({b"authorization", b"cookie", b"x-api-key", b"proxy-authorization"}
                                 & request["headers"].keys())

    def test_remote_credentials_and_legacy_sse(self):
        for transport in ("streamable_http", "sse"):
            with self.subTest(transport=transport), loopback_server(transport) as (url, requests, _):
                client = mcp_client.McpClient(url, api_key="loopback-test-token", transport=transport)
                try:
                    self.assertTrue(client.connect()[0])
                    self.assertEqual([tool["name"] for tool in client.list_tools()], ["lookup"])
                    success, result = client.call_tool("lookup", {"question": QUESTION})
                    self.assertTrue(success)
                    self.assertIn(SOURCE, result.content[0].text)
                    self.assertTrue(all(r["headers"].get(b"authorization") == b"Bearer loopback-test-token"
                                        for r in requests))
                finally:
                    close_client(client)

    def test_stdio(self):
        client = mcp_client.McpClient(transport="stdio", stdio_config={
            "command": sys.executable, "args": [str(Path(__file__).resolve()), "--stdio"],
            "env": {"PYTHONPATH": str(Path(__file__).resolve().parents[1])},
        })
        try:
            self.assertTrue(client.connect()[0])
            success, result = client.call_tool("lookup", {"question": QUESTION})
            self.assertTrue(success)
            self.assertIn(SOURCE, result.content[0].text)
        finally:
            close_client(client)

    def test_missing_transport_dependency_and_unavailable_server(self):
        with patch.object(mcp_client, "streamablehttp_client", None):
            client = mcp_client.McpClient("http://127.0.0.1:1/mcp", transport="streamable_http")
            try:
                success, message = client.connect()
                self.assertFalse(success)
                self.assertIn("pip install -U mcp", message)
            finally:
                close_client(client)
            # The default still uses SSE even when Streamable HTTP is unavailable.
            with loopback_server("sse") as (url, _, _):
                client = mcp_client.McpClient(url)
                try:
                    self.assertEqual(client.transport, "sse")
                    self.assertTrue(client.connect()[0])
                finally:
                    close_client(client)
        with loopback_server() as (url, _, unavailable):
            unavailable.set()
            client = mcp_client.McpClient(url, transport="streamable_http")
            try:
                self.assertFalse(client.connect()[0])
                self.assertFalse(client.connected)
                self.assertEqual(client.get_cached_tools(), [])
            finally:
                close_client(client)


@unittest.skipUnless(os.getenv("FAY_MCP_LIVE") == "1", "opt-in public network lookup")
class AnonymousLiveTests(unittest.TestCase):
    def test_public_python_documentation_through_fay_routes(self):
        import httpx
        observed = []
        original_send = httpx.AsyncClient.send
        issued_cookie_names = set()

        async def audit(client, request, *args, **kwargs):
            self.assertEqual(request.url.host, "mcp.parallel.ai")
            self.assertEqual(request.headers.get("User-Agent"), "Fay-MCP/1.0")
            self.assertFalse({"authorization", "x-api-key", "proxy-authorization"}
                             & request.headers.keys())
            cookie_names = {part.strip().split("=", 1)[0]
                            for part in request.headers.get("cookie", "").split(";") if part.strip()}
            self.assertLessEqual(cookie_names, issued_cookie_names)
            self.assertLessEqual(cookie_names, {"__cf_bm", "_cfuvid"})
            observed.append(request.method)
            response = await original_send(client, request, *args, **kwargs)
            issued_cookie_names.update(response.cookies.keys())
            return response

        with patch.object(httpx.AsyncClient, "send", audit), isolated_service() as (_, api):
            response = api.post("/api/mcp/servers", json={
                "name": "Public documentation", "transport": "streamable_http",
                "ip": "https://mcp.parallel.ai/mcp?tools=web_search", "key": "",
            })
            sid = response.json["server"]["id"]
            response = api.post(f"/api/mcp/servers/{sid}/connect")
            self.assertTrue(response.json["success"], response.json)
            tools = api.get(f"/api/mcp/servers/{sid}/tools").json["tools"]
            self.assertEqual([tool["name"] for tool in tools], ["web_search"])
            response = api.post(f"/api/mcp/servers/{sid}/call", json={
                "method": "web_search", "params": {
                    "objective": QUESTION,
                    "search_queries": ["site:docs.python.org asyncio wait_for timeout"],
                },
            })
            self.assertTrue(response.json["success"], response.json)
            result = response.json["result"]
            self.assertFalse(result.get("isError", False), result)
            sources = result["structuredContent"]["results"]
            self.assertIn(SOURCE, [source["url"] for source in sources])
            print(f"Anonymous Fay lookup returned official source: {SOURCE}; "
                  f"observed {len(observed)} requests with Fay-MCP/1.0 and no authorization/API key headers; "
                  f"only server-issued cookie names: {sorted(issued_cookie_names)}")


if __name__ == "__main__":
    if "--stdio" in sys.argv:
        documentation_server().run(transport="stdio")
    else:
        unittest.main()
