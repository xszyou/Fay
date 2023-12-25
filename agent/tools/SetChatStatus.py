import os
from typing import Any

from langchain.tools import BaseTool
from agent import agent_service


class SetChatStatus(BaseTool):
    name = "SetChatStatus"
    description = """此工具用于设置聊天状态，当识别到主人想进行交流聊天时使用此工具"""

    def __init__(self):
        super().__init__()

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        # 用例中没有用到 arun 不予具体实现
        pass


    def _run(self, para: str) -> str:
        agent_service.agent.is_chat = True
        return "设置聊天状态成功"



if __name__ == "__main__":
    tool = SetChatStatus()
    info = tool.run("该下班了，请注意休息")
    print(info)
