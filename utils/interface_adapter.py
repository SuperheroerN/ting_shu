"""
接口适配器基类和通用适配器
支持通过字段映射配置自动适配不同接口的返回值格式
"""
import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod


class InterfaceAdapter(ABC):
    """接口适配器基类"""
    
    def __init__(self, interface_name: str, config: Dict):
        """
        初始化适配器
        :param interface_name: 接口名称
        :param config: 接口配置字典，包含 search, chapters, url 三个配置类型的字段映射
        """
        self.interface_name = interface_name
        self.config = config
        self.search_config = config.get('search', {})
        self.chapters_config = config.get('chapters', {})
        self.url_config = config.get('url', {})
    
    @abstractmethod
    def search_books(self, keyword: str) -> Optional[Dict]:
        """搜索书籍"""
        pass
    
    @abstractmethod
    def get_chapters(self, book_id: str, page: int = 1, size: int = 50) -> Optional[Dict]:
        """获取章节列表"""
        pass
    
    @abstractmethod
    def get_audio_url(self, book_id: Optional[str], chapter_id: str) -> Optional[str]:
        """获取音频URL"""
        pass
    
    def get_pagination_info(self, raw_data: Dict, page: int, size: int) -> Dict[str, int]:
        """
        从章节原始数据中提取分页信息
        使用 chapters_config.field_mapping.pagination 中的配置：
        {
            "total_count_field": "data.count",
            "max_page_field": "data.maxPageId"  # 可选
        }
        这样后续新增的接口只要配置好字段映射即可自动支持分页统计。
        """
        pagination = {
            "total_count": 0,
            "total_pages": 1
        }

        if not raw_data:
            return pagination

        field_mapping = self.chapters_config.get("field_mapping", {})
        pagination_map = field_mapping.get("pagination", {})
        if not pagination_map:
            return pagination

        total_count_field = pagination_map.get("total_count_field")
        max_page_field = pagination_map.get("max_page_field")

        # 提取总章节数
        total_count = 0
        if total_count_field:
            value = self._get_nested_value(raw_data, total_count_field)
            try:
                total_count = int(value or 0)
            except (TypeError, ValueError):
                total_count = 0

        # 提取总页数（如果接口直接提供）
        total_pages = 0
        if max_page_field:
            value = self._get_nested_value(raw_data, max_page_field)
            try:
                total_pages = int(value or 0)
            except (TypeError, ValueError):
                total_pages = 0

        # 如果没有提供总页数，但有总条数，则根据每页大小计算
        if total_pages <= 0 and size > 0 and total_count > 0:
            total_pages = (total_count + size - 1) // size

        if total_count > 0:
            pagination["total_count"] = total_count
        if total_pages > 0:
            pagination["total_pages"] = total_pages

        return pagination

    def normalize_book_data(self, raw_data: Dict) -> List[Dict]:
        """
        标准化书籍搜索数据
        使用字段映射配置自动提取字段
        """
        if not raw_data:
            return []
        
        # 获取字段映射配置
        mapping = self.search_config.get('field_mapping', {})
        success_field = mapping.get('success_field')  # 成功标识字段（可能为None）
        success_value = mapping.get('success_value')  # 成功值（可能为None）
        data_path = mapping.get('data_path', 'data.bookData')  # 数据路径
        
        # 检查是否成功（如果success_field为None，则跳过检查）
        if success_field is not None:
            actual_value = raw_data.get(success_field)
            if actual_value != success_value:
                print(f"[{self.interface_name}] 搜索失败: success_field={success_field}, expected={success_value}, actual={actual_value}")
                return []
        else:
            # 如果没有配置success_field，检查data_path是否存在
            data_check = self._get_nested_value(raw_data, data_path)
            if data_check is None:
                print(f"[{self.interface_name}] 搜索失败: 数据路径 {data_path} 不存在")
                return []
        
        # 提取数据列表
        data_list = self._get_nested_value(raw_data, data_path)
        if not isinstance(data_list, list):
            print(f"[{self.interface_name}] 数据路径错误: data_path={data_path}, result_type={type(data_list)}, result={data_list}")
            return []
        
        print(f"[{self.interface_name}] 搜索成功，找到 {len(data_list)} 条结果")
        
        # 字段映射
        field_map = mapping.get('fields', {})
        
        normalized = []
        for item in data_list:
            # 对于每个字段，如果映射值是 'N/A'，直接使用 'N/A'，否则从数据中提取
            def get_field_value(field_key: str, default_field: str = None) -> Any:
                mapped_field = field_map.get(field_key, default_field or field_key)
                if mapped_field == 'N/A':
                    return 'N/A'
                return self._get_mapped_value(item, mapped_field, default='N/A' if field_key in ['count', 'heat', 'bookName'] else '')
            
            book = {
                'id': get_field_value('id', 'id'),
                'bookTitle': get_field_value('bookTitle', 'bookTitle'),
                'bookName': get_field_value('bookName', 'bookName'),
                'bookAnchor': get_field_value('bookAnchor', 'bookAnchor'),
                'bookImage': get_field_value('bookImage', 'bookImage'),
                'bookDesc': get_field_value('bookDesc', 'bookDesc'),
                'count': get_field_value('count', 'count'),
                'heat': get_field_value('heat', 'heat'),
                'interface': self.interface_name
            }
            normalized.append(book)
        
        return normalized
    
    def normalize_chapter_data(self, raw_data: Dict) -> Dict:
        """
        标准化章节列表数据
        """
        normalized = {
            'book_title': '',
            'book_image': '',
            'book_author': '',
            'book_anchor': '',
            'chapters': []
        }
        
        if not raw_data:
            return normalized
        
        # 获取字段映射配置
        mapping = self.chapters_config.get('field_mapping', {})
        success_field = mapping.get('success_field', 'status')
        success_value = mapping.get('success_value', 0)
        data_path = mapping.get('data_path', 'data.list')
        
        # 检查是否成功
        if raw_data.get(success_field) != success_value:
            return normalized
        
        # 提取章节列表
        chapter_list = self._get_nested_value(raw_data, data_path)
        if not isinstance(chapter_list, list) or len(chapter_list) == 0:
            return normalized
        
        # 获取书籍信息（从第一个章节）
        first_chapter = chapter_list[0]
        book_info_map = mapping.get('book_info_fields', {})
        normalized['book_title'] = self._get_mapped_value(first_chapter, book_info_map.get('book_title', 'bookTitle'))
        normalized['book_image'] = self._get_mapped_value(first_chapter, book_info_map.get('book_image', 'bookImage'))
        normalized['book_anchor'] = self._get_mapped_value(first_chapter, book_info_map.get('book_anchor', 'bookHost'))
        
        # 处理章节列表
        chapter_map = mapping.get('chapter_fields', {})
        for item in chapter_list:
            # 处理时长格式
            duration_raw = self._get_mapped_value(item, chapter_map.get('duration', 'time'))
            duration = self._format_duration(duration_raw, chapter_map.get('duration_format', 'auto'))
            
            chapter = {
                'chapter_id': str(self._get_mapped_value(item, chapter_map.get('chapter_id', 'chapterId'))),
                'title': self._get_mapped_value(item, chapter_map.get('title', 'title')),
                'duration': duration,
                'order': int(self._get_mapped_value(item, chapter_map.get('order', 'position'), default=0))
            }
            normalized['chapters'].append(chapter)
        
        # 排序
        normalized['chapters'].sort(key=lambda x: x['order'])
        
        return normalized
    
    def extract_audio_url(self, raw_data: Dict) -> Optional[str]:
        """
        从响应中提取音频URL
        """
        if not raw_data:
            return None
        
        mapping = self.url_config.get('field_mapping', {})
        success_field = mapping.get('success_field', 'status')
        success_value = mapping.get('success_value', 0)
        url_field = mapping.get('url_field', 'src')
        
        # 检查是否成功
        if raw_data.get(success_field) != success_value:
            return None
        
        # 提取URL
        url = self._get_mapped_value(raw_data, url_field)
        return url if url else None
    
    def _get_mapped_value(self, data: Dict, field_path: str, default: Any = '') -> Any:
        """
        根据字段路径提取值
        支持点号分隔的嵌套路径，如 'data.bookTitle'
        如果 field_path 是 'N/A'，直接返回 default
        """
        if not field_path or field_path == 'N/A':
            return default
        
        result = self._get_nested_value(data, field_path)
        # 如果结果是 None 或空字符串，返回默认值
        if result is None or result == '':
            return default
        return result
    
    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """
        获取嵌套字典的值
        如 'data.list' -> data['data']['list']
        """
        if not path:
            return None
        
        keys = path.split('.')
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
            if value is None:
                return None
        return value
    
    def _format_duration(self, duration: Any, format_type: str = 'auto') -> str:
        """
        格式化时长
        format_type: 'auto'（自动识别）, 'seconds'（秒数）, 'string'（字符串，如 '55:11'）
        """
        if not duration:
            return '00:00'
        
        if format_type == 'string' or isinstance(duration, str):
            return duration
        
        # 如果是数字，转换为 MM:SS 格式
        try:
            seconds = int(duration)
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes:02d}:{secs:02d}"
        except (ValueError, TypeError):
            return str(duration)
    
    def _make_request(self, url: str, method: str = 'GET', params: Optional[Dict] = None, 
                     data: Optional[Dict] = None, json_data: Optional[Dict] = None, 
                     headers: Optional[Dict] = None, timeout: int = 10) -> Optional[Dict]:
        """
        发送HTTP请求
        :param url: 请求URL
        :param method: HTTP方法 (GET, POST, PUT, DELETE等)
        :param params: URL参数（用于GET请求）
        :param data: 表单数据（用于POST请求）
        :param json_data: JSON数据（用于POST请求）
        :param headers: 请求头
        :param timeout: 超时时间（秒）
        """
        try:
            method = method.upper()
            
            # 准备请求参数
            request_kwargs = {
                'timeout': timeout
            }
            
            if headers:
                request_kwargs['headers'] = headers
            
            if method == 'GET':
                if params:
                    request_kwargs['params'] = params
                response = requests.get(url, **request_kwargs)
            elif method == 'POST':
                if json_data:
                    request_kwargs['json'] = json_data
                elif data:
                    request_kwargs['data'] = data
                response = requests.post(url, **request_kwargs)
            elif method == 'PUT':
                if json_data:
                    request_kwargs['json'] = json_data
                elif data:
                    request_kwargs['data'] = data
                response = requests.put(url, **request_kwargs)
            elif method == 'DELETE':
                response = requests.delete(url, **request_kwargs)
            else:
                # 默认使用GET
                response = requests.get(url, **request_kwargs)
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"{self.interface_name}接口请求失败 ({method} {url}): {e}")
            return None
        except ValueError as e:
            print(f"{self.interface_name}接口响应解析失败: {e}")
            return None


class ConfigBasedAdapter(InterfaceAdapter):
    """基于配置的通用适配器"""
    
    def search_books(self, keyword: str) -> Optional[Dict]:
        """搜索书籍"""
        import urllib.parse
        encoded_keyword = urllib.parse.quote(keyword)
        
        # 支持 url 和 _url 两种键名
        url_template = self.search_config.get('url', '') or self.search_config.get('_url', '')
        if not url_template:
            return None
        
        # 获取HTTP方法（默认GET）
        method = self.search_config.get('method', 'GET').upper()
        
        # 获取请求头配置
        headers = self.search_config.get('headers', {})
        if isinstance(headers, str):
            try:
                headers = json.loads(headers)
            except:
                headers = {}
        
        url = url_template.replace('{keyword}', encoded_keyword)
        
        print(f"=== {self.interface_name}接口搜索调试信息 ===")
        print(f"搜索关键词: {keyword}")
        print(f"请求方法: {method}")
        print(f"请求URL: {url}")
        
        # 根据方法类型处理参数
        if method == 'GET':
            result = self._make_request(url, method=method, headers=headers)
        elif method == 'POST':
            # POST请求：检查是否需要JSON或表单数据
            post_data_config = self.search_config.get('post_data', {})
            if post_data_config.get('type') == 'json':
                json_data = post_data_config.get('data', {})
                # 替换占位符
                json_data_str = json.dumps(json_data).replace('{keyword}', keyword)
                json_data = json.loads(json_data_str)
                result = self._make_request(url, method=method, json_data=json_data, headers=headers)
            else:
                # 表单数据
                form_data = post_data_config.get('data', {})
                # 替换占位符
                form_data = {k: v.replace('{keyword}', keyword) if isinstance(v, str) else v 
                            for k, v in form_data.items()}
                result = self._make_request(url, method=method, data=form_data, headers=headers)
        else:
            result = self._make_request(url, method=method, headers=headers)
        
        if result:
            print(f"响应状态码: 200")
            print(f"响应内容: {json.dumps(result, ensure_ascii=False)[:200]}...")
        
        return result
    
    def get_chapters(self, book_id: str, page: int = 1, size: int = 50) -> Optional[Dict]:
        """获取章节列表"""
        # 支持 url 和 _url 两种键名
        url_template = self.chapters_config.get('url', '') or self.chapters_config.get('_url', '')
        if not url_template:
            return None
        
        # 获取HTTP方法（默认GET）
        method = self.chapters_config.get('method', 'GET').upper()
        
        # 获取请求头配置
        headers = self.chapters_config.get('headers', {})
        if isinstance(headers, str):
            try:
                headers = json.loads(headers)
            except:
                headers = {}
        
        # 替换占位符
        url = url_template
        url = url.replace('{bookId}', str(book_id))
        url = url.replace('{page}', str(page))
        url = url.replace('{size}', str(size))
        
        # 如果需要时间戳
        if '{timestamp}' in url:
            timestamp = int(datetime.now().timestamp() * 1000)
            url = url.replace('{timestamp}', str(timestamp))
        
        print(f"=== {self.interface_name}接口章节列表调试信息 ===")
        print(f"请求方法: {method}")
        print(f"请求参数: book_id={book_id}, page={page}, size={size}")
        print(f"请求URL: {url}")
        
        # 根据方法类型处理参数
        if method == 'GET':
            result = self._make_request(url, method=method, headers=headers)
        elif method == 'POST':
            post_data_config = self.chapters_config.get('post_data', {})
            if post_data_config.get('type') == 'json':
                json_data = post_data_config.get('data', {})
                # 替换占位符
                json_data_str = json.dumps(json_data)\
                    .replace('{bookId}', str(book_id))\
                    .replace('{page}', str(page))\
                    .replace('{size}', str(size))
                if '{timestamp}' in json_data_str:
                    timestamp = int(datetime.now().timestamp() * 1000)
                    json_data_str = json_data_str.replace('{timestamp}', str(timestamp))
                json_data = json.loads(json_data_str)
                result = self._make_request(url, method=method, json_data=json_data, headers=headers)
            else:
                form_data = post_data_config.get('data', {})
                form_data = {k: str(v).replace('{bookId}', str(book_id))
                            .replace('{page}', str(page))
                            .replace('{size}', str(size))
                            if isinstance(v, str) else v 
                            for k, v in form_data.items()}
                result = self._make_request(url, method=method, data=form_data, headers=headers)
        else:
            result = self._make_request(url, method=method, headers=headers)
        
        # 特殊处理：如果配置中指定了需要额外的总章节数查询
        if result and self.chapters_config.get('need_total_count_query', False):
            # 这里可以根据需要实现额外的查询逻辑
            pass
        
        return result
    
    def get_audio_url(self, book_id: Optional[str], chapter_id: str) -> Optional[str]:
        """获取音频URL"""
        # 支持 url 和 _url 两种键名
        url_template = self.url_config.get('url', '') or self.url_config.get('_url', '')
        if not url_template:
            return None
        
        # 获取HTTP方法（默认GET）
        method = self.url_config.get('method', 'GET').upper()
        
        # 获取请求头配置
        headers = self.url_config.get('headers', {})
        if isinstance(headers, str):
            try:
                headers = json.loads(headers)
            except:
                headers = {}
        
        # 替换占位符
        url = url_template
        if '{bookId}' in url:
            if not book_id:
                return None
            url = url.replace('{bookId}', str(book_id))
        if '{chapterId}' in url:
            url = url.replace('{chapterId}', str(chapter_id))
        if '{trackId}' in url:
            url = url.replace('{trackId}', str(chapter_id))
        if '{timestamp}' in url:
            timestamp = self.url_config.get('timestamp', 1765629405658)  # 默认时间戳或配置中的时间戳
            url = url.replace('{timestamp}', str(timestamp))
        
        print(f"=== {self.interface_name}接口音频URL调试信息 ===")
        print(f"请求方法: {method}")
        print(f"请求参数: book_id={book_id}, chapter_id={chapter_id}")
        print(f"请求URL: {url}")
        
        # 根据方法类型处理参数
        if method == 'GET':
            result = self._make_request(url, method=method, headers=headers)
        elif method == 'POST':
            post_data_config = self.url_config.get('post_data', {})
            if post_data_config.get('type') == 'json':
                json_data = post_data_config.get('data', {})
                # 替换占位符
                json_data_str = json.dumps(json_data)
                if book_id:
                    json_data_str = json_data_str.replace('{bookId}', str(book_id))
                json_data_str = json_data_str.replace('{chapterId}', str(chapter_id))\
                    .replace('{trackId}', str(chapter_id))
                if '{timestamp}' in json_data_str:
                    timestamp = self.url_config.get('timestamp', 1765629405658)
                    json_data_str = json_data_str.replace('{timestamp}', str(timestamp))
                json_data = json.loads(json_data_str)
                result = self._make_request(url, method=method, json_data=json_data, headers=headers)
            else:
                form_data = post_data_config.get('data', {})
                form_data = {k: str(v).replace('{chapterId}', str(chapter_id))
                            .replace('{trackId}', str(chapter_id))
                            if isinstance(v, str) else v 
                            for k, v in form_data.items()}
                if book_id:
                    form_data = {k: str(v).replace('{bookId}', str(book_id)) 
                                if isinstance(v, str) else v 
                                for k, v in form_data.items()}
                result = self._make_request(url, method=method, data=form_data, headers=headers)
        else:
            result = self._make_request(url, method=method, headers=headers)
        
        if result:
            audio_url = self.extract_audio_url(result)
            if audio_url:
                print(f"成功获取音频地址: {audio_url}")
            else:
                print(f"未能从响应中提取音频URL")
            return audio_url
        
        return None