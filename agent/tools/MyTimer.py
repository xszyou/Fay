import abc
import sqlite3
from typing import Any
import ast


from langchain.tools import BaseTool


class MyTimer(BaseTool, abc.ABC):
    name = "MyTimer"
    description = "用于设置定时任务,每次调用只可以设置一次定时任务.使用的时候需要接受3个参数，第1个参数是时间,第2个参数是循环规则（如:'1000100'代表星期一和星期五循环，'0000000'代表不循环），第3个参数代表要执行的事项,如：('15:15', '0000001', '提醒主人叫咖啡')"

    def __init__(self):
        super().__init__()

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        # 用例中没有用到 arun 不予具体实现
        pass


    def _run(self, para) -> str:
        para = ast.literal_eval(para)
        conn = sqlite3.connect('timer.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO timer (time, repeat_rule, content) VALUES (?, ?, ?)", (para[0], para[1], para[2]))
        conn.commit()
        conn.close()
        return "定时任务设置成功"


if __name__ == "__main__":
    calculator_tool = MyTimer()
    result = calculator_tool.run("sqrt(2) + 3")
    print(result)
