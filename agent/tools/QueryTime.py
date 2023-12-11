import abc
import math
from typing import Any
from datetime import datetime
from langchain.tools import BaseTool

class QueryTime(BaseTool, abc.ABC):
    name = "QueryTime"
    description = "用于查询当前日期、星期几及时间" 

    def __init__(self):
        super().__init__()

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        # 用例中没有用到 arun 不予具体实现
        pass

    def _run(self, para) -> str:
        # 获取当前时间
        now = datetime.now()
         # 获取当前日期
        today = now.date()
        # 获取星期几的信息
        week_day = today.strftime("%A")
        # 将星期几的英文名称转换为中文
        week_day_zh = {
            "Monday": "星期一",
            "Tuesday": "星期二",
            "Wednesday": "星期三",
            "Thursday": "星期四",
            "Friday": "星期五",
            "Saturday": "星期六",
            "Sunday": "星期日",
        }.get(week_day, "未知")
        # 将日期格式化为字符串
        date_str = today.strftime("%Y年%m月%d日")
        
        # 将时间格式化为字符串
        time_str = now.strftime("%H:%M")

        return "现在时间是：{0} {1} {2}".format(time_str, week_day_zh, date_str)

if __name__ == "__main__":
    tool = QueryTime()
    result = tool.run("")
    print(result)
