#!/usr/bin/env python3
"""
Fay日程管理MCP Server
基于agent目录逻辑实现的本地日程管理系统，支持与Fay文字沟通接口集成
"""

import os
import sys
import json
import sqlite3
import datetime
import threading
import time
import asyncio
import logging
import requests
import subprocess
import signal
import atexit
import re
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager

# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

try:
    from mcp.server import Server
    from mcp.types import Resource, Tool, TextContent, ImageContent, EmbeddedResource
    import mcp.server.stdio
    from pydantic import AnyUrl
except ImportError:
    print("MCP库未安装，请运行: pip install mcp")
    sys.exit(1)

# 配置Fay API地址
FAY_API_URL = "http://127.0.0.1:5000/v1/chat/completions"
FAY_NOTIFY_URL = "http://127.0.0.1:5000/api/schedule/notify"  # 专用的日程提醒接口

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("schedule_manager")

# 数据库文件路径
DB_PATH = os.path.join(os.path.dirname(__file__), 'schedules.db')

class ScheduleManager:
    """日程管理核心类"""
    
    def __init__(self):
        self.scheduled_tasks = {}
        self.task_threads = {}
        self.executed_tasks = {}  # 记录已执行的任务，防止重复执行
        self.scheduler_lock_file = os.path.join(os.path.dirname(__file__), '.scheduler.lock')
        self.scheduler_running = False
        self.web_server_process = None
        self.init_database()
        self.start_scheduler()
        # 不在初始化时启动Web服务器，而是在MCP连接时启动
    
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
        logger.info("数据库初始化完成")
    
    def add_schedule(self, title: str, content: str, schedule_time: str, repeat_rule: str = '0000000', uid: int = 0) -> Dict[str, Any]:
        """添加日程"""
        try:
            # 验证时间格式
            try:
                datetime.datetime.strptime(schedule_time, '%Y-%m-%d %H:%M')
            except ValueError:
                try:
                    # 如果只有时间，默认为今天
                    time_part = datetime.datetime.strptime(schedule_time, '%H:%M').time()
                    schedule_time = datetime.datetime.combine(datetime.date.today(), time_part).strftime('%Y-%m-%d %H:%M')
                except ValueError:
                    return {"success": False, "message": "时间格式错误，请使用 YYYY-MM-DD HH:MM 或 HH:MM 格式"}
            
            # 验证重复规则
            if not all(c in '01' for c in repeat_rule) or len(repeat_rule) != 7:
                return {"success": False, "message": "重复规则格式错误，应为7位数字，每位代表周一到周日(1=重复,0=不重复)"}
            
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
            
            logger.info(f"添加日程成功: {title} - {schedule_time}")
            return {"success": True, "message": "日程添加成功", "schedule_id": schedule_id}
            
        except Exception as e:
            logger.error(f"添加日程失败: {e}")
            return {"success": False, "message": f"添加日程失败: {str(e)}"}
    
    def get_schedules(self, status: str = 'active', uid: Optional[int] = None) -> List[Dict[str, Any]]:
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
            
            return schedules
            
        except Exception as e:
            logger.error(f"获取日程列表失败: {e}")
            return []
    
    def update_schedule(self, schedule_id: int, title: Optional[str] = None, content: Optional[str] = None, 
                       schedule_time: Optional[str] = None, repeat_rule: Optional[str] = None, 
                       status: Optional[str] = None) -> Dict[str, Any]:
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
                            logger.info(f"日程 ID {schedule_id} 时间更新，自动从completed恢复为active")
                            
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
                    logger.info(f"日程 ID {schedule_id} 改为重复任务，自动从completed恢复为active")
                    
            # 处理状态更新
            if status is not None:
                updates.append("status = ?")
                params.append(status)
            elif auto_activate:
                # 如果需要自动激活，并且没有明确指定状态，则设置为active
                updates.append("status = ?")
                params.append('active')
                status = 'active'  # 更新status变量以便后续重新调度
            
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
            conn.close()
            
            # 如果更新了时间相关字段或状态，需要重新调度定时器
            if schedule_time is not None or repeat_rule is not None or status is not None or auto_activate:
                self._reschedule_task(schedule_id)
            
            logger.info(f"更新日程成功: ID {schedule_id}")
            if auto_activate:
                return {"success": True, "message": "日程更新成功，状态已自动恢复为活跃"}
            else:
                return {"success": True, "message": "日程更新成功"}
            
        except Exception as e:
            logger.error(f"更新日程失败: {e}")
            return {"success": False, "message": f"更新日程失败: {str(e)}"}
    
    def delete_schedule(self, schedule_id: int) -> Dict[str, Any]:
        """删除日程（软删除）"""
        try:
            # 先取消定时器和清理执行记录
            if schedule_id in self.task_threads:
                if isinstance(self.task_threads[schedule_id], threading.Timer):
                    self.task_threads[schedule_id].cancel()
                    logger.info(f"已取消删除任务 ID {schedule_id} 的定时器")
                del self.task_threads[schedule_id]
            
            # 清除执行记录
            executed_keys_to_remove = [key for key in self.executed_tasks.keys() if key.startswith(f"{schedule_id}_")]
            for key in executed_keys_to_remove:
                del self.executed_tasks[key]
            
            # 更新数据库状态为删除，但不触发重新调度
            return self._update_schedule_without_reschedule(schedule_id, status='deleted')
            
        except Exception as e:
            logger.error(f"删除日程失败: {e}")
            return {"success": False, "message": f"删除日程失败: {str(e)}"}
    
    def _update_schedule_without_reschedule(self, schedule_id: int, **kwargs) -> Dict[str, Any]:
        """更新日程但不触发重新调度（内部方法）"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # 构建更新语句
            updates = []
            params = []
            
            for field, value in kwargs.items():
                if value is not None:
                    if field == 'schedule_time':
                        # 验证时间格式
                        try:
                            datetime.datetime.strptime(value, '%Y-%m-%d %H:%M')
                        except ValueError:
                            return {"success": False, "message": "时间格式错误"}
                    elif field == 'repeat_rule':
                        if not all(c in '01' for c in value) or len(value) != 7:
                            return {"success": False, "message": "重复规则格式错误"}
                    
                    updates.append(f"{field} = ?")
                    params.append(value)
            
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
            conn.close()
            
            logger.info(f"更新日程成功(无重新调度): ID {schedule_id}")
            return {"success": True, "message": "日程更新成功"}
            
        except Exception as e:
            logger.error(f"更新日程失败: {e}")
            return {"success": False, "message": f"更新日程失败: {str(e)}"}
    
    def _reschedule_task(self, schedule_id: int):
        """重新调度任务定时器"""
        try:
            logger.info(f"开始重新调度任务 ID {schedule_id}")
            
            # 1. 彻底清理task_threads中的记录（包括Timer对象和状态标记）
            if schedule_id in self.task_threads:
                task_item = self.task_threads[schedule_id]
                if isinstance(task_item, threading.Timer):
                    task_item.cancel()
                    logger.info(f"已取消任务 ID {schedule_id} 的旧定时器")
                elif isinstance(task_item, str):
                    logger.info(f"清理任务 ID {schedule_id} 的状态标记: {task_item}")
                del self.task_threads[schedule_id]
            
            # 2. 彻底清除executed_tasks中的所有相关执行记录
            # 包括所有可能的时间戳组合
            executed_keys_to_remove = []
            for key in list(self.executed_tasks.keys()):
                # 匹配所有与此schedule_id相关的记录
                if key.startswith(f"{schedule_id}_") or f"_{schedule_id}_" in key:
                    executed_keys_to_remove.append(key)
            
            for key in executed_keys_to_remove:
                del self.executed_tasks[key]
                logger.info(f"已清除任务 ID {schedule_id} 的执行记录: {key}")
            
            # 3. 获取更新后的日程信息（包括所有状态）
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM schedules WHERE id = ?", (schedule_id,))
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                logger.warning(f"找不到任务 ID {schedule_id}")
                return
            
            # 构建日程对象
            updated_schedule = {
                "id": row[0],
                "title": row[1],
                "content": row[2],
                "schedule_time": row[3],
                "repeat_rule": row[4],
                "status": row[5],
                "created_at": row[6],
                "updated_at": row[7],
                "uid": row[8] if len(row) > 8 else 0
            }
            
            # 4. 只有active状态的任务才重新调度
            if updated_schedule['status'] != 'active':
                logger.info(f"任务 ID {schedule_id} 状态为 {updated_schedule['status']}，不进行调度")
                return
            
            # 5. 计算下次执行时间并重新调度
            next_time = self.parse_repeat_rule(updated_schedule['repeat_rule'], updated_schedule['schedule_time'])
            if next_time:
                current_time = datetime.datetime.now()
                
                # 对于刚修改的任务，即使时间刚过期也允许立即执行
                if next_time > current_time:
                    self.schedule_task(updated_schedule, next_time)
                    logger.info(f"任务 ID {schedule_id} 已重新调度到 {next_time}")
                elif (current_time - next_time).total_seconds() < 300:  # 5分钟内
                    logger.info(f"任务 ID {schedule_id} 刚过期，立即执行")
                    self.execute_schedule_task(updated_schedule)
                    
                    # 如果是重复任务，计算下一次执行时间
                    if updated_schedule['repeat_rule'] != '0000000':
                        # 计算明天或下个周期的执行时间
                        tomorrow = current_time + datetime.timedelta(days=1)
                        next_next_time = self.parse_repeat_rule(updated_schedule['repeat_rule'], 
                                                               tomorrow.strftime('%Y-%m-%d') + ' ' + 
                                                               updated_schedule['schedule_time'].split(' ')[1])
                        if next_next_time and next_next_time > current_time:
                            self.schedule_task(updated_schedule, next_next_time)
                            logger.info(f"重复任务 ID {schedule_id} 下次执行时间: {next_next_time}")
                else:
                    logger.warning(f"任务 ID {schedule_id} 已过期超过5分钟: {next_time}")
            else:
                logger.info(f"任务 ID {schedule_id} 不需要调度")
                
        except Exception as e:
            logger.error(f"重新调度任务 ID {schedule_id} 失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def get_repeat_text(self, repeat_rule: str) -> str:
        """获取重复规则文本 - 与web界面保持一致"""
        if repeat_rule == '0000000':
            return '单次执行'
        
        days = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        repeat_days = []
        for i in range(7):
            if repeat_rule[i] == '1':
                repeat_days.append(days[i])
        
        if len(repeat_days) == 7:
            return '每日重复'
        elif len(repeat_days) == 5 and repeat_rule[5:7] == '00':  # 工作日
            return '工作日重复'
        else:
            return '重复: ' + ', '.join(repeat_days)
    
    def format_datetime(self, date_time_str: str) -> str:
        """格式化日期时间 - 与web界面保持一致"""
        try:
            dt = datetime.datetime.strptime(date_time_str, '%Y-%m-%d %H:%M')
            return dt.strftime('%Y-%m-%d %H:%M')
        except ValueError:
            return date_time_str
    
    def parse_natural_language_schedule(self, text: str, uid: int = 0):
        """解析自然语言日程指令"""
        try:
            # 清理输入文本
            text = text.strip()
            
            # 提取时间信息的正则模式
            time_patterns = [
                (r'明天\s*(上午|下午|中午|晚上|早上)\s*(\d{1,2})\s*[点时]?(\d{0,2})\s*分?', 1, 'time_with_period'),
                (r'明天\s*(\d{1,2})\s*[点时](\d{0,2})\s*分?', 1, 'time_only'),
                (r'后天\s*(上午|下午|中午|晚上|早上)\s*(\d{1,2})\s*[点时]?(\d{0,2})\s*分?', 2, 'time_with_period'),
                (r'后天\s*(\d{1,2})\s*[点时](\d{0,2})\s*分?', 2, 'time_only'),
                (r'今天\s*(上午|下午|中午|晚上|早上)\s*(\d{1,2})\s*[点时]?(\d{0,2})\s*分?', 0, 'time_with_period'),
                (r'今天\s*(\d{1,2})\s*[点时](\d{0,2})\s*分?', 0, 'time_only'),
                (r'(\d{1,2})\s*分钟后', 0, 'minutes_later'),
                (r'(\d{1,2})\s*小时后', 0, 'hours_later'),
            ]
            
            # 提取任务内容的模式 - 移除时间和提醒词汇
            task_extract_patterns = [
                r'(提醒我|叫我|提醒)\s*(.+)',
                r'(.+)\s*(提醒|提示)',
                r'(.+)'  # 最后的兜底模式
            ]
            
            schedule_time = None
            task_content = None
            
            # 尝试匹配时间模式
            for pattern, day_offset, pattern_type in time_patterns:
                match = re.search(pattern, text)
                if match:
                    try:
                        base_date = datetime.date.today() + datetime.timedelta(days=day_offset)
                        
                        if pattern_type == 'time_with_period':
                            period = match.group(1)
                            hour = int(match.group(2))
                            minute = int(match.group(3)) if match.group(3) else 0
                            
                            # 根据时间段调整小时
                            if period in ['下午', '晚上'] and hour < 12:
                                hour += 12
                            elif period in ['上午', '早上'] and hour == 12:
                                hour = 0
                            elif period == '中午' and hour != 12:
                                hour = 12
                                
                        elif pattern_type == 'time_only':
                            hour = int(match.group(1))
                            minute = int(match.group(2)) if match.group(2) else 0
                            
                        elif pattern_type == 'minutes_later':
                            minutes = int(match.group(1))
                            target_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
                            schedule_time = target_time.strftime('%Y-%m-%d %H:%M')
                            break
                            
                        elif pattern_type == 'hours_later':
                            hours = int(match.group(1))
                            target_time = datetime.datetime.now() + datetime.timedelta(hours=hours)
                            schedule_time = target_time.strftime('%Y-%m-%d %H:%M')
                            break
                        
                        if pattern_type not in ['minutes_later', 'hours_later']:
                            # 确保时间合法
                            if 0 <= hour <= 23 and 0 <= minute <= 59:
                                schedule_time = f"{base_date.strftime('%Y-%m-%d')} {hour:02d}:{minute:02d}"
                        
                        if schedule_time:
                            # 从原文中移除时间部分
                            remaining_text = re.sub(pattern, '', text).strip()
                            break
                            
                    except ValueError:
                        continue
            
            # 如果没有找到具体时间，使用默认时间
            if not schedule_time:
                # 默认为明天上午9点
                tomorrow = datetime.date.today() + datetime.timedelta(days=1)
                schedule_time = f"{tomorrow.strftime('%Y-%m-%d')} 09:00"
                remaining_text = text
            else:
                remaining_text = remaining_text or text
            
            # 提取任务内容
            for pattern in task_extract_patterns:
                match = re.search(pattern, remaining_text, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    if len(groups) == 2:
                        # 如果有两个捕获组，选择更有意义的那个
                        task_content = groups[1] if groups[1] and len(groups[1].strip()) > len(groups[0].strip()) else groups[0]
                    else:
                        task_content = groups[0]
                    task_content = task_content.strip()
                    
                    # 清理任务内容中的无用词汇
                    cleanup_words = ['提醒我', '叫我', '提醒', '提示', '的', '了', '吧', '呀', '啊']
                    for word in cleanup_words:
                        task_content = task_content.replace(word, '').strip()
                    
                    if task_content:
                        break
            
            # 如果还是没有提取到内容，使用原始文本
            if not task_content or len(task_content.strip()) < 2:
                task_content = text
            
            # 生成更合适的标题和内容
            title = task_content
            content = f"提醒事项：{task_content}"
            
            # 调用原有的添加日程功能
            result = self.add_schedule(title, content, schedule_time, '0000000', uid)
            
            # 返回解析结果
            if result.get('success'):
                parsed_info = {
                    "原始指令": text,
                    "解析的时间": schedule_time,
                    "提取的任务": task_content,
                    "生成的标题": title,
                    "生成的内容": content
                }
                result["解析信息"] = parsed_info
                logger.info(f"自然语言解析成功: {parsed_info}")
            
            return result
            
        except Exception as e:
            logger.error(f"自然语言解析失败: {e}")
            return {"success": False, "message": f"解析指令失败: {str(e)}"}
    
    def send_to_fay(self, message: str, uid: int = 0):
        """发送消息给Fay - 使用v1/chat/completions接口"""
        print("***********************************************************************")
        logger.info(f"[DEBUG] send_to_fay 被调用，消息: {message}, uid: {uid}")
        
        # 防止消息重复发送
        msg_hash = hash(f"{message}_{uid}_{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
        if hasattr(self, '_sent_messages'):
            if msg_hash in self._sent_messages:
                logger.warning(f"[DEBUG] 消息在1分钟内已发送过，跳过: {message}")
                return
        else:
            self._sent_messages = set()
        
        self._sent_messages.add(msg_hash)
        
        try:
            # 使用线程发送，避免阻塞
            def send_message():
                try:
                    logger.info(f"[DEBUG] 开始发送HTTP请求到Fay API")
                    # 获取用户名
                    username = f"User{uid}" if uid > 0 else "User"
                    
                    # 构建请求数据 - 使用v1/chat/completions格式
                    payload = {
                        "messages": [
                            {
                                "role": "user",
                                "content": message
                            }
                        ],
                        "model": "fay-streaming",
                        "stream": False  # 使用非流式响应
                    }
                    
                    logger.info(f"[DEBUG] 请求payload: {payload}")
                    
                    # 发送HTTP请求到v1/chat/completions接口
                    response = requests.post(
                        FAY_API_URL,
                        json=payload,
                        headers={
                            "Content-Type": "application/json"
                        },
                        timeout=30
                    )
                    
                    logger.info(f"[DEBUG] HTTP响应状态码: {response.status_code}")
                    
                    if response.status_code == 200:
                        logger.info(f"消息已发送给Fay: {message}")
                        try:
                            resp_data = response.json()
                            logger.debug(f"Fay响应: {resp_data}")
                        except:
                            logger.debug(f"Fay响应: {response.text[:200]}")
                    else:
                        logger.error(f"Fay API响应错误: {response.status_code} - {response.text}")
                        
                except requests.exceptions.RequestException as e:
                    logger.error(f"发送消息给Fay失败 (网络错误): {e}")
                except Exception as e:
                    logger.error(f"发送消息给Fay失败: {e}")
            
            thread = threading.Thread(target=send_message)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            logger.error(f"发送消息给Fay失败: {e}")
    
    def parse_repeat_rule(self, rule: str, task_time: str) -> Optional[datetime.datetime]:
        """解析重复规则，返回下次执行时间"""
        try:
            task_datetime = datetime.datetime.strptime(task_time, '%Y-%m-%d %H:%M')
            now = datetime.datetime.now()
            
            if rule == '0000000':  # 不重复
                if task_datetime > now:
                    return task_datetime
                else:
                    return None
            else:
                # 重复任务，找到下一个执行时间
                today = now.date()
                task_time_obj = task_datetime.time()
                
                # 检查今天是否需要执行
                weekday = today.weekday()  # 0=周一，6=周日
                if rule[weekday] == '1':
                    today_task_time = datetime.datetime.combine(today, task_time_obj)
                    if today_task_time > now:
                        return today_task_time
                
                # 找到下一个执行日期
                for i in range(1, 8):
                    next_day = today + datetime.timedelta(days=i)
                    next_weekday = next_day.weekday()
                    if rule[next_weekday] == '1':
                        return datetime.datetime.combine(next_day, task_time_obj)
                
                return None
                
        except Exception as e:
            logger.error(f"解析重复规则失败: {e}")
            return None
    
    def execute_schedule_task(self, schedule: Dict[str, Any]):
        """执行日程任务"""
        schedule_id = schedule['id']
        
        # 检查是否在短时间内已执行过（防止重复执行）
        now = datetime.datetime.now()
        executed_key = f"{schedule_id}_{schedule['schedule_time']}"
        
        if executed_key in self.executed_tasks:
            last_executed = self.executed_tasks[executed_key]
            if (now - last_executed).total_seconds() < 120:  # 2分钟内不重复执行
                logger.warning(f"[DEBUG] 任务 {schedule['title']} (ID: {schedule_id}) 在2分钟内已执行过，跳过")
                return
        
        logger.info(f"[DEBUG] 开始执行日程任务: {schedule['title']} (ID: {schedule_id}), 时间: {now}")
        logger.info(f"[DEBUG] task_threads 当前内容: {list(self.task_threads.keys())}")
        logger.info(f"[DEBUG] executed_tasks 当前内容: {list(self.executed_tasks.keys())}")
        
        # 记录执行时间
        self.executed_tasks[executed_key] = now
        
        # 构建消息
        message = f"【日程提醒】{schedule['title']}: {schedule['content']}"
        
        # 发送给Fay
        logger.info(f"[DEBUG] 准备发送消息给Fay: {message}")
        self.send_to_fay(message, schedule['uid'])
        
        # 标记任务已执行
        self.task_threads[schedule_id] = "executed"
        
        # 如果是非重复任务，直接删除
        if schedule['repeat_rule'] == '0000000':
            logger.info(f"[DEBUG] 单次任务执行完成，直接删除: ID {schedule_id}")
            result = self.delete_schedule(schedule['id'])
            logger.info(f"[DEBUG] 删除结果: {result}")
            if not result.get('success'):
                logger.error(f"[ERROR] 删除任务失败: {result.get('message')}")
        else:
            logger.info(f"[DEBUG] 重复任务，保持active状态: ID {schedule_id}")
        # 注意：重复任务的下次调度会在下一次schedule_loop中自动处理
    
    def schedule_task(self, schedule: Dict[str, Any], execute_time: datetime.datetime):
        """调度任务执行"""
        schedule_id = schedule['id']
        
        # 取消之前的任务（如果是Timer对象）
        if schedule_id in self.task_threads:
            if isinstance(self.task_threads[schedule_id], threading.Timer):
                self.task_threads[schedule_id].cancel()
            del self.task_threads[schedule_id]
        
        # 计算延迟时间
        current_time = datetime.datetime.now()
        delay = (execute_time - current_time).total_seconds()
        
        if delay > 0:
            # 创建定时器
            timer = threading.Timer(delay, self.execute_schedule_task, args=[schedule])
            timer.start()
            self.task_threads[schedule_id] = timer
            logger.info(f"任务已调度: {schedule['title']} 将在 {execute_time} 执行")
        elif delay > -60:  # 刚过期不到1分钟，立即执行
            logger.warning(f"[DEBUG] 任务 {schedule['title']} 刚过期 {-delay:.1f} 秒，立即执行")
            # 直接执行任务
            self.execute_schedule_task(schedule)
        else:
            # 任务已过期超过1分钟，直接标记为已完成（对于非重复任务）
            logger.warning(f"[DEBUG] 任务 {schedule['title']} 已过期 {-delay/60:.1f} 分钟")
            if schedule['repeat_rule'] == '0000000':
                logger.info(f"[DEBUG] 非重复任务已过期，标记为completed: ID {schedule_id}")
                self.update_schedule(schedule_id, status='completed')
            # 标记为已处理，防止重复调度
            self.task_threads[schedule_id] = "expired"
    
    def start_scheduler(self):
        """启动调度器"""
        
        # 检查是否已有调度器在运行
        if os.path.exists(self.scheduler_lock_file):
            # 检查锁文件的时间，如果超过2分钟认为是死锁
            try:
                lock_time = os.path.getmtime(self.scheduler_lock_file)
                if time.time() - lock_time < 120:  # 2分钟内
                    logger.info("调度器已在其他进程中运行，跳过启动")
                    return
                else:
                    logger.warning("检测到过期的调度器锁，清理并重新启动")
                    os.remove(self.scheduler_lock_file)
            except:
                pass
        
        # 创建锁文件
        try:
            with open(self.scheduler_lock_file, 'w') as f:
                f.write(str(os.getpid()))
            self.scheduler_running = True
        except:
            logger.error("无法创建调度器锁文件")
            return
        
        def schedule_loop():
            loop_count = 0
            while self.scheduler_running:
                try:
                    loop_count += 1
                    current_time = datetime.datetime.now()
                    logger.info(f"[DEBUG] === 调度循环 #{loop_count} 开始 === 时间: {current_time}")
                    
                    # 检查锁文件PID是否与当前进程匹配
                    if os.path.exists(self.scheduler_lock_file):
                        try:
                            with open(self.scheduler_lock_file, 'r') as f:
                                lock_pid = int(f.read().strip())
                            current_pid = os.getpid()
                            if lock_pid != current_pid:
                                logger.error(f"[ERROR] 检测到PID冲突！锁文件PID: {lock_pid}, 当前PID: {current_pid}")
                                logger.error("[ERROR] 有其他调度器进程在运行，退出当前调度器")
                                self.scheduler_running = False
                                break
                        except:
                            pass
                        # 更新锁文件时间
                        os.utime(self.scheduler_lock_file, None)
                    else:
                        logger.error("[ERROR] 锁文件丢失，退出调度器")
                        self.scheduler_running = False
                        break
                    
                    # 检查是否有重新调度触发文件
                    reschedule_dir = os.path.dirname(self.scheduler_lock_file)
                    for filename in os.listdir(reschedule_dir):
                        if filename.startswith('.reschedule_'):
                            try:
                                # 提取schedule_id
                                schedule_id = int(filename.replace('.reschedule_', ''))
                                trigger_file = os.path.join(reschedule_dir, filename)
                                
                                logger.info(f"[DEBUG] 发现重新调度触发文件: {filename}, 日程ID: {schedule_id}")
                                
                                # 删除触发文件
                                os.remove(trigger_file)
                                
                                # 强制重新调度该任务
                                self._reschedule_task(schedule_id)
                                logger.info(f"[DEBUG] 已处理重新调度请求: ID {schedule_id}")
                                
                            except Exception as e:
                                logger.error(f"处理重新调度触发文件失败: {e}")
                    
                    # 每10分钟清理一次过期的执行记录
                    if loop_count % 20 == 0:  # 20 * 30秒 = 10分钟
                        now = datetime.datetime.now()
                        expired_keys = []
                        for key, exec_time in self.executed_tasks.items():
                            if (now - exec_time).total_seconds() > 600:  # 10分钟前的记录
                                expired_keys.append(key)
                        for key in expired_keys:
                            del self.executed_tasks[key]
                        if expired_keys:
                            logger.info(f"[DEBUG] 清理了 {len(expired_keys)} 个过期执行记录")
                    
                    # 获取所有活跃的日程
                    schedules = self.get_schedules('active')
                    logger.info(f"[DEBUG] 本次循环获取到 {len(schedules)} 个活跃任务")
                    
                    for schedule in schedules:
                        logger.info(f"[DEBUG] 处理任务: ID={schedule['id']}, 标题='{schedule['title']}', 状态='{schedule['status']}'")
                        schedule_id = schedule['id']
                        
                        # 解析执行时间
                        next_time = self.parse_repeat_rule(schedule['repeat_rule'], schedule['schedule_time'])
                        
                        logger.debug(f"[DEBUG] 处理任务 ID {schedule_id}: {schedule['title']}, next_time={next_time}, 当前时间={datetime.datetime.now()}")
                        
                        if next_time:
                            # 如果任务已经在调度中，跳过
                            if schedule_id in self.task_threads:
                                # 任务已被调度过，不管Timer是否还活着都跳过
                                # 这防止了同一任务被多次调度
                                logger.debug(f"[DEBUG] 任务 ID {schedule_id} 已在 task_threads 中，跳过")
                                continue
                            
                            # 只有当任务时间还未到且未被调度时才创建新的Timer
                            current_time = datetime.datetime.now()
                            if next_time > current_time:
                                logger.info(f"调度任务 {schedule['title']} (ID: {schedule_id}) 将在 {next_time} 执行")
                                self.schedule_task(schedule, next_time)
                            else:
                                logger.warning(f"[DEBUG] 任务 ID {schedule_id} 时间已过期: {next_time} < {current_time}")
                        else:
                            logger.debug(f"[DEBUG] 任务 ID {schedule_id} parse_repeat_rule 返回 None")
                    
                    # 每30秒检查一次（参考agent_service.py的实现）
                    time.sleep(30)
                    
                except Exception as e:
                    logger.error(f"调度器错误: {e}")
                    time.sleep(60)
        
        # 启动调度线程
        # 注册退出时清理锁文件
        def cleanup_lock():
            if self.scheduler_running and os.path.exists(self.scheduler_lock_file):
                try:
                    os.remove(self.scheduler_lock_file)
                    logger.info("调度器锁文件已清理")
                except:
                    pass
            self.scheduler_running = False
        
        atexit.register(cleanup_lock)
        
        scheduler_thread = threading.Thread(target=schedule_loop)
        scheduler_thread.daemon = True
        scheduler_thread.start()
        logger.info("日程调度器已启动")
    
    def start_web_server(self):
        """启动Web服务器"""
        try:
            # 如果已经有Web服务器在运行，先停止它
            if self.web_server_process is not None:
                self.stop_web_server()
            
            # 检查web_server.py文件是否存在
            web_server_path = os.path.join(os.path.dirname(__file__), 'web_server.py')
            if not os.path.exists(web_server_path):
                logger.warning("web_server.py 文件不存在，跳过启动Web服务器")
                return
            
            # 启动Web服务器进程
            self.web_server_process = subprocess.Popen(
                [sys.executable, 'web_server.py', '--host', '127.0.0.1', '--port', '5011'],
                cwd=os.path.dirname(__file__),
                stdout=subprocess.DEVNULL,  # 不显示输出，避免干扰MCP通信
                stderr=subprocess.DEVNULL
            )
            
            # 等待一小段时间检查进程是否正常启动
            time.sleep(2)
            if self.web_server_process and self.web_server_process.poll() is None:
                logger.info("Web服务器已启动 - 访问地址: http://127.0.0.1:5011")
            else:
                logger.warning("Web服务器启动失败")
                self.web_server_process = None
                        
        except Exception as e:
            logger.error(f"启动Web服务器失败: {e}")
            self.web_server_process = None
    
    def stop_web_server(self):
        """停止Web服务器"""
        if self.web_server_process:
            try:
                # 先尝试正常终止
                self.web_server_process.terminate()
                try:
                    self.web_server_process.wait(timeout=3)
                    logger.info("Web服务器已正常停止")
                except subprocess.TimeoutExpired:
                    # 如果3秒内没有停止，强制杀死
                    self.web_server_process.kill()
                    self.web_server_process.wait(timeout=2)
                    logger.info("Web服务器已强制停止")
                self.web_server_process = None
            except Exception as e:
                logger.error(f"停止Web服务器失败: {e}")
                self.web_server_process = None

# 全局日程管理器实例
schedule_manager = ScheduleManager()

# 注册清理函数
def cleanup():
    """清理函数"""
    try:
        logger.info("正在清理资源...")
        schedule_manager.stop_web_server()
    except Exception as e:
        logger.error(f"清理资源时出错: {e}")

atexit.register(cleanup)

# 信号处理
def signal_handler(signum, frame):
    """信号处理函数"""
    logger.info(f"收到信号 {signum}，正在退出...")
    cleanup()
    sys.exit(0)

# 注册信号处理器
try:
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    # Windows特有信号
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, signal_handler)
except Exception as e:
    logger.warning(f"注册信号处理器失败: {e}")

# 创建MCP服务器
server = Server("schedule-manager")

@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """返回可用工具列表"""
    return [
        Tool(
            name="add_schedule",
            description="添加新的日程安排",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "日程标题"
                    },
                    "content": {
                        "type": "string", 
                        "description": "日程详细内容"
                    },
                    "schedule_time": {
                        "type": "string",
                        "description": "执行时间，格式: YYYY-MM-DD HH:MM 或 HH:MM（默认今天）"
                    },
                    "repeat_rule": {
                        "type": "string",
                        "description": "重复规则，7位数字，每位代表周一到周日(1=重复,0=不重复)，默认'0000000'",
                        "default": "0000000"
                    },
                    "uid": {
                        "type": "integer",
                        "description": "用户ID，默认0",
                        "default": 0
                    }
                },
                "required": ["title", "content", "schedule_time"]
            }
        ),
        Tool(
            name="get_schedules",
            description="获取日程列表",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "日程状态筛选: active(活跃), completed(已完成), deleted(已删除)",
                        "default": "active"
                    },
                    "uid": {
                        "type": "integer",
                        "description": "用户ID筛选，不提供则获取所有用户的日程"
                    }
                }
            }
        ),
        Tool(
            name="update_schedule",
            description="更新日程信息",
            inputSchema={
                "type": "object",
                "properties": {
                    "schedule_id": {
                        "type": "integer",
                        "description": "日程ID"
                    },
                    "title": {
                        "type": "string",
                        "description": "新的标题"
                    },
                    "content": {
                        "type": "string",
                        "description": "新的内容"
                    },
                    "schedule_time": {
                        "type": "string",
                        "description": "新的执行时间，格式: YYYY-MM-DD HH:MM"
                    },
                    "repeat_rule": {
                        "type": "string",
                        "description": "新的重复规则"
                    },
                    "status": {
                        "type": "string",
                        "description": "新的状态: active, completed, deleted"
                    }
                },
                "required": ["schedule_id"]
            }
        ),
        Tool(
            name="delete_schedule",
            description="删除日程（软删除）",
            inputSchema={
                "type": "object",
                "properties": {
                    "schedule_id": {
                        "type": "integer",
                        "description": "要删除的日程ID"
                    }
                },
                "required": ["schedule_id"]
            }
        ),
        Tool(
            name="send_message_to_fay",
            description="直接发送消息给Fay",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "要发送的消息内容"
                    },
                    "uid": {
                        "type": "integer",
                        "description": "用户ID",
                        "default": 0
                    }
                },
                "required": ["message"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """处理工具调用"""
    
    if name == "add_schedule":
        result = schedule_manager.add_schedule(
            title=arguments["title"],
            content=arguments["content"],
            schedule_time=arguments["schedule_time"],
            repeat_rule=arguments.get("repeat_rule", "0000000"),
            uid=arguments.get("uid", 0)
        )
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
    
    elif name == "get_schedules":
        schedules = schedule_manager.get_schedules(
            status=arguments.get("status", "active"),
            uid=arguments.get("uid")
        )
        return [TextContent(type="text", text=json.dumps(schedules, ensure_ascii=False, indent=2))]
    
    elif name == "update_schedule":
        result = schedule_manager.update_schedule(
            schedule_id=arguments["schedule_id"],
            title=arguments.get("title"),
            content=arguments.get("content"),
            schedule_time=arguments.get("schedule_time"),
            repeat_rule=arguments.get("repeat_rule"),
            status=arguments.get("status")
        )
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
    
    elif name == "delete_schedule":
        result = schedule_manager.delete_schedule(arguments["schedule_id"])
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
    
    elif name == "send_message_to_fay":
        schedule_manager.send_to_fay(
            message=arguments["message"],
            uid=arguments.get("uid", 0)
        )
        return [TextContent(type="text", text=json.dumps({"success": True, "message": "消息已发送给Fay"}, ensure_ascii=False))]
    
    else:
        return [TextContent(type="text", text=f"未知工具: {name}")]

async def main():
    """主函数"""
    logger.info("Fay日程管理MCP Server 启动中...")
    
    try:
        # 使用stdio传输运行服务器
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            # MCP连接建立时启动Web服务器
            schedule_manager.start_web_server()
            logger.info("MCP连接已建立，Web服务器已启动")
            
            # 使用服务器的标准初始化选项
            init_opts = server.create_initialization_options()
            await server.run(read_stream, write_stream, init_opts)
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭服务器...")
    except Exception as e:
        logger.error(f"MCP服务器运行错误: {e}")
    finally:
        # MCP连接断开时关闭Web服务器
        schedule_manager.stop_web_server()
        logger.info("MCP服务器已关闭，Web服务器已停止")

if __name__ == "__main__":
    asyncio.run(main())
