import os
from typing import Any

import requests
from langchain.tools import BaseTool


class Weather(BaseTool):
    name = "weather"
    description = "Use for searching weather at a specific location"

    def __init__(self):
        super().__init__()

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        # 用例中没有用到 arun 不予具体实现
        pass


    def _run(self, para: str) -> str:
        return "今天天气晴朗，风和日丽，气温25度，空气十分清新，心情美美哒"


if __name__ == "__main__":
    weather_tool = Weather()
    weather_info = weather_tool.run("成都")
    print(weather_info)
