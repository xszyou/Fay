from asyncio import AbstractEventLoop

import websockets
import asyncio
import json

from websockets.legacy.server import Serve

from scheduler.thread_manager import MyThread


class MyServer:
    def __init__(self, host='127.0.0.1', port=10000):
        self.__host = host  # ip
        self.__port = port  # 端口号
        self.__listCmd = []  # 要发送的信息的列表
        self.__server: Serve = None
        self.__message_value = None  # client返回消息的value
        self.__event_loop: AbstractEventLoop = None
        self.__running = True
        self.__pending = None

    def __del__(self):
        self.stop_server()

    async def __consumer_handler(self, websocket, path):
        async for message in websocket:
            await self.__consumer(message)

    async def __producer_handler(self, websocket, path):
        while self.__running:
            await asyncio.sleep(0.000001)
            message = await self.__producer()
            if message:
                await websocket.send(message)
                # util.log('发送 {}'.format(message))

    async def __handler(self, websocket, path):
        consumer_task = asyncio.ensure_future(self.__consumer_handler(websocket, path))
        producer_task = asyncio.ensure_future(self.__producer_handler(websocket, path))
        done, self.__pending = await asyncio.wait([consumer_task, producer_task], return_when=asyncio.FIRST_COMPLETED, )
        for task in self.__pending:
            task.cancel()

    # 接收处理
    async def __consumer(self, message):
        pass
        # print('recv message: {0}'.format(message))

    # 发送处理
    async def __producer(self):
        if len(self.__listCmd) > 0:
            return self.__listCmd.pop(0)
        else:
            return None

    # 创建server
    def __connect(self):
        self.__event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.__event_loop)
        self.__isExecute = True
        if self.__server:
            print('server already exist')
            return
        self.__server = websockets.serve(self.__handler, self.__host, self.__port)
        asyncio.get_event_loop().run_until_complete(self.__server)
        asyncio.get_event_loop().run_forever()

    # 往要发送的命令列表中，添加命令
    def add_cmd(self, content):
        if not self.__running:
            return
        jsonObj = json.dumps(content)
        self.__listCmd.append(jsonObj)
        # util.log('命令 {}'.format(content))

    # 开启服务
    def start_server(self):
        MyThread(target=self.__connect).start()

    # 关闭服务
    def stop_server(self):
        self.__running = False
        if self.__server is None:
            return
        self.__server.ws_server.close()
        self.__server = None
        try:
            all_tasks = asyncio.all_tasks(self.__event_loop)
            for task in all_tasks:
                # print(task.cancel())
                while not task.cancel():
                    print("无法关闭！")
            self.__event_loop.stop()
            self.__event_loop.close()
        except BaseException as e:
            print("Error: {}".format(e))


__instance: MyServer = None
__web_instance: MyServer = None


def new_instance(host='127.0.0.1', port=10000) -> MyServer:
    global __instance
    if __instance is None:
        __instance = MyServer(host, port)
    return __instance


def new_web_instance(host='127.0.0.1', port=10000) -> MyServer:
    global __web_instance
    if __web_instance is None:
        __web_instance = MyServer(host, port)
    return __web_instance


def get_instance() -> MyServer:
    return __instance


def get_web_instance() -> MyServer:
    return __web_instance
