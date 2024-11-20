import abc
from typing import Any
from langchain.tools import BaseTool
import re
import random
class ToRemind(BaseTool, abc.ABC):
    name: str = "ToRemind"
    description: str = ("用于实时发送信息提醒主人做某事项（不能带时间），传入事项内容作为参数。")

    def __init__(self):
        super().__init__()

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        # 用例中没有用到 arun 不予具体实现
        pass

    def _run(self, para: str) -> str:
     
        para = para.replace("提醒", "回复")
        demo = [
        "主人！是时候（事项内容）了喔~",
        "亲爱的主人，现在是（事项内容）的时候啦！",
        "嘿，主人，该（事项内容）了哦~",
        "温馨提醒：（事项内容）的时间到啦，主人！",
        "小提醒：主人，现在可以（事项内容）了~"
        ]

        return f"直接以中文友善{para}，如"+ random.choice(demo)

if __name__ == "__main__":
    my_timer = ToRemind()
    result = my_timer._run("提醒主人叫咖啡")
    print(result)
