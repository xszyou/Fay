import websocket
import datetime
import threading
import requests
import vlc  # 使用 VLC 播放音频
import time
import json
import queue

# 配置项
config = {
    "enable_auto_get": True,  # 设置是否启用主动获取播放项
     "url" : "127.0.0.1" #服务端Url
}

audio_queue = queue.Queue()
player = None

def on_message(ws, message):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    print(f"[{timestamp}] Received message: {message}")

    try:
        # 解析收到的 JSON 数据
        data = json.loads(message)
        if "Data" in data and "HttpValue" in data["Data"]:
            audio_url = data["Data"]["HttpValue"]
            audio_queue.put(audio_url)
            process_audio_queue()
    except json.JSONDecodeError as e:
        print(f"[Error] Failed to parse message as JSON: {e}")

def process_audio_queue():
    global player
    if not player or player.get_state() == vlc.State.Ended:
        if not audio_queue.empty():
            audio_url = audio_queue.get()
            play_audio(audio_url)
         

def play_audio(url):
    global player
    # 使用 VLC 播放音频
    player = vlc.MediaPlayer(url)
    player.play()

    # 启动线程等待音频播放结束
    threading.Thread(target=wait_for_audio_end).start()

def wait_for_audio_end():
    global player
    # 等待音频播放结束
    while True:
        state = player.get_state()
        if state == vlc.State.Ended:
            break
        time.sleep(0.01)
    # 播放结束后处理队列
    process_audio_queue()

def on_error(ws, error):
    print(f"[Error] {error}")

def on_close(ws, close_status_code, close_msg):
    print("### Connection closed ###")

def on_open(ws):
    print("### Connection opened ###")

if __name__ == "__main__":
    # 启用 WebSocket 调试信息（可选）
    # websocket.enableTrace(True)

    # 替换为您的 WebSocket 服务器地址
    ws_url = f"ws://{config['url']}:10002"

    ws = websocket.WebSocketApp(ws_url,
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)

    # 运行 WebSocket 客户端
    wst = threading.Thread(target=ws.run_forever)
    wst.daemon = True
    wst.start()

    try:
        while True:
            pass  # 保持主线程运行
    except KeyboardInterrupt:
        ws.close()
        print("Exited")