"""
后台管理路由
"""
from flask import Blueprint, request, jsonify, session, render_template
from models.database import db, User, APIConfig, IPAccessLog, IPBlacklist, Announcement, IPAnnouncementConfirm, Feedback, AppConfig, InterfaceDefinition
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import func, distinct
from functools import wraps
import json

admin_bp = Blueprint('admin', __name__)

def get_admin_user():
    """获取超级管理员（数据库第一个用户）"""
    return User.query.order_by(User.id.asc()).first()

def admin_required(f):
    """管理员权限装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 检查是否登录
        user_id = session.get('admin_user_id')
        if not user_id:
            return jsonify({'error': '请先登录'}), 401
        
        # 检查是否是超级管理员（第一个用户）
        admin_user = get_admin_user()
        if not admin_user or user_id != admin_user.id:
            return jsonify({'error': '权限不足'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/admin')
def admin_login_page():
    """后台登录页面"""
    return render_template('admin/login.html')

@admin_bp.route('/admin/login', methods=['POST'])
def admin_login():
    """后台登录"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({'error': '用户名和密码不能为空'}), 400
        
        # 获取超级管理员（第一个用户）
        admin_user = get_admin_user()
        if not admin_user:
            return jsonify({'error': '系统未初始化，请先创建用户'}), 400
        
        # 验证用户名和密码
        if admin_user.username != username:
            return jsonify({'error': '用户名或密码错误'}), 401
        
        if not check_password_hash(admin_user.password, password):
            return jsonify({'error': '用户名或密码错误'}), 401
        
        # 设置管理员session
        session['admin_user_id'] = admin_user.id
        session['admin_username'] = admin_user.username
        
        return jsonify({
            'success': True,
            'message': '登录成功',
            'user': admin_user.to_dict()
        })
        
    except Exception:
        return jsonify({'error': '登录失败，请重试'}), 500

@admin_bp.route('/admin/logout', methods=['POST'])
@admin_required
def admin_logout():
    """后台退出"""
    session.pop('admin_user_id', None)
    session.pop('admin_username', None)
    return jsonify({'success': True, 'message': '已退出登录'})

@admin_bp.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """后台首页"""
    return render_template('admin/dashboard.html')

@admin_bp.route('/admin/api/stats', methods=['GET'])
@admin_required
def admin_stats():
    """获取统计信息"""
    try:
        # 注册人数
        total_users = User.query.count()
        
        # 今日注册人数
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_users = User.query.filter(User.register_time >= today_start).count()
        
        # IP访问统计（最近7天）
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        ip_stats = db.session.query(
            IPAccessLog.ip_address,
            func.count(IPAccessLog.id).label('count')
        ).filter(IPAccessLog.access_time >= seven_days_ago)\
         .group_by(IPAccessLog.ip_address)\
         .order_by(func.count(IPAccessLog.id).desc())\
         .limit(20).all()
        
        ip_list = [{'ip': item.ip_address, 'count': item.count} for item in ip_stats]
        
        # 今日访问IP数
        today_ip_count = db.session.query(
            func.count(distinct(IPAccessLog.ip_address))
        ).filter(IPAccessLog.access_time >= today_start).scalar() or 0
        
        # 总访问次数（最近7天）
        total_access = db.session.query(func.count(IPAccessLog.id))\
            .filter(IPAccessLog.access_time >= seven_days_ago).scalar() or 0
        
        # 黑名单数量
        blacklist_count = IPBlacklist.query.count()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_users': total_users,
                'today_users': today_users,
                'today_ip_count': today_ip_count,
                'total_access': total_access,
                'blacklist_count': blacklist_count
            },
            'ip_list': ip_list
        })
    except Exception:
        return jsonify({'error': '获取统计信息失败'}), 500


@admin_bp.route('/admin/api/users', methods=['GET'])
@admin_required
def admin_list_users():
    """获取用户列表"""
    try:
        users = User.query.order_by(User.id.asc()).all()
        admin_user = get_admin_user()
        admin_id = admin_user.id if admin_user else None
        return jsonify({
            'success': True,
            'users': [
                {
                    **u.to_dict(),
                    'is_admin': (u.id == admin_id)
                } for u in users
            ]
        })
    except Exception:
        return jsonify({'error': '获取用户列表失败'}), 500


@admin_bp.route('/admin/api/users', methods=['POST'])
@admin_required
def admin_create_user():
    """后台创建新用户"""
    try:
        data = request.get_json() or {}
        username = (data.get('username') or '').strip()
        password = (data.get('password') or '').strip()

        if not username or not password:
            return jsonify({'error': '用户名和密码不能为空'}), 400
        if len(password) < 6:
            return jsonify({'error': '密码长度至少6位'}), 400

        # 检查是否已存在
        existing = User.query.filter_by(username=username).first()
        if existing:
            return jsonify({'error': '该用户名已存在'}), 400

        from werkzeug.security import generate_password_hash
        new_user = User(
            username=username,
            password=generate_password_hash(password),
            register_time=datetime.utcnow()
        )
        db.session.add(new_user)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '用户创建成功',
            'user': new_user.to_dict()
        }), 201
    except Exception:
        db.session.rollback()
        return jsonify({'error': '创建用户失败'}), 500


@admin_bp.route('/admin/api/users/<int:user_id>', methods=['DELETE'])
@admin_required
def admin_delete_user(user_id):
    """后台删除用户（不能删除第一个超级管理员）"""
    try:
        admin_user = get_admin_user()
        if admin_user and user_id == admin_user.id:
            return jsonify({'error': '不能删除超级管理员账户'}), 400

        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404

        db.session.delete(user)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '用户已删除'
        })
    except Exception:
        db.session.rollback()
        return jsonify({'error': '删除用户失败'}), 500

@admin_bp.route('/admin/api/ip-blacklist', methods=['GET'])
@admin_required
def get_ip_blacklist():
    """获取IP黑名单列表"""
    try:
        blacklist = IPBlacklist.query.order_by(IPBlacklist.create_time.desc()).all()
        return jsonify({
            'success': True,
            'blacklist': [item.to_dict() for item in blacklist]
        })
    except Exception:
        return jsonify({'error': '获取IP黑名单失败'}), 500

@admin_bp.route('/admin/api/ip-blacklist', methods=['POST'])
@admin_required
def add_ip_blacklist():
    """添加IP到黑名单"""
    try:
        data = request.get_json()
        ip_address = data.get('ip_address', '').strip()
        reason = data.get('reason', '').strip()
        
        if not ip_address:
            return jsonify({'error': 'IP地址不能为空'}), 400
        
        # 检查是否已存在
        existing = IPBlacklist.query.filter_by(ip_address=ip_address).first()
        if existing:
            return jsonify({'error': '该IP已在黑名单中'}), 400
        
        # 添加黑名单
        admin_username = session.get('admin_username', 'admin')
        blacklist_item = IPBlacklist(
            ip_address=ip_address,
            reason=reason,
            create_by=admin_username
        )
        
        db.session.add(blacklist_item)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '已添加到黑名单',
            'item': blacklist_item.to_dict()
        })
    except Exception:
        db.session.rollback()
        return jsonify({'error': '添加黑名单失败'}), 500

@admin_bp.route('/admin/api/ip-blacklist/<int:item_id>', methods=['DELETE'])
@admin_required
def remove_ip_blacklist(item_id):
    """从黑名单移除IP"""
    try:
        item = IPBlacklist.query.get(item_id)
        if not item:
            return jsonify({'error': '黑名单项不存在'}), 404
        
        db.session.delete(item)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '已从黑名单移除'
        })
    except Exception:
        db.session.rollback()
        return jsonify({'error': '移除黑名单失败'}), 500

@admin_bp.route('/admin/api/interface-definitions', methods=['GET'])
@admin_required
def get_interface_definitions():
    """获取所有接口定义"""
    try:
        definitions = InterfaceDefinition.query.order_by(InterfaceDefinition.interface_name).all()
        
        return jsonify({
            'success': True,
            'definitions': [defn.to_dict() for defn in definitions]
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'获取接口定义失败: {str(e)}'}), 500

@admin_bp.route('/admin/api/interface-definitions', methods=['POST'])
@admin_required
def create_interface_definition():
    """创建新的接口定义"""
    try:
        data = request.get_json()
        interface_name = data.get('interface_name', '').strip()
        display_name = data.get('display_name', '').strip()
        description = data.get('description', '')
        enabled = data.get('enabled', True)
        field_mapping = data.get('field_mapping', {})
        
        if not interface_name:
            return jsonify({'error': '接口名称不能为空'}), 400
        if not display_name:
            return jsonify({'error': '显示名称不能为空'}), 400
        
        # 检查接口名称是否已存在
        existing = InterfaceDefinition.query.filter_by(interface_name=interface_name).first()
        if existing:
            return jsonify({'error': f'接口名称 {interface_name} 已存在'}), 400
        
        # 创建接口定义
        definition = InterfaceDefinition(
            interface_name=interface_name,
            display_name=display_name,
            description=description,
            enabled=enabled,
            field_mapping=json.dumps(field_mapping) if field_mapping else None
        )
        db.session.add(definition)
        db.session.commit()
        
        # 重新加载适配器
        from utils.interface_registry import registry
        registry.reload(interface_name)
        
        return jsonify({
            'success': True,
            'message': '接口定义创建成功',
            'definition': definition.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'创建接口定义失败: {str(e)}'}), 500

@admin_bp.route('/admin/api/interface-definitions/<interface_name>', methods=['PUT'])
@admin_required
def update_interface_definition(interface_name):
    """更新接口定义"""
    try:
        definition = InterfaceDefinition.query.filter_by(interface_name=interface_name).first()
        if not definition:
            return jsonify({'error': '接口定义不存在'}), 404
        
        data = request.get_json()
        if 'display_name' in data:
            definition.display_name = data['display_name'].strip()
        if 'description' in data:
            definition.description = data['description']
        if 'enabled' in data:
            definition.enabled = data['enabled']
        if 'field_mapping' in data:
            definition.field_mapping = json.dumps(data['field_mapping']) if data['field_mapping'] else None
        
        definition.update_time = datetime.utcnow()
        db.session.commit()
        
        # 重新加载适配器
        from utils.interface_registry import registry
        registry.reload(interface_name)
        
        return jsonify({
            'success': True,
            'message': '接口定义更新成功',
            'definition': definition.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'更新接口定义失败: {str(e)}'}), 500

@admin_bp.route('/admin/api/interface-definitions/<interface_name>', methods=['DELETE'])
@admin_required
def delete_interface_definition(interface_name):
    """删除接口定义"""
    try:
        # 允许删除数据库记录
        # 不阻止删除，让用户可以重置为默认配置
        
        definition = InterfaceDefinition.query.filter_by(interface_name=interface_name).first()
        if not definition:
            return jsonify({'error': '接口定义不存在'}), 404
        
        # 删除相关的API配置
        APIConfig.query.filter_by(interface=interface_name).delete()
        
        # 删除接口定义
        db.session.delete(definition)
        db.session.commit()
        
        # 从注册器中移除适配器
        from utils.interface_registry import registry
        registry.unregister(interface_name)
        
        return jsonify({
            'success': True,
            'message': '接口定义删除成功'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'删除接口定义失败: {str(e)}'}), 500

@admin_bp.route('/admin/api/interfaces/list', methods=['GET'])
@admin_required
def list_available_interfaces():
    """获取所有可用接口列表（仅自定义接口）"""
    try:
        # 从数据库获取所有启用的接口定义
        definitions = InterfaceDefinition.query.filter_by(enabled=True).all()
        defined_interfaces = {defn.interface_name for defn in definitions}
        
        # 合并结果（仅自定义接口）
        all_interfaces = list(defined_interfaces)
        
        # 获取接口详细信息
        interface_details = []
        for interface_name in all_interfaces:
            definition = InterfaceDefinition.query.filter_by(interface_name=interface_name).first()
            if definition:
                interface_details.append({
                    'interface_name': interface_name,
                    'display_name': definition.display_name,
                    'description': definition.description,
                    'enabled': definition.enabled,
                    'is_builtin': False
                })
        
        return jsonify({
            'success': True,
            'interfaces': interface_details
        })
    except Exception as e:
        return jsonify({'error': f'获取接口列表失败: {str(e)}'}), 500

@admin_bp.route('/admin/api/announcement', methods=['GET'])
@admin_required
def admin_get_announcement():
    """获取公告（管理端）"""
    try:
        announcements = Announcement.query.order_by(Announcement.update_time.desc()).all()
        return jsonify({
            'success': True,
            'announcements': [ann.to_dict() for ann in announcements]
        })
    except Exception:
        return jsonify({'error': '获取公告失败'}), 500

@admin_bp.route('/admin/api/announcement', methods=['POST'])
@admin_required
def admin_create_announcement():
    """创建公告"""
    try:
        data = request.get_json()
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()
        is_active = data.get('is_active', True)
        
        if not title or not content:
            return jsonify({'error': '标题和内容不能为空'}), 400
        
        # 如果创建新公告，将旧公告设为非激活
        if is_active:
            Announcement.query.update({Announcement.is_active: False})
        
        announcement = Announcement(
            title=title,
            content=content,
            is_active=is_active,
            create_time=datetime.utcnow(),
            update_time=datetime.utcnow()
        )
        db.session.add(announcement)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '公告创建成功',
            'announcement': announcement.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': '创建公告失败'}), 500

@admin_bp.route('/admin/api/announcement/<int:announcement_id>', methods=['PUT'])
@admin_required
def admin_update_announcement(announcement_id):
    """更新公告"""
    try:
        announcement = Announcement.query.get(announcement_id)
        if not announcement:
            return jsonify({'error': '公告不存在'}), 404
        
        data = request.get_json()
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()
        is_active = data.get('is_active')
        
        if not title or not content:
            return jsonify({'error': '标题和内容不能为空'}), 400
        
        # 如果激活新公告，将其他公告设为非激活
        if is_active and not announcement.is_active:
            Announcement.query.filter(Announcement.id != announcement_id).update({Announcement.is_active: False})
        
        announcement.title = title
        announcement.content = content
        if is_active is not None:
            announcement.is_active = is_active
        announcement.update_time = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '公告更新成功',
            'announcement': announcement.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': '更新公告失败'}), 500

@admin_bp.route('/admin/api/announcement/<int:announcement_id>', methods=['DELETE'])
@admin_required
def admin_delete_announcement(announcement_id):
    """删除公告"""
    try:
        announcement = Announcement.query.get(announcement_id)
        if not announcement:
            return jsonify({'error': '公告不存在'}), 404
        
        db.session.delete(announcement)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '公告删除成功'
        })
    except Exception:
        db.session.rollback()
        return jsonify({'error': '删除公告失败'}), 500

@admin_bp.route('/admin/api/announcement/stats', methods=['GET'])
@admin_required
def admin_announcement_stats():
    """获取公告统计信息"""
    try:
        # 总公告数
        total_announcements = Announcement.query.count()
        
        # 启用的公告数
        active_announcements = Announcement.query.filter_by(is_active=True).count()
        
        # 总确认数
        total_confirms = IPAnnouncementConfirm.query.count()
        
        # 最近7天的确认数
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_confirms = IPAnnouncementConfirm.query.filter(
            IPAnnouncementConfirm.confirm_time >= seven_days_ago
        ).count()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_announcements': total_announcements,
                'active_announcements': active_announcements,
                'total_confirms': total_confirms,
                'recent_confirms': recent_confirms
            }
        })
    except Exception:
        return jsonify({'error': '获取统计信息失败'}), 500

@admin_bp.route('/admin/api/feedback', methods=['GET'])
@admin_required
def admin_get_feedback():
    """获取反馈列表（管理端）"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', '')  # pending, processed, 或空（全部）
        
        query = Feedback.query
        
        if status:
            query = query.filter_by(status=status)
        
        # 分页
        pagination = query.order_by(Feedback.create_time.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        feedbacks = pagination.items
        
        return jsonify({
            'success': True,
            'feedbacks': [fb.to_dict() for fb in feedbacks],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages
            }
        })
    except Exception:
        return jsonify({'error': '获取反馈列表失败'}), 500

@admin_bp.route('/admin/api/feedback/<int:feedback_id>', methods=['PUT'])
@admin_required
def admin_update_feedback(feedback_id):
    """更新反馈状态（标记为已处理）"""
    try:
        feedback = Feedback.query.get(feedback_id)
        if not feedback:
            return jsonify({'error': '反馈不存在'}), 404
        
        data = request.get_json()
        status = data.get('status', 'processed')
        remark = data.get('remark', '').strip()
        
        # 获取当前管理员用户名
        admin_user = get_admin_user()
        admin_username = admin_user.username if admin_user else '系统'
        
        feedback.status = status
        feedback.remark = remark if remark else None
        feedback.process_time = datetime.utcnow()
        feedback.process_by = admin_username
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '反馈状态已更新',
            'feedback': feedback.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': '更新反馈状态失败'}), 500

@admin_bp.route('/admin/api/feedback/<int:feedback_id>', methods=['DELETE'])
@admin_required
def admin_delete_feedback(feedback_id):
    """删除反馈"""
    try:
        feedback = Feedback.query.get(feedback_id)
        if not feedback:
            return jsonify({'error': '反馈不存在'}), 404
        
        db.session.delete(feedback)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '反馈已删除'
        })
    except Exception:
        db.session.rollback()
        return jsonify({'error': '删除反馈失败'}), 500

@admin_bp.route('/admin/api/feedback/stats', methods=['GET'])
@admin_required
def admin_feedback_stats():
    """获取反馈统计信息"""
    try:
        # 总反馈数
        total_feedbacks = Feedback.query.count()
        
        # 待处理反馈数
        pending_feedbacks = Feedback.query.filter_by(status='pending').count()
        
        # 已处理反馈数
        processed_feedbacks = Feedback.query.filter_by(status='processed').count()
        
        # 最近7天的反馈数
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_feedbacks = Feedback.query.filter(
            Feedback.create_time >= seven_days_ago
        ).count()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_feedbacks': total_feedbacks,
                'pending_feedbacks': pending_feedbacks,
                'processed_feedbacks': processed_feedbacks,
                'recent_feedbacks': recent_feedbacks
            }
        })
    except Exception:
        return jsonify({'error': '获取统计信息失败'}), 500

@admin_bp.route('/admin/api/app-config', methods=['GET'])
@admin_required
def get_app_config():
    """获取应用配置"""
    try:
        mobile_only_access = AppConfig.get_config('mobile_only_access', False)
        allow_register = AppConfig.get_config('allow_register', True)
        return jsonify({
            'success': True,
            'config': {
                'mobile_only_access': mobile_only_access,
                'allow_register': allow_register
            }
        })
    except Exception:
        return jsonify({'error': '获取应用配置失败'}), 500

@admin_bp.route('/admin/api/app-config', methods=['POST'])
@admin_required
def update_app_config():
    """更新应用配置"""
    try:
        data = request.get_json() or {}
        mobile_only_access = data.get('mobile_only_access', False)
        allow_register = data.get('allow_register', True)
        
        # 保存配置：仅允许手机访问
        AppConfig.set_config(
            'mobile_only_access',
            mobile_only_access,
            '仅允许手机设备访问（开启后只有手机用户才能访问网站）'
        )

        # 保存配置：是否开放注册
        AppConfig.set_config(
            'allow_register',
            allow_register,
            '是否开放前台用户注册（True=开放，False=禁止注册）'
        )
        
        return jsonify({
            'success': True,
            'message': '配置已更新'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': '更新配置失败'}), 500


