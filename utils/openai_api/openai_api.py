import os
import openai
 
# 设置OpenAI API的密钥
# openai.api_key = os.getenv("OPENAI_API_KEY")
openai.base_url = "http://127.0.0.1:8000/v1/chat/completions"
# 定义API请求的数据
data = {
    "model": "chatglm3-6b",
    "prompt": "Say this is a test",
    "temperature": 0.5,  # 控制输出结果的随机性，范围从0.0到1.0，越高越随机
    "max_tokens": 75,    # 控制输出文本的长度
    "top_p": 1,          # 一个更复杂的参数，与temperature类似但更加精细控制
    "n": 1,              # 要返回的最完整的文本段落数
    "stream": False      # 是否以流的形式返回输出
}

# 发送API请求
response = openai.Completion.create(**data)

# 打印响应结果
print(response.get("choices")[0]["text"])