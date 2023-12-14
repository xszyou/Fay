import abc
import sqlite3
from typing import Any
import ast


from langchain.tools import BaseTool


class QueryTimerDB(BaseTool, abc.ABC):
    name = "QueryTimerDB"
    description = "用于查询所有定时任务，返回的数据里包含3个参数:时间、循环规则（如:'1000100'代表星期一和星期五循环，'0000000'代表不循环）、执行的事项"

    def __init__(self):
        super().__init__()

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        # 用例中没有用到 arun 不予具体实现
        pass


    def _run(self, para) -> str:
        conn = sqlite3.connect('timer.db')
        cursor = conn.cursor()
        # 执行查询
        cursor.execute("SELECT * FROM timer")
        # 获取所有记录
        rows = cursor.fetchall()
        # 拼接结果
        result = ""
        for row in rows:
            result = result +  str(row) + "\n"
        conn.commit()
        conn.close()
        return result


if __name__ == "__main__":
    tool = QueryTimerDB()
    result = tool.run("")
    print(result)
