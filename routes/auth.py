"""
用户认证相关路由
"""
from flask import Blueprint, request, jsonify, session
from models.database import db, User, AppConfig
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import time
from utils.request_auth import get_current_api_key, verify_signature, REQUEST_TIMEOUT
from utils.logger import get_auth_logger, get_audit_logger, log_error_with_context
from utils.api_response import api_success, api_error, handle_exceptions

# 初始化日志
auth_logger = get_auth_logger()
audit_logger = get_audit_logger()  # 审计日志，记录关键操作

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/api/auth/register', methods=['POST'])
@handle_exceptions
def register():
    """用户注册"""
    try:
        # 检查是否开放注册
        allow_register = AppConfig.get_config('allow_register', True)
        if not allow_register:
            return api_error('当前已关闭注册，请联系管理员开通', code=403, error_type='PermissionError')

        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return api_error('用户名和密码不能为空', code=400, error_type='ValidationError')
        
        if len(password) < 6:
            return api_error('密码长度至少6位', code=400, error_type='ValidationError')
        
        # 检查用户名是否已存在
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return api_error('用户名已存在', code=400, error_type='DuplicateError')
        
        # 创建新用户（增强密码哈希强度）
        new_user = User(
            username=username,
            password=generate_password_hash(password, method='pbkdf2:sha256:260000'),
            register_time=datetime.utcnow()
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        # 设置session
        session['user_id'] = new_user.id
        session['username'] = new_user.username
        
        # 记录审计日志
        audit_logger.info(f"用户注册: {username} (ID: {new_user.id}) from {request.remote_addr}")
        
        return api_success(
            data={'user': new_user.to_dict()},
            message='注册成功',
            code=201
        )
        
    except Exception as e:
        db.session.rollback()
        log_error_with_context(auth_logger, e, {'username': username, 'action': 'register'})
        return api_error('注册失败，请重试', code=500, error_type='DatabaseError', details=str(e))

@auth_bp.route('/api/auth/login', methods=['POST'])
@handle_exceptions
def login():
    """用户登录"""
    try:
        data = request.get_json() or {}
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        timestamp = str(data.get('timestamp', '')).strip()
        signature = str(data.get('signature', '')).strip()
        
        if not username or not password:
            return api_error('用户名和密码不能为空', code=400, error_type='ValidationError')

        # 校验登录请求签名（HMAC-SHA256 + 动态密钥）
        if not timestamp or not signature:
            return api_error('登录请求缺少签名', code=403, error_type='AuthError')

        # 时间戳有效期校验
        try:
            ts = float(timestamp)
        except Exception:
            return api_error('登录请求时间无效', code=403, error_type='AuthError')

        if abs(time.time() - ts) > REQUEST_TIMEOUT:
            return api_error('登录请求已过期，请刷新页面重试', code=403, error_type='AuthError')

        # 获取当前/旧密钥并验证签名
        current_key, old_key = get_current_api_key()
        keys = [k for k in (current_key, old_key) if k]
        params = {
            'username': username,
            'password': password,
        }
        if (not keys) or (not verify_signature(signature, timestamp, params, keys)):
            auth_logger.warning(f"登录签名验证失败: {username} from {request.remote_addr}")
            return api_error('登录签名无效', code=403, error_type='AuthError')
        
        # 查找用户
        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password, password):
            auth_logger.warning(f"登录失败: {username} from {request.remote_addr}")
            return api_error('用户名或密码错误', code=401, error_type='AuthError')
        
        # 设置session
        session['user_id'] = user.id
        session['username'] = user.username
        
        # 记录审计日志
        audit_logger.info(f"用户登录: {username} (ID: {user.id}) from {request.remote_addr}")
        
        return api_success(
            data={'user': user.to_dict()},
            message='登录成功'
        )
        
    except Exception as e:
        log_error_with_context(auth_logger, e, {'username': username, 'action': 'login'})
        return api_error('登录失败，请重试', code=500, error_type='ServerError', details=str(e))

@auth_bp.route('/api/auth/logout', methods=['POST'])
def logout():
    """用户退出"""
    session.clear()
    return jsonify({'success': True, 'message': '已退出登录'})

@auth_bp.route('/api/auth/status', methods=['GET'])
def get_auth_status():
    """获取当前登录状态"""
    user_id = session.get('user_id')
    username = session.get('username')
    
    if user_id:
        user = User.query.get(user_id)
        if user:
            return jsonify({
                'logged_in': True,
                'user': user.to_dict()
            })
    
    return jsonify({'logged_in': False})

@auth_bp.route('/api/auth/api-key', methods=['GET'])
def get_api_key():
    """获取API请求密钥（供前端签名使用）"""
    try:
        from utils.request_auth import get_api_key_for_client
        key_data = get_api_key_for_client()
        
        if key_data:
            return jsonify({
                'success': True,
                'key': key_data['key'],
                'expires_at': key_data['expires_at']
            })
        else:
            return jsonify({'error': '获取密钥失败'}), 500
    except Exception:
        return jsonify({'error': '获取密钥失败'}), 500

def get_current_user():
    """获取当前登录用户"""
    user_id = session.get('user_id')
    if user_id:
        return User.query.get(user_id)
    return None











