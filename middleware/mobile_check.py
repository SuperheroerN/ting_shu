"""
手机设备检测中间件
"""
from flask import request
import re

def is_mobile_device():
    """检测是否为手机设备"""
    user_agent = request.headers.get('User-Agent', '').lower()
    
    # 手机设备关键词
    mobile_keywords = [
        'mobile', 'android', 'iphone', 'ipod', 'ipad', 
        'blackberry', 'windows phone', 'opera mini', 
        'iemobile', 'kindle', 'silk', 'fennec', 
        'maemo', 'bada', 'nokia', 'lg', 'ucweb',
        'skyfire', 'bolt', 'teashark', 'blazer',
        'mini', 'mmp', 'windows ce', 'smartphone',
        'palm', 'netfront', 'semc-browser', 'opera mobi',
        'symbian', 'webos', 'pda', 'avantgo', 'avantg',
        'plucker', 'xiino', 'risc os', 'teleca', 'opera mini'
    ]
    
    # 检查是否包含手机关键词
    for keyword in mobile_keywords:
        if keyword in user_agent:
            return True
    
    # 检查移动设备的常见屏幕尺寸（通过User-Agent中的信息判断）
    mobile_patterns = [
        r'android.*mobile',
        r'iphone',
        r'ipod',
        r'ipad',
        r'windows\s+phone',
        r'blackberry',
        r'opera\s+mini',
        r'iemobile',
        r'mobile.*firefox'
    ]
    
    for pattern in mobile_patterns:
        if re.search(pattern, user_agent, re.IGNORECASE):
            return True
    
    return False

def check_mobile_only_access(enabled):
    """
    检查是否只允许手机访问
    enabled: 是否启用手机版限制
    返回: (is_blocked, error_message)
    """
    if not enabled:
        return False, None
    
    # 允许访问后台管理页面（管理员需要从任何设备访问）
    if request.path.startswith('/admin'):
        return False, None
    
    # 允许访问静态资源
    if request.path.startswith('/static/'):
        return False, None
    
    # 检查是否为手机设备
    if not is_mobile_device():
        return True, '仅允许手机设备访问，请使用手机浏览器打开'
    
    return False, None



