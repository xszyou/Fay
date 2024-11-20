from bs4 import BeautifulSoup
import abc
from typing import Any
from langchain.tools import BaseTool
import requests

class WebPageScraper(BaseTool, abc.ABC):
    name: str = "WebPageScraper"
    description: str = "此工具用于获取网页内容，使用时请传入需要查询的网页地址作为参数，如：https://www.baidu.com/。" 
 
    def __init__(self):
        super().__init__()

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        # 用例中没有用到 arun 不予具体实现
        pass

    def _run(self, para) -> str:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
        try:
            response = requests.get(para, headers=headers, timeout=10, verify=True)
            soup = BeautifulSoup(response.text, 'html.parser')
            return soup
        except requests.exceptions.SSLCertVerificationError:
            return 'SSL证书验证失败'
        except requests.exceptions.Timeout:
            return '请求超时'
        except Exception as e:
            print("Http Error:", e)
            return '无法获取该网页内容'
        
if __name__ == "__main__":
    tool = WebPageScraper()
    result = tool.run("https://book.douban.com/review/14636204")
    print(result)