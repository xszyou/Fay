import sqlite3
import time
import threading
import functools
from utils import util
def synchronized(func):
  @functools.wraps(func)
  def wrapper(self, *args, **kwargs):
    with self.lock:
      return func(self, *args, **kwargs)
  return wrapper

__content_tb = None
def new_instance():
    global __content_tb
    if __content_tb is None:
        __content_tb = Content_Db()
        __content_tb.init_db()
    return __content_tb


class Content_Db:

    def __init__(self) -> None:
        self.lock = threading.Lock()
           
   

    #初始化
    def init_db(self):
        conn = sqlite3.connect('fay.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS T_Msg
            (id INTEGER PRIMARY KEY     autoincrement,
            type        char(10),
            way        char(10),
            content           TEXT    NOT NULL,
            createtime         Int,
            username TEXT DEFAULT 'User',
            uid         Int);''')
        conn.commit()
        conn.close()
       
 


    #添加对话
    @synchronized
    def add_content(self,type,way,content,username='User',uid=0):
        conn = sqlite3.connect("fay.db")
        cur = conn.cursor()
        try:
            cur.execute("insert into T_Msg (type,way,content,createtime,username,uid) values (?,?,?,?,?,?)",(type,way,content,int(time.time()),username,uid))
            conn.commit()
        except:
               util.log(1, "请检查参数是否有误")
               conn.close()
               return 0
        conn.close()
        return cur.lastrowid
     
        

    #获取对话内容
    @synchronized
    def get_list(self,way,order,limit,uid=0):
        conn = sqlite3.connect("fay.db")
        cur = conn.cursor()
        where_uid = ""
        if int(uid) != 0:
            where_uid = f" and uid = {uid} "
        if(way == 'all'):
            cur.execute("select type,way,content,createtime,datetime(createtime, 'unixepoch', 'localtime') as timetext,username from T_Msg  where 1 "+where_uid+" order by id "+order+" limit ?",(limit,))
        elif(way == 'notappended'):
            cur.execute("select type,way,content,createtime,datetime(createtime, 'unixepoch', 'localtime') as timetext,username from T_Msg where way != 'appended' "+where_uid+" order by id "+order+" limit ?",(limit,))
        else:
            cur.execute("select type,way,content,createtime,datetime(createtime, 'unixepoch', 'localtime') as timetext,username from T_Msg where way = ? "+where_uid+" order by id "+order+" limit ?",(way,limit,))

        list = cur.fetchall()
        conn.close()
        return list





   



