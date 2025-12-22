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

    # 初始化数据库
    def init_db(self):
        conn = sqlite3.connect('memory/fay.db')
        conn.text_factory = str
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS T_Msg
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
            type        CHAR(10),
            way         CHAR(10),
            content     TEXT    NOT NULL,
            createtime  INT,
            username    TEXT DEFAULT 'User',
            uid         INT);''')
        # 对话采纳记录表
        c.execute('''CREATE TABLE IF NOT EXISTS T_Adopted
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
            msg_id      INTEGER UNIQUE,
            adopted_time INT,
            FOREIGN KEY(msg_id) REFERENCES T_Msg(id));''')
        conn.commit()
        conn.close()

    # 添加对话
    @synchronized
    def add_content(self, type, way, content, username='User', uid=0):
        conn = sqlite3.connect("memory/fay.db")
        conn.text_factory = str
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO T_Msg (type, way, content, createtime, username, uid) VALUES (?, ?, ?, ?, ?, ?)",
                        (type, way, content, int(time.time()), username, uid))
            conn.commit()
            last_id = cur.lastrowid
        except Exception as e:
            util.log(1, "请检查参数是否有误: {}".format(e))
            conn.close()
            return 0
        conn.close()
        return last_id

    # 更新对话内容
    @synchronized
    def update_content(self, msg_id, content):
        """
        更新指定ID的消息内容
        :param msg_id: 消息ID
        :param content: 新的内容
        :return: 是否更新成功
        """
        conn = sqlite3.connect("memory/fay.db")
        conn.text_factory = str
        cur = conn.cursor()
        try:
            cur.execute("UPDATE T_Msg SET content = ? WHERE id = ?", (content, msg_id))
            conn.commit()
            affected_rows = cur.rowcount
        except Exception as e:
            util.log(1, f"更新消息内容失败: {e}")
            conn.close()
            return False
        conn.close()
        return affected_rows > 0

    # 根据ID查询对话记录
    @synchronized
    def get_content_by_id(self, msg_id):
        conn = sqlite3.connect("memory/fay.db")
        conn.text_factory = str
        cur = conn.cursor()
        cur.execute("SELECT * FROM T_Msg WHERE id = ?", (msg_id,))
        record = cur.fetchone()
        conn.close()
        return record

    # 添加对话采纳记录
    @synchronized
    def adopted_message(self, msg_id):
        conn = sqlite3.connect('memory/fay.db')
        conn.text_factory = str
        cur = conn.cursor()
        # 检查消息ID是否存在
        cur.execute("SELECT 1 FROM T_Msg WHERE id = ?", (msg_id,))
        if cur.fetchone() is None:
            util.log(1, "消息ID不存在")
            conn.close()
            return False
        try:
            cur.execute("INSERT INTO T_Adopted (msg_id, adopted_time) VALUES (?, ?)", (msg_id, int(time.time())))
            conn.commit()
        except sqlite3.IntegrityError:
            util.log(1, "该消息已被采纳")
            conn.close()
            return False
        conn.close()
        return True

    # 取消采纳：删除采纳记录并返回相同clean_content的所有消息ID
    @synchronized
    def unadopt_message(self, msg_id, clean_content):
        """
        取消采纳消息
        :param msg_id: 消息ID
        :param clean_content: 过滤掉think标签后的干净内容，用于匹配QA文件
        :return: (success, same_content_ids)
        """
        import re
        conn = sqlite3.connect('memory/fay.db')
        conn.text_factory = str
        cur = conn.cursor()

        # 获取所有fay类型的消息，检查过滤think后的内容是否匹配
        cur.execute("SELECT id, content FROM T_Msg WHERE type = 'fay'")
        all_fay_msgs = cur.fetchall()

        # 规范化目标内容：去掉换行符和首尾空格
        clean_content_normalized = clean_content.replace('\n', '').replace('\r', '').strip()

        same_content_ids = []
        for row in all_fay_msgs:
            row_id, row_content = row
            # 过滤掉think标签内容后比较
            row_clean = re.sub(r'<think>[\s\S]*?</think>', '', row_content, flags=re.IGNORECASE).strip()
            # 规范化后比较
            row_clean_normalized = row_clean.replace('\n', '').replace('\r', '').strip()
            if row_clean_normalized == clean_content_normalized:
                same_content_ids.append(row_id)

        # 删除这些消息的采纳记录
        if same_content_ids:
            placeholders = ','.join('?' * len(same_content_ids))
            cur.execute(f"DELETE FROM T_Adopted WHERE msg_id IN ({placeholders})", same_content_ids)
            conn.commit()

        conn.close()
        return True, same_content_ids

    # 获取对话内容
    @synchronized
    def get_list(self, way, order, limit, uid=0):
        conn = sqlite3.connect("memory/fay.db")
        conn.text_factory = str
        cur = conn.cursor()
        where_uid = ""
        if int(uid) != 0:
            where_uid = f" AND T_Msg.uid = {uid} "
        base_query = f"""
            SELECT T_Msg.type, T_Msg.way, T_Msg.content, T_Msg.createtime,
                   datetime(T_Msg.createtime, 'unixepoch', 'localtime') AS timetext,
                   T_Msg.username,T_Msg.id,
                   CASE WHEN T_Adopted.msg_id IS NOT NULL THEN 1 ELSE 0 END AS is_adopted
            FROM T_Msg
            LEFT JOIN T_Adopted ON T_Msg.id = T_Adopted.msg_id
            WHERE 1 {where_uid}
        """
        if way == 'all':
            query = base_query + f" ORDER BY T_Msg.id {order} LIMIT ?"
            cur.execute(query, (limit,))
        elif way == 'notappended':
            query = base_query + f" AND T_Msg.way != 'appended' ORDER BY T_Msg.id {order} LIMIT ?"
            cur.execute(query, (limit,))
        else:
            query = base_query + f" AND T_Msg.way = ? ORDER BY T_Msg.id {order} LIMIT ?"
            cur.execute(query, (way, limit))
        list = cur.fetchall()
        conn.close()
        return list
    

    @synchronized
    def get_recent_messages_by_user(self, username='User', limit=30):
        conn = sqlite3.connect("memory/fay.db")
        conn.text_factory = str
        cur = conn.cursor()
        cur.execute(
            """
            SELECT type, content
            FROM T_Msg
            WHERE username = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (username, limit),
        )
        rows = cur.fetchall()
        conn.close()
        rows.reverse()
        return rows

    @synchronized
    def get_recent_messages_all(self, limit=30):
        """获取所有用户的最近消息（不按用户隔离）"""
        conn = sqlite3.connect("memory/fay.db")
        conn.text_factory = str
        cur = conn.cursor()
        cur.execute(
            """
            SELECT type, content, username
            FROM T_Msg
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()
        conn.close()
        rows.reverse()
        return rows

    @synchronized
    def get_previous_user_message(self, msg_id):
        conn = sqlite3.connect("memory/fay.db")
        cur = conn.cursor()
        cur.execute("""
            SELECT id, type, way, content, createtime, datetime(createtime, 'unixepoch', 'localtime') AS timetext, username
            FROM T_Msg
            WHERE id < ? AND type != 'fay'
            ORDER BY id DESC
            LIMIT 1
        """, (msg_id,))
        record = cur.fetchone()
        conn.close()
        return record

    # 删除指定用户名的所有消息
    @synchronized
    def delete_messages_by_username(self, username):
        """
        删除指定用户名的所有消息（包括用户发送的和Fay回复给该用户的）
        :param username: 用户名
        :return: 删除的消息数量
        """
        conn = sqlite3.connect("memory/fay.db")
        conn.text_factory = str
        cur = conn.cursor()
        try:
            # 先获取该用户所有消息的ID，用于删除采纳记录
            cur.execute("SELECT id FROM T_Msg WHERE username = ?", (username,))
            msg_ids = [row[0] for row in cur.fetchall()]

            # 删除这些消息的采纳记录
            if msg_ids:
                placeholders = ','.join('?' * len(msg_ids))
                cur.execute(f"DELETE FROM T_Adopted WHERE msg_id IN ({placeholders})", msg_ids)

            # 删除消息
            cur.execute("DELETE FROM T_Msg WHERE username = ?", (username,))
            deleted_count = cur.rowcount
            conn.commit()
        except Exception as e:
            util.log(1, f"删除用户消息失败: {e}")
            deleted_count = 0
        conn.close()
        return deleted_count
