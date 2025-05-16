import requests
import json

def test_gpt_nonstream(prompt):
    url = 'http://127.0.0.1:5000/v1/chat/completions'  # 替换为您的接口地址
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer YOUR_API_KEY',  # 如果您的接口需要身份验证
    }
    data = {
        'model': 'fay',
        'messages': [
            {'role': '小敏', 'content': prompt}
        ],
        'stream': False  # 禁用流式传输，使用非流式响应
    }

    response = requests.post(url, headers=headers, data=json.dumps(data))

    if response.status_code != 200:
        print(f"请求失败，状态码：{response.status_code}")
        print(f"响应内容：{response.text}")
        return

    # 处理非流式响应
    try:
        response_data = response.json()
        
        # 从响应中提取内容
        choices = response_data.get('choices', [])
        if choices:
            message = choices[0].get('message', {})
            content = message.get('content', '')
            print(f"完整响应内容: {content}")
            
            # 打印一些额外的响应信息
            print(f"\n请求ID: {response_data.get('id', 'N/A')}")
            print(f"模型: {response_data.get('model', 'N/A')}")
            
            # 打印使用量信息
            usage = response_data.get('usage', {})
            if usage:
                print(f"Token 使用情况:")
                print(f"  - 提示词 tokens: {usage.get('prompt_tokens', 0)}")
                print(f"  - 补全 tokens: {usage.get('completion_tokens', 0)}")
                print(f"  - 总计 tokens: {usage.get('total_tokens', 0)}")
            
            return content
    except json.JSONDecodeError:
        print(f"无法解析响应数据为JSON: {response.text}")
    except Exception as e:
        print(f"处理响应时出错: {str(e)}")

if __name__ == "__main__":
    user_input = "哈哈"
    print("发送请求到 GPT API (非流式模式)...")
    print("-" * 50)
    test_gpt_nonstream(user_input)
    print("-" * 50)
    print("请求完成") 