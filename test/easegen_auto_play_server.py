from flask import Flask, request, jsonify
import requests
import time
import threading
import tkinter as tk
from PIL import Image, ImageTk
import urllib.request
from io import BytesIO

app = Flask(__name__)

last_displayed_img_url = None

def display_image(img_url):
    global last_displayed_img_url
    if img_url == last_displayed_img_url:
        return

    last_displayed_img_url = img_url

    def run_display():
        root = tk.Tk()
        root.attributes('-fullscreen', False)
        root.configure(background='black')

        try:
            with urllib.request.urlopen(img_url) as url:
                image_data = url.read()
                image = Image.open(BytesIO(image_data))
                photo = ImageTk.PhotoImage(image)
                label = tk.Label(root, image=photo, bg='black')
                label.pack(expand=True)
        except Exception as e:
            label = tk.Label(root, text=f"无法加载图像: {str(e)}", fg='white', bg='black')
            label.pack(expand=True)

        root.bind("<Escape>", lambda e: root.destroy())
        root.mainloop()

    threading.Thread(target=run_display, daemon=True).start()

@app.route('/get_auto_play_item', methods=['POST'])
def get_wav():
    try:
        # 获取用户标识（例如，通过POST请求中的JSON数据）
        data = request.json
        user = data.get('user', 'User')

        # 通过HTTP GET请求从指定地址获取最新数据
        course_id = data.get('course_id', 1164)
        
        headers = {
            'easegen-api-key': 'ak_SzEhMFPTKjIQBhGVmkle'
        }
        
        response = requests.get(
            "http://36.103.251.108:48080/admin-api/digitalcourse/courses/getCourseText",
            params={
                'course_id': course_id,
            },
            headers=headers,
            timeout=10
        )
        
        # 检查请求是否成功
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('code') == 0:
                data = response_data.get('data', {})
                audio = data.get('audio', '')
                text = data.get('text', '')
                timestamp = data.get('timestamp', int(time.time()))
                img = data.get('img', '')

                # 显示图像
                if img:
                    display_image(img)
                
                # 返回的JSON响应
                return jsonify({
                    'audio': audio,
                    'text': text,
                    'timestamp': timestamp
                })
            else:
                return jsonify({'error': '获取数据失败'}), 500
        else:
            return jsonify({'error': '请求失败'}), 500
    except requests.exceptions.Timeout:
        return jsonify({'error': '请求超时'}), 500
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'请求出现异常: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6000)
