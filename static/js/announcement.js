/**
 * 公告管理
 */

class AnnouncementManager {
    constructor() {
        this.overlay = null;
        this.isShowing = false;
    }

    /**
     * 检查并显示公告
     */
    async checkAndShow() {
        try {
            const response = await fetch('/api/announcement');
            const data = await response.json();

            if (data.success && data.has_announcement && !data.confirmed) {
                // 有公告且未确认，显示公告
                this.show(data.announcement);
            }
        } catch (error) {
            console.error('检查公告失败:', error);
        }
    }

    /**
     * 显示公告
     */
    show(announcement) {
        if (this.isShowing) {
            return;
        }

        this.isShowing = true;
        document.body.classList.add('announcement-open');

        // 创建弹窗HTML
        const overlay = document.createElement('div');
        overlay.className = 'announcement-overlay';
        overlay.innerHTML = `
            <div class="announcement-modal">
                <div class="announcement-header">
                    <h3>${this.escapeHtml(announcement.title)}</h3>
                    <button class="announcement-close" type="button" aria-label="关闭">×</button>
                </div>
                <div class="announcement-content">
                    ${this.formatContent(announcement.content)}
                </div>
                <div class="announcement-footer">
                    <button class="announcement-btn announcement-btn-primary" id="announcement-confirm-btn">
                        我已阅读并同意
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);
        this.overlay = overlay;

        // 绑定事件
        const closeBtn = overlay.querySelector('.announcement-close');
        const confirmBtn = overlay.querySelector('#announcement-confirm-btn');

        // 关闭按钮（禁用，必须点击确认）
        closeBtn.style.display = 'none'; // 隐藏关闭按钮，强制确认

        // 确认按钮
        confirmBtn.addEventListener('click', () => {
            this.confirm(announcement.id);
        });

        // 阻止点击外部关闭
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                e.preventDefault();
                e.stopPropagation();
            }
        });
    }

    /**
     * 确认公告
     */
    async confirm(announcementId) {
        try {
            const response = await fetch('/api/announcement/confirm', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    announcement_id: announcementId
                })
            });

            const data = await response.json();

            if (data.success) {
                this.hide();
            } else {
                alert(data.error || '确认失败，请重试');
            }
        } catch (error) {
            console.error('确认公告失败:', error);
            alert('网络错误，请重试');
        }
    }

    /**
     * 隐藏公告
     */
    hide() {
        if (this.overlay) {
            this.overlay.remove();
            this.overlay = null;
        }
        this.isShowing = false;
        document.body.classList.remove('announcement-open');
    }

    /**
     * 格式化内容（支持换行）
     */
    formatContent(content) {
        if (!content) {
            return '';
        }
        // 将换行符转换为<br>
        return this.escapeHtml(content).replace(/\n/g, '<br>');
    }

    /**
     * HTML转义
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// 创建全局实例
const announcementManager = new AnnouncementManager();

// 页面加载时检查公告
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        announcementManager.checkAndShow();
    });
} else {
    announcementManager.checkAndShow();
}





