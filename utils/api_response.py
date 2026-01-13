"""
统一的API响应格式工具
"""
from flask import jsonify
from datetime import datetime
from functools import wraps
from utils.logger import get_api_logger, log_error_with_context

logger = get_api_logger()

def api_success(data=None, message=None, code=200):
    """
    成功响应
    
    Args:
        data: 响应数据
        message: 成功消息
        code: HTTP状态码
    
    Returns:
        Flask响应对象
    """
    response = {
        'success': True,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }
    
    if message:
        response['message'] = message
    
    if data is not None:
        response['data'] = data
    
    return jsonify(response), code

def api_error(error_message, code=400, error_type=None, details=None):
    """
    错误响应
    
    Args:
        error_message: 错误消息
        code: HTTP状态码
        error_type: 错误类型（如 'ValidationError', 'AuthError'）
        details: 详细错误信息（仅在DEBUG模式下返回）
    
    Returns:
        Flask响应对象
    """
    response = {
        'success': False,
        'error': error_message,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }
    
    if error_type:
        response['error_type'] = error_type
    
    # 详细错误信息仅在开发环境返回
    if details:
        from flask import current_app
        if current_app.debug:
            response['details'] = details
    
    return jsonify(response), code

def validate_params(required_params=None, optional_params=None):
    """
    参数验证装饰器
    
    Args:
        required_params: 必需参数列表 [(参数名, 类型), ...]
        optional_params: 可选参数列表 [(参数名, 类型, 默认值), ...]
    
    使用示例:
        @validate_params(
            required_params=[('book_id', str), ('interface', str)],
            optional_params=[('page', int, 1)]
        )
        def my_api_func(validated_data):
            book_id = validated_data['book_id']
            ...
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            from flask import request
            
            # 获取请求数据
            if request.method == 'GET':
                data = request.args.to_dict()
            else:
                data = request.get_json() or {}
            
            validated_data = {}
            
            # 验证必需参数
            if required_params:
                for param_name, param_type in required_params:
                    value = data.get(param_name)
                    
                    if value is None or value == '':
                        return api_error(
                            f'缺少必需参数: {param_name}',
                            code=400,
                            error_type='ValidationError'
                        )
                    
                    # 类型转换
                    try:
                        if param_type == bool:
                            # 特殊处理布尔值
                            if isinstance(value, str):
                                validated_data[param_name] = value.lower() in ('true', '1', 'yes')
                            else:
                                validated_data[param_name] = bool(value)
                        elif param_type == int:
                            validated_data[param_name] = int(value)
                        elif param_type == float:
                            validated_data[param_name] = float(value)
                        else:
                            validated_data[param_name] = param_type(value)
                    except (ValueError, TypeError) as e:
                        return api_error(
                            f'参数类型错误: {param_name} 应为 {param_type.__name__}',
                            code=400,
                            error_type='ValidationError'
                        )
            
            # 验证可选参数
            if optional_params:
                for param_info in optional_params:
                    if len(param_info) == 3:
                        param_name, param_type, default_value = param_info
                    else:
                        param_name, param_type = param_info
                        default_value = None
                    
                    value = data.get(param_name, default_value)
                    
                    if value is not None:
                        try:
                            if param_type == bool:
                                if isinstance(value, str):
                                    validated_data[param_name] = value.lower() in ('true', '1', 'yes')
                                else:
                                    validated_data[param_name] = bool(value)
                            elif param_type == int:
                                validated_data[param_name] = int(value)
                            elif param_type == float:
                                validated_data[param_name] = float(value)
                            else:
                                validated_data[param_name] = param_type(value)
                        except (ValueError, TypeError):
                            validated_data[param_name] = default_value
                    else:
                        validated_data[param_name] = default_value
            
            # 将验证后的数据传递给函数
            return f(validated_data, *args, **kwargs)
        
        return wrapper
    return decorator

def handle_exceptions(f):
    """
    统一异常处理装饰器
    
    捕获并记录所有异常，返回统一的错误响应
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            log_error_with_context(logger, e, {'function': f.__name__})
            return api_error(
                f'参数错误: {str(e)}',
                code=400,
                error_type='ValueError'
            )
        except PermissionError as e:
            log_error_with_context(logger, e, {'function': f.__name__})
            return api_error(
                '权限不足',
                code=403,
                error_type='PermissionError'
            )
        except Exception as e:
            log_error_with_context(logger, e, {'function': f.__name__})
            from flask import current_app
            return api_error(
                '服务器内部错误',
                code=500,
                error_type=type(e).__name__,
                details=str(e) if current_app.debug else None
            )
    
    return wrapper
