/**
 * 请求认证工具 - 使用HMAC签名 + 动态密钥
 * 密钥定期轮换，旧密钥在宽限期内仍然有效
 */

// API密钥缓存
let apiKeyCache = {
    key: null,
    expiresAt: null,
    lastFetchTime: null
};

// 密钥缓存有效期（秒）- 提前5分钟刷新
const KEY_CACHE_DURATION = 3300; // 55分钟

/**
 * 获取API密钥（带缓存）
 */
async function getApiKey() {
    const now = Math.floor(Date.now() / 1000);
    
    // 如果缓存有效，直接返回
    if (apiKeyCache.key && apiKeyCache.expiresAt && apiKeyCache.expiresAt > now + 300) {
        return apiKeyCache.key;
    }
    
    // 如果缓存太旧，重新获取
    if (apiKeyCache.lastFetchTime && (now - apiKeyCache.lastFetchTime) > KEY_CACHE_DURATION) {
        apiKeyCache.key = null;
        apiKeyCache.expiresAt = null;
    }
    
    // 从服务器获取新密钥（这里我们需要一个API端点）
    try {
        const response = await fetch('/api/auth/api-key', {
            method: 'GET',
            credentials: 'same-origin'
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.key) {
                apiKeyCache.key = data.key;
                apiKeyCache.expiresAt = data.expires_at || (now + 3600);
                apiKeyCache.lastFetchTime = now;
                return apiKeyCache.key;
            }
        }
    } catch (error) {
        console.warn('获取API密钥失败，使用默认密钥:', error);
    }
    
    // 如果获取失败，返回缓存的密钥（如果有）
    if (apiKeyCache.key) {
        return apiKeyCache.key;
    }
    
    // 最后的后备方案（不应到达这里，但如果到达了，使用一个默认值）
    return null;
}

/**
 * 生成HMAC-SHA256签名
 */
async function generateSignature(key, timestamp, params) {
    // 将参数字典转换为排序后的字符串
    const paramStr = Object.keys(params)
        .sort()
        .map(k => `${k}=${params[k]}`)
        .join('&');
    
    // 组合：时间戳 + 参数字符串
    const signString = `${timestamp}&${paramStr}`;
    
    // 使用Web Crypto API生成HMAC-SHA256签名
    if (window.crypto && window.crypto.subtle) {
        try {
            const encoder = new TextEncoder();
            const keyData = encoder.encode(key);
            const messageData = encoder.encode(signString);
            
            // 导入密钥
            const cryptoKey = await window.crypto.subtle.importKey(
                'raw',
                keyData,
                { name: 'HMAC', hash: 'SHA-256' },
                false,
                ['sign']
            );
            
            // 生成签名
            const signature = await window.crypto.subtle.sign('HMAC', cryptoKey, messageData);
            
            // 转换为hex字符串
            const hashArray = Array.from(new Uint8Array(signature));
            return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
        } catch (error) {
            console.error('HMAC签名生成失败:', error);
            throw error;
        }
    } else {
        // 不支持Web Crypto API的浏览器（极少数）
        throw new Error('浏览器不支持HMAC签名');
    }
}

/**
 * 生成普通请求（已移除HMAC签名）
 * @param {string} url - 请求URL
 * @param {object} params - 请求参数
 * @param {object} options - 额外的fetch选项
 * @returns {Promise} fetch响应
 */
async function authenticatedFetch(url, params = {}, options = {}) {
    // 构建完整URL
    const paramStr = Object.keys(params)
        .map(k => `${encodeURIComponent(k)}=${encodeURIComponent(params[k])}`)
        .join('&');
    const fullUrl = paramStr ? `${url}?${paramStr}` : url;
    
    // 直接发送请求，不再添加签名
    const response = await fetch(fullUrl, {
        method: 'GET',
        credentials: 'same-origin',
        ...options
    });
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({ error: '请求失败' }));
        throw new Error(error.error || `请求失败 (${response.status})`);
    }
    
    return response.json();
}

// 导出函数
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { authenticatedFetch, getApiKey };
}

