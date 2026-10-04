/**
 * Marcbantu Africa — Auth page handlers.
 * Wires up login.html and register.html forms.
 */

(function () {
    'use strict';

    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    // ============================================================
    // UI HELPERS
    // ============================================================
    function showError(form, message) {
        const box = form.querySelector('.form-error') || createErrorBox(form);
        box.textContent = message;
        box.style.display = 'block';
        setTimeout(() => { box.style.display = 'none'; }, 6000);
    }

    function createErrorBox(form) {
        const box = document.createElement('div');
        box.className = 'form-error';
        box.style.cssText = `
            background:#fde8e8; color:#c0392b; padding:12px 16px;
            border-radius:10px; margin-bottom:15px; font-size:14px;
            border-left:4px solid #c0392b;
        `;
        form.insertBefore(box, form.firstChild);
        return box;
    }

    function showSuccess(form, message) {
        const box = form.querySelector('.form-success') || createSuccessBox(form);
        box.textContent = message;
        box.style.display = 'block';
    }

    function createSuccessBox(form) {
        const box = document.createElement('div');
        box.className = 'form-success';
        box.style.cssText = `
            background:#e8f0e1; color:#2e7d32; padding:12px 16px;
            border-radius:10px; margin-bottom:15px; font-size:14px;
            border-left:4px solid #2e7d32;
        `;
        form.insertBefore(box, form.firstChild);
        return box;
    }

    function setLoading(btn, loading, text = null) {
        if (!btn) return;
        btn.disabled = loading;
        if (loading) {
            btn.dataset.originalText = btn.innerHTML;
            btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${text || 'Please wait...'}`;
        } else {
            btn.innerHTML = btn.dataset.originalText || btn.innerHTML;
        }
    }

    // ============================================================
    // LOGIN
    // ============================================================
    function bindLoginForm() {
        const form = $('#loginForm');
        if (!form) return;

        // Show expired message if redirected
        if (new URLSearchParams(window.location.search).get('expired') === '1') {
            showError(form, 'Your session expired. Please log in again.');
        }

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = form.querySelector('button[type="submit"]');
            const phone = form.querySelector('[name="phone"]')?.value.trim();
            const password = form.querySelector('[name="password"]')?.value;

            if (!phone || !password) {
                showError(form, 'Please enter phone and password.');
                return;
            }

            setLoading(btn, true, 'Logging in...');
            const result = await Api.login({ phone, password });
            setLoading(btn, false);

            if (!result.ok) {
                showError(form, result.error || 'Login failed.');
                return;
            }

            const { token, farmer } = result.data;
            Auth.setToken(token);
            Auth.setUser(farmer);

            showSuccess(form, 'Login successful! Redirecting...');

            // Determine redirect
            const redirect = new URLSearchParams(window.location.search).get('redirect');
            setTimeout(() => {
                window.location.href = redirect || '/dashboard.html';
            }, 500);
        });
    }

    // ============================================================
    // REGISTER
    // ============================================================
    function bindRegisterForm() {
        const form = $('#registerForm');
        if (!form) return;

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = form.querySelector('button[type="submit"]');
            const data = {
                phone: form.querySelector('[name="phone"]')?.value.trim(),
                full_name: form.querySelector('[name="full_name"]')?.value.trim(),
                password: form.querySelector('[name="password"]')?.value,
                email: form.querySelector('[name="email"]')?.value.trim() || undefined,
                county: form.querySelector('[name="county"]')?.value.trim() || undefined,
                location: form.querySelector('[name="location"]')?.value.trim() || undefined,
            };

            if (!data.phone || !data.full_name || !data.password) {
                showError(form, 'Please fill in all required fields.');
                return;
            }

            if (data.password.length < 6) {
                showError(form, 'Password must be at least 6 characters.');
                return;
            }

            setLoading(btn, true, 'Creating account...');
            const result = await Api.register(data);
            setLoading(btn, false);

            if (!result.ok) {
                showError(form, result.error || 'Registration failed.');
                return;
            }

            const { token, farmer } = result.data;
            Auth.setToken(token);
            Auth.setUser(farmer);

            showSuccess(form, 'Account created! Redirecting to dashboard...');

            setTimeout(() => {
                window.location.href = '/dashboard.html';
            }, 800);
        });
    }

    // ============================================================
    // LOGOUT BUTTON
    // ============================================================
    function bindLogout() {
        document.querySelectorAll('[data-action="logout"]').forEach((el) => {
            el.addEventListener('click', async (e) => {
                e.preventDefault();
                if (!confirm('Log out of Marcbantu?')) return;
                try {
                    await Api.logout();
                } catch { }
                Auth.logout('/login.html');
            });
        });
    }

    // ============================================================
    // AUTO-REDIRECT IF ALREADY LOGGED IN
    // ============================================================
    function redirectIfLoggedIn() {
        const path = window.location.pathname;
        if ((path.includes('login') || path.includes('register')) && Auth.isLoggedIn() && !Auth.isExpired()) {
            window.location.href = '/dashboard.html';
        }
    }

    // ============================================================
    // BOOT
    // ============================================================
    document.addEventListener('DOMContentLoaded', () => {
        redirectIfLoggedIn();
        bindLoginForm();
        bindRegisterForm();
        bindLogout();
    });
})();