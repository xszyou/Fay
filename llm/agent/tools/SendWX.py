import abc
from typing import Any
from langchain.tools import BaseTool
import requests
import json

url = "http://127.0.0.1:4008/send"
headers = {'Content-Type': 'application/json'}
data = {
    "message": "你好",
    "receiver": "@2efc4e10cf2eafd0b0125930e4b96ed0cebffa75b2fd272590e38763225a282b"
}


class SendWX(BaseTool, abc.ABC):
    name = "SendWX"
    description = "给主人微信发送消息，传入参数是:('消息内容')" 

    def __init__(self):
        super().__init__()

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        # 用例中没有用到 arun 不予具体实现
        pass

    def _run(self, para) -> str:
        global data
        data['message'] = para
        response = requests.post(url, headers=headers, data=json.dumps(data))
        return "成功给主人,发送微信消息：{}".format(para)

