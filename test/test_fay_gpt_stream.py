import requests
import json

def test_gpt(prompt, username="张三", observation="", no_reply=False):
    url = 'http://127.0.0.1:5000/v1/chat/completions'  # 替换为您的接口地址
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer YOUR_API_KEY',  # 如果您的接口需要身份验证
    }
    data = {
        'model': 'fay-streaming', #model为llm时，会直接透传到上游的llm输出，fay不作任何处理、记录
        'messages': [
            {'role': username, 'content': prompt}
        ],
        'stream': True,  # 启用流式传输
        'observation': observation,  # 观察数据
        'no_reply': no_reply
    }

    print(f"[用户] {username}: {prompt}")
    if observation:
        print(f"[观察数据] {observation}")
    print("-" * 50)
    print("[Fay回复] ", end="")

    response = requests.post(url, headers=headers, data=json.dumps(data), stream=True)

    if response.status_code != 200:
        print(f"请求失败，状态码：{response.status_code}")
        print(f"响应内容：{response.text}")
        return

    # 处理流式响应
    for line in response.iter_lines(decode_unicode=True):
        if line:
            if line.strip() == 'data: [DONE]':
                print("\n流式传输完成")
                break
            # 每一行数据以 'data: ' 开头，去掉这个前缀
            if line.startswith('data:'):
                line = line[5:].strip()
                # 将 JSON 字符串解析为字典
                try:
                    data = json.loads(line)
                    # 从数据中提取生成的内容
                    choices = data.get('choices')
                    if choices:
                        delta = choices[0].get('delta', {})
                        content = delta.get('content', '')
                        if content:
                            print(content, end='', flush=True)
                except json.JSONDecodeError:
                    print(f"\n无法解析的 JSON 数据：{line}")
            else:
                print(f"\n收到未知格式的数据：{line}")

# 观察数据样本
OBSERVATION_SAMPLES = {
    "张三": """识别到对话的人是张三
认知状态：正常
听力：正常
视力：正常
兴趣爱好：写代码、音乐、电影
避免话题：学习成绩""",

    "李奶奶": """识别到对话的人是李奶奶
认知状态：轻度记忆衰退
听力：需要大声说话
视力：正常
兴趣爱好：养花、看戏曲、聊家常
避免话题：子女工作压力""",

    "王叔叔": """识别到对话的人是王叔叔
认知状态：正常
听力：正常
视力：老花眼
兴趣爱好：钓鱼、下棋、看新闻
避免话题：退休金""",

    "小明": """识别到对话的人是小明
认知状态：正常
听力：正常
视力：正常
年龄：10岁
兴趣爱好：玩游戏、看动画片、踢足球
避免话题：考试分数、作业""",
}

if __name__ == "__main__":
    # 示例1：带观察数据的对话
    print("=" * 60)
    print("示例1：张三的对话（带观察数据）")
    print("=" * 60)
    test_gpt("你好，今天天气不错啊", username="user", observation=OBSERVATION_SAMPLES["张三"])

    print("\n")

    # 示例2：不带观察数据的对话
    # print("=" * 60)
    # print("示例2：普通对话（不带观察数据）")
    # print("=" * 60)
    # test_gpt("你好", username="User", observation="")

    # 示例3：李奶奶的对话
    # print("=" * 60)
    # print("示例3：李奶奶的对话")
    # print("=" * 60)
    # test_gpt("小菲啊，我今天有点闷", username="李奶奶", observation=OBSERVATION_SAMPLES["李奶奶"])

    print("\n请求完成")
