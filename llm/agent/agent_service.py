import sqlite3
import threading
import datetime
import time
import os
from scheduler.thread_manager import MyThread
from core import member_db
from core.interact import Interact
from utils import util
import fay_booter

scheduled_tasks = {}
agent_running = False


# 数据库初始化
def init_db():
    conn = sqlite3.connect('timer.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS timer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT NOT NULL,
            repeat_rule TEXT NOT NULL,
            content TEXT NOT NULL,
            uid INTEGER
        )
    ''')
    conn.commit()
    conn.close()

    

# 插入测试数据
def insert_test_data():
    conn = sqlite3.connect('timer.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO timer (time, repeat_rule, content) VALUES (?, ?, ?)", ('16:20', '1010001', 'Meeting Reminder'))
    conn.commit()
    conn.close()

# 解析重复规则返回待执行时间，None代表不在今天的待执行计划
def parse_repeat_rule(rule, task_time):
    today = datetime.datetime.now()
    if rule == '0000000':  # 不重复
        task_datetime = datetime.datetime.combine(today.date(), task_time)
        if task_datetime > today:
            return task_datetime
        else:
            return None
    for i, day in enumerate(rule):
        if day == '1' and today.weekday() == i:
            task_datetime = datetime.datetime.combine(today.date(), task_time)
            if task_datetime > today:
                return task_datetime
    return None

# 执行任务
def execute_task(task_time, id, content, uid):
    username = member_db.new_instance().find_username_by_uid(uid=uid)
    if not username:
        username = "User"
    interact = Interact("text", 1, {'user': username, 'msg': "执行任务->立刻\n" + content, 'observation': ""})
    util.printInfo(3, "系统", '执行任务：{}'.format(interact.data["msg"]), time.time())
    text = fay_booter.feiFei.on_interact(interact)
    if text is not None and id in scheduled_tasks:
        del scheduled_tasks[id]
        # 如果不重复，执行后删除记录
        conn = sqlite3.connect('timer.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM timer WHERE repeat_rule = '0000000' AND id = ?", (id,))
        conn.commit()
        conn.close()


# 30秒扫描一次数据库，当扫描到今天的不存在于定时任务列表的记录，则添加到定时任务列表。执行完的记录从定时任务列表中清除。
def check_and_execute():
    while agent_running:
        conn = sqlite3.connect('timer.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM timer")
        rows = cursor.fetchall()
        for row in rows:
            id, task_time_str, repeat_rule, content, uid = row
            task_time = datetime.datetime.strptime(task_time_str, '%H:%M').time()
            next_execution = parse_repeat_rule(repeat_rule, task_time)

            if next_execution and id not in scheduled_tasks:
                timer_thread = threading.Timer((next_execution - datetime.datetime.now()).total_seconds(), execute_task, [next_execution, id, content, uid])
                timer_thread.start()
                scheduled_tasks[id] = timer_thread

        conn.close()
        time.sleep(30)  # 30秒扫描一次

# agent启动
def agent_start():
    global agent_running
    
    agent_running = True
    #初始计划
    if not os.path.exists("./timer.db"):
        init_db()
        content ="""执行任务->
            你是一个数字人，你的责任是陪伴主人生活、工作：
            1、在每天早上8点提醒主人起床;
            2、每天12:00及18:30提醒主人吃饭;  
            3、每天21:00陪主人聊聊天; 
            4、每天23:00提醒主人睡觉。 
            """
        interact = Interact("text", 1, {'user': 'User', 'msg': content, 'observation': ""})
        util.printInfo(3, "系统", '执行任务：{}'.format(interact.data["msg"]), time.time())
        text = fay_booter.feiFei.on_interact(interact)
        if text is None:
            util.printInfo(3, "系统", '任务执行失败', time.time())
        
    check_and_execute_thread = MyThread(target=check_and_execute)
    check_and_execute_thread.start()

    

def agent_stop():
    global agent_running 
    global scheduled_tasks
    # 取消所有定时任务
    for task in scheduled_tasks.values():
        task.cancel()
    agent_running = False
    scheduled_tasks = {}
    

if __name__ == "__main__":
    agent_start()
