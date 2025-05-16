from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import json
import sys
import threading
import time
from utils import util

# 添加项目根目录到sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# 导入项目中的模块
from llm.nlp_cognitive_stream import save_agent_memory, create_agent, set_memory_cleared_flag

# 创建Flask应用
app = Flask(__name__)

# 全局变量
instruction = ""
genagents_port = 5001
genagents_host = "0.0.0.0"
genagents_debug = True
server_thread = None
shutdown_flag = False
fay_agent = None

# 确保模板和静态文件目录存在
def setup_directories():
    os.makedirs(os.path.join(os.path.dirname(__file__), 'templates'), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), 'static'), exist_ok=True)

# 读取指令文件
def load_instruction():
    global instruction
    instruction_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instruction.json')
    if os.path.exists(instruction_file):
        try:
            with open(instruction_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                instruction = data.get('instruction', '')
            # 读取后删除文件，防止重复使用
            os.remove(instruction_file)
        except Exception as e:
            print(f"读取指令文件出错: {str(e)}")

@app.route('/')
def index():
    """提供主页HTML"""
    return render_template('decision_interview.html', instruction=instruction)

# 关闭服务器的函数
def shutdown_server():
    global shutdown_flag
    shutdown_flag = True
    # 不再直接访问request对象，而是设置标志让服务器自行关闭
    print("服务器将在处理完当前请求后关闭...")

# 清除记忆API
@app.route('/api/clear-memory', methods=['POST'])
def api_clear_memory():
    try:
        # 获取memory目录路径
        memory_dir = os.path.join(os.getcwd(), "memory")
        
        # 检查目录是否存在
        if not os.path.exists(memory_dir):
            return jsonify({'success': False, 'message': '记忆目录不存在'}), 400
        
        # 清空memory目录下的所有文件（保留目录结构）
        for root, dirs, files in os.walk(memory_dir):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        util.log(1, f"已删除文件: {file_path}")
                except Exception as e:
                    util.log(1, f"删除文件时出错: {file_path}, 错误: {str(e)}")
        
        # 删除memory_dir下的所有子目录
        import shutil
        for item in os.listdir(memory_dir):
            item_path = os.path.join(memory_dir, item)
            if os.path.isdir(item_path):
                try:
                    shutil.rmtree(item_path)
                    util.log(1, f"已删除目录: {item_path}")
                except Exception as e:
                    util.log(1, f"删除目录时出错: {item_path}, 错误: {str(e)}")
        
        # 创建一个标记文件，表示记忆已被清除，防止退出时重新保存
        with open(os.path.join(memory_dir, ".memory_cleared"), "w") as f:
            f.write("Memory has been cleared. Do not save on exit.")
        
        # 设置记忆清除标记
        try:
            # 导入并修改nlp_cognitive_stream模块中的保存函数
            from llm.nlp_cognitive_stream import set_memory_cleared_flag, clear_agent_memory
            
            # 设置记忆清除标记
            set_memory_cleared_flag(True)
            
            # 清除内存中已加载的记忆
            clear_agent_memory()
            
            util.log(1, "已同时清除文件存储和内存中的记忆")
        except Exception as e:
            util.log(1, f"清除内存中记忆时出错: {str(e)}")
        
        util.log(1, "记忆已清除，需要重启应用才能生效")
        return jsonify({'success': True, 'message': '记忆已清除，请重启应用使更改生效'}), 200
    except Exception as e:
        util.log(1, f"清除记忆时出错: {str(e)}")
        return jsonify({'success': False, 'message': f'清除记忆时出错: {str(e)}'}), 500

@app.route('/api/submit', methods=['POST'])
def submit_data():
    """处理提交的表单数据并将其添加到Agent的记忆中"""
    try:
        # 接收JSON格式的表单数据
        data = request.json
        
        if not data or 'dimensions' not in data:
            return jsonify({'status': 'error', 'message': '数据格式不正确'}), 400
        
        # 导入需要的函数
        from llm.nlp_cognitive_stream import get_current_time_step, save_agent_memory, create_agent
        
        # 确保Fay的agent已经初始化
        global fay_agent
        if fay_agent is None:
            fay_agent = create_agent()
        
        # 确保embeddings不为None
        if fay_agent.memory_stream.embeddings is None:
            fay_agent.memory_stream.embeddings = {}
        
        # 使用全局函数获取时间步
        time_step = get_current_time_step() + 1
        
        # 处理各维度数据
        for dimension_name, dimension_qa in data['dimensions'].items():
            # 为每个维度创建一个摘要记忆
            dimension_summary = f"决策分析维度: {dimension_name}\n"
            
            for qa_pair in dimension_qa:
                question = qa_pair.get('问题', '')
                answer = qa_pair.get('回答', '')
                dimension_summary += f"问题: {question}\n回答: {answer}\n\n"
            
            # 将维度摘要添加到Agent的记忆中
            fay_agent.remember(dimension_summary, time_step=time_step)
            time_step += 1
        
        # 添加一个总结记忆
        global instruction  # 明确声明使用全局变量
        summary = f"[系统指令] 基于以上决策分析，你的人格已被重新定义。"
        if 'instruction' in globals() and instruction:
            summary += f" 你需要遵循以下指令：{instruction}"
        
        fay_agent.remember(summary, time_step=time_step)
        
        # 保存记忆
        save_agent_memory()
        
        # 设置关闭标志，让服务器在响应后关闭
        global shutdown_flag
        shutdown_flag = True
        
        # 返回响应，添加自动关闭窗口的JavaScript代码
        return jsonify({
            'status': 'success', 
            'message': '决策分析数据已克隆到记忆中，请关闭页面并重启Fay',
            'redirect': 'http://localhost:8080/setting',
            'closeWindow': True  # 添加标志，指示前端关闭窗口
        })
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"处理决策分析数据时出错: {str(e)}\n{error_details}")
        return jsonify({'status': 'error', 'message': f'处理数据时出错: {str(e)}'}), 500

@app.route('/api/shutdown', methods=['POST'])
def shutdown():
    """手动关闭服务器的API"""
    shutdown_server()
    return jsonify({'status': 'success', 'message': '服务器正在关闭'})

@app.route('/static/<path:filename>')
def serve_static(filename):
    # 提供静态文件
    return send_from_directory('static', filename)

@app.route('/templates/<path:filename>')
def serve_template(filename):
    # 提供模板文件（仅用于调试）
    return send_from_directory('templates', filename)

# 全局变量，用于控制服务器关闭
shutdown_flag = False

# 检查是否请求关闭服务器
def is_shutdown_requested():
    global shutdown_flag
    return shutdown_flag

# 设置应用程序，复制必要的文件到正确的位置
def setup():
    setup_directories()
    
    # 确保decision_interview.html存在于templates目录
    template_source = os.path.join(os.path.dirname(__file__), 'decision_interview.html')
    template_dest = os.path.join(os.path.dirname(__file__), 'templates', 'decision_interview.html')
    
    if os.path.exists(template_source) and not os.path.exists(template_dest):
        import shutil
        shutil.copy2(template_source, template_dest)

# 启动决策分析服务
def start_genagents_server(instruction_text="", port=None, host=None, debug=None):
    global instruction, genagents_port, genagents_host, genagents_debug, shutdown_flag
    
    # 重置关闭标志
    shutdown_flag = False
    
    # 设置指令
    if instruction_text:
        instruction = instruction_text
    else:
        load_instruction()
    
    # 设置服务器参数
    if port is not None:
        genagents_port = port
    if host is not None:
        genagents_host = host
    if debug is not None:
        genagents_debug = debug
    
    # 设置应用
    setup()
    
    # 返回应用实例，但不启动
    return app

# 直接运行时启动服务器
if __name__ == '__main__':
    setup()  # 确保所有必要的目录和文件都存在
    load_instruction()  # 加载指令
    print(f"启动Flask服务器，请访问 http://127.0.0.1:{genagents_port}/ 打开页面")
    
    # 使用Werkzeug的服务器，并添加关闭检查
    from werkzeug.serving import make_server
    
    # 创建服务器
    server = make_server(genagents_host, genagents_port, app)
    
    # 启动服务器，但在单独的线程中运行，以便我们可以检查shutdown_flag
    import threading
    
    def run_server():
        server.serve_forever()
    
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    
    # 主线程检查shutdown_flag
    try:
        while not is_shutdown_requested():
            time.sleep(1)
    except KeyboardInterrupt:
        print("接收到键盘中断，正在关闭服务器...")
    finally:
        print("正在关闭服务器...")
        server.shutdown()