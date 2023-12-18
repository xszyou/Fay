import os
from typing import Any

from langchain.tools import BaseTool
import agent.tools.IotmService as IotmService

class getOnRunLinkage(BaseTool):
    name = "getOnRunLinkage"
    description = "此工具用于查询农业箱当前在运行的联动，设备序号：小风扇（1）、电热风扇(2)、制冷风扇(3)、肥料开关(4)、补光设备(5)、植物生长灯(6)、二氧化碳(7)"

    def __init__(self):
        super().__init__()

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        # 用例中没有用到 arun 不予具体实现
        pass


    def _run(self, para: str) -> str:
        infos = IotmService.get_on_run_linkage()
        return infos

if __name__ == "__main__":
    tool = getOnRunLinkage()
    info = tool.run("")
    print(info)
