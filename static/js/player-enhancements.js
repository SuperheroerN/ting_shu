/**
 * 播放器增强模块
 * 为播放器添加加载状态提示、错误重试、智能预加载等功能
 */

(function() {
    'use strict';
    
    const { CONSTANTS, ErrorHandler } = window.PlayerUtils;
    
    /**
     * 加载状态管理器
     */
    class LoadingStateManager {
        constructor() {
            this.isLoading = false;
            this.loadStartTime = 0;
            this.indicator = null;
            this.createIndicator();
        }
        
        /**
         * 创建加载指示器
         */
        createIndicator() {
            if (this.indicator) return;
            
            this.indicator = document.createElement('div');
            this.indicator.className = 'player-loading-indicator';
            this.indicator.innerHTML = `
                <div class="loading-spinner"></div>
                <div class="loading-text">加载中...</div>
            `;
            this.indicator.style.cssText = `
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: rgba(0, 0, 0, 0.8);
                color: white;
                padding: 20px 30px;
                border-radius: 12px;
                display: none;
                align-items: center;
                gap: 15px;
                z-index: 10000;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            `;
            
            // 添加样式
            const style = document.createElement('style');
            style.textContent = `
                .loading-spinner {
                    width: 24px;
                    height: 24px;
                    border: 3px solid rgba(255, 255, 255, 0.3);
                    border-top-color: white;
                    border-radius: 50%;
                    animation: spin 0.8s linear infinite;
                }
                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
                .player-loading-indicator {
                    display: none;
                }
                .player-loading-indicator.active {
                    display: flex !important;
                }
            `;
            document.head.appendChild(style);
            document.body.appendChild(this.indicator);
        }
        
        /**
         * 显示加载状态
         */
        show(text = '加载中...') {
            this.isLoading = true;
            this.loadStartTime = Date.now();
            if (this.indicator) {
                const textEl = this.indicator.querySelector('.loading-text');
                if (textEl) textEl.textContent = text;
                this.indicator.classList.add('active');
            }
        }
        
        /**
         * 隐藏加载状态
         */
        hide() {
            this.isLoading = false;
            const loadTime = Date.now() - this.loadStartTime;
            console.log(`加载完成，耗时: ${loadTime}ms`);
            
            if (this.indicator) {
                this.indicator.classList.remove('active');
            }
        }
        
        /**
         * 更新加载文本
         */
        updateText(text) {
            if (this.indicator) {
                const textEl = this.indicator.querySelector('.loading-text');
                if (textEl) textEl.textContent = text;
            }
        }
    }
    
    /**
     * 进度提示管理器
     */
    class ProgressToastManager {
        constructor() {
            this.toast = null;
            this.hideTimer = null;
        }
        
        /**
         * 显示进度提示
         */
        show(message, duration = 2000) {
            // 如果已存在，先移除
            if (this.toast) {
                this.toast.remove();
                clearTimeout(this.hideTimer);
            }
            
            this.toast = document.createElement('div');
            this.toast.className = 'player-progress-toast';
            this.toast.textContent = message;
            this.toast.style.cssText = `
                position: fixed;
                bottom: 100px;
                left: 50%;
                transform: translateX(-50%);
                background: rgba(0, 0, 0, 0.8);
                color: white;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 14px;
                z-index: 10001;
                animation: slideUp 0.3s ease;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            `;
            
            // 添加动画
            if (!document.getElementById('progress-toast-style')) {
                const style = document.createElement('style');
                style.id = 'progress-toast-style';
                style.textContent = `
                    @keyframes slideUp {
                        from {
                            opacity: 0;
                            transform: translate(-50%, 20px);
                        }
                        to {
                            opacity: 1;
                            transform: translate(-50%, 0);
                        }
                    }
                    @keyframes slideDown {
                        from {
                            opacity: 1;
                            transform: translate(-50%, 0);
                        }
                        to {
                            opacity: 0;
                            transform: translate(-50%, 20px);
                        }
                    }
                `;
                document.head.appendChild(style);
            }
            
            document.body.appendChild(this.toast);
            
            // 自动隐藏
            this.hideTimer = setTimeout(() => {
                if (this.toast) {
                    this.toast.style.animation = 'slideDown 0.3s ease';
                    setTimeout(() => {
                        if (this.toast) {
                            this.toast.remove();
                            this.toast = null;
                        }
                    }, 300);
                }
            }, duration);
        }
    }
    
    /**
     * 智能预加载管理器
     */
    class SmartPreloadManager {
        constructor() {
            this.preloadedChapters = new Set();
            this.preloadThreshold = CONSTANTS.PRELOAD_THRESHOLD;
        }
        
        /**
         * 检查是否需要预加载
         */
        shouldPreload(audio, nextChapterId) {
            if (!audio || !nextChapterId) return false;
            if (this.preloadedChapters.has(nextChapterId)) return false;
            
            const duration = audio.duration;
            const currentTime = audio.currentTime;
            
            if (!duration || isNaN(duration)) return false;
            
            const progress = currentTime / duration;
            return progress >= this.preloadThreshold;
        }
        
        /**
         * 执行预加载
         */
        async preload(chapterId, fetchFunc) {
            if (this.preloadedChapters.has(chapterId)) {
                return;
            }
            
            console.log(`智能预加载: 开始预加载章节 ${chapterId}`);
            
            try {
                await fetchFunc(chapterId);
                this.preloadedChapters.add(chapterId);
                console.log(`智能预加载: 章节 ${chapterId} 预加载完成`);
            } catch (error) {
                console.error(`智能预加载: 章节 ${chapterId} 预加载失败`, error);
            }
        }
        
        /**
         * 清除预加载记录
         */
        clearPreloaded(chapterId) {
            this.preloadedChapters.delete(chapterId);
        }
        
        /**
         * 重置
         */
        reset() {
            this.preloadedChapters.clear();
        }
    }
    
    /**
     * 缓存统计面板
     */
    class CacheStatsPanel {
        constructor() {
            this.panel = null;
            this.isVisible = false;
        }
        
        /**
         * 创建统计面板
         */
        createPanel() {
            if (this.panel) return;
            
            this.panel = document.createElement('div');
            this.panel.className = 'cache-stats-panel';
            this.panel.style.cssText = `
                position: fixed;
                top: 60px;
                right: 10px;
                background: rgba(0, 0, 0, 0.85);
                color: white;
                padding: 15px;
                border-radius: 8px;
                font-size: 12px;
                font-family: monospace;
                z-index: 9999;
                display: none;
                min-width: 200px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            `;
            
            document.body.appendChild(this.panel);
        }
        
        /**
         * 更新统计数据
         */
        update(stats) {
            if (!this.panel) this.createPanel();
            
            this.panel.innerHTML = `
                <div style="font-weight: bold; margin-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.3); padding-bottom: 5px;">
                    📊 缓存统计
                </div>
                <div style="line-height: 1.8;">
                    <div>缓存大小: ${stats.cacheSize}/${stats.maxSize}</div>
                    <div>命中率: ${stats.hitRate}</div>
                    <div>命中次数: ${stats.hits}</div>
                    <div>未命中: ${stats.misses}</div>
                    <div>淘汰次数: ${stats.evictions}</div>
                </div>
            `;
        }
        
        /**
         * 切换显示/隐藏
         */
        toggle() {
            if (!this.panel) this.createPanel();
            
            this.isVisible = !this.isVisible;
            this.panel.style.display = this.isVisible ? 'block' : 'none';
            
            if (this.isVisible && window.audioCachePool) {
                this.update(window.audioCachePool.getStats());
            }
        }
    }
    
    // 导出增强功能
    window.PlayerEnhancements = {
        LoadingStateManager,
        ProgressToastManager,
        SmartPreloadManager,
        CacheStatsPanel
    };
    
    // 自动初始化全局实例
    window.playerLoadingManager = new LoadingStateManager();
    window.playerToastManager = new ProgressToastManager();
    window.smartPreloadManager = new SmartPreloadManager();
    window.cacheStatsPanel = new CacheStatsPanel();
    
    // 添加调试快捷键
    document.addEventListener('keydown', (e) => {
        // Ctrl+Shift+S 显示缓存统计
        if (e.ctrlKey && e.shiftKey && e.key === 'S') {
            window.cacheStatsPanel.toggle();
            if (window.cacheStatsPanel.isVisible && window.audioCachePool) {
                window.cacheStatsPanel.update(window.audioCachePool.getStats());
            }
        }
    });
    
    console.log('✅ 播放器增强模块已加载');
})();
