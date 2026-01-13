/**
 * PWA调试工具
 * 在控制台输入 checkPWA() 查看PWA状态
 */

window.checkPWA = function() {
    console.log('\n=== 📱 PWA 状态检查 ===\n');
    
    const results = {
        protocol: location.protocol,
        hostname: location.hostname,
        isSecure: location.protocol === 'https:' || location.hostname === 'localhost',
        hasServiceWorker: 'serviceWorker' in navigator,
        hasManifest: !!document.querySelector('link[rel="manifest"]'),
        isStandalone: window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone,
        hasBeforeInstallPrompt: !!window.pwaInstall?.deferredPrompt,
        swRegistration: null,
        manifestData: null
    };
    
    // 检查Service Worker注册状态
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.getRegistration().then(reg => {
            if (reg) {
                results.swRegistration = {
                    scope: reg.scope,
                    state: reg.active?.state,
                    updateViaCache: reg.updateViaCache
                };
                console.log('✅ Service Worker已注册:', results.swRegistration);
            } else {
                console.log('❌ Service Worker未注册');
            }
        });
    }
    
    // 检查manifest
    const manifestLink = document.querySelector('link[rel="manifest"]');
    if (manifestLink) {
        fetch(manifestLink.href)
            .then(r => r.json())
            .then(data => {
                results.manifestData = data;
                console.log('✅ Manifest数据:', data);
                
                // 检查图标
                const missingIcons = [];
                data.icons?.forEach(icon => {
                    fetch(icon.src, { method: 'HEAD' }).catch(() => {
                        missingIcons.push(icon.src);
                    });
                });
                
                if (missingIcons.length > 0) {
                    console.warn('⚠️ 缺失的图标:', missingIcons);
                }
            })
            .catch(err => {
                console.error('❌ 无法加载Manifest:', err);
            });
    }
    
    // 输出结果
    console.log('\n--- 基础检查 ---');
    console.log('协议:', results.protocol, results.isSecure ? '✅' : '❌ (需要HTTPS)');
    console.log('主机名:', results.hostname);
    console.log('Service Worker支持:', results.hasServiceWorker ? '✅' : '❌');
    console.log('Manifest链接:', results.hasManifest ? '✅' : '❌');
    console.log('独立模式运行:', results.isStandalone ? '✅ (已安装)' : '❌ (未安装)');
    console.log('安装提示可用:', results.hasBeforeInstallPrompt ? '✅' : '❌');
    
    // 给出建议
    console.log('\n--- 建议 ---');
    if (!results.isSecure) {
        console.log('❌ 请使用HTTPS访问或在localhost测试');
    }
    if (!results.hasServiceWorker) {
        console.log('❌ 浏览器不支持Service Worker，请更新浏览器');
    }
    if (!results.hasManifest) {
        console.log('❌ 未找到manifest.json链接，请检查HTML头部');
    }
    if (!results.hasBeforeInstallPrompt && !results.isStandalone) {
        console.log('⚠️ beforeinstallprompt事件未触发，可能原因:');
        console.log('   1. 已经安装过PWA');
        console.log('   2. 不满足PWA安装条件');
        console.log('   3. 浏览器不支持PWA安装');
    }
    if (results.isStandalone) {
        console.log('✅ PWA已安装且正在独立模式运行');
    }
    
    console.log('\n=== 检查完成 ===\n');
    
    return results;
};

// 添加快捷调试命令
window.debugPWA = {
    check: window.checkPWA,
    
    // 查看缓存
    async listCaches() {
        const cacheNames = await caches.keys();
        console.log('📦 缓存列表:', cacheNames);
        
        for (const name of cacheNames) {
            const cache = await caches.open(name);
            const keys = await cache.keys();
            console.log(`\n缓存 "${name}" (${keys.length}项):`);
            keys.forEach(req => console.log('  -', req.url));
        }
    },
    
    // 清除所有缓存
    async clearCaches() {
        const cacheNames = await caches.keys();
        await Promise.all(cacheNames.map(name => caches.delete(name)));
        console.log('✅ 已清除所有缓存');
    },
    
    // 重新注册SW
    async reregisterSW() {
        const reg = await navigator.serviceWorker.getRegistration();
        if (reg) {
            await reg.unregister();
            console.log('✅ 已注销Service Worker');
        }
        window.location.reload();
    },
    
    // 强制更新SW
    async updateSW() {
        const reg = await navigator.serviceWorker.getRegistration();
        if (reg) {
            await reg.update();
            console.log('✅ 已触发Service Worker更新');
        } else {
            console.log('❌ Service Worker未注册');
        }
    }
};

console.log('💡 PWA调试工具已加载');
console.log('📝 使用方法:');
console.log('   checkPWA()           - 检查PWA状态');
console.log('   debugPWA.listCaches()    - 查看缓存');
console.log('   debugPWA.clearCaches()   - 清除缓存');
console.log('   debugPWA.updateSW()      - 更新Service Worker');
console.log('   debugPWA.reregisterSW()  - 重新注册Service Worker');
