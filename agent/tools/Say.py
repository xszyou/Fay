import os
from typing import Any

import requests
from langchain.tools import BaseTool
import fay_booter
from core.interact import Interact


class Say(BaseTool):
    name = "Say"
    description = """此工具用于语音输出内容，用于与主人沟通及提醒主人，使用时请传入说话内容作为参数，例如：“该下班了，请注意休息”"""

    def __init__(self):
        super().__init__()

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        # 用例中没有用到 arun 不予具体实现
        pass


    def _run(self, para: str) -> str:
        interact = Interact("agent", 1, {'user': '', 'msg': para})
        fay_booter.feiFei.on_interact(interact)
        return "语音输出了：" + para



if __name__ == "__main__":
    tool = Say()
    info = tool.run("该下班了，请注意休息")
    print(info)
