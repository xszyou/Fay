import os
from typing import Any

from langchain.tools import BaseTool
import tools.IotmService as IotmService

class GetSwitchLog(BaseTool):
    name = "GetSwitchLog"
    description = "此工具用于查询农业箱的设备开关当天的操作历史记录"

    def __init__(self):
        super().__init__()

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        # 用例中没有用到 arun 不予具体实现
        pass


    def _run(self, para: str):
        logs = IotmService.get_switch_log()
        device_logs = {}

        switch_mapping = {
            1: '小风扇',
            2: '电热风扇',
            3: '制冷风扇',
            4: '水开关',
            5: '肥料开关',
            6: '植物生长灯',
            7: '二氧化碳'
        }

        for val in logs:
            switch_name = switch_mapping[val['number']]
            status = 'on' if val['status'] == 1 else 'off'
            info = val['timetText']

            if switch_name not in device_logs:
                device_logs[switch_name] = {'on': [], 'off': []}

            device_logs[switch_name][status].append(info)

        return device_logs

if __name__ == "__main__":
    tool = GetSwitchLog()
    info = tool.run("")
    print(info)
