from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    """用户表"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    register_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # 关联关系
    bookshelf_items = db.relationship('Bookshelf', backref='user', lazy=True, cascade='all, delete-orphan')
    play_history_items = db.relationship('PlayHistory', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'register_time': self.register_time.isoformat() if self.register_time else None
        }

class Bookshelf(db.Model):
    """书架表"""
    __tablename__ = 'bookshelf'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    book_id = db.Column(db.String(100), nullable=False)
    interface = db.Column(db.String(20), nullable=False)
    book_title = db.Column(db.String(500), nullable=False)
    book_image = db.Column(db.String(1000))
    book_anchor = db.Column(db.String(200))
    add_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # 唯一约束：同一用户不能添加同一本书两次
    __table_args__ = (db.UniqueConstraint('user_id', 'book_id', 'interface', name='unique_user_book'),)
    
    def to_dict(self):
        return {
            'id': self.id,
            'book_id': self.book_id,
            'interface': self.interface,
            'book_title': self.book_title,
            'book_image': self.book_image,
            'book_anchor': self.book_anchor,
            'add_time': self.add_time.isoformat() if self.add_time else None
        }

class PlayHistory(db.Model):
    """播放历史表"""
    __tablename__ = 'play_history'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    book_id = db.Column(db.String(100), nullable=False)
    interface = db.Column(db.String(20), nullable=False)
    chapter_id = db.Column(db.String(100), nullable=False)
    chapter_title = db.Column(db.String(500), nullable=False)
    book_title = db.Column(db.String(500), nullable=False)
    book_image = db.Column(db.String(1000))
    book_anchor = db.Column(db.String(200))
    play_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def to_dict(self):
        try:
            return {
                'id': self.id,
                'book_id': self.book_id or '',
                'interface': self.interface or '',
                'chapter_id': self.chapter_id or '',
                'chapter_title': self.chapter_title or '',
                'book_title': self.book_title or '',
                'book_image': self.book_image or '',
                'book_anchor': self.book_anchor or '',
                'play_time': self.play_time.isoformat() if self.play_time else None
            }
        except Exception as e:
            # 如果转换失败，返回基本字段
            return {
                'id': getattr(self, 'id', None),
                'book_id': str(getattr(self, 'book_id', '')),
                'interface': str(getattr(self, 'interface', '')),
                'chapter_id': str(getattr(self, 'chapter_id', '')),
                'chapter_title': str(getattr(self, 'chapter_title', '')),
                'book_title': str(getattr(self, 'book_title', '')),
                'book_image': str(getattr(self, 'book_image', '')),
                'book_anchor': str(getattr(self, 'book_anchor', '')),
                'play_time': None
            }

class APIConfig(db.Model):
    """API接口配置表"""
    __tablename__ = 'api_config'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    interface = db.Column(db.String(20), nullable=False)
    config_type = db.Column(db.String(50), nullable=False)  # 'search', 'chapters', 'url'
    config_key = db.Column(db.String(100))  # 配置键名（如URL模板中的参数名）
    config_value = db.Column(db.Text)  # 配置值（如URL、token等）
    description = db.Column(db.String(500))  # 配置说明
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 唯一约束：同一接口、类型、键的组合只能有一条记录
    __table_args__ = (db.UniqueConstraint('interface', 'config_type', 'config_key', name='unique_interface_type_key'),)
    
    def to_dict(self):
        return {
            'id': self.id,
            'interface': self.interface,
            'config_type': self.config_type,
            'config_key': self.config_key,
            'config_value': self.config_value,
            'description': self.description,
            'update_time': self.update_time.isoformat() if self.update_time else None
        }

class IPAccessLog(db.Model):
    """IP访问记录表"""
    __tablename__ = 'ip_access_log'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ip_address = db.Column(db.String(50), nullable=False, index=True)
    user_agent = db.Column(db.String(500))
    request_path = db.Column(db.String(500))
    request_method = db.Column(db.String(10))
    access_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'request_path': self.request_path,
            'request_method': self.request_method,
            'access_time': self.access_time.isoformat() if self.access_time else None
        }

class IPBlacklist(db.Model):
    """IP黑名单表"""
    __tablename__ = 'ip_blacklist'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ip_address = db.Column(db.String(50), nullable=False, unique=True, index=True)
    reason = db.Column(db.String(500))  # 拉黑原因
    create_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    create_by = db.Column(db.String(80))  # 创建者（管理员用户名）
    
    def to_dict(self):
        return {
            'id': self.id,
            'ip_address': self.ip_address,
            'reason': self.reason,
            'create_time': self.create_time.isoformat() if self.create_time else None,
            'create_by': self.create_by
        }

class Announcement(db.Model):
    """公告表"""
    __tablename__ = 'announcement'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(200), nullable=False)  # 公告标题
    content = db.Column(db.Text, nullable=False)  # 公告内容
    is_active = db.Column(db.Boolean, default=True, nullable=False)  # 是否启用
    create_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'is_active': self.is_active,
            'create_time': self.create_time.isoformat() if self.create_time else None,
            'update_time': self.update_time.isoformat() if self.update_time else None
        }

class IPAnnouncementConfirm(db.Model):
    """IP公告确认记录表"""
    __tablename__ = 'ip_announcement_confirm'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ip_address = db.Column(db.String(50), nullable=False, index=True)
    announcement_id = db.Column(db.Integer, db.ForeignKey('announcement.id', ondelete='CASCADE'), nullable=False, index=True)
    confirm_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # 唯一约束：同一IP对同一公告只能确认一次
    __table_args__ = (db.UniqueConstraint('ip_address', 'announcement_id', name='unique_ip_announcement'),)
    
    def to_dict(self):
        return {
            'id': self.id,
            'ip_address': self.ip_address,
            'announcement_id': self.announcement_id,
            'confirm_time': self.confirm_time.isoformat() if self.confirm_time else None
        }

class Feedback(db.Model):
    """用户反馈表"""
    __tablename__ = 'feedback'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)  # 可为空，未登录用户也可以反馈
    ip_address = db.Column(db.String(50), nullable=False, index=True)  # IP地址
    content = db.Column(db.Text, nullable=False)  # 反馈内容
    contact = db.Column(db.String(200))  # 联系方式（可选）
    status = db.Column(db.String(20), default='pending', nullable=False)  # 状态：pending(待处理), processed(已处理)
    create_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    process_time = db.Column(db.DateTime)  # 处理时间
    process_by = db.Column(db.String(80))  # 处理人（管理员用户名）
    remark = db.Column(db.Text)  # 备注
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'ip_address': self.ip_address,
            'content': self.content,
            'contact': self.contact,
            'status': self.status,
            'create_time': self.create_time.isoformat() if self.create_time else None,
            'process_time': self.process_time.isoformat() if self.process_time else None,
            'process_by': self.process_by,
            'remark': self.remark
        }

class AppConfig(db.Model):
    """应用配置表"""
    __tablename__ = 'app_config'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    config_key = db.Column(db.String(100), unique=True, nullable=False, index=True)  # 配置键
    config_value = db.Column(db.Text)  # 配置值（JSON字符串或普通字符串）
    description = db.Column(db.String(500))  # 配置说明
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'config_key': self.config_key,
            'config_value': self.config_value,
            'description': self.description,
            'update_time': self.update_time.isoformat() if self.update_time else None
        }
    
    @staticmethod
    def get_config(key, default_value=None):
        """获取配置值"""
        try:
            config = AppConfig.query.filter_by(config_key=key).first()
            if config and config.config_value:
                # 尝试解析为布尔值
                config_value = str(config.config_value).lower()
                if config_value in ('true', '1', 'yes', 'on'):
                    return True
                elif config_value in ('false', '0', 'no', 'off'):
                    return False
                return config.config_value
            return default_value
        except Exception:
            return default_value
    
    @staticmethod
    def set_config(key, value, description=None):
        """设置配置值"""
        try:
            config = AppConfig.query.filter_by(config_key=key).first()
            if config:
                config.config_value = str(value)
                if description:
                    config.description = description
                config.update_time = datetime.utcnow()
            else:
                config = AppConfig(
                    config_key=key,
                    config_value=str(value),
                    description=description or ''
                )
                db.session.add(config)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e


class InterfaceDefinition(db.Model):
    """接口定义表 - 存储接口的基本信息和字段映射配置"""
    __tablename__ = 'interface_definition'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    interface_name = db.Column(db.String(50), unique=True, nullable=False, index=True)  # 接口名称
    display_name = db.Column(db.String(100), nullable=False)  # 显示名称
    description = db.Column(db.Text)  # 接口描述
    enabled = db.Column(db.Boolean, default=True, nullable=False)  # 是否启用
    field_mapping = db.Column(db.Text)  # 字段映射配置（JSON字符串）
    create_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        import json
        field_mapping_dict = None
        if self.field_mapping:
            try:
                field_mapping_dict = json.loads(self.field_mapping)
            except:
                pass
        
        return {
            'id': self.id,
            'interface_name': self.interface_name,
            'display_name': self.display_name,
            'description': self.description,
            'enabled': self.enabled,
            'field_mapping': field_mapping_dict,
            'create_time': self.create_time.isoformat() if self.create_time else None,
            'update_time': self.update_time.isoformat() if self.update_time else None
        }



