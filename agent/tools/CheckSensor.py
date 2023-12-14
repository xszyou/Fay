import os
from typing import Any

import requests
from langchain.tools import BaseTool


class CheckSensor(BaseTool):
    name = "CheckSensor"
    description = "此工具用于查询农业箱传感器数据及设备开关状态"

    def __init__(self):
        super().__init__()

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        # 用例中没有用到 arun 不予具体实现
        pass


    def _run(self, para: str) -> str:
        return """
    {
    "result": True,
    "ts": "2023-05-09 17:54:31.948",
    "data": [
        "co2": 
            {
                "ts": "2022-05-09 17:54:31.948",
                "val": "1000ppm",
        "desc":"箱内的二氧化碳含量"
                },

        "inside_temperature": 
                {
                    "ts": "2022-05-09 17:54:31.948",
                    "val": 28,
        "desc":"箱内的温度"
                },

        "inside_humidity": 
                {
                    "ts": "2022-05-09 17:54:31.948",
                    "val": 80,
        "desc":"箱内的湿度"
                },

        "outside_temperature": 
                {
                    "ts": "2022-05-09 17:54:31.948",
                    "val": 28,
        "desc":"箱外的温度"
                },

        "outside_humidity": 
                {
                    "ts": "2022-05-09 17:54:31.948",
                    "val": 80,
        "desc":"箱外的湿度"
                },

        "inside_illuminance": 
                {
                    "ts": "2022-05-09 17:54:31.948",
                    "val": "300lux"
        "desc":"箱内的光照强度的值，当箱内光照强度太低时，生长灯会被打开，传感器位置是可以检测到生长灯的亮度的"
                },

        "inside_soil": 
                {
                    "ts": "2022-05-09 17:54:31.948",
                    "val": 70
        "desc":"箱内土壤的湿度，检测的数所有延迟，水在土壤里有个渗透的过程"
                },


            
        ],
        "制冷":"off",
        "加热":"off",
        "通风":"off",
        "加co2":"off",
        "补光":"off",
        "浇水":"off"
    }
"""



if __name__ == "__main__":
    tool = CheckSensor()
    info = tool.run("")
    print(info)
