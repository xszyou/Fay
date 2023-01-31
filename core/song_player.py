import os.path
import random
import time

import eyed3
import requests
import re
import pygame

from utils import util

__playing = False

song_name = ""


def __play_song(song_id: str):
    file_url = "./songs/{}.mp3".format(song_name)
    if not os.path.exists("./songs"):
        os.mkdir("./songs")
    if not os.path.exists(file_url):
        url = "https://music.163.com/song/media/outer/url?id=" + song_id
        response = requests.request("GET", url)
        with open(file_url, "wb") as mp3:
            mp3.write(response.content)
    pygame.mixer.music.load(file_url)
    pygame.mixer.music.play()
    util.log(3, "正在播放 {}".format(song_name))
    audio_length = eyed3.load(file_url).info.time_secs
    last_time = time.time()
    while __playing and time.time() - last_time < audio_length:
        time.sleep(0.05)
        pass


def __random_song():
    # 歌单列表
    id_list = [
        "3778678",  # 热歌榜
        # "1978921795",  # 电音榜
        # "10520166",  # 国电榜
        # "991319590",  # 说唱榜
    ]
    url = "https://music.163.com/discover/toplist?id=" + id_list[random.randrange(0, len(id_list))]
    response = requests.request("GET", url)
    song_list = re.findall("<li><a href=\"/song\?id=([0-9]*)\">(.*?)</a></li>", response.text)
    index = random.randrange(0, len(song_list))
    return song_list[index]


def play():
    global __playing
    global song_name
    __playing = True
    while __playing:
        song = __random_song()
        try:
            song_name = song[1]
            __play_song(song[0])
            break
        except Exception as e:
            util.log(1, "无法播放 {} 可能需要VIP".format(song[1]))


def stop():
    global __playing
    __playing = False
    pygame.mixer.music.stop()
