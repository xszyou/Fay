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
class Authorize_Tb:

    def __init__(self) -> None:
        self.lock = threading.Lock()
           
   

    #初始化
    def init_tb(self):
        conn = sqlite3.connect('fay.db')
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS T_Authorize
            (id INTEGER PRIMARY KEY     autoincrement,
            userid        char(100),
            accesstoken           TEXT,
            expirestime           BigInt,
            createtime         Int);
        ''')
        conn.commit()
        conn.close()

    #添加
    @synchronized
    def add(self,userid,accesstoken,expirestime):
        conn = sqlite3.connect("fay.db")
        cur = conn.cursor()
        cur.execute("insert into T_Authorize (userid,accesstoken,expirestime,createtime) values (?,?,?,?)",(userid,accesstoken,expirestime,int(time.time())))
        
        conn.commit()
        conn.close()
        return cur.lastrowid   

    #查询
    @synchronized
    def find_by_userid(self,userid):
        conn = sqlite3.connect("fay.db")
        cur = conn.cursor()
        cur.execute("select accesstoken,expirestime from T_Authorize where userid = ? order by id desc limit 1",(userid,))
        info = cur.fetchone()
        conn.close()
        return info

    # 更新token
    @synchronized
    def update_by_userid(self, userid, new_accesstoken, new_expirestime):
        conn = sqlite3.connect("fay.db")
        cur = conn.cursor()
        cur.execute("UPDATE T_Authorize SET accesstoken = ?, expirestime = ? WHERE userid = ?", 
                    (new_accesstoken, new_expirestime, userid))
        conn.commit()
        conn.close()