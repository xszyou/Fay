import socket
import pyaudio
import time
import pygame

import thread_manager

def get_stream():
        paudio = pyaudio.PyAudio()
        device_id = 0
        if device_id < 0:
            return
        stream = paudio.open(input_device_index=device_id, rate=16000, format=pyaudio.paInt16, channels=1, input=True)
        return stream

def send_audio(client):
    stream = get_stream()
    while stream:
        data = stream.read(1024, exception_on_overflow=False)
        client.send(data)
        time.sleep(0.005)
        print(".", end="")

def receive_audio(client):
    while True:
        data = client.recv(9)
        filedata = b''
        if b"\x00\x01\x02\x03\x04\x05\x06\x07\x08" == data: #mp3文件开始传输标志
            while True:
                data = client.recv(1024)
                filedata += data
                filedata = filedata.replace(b'\xf0\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8', b"") #去除心跳信息
                if b"\x08\x07\x06\x05\x04\x03\x02\x01\x00" == filedata[-9:]:#mp3文件结束传输标志
                    filedata = filedata[:-9]
                    break
            print("receive audio end:{}".format(len(filedata)), end="")

            filename = "sample/recv_{}.mp3".format(time.time())
            with open(filename, "wb") as f:
                f.write(filedata)
                f.close()
            pygame.mixer.music.load(filename)
            pygame.mixer.music.play()

            


if __name__ == "__main__":
    client = socket.socket()
    client.connect(("192.168.1.101", 10001))
    pygame.mixer.init()
    thread_manager.MyThread(target=send_audio, args=(client,)).start()
    thread_manager.MyThread(target=receive_audio, args=(client,)).start()




    