import asyncio
import websockets
import argparse
import json
from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess
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
model_dir = "iic/SenseVoiceSmall"

asr_model = AutoModel(
    model=model_dir,
    trust_remote_code=True,
    remote_code="./model.py",
    vad_model="fsmn-vad",
    vad_kwargs={"max_single_segment_time": 30000},
    device="cuda:1",
)
print("model loaded")
websocket_users = {}
task_queue = asyncio.Queue()

async def ws_serve(websocket, path):
    global websocket_users
    user_id = id(websocket)
    websocket_users[user_id] = websocket
    try:
        async for message in websocket:
            if isinstance(message, str):
                data = json.loads(message)
                if 'url' in data:
                    await task_queue.put((websocket, data['url']))
    except websockets.exceptions.ConnectionClosed as e:
        logger.info(f"Connection closed: {e.reason}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        logger.info(f"Cleaning up connection for user {user_id}")
        if user_id in websocket_users:
            del websocket_users[user_id]
        await websocket.close()
        logger.info("WebSocket closed")

async def worker():
    while True:
        websocket, url = await task_queue.get()
        if websocket.open:
            await process_wav_file(websocket, url)
        else:
            logger.info("WebSocket connection is already closed when trying to process file")
        task_queue.task_done()

async def process_wav_file(websocket, url):
    #热词
    param_dict = {"sentence_timestamp": False}
    with open("data/hotword.txt", "r", encoding="utf-8") as f:
        lines = f.readlines()
        lines = [line.strip() for line in lines]
    hotword = " ".join(lines)
    print(f"热词：{hotword}")
    param_dict["hotword"] = hotword
    wav_path = url
    try:
        res = asr_model.generate(input=wav_path, cache={},
    language="auto",  # "zh", "en", "yue", "ja", "ko", "nospeech"
    use_itn=True,
    batch_size_s=60,
    merge_vad=True,  #
    merge_length_s=15, **param_dict)
        if res:
            if 'text' in res[0] and websocket.open:
                text = rich_transcription_postprocess(res[0]["text"])
                await websocket.send(text)
    except Exception as e:
        print(f"Error during model.generate: {e}")
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)

async def main():
    start_server = websockets.serve(ws_serve, args.host, args.port, subprotocols=["binary"], ping_interval=10)
    await start_server
    worker_task = asyncio.create_task(worker())
    await worker_task

# 使用 asyncio 运行主函数
asyncio.run(main())