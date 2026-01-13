"""
统一的日志配置模块
支持控制台输出、文件记录和日志轮转
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

# 日志目录
LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)

# 日志格式
LOG_FORMAT = '[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

def setup_logger(name='app', level=logging.INFO, log_file='app.log', max_bytes=10*1024*1024, backup_count=5):
    """
    配置日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别
        log_file: 日志文件名
        max_bytes: 单个日志文件最大大小（默认10MB）
        backup_count: 保留的日志文件数量
    
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    logger = logging.getLogger(name)
    
    # 如果已经配置过，直接返回
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    logger.propagate = False
    
    # 创建格式化器
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器（带轮转）
    if log_file:
        log_path = LOG_DIR / log_file
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

def get_logger(name='app'):
    """
    获取日志记录器（如果不存在则创建）
    
    Args:
        name: 日志记录器名称
    
    Returns:
        logging.Logger: 日志记录器实例
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger = setup_logger(name)
    return logger

# 创建不同模块的日志记录器
def get_api_logger():
    """API相关日志"""
    return get_logger('api')

def get_db_logger():
    """数据库相关日志"""
    return get_logger('database')

def get_auth_logger():
    """认证相关日志"""
    return get_logger('auth')

def get_error_logger():
    """错误日志（单独文件）"""
    return setup_logger('error', level=logging.ERROR, log_file='error.log')

# 审计日志（记录关键操作）
def get_audit_logger():
    """审计日志"""
    return setup_logger('audit', level=logging.INFO, log_file='audit.log')

def log_api_request(logger, request, extra_info=None):
    """
    记录API请求信息
    
    Args:
        logger: 日志记录器
        request: Flask request对象
        extra_info: 额外信息字典
    """
    ip = request.remote_addr
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
    
    log_msg = f"API请求 {request.method} {request.path} from {ip}"
    if extra_info:
        log_msg += f" | {extra_info}"
    
    logger.info(log_msg)

def log_db_operation(logger, operation, table, extra_info=None):
    """
    记录数据库操作
    
    Args:
        logger: 日志记录器
        operation: 操作类型（SELECT/INSERT/UPDATE/DELETE）
        table: 表名
        extra_info: 额外信息
    """
    log_msg = f"数据库操作 {operation} {table}"
    if extra_info:
        log_msg += f" | {extra_info}"
    
    logger.debug(log_msg)

def log_error_with_context(logger, error, context=None):
    """
    记录错误及上下文
    
    Args:
        logger: 日志记录器
        error: 异常对象
        context: 上下文信息字典
    """
    error_msg = f"错误: {type(error).__name__}: {str(error)}"
    if context:
        error_msg += f" | 上下文: {context}"
    
    logger.error(error_msg, exc_info=True)
