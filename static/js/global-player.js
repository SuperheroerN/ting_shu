/**
 * 全局音频播放器管理器
 * 支持跨页面持续播放和可拖拽悬浮窗口
 */

class GlobalPlayer {
    constructor() {
        this.audio = null;
        this.currentBook = null;
        this.currentChapter = null;
        this.currentAudioUrl = null;
        this.isInitialized = false;
        this.updateInterval = null;
        this._isSwitchingChapter = false; // 防止重复切换章节
        
        // 拖拽相关
        this.isDragging = false;
        this.dragOffset = { x: 0, y: 0 };
        this.position = { x: 0, y: 0 };
        
        // 确保在页面加载后初始化
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
        } else {
            this.init();
        }
    }

    init() {
        // 创建全局音频元素（单例）
        if (!this.audio) {
            this.audio = new Audio();
            this.audio.preload = 'metadata';
            // 不设置crossOrigin，让浏览器自动处理，避免跨域问题
            // this.audio.crossOrigin = 'anonymous';
            
            // 绑定音频事件
            this.bindAudioEvents();
        }
        
        // 创建播放器UI（如果不存在）
        this.createPlayerUI();
        
        // 绑定UI事件（每次初始化都重新绑定，确保事件正常工作）
        this.bindUIEvents();
        
        // 绑定拖拽事件（每次初始化都重新绑定）
        this.bindDragEvents();
        
        // 恢复播放状态
        this.restorePlayState();
        
        // 恢复位置
        this.restorePosition();
        
        // 开始更新UI
        this.startUpdateUI();
        
        this.isInitialized = true;
        
        // 如果有播放状态，显示播放器
        if (this.currentBook) {
            this.showPlayer();
        }
    }

    /**
     * 创建播放器UI（简化版：只有封面图片）
     */
    createPlayerUI() {
        let player = document.getElementById('global-player');
        if (!player) {
            player = document.createElement('div');
            player.id = 'global-player';
            player.innerHTML = `
                <div class="global-player-cover-container">
                    <img class="global-player-book-image" src="" alt="封面">
                    <div class="global-player-play-indicator"></div>
                </div>
            `;
            document.body.appendChild(player);
            
            // 点击封面进入播放页
            player.addEventListener('click', () => {
                this.goToPlayerPage();
            });
        }
    }

    /**
     * 绑定音频事件
     */
    bindAudioEvents() {
        // 播放状态变化
        this.audio.addEventListener('play', () => {
            this.savePlayState();
            this.updateUI();
            this.setupMediaSession();
            // 更新MediaSession播放状态
            if ('mediaSession' in navigator) {
                navigator.mediaSession.playbackState = 'playing';
            }
        });

        this.audio.addEventListener('pause', () => {
            this.savePlayState();
            this.updateUI();
            // 更新MediaSession播放状态
            if ('mediaSession' in navigator) {
                navigator.mediaSession.playbackState = 'paused';
            }
        });

        // 监听playing事件，触发下一章缓存
        this.audio.addEventListener('playing', () => {
            // 触发下一章缓存（如果player.html中的函数存在）
            if (typeof window.triggerNextChapterCache === 'function') {
                setTimeout(() => {
                    window.triggerNextChapterCache();
                }, 50);
            }
        });

        this.audio.addEventListener('ended', () => {
            console.log('全局播放器：播放结束事件触发');
            this.savePlayState();
            this.updateUI();
            
            // ✅ 修复：如果在播放页面，交给player.html处理，避免双重触发
            if (window.location.pathname.includes('/player/')) {
                console.log('当前在播放页面，由播放页面处理ended事件');
                return;
            }
            
            // 防止重复触发：检查是否正在切换章节
            if (this._isSwitchingChapter) {
                console.log('正在切换章节，跳过自动播放下一章');
                return;
            }
            
            // 非播放页面（如首页、详情页），自动播放下一章
            setTimeout(() => {
                // 再次检查，确保没有重复触发
                if (!this._isSwitchingChapter) {
                    this.autoPlayNext();
                }
            }, 100);
        });

        // 时间更新
        this.audio.addEventListener('timeupdate', () => {
            this.savePlayState();
            this.updateProgress();
            this.updateMediaSessionPosition();
        });

        // 加载元数据
        this.audio.addEventListener('loadedmetadata', () => {
            this.updateUI();
            this.setupMediaSession();
        });

        // 时间更新时更新MediaSession
        this.audio.addEventListener('timeupdate', () => {
            this.updateMediaSessionPosition();
        });

        // 错误处理
        this.audio.addEventListener('error', (e) => {
            // 检查是否是真正的错误（排除一些可以忽略的情况）
            if (e.target.error) {
                const error = e.target.error;
                // 忽略用户中止的错误（MEDIA_ERR_ABORTED）
                if (error.code === error.MEDIA_ERR_ABORTED) {
                    console.log('音频加载被用户中止（正常情况）');
                    return;
                }
                
                // 检查URL是否是有效的音频URL（不是页面URL）
                const audioUrl = this.audio.src;
                if (audioUrl && !audioUrl.match(/\.(mp3|m4a|aac|ogg|wav|flac|webm)(\?|$)/i) && 
                    audioUrl.includes('/player/')) {
                    // 如果URL是播放页面URL而不是音频文件URL，这是正常的（可能是初始化时的临时状态）
                    console.log('音频URL是播放页面URL（可能是初始化状态，可忽略）:', audioUrl);
                    return;
                }
                
                // 其他错误才真正记录
                const errorMessage = this.getErrorMessage(error);
                console.error('音频播放错误:', {
                    code: error.code,
                    message: errorMessage,
                    url: audioUrl
                });
                
                // 如果是网络错误或解码错误，尝试重新获取音频URL
                if (error.code === error.MEDIA_ERR_NETWORK || error.code === error.MEDIA_ERR_DECODE) {
                    console.log('检测到网络或解码错误，尝试重新获取音频URL');
                    if (this.currentBook && this.currentChapter) {
                        // 延迟一点再尝试，避免频繁重试
                        setTimeout(() => {
                            if (typeof authenticatedFetch !== 'undefined') {
                                authenticatedFetch('/get_chapter', {
                                    bookId: this.currentBook.bookId,
                                    chapterId: this.currentChapter.chapterId,
                                    interface: this.currentBook.interface
                                }).then(response => {
                                    if (response.url) {
                                        this.play(
                                            this.currentBook.bookId,
                                            this.currentBook.interface,
                                            this.currentChapter.chapterId,
                                            this.currentBook.bookTitle,
                                            this.currentChapter.chapterTitle,
                                            this.currentBook.bookImage,
                                            response.url
                                        );
                                    }
                                }).catch(err => {
                                    console.error('重新获取音频URL失败:', err);
                                });
                            }
                        }, 1000);
                    }
                }
            } else {
                // 没有错误对象，可能是其他类型的错误
                console.log('音频事件（可能是正常状态变化）:', e.type);
            }
        });
    }
    
    /**
     * 获取错误消息
     */
    getErrorMessage(error) {
        if (!error || !error.code) return '未知错误';
        
        switch(error.code) {
            case error.MEDIA_ERR_ABORTED:
                return '用户中止';
            case error.MEDIA_ERR_NETWORK:
                return '网络错误';
            case error.MEDIA_ERR_DECODE:
                return '解码错误';
            case error.MEDIA_ERR_SRC_NOT_SUPPORTED:
                return '格式不支持';
            default:
                return '未知错误';
        }
        
        // 设置MediaSession API（支持iOS息屏控制）
        this.setupMediaSession();
    }
    
    /**
     * 设置MediaSession API（支持iOS息屏后继续播放和自动下一章）
     */
    setupMediaSession() {
        if (!('mediaSession' in navigator)) {
            return;
        }
        
        if (!this.currentBook || !this.currentChapter) {
            return;
        }
        
        try {
            // 设置媒体元数据
            navigator.mediaSession.metadata = new MediaMetadata({
                title: this.currentChapter.chapterTitle || '未知章节',
                artist: this.currentBook.bookTitle || '未知书籍',
                album: this.currentBook.bookTitle || '未知书籍',
                artwork: [
                    {
                        src: this.currentBook.bookImage || '/static/images/icon-192x192.png',
                        sizes: '192x192',
                        type: 'image/png'
                    },
                    {
                        src: this.currentBook.bookImage || '/static/images/icon-512x512.png',
                        sizes: '512x512',
                        type: 'image/png'
                    }
                ]
            });
            
            // 设置播放操作
            navigator.mediaSession.setActionHandler('play', () => {
                if (this.audio && !this.audio.paused) {
                    return; // 已经在播放，避免重复
                }
                this.audio.play();
            });
            
            navigator.mediaSession.setActionHandler('pause', () => {
                if (this.audio && this.audio.paused) {
                    return; // 已经暂停，避免重复
                }
                this.audio.pause();
            });
            
            // ✅ 修复：不在这里设置播放状态，由play/pause事件处理（97行和110行）
            // 避免状态不同步导致iOS息屏播放失败
            
            // 设置下一首操作（用于自动播放下一章）
            navigator.mediaSession.setActionHandler('nexttrack', () => {
                console.log('MediaSession: 下一章');
                // 防止重复触发
                if (!this._isSwitchingChapter) {
                    this.autoPlayNext();
                }
            });
            
            // 设置上一首操作
            navigator.mediaSession.setActionHandler('previoustrack', async () => {
                console.log('MediaSession: 上一章');
                if (this.currentBook && this.currentChapter) {
                    try {
                        const data = await authenticatedFetch('/get_chapter_context', {
                            bookId: this.currentBook.bookId,
                            chapterId: this.currentChapter.chapterId,
                            interface: this.currentBook.interface
                        });
                        if (data.prev_chapter && data.prev_chapter.chapter_id) {
                            const urlData = await authenticatedFetch('/get_chapter', {
                                bookId: this.currentBook.bookId,
                                chapterId: data.prev_chapter.chapter_id,
                                interface: this.currentBook.interface
                            });
                            if (urlData.url) {
                                this.play(
                                    this.currentBook.bookId,
                                    this.currentBook.interface,
                                    data.prev_chapter.chapter_id,
                                    this.currentBook.bookTitle,
                                    data.prev_chapter.title || '未知章节',
                                    this.currentBook.bookImage,
                                    urlData.url
                                );
                            }
                        }
                    } catch (error) {
                        console.error('播放上一章失败:', error);
                    }
                }
            });
            
            // 设置进度控制
            if ('setPositionState' in navigator.mediaSession) {
                navigator.mediaSession.setActionHandler('seekto', (details) => {
                    if (details.seekTime !== undefined) {
                        this.audio.currentTime = details.seekTime;
                    }
                });
            }
        } catch (error) {
            console.error('设置MediaSession失败:', error);
        }
    }
    
    /**
     * 更新MediaSession播放位置
     */
    updateMediaSessionPosition() {
        if (!('mediaSession' in navigator) || !this.audio || !('setPositionState' in navigator.mediaSession)) {
            return;
        }
        
        try {
            navigator.mediaSession.setPositionState({
                duration: this.audio.duration || 0,
                playbackRate: this.audio.playbackRate || 1,
                position: this.audio.currentTime || 0
            });
        } catch (error) {
            // 某些浏览器可能不支持setPositionState
        }
    }

    /**
     * 绑定UI事件（简化版：只需点击进入播放页）
     */
    bindUIEvents() {
        const player = document.getElementById('global-player');
        if (!player) return;
        
        // 点击封面进入播放页（已在createPlayerUI中绑定）
        // 这里可以添加其他需要的交互
    }

    /**
     * 绑定拖拽事件
     */
    bindDragEvents() {
        const player = document.getElementById('global-player');
        if (!player) return;

        // 整个播放器都可以拖拽
        const dragHandle = player;

        // 鼠标按下
        dragHandle.addEventListener('mousedown', (e) => {
            // 只有按住鼠标移动超过5px才认为是拖拽，否则是点击
            const startX = e.clientX;
            const startY = e.clientY;
            let moved = false;
            
            const onMouseMove = (e) => {
                const deltaX = Math.abs(e.clientX - startX);
                const deltaY = Math.abs(e.clientY - startY);
                if (deltaX > 5 || deltaY > 5) {
                    moved = true;
                    this.isDragging = true;
                    const rect = player.getBoundingClientRect();
                    this.dragOffset.x = e.clientX - rect.left;
                    this.dragOffset.y = e.clientY - rect.top;
                    player.style.cursor = 'grabbing';
                    e.preventDefault();
                }
            };
            
            const onMouseUp = () => {
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', onMouseUp);
                if (!moved) {
                    // 没有移动，视为点击，进入播放页
                    this.goToPlayerPage();
                }
            };
            
            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
            e.preventDefault();
        });

        // 鼠标移动
        document.addEventListener('mousemove', (e) => {
            if (!this.isDragging) return;
            
            // 计算新位置
            let newX = e.clientX - this.dragOffset.x;
            let newY = e.clientY - this.dragOffset.y;
            
            // 限制在可视区域内，考虑底部导航栏和边距
            const margin = window.innerWidth <= 480 ? 8 : 12;
            const bottomNavHeight = 60;
            const maxX = window.innerWidth - player.offsetWidth - margin;
            const maxY = window.innerHeight - player.offsetHeight - bottomNavHeight - margin;
            
            newX = Math.max(margin, Math.min(newX, maxX));
            newY = Math.max(margin, Math.min(newY, maxY));
            
            // 使用left和top定位
            player.style.left = newX + 'px';
            player.style.top = newY + 'px';
            player.style.right = 'auto';
            player.style.bottom = 'auto';
            
            e.preventDefault();
        });

        // 鼠标释放
        document.addEventListener('mouseup', () => {
            if (this.isDragging) {
                this.isDragging = false;
                const player = document.getElementById('global-player');
                if (player) {
                    player.style.cursor = '';
                    this.savePosition();
                }
            }
        });

        // 触摸事件（移动端）
        dragHandle.addEventListener('touchstart', (e) => {
            const touch = e.touches[0];
            const startX = touch.clientX;
            const startY = touch.clientY;
            let moved = false;
            
            const onTouchMove = (e) => {
                const touch = e.touches[0];
                const deltaX = Math.abs(touch.clientX - startX);
                const deltaY = Math.abs(touch.clientY - startY);
                if (deltaX > 5 || deltaY > 5) {
                    if (!moved) {
                        // 第一次移动时设置拖拽偏移
                        const rect = player.getBoundingClientRect();
                        this.dragOffset.x = touch.clientX - rect.left;
                        this.dragOffset.y = touch.clientY - rect.top;
                    }
                    moved = true;
                    this.isDragging = true;
                    
                    // 计算新位置
                    let newX = touch.clientX - this.dragOffset.x;
                    let newY = touch.clientY - this.dragOffset.y;
                    
                    // 限制在可视区域内
                    const margin = 8;
                    const bottomNavHeight = 60;
                    const maxX = window.innerWidth - player.offsetWidth - margin;
                    const maxY = window.innerHeight - player.offsetHeight - bottomNavHeight - margin;
                    
                    newX = Math.max(margin, Math.min(newX, maxX));
                    newY = Math.max(margin, Math.min(newY, maxY));
                    
                    // 更新位置
                    player.style.left = newX + 'px';
                    player.style.top = newY + 'px';
                    player.style.right = 'auto';
                    player.style.bottom = 'auto';
                    
                    e.preventDefault();
                }
            };
            
            const onTouchEnd = () => {
                document.removeEventListener('touchmove', onTouchMove);
                document.removeEventListener('touchend', onTouchEnd);
                if (!moved) {
                    // 没有移动，视为点击，进入播放页
                    this.goToPlayerPage();
                } else {
                    this.isDragging = false;
                    this.savePosition();
                }
            };
            
            document.addEventListener('touchmove', onTouchMove);
            document.addEventListener('touchend', onTouchEnd);
        });

        // 触摸移动和结束事件已在touchstart中处理
    }

    /**
     * 更新播放器位置（已集成到mousemove和touchmove中）
     */
    updatePlayerPosition() {
        // 位置更新已在拖拽事件处理函数中完成
    }

    /**
     * 保存位置到localStorage
     */
    savePosition() {
        try {
            const player = document.getElementById('global-player');
            if (player) {
                // 保存right和bottom值
                const position = {
                    right: player.style.right,
                    bottom: player.style.bottom,
                    left: player.style.left,
                    top: player.style.top
                };
                localStorage.setItem('globalPlayerPosition', JSON.stringify(position));
            }
        } catch (e) {
            console.error('保存播放器位置失败:', e);
        }
    }

    /**
     * 恢复位置
     */
    restorePosition() {
        try {
            const saved = localStorage.getItem('globalPlayerPosition');
            const player = document.getElementById('global-player');
            if (!player) return;
            
            // 确保播放器已渲染
            if (player.offsetWidth === 0) {
                setTimeout(() => this.restorePosition(), 100);
                return;
            }
            
            if (saved) {
                const position = JSON.parse(saved);
                // 恢复保存的位置样式
                if (position.right) player.style.right = position.right;
                if (position.bottom) player.style.bottom = position.bottom;
                if (position.left) player.style.left = position.left;
                if (position.top) player.style.top = position.top;
            } else {
                this.setDefaultPosition();
            }
        } catch (e) {
            console.error('恢复播放器位置失败:', e);
            this.setDefaultPosition();
        }
    }

    /**
     * 设置默认位置（右下角，避开底部导航栏）
     */
    setDefaultPosition() {
        const player = document.getElementById('global-player');
        if (!player) return;
        
        const margin = window.innerWidth <= 480 ? 12 : 20;
        const bottomNavHeight = 60;
        
        setTimeout(() => {
            // 使用right和bottom定位更简单
            player.style.right = margin + 'px';
            player.style.bottom = (bottomNavHeight + margin) + 'px';
            player.style.left = 'auto';
            player.style.top = 'auto';
            this.savePosition();
        }, 100);
    }

    /**
     * 播放音频
     */
    play(bookId, interfaceType, chapterId, bookTitle, chapterTitle, bookImage, audioUrl) {
        console.log('GlobalPlayer.play called:', { bookId, chapterId, audioUrl });
        
        if (!audioUrl) {
            console.error('音频URL为空，无法播放');
            return;
        }
        
        // 检查是否是同一章节（在保存之前判断）
        const isSameChapter = this.currentChapter && this.currentChapter.chapterId === chapterId;
        const isSameUrl = this.currentAudioUrl === audioUrl;
        
        // 保存当前播放信息（在判断之后保存，避免影响判断）
        this.currentBook = {
            bookId,
            interface: interfaceType,
            bookTitle,
            bookImage
        };
        this.currentChapter = {
            chapterId,
            chapterTitle
        };

        // 检查是否需要重新加载音频
        // 如果章节改变或URL改变，重新加载
        const needReload = !isSameChapter || !isSameUrl;
        
        if (needReload) {
            console.log('加载新的音频URL:', audioUrl);
            console.log('当前章节:', this.currentChapter?.chapterId, '新章节:', chapterId);
            console.log('当前URL:', this.currentAudioUrl, '新URL:', audioUrl);
            
            // 先暂停当前播放
            if (!this.audio.paused) {
                this.audio.pause();
            }
            
            // 设置新的URL
            this.currentAudioUrl = audioUrl;
            this.audio.src = audioUrl;
            
            // 清除之前的加载状态
            this.audio.load();
            
            // 等待音频元数据加载完成后再播放
            const playAfterLoad = () => {
                // 恢复播放位置（仅当是同一章节时）
                if (isSameChapter) {
                    const savedState = this.getSavedState();
                    if (savedState && savedState.bookId === bookId && savedState.chapterId === chapterId) {
                        if (savedState.currentTime && savedState.currentTime < this.audio.duration) {
                            this.audio.currentTime = savedState.currentTime;
                            console.log('恢复播放位置:', savedState.currentTime);
                        }
                    }
                }
                
                // 播放
                const playPromise = this.audio.play();
                if (playPromise !== undefined) {
                    playPromise
                        .then(() => {
                            console.log('播放成功');
                            this.showPlayer();
                            this.savePlayState();
                            this.setupMediaSession();
                            
                            // 触发下一章缓存（如果player.html中的函数存在）
                            if (typeof window.triggerNextChapterCache === 'function') {
                                // 延迟一点确保所有状态都已更新
                                setTimeout(() => {
                                    window.triggerNextChapterCache();
                                }, 100);
                            }
                        })
                        .catch(error => {
                            console.error('播放失败:', error);
                            this._isSwitchingChapter = false;
                            
                            // 如果是用户交互错误，不显示提示（避免打断用户）
                            if (error.name !== 'NotAllowedError') {
                                console.error('播放错误详情:', error);
                                
                                // ✅ 显示错误提示
                                if (typeof window.showToast === 'function') {
                                    window.showToast('播放失败: ' + (error.message || '未知错误'), 'error');
                                }
                            }
                        });
                }
            };
            
            // 监听加载完成事件
            let loadHandled = false;
            const onLoadedData = () => {
                if (loadHandled) return;
                loadHandled = true;
                this.audio.removeEventListener('loadeddata', onLoadedData);
                this.audio.removeEventListener('canplay', onCanPlay);
                this.audio.removeEventListener('canplaythrough', onCanPlayThrough);
                // 重置切换标志，允许下次切换
                this._isSwitchingChapter = false;
                playAfterLoad();
            };
            
            const onCanPlay = () => {
                if (loadHandled) return;
                loadHandled = true;
                this.audio.removeEventListener('loadeddata', onLoadedData);
                this.audio.removeEventListener('canplay', onCanPlay);
                this.audio.removeEventListener('canplaythrough', onCanPlayThrough);
                playAfterLoad();
            };
            
            const onCanPlayThrough = () => {
                if (loadHandled) return;
                loadHandled = true;
                this.audio.removeEventListener('loadeddata', onLoadedData);
                this.audio.removeEventListener('canplay', onCanPlay);
                this.audio.removeEventListener('canplaythrough', onCanPlayThrough);
                playAfterLoad();
            };
            
            this.audio.addEventListener('loadeddata', onLoadedData, { once: true });
            this.audio.addEventListener('canplay', onCanPlay, { once: true });
            this.audio.addEventListener('canplaythrough', onCanPlayThrough, { once: true });
            
            // 如果元数据已加载，直接播放
            if (this.audio.readyState >= 2) {
                setTimeout(() => {
                    if (!loadHandled) {
                        loadHandled = true;
                        playAfterLoad();
                    }
                }, 200);
            } else {
                // ✅ 改进超时处理：检查readyState，避免在未加载时播放
                setTimeout(() => {
                    if (!loadHandled) {
                        if (this.audio.readyState >= 2) {
                            // 已加载元数据，可以尝试播放
                            console.log('音频加载超时，但元数据已就绪，尝试播放');
                            loadHandled = true;
                            playAfterLoad();
                        } else {
                            // 真正的加载失败
                            console.error('音频加载失败：超时且readyState=' + this.audio.readyState);
                            loadHandled = true;
                            this._isSwitchingChapter = false;
                            
                            // ✅ 显示错误提示
                            if (typeof window.showToast === 'function') {
                                window.showToast('音频加载超时，请检查网络', 'error');
                            }
                        }
                    }
                }, 5000);
            }
        } else {
            // 同一章节，直接播放或恢复播放
            console.log('同一章节，恢复播放');
            const playPromise = this.audio.play();
            if (playPromise !== undefined) {
                playPromise
                    .then(() => {
                        console.log('播放成功');
                        this.showPlayer();
                        this.savePlayState();
                    })
                    .catch(error => {
                        console.error('播放失败:', error);
                    });
            }
        }
    }

    /**
     * 暂停播放
     */
    pause() {
        if (this.audio) {
            this.audio.pause();
        }
    }

    /**
     * 切换播放/暂停
     */
    togglePlayPause() {
        console.log('togglePlayPause called, audio:', this.audio, 'paused:', this.audio?.paused);
        
        if (!this.audio) {
            console.error('音频元素未初始化');
            // 尝试重新初始化音频元素
            this.audio = new Audio();
            this.audio.preload = 'metadata';
            this.bindAudioEvents();
            
            // 如果有当前播放信息，尝试重新播放
            if (this.currentBook && this.currentChapter && this.currentAudioUrl) {
                this.play(
                    this.currentBook.bookId,
                    this.currentBook.interface,
                    this.currentChapter.chapterId,
                    this.currentBook.bookTitle,
                    this.currentChapter.chapterTitle,
                    this.currentBook.bookImage,
                    this.currentAudioUrl
                );
            } else {
                console.error('没有播放信息，无法重新播放');
                return;
            }
        }

        if (!this.currentBook) {
            console.error('没有正在播放的内容');
            return;
        }

        if (this.audio.paused) {
            console.log('尝试播放音频');
            const playPromise = this.audio.play();
            if (playPromise !== undefined) {
                playPromise
                    .then(() => {
                        console.log('播放成功');
                        this.showPlayer();
                    })
                    .catch(error => {
                        console.error('播放失败:', error);
                        // 如果播放失败，尝试重新获取音频URL并播放
                        if (this.currentBook && this.currentChapter) {
                            console.log('播放失败，尝试重新获取音频URL');
                            // 在播放器页面中，应该通过authenticatedFetch获取新的音频URL
                            if (typeof authenticatedFetch !== 'undefined') {
                                authenticatedFetch('/get_chapter', {
                                    bookId: this.currentBook.bookId,
                                    chapterId: this.currentChapter.chapterId,
                                    interface: this.currentBook.interface
                                }).then(response => {
                                    if (response.url) {
                                        this.play(
                                            this.currentBook.bookId,
                                            this.currentBook.interface,
                                            this.currentChapter.chapterId,
                                            this.currentBook.bookTitle,
                                            this.currentChapter.chapterTitle,
                                            this.currentBook.bookImage,
                                            response.url
                                        );
                                    }
                                }).catch(err => {
                                    console.error('重新获取音频URL失败:', err);
                                });
                            }
                        }
                    });
            }
        } else {
            console.log('暂停播放');
            this.audio.pause();
        }
    }

    /**
     * 设置播放位置
     */
    setCurrentTime(time) {
        if (this.audio && !isNaN(time)) {
            this.audio.currentTime = Math.max(0, Math.min(time, this.audio.duration || 0));
        }
    }

    /**
     * 设置音量
     */
    setVolume(volume) {
        if (this.audio) {
            this.audio.volume = Math.max(0, Math.min(1, volume));
            this.savePlayState();
            this.updateVolumeIcon();
        }
    }

    /**
     * 切换静音
     */
    toggleMute() {
        if (this.audio) {
            this.audio.muted = !this.audio.muted;
            this.savePlayState();
            this.updateVolumeIcon();
            this.updateUI();
        }
    }

    /**
     * 更新音量图标
     */
    updateVolumeIcon() {
        const icon = document.querySelector('.global-player-volume-icon');
        if (icon && this.audio) {
            if (this.audio.muted || this.audio.volume === 0) {
                icon.textContent = '🔇';
            } else if (this.audio.volume < 0.5) {
                icon.textContent = '🔉';
            } else {
                icon.textContent = '🔊';
            }
        }
    }

    /**
     * 停止播放并隐藏播放器
     */
    stop() {
        if (this.audio) {
            this.audio.pause();
            this.audio.currentTime = 0;
        }
        this.currentBook = null;
        this.currentChapter = null;
        this.currentAudioUrl = null;
        this.hidePlayer();
        this.clearSavedState();
    }

    /**
     * 自动播放下一章
     */
    async autoPlayNext() {
        console.log('播放结束，尝试自动播放下一章');
        
        // 防止重复执行
        if (this._isSwitchingChapter) {
            console.log('正在切换章节，跳过自动播放');
            return;
        }
        
        if (!this.currentBook || !this.currentChapter) {
            console.log('没有当前播放信息，无法自动播放下一章');
            return;
        }
        
        // 标记正在切换，防止重复触发
        this._isSwitchingChapter = true;
        
        try {
            // 获取下一章信息
            const data = await authenticatedFetch('/get_chapter_context', {
                bookId: this.currentBook.bookId,
                chapterId: this.currentChapter.chapterId,
                interface: this.currentBook.interface
            });
            console.log('章节上下文数据:', data);
            
            if (data.next_chapter && data.next_chapter.chapter_id) {
                console.log('找到下一章，开始播放:', data.next_chapter);
                
                // 检查是否已经在播放页面处理过了（避免重复处理）
                if (window.chapterSwitchHandled && window.chapterSwitchHandledId === data.next_chapter.chapter_id) {
                    console.log('章节切换已在播放页面处理，跳过global-player处理');
                    // 清除标志，为下次做准备
                    window.chapterSwitchHandled = false;
                    window.chapterSwitchHandledId = null;
                    return;
                }
                
                // 先检查缓存池中是否有缓存的URL
                let audioUrl = null;
                if (window.audioCachePool) {
                    audioUrl = window.audioCachePool.get(data.next_chapter.chapter_id);
                    if (audioUrl) {
                        console.log('从缓存池获取下一章音频URL:', audioUrl);
                        // 标记已处理，避免重复处理
                        window.chapterSwitchHandled = true;
                        window.chapterSwitchHandledId = data.next_chapter.chapter_id;
                    }
                }
                
                // 如果缓存池中没有，检查旧的单个缓存（向后兼容）
                if (!audioUrl && window.cachedNextChapterUrl && window.cachedNextChapterId === data.next_chapter.chapter_id) {
                    console.log('使用旧的单个缓存音频URL:', window.cachedNextChapterUrl);
                    audioUrl = window.cachedNextChapterUrl;
                    // 将旧的缓存添加到缓存池
                    if (window.audioCachePool) {
                        window.audioCachePool.add(data.next_chapter.chapter_id, audioUrl, null);
                    }
                    // 清除旧的单个缓存
                    window.cachedNextChapterUrl = null;
                    window.cachedNextChapterId = null;
                    // 标记已处理，避免重复处理
                    window.chapterSwitchHandled = true;
                    window.chapterSwitchHandledId = data.next_chapter.chapter_id;
                }
                
                // 如果都没有缓存，则调用API获取URL
                if (!audioUrl) {
                    console.log('未找到缓存的URL，调用API获取下一章音频URL');
                    const urlData = await authenticatedFetch('/get_chapter', {
                        bookId: this.currentBook.bookId,
                        chapterId: data.next_chapter.chapter_id,
                        interface: this.currentBook.interface
                    });
                    audioUrl = urlData.url;
                    // 将新获取的URL添加到缓存池
                    if (window.audioCachePool && audioUrl) {
                        window.audioCachePool.add(data.next_chapter.chapter_id, audioUrl, null);
                    }
                    // 标记已处理，避免重复处理
                    window.chapterSwitchHandled = true;
                    window.chapterSwitchHandledId = data.next_chapter.chapter_id;
                }
                
                if (audioUrl) {
                    // ✅ 修复：先更新章节信息，确保setupMediaSession获取到正确的metadata
                    this.currentChapter = {
                        chapterId: data.next_chapter.chapter_id,
                        chapterTitle: data.next_chapter.title || '未知章节'
                    };
                    
                    // ✅ 立即更新MediaSession，确保iOS息屏界面显示正确信息
                    // 这对iOS息屏播放至关重要！
                    this.setupMediaSession();
                    
                    // 播放下一章
                    this.play(
                        this.currentBook.bookId,
                        this.currentBook.interface,
                        data.next_chapter.chapter_id,
                        this.currentBook.bookTitle,
                        data.next_chapter.title || '未知章节',
                        this.currentBook.bookImage,
                        audioUrl
                    );
                    
                    // ✅ 关键修复：立即保存播放状态到localStorage
                    // 防止iOS设备息屏恢复时跳回之前的章节
                    this.savePlayState();
                } else {
                    console.error('下一章音频URL为空');
                    this._isSwitchingChapter = false;
                    
                    // ✅ 显示错误提示
                    if (typeof window.showToast === 'function') {
                        window.showToast('获取下一章失败，请重试', 'error');
                    }
                }
            } else {
                console.log('没有下一章，播放结束');
                this._isSwitchingChapter = false;
            }
        } catch (error) {
            console.error('自动播放下一章失败:', error);
            this._isSwitchingChapter = false;
        }
    }

    /**
     * 保存播放状态到localStorage
     */
    savePlayState() {
        if (!this.currentBook || !this.currentChapter || !this.audio) return;

        const state = {
            bookId: this.currentBook.bookId,
            interface: this.currentBook.interface,
            chapterId: this.currentChapter.chapterId,
            bookTitle: this.currentBook.bookTitle,
            chapterTitle: this.currentChapter.chapterTitle,
            bookImage: this.currentBook.bookImage,
            audioUrl: this.currentAudioUrl,
            currentTime: this.audio.currentTime,
            duration: this.audio.duration,
            volume: this.audio.volume,
            muted: this.audio.muted,
            paused: this.audio.paused,
            timestamp: Date.now()
        };

        try {
            localStorage.setItem('globalPlayerState', JSON.stringify(state));
        } catch (e) {
            console.error('保存播放状态失败:', e);
        }
    }

    /**
     * 从localStorage恢复播放状态
     */
    restorePlayState() {
        try {
            const saved = localStorage.getItem('globalPlayerState');
            if (!saved) return;

            const state = JSON.parse(saved);
            
            // 检查状态是否过期（超过1小时）
            // 修改：即使状态过期，也恢复书籍和章节信息，但不恢复音频URL
            const isExpired = Date.now() - state.timestamp > 3600000;

            // 恢复基本信息（即使过期也恢复，用于显示播放器UI）
            this.currentBook = {
                bookId: state.bookId,
                interface: state.interface,
                bookTitle: state.bookTitle,
                bookImage: state.bookImage
            };
            this.currentChapter = {
                chapterId: state.chapterId,
                chapterTitle: state.chapterTitle
            };

            // 如果状态未过期，恢复音频URL和设置
            if (!isExpired) {
                if (state.audioUrl && this.audio) {
                    // 检查是否是有效的音频文件URL（不是页面URL）
                    // 音频文件URL通常包含文件扩展名或特定的音频服务域名
                    const isAudioFileUrl = state.audioUrl.match(/\.(mp3|m4a|aac|ogg|wav|flac|webm)(\?|$)/i) || 
                                          (state.audioUrl.startsWith('http') && !state.audioUrl.includes('/player/'));
                    
                    if (isAudioFileUrl) {
                        this.currentAudioUrl = state.audioUrl;
                        this.audio.src = state.audioUrl;
                        this.audio.volume = state.volume || 1;
                        this.audio.muted = state.muted || false;
                    } else {
                        // 如果是页面URL，不设置audio.src，避免触发错误事件
                        console.log('跳过恢复无效的音频URL（可能是页面URL）:', state.audioUrl);
                        // 只恢复音量设置
                        this.audio.volume = state.volume || 1;
                        this.audio.muted = state.muted || false;
                    }
                }
            } else {
                // 状态过期：清除音频URL，但保留书籍和章节信息
                // 这样用户回来时可以看到播放器UI，但需要重新获取音频URL
                console.log('播放状态已过期，保留书籍信息但清除音频URL');
                this.currentAudioUrl = null;
                if (this.audio) {
                    this.audio.src = '';
                    this.audio.volume = state.volume || 1;
                    this.audio.muted = state.muted || false;
                }
            }
        } catch (e) {
            console.error('恢复播放状态失败:', e);
            this.clearSavedState();
        }
    }

    /**
     * 获取保存的状态
     */
    getSavedState() {
        try {
            const saved = localStorage.getItem('globalPlayerState');
            return saved ? JSON.parse(saved) : null;
        } catch (e) {
            return null;
        }
    }

    /**
     * 清除保存的状态
     */
    clearSavedState() {
        try {
            localStorage.removeItem('globalPlayerState');
        } catch (e) {
            console.error('清除播放状态失败:', e);
        }
    }

    /**
     * 显示浮动播放器
     */
    showPlayer() {
        const player = document.getElementById('global-player');
        if (player) {
            player.classList.add('active');
            this.updateUI();
        }
    }

    /**
     * 隐藏浮动播放器
     */
    hidePlayer() {
        const player = document.getElementById('global-player');
        if (player) {
            player.classList.remove('active');
        }
    }

    /**
     * 更新UI（简化版：只更新封面）
     */
    updateUI() {
        const player = document.getElementById('global-player');
        if (!player || !this.currentBook) return;

        // 只更新封面图片
        const bookImageEl = player.querySelector('.global-player-book-image');
        if (bookImageEl) {
            bookImageEl.src = this.currentBook.bookImage || '/static/images/default-book.png';
            bookImageEl.onerror = () => {
                bookImageEl.src = '/static/images/default-book.png';
            };
        }
    }

    /**
     * 更新进度条
     */
    updateProgress() {
        const progressBar = document.querySelector('.global-player-progress-filled');
        if (progressBar && this.audio && !isNaN(this.audio.duration) && this.audio.duration > 0) {
            const percent = (this.audio.currentTime / this.audio.duration) * 100;
            progressBar.style.width = percent + '%';
        }
    }

    /**
     * 开始更新UI循环
     */
    startUpdateUI() {
        if (this.updateInterval) return;
        
        this.updateInterval = setInterval(() => {
            if (this.currentBook && this.audio) {
                this.updateUI();
            }
        }, 500);
    }

    /**
     * 停止更新UI循环
     */
    stopUpdateUI() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }

    /**
     * 格式化时间
     */
    formatTime(time) {
        if (isNaN(time) || time < 0) return '00:00';
        const minutes = Math.floor(time / 60);
        const seconds = Math.floor(time % 60);
        return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }

    /**
     * 跳转到播放页
     */
    goToPlayerPage() {
        if (this.currentBook && this.currentChapter) {
            window.location.href = `/player/${this.currentBook.bookId}/${this.currentBook.interface}/${this.currentChapter.chapterId}`;
        }
    }
}

// 创建全局实例（确保只创建一个）
if (typeof window.globalPlayer === 'undefined') {
    window.globalPlayer = new GlobalPlayer();
} else {
    // 如果已存在，重新初始化
    if (window.globalPlayer.isInitialized) {
        window.globalPlayer.init();
    }
}

// 页面卸载前保存状态
window.addEventListener('beforeunload', () => {
    if (window.globalPlayer) {
        window.globalPlayer.savePlayState();
        window.globalPlayer.savePosition();
    }
});

// 页面可见性变化时保存状态
document.addEventListener('visibilitychange', () => {
    if (document.hidden && window.globalPlayer) {
        window.globalPlayer.savePlayState();
    }
});

// 窗口大小改变时，调整播放器位置避免超出屏幕
let resizeTimer;
window.addEventListener('resize', () => {
    if (window.globalPlayer) {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            const player = document.getElementById('global-player');
            if (player && player.classList.contains('active')) {
                // 如果使用的是left/top定位，检查是否超出屏幕
                if (player.style.left && player.style.left !== 'auto') {
                    const rect = player.getBoundingClientRect();
                    const margin = window.innerWidth <= 480 ? 8 : 12;
                    const bottomNavHeight = 60;
                    const maxX = window.innerWidth - player.offsetWidth - margin;
                    const maxY = window.innerHeight - player.offsetHeight - bottomNavHeight - margin;
                    
                    let needsUpdate = false;
                    let newLeft = parseFloat(player.style.left);
                    let newTop = parseFloat(player.style.top);
                    
                    if (rect.left < margin || rect.left > maxX) {
                        newLeft = Math.max(margin, Math.min(newLeft, maxX));
                        needsUpdate = true;
                    }
                    
                    if (rect.top < margin || rect.top > maxY) {
                        newTop = Math.max(margin, Math.min(newTop, maxY));
                        needsUpdate = true;
                    }
                    
                    if (needsUpdate) {
                        player.style.left = newLeft + 'px';
                        player.style.top = newTop + 'px';
                        window.globalPlayer.savePosition();
                    }
                }
            }
        }, 250);
    }
});
