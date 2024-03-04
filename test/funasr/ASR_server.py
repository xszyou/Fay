import asyncio
import websockets
import numpy as np
from queue import Queue
import threading
import argparse
import json
from funasr import AutoModel
import wave
import numpy as np
import tempfile
import os

# 设置日志级别
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.CRITICAL)

# 解析命令行参数
parser = argparse.ArgumentParser()
parser.add_argument("--host", type=str, default="0.0.0.0", help="host ip, localhost, 0.0.0.0")
parser.add_argument("--port", type=int, default=10197, help="grpc server port")
parser.add_argument("--ngpu", type=int, default=1, help="0 for cpu, 1 for gpu")
args = parser.parse_args()

# 初始化模型
print("model loading")
asr_model = AutoModel(model="paraformer-zh", model_revision="v2.0.4",
                  vad_model="fsmn-vad", vad_model_revision="v2.0.4",
                  punc_model="ct-punc-c", punc_model_revision="v2.0.4")
print("model loaded")
websocket_users = {}

async def ws_serve(websocket, path):
    global websocket_users
    user_id = id(websocket)
    try:
        async for message in websocket:
            if isinstance(message, str):
                data = json.loads(message)
                if 'url' in data:
                    await process_wav_file(websocket, data['url'], user_id)
    finally:
        if user_id in websocket_users:
            del websocket_users[user_id]

async def process_wav_file(websocket, message, user_id):
    wav_path = message
    try:
        res = asr_model.generate(input=wav_path)
        os.remove(wav_path)
        if 'text' in res[0]: 
            await websocket.send(res[0]['text'])
    except Exception as e:
        logger.error(f"Error during model.generate: {e}")

def send_recognition_result(websocket, text):
    asyncio.run_coroutine_threadsafe(websocket.send(text), asyncio.get_event_loop())

start_server = websockets.serve(ws_serve, args.host, args.port, subprotocols=["binary"], ping_interval=None)
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()