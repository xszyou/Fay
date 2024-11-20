import abc
from typing import Any
from langchain.tools import BaseTool
import fay_booter

class SendToPanel(BaseTool, abc.ABC):
    name = "SendToPanel"
    description = "用于给主人面板发送消息，使用时请传入消息内容作为参数。" 

    def __init__(self):
        super().__init__()

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        # 用例中没有用到 arun 不予具体实现
        pass

    def _run(self, para) -> str:
        fay_booter.feiFei.send_to_panel(para)
        return "成功给主人,发送消息：{}".format(para)
        


if __name__ == "__main__":
    tool = SendToPanel()
    result = tool.run("归纳一下近年关于“经济发展”的论文的特点和重点")
    print(result)
