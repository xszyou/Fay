"""
这是对于清华智谱VisualGLM-6B的代码，在使用前请先安装并启动好VisualGLM-6B.
https://github.com/THUDM/VisualGLM-6B
"""
import json
import requests
import uuid
import os
import cv2
from ai_module import yolov8

# Initialize an empty history list
communication_history = []

def question(cont):
    if not yolov8.new_instance().get_status():
        return "请先启动“Fay Eyes”"
    content = {
        "text":cont,
        "history":communication_history}
    img = yolov8.new_instance().get_img()
    if yolov8.new_instance().get_status() and img is not None:
        filename = str(uuid.uuid4()) + ".jpg"
        current_working_directory = os.getcwd()
        filepath = os.path.join(current_working_directory, "data", filename)
        cv2.imwrite(filepath, img)
        content["image"] = filepath
    url = "http://127.0.0.1:8080"
    print(content)
    req = json.dumps(content)
    headers = {'content-type': 'application/json'}
    r = requests.post(url, headers=headers, data=req)

    # Save this conversation to history
    communication_history.append([cont, r.text])

    return r.text + "\n(相片:" + filepath + ")"