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
        # contentdb = content_db.new_instance()
        # list = contentdb.get_list('all','desc',11)
        # answer_info = dict()
        # chat_list = []
        # i = len(list)-1
        # while i >= 0:
        #     answer_info = dict()
        #     if list[i][0] == "member":
        #         answer_info["role"] = "user"
        #         answer_info["content"] = list[i][2]
        #     elif list[i][0] == "fay":
        #         answer_info["role"] = "bot"
        #         answer_info["content"] = list[i][2]
        #     chat_list.append(answer_info)
        #     i -= 1
        content = {
            "model": self.model,
            "prompt":"请简单回复我。" +  cont,
            "history":chat_list}
        url = self.__URL
        req = json.dumps(content)
        
        headers = {'content-type': 'application/json'}
        r = requests.post(url, headers=headers, data=req)
        res = json.loads(r.text)
        
        return res['choices'][0]['text']

    def question2(self,cont):
        chat_list = []
        # contentdb = content_db.new_instance()
        # list = contentdb.get_list('all','desc',11)
        # answer_info = dict()
        # chat_list = []
        # i = len(list)-1
        # while i >= 0:
        #     answer_info = dict()
        #     if list[i][0] == "member":
        #         answer_info["role"] = "user"
        #         answer_info["content"] = list[i][2]
        #     elif list[i][0] == "fay":
        #         answer_info["role"] = "bot"
        #         answer_info["content"] = list[i][2]
        #     chat_list.append(answer_info)
        #     i -= 1
        content = {
            "model": self.model,
            "prompt":"请简单回复我。" +  cont,
            "history":chat_list}
        url = self.__URL2
        req = json.dumps(content)
        
        headers = {'content-type': 'application/json'}
        r = requests.post(url, headers=headers, data=req)
        res = json.loads(r.text)
        
        return res['choices'][0]['message']['content']
    
if __name__ == "__main__":
    vllm = VllmGPT('192.168.1.3','8101')
    req = vllm.question("你叫什么名字啊今年多大了")
    print(req)
