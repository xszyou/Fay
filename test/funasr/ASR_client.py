import pyaudio
import websockets
import asyncio
from queue import Queue
import argparse
import json

parser = argparse.ArgumentParser()
parser.add_argument("--host",
                    type=str,
                    default="172.16.77.144",
                    required=False,
                    help="host ip, localhost, 0.0.0.0")
parser.add_argument("--port",
                    type=int,
                    default=10194,
                    required=False,
                    help="grpc server port")
parser.add_argument("--chunk_size",
                    type=int,
                    default=160,
                    help="ms")
parser.add_argument("--vad_needed",
                    type=bool,
                    default=True)
args = parser.parse_args()

voices = Queue()

async def record():
    global voices 
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    CHUNK = int(RATE / 1000 * args.chunk_size)

    p = pyaudio.PyAudio()

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    while True:
        data = stream.read(CHUNK)
        voices.put(data)
        await asyncio.sleep(0.01)

async def ws_send():
    global voices
    global websocket
    print("started to sending data!")
    #设置传入参数，是否需要vad
    data_head = {
        'vad_need': args.vad_needed,
        'state': ''
    }
    if type(data_head) == dict:
        await websocket.send(json.dumps(data_head))

    while True:
        while not voices.empty():
            data = voices.get()
            voices.task_done()
            try:

                if type(data) == bytes:
                    await websocket.send(data) # 通过ws对象发送数据
            except Exception as e:
                print('Exception occurred:', e)
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.01)

async def message():
    global websocket
    while True:
        try:
            print(await websocket.recv())
        except Exception as e:
            print("Exception:", e)          

async def ws_client():
    global websocket # 定义一个全局变量ws，用于保存websocket连接对象
    # uri = "ws://11.167.134.197:8899"
    uri = "ws://{}:{}".format(args.host, args.port)
    async for websocket in websockets.connect(uri, subprotocols=["binary"], ping_interval=None):
        task1 = asyncio.create_task(record()) # 创建一个后台任务录音
        task2 = asyncio.create_task(ws_send()) # 创建一个后台任务发送
        task3 = asyncio.create_task(message()) # 创建一个后台接收消息的任务
        await asyncio.gather(task1,  task2, task3)

asyncio.get_event_loop().run_until_complete(ws_client()) # 启动协程
asyncio.get_event_loop().run_forever()
