import sqlite3

def print_all_records():
    # 连接到数据库
    conn = sqlite3.connect('timer.db')
    cursor = conn.cursor()

    # 执行查询
    cursor.execute("SELECT * FROM timer")

    # 获取所有记录
    rows = cursor.fetchall()

    # 打印记录
    for row in rows:
        print(row)

    # 关闭数据库连接
    conn.close()

def insert_test_data():

    conn = sqlite3.connect('timer.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO timer (time, repeat_rule, content) VALUES (?, ?, ?)", ('22:25', '0000001', '提醒主人叫咖啡'))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    print_all_records()
    # insert_test_data()
