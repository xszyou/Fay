#!/usr/bin/env python3
"""
Fay日程管理Web服务器
提供独立的网页界面和API接口
"""

import os
import sys
import json
import sqlite3
import datetime

# 检查并安装依赖
try:
    from flask import Flask, jsonify, request, send_from_directory
    from flask_cors import CORS
except ImportError:
    print("正在安装必要的依赖包...")
    import subprocess
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'flask', 'flask-cors'])
        from flask import Flask, jsonify, request, send_from_directory
        from flask_cors import CORS
        print("依赖包安装完成")
    except Exception as e:
        print(f"安装依赖包失败: {e}")
        print("请手动运行: pip install flask flask-cors")
        sys.exit(1)

# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 数据库文件路径
DB_PATH = os.path.join(os.path.dirname(__file__), 'schedules.db')

class ScheduleWebAPI:
    """日程管理Web API类"""
    
    def __init__(self):
        self.init_database()
    
    def init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                schedule_time TEXT NOT NULL,
                repeat_rule TEXT NOT NULL DEFAULT '0000000',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                uid INTEGER DEFAULT 0
            )
        ''')
        conn.commit()
        conn.close()
    
    def get_schedules(self, status='active', uid=None):
        """获取日程列表"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            if uid is not None:
                if status == 'all':
                    # 'all' 表示显示所有未删除的日程（active + completed）
                    cursor.execute("SELECT * FROM schedules WHERE status != 'deleted' AND uid = ? ORDER BY schedule_time", (uid,))
                else:
                    cursor.execute("SELECT * FROM schedules WHERE status = ? AND uid = ? ORDER BY schedule_time", (status, uid))
            else:
                if status == 'all':
                    # 'all' 表示显示所有未删除的日程（active + completed）
                    cursor.execute("SELECT * FROM schedules WHERE status != 'deleted' ORDER BY schedule_time")
                else:
                    cursor.execute("SELECT * FROM schedules WHERE status = ? ORDER BY schedule_time", (status,))
            
            rows = cursor.fetchall()
            conn.close()
            
            schedules = []
            for row in rows:
                schedules.append({
                    "id": row[0],
                    "title": row[1],
                    "content": row[2],
                    "schedule_time": row[3],
                    "repeat_rule": row[4],
                    "status": row[5],
                    "created_at": row[6],
                    "updated_at": row[7],
                    "uid": row[8]
                })
            
            return {"success": True, "schedules": schedules}
            
        except Exception as e:
            return {"success": False, "message": f"获取日程列表失败: {str(e)}"}
    
    def add_schedule(self, title, content, schedule_time, repeat_rule='0000000', uid=0):
        """添加日程"""
        try:
            # 验证时间格式
            try:
                datetime.datetime.strptime(schedule_time, '%Y-%m-%d %H:%M')
            except ValueError:
                return {"success": False, "message": "时间格式错误，请使用 YYYY-MM-DD HH:MM 格式"}
            
            # 验证重复规则
            if not all(c in '01' for c in repeat_rule) or len(repeat_rule) != 7:
                return {"success": False, "message": "重复规则格式错误"}
            
            now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO schedules (title, content, schedule_time, repeat_rule, created_at, updated_at, uid) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (title, content, schedule_time, repeat_rule, now, now, uid)
            )
            schedule_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return {"success": True, "message": "日程添加成功", "schedule_id": schedule_id}
            
        except Exception as e:
            return {"success": False, "message": f"添加日程失败: {str(e)}"}
    
    def update_schedule(self, schedule_id, title=None, content=None, schedule_time=None, repeat_rule=None, status=None):
        """更新日程"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # 先获取当前日程信息
            cursor.execute("SELECT status, repeat_rule FROM schedules WHERE id = ?", (schedule_id,))
            current_schedule = cursor.fetchone()
            if not current_schedule:
                conn.close()
                return {"success": False, "message": "日程不存在"}
            
            current_status, current_repeat_rule = current_schedule
            
            # 构建更新语句
            updates = []
            params = []
            auto_activate = False  # 是否需要自动激活
            
            if title is not None:
                updates.append("title = ?")
                params.append(title)
            if content is not None:
                updates.append("content = ?")
                params.append(content)
            if schedule_time is not None:
                # 验证时间格式
                try:
                    new_time = datetime.datetime.strptime(schedule_time, '%Y-%m-%d %H:%M')
                    updates.append("schedule_time = ?")
                    params.append(schedule_time)
                    
                    # 如果更新了时间，并且当前状态是completed，检查是否需要重新激活
                    if current_status == 'completed':
                        now = datetime.datetime.now()
                        # 如果新时间在未来，或者是重复任务，自动激活
                        if new_time > now or (repeat_rule or current_repeat_rule) != '0000000':
                            auto_activate = True
                            print(f"[Web] 日程 ID {schedule_id} 时间更新，自动从completed恢复为active")
                            
                except ValueError:
                    return {"success": False, "message": "时间格式错误"}
            if repeat_rule is not None:
                if not all(c in '01' for c in repeat_rule) or len(repeat_rule) != 7:
                    return {"success": False, "message": "重复规则格式错误"}
                updates.append("repeat_rule = ?")
                params.append(repeat_rule)
                
                # 如果从单次改为重复，并且当前是completed，自动激活
                if current_status == 'completed' and repeat_rule != '0000000':
                    auto_activate = True
                    print(f"[Web] 日程 ID {schedule_id} 改为重复任务，自动从completed恢复为active")
                    
            # 处理状态更新
            if status is not None:
                updates.append("status = ?")
                params.append(status)
            elif auto_activate:
                # 如果需要自动激活，并且没有明确指定状态，则设置为active
                updates.append("status = ?")
                params.append('active')
                print(f"[Web] 日程 ID {schedule_id} 状态设置为active")
            
            if not updates:
                return {"success": False, "message": "没有提供要更新的字段"}
            
            updates.append("updated_at = ?")
            params.append(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            params.append(schedule_id)
            
            cursor.execute(f"UPDATE schedules SET {', '.join(updates)} WHERE id = ?", params)
            
            if cursor.rowcount == 0:
                conn.close()
                return {"success": False, "message": "日程不存在"}
            
            conn.commit()
            
            # 如果有更新时间或状态，通知调度器重新调度（通过创建触发文件）
            if schedule_time is not None or repeat_rule is not None or status is not None or auto_activate:
                # 创建一个触发文件，让调度器知道需要重新检查
                trigger_file = os.path.join(os.path.dirname(__file__), f'.reschedule_{schedule_id}')
                try:
                    with open(trigger_file, 'w') as f:
                        f.write(str(datetime.datetime.now()))
                    print(f"[Web] 创建重新调度触发文件: {trigger_file}")
                except:
                    pass
            
            conn.close()
            
            if auto_activate:
                return {"success": True, "message": "日程更新成功，状态已自动恢复为活跃"}
            else:
                return {"success": True, "message": "日程更新成功"}
            
        except Exception as e:
            return {"success": False, "message": f"更新日程失败: {str(e)}"}
    
    def delete_schedule(self, schedule_id):
        """删除日程（软删除）"""
        return self.update_schedule(schedule_id, status='deleted')

# 创建API实例
schedule_api = ScheduleWebAPI()

# Web路由
@app.route('/')
def index():
    """主页，返回日程管理网页"""
    return send_from_directory(os.path.dirname(__file__), 'schedule_web.html')

@app.route('/api/schedule/list')
def api_get_schedules():
    """获取日程列表API"""
    status = request.args.get('status', 'all')
    uid = request.args.get('uid', type=int)
    result = schedule_api.get_schedules(status, uid)
    return jsonify(result)

@app.route('/api/schedule/create', methods=['POST'])
def api_create_schedule():
    """创建日程API"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "无效的请求数据"})
    
    title = data.get('title')
    content = data.get('content', '')
    schedule_time = data.get('schedule_time')
    repeat_rule = data.get('repeat_rule', '0000000')
    uid = data.get('uid', 0)
    
    if not title or not schedule_time:
        return jsonify({"success": False, "message": "标题和时间为必填项"})
    
    result = schedule_api.add_schedule(title, content, schedule_time, repeat_rule, uid)
    return jsonify(result)

@app.route('/api/schedule/update/<int:schedule_id>', methods=['PUT'])
def api_update_schedule(schedule_id):
    """更新日程API"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "无效的请求数据"})
    
    result = schedule_api.update_schedule(
        schedule_id,
        title=data.get('title'),
        content=data.get('content'),
        schedule_time=data.get('schedule_time'),
        repeat_rule=data.get('repeat_rule'),
        status=data.get('status')
    )
    return jsonify(result)

@app.route('/api/schedule/complete/<int:schedule_id>', methods=['PUT'])
def api_complete_schedule(schedule_id):
    """完成日程API - 直接删除"""
    result = schedule_api.delete_schedule(schedule_id)
    return jsonify(result)

@app.route('/api/schedule/delete/<int:schedule_id>', methods=['DELETE'])
def api_delete_schedule(schedule_id):
    """删除日程API"""
    result = schedule_api.delete_schedule(schedule_id)
    return jsonify(result)

@app.route('/api/health')
def api_health():
    """健康检查API"""
    return jsonify({"status": "ok", "message": "Fay日程管理服务运行正常"})

if __name__ == '__main__':
    import argparse
    import signal
    import atexit
    import threading
    import time
    
    try:
        import psutil
        HAS_PSUTIL = True
    except ImportError:
        HAS_PSUTIL = False
        print("警告: psutil未安装，无法监控父进程")
    
    # 获取父进程ID
    parent_pid = os.getppid()
    
    def cleanup():
        print("Web服务器正在关闭...")
    
    def signal_handler(sig, frame):
        print(f"收到信号 {sig}，正在关闭Web服务器...")
        cleanup()
        sys.exit(0)
    
    def monitor_parent():
        """监控父进程，如果父进程不存在则退出"""
        if not HAS_PSUTIL:
            return
            
        while True:
            try:
                # 检查父进程是否还存在
                if not psutil.pid_exists(parent_pid):
                    print(f"父进程 {parent_pid} 已退出，关闭Web服务器...")
                    cleanup()
                    os._exit(0)  # 强制退出
                time.sleep(5)  # 每5秒检查一次
            except Exception as e:
                print(f"监控父进程时出错: {e}")
                time.sleep(5)
    
    # 注册清理和信号处理
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 启动父进程监控线程
    if HAS_PSUTIL:
        try:
            monitor_thread = threading.Thread(target=monitor_parent, daemon=True)
            monitor_thread.start()
            print(f"已启动父进程监控 (父进程PID: {parent_pid})")
        except Exception as e:
            print(f"启动父进程监控失败: {e}")
    else:
        print("跳过父进程监控（psutil不可用）")
    
    parser = argparse.ArgumentParser(description='Fay日程管理Web服务器')
    parser.add_argument('--host', default='127.0.0.1', help='服务器地址')
    parser.add_argument('--port', default=5011, type=int, help='服务器端口')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    
    args = parser.parse_args()
    
    print(f"启动Fay日程管理Web服务器...")
    print(f"访问地址: http://{args.host}:{args.port}")
    print(f"API文档: http://{args.host}:{args.port}/api/health")
    
    try:
        app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)
    except KeyboardInterrupt:
        print("Web服务器已停止")
    except Exception as e:
        print(f"Web服务器启动失败: {e}")
        sys.exit(1)