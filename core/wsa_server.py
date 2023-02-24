from asyncio import AbstractEventLoop

import websockets
import asyncio
import json
from abc import abstractmethod
from websockets.legacy.server import Serve

from scheduler.thread_manager import MyThread
from utils import util


class MyServer:
    def __init__(self, host='0.0.0.0', port=10000):
        self.__host = host  # ip
        self.__port = port  # 端口号
        self.__listCmd = []  # 要发送的信息的列表
        self.__server: Serve = None
        self.__message_value = None  # client返回消息的value
        self.__event_loop: AbstractEventLoop = None
        self.__running = True
        self.__pending = None
        self.isConnect = False

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
        isConnect = True
        util.log(1,"websocket连接上:{}".format(self.__port))
        self.on_connect_handler()
        consumer_task = asyncio.ensure_future(self.__consumer_handler(websocket, path))
        producer_task = asyncio.ensure_future(self.__producer_handler(websocket, path))
        done, self.__pending = await asyncio.wait([consumer_task, producer_task], return_when=asyncio.FIRST_COMPLETED, )
        for task in self.__pending:
            task.cancel()
            isConnect = False
            util.log(1,"websocket连接断开:{}".format(self.__port))

    # 接收处理
    async def __consumer(self, message):
        self.on_revice_handler(message)

    # 发送处理
    async def __producer(self):
        if len(self.__listCmd) > 0:
            return self.__listCmd.pop(0)
        else:
            return None


    #Edit by xszyou on 20230113:通过继承此类来实现服务端的接收处理逻辑
    @abstractmethod
    def on_revice_handler(self, message):
        pass
    #Edit by xszyou on 20230114:通过继承此类来实现服务端的连接处理逻辑
    @abstractmethod
    def on_connect_handler(self):
        pass
    

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
        isConnect = False
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

class HumanServer(MyServer):
    def __init__(self, host='0.0.0.0', port=10000):
        super().__init__(host, port)

    def on_revice_handler(self, message):
        pass
    
    def on_connect_handler(self):
        pass

class WebServer(MyServer):
    def __init__(self, host='0.0.0.0', port=10000):
        super().__init__(host, port)

    def on_revice_handler(self, message):
        pass
    
    def on_connect_handler(self):
        self.add_cmd({"panelMsg": "使用提示：直播，请关闭麦克风。连接数字人，请关闭面板播放。"})

class TestServer(MyServer):
    def __init__(self, host='0.0.0.0', port=10000):
        super().__init__(host, port)

    def on_revice_handler(self, message):
        print(message)
    
    def on_connect_handler(self):
        print("连接上了")




__instance: MyServer = None
__web_instance: MyServer = None


def new_instance(host='0.0.0.0', port=10000) -> MyServer:
    global __instance
    if __instance is None:
        __instance = HumanServer(host, port)
    return __instance


def new_web_instance(host='0.0.0.0', port=10000) -> MyServer:
    global __web_instance
    if __web_instance is None:
        __web_instance = WebServer(host, port)
    return __web_instance


def get_instance() -> MyServer:
    return __instance


def get_web_instance() -> MyServer:
    return __web_instance

if __name__ == '__main__':
    testServer = TestServer(host='0.0.0.0', port=10000)
    testServer.start_server()