def normalize_book_data(raw_data, interface):
    """
    标准化书籍数据
    优先使用适配器，如果没有适配器则使用硬编码逻辑（向后兼容）
    """
    # 尝试使用适配器
    from utils.interface_registry import get_interface_adapter
    adapter = get_interface_adapter(interface)
    if adapter:
        return adapter.normalize_book_data(raw_data)
    
    # 兼容旧代码（硬编码逻辑）
    normalized = []
    
    # 确保raw_data不是None
    if not raw_data:
        return normalized
    
    if interface == 'lam' and raw_data.get('status') == 0:
        # 处理lam接口数据
        book_data = raw_data.get('data', {}).get('bookData', [])
        if isinstance(book_data, list):
            for item in book_data:
                normalized.append({
                    'id': item.get('id', ''),
                    'bookTitle': item.get('bookTitle', ''),
                    'bookName': item.get('bookName', ''),
                    'bookAnchor': item.get('bookAnchor', ''),
                    'bookImage': item.get('bookImage', ''),
                    'bookDesc': item.get('bookDesc', ''),
                    'count': item.get('count', 'N/A'),
                    'heat': item.get('heat', 'N/A'),
                    'interface': 'lam'  # 添加接口标识
                })
    elif interface == 'tt':
        # 处理tt接口数据
        tt_data = raw_data.get('data', [])
        if isinstance(tt_data, list):
            for item in tt_data:
                normalized.append({
                    'id': item.get('albumId', ''),  # 使用albumId作为id
                    'bookTitle': item.get('title', ''),
                    'bookName': 'N/A',  # tt接口没有作者信息
                    'bookAnchor': item.get('Nickname', ''),
                    'bookImage': item.get('cover', ''),
                    'bookDesc': item.get('intro', ''),
                    'count': 'N/A',  # tt接口没有章节数信息
                    'heat': 'N/A',  # tt接口没有热度信息
                    'interface': 'tt'  # 添加接口标识
                })
    
    return normalized

def normalize_chapter_data(raw_data, interface):
    """
    标准化章节数据
    优先使用适配器，如果没有适配器则使用硬编码逻辑（向后兼容）
    """
    # 尝试使用适配器
    from utils.interface_registry import get_interface_adapter
    adapter = get_interface_adapter(interface)
    if adapter:
        return adapter.normalize_chapter_data(raw_data)
    
    # 兼容旧代码（硬编码逻辑）
    normalized = {
        'book_title': '',
        'book_image': '',
        'book_author': '',
        'book_anchor': '',
        'chapters': []
    }
    
    if interface == 'lam' and raw_data and raw_data.get('status') == 0:
        # 处理lam接口数据
        if raw_data.get('data', {}).get('list', []):
            # 获取书籍信息（从第一个章节中）
            first_chapter = raw_data['data']['list'][0]
            normalized['book_title'] = first_chapter.get('bookTitle', '')
            normalized['book_image'] = first_chapter.get('bookImage', '')
            normalized['book_author'] = ''  # lam接口没有作者信息
            normalized['book_anchor'] = first_chapter.get('bookHost', '')
            
            # 处理章节列表
            for item in raw_data['data']['list']:
                normalized['chapters'].append({
                    'chapter_id': item.get('chapterId', ''),
                    'title': item.get('title', ''),
                    'duration': item.get('time', ''),
                    'order': item.get('position', 0)
                })
    elif interface == 'tt' and raw_data and raw_data.get('ret') == 0:
        # 处理tt接口数据
        if raw_data.get('data', {}).get('list', []):
            # 获取书籍信息（从第一个章节中）
            first_chapter = raw_data['data']['list'][0]
            normalized['book_title'] = first_chapter.get('albumTitle', '')
            normalized['book_image'] = first_chapter.get('coverLarge', '')
            normalized['book_author'] = ''  # tt接口没有作者信息
            normalized['book_anchor'] = first_chapter.get('nickname', '')
            
            # 处理章节列表
            for item in raw_data['data']['list']:
                # 转换时长（秒 -> MM:SS）
                seconds = item.get('duration', 0)
                minutes = seconds // 60
                seconds = seconds % 60
                duration = f"{minutes:02d}:{seconds:02d}"
                
                normalized['chapters'].append({
                    'chapter_id': item.get('trackId', ''),
                    'title': item.get('title', ''),
                    'duration': duration,
                    'order': item.get('orderNo', 0)
                })
    
    # 对章节列表进行排序，确保章节顺序正确
    normalized['chapters'].sort(key=lambda x: x['order'])
    
    return normalized