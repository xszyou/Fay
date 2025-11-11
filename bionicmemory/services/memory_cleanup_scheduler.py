"""
记忆库定时清理服务
使用 apscheduler 定期清理长短期记忆库
"""

import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from bionicmemory.core.memory_system import LongShortTermMemorySystem
from bionicmemory.algorithms.newton_cooling_helper import CoolingRate

# 使用统一日志配置
from bionicmemory.utils.logging_config import get_logger
logger = get_logger(__name__)

class MemoryCleanupScheduler:
    """
    记忆库定时清理调度器
    负责定期清理长短期记忆库中的过期记录
    """
    
    def __init__(self, memory_system: LongShortTermMemorySystem):
        """
        初始化清理调度器
        
        Args:
            memory_system: 长短期记忆系统实例
        """
        self.memory_system = memory_system
        self.scheduler = BackgroundScheduler()
        self.is_running = False
        
        logger.info("记忆库清理调度器初始化完成")
    
    def start(self):
        """启动定时清理服务"""
        try:
            if self.is_running:
                logger.warning("清理调度器已经在运行")
                return
            
            # 添加定时清理任务
            self._add_cleanup_jobs()
            
            # 启动调度器
            self.scheduler.start()
            self.is_running = True
            
            logger.info("记忆库清理调度器启动成功")
            
        except Exception as e:
            logger.error(f"启动清理调度器失败: {e}")
            raise
    
    def stop(self):
        """停止定时清理服务"""
        try:
            if not self.is_running:
                logger.warning("清理调度器未在运行")
                return
            
            # 停止调度器
            self.scheduler.shutdown()
            self.is_running = False
            
            logger.info("记忆库清理调度器已停止")
            
        except Exception as e:
            logger.error(f"停止清理调度器失败: {e}")
            raise
    
    def _add_cleanup_jobs(self):
        """添加定时清理任务"""
        try:
            # 1. 短期记忆库清理任务 - 每10分钟执行一次
            # 短期记忆使用 MINUTES_20 遗忘速率，需要更频繁的清理
            short_term_trigger = IntervalTrigger(minutes=10)
            self.scheduler.add_job(
                func=self._cleanup_short_term_memory,
                trigger=short_term_trigger,
                id="short_term_cleanup",
                name="短期记忆库清理",
                max_instances=1,
                coalesce=True
            )
            
            # 2. 长期记忆库清理任务 - 每天夜里4点执行
            # 长期记忆使用 DAYS_31 遗忘速率，可以每天清理一次
            long_term_trigger = CronTrigger(hour=4, minute=0)
            self.scheduler.add_job(
                func=self._cleanup_long_term_memory,
                trigger=long_term_trigger,
                id="long_term_cleanup",
                name="长期记忆库清理",
                max_instances=1,
                coalesce=True
            )
            

            
            logger.info("定时清理任务添加完成")
            
        except Exception as e:
            logger.error(f"添加定时清理任务失败: {e}")
            raise
    
    def _cleanup_short_term_memory(self):
        """清理短期记忆库 - 每10分钟执行一次"""
        try:
            logger.info("开始执行短期记忆库定时清理")
            
            # 🔒 注意：定时清理是系统级操作，清理所有用户的过期记录
            # 这是合理的，因为系统需要维护整体性能
            self.memory_system._cleanup_collection(
                self.memory_system.short_term_collection_name,
                CoolingRate.MINUTES_20,
                self.memory_system.short_term_threshold
            )
            
            logger.info(f"短期记忆库定时清理完成")
            
        except Exception as e:
            logger.error(f"短期记忆库定时清理失败: {e}")
    
    def _cleanup_long_term_memory(self):
        """清理长期记忆库"""
        try:
            logger.info("开始执行长期记忆库定时清理")
            
            # 🔒 注意：定时清理是系统级操作，清理所有用户的过期记录
            # 这是合理的，因为系统需要维护整体性能
            self.memory_system._cleanup_collection(
                self.memory_system.long_term_collection_name,
                CoolingRate.DAYS_31,
                self.memory_system.long_term_threshold
            )
            
            logger.info(f"长期记忆库定时清理完成")
            
        except Exception as e:
            logger.error(f"长期记忆库定时清理失败: {e}")
    

    
    def get_scheduler_status(self) -> dict:
        """
        获取调度器状态
        
        Returns:
            调度器状态信息
        """
        try:
            if not self.is_running:
                return {
                    "status": "stopped",
                    "jobs": [],
                    "message": "调度器未运行"
                }
            
            # 获取所有任务信息
            jobs = []
            for job in self.scheduler.get_jobs():
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": str(job.next_run_time) if job.next_run_time else "None",
                    "trigger": str(job.trigger)
                })
            
            return {
                "status": "running",
                "jobs": jobs,
                "message": "调度器运行正常"
            }
            
        except Exception as e:
            logger.error(f"获取调度器状态失败: {e}")
            return {
                "status": "error",
                "jobs": [],
                "message": f"获取状态失败: {e}"
            }
    
    def add_custom_cleanup_job(self, 
                               func, 
                               trigger, 
                               job_id: str, 
                               name: str = None):
        """
        添加自定义清理任务
        
        Args:
            func: 要执行的函数
            trigger: 触发器
            job_id: 任务ID
            name: 任务名称
        """
        try:
            if not self.is_running:
                logger.warning("调度器未运行，无法添加任务")
                return False
            
            self.scheduler.add_job(
                func=func,
                trigger=trigger,
                id=job_id,
                name=name or job_id,
                max_instances=1,
                coalesce=True
            )
            
            logger.info(f"自定义清理任务添加成功: {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"添加自定义清理任务失败: {e}")
            return False
    
    def remove_job(self, job_id: str) -> bool:
        """
        移除指定的任务
        
        Args:
            job_id: 任务ID
        
        Returns:
            是否移除成功
        """
        try:
            if not self.is_running:
                logger.warning("调度器未运行，无法移除任务")
                return False
            
            self.scheduler.remove_job(job_id)
            logger.info(f"任务移除成功: {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"移除任务失败: {e}")
            return False
    
    def pause_job(self, job_id: str) -> bool:
        """
        暂停指定的任务
        
        Args:
            job_id: 任务ID
        
        Returns:
            是否暂停成功
        """
        try:
            if not self.is_running:
                logger.warning("调度器未运行，无法暂停任务")
                return False
            
            self.scheduler.pause_job(job_id)
            logger.info(f"任务暂停成功: {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"暂停任务失败: {e}")
            return False
    
    def resume_job(self, job_id: str) -> bool:
        """
        恢复指定的任务
        
        Args:
            job_id: 任务ID
        
        Returns:
            是否恢复成功
        """
        try:
            if not self.is_running:
                logger.warning("调度器未运行，无法恢复任务")
                return False
            
            self.scheduler.resume_job(job_id)
            logger.info(f"任务恢复成功: {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"恢复任务失败: {e}")
            return False
    
    def run_cleanup_now(self):
        """立即执行一次清理任务"""
        try:
            logger.info("开始执行立即清理任务")
            
            # 执行清理 - 同时清理长短期记忆库
            self.memory_system._cleanup_collection(
                self.memory_system.short_term_collection_name,
                CoolingRate.MINUTES_20,
                self.memory_system.short_term_threshold
            )
            self.memory_system._cleanup_collection(
                self.memory_system.long_term_collection_name,
                CoolingRate.DAYS_31,
                self.memory_system.long_term_threshold
            )
            
            logger.info("立即清理任务执行完成")
            
        except Exception as e:
            logger.error(f"立即清理任务执行失败: {e}")
            raise
