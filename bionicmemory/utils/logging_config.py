"""
统一日志配置模块
提供统一的日志格式配置，确保所有模块使用相同的日志输出格式
支持环境变量配置日志级别和输出文件，支持按日期的多日志文件
"""

import logging
import logging.handlers
import sys
import os
from pathlib import Path
from datetime import datetime

def setup_logging():
    """设置统一的日志配置"""
    # 从环境变量读取配置
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    log_dir = os.getenv('LOG_DIR', './logs/')
    
    # 创建日志目录
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # 按日期生成日志文件名
    today = datetime.now().strftime('%Y-%m-%d')
    log_file = log_path / f'bionicmemory-{today}.log'
    
    # 统一格式：时间 - 级别 - 文件名:行号 - 消息
    format_string = '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # 配置日志级别
    numeric_level = getattr(logging, log_level, logging.INFO)
    
    # 创建格式化器
    formatter = logging.Formatter(format_string, date_format)
    
    # 清除现有的处理器
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 控制台处理器（解决乱码问题）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(numeric_level)
    # 设置控制台输出编码
    if hasattr(console_handler.stream, 'reconfigure'):
        console_handler.stream.reconfigure(encoding='utf-8')
    
    # 文件处理器（按日期轮转）
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file,
        when='midnight',  # 每天午夜轮转
        interval=1,        # 间隔1天
        backupCount=30,    # 保留30天的日志
        encoding='utf-8'   # 解决乱码问题
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(numeric_level)
    
    # 配置根日志器
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # 设置第三方库的日志级别，避免过多输出
    logging.getLogger('chromadb').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('transformers').setLevel(logging.WARNING)
    logging.getLogger('sentence_transformers').setLevel(logging.WARNING)

def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的日志器
    
    Args:
        name: 日志器名称，通常使用__name__
        
    Returns:
        配置好的日志器实例
    """
    return logging.getLogger(name)

# 在模块导入时自动设置默认日志配置
setup_logging()
