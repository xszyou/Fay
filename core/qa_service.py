import os
import csv
import difflib
import random
from utils import config_util as cfg
from scheduler.thread_manager import MyThread
import shlex
import subprocess
import time
from utils import util

class QAService:
    
    def __init__(self):
         # 人设提问关键字
        self.attribute_keyword = [
            [['你叫什么名字', '你的名字是什么'], 'name'],
            [['你是男的还是女的', '你是男生还是女生', '你的性别是什么', '你是男生吗', '你是女生吗', '你是男的吗', '你是女的吗', '你是男孩子吗', '你是女孩子吗', ], 'gender', ],
            [['你今年多大了', '你多大了', '你今年多少岁', '你几岁了', '你今年几岁了', '你今年几岁了', '你什么时候出生', '你的生日是什么', '你的年龄'], 'age', ],
            [['你的家乡在哪', '你的家乡是什么', '你家在哪', '你住在哪', '你出生在哪', '你的出生地在哪', '你的出生地是什么', ], 'birth', ],
            [['你的生肖是什么', '你属什么', ], 'zodiac', ],
            [['你是什么座', '你是什么星座', '你的星座是什么', ], 'constellation', ],
            [['你是做什么的', '你的职业是什么', '你是干什么的', '你的职位是什么', '你的工作是什么', '你是做什么工作的'], 'job', ],
            [['你的爱好是什么', '你有爱好吗', '你喜欢什么', '你喜欢做什么'], 'hobby'],
            [['联系方式', '联系你们', '怎么联系客服', '有没有客服'], 'contact']
        ]

        self.command_keyword = [
            [['关闭', '再见', '你走吧'], 'stop'],
            [['静音', '闭嘴', '我想静静'], 'mute'],
            [['取消静音', '你在哪呢', '你可以说话了'], 'unmute'],
            [['换个性别', '换个声音'], 'changeVoice']
        ]

    def question(self, query_type, text):
        if query_type == 'qa':
            answer_dict = self.__read_qna(cfg.config['interact'].get('QnA'))
            answer, action = self.__get_keyword(answer_dict, text, query_type)
            if action:
                MyThread(target=self.__run, args=[action]).start()
            return answer, 'qa'
    
        elif query_type == 'Persona':
            answer_dict = self.attribute_keyword
            answer, action  = self.__get_keyword(answer_dict, text, query_type)
            return answer, 'Persona'
        elif query_type == 'command':
            answer, action  = self.__get_keyword(self.command_keyword, text, query_type)
            return answer, 'command'
        return None, None

    def __run(self, action):
        time.sleep(0.1)
        args = shlex.split(action)  # 分割命令行参数
        subprocess.Popen(args)

    def __read_qna(self, filename):
        qna = []
        try:
            with open(filename, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                next(reader)  # 跳过表头
                for row in reader:
                    if len(row) >= 2:
                        qna.append([row[0].split(";"), row[1], row[2] if len(row) >= 3 else None])
        except Exception as e:
            pass
        return qna

    def record_qapair(self, question, answer):
        if not cfg.config['interact']['QnA'] or cfg.config['interact']['QnA'][-3:] != 'csv':
            util.log(1, 'qa文件没有指定，不记录大模型回复')
            return
        log_file = cfg.config['interact']['QnA']  # 指定 CSV 文件的名称或路径
        file_exists = os.path.isfile(log_file)
        with open(log_file, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            if not file_exists:
                # 写入表头
                writer.writerow(['Question', 'Answer'])
            writer.writerow([question, answer])

    def __get_keyword(self, keyword_dict, text, query_type):
        threshold = 0.6
        candidates = []

        for qa in keyword_dict:
            if len(qa) < 2:
                continue
            for quest in qa[0]:
                similar = self.__string_similar(text, quest)
                if quest in text:
                    similar += 0.3
                if similar >= threshold:
                    action = qa[2] if (query_type == "qa" and len(qa) > 2) else None
                    candidates.append((similar, qa[1], action))

        if not candidates:
            return None, None

        candidates.sort(key=lambda x: x[0], reverse=True)

        max_hits = max(1, int(len(keyword_dict) * 0.1))
        candidates = candidates[:max_hits]

        chosen = random.choice(candidates)
        return chosen[1], chosen[2]

    def __string_similar(self, s1, s2):
        return difflib.SequenceMatcher(None, s1, s2).quick_ratio()


