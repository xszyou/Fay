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
        # content = {
        #     "model": self.model,
        #     "prompt": cont,
        #     "max_tokens": 768,
        #     "temperature": 0}
        # url = self.__URL
        # req = json.dumps(content,ensure_ascii=False)
        # print(req)
        # headers = {'content-type': 'application/json'}
        # r = requests.get(url, headers=headers, data=req)
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
        # print(res)
        return res['choices'][0]['text']
        # return r

    def question2(self,cont):
        chat_list = []
        # contentdb = content_db.new_instance()
        # list = contentdb.get_list('all','desc',11)
        # answer_info = dict()
        chat_list = []
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
        print(url)
        print(req)
        # headers = {'content-type': 'application/json'}
        headers = {'content-type': 'application/json', 'Authorization': 'Bearer '}
        r = requests.post(url, headers=headers, json=content)
        res = json.loads(r.text)
        
        return res['choices'][0]['message']['content']
    
if __name__ == "__main__":
    vllm = VllmGPT('127.0.0.1','8101')
    req = vllm.question2("你叫什么名字啊今年多大了")
    print(req)
    # url = "http://127.0.0.1:8101/v1/completions"
    # req = json.dumps({
    #     "model": "THUDM/chatglm3-6b",
    #     "prompt": "你叫什么名字啊今年多大了",
    #     "max_tokens": 768,
    #     "temperature": 0})
    # print(url)
    # print(req)

    # headers = {'content-type': 'application/json'}
    # r = requests.post(url, headers=headers, data=req)
    # a = json.loads(r.text)['choices'][0]['text']
    # print(a)
