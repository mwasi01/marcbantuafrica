/**
 * Marcbantu Africa — Shared app layer.
 * Loaded on every authenticated page.
 * Provides: UI helpers, toast, sidebar, notifications, offline banner.
 */

(function () {
    'use strict';

    // ============================================================
    // DOM HELPERS
    // ============================================================
    const $ = (sel, root = document) => root.querySelector(sel);
    const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

    // ============================================================
    // FORMATTING
    // ============================================================
    const Fmt = {
        currency(amount, currency = 'KES') {
            if (amount == null || isNaN(amount)) return `${currency} 0`;
            return `${currency} ${Number(amount).toLocaleString('en-KE', {
                minimumFractionDigits: 0,
                maximumFractionDigits: 0,
            })}`;
        },

        currencyFull(amount, currency = 'KES') {
            if (amount == null || isNaN(amount)) return `${currency} 0.00`;
            return `${currency} ${Number(amount).toLocaleString('en-KE', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            })}`;
        },

        number(n, decimals = 0) {
            if (n == null || isNaN(n)) return '0';
            return Number(n).toLocaleString('en-KE', {
                minimumFractionDigits: decimals,
                maximumFractionDigits: decimals,
            });
        },

        percent(n, decimals = 1) {
            if (n == null || isNaN(n)) return '0%';
            return `${Number(n).toFixed(decimals)}%`;
        },

        date(d) {
            if (!d) return '—';
            try {
                const date = new Date(d);
                return date.toLocaleDateString('en-KE', {
                    year: 'numeric', month: 'short', day: 'numeric',
                });
            } catch { return d; }
        },

        dateRelative(d) {
            if (!d) return '—';
            try {
                const date = new Date(d);
                const diff = Date.now() - date.getTime();
                const sec = Math.floor(diff / 1000);
                if (sec < 60) return 'just now';
                const min = Math.floor(sec / 60);
                if (min < 60) return `${min}m ago`;
                const hr = Math.floor(min / 60);
                if (hr < 24) return `${hr}h ago`;
                const day = Math.floor(hr / 24);
                if (day < 7) return `${day}d ago`;
                return Fmt.date(d);
            } catch { return d; }
        },

        time(d) {
            if (!d) return '—';
            try {
                return new Date(d).toLocaleTimeString('en-KE', {
                    hour: '2-digit', minute: '2-digit',
                });
            } catch { return d; }
        },

        initials(name) {
            if (!name) return '?';
            return name
                .split(' ')
                .filter(Boolean)
                .map((p) => p[0])
                .slice(0, 2)
                .join('')
                .toUpperCase();
        },

        titleCase(s) {
            if (!s) return '';
            return String(s)
                .replace(/_/g, ' ')
                .replace(/\b\w/g, (c) => c.toUpperCase());
        },

        truncate(s, n = 60) {
            if (!s) return '';
            return s.length > n ? s.slice(0, n - 3) + '...' : s;
        },
    };

    // ============================================================
    // TOAST SYSTEM
    // ============================================================
    const Toast = {
        container: null,

        ensureContainer() {
            if (this.container) return this.container;
            this.container = document.createElement('div');
            this.container.id = 'toast-container';
            this.container.style.cssText = `
                position:fixed; top:20px; right:20px; z-index:9999;
                display:flex; flex-direction:column; gap:10px;
                pointer-events:none; max-width:360px;
            `;
            document.body.appendChild(this.container);
            return this.container;
        },

        show(message, type = 'info', duration = 4000) {
            const container = this.ensureContainer();
            const palettes = {
                success: { bg: '#e8f0e1', border: '#2e7d32', icon: 'fa-check-circle', color: '#2e7d32' },
                error: { bg: '#fde8e8', border: '#c0392b', icon: 'fa-exclamation-circle', color: '#c0392b' },
                warning: { bg: '#fef3d0', border: '#d4a017', icon: 'fa-exclamation-triangle', color: '#8a6914' },
                info: { bg: '#e3f2fd', border: '#1565c0', icon: 'fa-info-circle', color: '#1565c0' },
            };
            const colors = palettes[type] || palettes.info;

            const toast = document.createElement('div');
            toast.style.cssText = `
                background:${colors.bg}; color:${colors.color};
                padding:14px 18px; border-radius:12px;
                border-left:4px solid ${colors.border};
                box-shadow:0 8px 24px rgba(0,0,0,0.12);
                font-size:14px; font-weight:500;
                display:flex; align-items:center; gap:10px;
                pointer-events:auto; cursor:pointer;
                opacity:0; transform:translateX(100%);
                transition:all 0.3s ease;
            `;
            toast.innerHTML = `
                <i class="fas ${colors.icon}" style="font-size:18px;"></i>
                <span style="flex:1;">${message}</span>
            `;

            container.appendChild(toast);
            requestAnimationFrame(() => {
                toast.style.opacity = '1';
                toast.style.transform = 'translateX(0)';
            });

            const remove = () => {
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(100%)';
                setTimeout(() => toast.remove(), 300);
            };

            toast.addEventListener('click', remove);
            setTimeout(remove, duration);
        },

        success(msg) { this.show(msg, 'success'); },
        error(msg) { this.show(msg, 'error', 6000); },
        warning(msg) { this.show(msg, 'warning'); },
        info(msg) { this.show(msg, 'info'); },
    };

    // ============================================================
    // MODAL
    // ============================================================
    const Modal = {
        open(contentOrId) {
            let modal;
            const isHtmlString = typeof contentOrId === 'string'
                && contentOrId.trim().startsWith('<');

            if (!isHtmlString && typeof contentOrId === 'string') {
                modal = document.getElementById(contentOrId);
                if (!modal) return;
                modal.classList.add('open');
            } else {
                modal = document.createElement('div');
                modal.className = 'modal-overlay open';
                modal.innerHTML = `<div class="modal">${contentOrId}</div>`;
                modal.style.cssText = `
                    position:fixed; inset:0; background:rgba(0,0,0,0.6);
                    z-index:2000; display:flex; align-items:center;
                    justify-content:center; padding:20px;
                `;
                document.body.appendChild(modal);
            }

            modal.addEventListener('click', (e) => {
                if (e.target === modal) Modal.close(modal);
            });

            const handler = (e) => {
                if (e.key === 'Escape') {
                    Modal.close(modal);
                    document.removeEventListener('keydown', handler);
                }
            };
            document.addEventListener('keydown', handler);

            return modal;
        },


        close(modal) {
            if (!modal) return;
            modal.classList.remove('open');
            if (modal.parentNode && !modal.id) {
                setTimeout(() => modal.remove(), 300);
            }
        },

        closeAll() {
            $$('.modal-overlay.open').forEach((m) => this.close(m));
        },

        confirm(message, title = 'Confirm') {
            return new Promise((resolve) => {
                const modal = this.open(`
                    <div style="padding:24px;">
                        <h3 style="margin:0 0 12px; color:#1a3c2e;">${title}</h3>
                        <p style="color:#4a5a4a; margin-bottom:20px;">${message}</p>
                        <div style="display:flex; gap:12px; justify-content:flex-end;">
                            <button class="btn-outline" data-action="cancel">Cancel</button>
                            <button class="btn-primary" data-action="confirm">Confirm</button>
                        </div>
                    </div>
                `);

                modal.querySelector('[data-action="cancel"]').addEventListener('click', () => {
                    this.close(modal);
                    resolve(false);
                });
                modal.querySelector('[data-action="confirm"]').addEventListener('click', () => {
                    this.close(modal);
                    resolve(true);
                });
            });
        },
    };

    // ============================================================
    // SIDEBAR
    // ============================================================
    const Sidebar = {
        init() {
            const toggle = $('.menu-toggle-app');
            const sidebar = $('#sidebar');
            if (toggle && sidebar) {
                toggle.addEventListener('click', () => {
                    sidebar.classList.toggle('open');
                });
            }

            // Highlight active nav
            const currentPath = window.location.pathname.split('/').pop() || 'dashboard.html';
            $$('.sidebar-nav a').forEach((link) => {
                const href = link.getAttribute('href');
                if (href === currentPath || (href && currentPath.startsWith(href.replace('.html', '')))) {
                    link.classList.add('active');
                } else {
                    link.classList.remove('active');
                }
            });

            // User avatar in topbar
            const user = Auth.getUser();
            if (user) {
                $$('.user-avatar').forEach((el) => {
                    el.textContent = Fmt.initials(user.full_name);
                    el.title = user.full_name;
                });
                $$('.user-greeting').forEach((el) => {
                    const hour = new Date().getHours();
                    const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
                    el.textContent = `${greeting}, ${user.full_name?.split(' ')[0] || 'farmer'} 👋`;
                });
            }

            // Handle logout
            $$('[data-action="logout"]').forEach((el) => {
                el.addEventListener('click', async (e) => {
                    e.preventDefault();
                    const ok = await Modal.confirm('Log out of Marcbantu?', 'Confirm logout');
                    if (!ok) return;
                    try { await Api.logout(); } catch { }
                    Auth.logout('/login.html');
                });
            });
        },
    };

    // ============================================================
    // NOTIFICATIONS
    // ============================================================
    const Notifications = {
        async updateBadge() {
            if (!Auth.isLoggedIn()) return;
            const result = await Api.unreadCount();
            if (!result.ok) return;
            const count = result.data?.unread_count || 0;
            const badges = $$('.notification-badge');
            badges.forEach((b) => {
                b.textContent = count;
                b.style.display = count > 0 ? 'flex' : 'none';
            });
        },

        async load() {
            const panel = $('#notificationPanel');
            if (!panel) return;
            const result = await Api.listNotifications({ limit: 10 });
            if (!result.ok) return;
            const { notifications, unread_count } = result.data || {};
            this.render(panel, notifications || []);
            await this.updateBadge();
        },

        render(panel, items) {
            if (!items.length) {
                panel.innerHTML = `<div style="padding:20px; text-align:center; color:#8a9c8c; font-size:13px;">No notifications yet</div>`;
                return;
            }

            panel.innerHTML = items.map((n) => `
                <div style="padding:12px; border-bottom:1px solid #eef1ea; cursor:pointer; ${!n.read ? 'background:#fbfcf9;' : ''}"
                     onclick="MarkAsRead(${n.id}, this)">
                    <div style="display:flex; gap:10px; align-items:flex-start;">
                        <i class="fas fa-${this.iconFor(n.type)}" style="color:#d4a017; margin-top:3px;"></i>
                        <div style="flex:1;">
                            <div style="font-weight:600; font-size:13px; color:#1a3c2e;">${n.title}</div>
                            <div style="font-size:12px; color:#4a5a4a; margin-top:2px;">${n.message}</div>
                            <div style="font-size:11px; color:#8a9c8c; margin-top:4px;">${Fmt.dateRelative(n.created_at)}</div>
                        </div>
                    </div>
                </div>
            `).join('');
        },

        iconFor(type) {
            return {
                weather: 'cloud-sun',
                market: 'tag',
                reminder: 'bell',
                alert: 'exclamation-triangle',
                system: 'cog',
                finance: 'coins',
                pest: 'bug',
                learning: 'graduation-cap',
            }[type] || 'bell';
        },
    };

    window.MarkAsRead = async function (id, el) {
        await Api.markRead(id);
        if (el) el.style.background = 'transparent';
        await Notifications.updateBadge();
    };

    // ============================================================
    // OFFLINE HANDLING
    // ============================================================
    function initOfflineBanner() {
        const banner = document.createElement('div');
        banner.id = 'offline-banner';
        banner.style.cssText = `
            position:fixed; bottom:0; left:0; right:0;
            background:#c0392b; color:#fff; padding:8px 16px;
            text-align:center; font-size:13px; font-weight:600;
            z-index:8000; display:none;
        `;
        banner.innerHTML = '<i class="fas fa-wifi"></i> You are offline — changes will sync when you reconnect';
        document.body.appendChild(banner);

        const update = () => {
            banner.style.display = navigator.onLine ? 'none' : 'block';
        };
        window.addEventListener('online', () => {
            update();
            Toast.success('Back online!');
            if (window.OfflineSync) window.OfflineSync.flush();
        });
        window.addEventListener('offline', () => {
            update();
            Toast.warning('You are offline. Data will sync later.');
        });
        update();
    }

    // ============================================================
    // SHARED FETCH LOADER
    // ============================================================
    async function loadWithLoader(fn, target) {
        if (target) target.innerHTML = '<div style="padding:40px; text-align:center; color:#8a9c8c;"><i class="fas fa-spinner fa-spin" style="font-size:24px;"></i></div>';
        try {
            return await fn();
        } catch (err) {
            console.error(err);
            Toast.error('Failed to load data');
        }
    }

    // ============================================================
    // BOOT
    // ============================================================
    document.addEventListener('DOMContentLoaded', () => {
        // Require auth on app pages (except login/register/index)
        const path = window.location.pathname;
        const publicPages = ['/', '/index.html', '/login.html', '/register.html', '/about.html', '/contact.html', '/partners.html', '/404.html', '/privacy.html', '/terms.html'];
        const isPublic = publicPages.some((p) => path === p || path.endsWith(p));

        if (!isPublic && !path.includes('login') && !path.includes('register')) {
            if (!Auth.requireLogin()) return;
        }

        Sidebar.init();
        initOfflineBanner();

        if (Auth.isLoggedIn()) {
            Notifications.updateBadge();
        }
    });

    // ============================================================
    // EXPORTS
    // ============================================================
    window.UI = {
        $, $$, Fmt, Toast, Modal, Sidebar, Notifications, loadWithLoader,
    };
    window.$ = $;
    window.$$ = $$;
    window.Fmt = Fmt;
    window.Toast = Toast;
    window.Modal = Modal;
})();