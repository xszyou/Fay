import websocket
import pyaudio
import time
import pygame
import threading
import os
import sys
from websocket import WebSocketApp
from pydub import AudioSegment
from io import BytesIO

# Global variables
is_speaking = False
receive_buffer = b''
connected = False  # 跟踪连接状态

# Ensure the 'samples' directory exists
os.makedirs("samples", exist_ok=True)

def get_stream():
    """Initialize and return the audio input stream."""
    paudio = pyaudio.PyAudio()
    device_id = 0  # Adjust this if you have multiple input devices
    if device_id < 0:
        print("No input device found.")
        return None
    stream = paudio.open(
        input_device_index=device_id,
        rate=16000,
        format=pyaudio.paInt16,
        channels=1,
        input=True
    )
    return stream

def send_audio(ws):
    """Continuously read audio from the microphone and send it over WebSocket."""
    global is_speaking, connected
    
    # 等待连接完全建立
    time.sleep(1)
    
    stream = get_stream()
    if not stream:
        print("无法获取音频流")
        return
        
    print("开始传输音频数据...")
    
    while stream and connected:
        try:
            if is_speaking:
                time.sleep(0.01)
                continue
                
            # 读取音频数据
            data = stream.read(1024, exception_on_overflow=False)
            
            # 只有建立连接后才发送数据
            if connected:
                ws.send(data, opcode=websocket.ABNF.OPCODE_BINARY)
                
            # 添加小延迟以匹配socket版本
            time.sleep(0.005)
            
            # 打印进度
            print(".", end="", flush=True)
        except Exception as e:
            print(f"\n发送音频时出错: {e}")
            break
    
    # 资源清理
    if stream:
        stream.stop_stream()
        stream.close()
    print("\n音频传输停止")

def process_receive_buffer():
    """Process the receive buffer to extract and play complete audio files."""
    global receive_buffer, is_speaking
    
    # 定义开始和结束标记
    start_marker = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08"
    end_marker = b"\x08\x07\x06\x05\x04\x03\x02\x01\x00"
    
    # 查找开始标记
    start_index = receive_buffer.find(start_marker)
    if start_index == -1:
        # 没有找到开始标记，清空缓冲区
        receive_buffer = b''
        return
    
    # 查找结束标记
    end_index = receive_buffer.find(end_marker, start_index + len(start_marker))
    if end_index == -1:
        # 结束标记尚未到达，等待更多数据
        return
    
    # 提取开始和结束标记之间的音频数据
    filedata = receive_buffer[start_index + len(start_marker):end_index]
    # 移除心跳或不需要的字节
    filedata = filedata.replace(b'\xf0\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8', b"")
    
    print(f"\n接收到音频数据，长度: {len(filedata)} 字节")
    
    # 保存并播放音频
    timestamp = int(time.time())
    filename = f"samples/recv_{timestamp}.mp3"
    with open(filename, 'wb') as wf:
        wf.write(filedata)
    
    # 播放音频
    is_speaking = True
    pygame.mixer.music.load(filename)
    pygame.mixer.music.play()
    
    # 等待播放结束
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)
    
    is_speaking = False
    
    # 更新缓冲区
    receive_buffer = receive_buffer[end_index + len(end_marker):]

def on_message(ws, message):
    """Callback when a message is received from the WebSocket."""
    global receive_buffer
    if isinstance(message, bytes):
        receive_buffer += message
        process_receive_buffer()
    else:
        # 处理文本消息
        print(f"收到文本消息: {message}")

def on_error(ws, error):
    """Callback when an error occurs."""
    print(f"WebSocket错误: {error}")

def on_close(ws, close_status_code, close_msg):
    """Callback when the WebSocket connection is closed."""
    global connected
    connected = False
    print(f"WebSocket连接关闭，代码: {close_status_code}, 消息: {close_msg}")

def on_open(ws):
    """Callback when the WebSocket connection is opened."""
    global connected
    print("WebSocket连接已建立")
    
    # 初始化音频播放器
    pygame.mixer.init()
    
    # 连接已建立
    connected = True
    
    # 发送初始配置消息
    try:
        # 发送用户名
        print("发送用户名...")
        username_message = b"<username>user_device_32_6</username>"
        ws.send(username_message, opcode=websocket.ABNF.OPCODE_BINARY)
        
        # 可选：发送输出设置
        # output_message = b"<output>False</output>"
        # ws.send(output_message, opcode=websocket.ABNF.OPCODE_BINARY)
    except Exception as e:
        print(f"发送初始消息时出错: {e}")
    
    # 启动音频发送线程
    print("启动音频发送线程...")
    send_thread = threading.Thread(target=send_audio, args=(ws,))
    send_thread.daemon = True
    send_thread.start()

if __name__ == "__main__":
    # WebSocket服务器URL
    ws_url = "ws://127.0.0.1:9001"
    
    # 创建WebSocketApp实例
    ws_app = WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    print(f"正在连接WebSocket服务器: {ws_url}...")
    
    # 设置ping间隔(与socket类似保持连接)
    ws_app.run_forever(ping_interval=30)
