import json
import requests
# from core import content_db

class VllmGPT:

    def __init__(self, host="127.0.0.1",
                 port="8000",
                 model="THUDM/chatglm3-6b",
                 max_tokens="1024"):
        self.host = host
        self.port = port
        self.model=model
        self.max_tokens=max_tokens
        self.__URL = "http://{}:{}/v1/completions".format(self.host, self.port)
        self.__URL2 = "http://{}:{}/v1/chat/completions".format(self.host, self.port)

    def question(self,cont):
        chat_list = []
        url = "http://127.0.0.1:8101/v1/completions"
        req = json.dumps({
            "model": "THUDM/chatglm3-6b",
            "prompt": cont,
            "max_tokens": 768,
            "temperature": 0})
        print(url)
        print(req)
        
        headers = {'content-type': 'application/json'}
        r = requests.post(url, headers=headers, data=req)
        res = json.loads(r.text)
        
        return res['choices'][0]['text']

    def question2(self,cont):
        chat_list = []
        current_chat={"role": "user", "content": cont}
        chat_list.append(current_chat)
        content = {
            "model": self.model,
            "messages": chat_list,
            "max_tokens": 768,
            "temperature": 0.3,
            "user":"live-virtual-digital-person"}
        url = self.__URL2
        req = json.dumps(content)
        headers = {'content-type': 'application/json', 'Authorization': 'Bearer '}
        r = requests.post(url, headers=headers, json=content)
        res = json.loads(r.text)
        
        return res['choices'][0]['message']['content']
    
if __name__ == "__main__":
    vllm = VllmGPT('127.0.0.1','8101','Qwen-7B-Chat')
    req = vllm.question2("你叫什么名字啊今年多大了")
    print(req)
