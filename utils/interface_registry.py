"""
接口注册器 - 管理所有接口适配器
支持动态注册、加载和获取接口适配器
"""
from typing import Dict, Optional
from utils.interface_adapter import ConfigBasedAdapter, InterfaceAdapter
from utils.api_config import get_api_config
import json


class InterfaceRegistry:
    """接口注册器（单例模式）"""
    
    _instance = None
    _adapters: Dict[str, InterfaceAdapter] = {}
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(InterfaceRegistry, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._adapters = {}
            self._initialized = True
    
    def register(self, interface_name: str, adapter: InterfaceAdapter):
        """注册接口适配器"""
        self._adapters[interface_name] = adapter
        print(f"接口适配器已注册: {interface_name}")
    
    def get_adapter(self, interface_name: str) -> Optional[InterfaceAdapter]:
        """获取接口适配器"""
        # 如果适配器已存在，直接返回
        if interface_name in self._adapters:
            return self._adapters[interface_name]
        
        # 否则尝试从数据库加载配置并创建适配器
        adapter = self._load_adapter_from_db(interface_name)
        if adapter:
            self._adapters[interface_name] = adapter
            return adapter
        
        return None
    
    def unregister(self, interface_name: str):
        """注销接口适配器"""
        if interface_name in self._adapters:
            del self._adapters[interface_name]
            print(f"接口适配器已注销: {interface_name}")
    
    def list_interfaces(self) -> list:
        """列出所有已注册的接口"""
        return list(self._adapters.keys())
    
    def _load_adapter_from_db(self, interface_name: str) -> Optional[InterfaceAdapter]:
        """
        从数据库加载接口配置并创建适配器
        优先使用数据库配置
        """
        from models.database import InterfaceDefinition
        
        try:
            # 从数据库获取接口定义（不限制enabled，因为可能需要在禁用时也能加载配置）
            interface_def = InterfaceDefinition.query.filter_by(
                interface_name=interface_name
            ).first()
            
            if not interface_def:
                return None
            
            # 获取各类型的URL配置
            search_config = get_api_config(interface_name, 'search')
            chapters_config = get_api_config(interface_name, 'chapters')
            url_config = get_api_config(interface_name, 'url')
            
            field_mapping = {}
            if interface_def and interface_def.field_mapping:
                # 如果数据库中有字段映射配置，使用数据库的
                try:
                    field_mapping = json.loads(interface_def.field_mapping)
                except:
                    print(f"[{interface_name}] 字段映射JSON解析失败，使用默认配置")
                    field_mapping = {}
            
            # 合并字段映射配置到URL配置中
            if 'search' in field_mapping:
                search_config['field_mapping'] = field_mapping['search']
            if 'chapters' in field_mapping:
                chapters_config['field_mapping'] = field_mapping['chapters']
            if 'url' in field_mapping:
                url_config['field_mapping'] = field_mapping['url']
            
            # 创建适配器配置
            adapter_config = {
                'search': search_config,
                'chapters': chapters_config,
                'url': url_config
            }
            
            # 创建适配器
            adapter = ConfigBasedAdapter(interface_name, adapter_config)
            return adapter
            
        except Exception as e:
            print(f"加载接口适配器失败 ({interface_name}): {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def reload(self, interface_name: Optional[str] = None):
        """
        重新加载接口适配器
        如果指定了 interface_name，只重新加载该接口；否则重新加载所有接口
        """
        if interface_name:
            if interface_name in self._adapters:
                del self._adapters[interface_name]
            self.get_adapter(interface_name)  # 这会触发重新加载
        else:
            # 重新加载所有接口
            interface_names = list(self._adapters.keys())
            self._adapters.clear()
            for name in interface_names:
                self.get_adapter(name)


# 全局注册器实例
registry = InterfaceRegistry()


def get_interface_adapter(interface_name: str) -> Optional[InterfaceAdapter]:
    """
    获取接口适配器（便捷函数）
    """
    return registry.get_adapter(interface_name)


def register_interface(interface_name: str, adapter: InterfaceAdapter):
    """
    注册接口适配器（便捷函数）
    """
    registry.register(interface_name, adapter)


def list_available_interfaces() -> list:
    """
    列出所有可用的接口（便捷函数）
    """
    return registry.list_interfaces()