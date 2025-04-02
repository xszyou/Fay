import sqlite3
from typing import Any

from langchain.tools import BaseTool

from llm.agent import agent_service


class DeleteTimer(BaseTool):
    name: str = "DeleteTimer"
    description: str = "用于删除某一个日程，接受任务id作为参数，如：2"

    def __init__(self):
        super().__init__()

    def _run(self, para) -> str:
        try:
            id = int(para)
        except ValueError:
            return "输入的 ID 无效，必须是数字。"
        
        try:
            with sqlite3.connect('memory/timer.db') as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM timer WHERE id = ?", (id,))
                conn.commit()
        except sqlite3.Error as e:
            return f"数据库错误: {e}"

        if id in agent_service.scheduled_tasks:
            agent_service.scheduled_tasks[id].cancel()
            del agent_service.scheduled_tasks[id]

        return f"任务 {id} 取消成功。"
        


if __name__ == "__main__":
    tool = DeleteTimer()
    result = tool.run("1")
    print(result)
