'''
  Copyright FunASR (https://github.com/alibaba-damo-academy/FunASR). All Rights
  Reserved. MIT License  (https://opensource.org/licenses/MIT)
  
  2022-2023 by zhaomingwork@qq.com  
'''
# pip install websocket-client
import ssl
from websocket import ABNF
from websocket import create_connection
from queue import Queue
import threading
import traceback
import json
import time
import numpy as np

import pyaudio
import asyncio
import argparse

# class for recognizer in websocket
class Funasr_websocket_recognizer():
    '''
    python asr recognizer lib

    '''

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="127.0.0.1", required=False, help="host ip, localhost, 0.0.0.0")
    parser.add_argument("--port", type=int, default=10194, required=False, help="grpc server port")
    parser.add_argument("--chunk_size", type=int, default=160, help="ms")
    parser.add_argument("--vad_needed", type=bool, default=True)
    args = parser.parse_args()

    def __init__(self, host="127.0.0.1",
                 port="10197",
                 is_ssl=True,
                 chunk_size="0, 10, 5",
                 chunk_interval=10,
                 mode="2pass",
                 wav_name="default"):
      '''
          host: server host ip
          port: server port
          is_ssl: True for wss protocal, False for ws
      '''
      try:
        if is_ssl == True:
            ssl_context = ssl.SSLContext()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            uri = "wss://{}:{}".format(host, port)
            ssl_opt={"cert_reqs": ssl.CERT_NONE}
        else:
            uri = "ws://{}:{}".format(host, port)
            ssl_context = None
            ssl_opt=None
        self.host = host
        self.port = port
 
        self.msg_queue = Queue() # used for recognized result text

        print("connect to url",uri)
        self.websocket=create_connection(uri, ssl=ssl_context, sslopt=ssl_opt)
 
        self.thread_msg = threading.Thread(target=Funasr_websocket_recognizer.thread_rec_msg, args=(self,))
        self.thread_msg.start()
        chunk_size = [int(x) for x in  chunk_size.split(",")]
        stride = int(60 *  chunk_size[1] / chunk_interval / 1000 * 16000 * 2)
        chunk_num = (len(audio_bytes) - 1) // stride + 1
       
        message = json.dumps({"mode": mode,
                              "chunk_size": chunk_size,
                              "encoder_chunk_look_back": 4,
                              "decoder_chunk_look_back": 1,
                              "chunk_interval": chunk_interval,
                              "wav_name": wav_name,
                              "is_speaking": True})
 
        self.websocket.send(message)
 
        print("send json",message)
      
      except Exception as e:
            print("Exception:", e)
            traceback.print_exc()
    
    # async def record():
    #     global voices 
    #     FORMAT = pyaudio.paInt16
    #     CHANNELS = 1
    #     RATE = 16000
    #     CHUNK = int(RATE / 1000 * args.chunk_size)

    #     p = pyaudio.PyAudio()

    #     stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)

    #     while True:
    #         data = stream.read(CHUNK)
    #         voices.put(data)
    #         await asyncio.sleep(0.01)


    # threads for rev msg
    def thread_rec_msg(self):
        try:
         while(True):
           msg=self.websocket.recv()
           if msg is None or len(msg) == 0:
             continue
           msg = json.loads(msg)
           
           self.msg_queue.put(msg)
        except Exception as e:
            print("client closed")
 
    # feed data to asr engine, wait_time means waiting for result until time out
    def feed_chunk(self, chunk, wait_time=0.01):
        try:
            self.websocket.send(chunk,  ABNF.OPCODE_BINARY)
            # loop to check if there is a message, timeout in 0.01s
            while(True):
               msg = self.msg_queue.get(timeout=wait_time)
               if self.msg_queue.empty():
                  break
                  
            return msg
        except:
            return ""
        
    def close(self,timeout=1):
        message = json.dumps({"is_speaking": False})
        self.websocket.send(message)
        # sleep for timeout seconds to wait for result
        time.sleep(timeout)
        msg=""
        while(not self.msg_queue.empty()):
            msg = self.msg_queue.get()
        
        self.websocket.close()
        # only resturn the last msg
        return msg
        
if __name__ == '__main__':
    
    print('example for Funasr_websocket_recognizer') 
    import wave
    wav_path = "long.wav"
    # wav_path = "/Users/zhifu/Downloads/modelscope_models/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch/example/asr_example.wav"
    with wave.open(wav_path, "rb") as wav_file:
                params = wav_file.getparams()
                frames = wav_file.readframes(wav_file.getnframes())
                audio_bytes = bytes(frames)
    
 
    stride = int(60 * 10 / 10 / 1000 * 16000 * 2)
    chunk_num = (len(audio_bytes) - 1) // stride + 1
    # create an recognizer 
    rcg = Funasr_websocket_recognizer()
    # loop to send chunk
    for i in range(chunk_num):

            beg = i * stride
            data = audio_bytes[beg:beg + stride]
 
            text = rcg.feed_chunk(data,wait_time=0.02)
            if len(text)>0:
               print("text",text)
            time.sleep(0.05)
 
    # get last message
    text = rcg.close(timeout=3)
    print("text",text)
 
    
            
