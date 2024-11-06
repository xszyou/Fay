import asyncio
import websockets
import socket
import threading
import time
import sys

__wss = None

def new_instance():
    global __wss
    if __wss is None:
        __wss = SocketBridgeService()
    return __wss

class SocketBridgeService:
    def __init__(self):
        self.websockets = {}  
        self.sockets = {}     
        self.message_queue = asyncio.Queue()  
        self.running = True
        self.loop = None
        self.tasks = set()
        self.server = None

    async def handler(self, websocket, path):
        ws_id = id(websocket)
        self.websockets[ws_id] = websocket
        try:
            if ws_id not in self.sockets:
                sock = await self.create_socket_client()
                if sock:
                    self.sockets[ws_id] = sock
                else:
                    print(f"Failed to connect TCP socket for WebSocket {ws_id}")
                    await websocket.close()
                    return
            receive_task = asyncio.create_task(self.receive_from_socket(ws_id))
            self.tasks.add(receive_task)
            receive_task.add_done_callback(self.tasks.discard)
            async for message in websocket:
                await self.send_to_socket(ws_id, message)
        except websockets.ConnectionClosed:
            pass
        except Exception as e:
            pass
        finally:
            self.close_socket_client(ws_id)
            self.websockets.pop(ws_id, None)

    async def create_socket_client(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect(('127.0.0.1', 10001))
            sock.setblocking(True)  # 设置为阻塞模式
            return sock
        except Exception as e:
            return None

    async def send_to_socket(self, ws_id, message):
        sock = self.sockets.get(ws_id)
        if sock:
            try:
                await asyncio.to_thread(sock.sendall, message)
            except Exception as e:
                self.close_socket_client(ws_id)

    async def receive_from_socket(self, ws_id):
        sock = self.sockets.get(ws_id)
        if not sock:
            return
        try:
            while self.running:
                data = await asyncio.to_thread(sock.recv, 4096)
                if data:
                    await self.message_queue.put((ws_id, data))
                else:
                    break
        except Exception as e:
            pass
        finally:
            self.close_socket_client(ws_id)

    async def process_message_queue(self):
        while self.running or not self.message_queue.empty():
            try:
                ws_id, data = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                websocket = self.websockets.get(ws_id)
                if websocket and websocket.open:
                    try:
                        await websocket.send(data)
                    except Exception as e:
                        pass
                self.message_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                pass

    def close_socket_client(self, ws_id):
        sock = self.sockets.pop(ws_id, None)
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception as e:
                pass
                # print(f"Error shutting down socket for WebSocket {ws_id}: {e}", file=sys.stderr)
            sock.close()

    async def start(self, host='0.0.0.0', port=9001):
        self.server = await websockets.serve(self.handler, host, port)
        process_task = asyncio.create_task(self.process_message_queue())
        self.tasks.add(process_task)
        process_task.add_done_callback(self.tasks.discard)
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
            except Exception as e:
                pass
                # print(f"Error closing WebSocket {ws_id}: {e}", file=sys.stderr)
        self.websockets.clear()

        for ws_id, sock in list(self.sockets.items()):
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception as e:
                pass
                # print(f"Error shutting down socket for WebSocket {ws_id}: {e}", file=sys.stderr)
            sock.close()
        self.sockets.clear()

        await self.message_queue.join()

        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()

        if self.server:
            self.server.close()
            await self.server.wait_closed()


    def start_service(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.start(host='0.0.0.0', port=9001))
        except Exception as e:
            pass
            # print(f"Service exception: {e}", file=sys.stderr)
        finally:
            self.loop.close()

if __name__ == '__main__':
    service = new_instance()
    service_thread = threading.Thread(target=service.start_service, daemon=True)
    service_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # 在服务的事件循环中运行 shutdown 协程
        print("Initiating shutdown...")
        if service.loop and service.loop.is_running():
            future = asyncio.run_coroutine_threadsafe(service.shutdown(), service.loop)
            try:
                future.result()  # 等待关闭完成
                print("Shutdown coroutine completed.")
            except Exception as e:
                print(f"Shutdown exception: {e}", file=sys.stderr)
        service_thread.join()
        print("Service has been shut down.")
