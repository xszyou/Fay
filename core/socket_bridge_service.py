import asyncio
import websockets
import socket
import threading
import time
import sys
import traceback

try:
    from utils import util
    def _log(msg):
        try:
            util.log(1, msg)
        except Exception:
            print(msg, file=sys.stderr)
except Exception:
    def _log(msg):
        print(msg, file=sys.stderr)

__wss = None

def new_instance():
    global __wss
    if __wss is None:
        __wss = SocketBridgeService()
    return __wss

def _reset_instance():
    global __wss
    __wss = None

class SocketBridgeService:
    def __init__(self):
        self.websockets = {}
        self.sockets = {}
        self.send_locks = {}
        self.running = True
        self.loop = None
        self.tasks = set()
        self.server = None
        self._connect_timeout = 5.0
        self._send_timeout = 10.0

    async def handler(self, websocket, path):
        ws_id = id(websocket)
        self.websockets[ws_id] = websocket
        receive_task = None
        try:
            sock = await self.create_socket_client()
            if sock is None:
                _log(f"[9001] 连接 10001 失败，断开 WebSocket {ws_id}")
                try:
                    await websocket.close()
                except Exception:
                    pass
                return
            self.sockets[ws_id] = sock
            self.send_locks[ws_id] = asyncio.Lock()

            receive_task = asyncio.create_task(self.receive_from_socket(ws_id))
            self.tasks.add(receive_task)
            receive_task.add_done_callback(self.tasks.discard)

            async for message in websocket:
                await self.send_to_socket(ws_id, message)
        except websockets.ConnectionClosed:
            pass
        except Exception:
            _log(f"[9001] handler 异常 ws_id={ws_id}: {traceback.format_exc()}")
        finally:
            if receive_task and not receive_task.done():
                receive_task.cancel()
            self.close_socket_client(ws_id)
            self.websockets.pop(ws_id, None)
            self.send_locks.pop(ws_id, None)

    async def create_socket_client(self):
        loop = asyncio.get_event_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self._connect_timeout)
        try:
            await loop.run_in_executor(None, sock.connect, ('127.0.0.1', 10001))
            sock.settimeout(None)
            return sock
        except Exception:
            _log(f"[9001] 连接 10001 失败: {traceback.format_exc()}")
            try:
                sock.close()
            except Exception:
                pass
            return None

    async def send_to_socket(self, ws_id, message):
        sock = self.sockets.get(ws_id)
        lock = self.send_locks.get(ws_id)
        if sock is None or lock is None:
            return
        try:
            async with lock:
                await asyncio.wait_for(
                    asyncio.to_thread(sock.sendall, message),
                    timeout=self._send_timeout,
                )
        except Exception:
            _log(f"[9001] send_to_socket 异常 ws_id={ws_id}: {traceback.format_exc()}")
            self.close_socket_client(ws_id)

    async def receive_from_socket(self, ws_id):
        sock = self.sockets.get(ws_id)
        websocket = self.websockets.get(ws_id)
        if not sock or not websocket:
            return
        try:
            while self.running:
                data = await asyncio.to_thread(sock.recv, 4096)
                if not data:
                    break
                if not websocket.open:
                    break
                try:
                    await websocket.send(data)
                except websockets.ConnectionClosed:
                    break
                except Exception:
                    _log(f"[9001] websocket.send 异常 ws_id={ws_id}: {traceback.format_exc()}")
                    break
        except asyncio.CancelledError:
            raise
        except Exception:
            _log(f"[9001] receive_from_socket 异常 ws_id={ws_id}: {traceback.format_exc()}")
        finally:
            self.close_socket_client(ws_id)

    def close_socket_client(self, ws_id):
        sock = self.sockets.pop(ws_id, None)
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass

    async def start(self, host='0.0.0.0', port=9001):
        self.server = await websockets.serve(self.handler, host, port)
        _log(f"[9001] socket_bridge_service 已监听 {host}:{port}")
        try:
            await self.server.wait_closed()
        except asyncio.CancelledError:
            pass
        finally:
            await self.shutdown()

    async def shutdown(self):
        if not self.running:
            return
        self.running = False

        for ws_id, ws in list(self.websockets.items()):
            try:
                await ws.close()
            except Exception:
                pass
        self.websockets.clear()

        for ws_id in list(self.sockets.keys()):
            self.close_socket_client(ws_id)
        self.send_locks.clear()

        for task in list(self.tasks):
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()

        if self.server:
            self.server.close()
            try:
                await self.server.wait_closed()
            except Exception:
                pass
            self.server = None

    def start_service(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.start(host='0.0.0.0', port=9001))
        except OSError as e:
            _log(f"[9001] 端口绑定失败（可能被占用）: {e}")
        except Exception:
            _log(f"[9001] start_service 启动异常: {traceback.format_exc()}")
        finally:
            try:
                self.loop.close()
            except Exception:
                pass
            _reset_instance()

if __name__ == '__main__':
    service = new_instance()
    service_thread = threading.Thread(target=service.start_service, daemon=True)
    service_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Initiating shutdown...")
        if service.loop and service.loop.is_running():
            future = asyncio.run_coroutine_threadsafe(service.shutdown(), service.loop)
            try:
                future.result(timeout=5)
                print("Shutdown coroutine completed.")
            except Exception as e:
                print(f"Shutdown exception: {e}", file=sys.stderr)
        service_thread.join(timeout=5)
        print("Service has been shut down.")
