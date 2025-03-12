import socket
import pyaudio
import time
import pygame

from threading import Thread
import wave
is_speaking = False
def get_stream():
        paudio = pyaudio.PyAudio()
        device_id = 0
        if device_id < 0:
            return
        stream = paudio.open(input_device_index=device_id, rate=16000, format=pyaudio.paInt16, channels=1, input=True)
        return stream

def send_audio(client):
    global is_speaking
    stream = get_stream()
    while stream:
        time.sleep(0.0001)
        if is_speaking:
            continue
        data = stream.read(1024, exception_on_overflow=False)
        client.send(data)
        time.sleep(0.005)
        print(".", end="")
        

def receive_audio(client):
    global is_speaking
    while True:
        data = client.recv(9)
        filedata = b''
        if b"\x00\x01\x02\x03\x04\x05\x06\x07\x08" == data: #文件开始传输标志
            while True:
                data = client.recv(1024)
                filedata += data
                filedata = filedata.replace(b'\xf0\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8', b"") #去除心跳信息
                if b"\x08\x07\x06\x05\x04\x03\x02\x01\x00" == filedata[-9:]:#文件结束传输标志
                    filedata = filedata[:-9]
                    break
            print("receive audio end:{}".format(len(filedata)), end="")

            filename = "samples/recv_{}.mp3".format(time.time())
            with open(filename, 'wb') as wf:
                wf.write(filedata)
            with wave.open(filename, 'rb') as wav_file:
                audio_length = wav_file.getnframes() / float(wav_file.getframerate())
            is_speaking = True
            pygame.mixer.music.load(filename)
            pygame.mixer.music.play()
            time.sleep(audio_length)
            is_speaking = False

            


if __name__ == "__main__":
    client = socket.socket()
    client.connect(("127.0.0.1", 10001))
    client.send(b"<username>user_device_32_6</username>")#指定用户名
    # client.send(b"<output>False<output>")#不回传音频（可以通过websocket 10003数字人接口接收音频http路径和本地路径）
    time.sleep(1)
    pygame.mixer.init()
    Thread(target=send_audio, args=(client,)).start()
    Thread(target=receive_audio, args=(client,)).start()




    