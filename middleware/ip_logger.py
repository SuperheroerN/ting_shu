"""
IP访问记录中间件
"""
from flask import request
from models.database import db, IPAccessLog, IPBlacklist
from datetime import datetime

def check_ip_blacklist():
    """检查IP是否在黑名单中"""
    ip_address = request.remote_addr
    # 检查X-Forwarded-For头（如果使用代理）
    if request.headers.get('X-Forwarded-For'):
        ip_address = request.headers.get('X-Forwarded-For').split(',')[0].strip()
    
    # 检查黑名单
    blacklisted = IPBlacklist.query.filter_by(ip_address=ip_address).first()
    if blacklisted:
        return True, ip_address
    return False, ip_address

def log_ip_access():
    """记录IP访问"""
    try:
        ip_address = request.remote_addr
        # 检查X-Forwarded-For头（如果使用代理）
        if request.headers.get('X-Forwarded-For'):
            ip_address = request.headers.get('X-Forwarded-For').split(',')[0].strip()
        
        # 跳过后台管理页面的访问记录（避免管理员操作产生大量日志）
        if request.path.startswith('/admin'):
            return
        
        # 记录访问
        log_entry = IPAccessLog(
            ip_address=ip_address,
            user_agent=request.headers.get('User-Agent', '')[:500],
            request_path=request.path[:500],
            request_method=request.method,
            access_time=datetime.utcnow()
        )
        
        db.session.add(log_entry)
        db.session.commit()
    except Exception:
        # 记录失败不影响正常请求
        try:
            db.session.rollback()
        except:
            pass




