"""
简单的请求频率限制中间件
使用内存存储（适合单进程部署）
如果是多进程/分布式部署，建议使用Redis
"""
from flask import request, jsonify
from functools import wraps
from collections import defaultdict
from datetime import datetime, timedelta
import time
from utils.logger import get_logger

logger = get_logger('rate_limiter')

class RateLimiter:
    """
    基于内存的简单频率限制器
    """
    def __init__(self):
        # 存储格式：{key: [(timestamp1, ), (timestamp2, ), ...]}
        self.requests = defaultdict(list)
        self.cleanup_interval = 300  # 5分钟清理一次过期记录
        self.last_cleanup = time.time()
    
    def _get_key(self, identifier):
        """生成唯一标识符"""
        return identifier
    
    def _cleanup(self):
        """清理过期的请求记录"""
        current_time = time.time()
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        # 清理1小时前的记录
        cutoff_time = current_time - 3600
        keys_to_delete = []
        
        for key, timestamps in self.requests.items():
            # 过滤掉过期的时间戳
            self.requests[key] = [ts for ts in timestamps if ts > cutoff_time]
            if not self.requests[key]:
                keys_to_delete.append(key)
        
        # 删除空的key
        for key in keys_to_delete:
            del self.requests[key]
        
        self.last_cleanup = current_time
        logger.debug(f"频率限制器清理完成，删除了 {len(keys_to_delete)} 个过期key")
    
    def is_allowed(self, key, limit, window):
        """
        检查是否允许请求
        
        Args:
            key: 唯一标识符（如IP地址）
            limit: 时间窗口内允许的最大请求数
            window: 时间窗口（秒）
        
        Returns:
            (是否允许, 剩余请求数, 重置时间)
        """
        current_time = time.time()
        cutoff_time = current_time - window
        
        # 执行清理
        self._cleanup()
        
        # 获取该key的请求记录
        timestamps = self.requests[key]
        
        # 过滤掉时间窗口之外的请求
        valid_timestamps = [ts for ts in timestamps if ts > cutoff_time]
        self.requests[key] = valid_timestamps
        
        # 检查是否超过限制
        if len(valid_timestamps) >= limit:
            # 计算重置时间（最早的请求时间 + 时间窗口）
            reset_time = valid_timestamps[0] + window
            remaining = 0
            allowed = False
        else:
            # 添加当前请求
            self.requests[key].append(current_time)
            remaining = limit - len(valid_timestamps) - 1
            reset_time = current_time + window
            allowed = True
        
        return allowed, remaining, reset_time

# 全局频率限制器实例
rate_limiter = RateLimiter()

def get_client_ip():
    """获取客户端真实IP地址"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr

def rate_limit(limit=100, window=60, key_func=None):
    """
    频率限制装饰器
    
    Args:
        limit: 时间窗口内允许的最大请求数
        window: 时间窗口（秒）
        key_func: 自定义key生成函数，默认使用IP地址
    
    使用示例:
        @app.route('/api/some-endpoint')
        @rate_limit(limit=10, window=60)  # 每分钟最多10次请求
        def some_endpoint():
            pass
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # 生成限制key
            if key_func:
                key = key_func()
            else:
                key = get_client_ip()
            
            # 检查是否允许请求
            allowed, remaining, reset_time = rate_limiter.is_allowed(
                key, limit, window
            )
            
            if not allowed:
                # 计算需要等待的时间
                wait_seconds = int(reset_time - time.time())
                
                logger.warning(
                    f"频率限制触发: IP={key}, "
                    f"限制={limit}/{window}s, "
                    f"路径={request.path}"
                )
                
                response = jsonify({
                    'error': '请求过于频繁，请稍后再试',
                    'error_type': 'RateLimitError',
                    'retry_after': wait_seconds
                })
                response.status_code = 429
                response.headers['Retry-After'] = str(wait_seconds)
                response.headers['X-RateLimit-Limit'] = str(limit)
                response.headers['X-RateLimit-Remaining'] = '0'
                response.headers['X-RateLimit-Reset'] = str(int(reset_time))
                return response
            
            # 添加频率限制响应头
            response = f(*args, **kwargs)
            
            # 如果响应是元组（response, status_code），需要特殊处理
            if isinstance(response, tuple):
                resp_obj, status_code = response[0], response[1]
                if hasattr(resp_obj, 'headers'):
                    resp_obj.headers['X-RateLimit-Limit'] = str(limit)
                    resp_obj.headers['X-RateLimit-Remaining'] = str(remaining)
                    resp_obj.headers['X-RateLimit-Reset'] = str(int(reset_time))
                return response
            elif hasattr(response, 'headers'):
                response.headers['X-RateLimit-Limit'] = str(limit)
                response.headers['X-RateLimit-Remaining'] = str(remaining)
                response.headers['X-RateLimit-Reset'] = str(int(reset_time))
            
            return response
        
        return wrapper
    return decorator

# 预定义的频率限制配置
def strict_rate_limit(f):
    """严格限制：每分钟10次"""
    return rate_limit(limit=10, window=60)(f)

def normal_rate_limit(f):
    """普通限制：每分钟30次"""
    return rate_limit(limit=30, window=60)(f)

def loose_rate_limit(f):
    """宽松限制：每分钟100次"""
    return rate_limit(limit=100, window=60)(f)
