from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session
from models.database import db, AppConfig
from config import SQLALCHEMY_DATABASE_URI, SQLALCHEMY_ENGINE_OPTIONS, SECRET_KEY
from routes.main import register_routes
from middleware.ip_logger import check_ip_blacklist, log_ip_access
from middleware.mobile_check import check_mobile_only_access
from datetime import timedelta
from utils.logger import setup_logger, get_logger
import os

# 初始化日志
logger = setup_logger('app', log_file='app.log')

app = Flask(__name__)

# 配置数据库
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = SQLALCHEMY_ENGINE_OPTIONS
app.config['SECRET_KEY'] = SECRET_KEY

# Session安全配置
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'  # 生产环境启用HTTPS only
app.config['SESSION_COOKIE_HTTPONLY'] = True  # 防止XSS攻击
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF保护
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # Session有效期7天

# 其他安全配置
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 限制请求体大小16MB

# 初始化数据库
db.init_app(app)

# 注册所有路由
register_routes(app)

# 健康检查端点
@app.route('/health')
def health_check():
    """ 服务健康检查 """
    import time
    try:
        # 检查数据库连接
        db.session.execute('SELECT 1')
        db_status = 'healthy'
    except Exception as e:
        logger.error(f"数据库健康检查失败: {e}")
        db_status = 'unhealthy'
    
    return jsonify({
        'status': 'healthy' if db_status == 'healthy' else 'degraded',
        'timestamp': time.time(),
        'database': db_status
    })

# 全局异常处理器
@app.errorhandler(Exception)
def handle_unexpected_error(error):
    """ 捕获所有未处理的异常 """
    logger.error(f"未捕获异常: {error}", exc_info=True)
    
    # 生产环境不返回详细错误信息
    if app.debug:
        return jsonify({
            'error': '服务器内部错误',
            'details': str(error),
            'type': type(error).__name__
        }), 500
    else:
        return jsonify({'error': '服务器内部错误，请稍后重试'}), 500

@app.errorhandler(404)
def handle_404(error):
    """ 处理404错误 """
    return jsonify({'error': '资源不存在'}), 404

@app.errorhandler(403)
def handle_403(error):
    """ 处理403错误 """
    return jsonify({'error': '访问被拒绝'}), 403

@app.errorhandler(500)
def handle_500(error):
    """ 处理500错误 """
    logger.error(f"500错误: {error}", exc_info=True)
    return jsonify({'error': '服务器错误'}), 500

# 允许未登录访问的路径（静态资源、登录/注册接口等）
PUBLIC_PATHS = {
    '/api/auth/login',
    '/api/auth/register',
    '/api/auth/status',
    '/api/auth/api-key',
    '/admin',
    '/admin/login',
    '/favicon.ico'
}

# 允许未登录访问的前缀
PUBLIC_PREFIXES = (
    '/static/',
    '/admin',
    '/api/docs',
    '/manifest',
    '/sw.js',
    '/static/manifest.json',
    '/static/sw.js',
    '/player/',
    '/detail/',
    '/results'
)

# IP黑名单检查中间件
@app.before_request
def before_request():
    # 检查IP黑名单
    is_blacklisted, ip_address = check_ip_blacklist()
    if is_blacklisted:
        return {'error': 'Access denied'}, 403
    
    # 检查手机版限制
    try:
        mobile_only_enabled = AppConfig.get_config('mobile_only_access', False)
        is_blocked, error_message = check_mobile_only_access(mobile_only_enabled)
        if is_blocked:
            # 返回友好的错误页面
            error_html = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>访问受限</title>
                <style>
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        min-height: 100vh;
                        margin: 0;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: #333;
                    }
                    .container {
                        background: white;
                        padding: 40px;
                        border-radius: 20px;
                        box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                        text-align: center;
                        max-width: 500px;
                        margin: 20px;
                    }
                    .icon {
                        font-size: 80px;
                        margin-bottom: 20px;
                    }
                    h1 {
                        margin: 0 0 20px 0;
                        color: #333;
                    }
                    p {
                        color: #666;
                        line-height: 1.6;
                        margin: 0 0 30px 0;
                    }
                    .note {
                        background: #f5f5f5;
                        padding: 15px;
                        border-radius: 10px;
                        margin-top: 20px;
                        font-size: 14px;
                        color: #888;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="icon">📱</div>
                    <h1>仅支持手机访问</h1>
                    <p>抱歉，当前网站仅支持手机设备访问，请使用手机浏览器打开。</p>
                    <div class="note">
                        如果您使用的是手机浏览器但仍然看到此提示，请联系管理员。
                    </div>
                </div>
            </body>
            </html>
            """
            return render_template_string(error_html), 403
    except Exception:
        # 如果检查失败，不影响正常访问
        pass
    
    # 记录IP访问（异步，不阻塞请求）
    try:
        log_ip_access()
    except:
        pass  # 记录失败不影响正常请求

    # 登录校验：除公开路径外，访问网站必须已登录
    path = request.path
    if request.method == 'OPTIONS':
        return

    if path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES):
        return

    # 个人中心页用于登录/注册，不拦截
    if path == '/profile':
        return

    if session.get('user_id'):
        return

    # API请求直接返回401，页面请求重定向到登录页
    # 这里只根据URL前缀判断是否为API，避免浏览器插件修改 Accept 头导致误判
    if path.startswith('/api/'):
        return jsonify({'error': '请先登录'}), 401

    next_url = request.full_path if request.query_string else path
    return redirect(url_for('profile', next=next_url))

if __name__ == '__main__':
    app.run(debug=True, port=6221, host='0.0.0.0')