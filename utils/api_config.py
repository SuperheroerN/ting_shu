"""
API配置工具 - 从数据库读取接口配置
"""
from models.database import db, APIConfig
from flask import current_app

def get_api_config(interface, config_type):
    """
    获取API配置
    :param interface: 接口名称
    :param config_type: 'search', 'chapters', 'url'
    :return: dict 配置字典
    """
    try:
        configs = APIConfig.query.filter_by(
            interface=interface,
            config_type=config_type
        ).all()
        
        if not configs:
            # 如果没有配置，返回空配置
            return {}
        
        # 组织配置
        result = {}
        for config in configs:
            if config.config_key:
                result[config.config_key] = config.config_value
            else:
                result['_url'] = config.config_value
        
        return result
    except Exception as e:
        print(f"获取API配置失败: {e}")
        return {}