/**
 * PWA 安装提示和管理
 */

class PWAInstall {
    constructor() {
        this.deferredPrompt = null;
        this.isInstalled = false;
        this.init();
    }

    init() {
        // 检查PWA支持
        this.checkPWASupport();
        
        // 检查是否已经安装
        this.checkIfInstalled();
        
        // 监听 beforeinstallprompt 事件
        window.addEventListener('beforeinstallprompt', (e) => {
            console.log('[PWA] beforeinstallprompt 事件触发');
            // 阻止默认的安装提示
            e.preventDefault();
            // 保存事件，稍后使用
            this.deferredPrompt = e;
            // 显示自定义安装提示
            this.showInstallBanner();
        });

        // 监听 appinstalled 事件
        window.addEventListener('appinstalled', () => {
            console.log('[PWA] PWA 已安装');
            this.isInstalled = true;
            this.hideInstallBanner();
            this.deferredPrompt = null;
            // 显示安装成功提示
            this.showInstalledMessage();
        });

        // 检查是否在独立模式下运行（已安装）
        if (window.matchMedia('(display-mode: standalone)').matches || 
            window.navigator.standalone) {
            this.isInstalled = true;
            console.log('[PWA] PWA 已安装（独立模式）');
        }
    }
    
    /**
     * 检查PWA支持
     */
    checkPWASupport() {
        const issues = [];
        
        // 检查HTTPS
        if (location.protocol !== 'https:' && location.hostname !== 'localhost') {
            issues.push('⚠️ PWA需要HTTPS支持（当前: ' + location.protocol + '）');
        }
        
        // 检查Service Worker支持
        if (!('serviceWorker' in navigator)) {
            issues.push('⚠️ 浏览器不支持Service Worker');
        }
        
        // 检查manifest支持
        if (!document.querySelector('link[rel="manifest"]')) {
            issues.push('⚠️ 未找到manifest.json链接');
        }
        
        if (issues.length > 0) {
            console.warn('[PWA] 支持检查问题:', issues.join('; '));
        } else {
            console.log('[PWA] ✅ PWA支持检查通过');
        }
        
        return issues.length === 0;
    }

    checkIfInstalled() {
        // 检查是否在独立模式下运行
        if (window.matchMedia('(display-mode: standalone)').matches) {
            this.isInstalled = true;
            return true;
        }
        
        // iOS Safari 检查
        if (window.navigator.standalone === true) {
            this.isInstalled = true;
            return true;
        }
        
        return false;
    }

    showInstallBanner() {
        // 如果已经安装，不显示
        if (this.isInstalled) {
            return;
        }

        // 检查是否已经显示过提示（24小时内）
        const lastShown = localStorage.getItem('pwa-install-banner-shown');
        const now = Date.now();
        if (lastShown && (now - parseInt(lastShown)) < 24 * 60 * 60 * 1000) {
            return;
        }

        // 创建安装提示横幅
        const banner = document.createElement('div');
        banner.id = 'pwa-install-banner';
        banner.innerHTML = `
            <div class="pwa-install-content">
                <div class="pwa-install-icon">📱</div>
                <div class="pwa-install-text">
                    <div class="pwa-install-title">安装到手机</div>
                    <div class="pwa-install-desc">将应用添加到主屏幕，随时访问</div>
                </div>
                <button class="pwa-install-btn" id="pwa-install-button">安装</button>
                <button class="pwa-install-close" id="pwa-install-close">×</button>
            </div>
        `;
        
        document.body.appendChild(banner);

        // 添加样式
        if (!document.getElementById('pwa-install-style')) {
            const style = document.createElement('style');
            style.id = 'pwa-install-style';
            style.textContent = `
                #pwa-install-banner {
                    position: fixed;
                    bottom: 80px;
                    left: 50%;
                    transform: translateX(-50%);
                    width: calc(100% - 20px);
                    max-width: 400px;
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
                    z-index: 10000;
                    padding: 12px;
                    animation: slideUp 0.3s ease;
                }
                
                @keyframes slideUp {
                    from {
                        transform: translateX(-50%) translateY(100%);
                        opacity: 0;
                    }
                    to {
                        transform: translateX(-50%) translateY(0);
                        opacity: 1;
                    }
                }
                
                .pwa-install-content {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                }
                
                .pwa-install-icon {
                    font-size: 32px;
                    flex-shrink: 0;
                }
                
                .pwa-install-text {
                    flex: 1;
                    min-width: 0;
                }
                
                .pwa-install-title {
                    font-size: 14px;
                    font-weight: 600;
                    color: #333;
                    margin-bottom: 2px;
                }
                
                .pwa-install-desc {
                    font-size: 12px;
                    color: #666;
                }
                
                .pwa-install-btn {
                    padding: 8px 16px;
                    background: #4a90e2;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: background 0.2s;
                    flex-shrink: 0;
                }
                
                .pwa-install-btn:hover {
                    background: #357abd;
                }
                
                .pwa-install-close {
                    width: 24px;
                    height: 24px;
                    border-radius: 50%;
                    border: none;
                    background: #f0f0f0;
                    color: #666;
                    font-size: 18px;
                    line-height: 1;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    flex-shrink: 0;
                    padding: 0;
                }
                
                .pwa-install-close:hover {
                    background: #e0e0e0;
                }
                
                @media (max-width: 480px) {
                    #pwa-install-banner {
                        bottom: 70px;
                        width: calc(100% - 16px);
                        padding: 10px;
                    }
                    
                    .pwa-install-icon {
                        font-size: 28px;
                    }
                    
                    .pwa-install-title {
                        font-size: 13px;
                    }
                    
                    .pwa-install-desc {
                        font-size: 11px;
                    }
                    
                    .pwa-install-btn {
                        padding: 6px 12px;
                        font-size: 13px;
                    }
                }
            `;
            document.head.appendChild(style);
        }

        // 绑定安装按钮事件
        const installBtn = document.getElementById('pwa-install-button');
        if (installBtn) {
            installBtn.addEventListener('click', () => {
                this.install();
            });
        }

        // 绑定关闭按钮事件
        const closeBtn = document.getElementById('pwa-install-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                this.hideInstallBanner();
            });
        }

        // 记录显示时间
        localStorage.setItem('pwa-install-banner-shown', now.toString());
    }

    hideInstallBanner() {
        const banner = document.getElementById('pwa-install-banner');
        if (banner) {
            banner.style.animation = 'slideDown 0.3s ease';
            setTimeout(() => {
                banner.remove();
            }, 300);
        }
    }

    async install() {
        if (!this.deferredPrompt) {
            // 如果没有 deferredPrompt，显示手动安装说明
            this.showManualInstallInstructions();
            this.hideInstallBanner();
            return;
        }

        // 显示安装提示
        this.deferredPrompt.prompt();

        // 等待用户响应
        const { outcome } = await this.deferredPrompt.userChoice;
        console.log('用户选择:', outcome);

        // 清除 deferredPrompt
        this.deferredPrompt = null;
        this.hideInstallBanner();

        if (outcome === 'accepted') {
            console.log('用户同意安装');
        } else {
            console.log('用户拒绝安装');
        }
    }

    showManualInstallInstructions() {
        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
        const isAndroid = /Android/.test(navigator.userAgent);
        
        let instructions = '';
        
        if (isIOS) {
            instructions = `
                <div style="text-align: center; padding: 20px;">
                    <h3>📱 iOS 安装说明</h3>
                    <ol style="text-align: left; display: inline-block; margin-top: 15px;">
                        <li>点击底部工具栏的 <strong>分享</strong> 按钮（□↑）</li>
                        <li>向下滚动，找到并点击 <strong>"添加到主屏幕"</strong></li>
                        <li>点击右上角的 <strong>"添加"</strong> 按钮</li>
                    </ol>
                </div>
            `;
        } else if (isAndroid) {
            instructions = `
                <div style="text-align: center; padding: 20px;">
                    <h3>📱 Android 安装说明</h3>
                    <ol style="text-align: left; display: inline-block; margin-top: 15px;">
                        <li>点击浏览器右上角的 <strong>菜单</strong> 按钮（⋮）</li>
                        <li>选择 <strong>"添加到主屏幕"</strong> 或 <strong>"安装应用"</strong></li>
                        <li>确认安装</li>
                    </ol>
                </div>
            `;
        } else {
            instructions = `
                <div style="text-align: center; padding: 20px;">
                    <h3>📱 安装说明</h3>
                    <p>请使用手机浏览器访问本网站</p>
                    <p>然后在浏览器菜单中选择"添加到主屏幕"</p>
                </div>
            `;
        }
        
        alert(instructions.replace(/<[^>]*>/g, '')); // 简单的文本提示
    }

    showInstalledMessage() {
        // 显示安装成功提示（可选）
        const message = document.createElement('div');
        message.style.cssText = `
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: #4a90e2;
            color: white;
            padding: 12px 24px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            z-index: 10001;
            animation: fadeInOut 3s ease;
        `;
        message.textContent = '✅ 应用已成功安装到主屏幕！';
        document.body.appendChild(message);
        
        setTimeout(() => {
            message.remove();
        }, 3000);
    }
}

// 初始化 PWA 安装管理器
if ('serviceWorker' in navigator) {
    // 注册 Service Worker
    window.addEventListener('load', () => {
        const swPath = '/static/sw.js';
        console.log('[PWA] 开始注册Service Worker:', swPath);
        
        navigator.serviceWorker.register(swPath)
            .then((registration) => {
                console.log('[PWA] ✅ Service Worker 注册成功:', registration.scope);
                
                // 检查更新
                registration.addEventListener('updatefound', () => {
                    const newWorker = registration.installing;
                    console.log('[PWA] 发现Service Worker更新');
                    
                    newWorker.addEventListener('statechange', () => {
                        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                            // 有新版本可用
                            console.log('[PWA] 有新版本可用，请刷新页面');
                            // 可以显示提示让用户刷新
                            if (window.playerToastManager) {
                                window.playerToastManager.show('发现新版本，请刷新页面', 5000);
                            }
                        }
                    });
                });
                
                // 定期检查更新（每小时）
                setInterval(() => {
                    registration.update().catch(err => {
                        console.warn('[PWA] Service Worker更新检查失败:', err);
                    });
                }, 60 * 60 * 1000);
            })
            .catch((error) => {
                console.error('[PWA] ❌ Service Worker 注册失败:', error);
                console.error('[PWA] 请检查:', [
                    '1. 是否使用HTTPS（或localhost）',
                    '2. sw.js文件是否存在',
                    '3. 服务器MIME类型配置是否正确'
                ].join('\n   '));
            });
    });
} else {
    console.warn('[PWA] ⚠️ 浏览器不支持Service Worker');
}

// 创建全局实例
if (typeof window.pwaInstall === 'undefined') {
    window.pwaInstall = new PWAInstall();
}



