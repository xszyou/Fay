from abc import abstractmethod
import json
import random
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.expected_conditions import presence_of_element_located
import websocket
import ssl
import subprocess
import os
import winreg

from core.interact import Interact
from scheduler.thread_manager import MyThread
from utils import config_util, util

USER_URL = 'https://www.douyin.com/user/'

interact_datas = []
class WS_Client:
    def __init__(self, host):
        self.__ws = None
        self.__host = host
        self.__connect(host)
 

    # 收到websocket消息的处理
    def on_message(self, ws, message):
        try:
            
            data = json.loads(message)
            if data["Type"] == 1:#留言
                if len(interact_datas) >= 5:
                    interact_datas.pop()
                interact = Interact("live", 1, {"user": json.loads(data["Data"])["User"]["Nickname"], "msg": json.loads(data["Data"])["Content"]})
                interact_datas.append(interact)
            if data["Type"] == 3:#进入
                if len(interact_datas) >= 5:
                    interact_datas.pop()
                interact_datas.append(Interact("live", 2, {"user": json.loads(data["Data"])["User"]["Nickname"], "msg": "来了"}))
            #...
        except Exception as e:
            pass

    # 收到websocket错误的处理
    def on_close(self, ws, code, msg):
        pass

    # 收到websocket错误的处理
    def on_error(self, ws, error):
        time.sleep(5)
        self.__connect(self.__host)

    # 收到websocket连接建立的处理
    def on_open(self, ws):
        pass
    def __connect(self, host):
        websocket.enableTrace(False)
        self.__ws = websocket.WebSocketApp(host, on_message=self.on_message)
        self.__ws.on_open = self.on_open
        self.__ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
    def close(self):
        self.__ws.close()


class Viewer:

    def __init__(self, url):
        self.url = url
        self.GIFT_TYPES = {
            '0ea40b8376ef8157791b928a339ed9c9': (1, '小星星', 1),
            'a29d6cdc0abb7286fdd403915196eaa7': (2, '玫瑰', 1),
            '802a21ae29f9fae5abe3693de9f874bd': (3, '抖音', 1),
            'a24b3cc863742fd4bc3de0f53dac4487': (4, '大啤酒', 2),
            '4960c39f645d524beda5d50dc372510e': (5, '你最好看', 2),
            'e9b7db267d0501b8963d8000c091e123': (6, '人气票', 1),
            '698373dfdac86a90b54facdc38698cbc': (7, '粉丝团灯牌', 1)
        }
        self.__running = True
        self.live_driver = None
        self.user_driver = None
        self.user_sec_uid = None
        self.last_join_data = ''
        self.last_interact_datas = []
        self.live_started = False
        self.last_chat_item_index = 0
        self.dy_msg_ws = None
        self.exe_process = None

    def __start(self):
        MyThread(target=self.__run_dy_msg_ws).start() #获取抖音监听内容
        # MyThread(target=self.__driver_alive_runnable).start()#直播浏览器运行
        self.chrome_options = Options()
        chrome_profile_path = "C:/Users/Administrator/AppData/Local/Google/Chrome/User Data"#视实际情况修改
        self.chrome_options.add_argument(f"user-data-dir={chrome_profile_path}")
        self.chrome_options.add_argument('--ignore-certificate-errors')
        self.chrome_options.add_argument('--allow-insecure-localhost')
        self.chrome_options.add_argument('--no-sandbox')  # 解决沙箱模式下的限制问题
        self.chrome_options.add_argument('--disable-dev-shm-usage')  # 解决共享内存不足的问题
        self.chrome_options.add_argument('--disable-gpu')  # 禁用GPU加速
        self.chrome_options.add_argument('--disable-extensions')  # 禁用扩展程序
        self.chrome_options.add_argument('--disable-notifications')
        self.chrome_options.add_argument('--disable-popup-blocking')
        self.chrome_options.add_argument('--disable-infobars')
        self.chrome_options.add_argument("--log-level=3")  # 只记录错误级别的消息

        
        #隐藏浏览器
        # self.chrome_options.add_argument('--headless')
        # self.chrome_options.add_argument('--blink-settings=imagesEnabled=false')
        # self.live_driver = webdriver.Chrome(config_util.system_chrome_driver, options=self.chrome_options)
        # self.live_driver.set_page_load_timeout(60)
        # self.live_driver.get(self.url)
        # self.user_driver = webdriver.Chrome(config_util.system_chrome_driver, options=self.chrome_options)#抖音加了验证码，暂时不获取粉丝数
        # self.__wait_live_start()#等待开播
        # self.user_sec_uid = self.__get_render_data(self.live_driver)['app']['initialState']['roomStore']['roomInfo']['room']['owner']['sec_uid']
        # MyThread(target=self.__live_state_runnable).start()#监测直播状态
        # MyThread(target=self.__join_runnable).start()#selenium监测粉丝进入
        # MyThread(target=self.__interact_runnable).start()#selenium监测直播间互动：留言、送礼
        # MyThread(target=self.__follower_runnable).start() #selenium监测粉丝变化
        self.live_started = True
        MyThread(target=self.__get_package_listen_interact_runnable).start()

    def __run_dy_msg_ws(self):
        exe_path = "./bin/Release_2.85/v2.85.exe"
        self.exe_process = subprocess.Popen([exe_path]) 
        while self.__running:
            try:
                self.dy_msg_ws = WS_Client('ws://127.0.0.1:8888')
            except Exception as e:
                print(e)
                time.sleep(5)


    def start(self):
        MyThread(target=self.__start).start()

    def is_live_started(self):
        return self.live_started

    def __wait_live_start(self):
        time.sleep(30)
        if self.__is_live():
            return
        util.log(1, '等待直播开始...')
        time.sleep(30)
        while not self.__is_live() and self.__running:
            try:
                self.live_driver.get(self.url)
            except:
                pass
            time.sleep(30)

    def __is_live(self):
        try:
            xpath = '//*[@id="_douyin_live_scroll_container_"]/div/div[2]/div/div[2]/div/div[2]/div'
            element = self.live_driver.find_element_by_xpath(xpath)
            return '结束' not in element.text
        except BaseException as e:
            print(e)
            return False

    def __driver_alive_runnable(self):
        while self.__running:
            time.sleep(0.1)
            try:
                if self.live_driver is not None:
                    try:
                        self.live_driver.execute_script('javascript:void(0);')
                    except:
                        if self.__running:
                            self.live_driver = webdriver.Chrome(config_util.system_chrome_driver, options=self.chrome_options)
                            self.live_driver.get(self.url)
                if self.user_driver is not None:
                    try:
                        self.user_driver.execute_script('javascript:void(0);')
                    except:
                        if self.__running:
                            self.user_driver = webdriver.Chrome(config_util.system_chrome_driver, options=self.chrome_options)
            except:
                pass

    def __live_state_runnable(self):
        while self.__running:
            is_live = self.__is_live()
            if is_live != self.live_started:
                self.live_started = self.__is_live()
                self.on_change_state(is_live)
                if not is_live:
                    util.log(1, '直播直播已结束，等待下场直播开始...')
            if is_live != True:
                try:
                    self.live_driver.get(self.url)
                except:
                    pass
                time.sleep(30)

    def __get_render_data(self, driver):
        wait = WebDriverWait(driver, 10)
        first_result = wait.until(presence_of_element_located((By.ID, "RENDER_DATA")))
        return json.loads(requests.utils.unquote(first_result.get_attribute("textContent")))

    def __get_interact_type(self, text):
        ary = text.split('：')
        if len(ary) >= 2:
            content_ary = ary[1].split(' ')
            if len(content_ary) == 3 and content_ary[0] == '送出了':
                return 3
        return 1

    def __get_gift_type(self, url):
        for gift_id in self.GIFT_TYPES.keys():
            if gift_id in url:
                return self.GIFT_TYPES.get(gift_id)
        return -1, '其他礼物', 0

    def __get_join_data(self):
        try:
            xpath = '//*[@id="_douyin_live_scroll_container_"]/div/div[2]/div/div[2]/div/div[1]/div/div/div/div[1]/div/div[2]'
            element = self.live_driver.find_element_by_xpath(xpath)
            ary = element.text.split('\n')
            text = ary[len(ary) - 1]
            if len(text) > 0 and self.last_join_data != text:
                self.last_join_data = text
                user = text[0:len(text) - 3]
                return Interact("live", 2, {"user": user, "msg": "来了"})
        except BaseException as e:
            return None
        return None

    def __get_interact_data(self):
        interact_data = []
        chatroom_xpath = '//*[@id="_douyin_live_scroll_container_"]/div/div[2]/div/div[2]/div/div[1]/div/div/div/div[1]/div/div[1]'
        try:
            chatroom_element = self.live_driver.find_element_by_xpath(chatroom_xpath)

            index_range = None

            if self.last_chat_item_index < 100:
                start = self.last_chat_item_index + 1
                if start < 1:
                    start = 1
                index_range = range(start, 101)  # 升序
            else:
                index_range = range(100, 0, -1)  # 降序

            # print("\n上一次: {}".format(self.last_chat_item_index))
            for index in index_range:

                # print("到了: {}".format(index))
                chatroom_item = None
                try:
                    chatroom_item = chatroom_element.find_element_by_xpath(chatroom_xpath + '/div[' + str(index) + ']')
                except:
                    pass

                item_id = None
                if self.last_chat_item_index < 100:
                    if chatroom_item is None:
                        self.last_chat_item_index = index - 1
                        break
                    elif index >= 100:
                        self.last_chat_item_index = index
                else:
                    if chatroom_item is None:
                        continue
                    item_id = chatroom_item.id
                    if item_id in self.last_interact_datas:
                        break

                # print(index)

                if len(self.last_interact_datas) > 200:
                    self.last_interact_datas.pop(0)

                self.last_interact_datas.append(item_id)
                item_text = chatroom_item.text
                ary = chatroom_item.text.replace('\r', '').split('\n')
                text = ary[len(ary) - 1]
                if len(text) < 1 and len(ary) > 1:
                    text = ary[len(ary) - 2]
                speak = self.__get_speak(text)
                if speak is None:
                    # print("无法分析[O]: " + item_text)
                    # print("无法分析[R]: " + text)
                    continue
                if self.__get_interact_type(text) == 3:
                    item_msg = None
                    try:
                        item_msg = chatroom_element.find_element_by_xpath(
                            chatroom_xpath + '/div[' + str(index) + ']/div/span[3]/span/span/img')
                    except:
                        continue
                    gift = self.__get_gift_type(item_msg.get_attribute('src'))
                    arg = speak[1].split(' ')
                    amount = int(arg[len(arg) - 1])  # 礼物数量
                    interact_data.append(Interact("live", 3, {
                        "user": speak[0],
                        "msg": ('送出了 {0} X {1}'.format(gift[1], amount)),
                        "gift": gift,
                        "amount": amount
                    }))
                else:
                    interact_data.append(Interact("live", 1, {"user": speak[0], "msg": speak[1]}))
        except BaseException as e:
            interact_data.reverse()
            return interact_data
        interact_data.reverse()
        return interact_data

    def __get_speak(self, text):
        ary = text.split('：')
        if len(ary) < 2:
            return None
        user = ary[0]
        speak = text[len(ary[0]) + 1:]
        if len(user) > 0 and len(speak) > 0:
            return user, speak

    def __join_runnable(self):
        while self.__running:
            if not self.live_started:
                continue
            # 进入 抓取
            join_data = self.__get_join_data()
            if join_data is not None:
                self.on_interact(join_data, time.time())
            time.sleep(0.05)

    def __interact_runnable(self):
        while self.__running:
            if not self.live_started:
                continue
            # 发言 & 刷礼物 抓取
            for interact in self.__get_interact_data():
                MyThread(target=self.on_interact, args=[interact, time.time()]).start()
                # self.on_interact(interact, time.time())
    
    #TODO Add by xszyou on 20230412.通过抓包监测互动数据
    def __get_package_listen_interact_runnable(self):
        while self.__running:
            if not self.live_started:
                continue
            
            for interact in interact_datas:
                MyThread(target=self.on_interact, args=[interact, time.time()]).start()
            interact_datas.clear()

    def __follower_runnable(self):
        followers = -1
        while self.__running:
            # 关注 抓取
            try:
                time.sleep(1.0 + random.random())
                self.user_driver.get(USER_URL + self.user_sec_uid)
                time.sleep(0.2)
                render_data = self.__get_render_data(self.user_driver)
                fs = -1
                for i in range(100, -1, -1):
                    if str(i) in render_data and 'user' in render_data[str(i)] and 'user' in render_data[str(i)]['user'] and 'followerCount' in render_data[str(i)]['user']['user']:
                        fs = int(render_data[str(i)]['user']['user']['followerCount'])
                        break
                if fs >= 0:
                    if self.live_started and 0 < followers < fs:
                        self.on_interact(
                            Interact("live", 4, {
                                "user": "None",
                                "msg": "粉丝关注"
                            }),
                            time.time()
                        )
                    followers = fs
                else:
                    util.log(1, '粉丝数获取异常')
            except BaseException as e:
                util.log(1, e)
                util.log(1, '粉丝数获取异常')

    def stop(self):
        self.__running = False
        if self.live_driver:
            self.live_driver.quit()
        if self.user_driver:
            self.user_driver.quit()
        if self.dy_msg_ws:
            self.dy_msg_ws.close()
            self.dy_msg_ws = None
            self.disable_windows_proxy()
            subprocess.run(["taskkill", "/F", "/PID", str(self.exe_process.pid)])
            
    
    #关闭系统代理
    def disable_windows_proxy(self):
        settings_key = r'Software\Microsoft\Windows\CurrentVersion\Internet Settings'
        try:
            registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            settings = winreg.OpenKey(registry, settings_key, 0, winreg.KEY_WRITE)
            
            # 设置代理启用值为0（禁用）
            winreg.SetValueEx(settings, 'ProxyEnable', 0, winreg.REG_DWORD, 0)
            
            # 清空代理服务器和代理覆盖设置
            winreg.SetValueEx(settings, 'ProxyServer', 0, winreg.REG_SZ, '')
            winreg.SetValueEx(settings, 'ProxyOverride', 0, winreg.REG_SZ, '')
            
            winreg.CloseKey(settings)
            winreg.CloseKey(registry)
            
            util.log(1, '系统代理已关闭。')
        except Exception as e:
            util.log(1, '关闭系统代理时出错:', e)

    @abstractmethod
    def on_interact(self, interact, event_time):
        pass

    @abstractmethod
    def on_change_state(self, is_live_started):
        pass
