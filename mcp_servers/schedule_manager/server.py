#!/usr/bin/env python3
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

# 娣诲姞椤圭洰鏍圭洰褰曞埌Python璺緞
def _runtime_dir():
    if getattr(sys, "frozen", False):
        return os.path.abspath(os.path.dirname(sys.executable))
    return os.path.abspath(os.path.dirname(__file__))


def _project_root():
    if getattr(sys, "frozen", False):
        return os.path.abspath(os.path.join(_runtime_dir(), "..", ".."))
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


RUNTIME_DIR = _runtime_dir()
project_root = _project_root()
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from mcp.server import Server
    from mcp.types import Resource, Tool, TextContent, ImageContent, EmbeddedResource
    import mcp.server.stdio
    from pydantic import AnyUrl
except ImportError:
    print("MCP搴撴湭瀹夎锛岃杩愯: pip install mcp")
    sys.exit(1)

# 閰嶇疆Fay API鍦板潃
FAY_API_URL = "http://127.0.0.1:5000/v1/chat/completions"
FAY_NOTIFY_URL = "http://127.0.0.1:5000/api/schedule/notify"  # 涓撶敤鐨勬棩绋嬫彁閱掓帴鍙?

# 閰嶇疆鏃ュ織
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("schedule_manager")

# 鏁版嵁搴撴枃浠惰矾寰?
DB_PATH = os.path.join(RUNTIME_DIR, 'schedules.db')

class ScheduleManager:

    
    def __init__(self):
        self.scheduled_tasks = {}
        self.task_threads = {}
        self.executed_tasks = {}  # 璁板綍宸叉墽琛岀殑浠诲姟锛岄槻姝㈤噸澶嶆墽琛?
        self.scheduler_lock_file = os.path.join(RUNTIME_DIR, '.scheduler.lock')
        self.scheduler_running = False
        self.web_server_process = None
        self.init_database()
        self.start_scheduler()
        # 涓嶅湪鍒濆鍖栨椂鍚姩Web鏈嶅姟鍣紝鑰屾槸鍦∕CP杩炴帴鏃跺惎鍔?
    
    def init_database(self):
        try:
            # 楠岃瘉骞舵爣鍑嗗寲鏃堕棿鏍煎紡锛屽彧淇濈暀 HH:MM
            try:
                # 灏濊瘯瑙ｆ瀽瀹屾暣鏍煎紡锛屾彁鍙栨椂闂撮儴鍒?
                if ' ' in schedule_time:
                    time_part = schedule_time.split(' ')[1]
                else:
                    time_part = schedule_time
                # 楠岃瘉鏃堕棿鏍煎紡
                datetime.datetime.strptime(time_part, '%H:%M')
                schedule_time = time_part  # 鍙繚瀛?HH:MM
            except ValueError:
                return {"success": False, "message": "Invalid time format, use HH:MM such as 09:30."}

            # 楠岃瘉閲嶅瑙勫垯
            if not all(c in '01' for c in repeat_rule) or len(repeat_rule) != 7:
                return {"success": False, "message": "閲嶅瑙勫垯鏍煎紡閿欒锛屽簲涓?浣嶆暟瀛楋紝姣忎綅浠ｈ〃鍛ㄤ竴鍒板懆鏃?1=閲嶅,0=涓嶉噸澶?"}

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

            logger.info(f"娣诲姞鏃ョ▼鎴愬姛: {title} - {schedule_time} (閲嶅瑙勫垯: {repeat_rule})")
            return {"success": True, "message": "鏃ョ▼娣诲姞鎴愬姛", "schedule_id": schedule_id}

        except Exception as e:
            logger.error(f"娣诲姞鏃ョ▼澶辫触: {e}")
            return {"success": False, "message": f"娣诲姞鏃ョ▼澶辫触: {str(e)}"}
    
    def get_schedules(self, status: str = 'active', uid: Optional[int] = None) -> List[Dict[str, Any]]:
        try:
            # 瑙ｆ瀽鏃堕棿锛堝彧鏈?HH:MM锛?
            # 鍏煎鏃ф牸寮?YYYY-MM-DD HH:MM
            if ' ' in task_time:
                time_str = task_time.split(' ')[1]
            else:
                time_str = task_time
            task_time_obj = datetime.datetime.strptime(time_str, '%H:%M').time()
            now = datetime.datetime.now()
            today = now.date()

            if rule == '0000000':
                # 鍗曟鎵ц锛氭壘鏈€杩戠殑鎵ц鏃堕棿锛堜粖澶╂垨鏄庡ぉ锛?
                today_task_time = datetime.datetime.combine(today, task_time_obj)
                if today_task_time > now:
                    # 浠婂ぉ杩樻病鍒拌繖涓椂闂达紝浠婂ぉ鎵ц
                    return today_task_time
                else:
                    # 浠婂ぉ宸茶繃锛屾槑澶╂墽琛?
                    tomorrow = today + datetime.timedelta(days=1)
                    return datetime.datetime.combine(tomorrow, task_time_obj)
            else:
                # 閲嶅浠诲姟锛氭壘涓嬩竴涓鍚堣鍒欑殑鎵ц鏃堕棿
                # 鍏堟鏌ヤ粖澶?
                weekday = today.weekday()  # 0=鍛ㄤ竴锛?=鍛ㄦ棩
                if rule[weekday] == '1':
                    today_task_time = datetime.datetime.combine(today, task_time_obj)
                    if today_task_time > now:
                        return today_task_time

                # 鎵句笅涓€涓墽琛屾棩鏈?
                for i in range(1, 8):
                    next_day = today + datetime.timedelta(days=i)
                    next_weekday = next_day.weekday()
                    if rule[next_weekday] == '1':
                        return datetime.datetime.combine(next_day, task_time_obj)

                return None

        except Exception as e:
            logger.error(f"瑙ｆ瀽閲嶅瑙勫垯澶辫触: {e}")
            return None
    
    def execute_schedule_task(self, schedule: Dict[str, Any]):
        schedule_id = schedule['id']

        # 妫€鏌ユ槸鍚﹀湪鐭椂闂村唴宸叉墽琛岃繃锛堥槻姝㈤噸澶嶆墽琛岋級
        now = datetime.datetime.now()
        # 浣跨敤鏃ユ湡+鏃堕棿浣滀负鎵ц璁板綍鐨刱ey锛岀‘淇濇瘡澶╁彧鎵ц涓€娆?
        executed_key = f"{schedule_id}_{now.strftime('%Y-%m-%d')}_{schedule['schedule_time']}"

        if executed_key in self.executed_tasks:
            last_executed = self.executed_tasks[executed_key]
            if (now - last_executed).total_seconds() < 120:  # 2鍒嗛挓鍐呬笉閲嶅鎵ц
                logger.warning(f"Task {schedule['title']} (ID: {schedule_id}) already executed today, skip duplicate run")
                return

        logger.info(f"鎵ц鏃ョ▼浠诲姟: {schedule['title']} (ID: {schedule_id})")

        # 璁板綍鎵ц鏃堕棿
        self.executed_tasks[executed_key] = now

        # 鏋勫缓娑堟伅
        message = f"[Schedule Reminder] {schedule['title']}: {schedule['content']}"

        # 鍙戦€佺粰Fay
        self.send_to_fay(message, schedule['uid'])

        # 鏍囪浠诲姟宸叉墽琛岋紙鐢ㄤ簬鏈璋冨害鍛ㄦ湡锛?
        self.task_threads[schedule_id] = "executed"

        # 鏍规嵁閲嶅瑙勫垯澶勭悊鐘舵€?
        if schedule['repeat_rule'] == '0000000':
            # 鍗曟浠诲姟锛氭墽琛屽悗鏍囪涓?completed
            logger.info(f"鍗曟浠诲姟鎵ц瀹屾垚锛屾爣璁颁负completed: ID {schedule_id}")
            self.update_schedule(schedule_id, status='completed')
        else:
            # 閲嶅浠诲姟锛氫笉鍙樻洿鐘舵€侊紝涓嬫璋冨害寰幆浼氳嚜鍔ㄨ绠椾笅娆℃墽琛屾椂闂?
            logger.info(f"閲嶅浠诲姟鎵ц瀹屾垚锛屼繚鎸乤ctive鐘舵€? ID {schedule_id}")
    
    def schedule_task(self, schedule: Dict[str, Any], execute_time: datetime.datetime):
        """璋冨害浠诲姟鎵ц"""
        schedule_id = schedule['id']
        
        # 鍙栨秷涔嬪墠鐨勪换鍔★紙濡傛灉鏄疶imer瀵硅薄锛?
        if schedule_id in self.task_threads:
            if isinstance(self.task_threads[schedule_id], threading.Timer):
                self.task_threads[schedule_id].cancel()
            del self.task_threads[schedule_id]
        
        # 璁＄畻寤惰繜鏃堕棿
        current_time = datetime.datetime.now()
        delay = (execute_time - current_time).total_seconds()
        
        if delay > 0:
            # 鍒涘缓瀹氭椂鍣?
            timer = threading.Timer(delay, self.execute_schedule_task, args=[schedule])
            timer.start()
            self.task_threads[schedule_id] = timer
            logger.info(f"浠诲姟宸茶皟搴? {schedule['title']} 灏嗗湪 {execute_time} 鎵ц")
        elif delay > -60:  # 鍒氳繃鏈熶笉鍒?鍒嗛挓锛岀珛鍗虫墽琛?
            logger.warning(f"[DEBUG] 浠诲姟 {schedule['title']} 鍒氳繃鏈?{-delay:.1f} 绉掞紝绔嬪嵆鎵ц")
            # 鐩存帴鎵ц浠诲姟
            self.execute_schedule_task(schedule)
        else:
            # 浠诲姟宸茶繃鏈熻秴杩?鍒嗛挓锛岀洿鎺ユ爣璁颁负宸插畬鎴愶紙瀵逛簬闈為噸澶嶄换鍔★級
            logger.warning(f"[DEBUG] 浠诲姟 {schedule['title']} 宸茶繃鏈?{-delay/60:.1f} 鍒嗛挓")
            if schedule['repeat_rule'] == '0000000':
                logger.info(f"[DEBUG] 闈為噸澶嶄换鍔″凡杩囨湡锛屾爣璁颁负completed: ID {schedule_id}")
                self.update_schedule(schedule_id, status='completed')
            # 鏍囪涓哄凡澶勭悊锛岄槻姝㈤噸澶嶈皟搴?
            self.task_threads[schedule_id] = "expired"
    
    def start_scheduler(self):

        
        # 妫€鏌ユ槸鍚﹀凡鏈夎皟搴﹀櫒鍦ㄨ繍琛?
        if os.path.exists(self.scheduler_lock_file):
            # 妫€鏌ラ攣鏂囦欢鐨勬椂闂达紝濡傛灉瓒呰繃2鍒嗛挓璁や负鏄閿?
            try:
                lock_time = os.path.getmtime(self.scheduler_lock_file)
                if time.time() - lock_time < 120:  # 2鍒嗛挓鍐?
                    logger.info("Scheduler already running in another process, skip startup")
                    return
                else:
                    logger.warning("Detected stale scheduler lock file, removing it and continuing startup")
                    os.remove(self.scheduler_lock_file)
            except:
                pass
        
        # 鍒涘缓閿佹枃浠?
        try:
            with open(self.scheduler_lock_file, 'w') as f:
                f.write(str(os.getpid()))
            self.scheduler_running = True
        except:
            logger.error("鏃犳硶鍒涘缓璋冨害鍣ㄩ攣鏂囦欢")
            return
        
        def schedule_loop():
            loop_count = 0
            while self.scheduler_running:
                try:
                    loop_count += 1
                    current_time = datetime.datetime.now()
                    logger.info(f"[DEBUG] === 璋冨害寰幆 #{loop_count} 寮€濮?=== 鏃堕棿: {current_time}")
                    
                    # 妫€鏌ラ攣鏂囦欢PID鏄惁涓庡綋鍓嶈繘绋嬪尮閰?
                    if os.path.exists(self.scheduler_lock_file):
                        try:
                            with open(self.scheduler_lock_file, 'r') as f:
                                lock_pid = int(f.read().strip())
                            current_pid = os.getpid()
                            if lock_pid != current_pid:
                                logger.error(f"[ERROR] 妫€娴嬪埌PID鍐茬獊锛侀攣鏂囦欢PID: {lock_pid}, 褰撳墠PID: {current_pid}")
                                logger.error("[ERROR] 鏈夊叾浠栬皟搴﹀櫒杩涚▼鍦ㄨ繍琛岋紝閫€鍑哄綋鍓嶈皟搴﹀櫒")
                                self.scheduler_running = False
                                break
                        except:
                            pass
                        # 鏇存柊閿佹枃浠舵椂闂?
                        os.utime(self.scheduler_lock_file, None)
                    else:
                        logger.error("[ERROR] 閿佹枃浠朵涪澶憋紝閫€鍑鸿皟搴﹀櫒")
                        self.scheduler_running = False
                        break
                    
                    # 妫€鏌ユ槸鍚︽湁閲嶆柊璋冨害瑙﹀彂鏂囦欢
                    reschedule_dir = os.path.dirname(self.scheduler_lock_file)
                    for filename in os.listdir(reschedule_dir):
                        if filename.startswith('.reschedule_'):
                            try:
                                # 鎻愬彇schedule_id
                                schedule_id = int(filename.replace('.reschedule_', ''))
                                trigger_file = os.path.join(reschedule_dir, filename)
                                
                                logger.info(f"[DEBUG] 鍙戠幇閲嶆柊璋冨害瑙﹀彂鏂囦欢: {filename}, 鏃ョ▼ID: {schedule_id}")
                                
                                # 鍒犻櫎瑙﹀彂鏂囦欢
                                os.remove(trigger_file)
                                
                                # 寮哄埗閲嶆柊璋冨害璇ヤ换鍔?
                                self._reschedule_task(schedule_id)
                                logger.info(f"[DEBUG] 宸插鐞嗛噸鏂拌皟搴﹁姹? ID {schedule_id}")
                                
                            except Exception as e:
                                logger.error(f"澶勭悊閲嶆柊璋冨害瑙﹀彂鏂囦欢澶辫触: {e}")
                    
                    # 姣?0鍒嗛挓娓呯悊涓€娆¤繃鏈熺殑鎵ц璁板綍
                    if loop_count % 20 == 0:  # 20 * 30绉?= 10鍒嗛挓
                        now = datetime.datetime.now()
                        expired_keys = []
                        for key, exec_time in self.executed_tasks.items():
                            if (now - exec_time).total_seconds() > 600:  # 10鍒嗛挓鍓嶇殑璁板綍
                                expired_keys.append(key)
                        for key in expired_keys:
                            del self.executed_tasks[key]
                        if expired_keys:
                            logger.info(f"[DEBUG] cleared {len(expired_keys)} expired execution markers")
                    
                    # 鑾峰彇鎵€鏈夋椿璺冪殑鏃ョ▼
                    schedules = self.get_schedules('active')
                    logger.info(f"[DEBUG] loaded {len(schedules)} active schedules")
                    
                    for schedule in schedules:
                        logger.info(f"[DEBUG] 澶勭悊浠诲姟: ID={schedule['id']}, 鏍囬='{schedule['title']}', 鐘舵€?'{schedule['status']}'")
                        schedule_id = schedule['id']
                        
                        # 瑙ｆ瀽鎵ц鏃堕棿
                        next_time = self.parse_repeat_rule(schedule['repeat_rule'], schedule['schedule_time'])
                        
                        logger.debug(f"[DEBUG] 澶勭悊浠诲姟 ID {schedule_id}: {schedule['title']}, next_time={next_time}, 褰撳墠鏃堕棿={datetime.datetime.now()}")
                        
                        if next_time:
                            # 濡傛灉浠诲姟宸茬粡鍦ㄨ皟搴︿腑锛岃烦杩?
                            if schedule_id in self.task_threads:
                                # 浠诲姟宸茶璋冨害杩囷紝涓嶇Timer鏄惁杩樻椿鐫€閮借烦杩?
                                # 杩欓槻姝簡鍚屼竴浠诲姟琚娆¤皟搴?
                                logger.debug(f"[DEBUG] 浠诲姟 ID {schedule_id} 宸插湪 task_threads 涓紝璺宠繃")
                                continue
                            
                            # 鍙湁褰撲换鍔℃椂闂磋繕鏈埌涓旀湭琚皟搴︽椂鎵嶅垱寤烘柊鐨凾imer
                            current_time = datetime.datetime.now()
                            if next_time > current_time:
                                logger.info(f"璋冨害浠诲姟 {schedule['title']} (ID: {schedule_id}) 灏嗗湪 {next_time} 鎵ц")
                                self.schedule_task(schedule, next_time)
                            else:
                                logger.warning(f"[DEBUG] 浠诲姟 ID {schedule_id} 鏃堕棿宸茶繃鏈? {next_time} < {current_time}")
                        else:
                            logger.debug(f"[DEBUG] 浠诲姟 ID {schedule_id} parse_repeat_rule 杩斿洖 None")
                    
                    # 姣?0绉掓鏌ヤ竴娆★紙鍙傝€僡gent_service.py鐨勫疄鐜帮級
                    time.sleep(30)
                    
                except Exception as e:
                    logger.error(f"璋冨害鍣ㄩ敊璇? {e}")
                    time.sleep(60)
        
        # 鍚姩璋冨害绾跨▼
        # 娉ㄥ唽閫€鍑烘椂娓呯悊閿佹枃浠?
        def cleanup_lock():
            if self.scheduler_running and os.path.exists(self.scheduler_lock_file):
                try:
                    os.remove(self.scheduler_lock_file)
                    logger.info("Scheduler lock file removed")
                except:
                    pass
            self.scheduler_running = False
        
        atexit.register(cleanup_lock)
        
        scheduler_thread = threading.Thread(target=schedule_loop)
        scheduler_thread.daemon = True
        scheduler_thread.start()
        logger.info("鏃ョ▼璋冨害鍣ㄥ凡鍚姩")
    
    def start_web_server(self):

        try:
            # 濡傛灉宸茬粡鏈塛eb鏈嶅姟鍣ㄥ湪杩愯锛屽厛鍋滄瀹?
            if self.web_server_process is not None:
                self.stop_web_server()
            
            # 妫€鏌eb_server.py鏂囦欢鏄惁瀛樺湪
            if getattr(sys, "frozen", False):
                web_server_command = os.path.join(RUNTIME_DIR, 'schedule_manager_web.exe')
                launch_args = [web_server_command, '--host', '127.0.0.1', '--port', '5011']
            else:
                web_server_command = os.path.join(RUNTIME_DIR, 'web_server.py')
                launch_args = [sys.executable, web_server_command, '--host', '127.0.0.1', '--port', '5011']
            if not os.path.exists(web_server_command):
                logger.warning("schedule_manager web server entry not found, skip launching web server")
                return
            self.web_server_process = subprocess.Popen(
                launch_args,
                cwd=RUNTIME_DIR,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # 绛夊緟涓€灏忔鏃堕棿妫€鏌ヨ繘绋嬫槸鍚︽甯稿惎鍔?
            time.sleep(2)
            if self.web_server_process and self.web_server_process.poll() is None:
                logger.info("Web鏈嶅姟鍣ㄥ凡鍚姩 - 璁块棶鍦板潃: http://127.0.0.1:5011")
            else:
                logger.warning("Web server failed to start")
                self.web_server_process = None
                        
        except Exception as e:
            logger.error(f"鍚姩Web鏈嶅姟鍣ㄥけ璐? {e}")
            self.web_server_process = None
    
    def stop_web_server(self):

        if self.web_server_process:
            try:
                # 鍏堝皾璇曟甯哥粓姝?
                self.web_server_process.terminate()
                try:
                    self.web_server_process.wait(timeout=3)
                    logger.info("Web鏈嶅姟鍣ㄥ凡姝ｅ父鍋滄")
                except subprocess.TimeoutExpired:
                    # 濡傛灉3绉掑唴娌℃湁鍋滄锛屽己鍒舵潃姝?
                    self.web_server_process.kill()
                    self.web_server_process.wait(timeout=2)
                    logger.info("Web鏈嶅姟鍣ㄥ凡寮哄埗鍋滄")
                self.web_server_process = None
            except Exception as e:
                logger.error(f"鍋滄Web鏈嶅姟鍣ㄥけ璐? {e}")
                self.web_server_process = None

# 鍏ㄥ眬鏃ョ▼绠＄悊鍣ㄥ疄渚?
schedule_manager = ScheduleManager()

# 娉ㄥ唽娓呯悊鍑芥暟
def cleanup():
    """娓呯悊鍑芥暟"""
    try:
        logger.info("姝ｅ湪娓呯悊璧勬簮...")
        schedule_manager.stop_web_server()
    except Exception as e:
        logger.error(f"娓呯悊璧勬簮鏃跺嚭閿? {e}")

atexit.register(cleanup)

# 淇″彿澶勭悊
def signal_handler(signum, frame):
    """淇″彿澶勭悊鍑芥暟"""
    logger.info(f"鏀跺埌淇″彿 {signum}锛屾鍦ㄩ€€鍑?..")
    cleanup()
    sys.exit(0)

# 娉ㄥ唽淇″彿澶勭悊鍣?
try:
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    # Windows鐗规湁淇″彿
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, signal_handler)
except Exception as e:
    logger.warning(f"娉ㄥ唽淇″彿澶勭悊鍣ㄥけ璐? {e}")

# 鍒涘缓MCP鏈嶅姟鍣?
server = Server("schedule-manager")

@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    return [
        Tool(
            name="add_schedule",
            description="Create a schedule task.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Schedule title"},
                    "content": {"type": "string", "description": "Schedule content"},
                    "schedule_time": {"type": "string", "description": "Execution time in HH:MM format"},
                    "repeat_rule": {
                        "type": "string",
                        "description": "7-digit repeat rule from Monday to Sunday, default 0000000",
                        "default": "0000000"
                    },
                    "uid": {"type": "integer", "description": "User id", "default": 0}
                },
                "required": ["title", "content", "schedule_time"]
            }
        ),
        Tool(
            name="get_schedules",
            description="List schedule tasks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status: active, completed, deleted or all",
                        "default": "active"
                    },
                    "uid": {"type": "integer", "description": "Optional user id filter"}
                }
            }
        ),
        Tool(
            name="update_schedule",
            description="Update a schedule task.",
            inputSchema={
                "type": "object",
                "properties": {
                    "schedule_id": {"type": "integer", "description": "Schedule id"},
                    "title": {"type": "string", "description": "Updated title"},
                    "content": {"type": "string", "description": "Updated content"},
                    "schedule_time": {"type": "string", "description": "Updated time in HH:MM format"},
                    "repeat_rule": {"type": "string", "description": "Updated repeat rule"},
                    "status": {"type": "string", "description": "Updated status: active, completed or deleted"}
                },
                "required": ["schedule_id"]
            }
        ),
        Tool(
            name="delete_schedule",
            description="Soft-delete a schedule task.",
            inputSchema={
                "type": "object",
                "properties": {
                    "schedule_id": {"type": "integer", "description": "Schedule id to delete"}
                },
                "required": ["schedule_id"]
            }
        ),
        Tool(
            name="send_message_to_fay",
            description="Send a message to Fay.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Message content"},
                    "uid": {"type": "integer", "description": "Optional user id", "default": 0}
                },
                "required": ["message"]
            }
        ),
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """澶勭悊宸ュ叿璋冪敤"""
    
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
        return [TextContent(type="text", text=json.dumps({"success": True, "message": "娑堟伅宸插彂閫佺粰Fay"}, ensure_ascii=False))]
    
    else:
        return [TextContent(type="text", text=f"鏈煡宸ュ叿: {name}")]

async def main():

    logger.info("Fay鏃ョ▼绠＄悊MCP Server 鍚姩涓?..")
    
    try:
        # 浣跨敤stdio浼犺緭杩愯鏈嶅姟鍣?
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            # MCP杩炴帴寤虹珛鏃跺惎鍔╓eb鏈嶅姟鍣?
            schedule_manager.start_web_server()
            logger.info("MCP杩炴帴宸插缓绔嬶紝Web鏈嶅姟鍣ㄥ凡鍚姩")
            
            # 浣跨敤鏈嶅姟鍣ㄧ殑鏍囧噯鍒濆鍖栭€夐」
            init_opts = server.create_initialization_options()
            await server.run(read_stream, write_stream, init_opts)
    except KeyboardInterrupt:
        logger.info("鏀跺埌涓柇淇″彿锛屾鍦ㄥ叧闂湇鍔″櫒...")
    except Exception as e:
        logger.error(f"MCP鏈嶅姟鍣ㄨ繍琛岄敊璇? {e}")
    finally:
        # MCP杩炴帴鏂紑鏃跺叧闂璚eb鏈嶅姟鍣?
        schedule_manager.stop_web_server()
        logger.info("MCP鏈嶅姟鍣ㄥ凡鍏抽棴锛學eb鏈嶅姟鍣ㄥ凡鍋滄")

if __name__ == "__main__":
    asyncio.run(main())

