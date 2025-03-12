"""
用户模拟自动播报服务器，在数字人教师、广告机和主播这种除了交互还需要主动输出的场景，可以使用自动播报服务器

"""
from flask import Flask, request, jsonify
import time

app = Flask(__name__)

@app.route('/get_auto_play_item', methods=['POST'])
def get_wav():
    # 获取用户标识（例如，通过POST请求中的JSON数据）
    # data = request.json
    # user = data.get('user', 'User')

    # 模拟WAV文件的URL（这里假设是某个静态文件服务的URL）
    wav_url = ""#f"http://120.79.187.154:5000/audio/sample-1729231423801.wav"

    # 模拟返回的文本
    response_text = "今天天气晴朗，适合外出哦！你有什么计划吗？" + str(time.time())

    # 获取当前时间戳，单位为秒
    timestamp = int(time.time())

    # 返回的JSON响应
    response = {
        'audio': wav_url,
        'text': response_text,
        'timestamp': timestamp
    }

    return jsonify(response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6000)
