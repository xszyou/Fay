import asyncio
import websockets
import socket
import threading
import time

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
        self.server = None
        self.event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.event_loop)

    async def handler(self, websocket, path):
        ws_id = id(websocket)
        self.websockets[ws_id] = websocket
        try:
            if ws_id not in self.sockets:
                self.sockets[ws_id] = await self.create_socket_client()
            asyncio.create_task(self.receive_from_socket(ws_id))
            async for message in websocket:
                await self.send_to_socket(ws_id, message)
        except websockets.ConnectionClosed:
            pass
        finally:
            self.close_socket_client(ws_id)

    async def create_socket_client(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('127.0.0.1', 10001))
        return sock

    async def send_to_socket(self, ws_id, message):
        sock = self.sockets.get(ws_id)
        if sock:
            asyncio.create_task(self.socket_send(sock, message))

    async def socket_send(self, sock, message):
        await asyncio.to_thread(sock.sendall, message)

    async def receive_from_socket(self, ws_id):
        sock = self.sockets.get(ws_id)
        while True:
            data = await asyncio.to_thread(sock.recv, 1024)
            if data:
                await self.message_queue.put((ws_id, data))

    async def process_message_queue(self):
        while True:
            if not self.running:
                break
            ws_id, data = await self.message_queue.get()
            websocket = self.websockets.get(ws_id)
            if websocket.open:
                await websocket.send(data)
            self.message_queue.task_done()

    def close_socket_client(self, ws_id):
        sock = self.sockets.pop(ws_id, None)
        if sock:
            sock.close()

    async def start(self, host='0.0.0.0', port=9001):
        self.server = await websockets.serve(self.handler, host, port, loop=self.event_loop)
        asyncio.create_task(self.process_message_queue())
        await asyncio.Future()  

    async def shutdown(self):
        self.running = False
        if self.server:
            for ws in self.websockets.values():
                await ws.close()
            if hasattr(self.server, 'close'):
                self.server.close()
            await asyncio.gather(*[w.wait_closed() for w in self.websockets.values()])
        for sock in self.sockets.values():
            sock.close()
        if self.server:
            await self.server.wait_closed()

    def stop_server(self):
        self.event_loop.call_soon_threadsafe(self.shutdown)
        self.event_loop.run_until_complete(self.shutdown())
        self.event_loop.close()

    def start_service(self):
        self.event_loop.run_until_complete(self.start(host='0.0.0.0', port=9001))
        try:
            self.event_loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop_server()

if __name__ == '__main__':
    service = new_instance()
    service_thread = threading.Thread(target=service.start_service)
    service_thread.start()

    # 等待一些时间或者直到收到停止信号
    try:
        while service.running:
            time.sleep(1)
    except KeyboardInterrupt:
        service.stop_server()
        service_thread.join()