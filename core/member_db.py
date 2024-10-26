import sqlite3
import time
import threading
import functools
def synchronized(func):
  @functools.wraps(func)
  def wrapper(self, *args, **kwargs):
    with self.lock:
      return func(self, *args, **kwargs)
  return wrapper

__member_db = None
def new_instance():
    global __member_db
    if __member_db is None:
        __member_db = Member_Db()
        __member_db.init_db()
    return __member_db


class Member_Db:

    def __init__(self) -> None:
        self.lock = threading.Lock()
           
   

    #初始化
    def init_db(self):
        conn = sqlite3.connect('user_profiles.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS T_Member
            (id INTEGER PRIMARY KEY     autoincrement,
            username        TEXT    NOT NULL UNIQUE);''')
        conn.commit()
        conn.close()
       
    # 添加新用户
    @synchronized
    def add_user(self, username):
        if self.is_username_exist(username) == "notexists":
            conn = sqlite3.connect('user_profiles.db')
            c = conn.cursor()
            c.execute('INSERT INTO T_Member (username) VALUES (?)', (username,))
            conn.commit()
            conn.close()
            return "success"
        else:
           return f"Username '{username}' already exists."

    # 修改用户名
    @synchronized
    def update_user(self, username, new_username):
        if self.is_username_exist(new_username) == "notexists":
            conn = sqlite3.connect('user_profiles.db')
            c = conn.cursor()
            c.execute('UPDATE T_Member SET username = ? WHERE username = ?', (new_username, username))
            conn.commit()
            conn.close()
            return "success"
        else:
            return f"Username '{new_username}' already exists."

    # 删除用户
    @synchronized
    def delete_user(self, username):
        conn = sqlite3.connect('user_profiles.db')
        c = conn.cursor()
        c.execute('DELETE FROM T_Member WHERE username = ?', (username,))
        conn.commit()
        conn.close()
        return "success"

    # 检查用户名是否已存在
    def is_username_exist(self, username):
        conn = sqlite3.connect('user_profiles.db')
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM T_Member WHERE username = ?', (username,))
        result = c.fetchone()[0]
        conn.close()
        if result > 0:
            return "exists"
        else:
            return "notexists"

    def find_user(self, username):
        conn = sqlite3.connect('user_profiles.db')
        c = conn.cursor()
        c.execute('SELECT * FROM T_Member WHERE username = ?', (username,))
        result = c.fetchone()
        conn.close()
        if result is None:
            return 0
        else:
           return result[0]

    @synchronized
    def query(self, sql):
        try:
            conn = sqlite3.connect('user_profiles.db')
            c = conn.cursor()
            c.execute(sql)
            results = c.fetchall()
            conn.commit()
            conn.close()
            return results
        except Exception as e:
            return f"执行时发生错误：{str(e)}"


    # 获取所有用户
    @synchronized
    def get_all_users(self):
        conn = sqlite3.connect('user_profiles.db')
        c = conn.cursor()
        c.execute('SELECT * FROM T_Member')
        results = c.fetchall()
        conn.close()
        return results
        





   



