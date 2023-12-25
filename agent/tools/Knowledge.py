import os
from typing import Any

import requests
from langchain.tools import BaseTool


class Knowledge(BaseTool):
    name = "Knowledge"
    description = """此工具用于查询箱内植物的专业知识，使用时请传入相关问题作为参数，例如：“草梅最适合的生长温度”"""

    def __init__(self):
        super().__init__()

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        # 用例中没有用到 arun 不予具体实现
        pass


    def _run(self, para: str) -> str:
        return "查询知识库：" + para



if __name__ == "__main__":
    tool = Knowledge()
    info = tool.run("草梅最适合的生长温度")
    print(info)
