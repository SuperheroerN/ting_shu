/**
 * Service Worker for 有声书搜索 PWA
 */

const CACHE_NAME = 'audiobook-search-v2';
const RUNTIME_CACHE = 'audiobook-runtime-v2';

// 需要缓存的静态资源
const STATIC_CACHE_URLS = [
    '/',
    '/static/css/base.css',
    '/static/css/home.css',
    '/static/css/results.css',
    '/static/css/detail.css',
    '/static/css/player.css',
    '/static/css/history.css',
    '/static/css/profile.css',
    '/static/css/navbar.css',
    '/static/css/announcement.css',
    '/static/css/global-player.css',
    '/static/js/api.js',
    '/static/js/auth-guard.js',
    '/static/js/request-auth.js',
    '/static/js/announcement.js',
    '/static/js/global-player.js',
    '/static/js/player-utils.js',
    '/static/js/player-enhancements.js',
    '/static/js/pwa-install.js',
    '/static/manifest.json',
    '/static/images/icon-192x192.png',
    '/static/images/icon-512x512.png'
];

// 需要运行时缓存的资源类型
const RUNTIME_CACHE_PATTERNS = [
    /\/static\//,
    /\/api\//,
    /\.(?:png|jpg|jpeg|svg|gif|webp)$/
];

// 安装事件 - 缓存静态资源
self.addEventListener('install', (event) => {
    console.log('[Service Worker] Installing...');
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[Service Worker] Caching static assets');
            return cache.addAll(STATIC_CACHE_URLS).catch((error) => {
                console.warn('[Service Worker] Failed to cache some assets:', error);
                // 即使部分资源缓存失败，也要继续安装
                return Promise.resolve();
            });
        })
    );
    // 强制激活新的 service worker
    self.skipWaiting();
});

// 激活事件 - 清理旧缓存
self.addEventListener('activate', (event) => {
    console.log('[Service Worker] Activating...');
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME && cacheName !== RUNTIME_CACHE) {
                        console.log('[Service Worker] Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    // 立即控制所有客户端
    return self.clients.claim();
});

//  fetch 事件 - 网络优先，缓存备用
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // 跳过非 GET 请求
    if (request.method !== 'GET') {
        return;
    }

    // 跳过跨域请求（除非是图片等静态资源）
    if (url.origin !== location.origin && !request.url.match(/\.(?:png|jpg|jpeg|svg|gif|webp)$/)) {
        return;
    }

    // API 请求：网络优先，失败时使用缓存
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(request)
                .then((response) => {
                    // 克隆响应，因为响应只能使用一次
                    const responseClone = response.clone();
                    // 缓存成功的响应
                    if (response.status === 200) {
                        caches.open(RUNTIME_CACHE).then((cache) => {
                            cache.put(request, responseClone);
                        });
                    }
                    return response;
                })
                .catch(() => {
                    // 网络失败，尝试从缓存获取
                    return caches.match(request).then((cachedResponse) => {
                        if (cachedResponse) {
                            return cachedResponse;
                        }
                        // 如果没有缓存，返回错误响应
                        return new Response(
                            JSON.stringify({ error: '网络错误，请检查网络连接' }),
                            {
                                status: 503,
                                headers: { 'Content-Type': 'application/json' }
                            }
                        );
                    });
                })
        );
        return;
    }

    // 静态资源：缓存优先，网络备用
    if (RUNTIME_CACHE_PATTERNS.some(pattern => pattern.test(request.url))) {
        event.respondWith(
            caches.match(request).then((cachedResponse) => {
                if (cachedResponse) {
                    return cachedResponse;
                }
                // 缓存中没有，从网络获取并缓存
                return fetch(request).then((response) => {
                    if (response.status === 200) {
                        const responseClone = response.clone();
                        caches.open(RUNTIME_CACHE).then((cache) => {
                            cache.put(request, responseClone);
                        });
                    }
                    return response;
                });
            })
        );
        return;
    }

    // HTML 页面：网络优先，缓存备用
    if (request.headers.get('accept').includes('text/html')) {
        event.respondWith(
            fetch(request)
                .then((response) => {
                    const responseClone = response.clone();
                    caches.open(RUNTIME_CACHE).then((cache) => {
                        cache.put(request, responseClone);
                    });
                    return response;
                })
                .catch(() => {
                    return caches.match(request).then((cachedResponse) => {
                        if (cachedResponse) {
                            return cachedResponse;
                        }
                        // 返回离线页面或默认页面
                        return caches.match('/');
                    });
                })
        );
        return;
    }
});

// 后台同步（如果支持）
self.addEventListener('sync', (event) => {
    console.log('[Service Worker] Background sync:', event.tag);
    // 可以在这里实现后台数据同步
});

// 推送通知（如果需要）
self.addEventListener('push', (event) => {
    console.log('[Service Worker] Push notification received');
    // 可以实现推送通知功能
});



