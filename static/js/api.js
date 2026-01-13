/**
 * API调用工具函数
 */

// API基础URL
const API_BASE = '';

// 登录缓存配置
const AUTH_CACHE_KEY = 'authCredentials';
const AUTH_CACHE_MAX_AGE = 7 * 24 * 60 * 60 * 1000; // 7天

function cacheAuthCredentials(username, password) {
    try {
        const payload = {
            username,
            password,
            savedAt: Date.now()
        };
        localStorage.setItem(AUTH_CACHE_KEY, btoa(JSON.stringify(payload)));
    } catch (e) {
        console.warn('缓存登录凭据失败:', e);
    }
}

function getCachedAuthCredentials() {
    try {
        const raw = localStorage.getItem(AUTH_CACHE_KEY);
        if (!raw) return null;
        const decoded = JSON.parse(atob(raw));
        if (!decoded || !decoded.username || !decoded.password) {
            clearCachedAuthCredentials();
            return null;
        }
        if (decoded.savedAt && Date.now() - decoded.savedAt > AUTH_CACHE_MAX_AGE) {
            clearCachedAuthCredentials();
            return null;
        }
        return decoded;
    } catch (e) {
        console.warn('读取缓存凭据失败，已清除:', e);
        clearCachedAuthCredentials();
        return null;
    }
}

function clearCachedAuthCredentials() {
    try {
        localStorage.removeItem(AUTH_CACHE_KEY);
    } catch (e) {
        console.warn('清除缓存凭据失败:', e);
    }
}

async function tryAutoLoginFromCache() {
    const cached = getCachedAuthCredentials();
    if (!cached) return { success: false, message: 'no-cache' };
    try {
        await AuthAPI.login(cached.username, cached.password, { remember: true, silent: true });
        return { success: true };
    } catch (error) {
        clearCachedAuthCredentials();
        return { success: false, error };
    }
}

/**
 * 通用API请求函数
 */
async function apiRequest(url, options = {}) {
    try {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'same-origin' // 包含cookies
        };
        
        const response = await fetch(url, { ...defaultOptions, ...options });
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || '请求失败');
        }
        
        return data;
    } catch (error) {
        console.error('API请求错误:', error);
        throw error;
    }
}

/**
 * 用户认证相关API
 */
const AuthAPI = {
    // 注册
    register: async (username, password, options = {}) => {
        const response = await apiRequest('/api/auth/register', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });
        const result = {
            success: response.success,
            message: response.message,
            user: response.data?.user
        };
        if (options.remember !== false) {
            cacheAuthCredentials(username, password);
        }
        return result;
    },
    
    // 登录
    login: async (username, password, options = {}) => {
        // 生成时间戳和HMAC签名（使用与请求认证相同的动态密钥）
        const timestamp = Math.floor(Date.now() / 1000).toString();
        let signature = null;
        try {
            if (typeof getApiKey === 'function' && typeof generateSignature === 'function') {
                const key = await getApiKey();
                if (key) {
                    signature = await generateSignature(key, timestamp, { username, password });
                }
            }
        } catch (e) {
            console.warn('生成登录签名失败:', e);
        }

        const payload = { username, password };
        if (signature) {
            payload.timestamp = timestamp;
            payload.signature = signature;
        }

        const response = await apiRequest('/api/auth/login', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
        const result = {
            success: response.success,
            message: response.message,
            user: response.data?.user
        };
        if (options.remember !== false) {
            cacheAuthCredentials(username, password);
        }
        return result;
    },
    
    // 退出
    logout: async (options = {}) => {
        const response = await apiRequest('/api/auth/logout', {
            method: 'POST'
        });
        const result = {
            success: response.success,
            message: response.message
        };
        if (options.clearCache !== false) {
            clearCachedAuthCredentials();
        }
        return result;
    },
    
    // 获取登录状态
    getStatus: async () => {
        return apiRequest('/api/auth/status');
    },

    // 使用本地缓存自动登录
    autoLoginFromCache: async () => {
        return tryAutoLoginFromCache();
    },

    // 获取应用级认证配置（如是否开放注册）
    getAuthConfig: async () => {
        try {
            const resp = await apiRequest('/admin/api/app-config');
            return resp.config || {};
        } catch (e) {
            console.warn('获取应用配置失败:', e);
            return {};
        }
    }
};

// 暴露缓存工具（给其他脚本使用）
if (typeof window !== 'undefined') {
    window.AuthCache = {
        cacheAuthCredentials,
        getCachedAuthCredentials,
        clearCachedAuthCredentials,
        tryAutoLoginFromCache
    };
}

/**
 * 书架相关API（需要登录）
 */
const BookshelfAPI = {
    // 获取书架
    get: async () => {
        try {
            const response = await apiRequest('/api/bookshelf');
            // API响应结构为 { success: true, data: { books: [...] }, timestamp: "..." }
            // 所以我们需要返回 books 数组
            return { books: response.data?.books || [] };
        } catch (error) {
            // 如果未登录，返回空数组（使用localStorage）
            if (error.message.includes('请先登录') || error.message.includes('401')) {
                return { books: getLocalBookshelf() };
            }
            throw error;
        }
    },
    
    // 添加到书架
    add: async (bookData) => {
        try {
            const response = await apiRequest('/api/bookshelf', {
                method: 'POST',
                body: JSON.stringify(bookData)
            });
            // API响应结构为 { success: true, data: {...}, message: "...", timestamp: "..." }
            // 返回完整的响应数据
            const result = {
                success: response.success,
                message: response.message,
                book: response.data?.book || bookData
            };
            // 如果已登录，同时更新本地缓存（保持同步）
            addToLocalBookshelf(bookData);
            return result;
        } catch (error) {
            // 如果未登录，使用localStorage
            if (error.message.includes('请先登录') || error.message.includes('401')) {
                addToLocalBookshelf(bookData);
                return { success: true, message: '已加入书架（本地）' };
            }
            throw error;
        }
    },
    
    // 从书架移除
    remove: async (bookId, interface) => {
        try {
            // 先尝试删除服务器数据（如果已登录）
            const response = await apiRequest('/api/bookshelf', {
                method: 'DELETE',
                body: JSON.stringify({ book_id: bookId, interface })
            });
            const result = {
                success: response.success,
                message: response.message
            };
            // 如果成功，同时删除本地数据（保持同步）
            removeFromLocalBookshelf(bookId, interface);
            return result;
        } catch (error) {
            // 如果未登录，使用localStorage
            if (error.message.includes('请先登录') || error.message.includes('401')) {
                removeFromLocalBookshelf(bookId, interface);
                return { success: true, message: '已从书架移除（本地）' };
            }
            throw error;
        }
    },
    
    // 检查是否在书架中
    check: async (bookId, interface) => {
        try {
            const data = await apiRequest(`/api/bookshelf/check?book_id=${encodeURIComponent(bookId)}&interface=${encodeURIComponent(interface)}`);
            return data.in_bookshelf;
        } catch (error) {
            // 如果未登录，使用localStorage
            if (error.message.includes('请先登录') || error.message.includes('401')) {
                return isInLocalBookshelf(bookId, interface);
            }
            return false;
        }
    },
    
    // 同步本地书架到服务器（登录后调用）
    sync: async () => {
        try {
            const localBookshelf = getLocalBookshelf();
            if (!localBookshelf || localBookshelf.length === 0) {
                // 即使本地没有数据，也获取服务器数据并更新本地缓存
                const serverData = await BookshelfAPI.get();
                if (serverData && serverData.books && serverData.books.length > 0) {
                    saveLocalBookshelf(serverData.books);
                }
                return { success: true, message: '没有需要同步的书架数据', synced_count: 0 };
            }
            
            // 先上传本地数据到服务器
            const response = await apiRequest('/api/bookshelf/sync', {
                method: 'POST',
                body: JSON.stringify({ books: localBookshelf })
            });
            const result = {
                success: response.success,
                message: response.message,
                synced_count: response.synced_count || 0,
                skipped_count: response.skipped_count || 0,
                error_count: response.error_count || 0
            };
            
            // 同步成功后，获取服务器最新数据并更新本地缓存（保留数据）
            if (result.success) {
                const serverData = await BookshelfAPI.get();
                if (serverData && serverData.books) {
                    saveLocalBookshelf(serverData.books);
                    console.log('已更新本地书架缓存，共', serverData.books.length, '本');
                }
            }
            
            return result;
        } catch (error) {
            console.error('同步书架失败:', error);
            throw error;
        }
    }
};

// localStorage 备用函数（未登录时使用）
function getLocalBookshelf() {
    const bookshelf = localStorage.getItem('bookshelf');
    return bookshelf ? JSON.parse(bookshelf) : [];
}

function saveLocalBookshelf(bookshelf) {
    localStorage.setItem('bookshelf', JSON.stringify(bookshelf));
}

function addToLocalBookshelf(bookData) {
    const bookshelf = getLocalBookshelf();
    const bookKey = `${bookData.book_id}_${bookData.interface}`;
    const exists = bookshelf.some(book => `${book.book_id}_${book.interface}` === bookKey);
    if (!exists) {
        bookshelf.push(bookData);
        saveLocalBookshelf(bookshelf);
    }
}

function removeFromLocalBookshelf(bookId, interface) {
    const bookshelf = getLocalBookshelf();
    const filtered = bookshelf.filter(book => 
        !(book.book_id == bookId && book.interface == interface)
    );
    saveLocalBookshelf(filtered);
}

function isInLocalBookshelf(bookId, interface) {
    const bookshelf = getLocalBookshelf();
    return bookshelf.some(book => 
        book.book_id == bookId && book.interface == interface
    );
}

/**
 * 播放历史相关API（需要登录）
 */
const HistoryAPI = {
    // 获取历史记录（合并数据库和本地数据）
    get: async (limit = 100) => {
        try {
            // 先尝试从数据库获取
            const dbResponse = await apiRequest(`/api/history?limit=${limit}`);
            const dbHistory = dbResponse.data?.history || [];
            
            // 如果数据库有数据，直接返回数据库的数据
            if (dbHistory.length > 0) {
                return { history: dbHistory };
            }
            
            // 如果数据库为空，检查本地是否有数据
            const localHistory = getLocalHistory();
            if (localHistory.length > 0) {
                // 返回本地数据（但提示用户需要同步）
                console.log('数据库历史记录为空，返回本地历史记录');
                return { history: localHistory, is_local: true };
            }
            
            return { history: [] };
        } catch (error) {
            // 如果未登录或请求失败，返回localStorage数据
            if (error.message.includes('请先登录') || error.message.includes('401')) {
                return { history: getLocalHistory() };
            }
            // 其他错误也尝试返回本地数据
            console.error('获取数据库历史记录失败，返回本地数据:', error);
            return { history: getLocalHistory() };
        }
    },
    
    // 添加历史记录
    add: async (historyData) => {
        try {
            // 如果已登录，保存到数据库
            const response = await apiRequest('/api/history', {
                method: 'POST',
                body: JSON.stringify(historyData)
            });
            // API响应结构为 { success: true, data: {...}, message: "...", timestamp: "..." }
            const result = {
                success: response.success,
                message: response.message
            };
            // 同时更新本地缓存（保持同步）
            addToLocalHistory(historyData);
            return result;
        } catch (error) {
            // 如果未登录，使用localStorage
            if (error.message.includes('请先登录') || error.message.includes('401')) {
                addToLocalHistory(historyData);
                return { success: true, message: '历史记录已保存（本地）' };
            }
            throw error;
        }
    },
    
    // 同步本地历史记录到数据库
    sync: async () => {
        try {
            const localHistory = getLocalHistory();
            const hasLocalData = localHistory.length > 0;
            
            if (!hasLocalData) {
                // 即使本地没有数据，也获取服务器数据并更新本地缓存
                const serverData = await HistoryAPI.get();
                if (serverData && serverData.history && serverData.history.length > 0) {
                    // 将服务器数据转换为本地格式并保存
                    const localFormat = serverData.history.map(item => ({
                        book_id: item.book_id,
                        interface: item.interface,
                        chapter_id: item.chapter_id,
                        chapter_title: item.chapter_title || '',
                        book_title: item.book_title || '',
                        book_image: item.book_image || '',
                        book_anchor: item.book_anchor || '',
                        playTime: item.play_time || new Date().toISOString()
                    }));
                    saveLocalHistory(localFormat);
                    console.log('已更新本地历史记录缓存，共', localFormat.length, '条');
                }
                return { success: true, message: '没有需要同步的历史记录', synced_count: 0 };
            }
            
            // 先上传本地数据到服务器
            const response = await apiRequest('/api/history/sync', {
                method: 'POST',
                body: JSON.stringify({ history: localHistory })
            });
            
            // 直接使用API响应的结构
            const result = {
                success: response.success,
                message: response.message || '同步完成',
                synced_count: response.synced_count || 0,
                skipped_count: response.skipped_count || 0,
                error_count: response.error_count || 0
            };
            
            // 同步成功后，获取服务器最新数据并更新本地缓存（保留数据）
            if (result.success) {
                const serverData = await HistoryAPI.get();
                if (serverData && serverData.history) {
                    // 将服务器数据转换为本地格式并保存
                    const localFormat = serverData.history.map(item => ({
                        book_id: item.book_id,
                        interface: item.interface,
                        chapter_id: item.chapter_id,
                        chapter_title: item.chapter_title || '',
                        book_title: item.book_title || '',
                        book_image: item.book_image || '',
                        book_anchor: item.book_anchor || '',
                        playTime: item.play_time || new Date().toISOString()
                    }));
                    saveLocalHistory(localFormat);
                    console.log('已更新本地历史记录缓存，共', localFormat.length, '条');
                }
            }
            
            return result;
        } catch (error) {
            console.error('同步历史记录失败:', error);
            throw error;
        }
    },
    
    // 删除单条历史记录
    delete: async (historyId) => {
        try {
            // 如果已登录，从数据库删除
            const response = await apiRequest(`/api/history/${historyId}`, {
                method: 'DELETE'
            });
            
            // 无论登录状态如何，都从本地缓存删除
            deleteLocalHistory(historyId);
            
            return {
                success: response.success,
                message: response.message
            };
        } catch (error) {
            // 如果未登录，只从本地缓存删除
            if (error.message.includes('请先登录') || error.message.includes('401')) {
                deleteLocalHistory(historyId);
                return { success: true, message: '已删除（本地）' };
            }
            throw error;
        }
    },
    
    // 清空所有历史记录
    clear: async () => {
        try {
            // 如果已登录，清空数据库
            const response = await apiRequest('/api/history', {
                method: 'DELETE'
            });
            
            // 无论登录状态如何，都清空本地缓存
            clearLocalHistory();
            
            return {
                success: response.success,
                message: response.message
            };
        } catch (error) {
            // 如果未登录，只清空本地缓存
            if (error.message.includes('请先登录') || error.message.includes('401')) {
                clearLocalHistory();
                return { success: true, message: '已清空（本地）' };
            }
            throw error;
        }
    }
};

// localStorage 备用函数（未登录时使用）
function getLocalHistory() {
    const history = localStorage.getItem('playHistory');
    if (!history) return [];
    try {
    const parsed = JSON.parse(history);
        if (!Array.isArray(parsed)) return [];
    // 转换为API格式
    return parsed.map((item, index) => ({
            id: index, // 本地数据使用索引作为ID
            index: index, // 同时保存index字段
        book_id: item.book_id,
        interface: item.interface,
        chapter_id: item.chapter_id,
            chapter_title: item.chapter_title || '',
            book_title: item.book_title || '',
            book_image: item.book_image || '',
            book_anchor: item.book_anchor || '',
            play_time: item.playTime || item.play_time || new Date().toISOString()
    }));
    } catch (e) {
        console.error('解析本地历史记录失败:', e);
        return [];
    }
}

function saveLocalHistory(history) {
    localStorage.setItem('playHistory', JSON.stringify(history));
}

function addToLocalHistory(historyData) {
    const history = JSON.parse(localStorage.getItem('playHistory') || '[]');
    const historyItem = {
        book_id: historyData.book_id,
        interface: historyData.interface,
        chapter_id: historyData.chapter_id,
        chapter_title: historyData.chapter_title,
        book_title: historyData.book_title,
        book_image: historyData.book_image,
        book_anchor: historyData.book_anchor,
        playTime: new Date().toISOString()
    };
    
    // 移除同一本书的旧记录（每本书只保留最新一条记录）
    const filtered = history.filter(item => 
        !(item.book_id == historyData.book_id && 
          item.interface == historyData.interface)
    );
    
    // 添加新记录到开头
    filtered.unshift(historyItem);
    const limited = filtered.slice(0, 100);
    saveLocalHistory(limited);
}

function deleteLocalHistory(historyId) {
    // historyId可能是数字索引（本地数据）或数据库ID
    const history = JSON.parse(localStorage.getItem('playHistory') || '[]');
    // 如果是数字且小于数组长度，说明是索引
    if (typeof historyId === 'number' && historyId >= 0 && historyId < history.length) {
        history.splice(historyId, 1);
    saveLocalHistory(history);
    } else {
        // 否则尝试按book_id和interface匹配删除
        const filtered = history.filter(item => {
            // 这里无法匹配，因为本地数据没有数据库ID
            // 但如果是数字索引，已经在上面处理了
            return true;
        });
        // 如果没有匹配到，忽略删除操作
        if (filtered.length < history.length) {
            saveLocalHistory(filtered);
        }
    }
}

function clearLocalHistory() {
    localStorage.setItem('playHistory', '[]');
}

/**
 * 统计数据相关API（需要登录）
 */
const StatsAPI = {
    // 获取统计信息
    get: async () => {
        try {
            return await apiRequest('/api/stats');
        } catch (error) {
            // 如果未登录，返回空统计
            if (error.message.includes('请先登录') || error.message.includes('401')) {
                return {
                    stats: {
                        total_books: 0,
                        total_chapters: 0,
                        total_hours: 0,
                        total_minutes: 0
                    },
                    recent_books: []
                };
            }
            throw error;
        }
    }
};

