/**
 * Marcbantu Africa — Profile page.
 */
(function () {
    'use strict';
    if (!window.Auth?.requireLogin()) return;


    // === Marcbantu UI guard ===
    if (!window.UI) {
        console.error('[profile.js] window.UI missing — app.js failed to load.');
        return;
    }
    // === end guard ===
    const { $, $$, Fmt, Toast, Modal } = window.UI;

    async function loadProfile() {
        const r = await Api.profile();
        if (!r.ok) { Toast.error('Failed to load profile'); return; }
        const f = r.data;

        Auth.setUser(f); // refresh cache

        // Fill form
        $$('[name="full_name"]').forEach((el) => el.value = f.full_name || '');
        $$('[name="email"]').forEach((el) => el.value = f.email || '');
        $$('[name="phone"]').forEach((el) => el.value = f.phone || '');
        $$('[name="county"]').forEach((el) => el.value = f.county || '');
        $$('[name="location"]').forEach((el) => el.value = f.location || '');
        $$('[name="language"]').forEach((el) => el.value = f.language || 'en');

        // Header
        const nameEl = $('#profile-name');
        const initialEl = $('#profile-initial');
        if (nameEl) nameEl.textContent = f.full_name;
        if (initialEl) initialEl.textContent = Fmt.initials(f.full_name);

        const statsEl = $('#profile-stats');
        if (statsEl) {
            statsEl.innerHTML = `
                <div class="stat" style="padding:14px; background:#fff; border-radius:12px; border:1px solid #e2e8dd; border-left:4px solid #d4a017;"><div style="font-size:11px; color:#4a5a4a; text-transform:uppercase; font-weight:600;">Farms</div><div style="font-size:1.4rem; font-weight:800; color:#1a3c2e;">${f.farm_count || 0}</div></div>
                <div class="stat" style="padding:14px; background:#fff; border-radius:12px; border:1px solid #e2e8dd; border-left:4px solid #d4a017;"><div style="font-size:11px; color:#4a5a4a; text-transform:uppercase; font-weight:600;">Records</div><div style="font-size:1.4rem; font-weight:800; color:#1a3c2e;">${f.record_count || 0}</div></div>
                <div class="stat" style="padding:14px; background:#fff; border-radius:12px; border:1px solid #e2e8dd; border-left:4px solid #d4a017;"><div style="font-size:11px; color:#4a5a4a; text-transform:uppercase; font-weight:600;">Enterprises</div><div style="font-size:1.4rem; font-weight:800; color:#1a3c2e;">${f.enterprise_count || 0}</div></div>
                <div class="stat" style="padding:14px; background:#fff; border-radius:12px; border:1px solid #e2e8dd; border-left:4px solid #d4a017;"><div style="font-size:11px; color:#4a5a4a; text-transform:uppercase; font-weight:600;">Tier</div><div style="font-size:1.4rem; font-weight:800; color:#1a3c2e; text-transform:capitalize;">${f.subscription_tier || 'starter'}</div></div>
            `;
        }

        loadSubscription();
    }

    async function loadSubscription() {
        const r = await Api.subscription();
        if (!r.ok) return;
        const s = r.data;
        const container = $('#subscription-info');
        if (!container) return;

        container.innerHTML = `
            <div style="padding:14px; background:#e8f0e1; border-radius:12px; margin-bottom:14px;">
                <div style="font-size:.85rem; color:#4a5a4a; text-transform:uppercase; font-weight:600;">Current Plan</div>
                <div style="font-size:1.6rem; font-weight:800; color:#1a3c2e; text-transform:capitalize;">${s.tier}</div>
                ${s.expires_at ? `<div style="font-size:.85rem; color:#4a5a4a; margin-top:4px;">Renews ${Fmt.date(s.expires_at)}</div>` : ''}
            </div>
            <div style="display:grid; gap:8px; font-size:.88rem;">
                <div style="display:flex; justify-content:space-between;"><span style="color:#4a5a4a;">Farms</span><strong>${s.usage?.farms || 0} / ${s.limits?.farms || 1}</strong></div>
                <div style="display:flex; justify-content:space-between;"><span style="color:#4a5a4a;">Records this month</span><strong>${s.usage?.records_this_month || 0} / ${s.limits?.records_per_month || 500}</strong></div>
            </div>
        `;
    }

    // ============================================================
    // UPDATE PROFILE
    // ============================================================
    function initProfileForm() {
        const form = $('#profileForm');
        if (!form) return;

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const fd = new FormData(form);
            const payload = {};
            for (const [k, v] of fd.entries()) if (v) payload[k] = v;

            const r = await Api.updateProfile(payload);
            if (!r.ok) { Toast.error(r.error); return; }
            Toast.success('Profile updated!');
            Auth.setUser(r.data);
            loadProfile();
        });
    }

    // ============================================================
    // CHANGE PASSWORD
    // ============================================================
    function initPasswordForm() {
        const form = $('#passwordForm');
        if (!form) return;

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const fd = new FormData(form);
            const r = await Api.changePassword({
                current_password: fd.get('current_password'),
                new_password: fd.get('new_password'),
            });
            if (!r.ok) { Toast.error(r.error); return; }
            Toast.success('Password changed!');
            form.reset();
        });
    }

    // ============================================================
    // REPORTS
    // ============================================================
    async function loadReports() {
        const container = $('#reports-list');
        if (!container) return;
        container.innerHTML = '<div style="text-align:center; padding:20px; color:#8a9c8c;"><i class="fas fa-spinner fa-spin"></i></div>';

        const r = await Api.reportCreditScore();
        if (!r.ok) {
            container.innerHTML = '<div style="color:#c0392b; padding:16px;">Unable to load reports</div>';
            return;
        }
        const cs = r.data;

        container.innerHTML = `
            <div style="background:#fff; border:1px solid #e2e8dd; border-radius:14px; padding:1.5rem; border-left:5px solid #d4a017;">
                <div style="font-size:.75rem; color:#4a5a4a; text-transform:uppercase; font-weight:700;">Farm Credit Score</div>
                <div style="font-size:2.2rem; font-weight:800; color:#1a3c2e; margin:.4rem 0;">${cs.score}</div>
                <div style="font-size:1rem; font-weight:600; color:${cs.score >= 650 ? '#2e7d32' : cs.score >= 550 ? '#b8860b' : '#c0392b'};">${cs.rating}</div>
                <div style="font-size:.88rem; color:#4a5a4a; margin-top:.8rem;">
                    Recommended loan limit: <strong>${Fmt.currency(cs.recommended_loan_limit)}</strong>
                </div>
                <p style="font-size:.82rem; color:#8a9c8c; margin-top:.8rem; font-style:italic;">${cs.note || ''}</p>
            </div>
            <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:12px; margin-top:16px;">
                <a href="${window.MarcbantuAPI}/api/reports/profit-loss" target="_blank" style="display:block; padding:14px; background:#fff; border:1px solid #e2e8dd; border-radius:12px; text-decoration:none; color:#1a3c2e;">
                    <i class="fas fa-file-invoice" style="color:#d4a017; font-size:1.4rem;"></i>
                    <div style="font-weight:600; margin-top:6px;">Profit & Loss</div>
                    <div style="font-size:.8rem; color:#8a9c8c;">View / download CSV</div>
                </a>
                <a href="${window.MarcbantuAPI}/api/reports/cash-flow" target="_blank" style="display:block; padding:14px; background:#fff; border:1px solid #e2e8dd; border-radius:12px; text-decoration:none; color:#1a3c2e;">
                    <i class="fas fa-chart-line" style="color:#d4a017; font-size:1.4rem;"></i>
                    <div style="font-weight:600; margin-top:6px;">Cash Flow</div>
                    <div style="font-size:.8rem; color:#8a9c8c;">Monthly statement</div>
                </a>
            </div>
        `;
    }

    document.addEventListener('DOMContentLoaded', () => {
        loadProfile();
        loadReports();
        initProfileForm();
        initPasswordForm();
    });
})();