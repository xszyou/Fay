import sqlite3
import threading
import datetime
import time
from agent.fay_agent import FayAgentCore

scheduled_tasks = {}
agent_running = False
agent = FayAgentCore()

# 数据库初始化
def init_db():
    conn = sqlite3.connect('timer.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS timer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT NOT NULL,
            repeat_rule TEXT NOT NULL,
            content TEXT NOT NULL
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
def execute_task(task_time, id, content):
    content = content
    agent.run(content)
    del scheduled_tasks[id]
    # 如果不重复，执行后删除记录
    conn = sqlite3.connect('timer.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM timer WHERE repeat_rule = '0000000' AND time = ? AND content = ?", (task_time.strftime('%H:%M'), content))
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
            id, task_time_str, repeat_rule, content = row
            task_time = datetime.datetime.strptime(task_time_str, '%H:%M').time()
            next_execution = parse_repeat_rule(repeat_rule, task_time)

            if next_execution and id not in scheduled_tasks:
                timer_thread = threading.Timer((next_execution - datetime.datetime.now()).total_seconds(), execute_task, [next_execution, id, content])
                timer_thread.start()
                scheduled_tasks[id] = timer_thread

        conn.close()
        time.sleep(30)  # 30秒扫描一次

# agent启动
def agent_start():
    global agent_running
    global agent
    
    agent_running = True
    init_db()
    # insert_test_data()
    check_and_execute_thread = threading.Thread(target=check_and_execute)
    check_and_execute_thread.start()

    #初始计划
    agent.run("""执行任务-->
        请为我一个个时间设置初始计划：
        1、在每天12:30到13:30安静不影响主人休息;
        2、每天12点提醒主人吃饭;  
        3、在星期一到星期五13:30提醒主人开始工作; 
        4、在星期一到星期五15:15提醒主人冲咖啡; 
        5、在星期一、星期三的11:15提醒主人开会; 
        6、在星期五17:30提醒主人开会;
        7、在星期一到星期五18:00提醒主人下班;
        8、在每天21点陪主人聊聊天;  
        9、在每天晚上10:30会跟据天气预报信息和前一天的运行情况，检查iotm系统当天的控制规则；
        10、在每天早上8点、中午12点、晚上10点检查农业种植箱的状态是否附合设定的预期执行，
        如果不符合请告知我调整。
        另外：在任何意外的情况需要进一步指导请马联系我。
        """)

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
