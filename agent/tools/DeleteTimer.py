import abc
import sqlite3
from typing import Any
import ast

from langchain.tools import BaseTool

from agent import agent_service


class DeleteTimer(BaseTool, abc.ABC):
    name = "DeleteTimer"
    description = "用于删除某一个定时任务，接受任务id作为参数，如：('2')"

    def __init__(self):
        super().__init__()

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        # 用例中没有用到 arun 不予具体实现
        pass


    def _run(self, para) -> str:
        para = ast.literal_eval(para)

        del agent_service.scheduled_tasks[int(para[0])]
        conn = sqlite3.connect('timer.db')
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM timer WHERE id = {id}")
        conn.commit()
        conn.close()

        return f"{id}任务取消成功"


if __name__ == "__main__":
    tool = DeleteTimer()
    result = tool.run("1")
    print(result)
