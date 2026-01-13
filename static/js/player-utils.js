/**
 * 播放器优化工具模块
 * 提供性能优化、错误处理、状态管理等通用功能
 */

// ==================== 常量定义 ====================
const PLAYER_CONSTANTS = {
    // 缓存配置
    CACHE_MAX_SIZE: 30,
    CACHE_STORAGE_KEY: 'audioCachePool',
    
    // 状态存储
    STATE_STORAGE_KEY: 'globalPlayerState',
    STATE_POSITION_KEY: 'globalPlayerPosition',
    STATE_EXPIRE_TIME: 3600000, // 1小时
    
    // 性能配置
    UI_UPDATE_INTERVAL: 500,
    PROGRESS_UPDATE_INTERVAL: 100,
    STORAGE_SAVE_DELAY: 1000,
    CLEANUP_INTERVAL: 300000, // 5分钟
    
    // 错误处理
    AUDIO_LOAD_TIMEOUT: 30000, // 30秒
    MAX_RETRY_COUNT: 3,
    RETRY_DELAY: 2000,
    
    // 预加载配置
    PRELOAD_THRESHOLD: 0.8, // 播放到80%时预加载下一章
    
    // 拖拽配置
    DRAG_MARGIN: {
        mobile: 8,
        desktop: 12
    },
    BOTTOM_NAV_HEIGHT: 60
};

// ==================== 性能优化工具 ====================

/**
 * 节流函数 - 限制函数执行频率
 */
function throttle(func, wait) {
    let timeout = null;
    let previous = 0;
    
    return function(...args) {
        const now = Date.now();
        const remaining = wait - (now - previous);
        
        if (remaining <= 0 || remaining > wait) {
            if (timeout) {
                clearTimeout(timeout);
                timeout = null;
            }
            previous = now;
            func.apply(this, args);
        } else if (!timeout) {
            timeout = setTimeout(() => {
                previous = Date.now();
                timeout = null;
                func.apply(this, args);
            }, remaining);
        }
    };
}

/**
 * 防抖函数 - 延迟执行，多次调用只执行最后一次
 */
function debounce(func, wait, immediate = false) {
    let timeout;
    
    return function(...args) {
        const later = () => {
            timeout = null;
            if (!immediate) func.apply(this, args);
        };
        
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        
        if (callNow) func.apply(this, args);
    };
}

/**
 * DOM元素缓存类
 */
class DOMCache {
    constructor() {
        this.cache = new Map();
    }
    
    get(selector, context = document) {
        const key = `${selector}:${context === document ? 'doc' : 'ctx'}`;
        if (!this.cache.has(key)) {
            const element = context.querySelector(selector);
            if (element) {
                this.cache.set(key, element);
            }
            return element;
        }
        return this.cache.get(key);
    }
    
    getAll(selector, context = document) {
        return context.querySelectorAll(selector);
    }
    
    clear() {
        this.cache.clear();
    }
    
    remove(selector) {
        this.cache.delete(selector);
    }
}

// ==================== 存储优化工具 ====================

/**
 * 批量存储管理器 - 延迟批量写入localStorage
 */
class BatchStorage {
    constructor(delay = PLAYER_CONSTANTS.STORAGE_SAVE_DELAY) {
        this.pending = new Map();
        this.delay = delay;
        this.saveTimer = null;
    }
    
    /**
     * 设置项（延迟保存）
     */
    set(key, value) {
        this.pending.set(key, value);
        this.scheduleSave();
    }
    
    /**
     * 立即获取（优先从待保存队列获取）
     */
    get(key) {
        if (this.pending.has(key)) {
            return this.pending.get(key);
        }
        try {
            const value = localStorage.getItem(key);
            return value ? JSON.parse(value) : null;
        } catch (e) {
            console.error('BatchStorage get error:', e);
            return null;
        }
    }
    
    /**
     * 移除项
     */
    remove(key) {
        this.pending.set(key, null);
        this.scheduleSave();
    }
    
    /**
     * 调度保存
     */
    scheduleSave() {
        if (this.saveTimer) {
            clearTimeout(this.saveTimer);
        }
        this.saveTimer = setTimeout(() => this.flush(), this.delay);
    }
    
    /**
     * 立即刷新到localStorage
     */
    flush() {
        if (this.pending.size === 0) return;
        
        try {
            this.pending.forEach((value, key) => {
                if (value === null) {
                    localStorage.removeItem(key);
                } else {
                    localStorage.setItem(key, JSON.stringify(value));
                }
            });
            this.pending.clear();
        } catch (e) {
            console.error('BatchStorage flush error:', e);
        }
    }
}

// ==================== 错误处理工具 ====================

/**
 * 音频加载器 - 支持超时和重试
 */
class AudioLoader {
    constructor(maxRetries = PLAYER_CONSTANTS.MAX_RETRY_COUNT) {
        this.maxRetries = maxRetries;
        this.currentRetry = 0;
        this.abortController = null;
    }
    
    /**
     * 加载音频URL（带超时和重试）
     */
    async loadWithRetry(fetchFunc, ...args) {
        this.currentRetry = 0;
        
        while (this.currentRetry < this.maxRetries) {
            try {
                return await this.loadWithTimeout(fetchFunc, ...args);
            } catch (error) {
                this.currentRetry++;
                console.warn(`音频加载失败 (尝试 ${this.currentRetry}/${this.maxRetries}):`, error);
                
                if (this.currentRetry >= this.maxRetries) {
                    throw new Error(`音频加载失败，已重试${this.maxRetries}次`);
                }
                
                // 等待后重试
                await this.delay(PLAYER_CONSTANTS.RETRY_DELAY * this.currentRetry);
            }
        }
    }
    
    /**
     * 带超时的加载
     */
    async loadWithTimeout(fetchFunc, ...args) {
        this.abortController = new AbortController();
        const timeoutId = setTimeout(
            () => this.abortController.abort(),
            PLAYER_CONSTANTS.AUDIO_LOAD_TIMEOUT
        );
        
        try {
            const result = await fetchFunc(...args, { signal: this.abortController.signal });
            clearTimeout(timeoutId);
            return result;
        } catch (error) {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                throw new Error('音频加载超时');
            }
            throw error;
        }
    }
    
    /**
     * 取消加载
     */
    abort() {
        if (this.abortController) {
            this.abortController.abort();
        }
    }
    
    /**
     * 延迟函数
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

/**
 * 错误处理器 - 统一错误处理和用户提示
 */
class ErrorHandler {
    /**
     * 处理音频错误
     */
    static handleAudioError(error, context = {}) {
        console.error('音频错误:', error, context);
        
        // 根据错误类型提供用户友好的提示
        let userMessage = '音频加载失败';
        
        if (error.message?.includes('超时')) {
            userMessage = '音频加载超时，请检查网络连接';
        } else if (error.message?.includes('网络')) {
            userMessage = '网络连接失败，请检查网络';
        } else if (error.message?.includes('格式')) {
            userMessage = '音频格式不支持';
        }
        
        this.showToast(userMessage, 'error');
        
        // 记录错误到控制台（生产环境可发送到服务器）
        this.logError(error, context);
    }
    
    /**
     * 显示Toast提示
     */
    static showToast(message, type = 'info') {
        // 简单的Toast实现，可以替换为更好的UI库
        const toast = document.createElement('div');
        toast.className = `player-toast player-toast-${type}`;
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: ${type === 'error' ? '#f44336' : '#4CAF50'};
            color: white;
            padding: 12px 24px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 100000;
            animation: slideDown 0.3s ease;
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'slideUp 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
    
    /**
     * 记录错误
     */
    static logError(error, context) {
        const errorLog = {
            message: error.message,
            stack: error.stack,
            context: context,
            timestamp: new Date().toISOString(),
            userAgent: navigator.userAgent
        };
        
        // 可以发送到服务器或存储到localStorage
        console.error('Error Log:', errorLog);
    }
}

// ==================== 状态管理工具 ====================

/**
 * 状态管理器 - 统一管理播放器状态
 */
class StateManager {
    constructor() {
        this.listeners = new Map();
        this.state = {};
    }
    
    /**
     * 设置状态
     */
    setState(key, value) {
        const oldValue = this.state[key];
        if (oldValue === value) return;
        
        this.state[key] = value;
        this.notify(key, value, oldValue);
    }
    
    /**
     * 获取状态
     */
    getState(key) {
        return this.state[key];
    }
    
    /**
     * 订阅状态变化
     */
    subscribe(key, callback) {
        if (!this.listeners.has(key)) {
            this.listeners.set(key, []);
        }
        this.listeners.get(key).push(callback);
        
        // 返回取消订阅函数
        return () => {
            const callbacks = this.listeners.get(key);
            const index = callbacks.indexOf(callback);
            if (index > -1) {
                callbacks.splice(index, 1);
            }
        };
    }
    
    /**
     * 通知订阅者
     */
    notify(key, newValue, oldValue) {
        const callbacks = this.listeners.get(key);
        if (callbacks) {
            callbacks.forEach(callback => callback(newValue, oldValue));
        }
    }
}

// ==================== URL验证工具 ====================

/**
 * URL验证器
 */
class URLValidator {
    /**
     * 检查是否为有效音频URL
     */
    static isValidAudioUrl(url) {
        if (!url || typeof url !== 'string') return false;
        
        // 检查是否包含音频文件扩展名
        const hasAudioExt = /\.(mp3|m4a|aac|ogg|wav|flac|webm)(\?|$)/i.test(url);
        
        // 检查是否是HTTP(S)协议且不是播放器页面URL
        const isHttpUrl = url.startsWith('http') && !url.includes('/player/');
        
        return hasAudioExt || isHttpUrl;
    }
    
    /**
     * 检查是否为blob URL
     */
    static isBlobUrl(url) {
        return url?.startsWith('blob:');
    }
}

// ==================== 导出 ====================
window.PlayerUtils = {
    CONSTANTS: PLAYER_CONSTANTS,
    throttle,
    debounce,
    DOMCache,
    BatchStorage,
    AudioLoader,
    ErrorHandler,
    StateManager,
    URLValidator
};
