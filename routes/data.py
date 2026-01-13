"""
数据操作相关路由（书架、播放历史等）
"""
from flask import Blueprint, request, jsonify
from models.database import db, Bookshelf, PlayHistory, User
from routes.auth import get_current_user
from datetime import datetime
from sqlalchemy import func, distinct
from utils.logger import get_api_logger, get_db_logger, log_error_with_context
from utils.api_response import api_success, api_error, handle_exceptions
from utils.rate_limiter import rate_limit, normal_rate_limit

# 初始化日志
logger = get_api_logger()
db_logger = get_db_logger()

data_bp = Blueprint('data', __name__)

# ========== 书架相关 ==========

@data_bp.route('/api/bookshelf', methods=['GET'])
@handle_exceptions
def get_bookshelf():
    """获取用户书架"""
    user = get_current_user()
    if not user:
        return api_error('请先登录', code=401, error_type='AuthError')
    
    try:
        books = Bookshelf.query.filter_by(user_id=user.id).order_by(Bookshelf.add_time.desc()).all()
        logger.info(f"用户 {user.id} 获取书架，共 {len(books)} 本书")
        return api_success(data={'books': [book.to_dict() for book in books]})
    except Exception as e:
        log_error_with_context(logger, e, {'user_id': user.id, 'action': 'get_bookshelf'})
        return api_error('获取书架失败', code=500, error_type='DatabaseError', details=str(e))

@data_bp.route('/api/bookshelf', methods=['POST'])
@handle_exceptions
@rate_limit(limit=30, window=60)  # 每分钟最多30次添加请求
def add_to_bookshelf():
    """添加到书架"""
    user = get_current_user()
    if not user:
        return api_error('请先登录', code=401, error_type='AuthError')
    
    try:
        data = request.get_json()
        book_id = data.get('book_id')
        interface = data.get('interface')
        book_title = data.get('book_title', '')
        book_image = data.get('book_image', '')
        book_anchor = data.get('book_anchor', '')
        
        if not book_id or not interface:
            return api_error('缺少必要参数', code=400, error_type='ValidationError')
        
        # 检查是否已存在
        existing = Bookshelf.query.filter_by(
            user_id=user.id,
            book_id=book_id,
            interface=interface
        ).first()
        
        if existing:
            return api_error('该书已在书架中', code=400, error_type='DuplicateError')
        
        # 添加新书
        new_book = Bookshelf(
            user_id=user.id,
            book_id=book_id,
            interface=interface,
            book_title=book_title,
            book_image=book_image,
            book_anchor=book_anchor,
            add_time=datetime.utcnow()
        )
        
        db.session.add(new_book)
        db.session.commit()
        
        logger.info(f"用户 {user.id} 添加书籍到书架: {book_title} ({book_id})")
        
        return api_success(
            data={'book': new_book.to_dict()},
            message='已加入书架',
            code=201
        )
        
    except Exception as e:
        db.session.rollback()
        log_error_with_context(logger, e, {
            'user_id': user.id,
            'book_id': book_id,
            'action': 'add_to_bookshelf'
        })
        return api_error('添加到书架失败', code=500, error_type='DatabaseError', details=str(e))

@data_bp.route('/api/bookshelf', methods=['DELETE'])
@handle_exceptions
def remove_from_bookshelf():
    """从书架移除"""
    user = get_current_user()
    if not user:
        return api_error('请先登录', code=401, error_type='AuthError')
    
    try:
        data = request.get_json()
        book_id = data.get('book_id')
        interface = data.get('interface')
        
        if not book_id or not interface:
            return api_error('缺少必要参数', code=400, error_type='ValidationError')
        
        book = Bookshelf.query.filter_by(
            user_id=user.id,
            book_id=book_id,
            interface=interface
        ).first()
        
        if not book:
            return api_error('该书不在书架中', code=404, error_type='NotFoundError')
        
        db.session.delete(book)
        db.session.commit()
        
        logger.info(f"用户 {user.id} 从书架移除书籍: {book.book_title} ({book_id})")
        
        return api_success(message='已从书架移除')
        
    except Exception as e:
        db.session.rollback()
        log_error_with_context(logger, e, {
            'user_id': user.id,
            'book_id': book_id,
            'action': 'remove_from_bookshelf'
        })
        return api_error('移除失败', code=500, error_type='DatabaseError', details=str(e))

@data_bp.route('/api/bookshelf/check', methods=['GET'])
def check_bookshelf():
    """检查书籍是否在书架中"""
    user = get_current_user()
    if not user:
        return jsonify({'in_bookshelf': False})
    
    try:
        book_id = request.args.get('book_id')
        interface = request.args.get('interface')
        
        if not book_id or not interface:
            return jsonify({'in_bookshelf': False})
        
        exists = Bookshelf.query.filter_by(
            user_id=user.id,
            book_id=book_id,
            interface=interface
        ).first() is not None
        
        return jsonify({'in_bookshelf': exists})
        
    except Exception:
        return jsonify({'in_bookshelf': False})

@data_bp.route('/api/bookshelf/sync', methods=['POST'])
def sync_bookshelf():
    """批量上传本地书架到数据库（登录后同步用）"""
    user = get_current_user()
    if not user:
        return jsonify({'error': '请先登录'}), 401
    
    try:
        data = request.get_json()
        local_bookshelf = data.get('books', [])
        
        if not local_bookshelf or len(local_bookshelf) == 0:
            return jsonify({
                'success': True,
                'message': '没有需要同步的书架数据',
                'synced_count': 0
            })
        
        synced_count = 0
        skipped_count = 0
        error_count = 0
        
        for book_data in local_bookshelf:
            try:
                book_id = book_data.get('book_id')
                interface = book_data.get('interface')
                
                if not book_id or not interface:
                    skipped_count += 1
                    continue
                
                # 检查数据库是否已有该书籍（必须指定user_id确保数据隔离）
                existing = Bookshelf.query.filter_by(
                    user_id=user.id,  # 关键：必须使用当前登录用户的ID
                    book_id=book_id,
                    interface=interface
                ).first()
                
                if existing:
                    # 如果已存在，更新信息（保持原有添加时间）
                    existing.book_title = book_data.get('book_title', existing.book_title)
                    existing.book_image = book_data.get('book_image', existing.book_image)
                    existing.book_anchor = book_data.get('book_anchor', existing.book_anchor)
                    skipped_count += 1
                else:
                    # 创建新记录（必须指定user_id）
                    new_book = Bookshelf(
                        user_id=user.id,  # 关键：使用当前登录用户的ID，确保数据隔离
                        book_id=book_id,
                        interface=interface,
                        book_title=book_data.get('book_title', ''),
                        book_image=book_data.get('book_image', ''),
                        book_anchor=book_data.get('book_anchor', ''),
                        add_time=datetime.utcnow()
                    )
                    db.session.add(new_book)
                    synced_count += 1
            except Exception:
                error_count += 1
                continue
        
        db.session.commit()
        
        result_message = f'同步完成：新增 {synced_count} 本，跳过 {skipped_count} 本'
        if error_count > 0:
            result_message += f'，错误 {error_count} 本'
        
        return jsonify({
            'success': True,
            'message': result_message,
            'synced_count': synced_count,
            'skipped_count': skipped_count,
            'error_count': error_count
        })
        
    except Exception:
        db.session.rollback()
        return jsonify({'error': '同步书架失败'}), 500

# ========== 播放历史相关 ==========

@data_bp.route('/api/history', methods=['GET'])
@handle_exceptions
def get_history():
    """获取播放历史（每本书只返回最新一条记录）"""
    user = get_current_user()
    if not user:
        return api_error('请先登录', code=401, error_type='AuthError')
    
    try:
        # 获取参数
        limit = request.args.get('limit', 100, type=int)
        
        # 先检查是否有任何历史记录
        total_count = PlayHistory.query.filter_by(user_id=user.id).count()
        
        if total_count == 0:
            logger.info(f"用户 {user.id} 没有历史记录")
            return api_success(data={'history': []})
        
        # 简化查询：先获取所有记录，然后在Python中处理去重
        # 这样可以避免复杂的子查询可能导致的兼容性问题
        all_history = PlayHistory.query.filter_by(user_id=user.id)\
            .order_by(PlayHistory.play_time.desc())\
            .all()
        
        # 在Python中处理：每本书（book_id + interface）只保留最新一条
        history_dict = {}
        for item in all_history:
            try:
                key = f"{item.book_id}_{item.interface}"
                if key not in history_dict:
                    history_dict[key] = item
                else:
                    # 如果已有记录，比较时间，保留更新的
                    item_time = item.play_time if item.play_time else datetime.min
                    dict_time = history_dict[key].play_time if history_dict[key].play_time else datetime.min
                    if item_time > dict_time:
                        history_dict[key] = item
            except Exception as e:
                db_logger.warning(f"处理历史记录项失败: {e}")
                continue
        
        # 转换为列表并按时间排序
        history = list(history_dict.values())
        history.sort(key=lambda x: x.play_time if x.play_time else datetime.min, reverse=True)
        
        # 限制返回数量
        history = history[:limit]
        
        # 安全地转换为字典
        history_list = []
        for item in history:
            try:
                history_list.append(item.to_dict())
            except Exception as e:
                db_logger.warning(f"转换历史记录失败: {e}")
                continue
        
        logger.info(f"用户 {user.id} 获取历史记录，共 {len(history_list)} 条")
        return api_success(data={'history': history_list})
        
    except Exception as e:
        log_error_with_context(logger, e, {'user_id': user.id, 'action': 'get_history'})
        return api_error('获取历史记录失败', code=500, error_type='DatabaseError', details=str(e))

@data_bp.route('/api/history', methods=['POST'])
@handle_exceptions
@rate_limit(limit=100, window=60)  # 每分钟最多100次播放记录
def add_history():
    """添加播放历史（每本书只保留最新一条记录）"""
    user = get_current_user()
    if not user:
        return jsonify({'error': '请先登录'}), 401
    
    try:
        data = request.get_json()
        book_id = data.get('book_id')
        interface = data.get('interface')
        chapter_id = data.get('chapter_id')
        chapter_title = data.get('chapter_title', '')
        book_title = data.get('book_title', '')
        book_image = data.get('book_image', '')
        book_anchor = data.get('book_anchor', '')
        
        if not book_id or not interface or not chapter_id:
            return jsonify({'error': '缺少必要参数'}), 400
        
        # 检查同一本书是否已有记录（不检查章节，每本书只保留一条最新记录）
        existing = PlayHistory.query.filter_by(
            user_id=user.id,
            book_id=book_id,
            interface=interface
        ).first()
        
        if existing:
            # 更新章节信息和播放时间
            existing.chapter_id = chapter_id
            existing.chapter_title = chapter_title
            existing.book_title = book_title
            existing.book_image = book_image
            existing.book_anchor = book_anchor
            existing.play_time = datetime.utcnow()
            db.session.commit()
            return jsonify({
                'success': True,
                'message': '历史记录已更新',
                'history': existing.to_dict()
            })
        
        # 创建新记录（这本书的第一条记录）
        new_history = PlayHistory(
            user_id=user.id,
            book_id=book_id,
            interface=interface,
            chapter_id=chapter_id,
            chapter_title=chapter_title,
            book_title=book_title,
            book_image=book_image,
            book_anchor=book_anchor,
            play_time=datetime.utcnow()
        )
        
        db.session.add(new_history)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '历史记录已保存',
            'history': new_history.to_dict()
        }), 201
        
    except Exception:
        db.session.rollback()
        return jsonify({'error': '保存历史记录失败'}), 500

@data_bp.route('/api/history/<int:history_id>', methods=['DELETE'])
def delete_history_item(history_id):
    """删除单条历史记录"""
    user = get_current_user()
    if not user:
        return jsonify({'error': '请先登录'}), 401
    
    try:
        history_item = PlayHistory.query.filter_by(
            id=history_id,
            user_id=user.id
        ).first()
        
        if not history_item:
            return jsonify({'error': '历史记录不存在'}), 404
        
        db.session.delete(history_item)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '已删除'
        })
        
    except Exception:
        db.session.rollback()
        return jsonify({'error': '删除失败'}), 500

@data_bp.route('/api/history', methods=['DELETE'])
def clear_history():
    """清空所有历史记录"""
    user = get_current_user()
    if not user:
        return jsonify({'error': '请先登录'}), 401
    
    try:
        deleted_count = PlayHistory.query.filter_by(user_id=user.id).delete()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'已清空 {deleted_count} 条历史记录'
        })
        
    except Exception:
        db.session.rollback()
        return jsonify({'error': '清空失败'}), 500

@data_bp.route('/api/history/sync', methods=['POST'])
def sync_history():
    """批量上传本地历史记录到数据库（登录后同步用）"""
    user = get_current_user()
    if not user:
        return jsonify({'error': '请先登录'}), 401
    
    try:
        data = request.get_json()
        local_history = data.get('history', [])
        
        if not local_history or len(local_history) == 0:
            return jsonify({
                'success': True,
                'message': '没有需要同步的历史记录',
                'synced_count': 0
            })
        
        synced_count = 0
        skipped_count = 0
        error_count = 0
        
        for item in local_history:
            try:
                book_id = item.get('book_id')
                interface = item.get('interface')
                chapter_id = item.get('chapter_id')
                
                if not book_id or not interface or not chapter_id:
                    skipped_count += 1
                    continue
                
                # 解析播放时间
                play_time_str = item.get('play_time') or item.get('playTime')
                try:
                    if play_time_str:
                        if isinstance(play_time_str, str):
                            # 处理各种时间格式
                            play_time_str = play_time_str.replace('Z', '+00:00')
                            if '+' not in play_time_str and play_time_str.count(':') >= 2:
                                # 如果没有时区信息，添加UTC时区
                                play_time_str += '+00:00'
                            play_time = datetime.fromisoformat(play_time_str)
                            # 转换为UTC时间（如果时区信息存在）
                            if play_time.tzinfo:
                                play_time = play_time.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                        else:
                            play_time = datetime.utcnow()
                    else:
                        play_time = datetime.utcnow()
                except Exception:
                    play_time = datetime.utcnow()
                
                # 检查数据库是否已有该书的记录（必须指定user_id确保数据隔离）
                existing = PlayHistory.query.filter_by(
                    user_id=user.id,  # 关键：必须使用当前登录用户的ID
                    book_id=book_id,
                    interface=interface
                ).first()
                
                if existing:
                    # 如果本地记录更新，则更新数据库；否则跳过
                    if play_time > existing.play_time:
                        existing.chapter_id = chapter_id
                        existing.chapter_title = item.get('chapter_title', '')
                        existing.book_title = item.get('book_title', '')
                        existing.book_image = item.get('book_image', '')
                        existing.book_anchor = item.get('book_anchor', '')
                        existing.play_time = play_time
                        synced_count += 1
                    else:
                        skipped_count += 1
                else:
                    # 创建新记录（必须指定user_id）
                    new_history = PlayHistory(
                        user_id=user.id,  # 关键：使用当前登录用户的ID，确保数据隔离
                        book_id=book_id,
                        interface=interface,
                        chapter_id=chapter_id,
                        chapter_title=item.get('chapter_title', ''),
                        book_title=item.get('book_title', ''),
                        book_image=item.get('book_image', ''),
                        book_anchor=item.get('book_anchor', ''),
                        play_time=play_time
                    )
                    db.session.add(new_history)
                    synced_count += 1
            except Exception:
                error_count += 1
                continue
        
        db.session.commit()
        
        result_message = f'同步完成：新增/更新 {synced_count} 条，跳过 {skipped_count} 条'
        if error_count > 0:
            result_message += f'，错误 {error_count} 条'
        
        return jsonify({
            'success': True,
            'message': result_message,
            'synced_count': synced_count,
            'skipped_count': skipped_count,
            'error_count': error_count
        })
        
    except Exception:
        db.session.rollback()
        return jsonify({'error': '同步历史记录失败'}), 500

# ========== 统计数据相关 ==========

@data_bp.route('/api/stats', methods=['GET'])
def get_stats():
    """获取听书统计"""
    user = get_current_user()
    if not user:
        return jsonify({'error': '请先登录'}), 401
    
    try:
        # 统计听过的书籍数（去重）- 使用Python去重避免MySQL 5.6兼容性问题
        try:
            all_books = db.session.query(
                PlayHistory.book_id,
                PlayHistory.interface
            ).filter_by(user_id=user.id).distinct().all()
            total_books = len(all_books) if all_books else 0
        except Exception:
            total_books = 0
        
        # 统计听过的书籍数（每本书在播放历史中只保留最新记录）
        total_books = PlayHistory.query.filter_by(user_id=user.id).count()
        
        # 统计听过的章节数（由于每本书只保留最新播放记录，这里统计的是用户播放过的书籍数量）
        # 实际上，PlayHistory表设计为每本书（user_id, book_id, interface）组合只保留一条记录
        # 所以total_chapters等于total_books，即用户播放过的不同书籍数量
        total_chapters = total_books
        
        # 统计听书时长（基于实际播放行为的合理估算）
        # 根据您的反馈，有声书章节通常只有几分钟到十几分钟
        # 由于我们只记录每本书的最新播放章节，所以这里估算用户平均每本书听了1个章节
        # 每个章节平均时长约为10-15分钟（符合有声书章节的实际长度）
        avg_minutes_per_chapter = 12  # 平均每章节12分钟，更符合有声书实际时长
        total_minutes = total_chapters * avg_minutes_per_chapter
        total_hours = total_minutes // 60
        
        # 获取最近听的书籍（去重，按最新播放时间）- 简化查询避免group_by问题
        try:
            # 先获取所有记录，在Python中处理
            all_recent = PlayHistory.query.filter_by(user_id=user.id)\
                .order_by(PlayHistory.play_time.desc())\
                .all()
            
            # 去重：每本书只保留最新一条
            recent_dict = {}
            for item in all_recent:
                key = f"{item.book_id}_{item.interface}"
                if key not in recent_dict:
                    recent_dict[key] = item
            
            # 按时间排序并取前10
            recent_list = list(recent_dict.values())
            recent_list.sort(key=lambda x: x.play_time if x.play_time else datetime.min, reverse=True)
            recent_books = [{
                'book_id': item.book_id,
                'interface': item.interface,
                'book_title': item.book_title or '',
                'book_image': item.book_image or ''
            } for item in recent_list[:10]]
        except Exception:
            recent_books = []
        
        return jsonify({
            'success': True,
            'stats': {
                'total_books': total_books,
                'total_chapters': total_chapters,
                'total_hours': total_hours,
                'total_minutes': total_minutes
            },
            'recent_books': recent_books
        })
        
    except Exception:
        return jsonify({'error': '获取统计信息失败'}), 500

