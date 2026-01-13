"""
请求认证工具 - 防止抓包和未授权访问
使用HMAC签名 + 动态密钥 + 时间戳验证
"""
import time
import hmac
import hashlib
import secrets
from datetime import datetime, timedelta
from flask import request, session, jsonify, current_app
from models.database import db, AppConfig

REQUEST_TIMEOUT = 300  # 请求有效期5分钟
KEY_ROTATION_INTERVAL = 3600  # 密钥轮换间隔（秒）- 1小时
KEY_GRACE_PERIOD = 600  # 旧密钥宽限期（秒）- 10分钟

def generate_api_key():
    """生成随机API密钥"""
    return secrets.token_urlsafe(32)  # 生成43字符的URL安全随机字符串

def get_current_api_key():
    """获取当前有效的API密钥"""
    try:
        # 从数据库获取密钥配置
        key_data = AppConfig.get_config('api_request_key', None)
        key_expiry = AppConfig.get_config('api_request_key_expiry', None)
        
        current_time = time.time()
        
        # 如果密钥不存在或已过期，生成新密钥
        if not key_data or not key_expiry or float(key_expiry) < current_time:
            new_key = generate_api_key()
            new_expiry = current_time + KEY_ROTATION_INTERVAL
            
            # 保存新密钥
            AppConfig.set_config('api_request_key', new_key, 'API请求签名密钥（动态轮换）')
            AppConfig.set_config('api_request_key_expiry', str(new_expiry), '密钥过期时间（Unix时间戳）')
            
            # 同时保存上一个密钥（用于宽限期）
            if key_data:
                AppConfig.set_config('api_request_key_old', key_data, '上一个API请求签名密钥（宽限期内有效）')
                AppConfig.set_config('api_request_key_old_expiry', str(current_time + KEY_GRACE_PERIOD), '旧密钥过期时间')
            
            return new_key, None
        
        # 检查旧密钥是否还在宽限期内
        old_key = AppConfig.get_config('api_request_key_old', None)
        old_key_expiry = AppConfig.get_config('api_request_key_old_expiry', None)
        old_key_valid = False
        
        if old_key and old_key_expiry and float(old_key_expiry) > current_time:
            old_key_valid = True
        
        return key_data, old_key if old_key_valid else None
        
    except Exception:
        # 如果获取失败，尝试从Flask current_app获取
        try:
            from flask import current_app
            return current_app.config.get('SECRET_KEY', 'default-secret-key'), None
        except:
            # 如果还是失败，返回None（验证将失败，但不会崩溃）
            return None, None

def generate_signature(key, timestamp, params):
    """
    生成HMAC-SHA256签名
    :param key: 签名密钥
    :param timestamp: 时间戳
    :param params: 参数字典
    :return: 签名（hex字符串）
    """
    # 将参数字典转换为排序后的字符串（确保一致性）
    param_str = '&'.join([f'{k}={v}' for k, v in sorted(params.items())])
    
    # 组合：时间戳 + 参数字符串
    sign_string = f'{timestamp}&{param_str}'
    
    # 生成HMAC-SHA256签名
    signature = hmac.new(
        key.encode('utf-8'),
        sign_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature

def verify_signature(signature, timestamp, params, keys):
    """
    验证签名
    :param signature: 客户端提供的签名
    :param timestamp: 时间戳
    :param params: 参数字典
    :param keys: 密钥列表（当前密钥和旧密钥）
    :return: 是否验证通过
    """
    for key in keys:
        if not key:
            continue
        expected_signature = generate_signature(key, timestamp, params)
        # 使用constant-time比较防止时序攻击
        if hmac.compare_digest(signature, expected_signature):
            return True
    return False

def verify_api_request(require_login=False):
    """
    验证API请求装饰器（已简化，移除HMAC签名验证）
    仅保留：
    1. Session验证（可选，如果require_login=True）
    
    :param require_login: 是否要求用户登录
    """
    def decorator(f):
        def wrapper(*args, **kwargs):
            try:
                # 仅验证Session（如果要求登录）
                if require_login:
                    user_id = session.get('user_id')
                    if not user_id:
                        return jsonify({'error': '请先登录'}), 401
                
                # 直接执行，不再验证签名
                return f(*args, **kwargs)
                
            except Exception:
                return jsonify({'error': '请求验证失败'}), 403
        
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

def get_api_key_for_client():
    """
    获取API密钥供客户端使用
    这个函数可以被前端调用，返回当前有效的密钥
    注意：密钥会在数据库中定期轮换
    """
    try:
        current_key, _ = get_current_api_key()
        key_expiry = AppConfig.get_config('api_request_key_expiry', None)
        return {
            'key': current_key,
            'expires_at': float(key_expiry) if key_expiry else None
        }
    except Exception:
        return None

