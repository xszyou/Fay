import os
import ast
from typing import Any

import requests
from langchain.tools import BaseTool
import json
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import agent.tools.IotmService as IotmService

class Switch(BaseTool):
    name = "Switch"
    description = '此工具用于控制小风扇、电热风扇、制冷风扇、水开关、肥料开关、植物生长灯、二氧化碳的开关，参数格式:("小风扇","on"),返回True为成功'

    def __init__(self):
        super().__init__()

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        # 用例中没有用到 arun 不予具体实现
        pass


    def _run(self, para: str) -> str:
        try:
            if not para:
                return "参数不能为空"
            para = ast.literal_eval(para)
            if not para:
                return "参数格式不正确"
            switch = para[0]
            switch_mapping = {
                '小风扇': 1,
                '电热风扇': 2,
                '制冷风扇': 3,
                '水开关': 4,
                '肥料开关': 5,
                '植物生长灯': 6,
                '二氧化碳': 7
            }
            if switch not in switch_mapping:
                return "未知的设备类型，请检查 'switch' 字段值"
            num = switch_mapping[switch]
            onoff = para[1]
            re = IotmService.do_switch_operation(num, onoff)
            return re
        except json.JSONDecodeError:
            return '参数格式不正确，请使用正确的 JSON 格式表示方式，例如 {"switch": "小风扇", "onoff": "on"}'



if __name__ == "__main__":
    tool = Switch()
    info = tool.run('("小风扇","off")')
    print(info)
