/**
 * 页面访问登录守卫 + 自动登录
 * 依赖：api.js (AuthAPI / AuthCache)
 */
(function () {
    async function ensureLoggedIn() {
        // 管理后台和登录页不做拦截
        const path = window.location.pathname || '';
        if (path.startsWith('/admin')) return;
        if (path === '/profile') {
            // 个人中心页会自行处理显示
            await attemptAutoLogin();
            return;
        }

        // 已登录直接通过
        try {
            const status = await AuthAPI.getStatus();
            if (status.logged_in) return;
        } catch (e) {
            // 忽略，继续尝试自动登录
        }

        // 尝试使用本地缓存自动登录
        const auto = await attemptAutoLogin();
        if (auto) return;

        // 未登录则跳转到登录页
        const next = encodeURIComponent(window.location.pathname + window.location.search);
        window.location.href = `/profile${next ? '?next=' + next : ''}`;
    }

    async function attemptAutoLogin() {
        if (typeof AuthAPI === 'undefined' || !AuthAPI.autoLoginFromCache) return false;
        const result = await AuthAPI.autoLoginFromCache();
        return !!(result && result.success);
    }

    document.addEventListener('DOMContentLoaded', ensureLoggedIn);
})();

