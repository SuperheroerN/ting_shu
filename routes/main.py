from flask import render_template, request, jsonify
from utils.request_auth import verify_api_request
from routes.auth import auth_bp
from routes.data import data_bp
from models.database import db, Announcement, IPAnnouncementConfirm, Feedback, InterfaceDefinition
from routes.auth import get_current_user
from datetime import datetime

def ensure_https_url(url):
    """
    将HTTP URL转换为HTTPS URL，避免Mixed Content警告
    只对已知支持HTTPS的CDN域名进行转换
    """
    if not url or not isinstance(url, str):
        return url
    
    # 支持HTTPS的CDN域名列表（喜马拉雅等）
    https_supported_domains = [
        'audiopay.cos.tx.xmcdn.com',
        'cos.tx.xmcdn.com',
        'xmcdn.com',
        'ximalaya.com',
        'hls.ximalaya.com',
        'fdfs.xmcdn.com',
        'file.ximalaya.com'
    ]
    
    # 如果URL是HTTP，且域名在支持列表中，转换为HTTPS
    if url.startswith('http://'):
        for domain in https_supported_domains:
            if domain in url:
                url = url.replace('http://', 'https://', 1)
                break
    
    return url

def register_routes(app):
    # 注册蓝图
    app.register_blueprint(auth_bp)
    app.register_blueprint(data_bp)
    from routes.admin import admin_bp
    app.register_blueprint(admin_bp)
    
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/history')
    def history():
        return render_template('history.html')
    
    @app.route('/profile')
    def profile():
        return render_template('profile.html')
    
    @app.route('/api/interfaces/list', methods=['GET'])
    def list_interfaces():
        """获取所有可用的接口列表（前端可用）"""
        try:
            from models.database import InterfaceDefinition
            
            # 从数据库获取所有启用的接口定义
            definitions = InterfaceDefinition.query.filter_by(enabled=True).all()
            
            # 获取接口详细信息
            interface_details = []
            for definition in definitions:
                interface_details.append({
                    'interface_name': definition.interface_name,
                    'display_name': definition.display_name,
                    'description': definition.description or '自定义接口'
                })
            
            return jsonify({
                'success': True,
                'interfaces': interface_details
            })
        except Exception as e:
            import traceback
            print(f"获取接口列表失败: {e}")
            traceback.print_exc()
            return jsonify({'error': f'获取接口列表失败: {str(e)}'}), 500
    
    @app.route('/search', methods=['POST'])
    def search():
        keyword = request.form.get('keyword', '')
        interface = request.form.get('interface')
        
        if not keyword:
            return jsonify({'error': '请输入搜索关键词'}), 400
        
        if not interface:
            return jsonify({'error': '请选择接口'}), 400
        
        # 使用适配器搜索
        from utils.interface_registry import get_interface_adapter
        adapter = get_interface_adapter(interface)
        
        if adapter:
            result = adapter.search_books(keyword)
            if result:
                # 标准化数据
                books = adapter.normalize_book_data(result)
                return jsonify({'books': books})
            else:
                return jsonify({'error': f'{interface}接口搜索失败，请重试'}), 500
        else:
            return jsonify({'error': f'接口 {interface} 不存在或未配置'}), 404
    
    @app.route('/results', methods=['GET'])
    def results():
        keyword = request.args.get('keyword', '')
        
        if not keyword:
            return render_template('index.html'), 302  # 重定向到主页
        
        # 搜索所有启用的接口
        all_books = []
        
        # 获取所有启用的接口
        from models.database import InterfaceDefinition
        definitions = InterfaceDefinition.query.filter_by(enabled=True).all()
        
        # 搜索每个接口
        from utils.interface_registry import get_interface_adapter
        for definition in definitions:
            try:
                adapter = get_interface_adapter(definition.interface_name)
                if adapter:
                    result = adapter.search_books(keyword)
                    if result:
                        books = adapter.normalize_book_data(result)
                        all_books.extend(books)
            except Exception as e:
                print(f"搜索接口 {definition.interface_name} 失败: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # 移除可能的重复书籍（基于id和interface的组合）
        unique_books = []
        seen_keys = set()
        for book in all_books:
            # 使用 id + interface 作为唯一键
            key = f"{book.get('id', '')}_{book.get('interface', '')}"
            if key not in seen_keys:
                seen_keys.add(key)
                unique_books.append(book)
        
        return render_template('results.html', keyword=keyword, books=unique_books, total_books=len(unique_books))
    
    @app.route('/get_chapter', methods=['GET'])
    @verify_api_request(require_login=True)
    def get_chapter():
        book_id = request.args.get('bookId')
        chapter_id = request.args.get('chapterId')
        interface = request.args.get('interface')
        
        if not chapter_id or not interface:
            return jsonify({'error': '缺少必要参数'}), 400
        
        # 使用适配器获取音频URL
        from utils.interface_registry import get_interface_adapter
        adapter = get_interface_adapter(interface)
        
        if adapter:
            audio_url = adapter.get_audio_url(book_id, chapter_id)
            if audio_url:
                # 将HTTP URL转换为HTTPS，避免Mixed Content警告
                audio_url = ensure_https_url(audio_url)
                return jsonify({'url': audio_url})
            else:
                return jsonify({'error': '获取音频URL失败'}), 500
        else:
            return jsonify({'error': f'接口 {interface} 不存在或未配置'}), 404
    
    @app.route('/detail/<book_id>/<interface>', methods=['GET'])
    def detail(book_id, interface):
        # 获取分页参数，默认第一页，每页50条
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 50))
        
        # 分页信息
        pagination = {
            'current_page': page,
            'page_size': size,
            'total_count': 0,
            'total_pages': 0
        }
        
        # 使用适配器获取章节列表
        from utils.interface_registry import get_interface_adapter
        adapter = get_interface_adapter(interface)
        
        if not adapter:
            return render_template('index.html'), 302  # 重定向到主页
        
        chapters_data = adapter.get_chapters(book_id, page, size)
        
        # 标准化章节数据
        normalized_data = adapter.normalize_chapter_data(chapters_data) if chapters_data else {
            'book_title': '未知',
            'book_image': '',
            'book_author': '',
            'book_anchor': '',
            'chapters': []
        }
        
        # 获取分页信息
        if chapters_data:
            try:
                page_info = adapter.get_pagination_info(chapters_data, page, size)
                if isinstance(page_info, dict):
                    pagination['total_count'] = int(page_info.get('total_count') or 0)
                    pagination['total_pages'] = int(page_info.get('total_pages') or 1)
            except Exception:
                # 忽略解析错误
                pass
        
        return render_template('detail.html', book_id=book_id, interface=interface, pagination=pagination, **normalized_data)
    
    @app.route('/player/<book_id>/<interface>/<chapter_id>', methods=['GET'])
    def player(book_id, interface, chapter_id):
        # 使用适配器获取章节信息
        from utils.interface_registry import get_interface_adapter
        adapter = get_interface_adapter(interface)
        
        if not adapter:
            return render_template('index.html'), 302  # 重定向到主页
        
        # 获取章节列表
        chapters_data = adapter.get_chapters(book_id, page=1, size=100)
        normalized_data = adapter.normalize_chapter_data(chapters_data) if chapters_data else {
            'book_title': '未知',
            'book_image': '',
            'book_author': '',
            'book_anchor': '',
            'chapters': []
        }
        
        # 查找当前章节
        current_chapter = None
        prev_chapter = None
        next_chapter = None
        
        chapters = normalized_data.get('chapters', [])
        for i, chapter in enumerate(chapters):
            if str(chapter['chapter_id']) == str(chapter_id):
                current_chapter = chapter
                if i > 0:
                    prev_chapter = chapters[i-1]
                if i < len(chapters) - 1:
                    next_chapter = chapters[i+1]
                break
        
        if not current_chapter:
            current_chapter = {'title': '未知章节', 'duration': '未知'}
        
        return render_template('player.html', 
                              book_id=book_id, 
                              interface=interface, 
                              chapter_id=chapter_id, 
                              book_title=normalized_data['book_title'],
                              book_image=normalized_data['book_image'],
                              book_author=normalized_data['book_author'],
                              book_anchor=normalized_data['book_anchor'],
                              chapter_title=current_chapter.get('title', '未知章节'),
                              chapter_duration=current_chapter.get('duration', '未知'),
                              current_chapter=current_chapter,
                              prev_chapter=prev_chapter,
                              next_chapter=next_chapter)
    
    @app.route('/api/announcement', methods=['GET'])
    def get_announcement():
        """获取当前启用的公告"""
        try:
            # 获取当前IP地址
            ip_address = request.remote_addr
            if request.headers.get('X-Forwarded-For'):
                ip_address = request.headers.get('X-Forwarded-For').split(',')[0].strip()
            
            # 获取当前启用的公告
            announcement = Announcement.query.filter_by(is_active=True).order_by(Announcement.update_time.desc()).first()
            
            if not announcement:
                return jsonify({
                    'success': True,
                    'has_announcement': False,
                    'announcement': None,
                    'confirmed': False
                })
            
            # 检查该IP是否已确认此公告
            confirm_record = IPAnnouncementConfirm.query.filter_by(
                ip_address=ip_address,
                announcement_id=announcement.id
            ).first()
            
            confirmed = confirm_record is not None
            
            return jsonify({
                'success': True,
                'has_announcement': True,
                'announcement': announcement.to_dict(),
                'confirmed': confirmed
            })
        except Exception:
            return jsonify({'error': '获取公告失败'}), 500
    
    @app.route('/api/announcement/confirm', methods=['POST'])
    def confirm_announcement():
        """确认公告"""
        try:
            # 获取当前IP地址
            ip_address = request.remote_addr
            if request.headers.get('X-Forwarded-For'):
                ip_address = request.headers.get('X-Forwarded-For').split(',')[0].strip()
            
            data = request.get_json()
            announcement_id = data.get('announcement_id')
            
            if not announcement_id:
                return jsonify({'error': '缺少公告ID'}), 400
            
            # 检查公告是否存在且启用
            announcement = Announcement.query.filter_by(id=announcement_id, is_active=True).first()
            if not announcement:
                return jsonify({'error': '公告不存在或已禁用'}), 404
            
            # 检查是否已确认
            existing = IPAnnouncementConfirm.query.filter_by(
                ip_address=ip_address,
                announcement_id=announcement_id
            ).first()
            
            if existing:
                return jsonify({
                    'success': True,
                    'message': '已确认过此公告'
                })
            
            # 创建确认记录
            confirm_record = IPAnnouncementConfirm(
                ip_address=ip_address,
                announcement_id=announcement_id,
                confirm_time=datetime.utcnow()
            )
            db.session.add(confirm_record)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': '公告确认成功'
            })
        except Exception:
            db.session.rollback()
            return jsonify({'error': '确认公告失败'}), 500
    
    @app.route('/api/feedback', methods=['POST'])
    def submit_feedback():
        """提交用户反馈"""
        try:
            # 获取当前IP地址
            ip_address = request.remote_addr
            if request.headers.get('X-Forwarded-For'):
                ip_address = request.headers.get('X-Forwarded-For').split(',')[0].strip()
            
            # 获取当前用户（如果有）
            user = get_current_user()
            user_id = user.id if user else None
            
            data = request.get_json()
            content = data.get('content', '').strip()
            contact = data.get('contact', '').strip()
            
            if not content:
                return jsonify({'error': '反馈内容不能为空'}), 400
            
            if len(content) > 5000:
                return jsonify({'error': '反馈内容不能超过5000字'}), 400
            
            # 创建反馈记录
            feedback = Feedback(
                user_id=user_id,
                ip_address=ip_address,
                content=content,
                contact=contact if contact else None,
                status='pending',
                create_time=datetime.utcnow()
            )
            db.session.add(feedback)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': '反馈提交成功，感谢您的反馈！'
            })
        except Exception:
            db.session.rollback()
            return jsonify({'error': '提交反馈失败，请重试'}), 500
    
    @app.route('/static/manifest.json')
    def manifest():
        """返回 PWA manifest.json"""
        from flask import send_from_directory
        import os
        return send_from_directory(os.path.join(app.root_path, 'static'), 'manifest.json', mimetype='application/manifest+json')
    
    @app.route('/static/sw.js')
    def service_worker():
        """返回 Service Worker"""
        from flask import send_from_directory, Response
        import os
        sw_path = os.path.join(app.root_path, 'static', 'sw.js')
        with open(sw_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return Response(content, mimetype='application/javascript')
