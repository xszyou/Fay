import abc
import sqlite3
from typing import Any
import ast


from langchain.tools import BaseTool


class QueryTimerDB(BaseTool, abc.ABC):
    name = "QueryTimerDB"
    description = "用于查询所有定时任务，结果包含3个参数，第1个参数是时间,第2个参数是循环规则（如:'1000100'代表星期一和星期五循环，'0000000'代表不循环），第3个参数代表要执行的事项,如：('15:15', '0000001', '提醒主人叫咖啡')"

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
            result = result + "\n" + str(row)
        conn.commit()
        conn.close()
        return result


if __name__ == "__main__":
    calculator_tool = MyTimer()
    result = calculator_tool.run("sqrt(2) + 3")
    print(result)
