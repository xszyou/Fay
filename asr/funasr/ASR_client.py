import pyaudio
import websockets
import asyncio
from queue import Queue
import argparse
import json

parser = argparse.ArgumentParser()
parser.add_argument("--host", type=str, default="127.0.0.1", required=False, help="host ip, localhost, 0.0.0.0")
parser.add_argument("--port", type=int, default=10197, required=False, help="grpc server port")
parser.add_argument("--chunk_size", type=int, default=160, help="ms")
parser.add_argument("--vad_needed", type=bool, default=True)
args = parser.parse_args()

voices = Queue()

async def record():
    global voices 
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    CHUNK = int(RATE / 1000 * args.chunk_size)

    p = pyaudio.PyAudio()

    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)

    while True:
        data = stream.read(CHUNK)
        voices.put(data)
        await asyncio.sleep(0.01)

async def ws_send(websocket):
    global voices
    print("Started sending data!")
    data_head = {
        'vad_need': args.vad_needed,
        'state': ''
    }
    await websocket.send(json.dumps(data_head))

    while True:
        while not voices.empty():
            data = voices.get()
            voices.task_done()
            try:
                await websocket.send(data)
            except Exception as e:
                print('Exception occurred:', e)
                return  # Return to attempt reconnection
            await asyncio.sleep(0.01)

async def message(websocket):
    while True:
        try:
            print(await websocket.recv())
        except Exception as e:
            print("Exception:", e)
            return  # Return to attempt reconnection

async def ws_client():
    uri = "ws://{}:{}".format(args.host, args.port)
    while True:
        try:
            async with websockets.connect(uri, subprotocols=["binary"], ping_interval=None) as websocket:
                task1 = asyncio.create_task(record())
                task2 = asyncio.create_task(ws_send(websocket))
                task3 = asyncio.create_task(message(websocket))
                await asyncio.gather(task1, task2, task3)
        except Exception as e:
            print("WebSocket connection failed: ", e)
            await asyncio.sleep(5)  # Wait for 5 seconds before trying to reconnect

asyncio.get_event_loop().run_until_complete(ws_client())