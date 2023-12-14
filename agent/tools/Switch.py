import os
from typing import Any

import requests
from langchain.tools import BaseTool


class Switch(BaseTool):
    name = "Switch"
    description = "此工具用于控制箱内制冷设备（A）、制热设备(B)、内外通风设备(C)、浇水设备(D)、补光设备(E)、二氧化碳设备(F)的开关状态，参数格式:('A':'on')"

    def __init__(self):
        super().__init__()

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        # 用例中没有用到 arun 不予具体实现
        pass


    def _run(self, para: str) -> str:
        return para



if __name__ == "__main__":
    tool = Switch()
    info = tool.run("""{"name":"制热设备","switch":"on"}""")
    print(info)
