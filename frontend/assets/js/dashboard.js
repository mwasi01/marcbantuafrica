/**
 * Marcbantu Africa — Dashboard page.
 * Loads KPIs, activity, tasks, market prices from the API.
 */

(function () {
    'use strict';

    if (!window.Auth?.requireLogin()) return;

    const { $, $$, Fmt, Toast } = window.UI || {};

    async function loadDashboard() {
        // KPI container
        const kpiContainer = $('#kpi-container');
        if (kpiContainer) {
            kpiContainer.innerHTML = Array(4).fill(0).map(() => `
                <div class="kpi" style="opacity:0.5;">
                    <div class="kpi-label">Loading...<i class="fas fa-spinner fa-spin"></i></div>
                    <div class="kpi-value">—</div>
                    <div class="kpi-change">—</div>
                </div>
            `).join('');
        }

        const result = await Api.dashboard();
        if (!result.ok) {
            Toast.error(result.error || 'Failed to load dashboard');
            return;
        }

        const data = result.data;

        // If the farmer has no farms, show a prominent setup CTA
        if (data.needs_setup) {
            renderGreeting(data.farmer);
            renderNeedsSetup(data);
            return;
        }

        renderGreeting(data.farmer);
        renderKPIs(data);
        renderRecentRecords(data.recent_records);
        renderRecentTransactions(data.recent_transactions);
        renderMarketPrices(data.market_prices);
        renderNotifications(data.notifications);
        updateTaskList(data);
    }

    function renderGreeting(farmer) {
        if (!farmer) return;
        $$('.user-greeting').forEach((el) => {
            const hour = new Date().getHours();
            const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
            const name = (farmer.full_name || 'farmer').split(' ')[0];
            el.textContent = `${greeting}, ${name} 👋`;
        });
    }

    function renderNeedsSetup(data) {
        const container = $('#kpi-container');
        if (!container) return;
        container.innerHTML = `
            <div class="kpi" style="grid-column:1/-1; background:linear-gradient(135deg,#2f5d3a,#1a3c2e); color:#fff; padding:2rem; border-radius:20px; border:2px solid #d4a017;">
                <div style="font-size:1.3rem; font-weight:800; margin-bottom:.5rem;">
                    <i class="fas fa-seedling" style="color:#e6b422;"></i> Welcome to Marcbantu!
                </div>
                <p style="color:#c8d6ca; margin:0 0 1.2rem; font-size:.95rem;">
                    You don't have any farms yet. Create your first farm to unlock records, planning, finance, weather, and the rest of your dashboard.
                </p>
                <button class="btn-primary" id="create-first-farm" style="font-size:1rem;">
                    <i class="fas fa-plus-circle"></i> Create Your First Farm
                </button>
            </div>
        `;
        const btn = document.getElementById('create-first-farm');
        if (btn) {
            btn.addEventListener('click', () => {
                window.Farm.openCreateModal(() => loadDashboard());
            });
        }
    }

    function renderKPIs(data) {
        const container = $('#kpi-container');
        if (!container) return;

        const finance = data.finance || {};

        const kpis = [
            {
                label: 'Total Income (Month)',
                value: Fmt.currency(finance.this_month_income),
                change: finance.income_change_pct,
                icon: 'fa-arrow-up',
                positive: (finance.income_change_pct || 0) >= 0,
            },
            {
                label: 'Total Expenses (Month)',
                value: Fmt.currency(finance.this_month_expenses),
                change: finance.expense_change_pct,
                icon: 'fa-arrow-down',
                positive: (finance.expense_change_pct || 0) <= 0, // lower is better
            },
            {
                label: 'Net Profit',
                value: Fmt.currency(finance.this_month_profit),
                change: null,
                icon: 'fa-coins',
                positive: (finance.this_month_profit || 0) >= 0,
            },
            {
                label: 'Active Enterprises',
                value: String(data.enterprises || 0),
                change: null,
                icon: 'fa-layer-group',
                positive: true,
                subtext: `${data.farms || 0} farm(s)`,
            },
        ];

        container.innerHTML = kpis.map((k) => `
            <div class="kpi">
                <div class="kpi-label">${k.label} <i class="fas ${k.icon}"></i></div>
                <div class="kpi-value" style="${k.label.includes('Profit') && !k.positive ? 'color:#c0392b' : k.label.includes('Profit') ? 'color:#2e7d32' : ''}">${k.value}</div>
                ${k.change != null
                ? `<div class="kpi-change ${k.positive ? 'up' : 'down'}">
                         <i class="fas fa-caret-${k.positive ? 'up' : 'down'}"></i>
                         ${Math.abs(k.change)}% vs last month
                       </div>`
                : k.subtext
                    ? `<div class="kpi-change" style="color:#4a5a4a;">${k.subtext}</div>`
                    : ''}
            </div>
        `).join('');
    }

    function renderRecentRecords(records) {
        const container = $('#recent-records');
        if (!container) return;
        if (!records || !records.length) {
            container.innerHTML = `<div style="padding:20px; text-align:center; color:#8a9c8c; font-size:13px;">No records yet. <a href="records.html" style="color:#1a3c2e; font-weight:600;">Add your first →</a></div>`;
            return;
        }
        container.innerHTML = records.map((r) => `
            <li style="display:flex; gap:12px; padding:12px 0; border-bottom:1px dashed #eef1ea; align-items:flex-start;">
                <div style="width:36px; height:36px; border-radius:10px; background:#e8f0e1; color:#1a3c2e; display:flex; align-items:center; justify-content:center; font-size:14px; flex-shrink:0;">
                    <i class="fas fa-${recordIcon(r.record_type)}"></i>
                </div>
                <div style="flex:1;">
                    <div style="font-weight:600; font-size:14px; color:#1a3c2e;">${Fmt.titleCase(r.activity || r.record_type)}</div>
                    <div style="font-size:12px; color:#4a5a4a; margin-top:2px;">${Fmt.truncate(r.description || '', 60)}</div>
                </div>
                <div style="font-size:11px; color:#8a9c8c; white-space:nowrap;">${Fmt.dateRelative(r.record_date)}</div>
            </li>
        `).join('');
    }

    function recordIcon(type) {
        return {
            crop_activity: 'seedling',
            livestock: 'cow',
            poultry: 'egg',
            input: 'boxes',
            harvest: 'wheat-awn',
            sale: 'tag',
            expense: 'receipt',
            observation: 'eye',
        }[type] || 'clipboard';
    }

    function renderRecentTransactions(txs) {
        const container = $('#recent-transactions');
        if (!container) return;
        if (!txs || !txs.length) {
            container.innerHTML = `<div style="padding:20px; text-align:center; color:#8a9c8c; font-size:13px;">No transactions yet</div>`;
            return;
        }
        container.innerHTML = txs.map((t) => {
            const isIncome = t.type === 'income';
            return `
                <li style="display:flex; gap:12px; padding:12px 0; border-bottom:1px dashed #eef1ea; align-items:flex-start;">
                    <div style="width:36px; height:36px; border-radius:10px; background:${isIncome ? '#e8f0e1' : '#fef3d0'}; color:${isIncome ? '#2e7d32' : '#b8860b'}; display:flex; align-items:center; justify-content:center; font-size:14px; flex-shrink:0;">
                        <i class="fas fa-${isIncome ? 'arrow-up' : 'arrow-down'}"></i>
                    </div>
                    <div style="flex:1;">
                        <div style="font-weight:600; font-size:14px; color:#1a3c2e;">${Fmt.titleCase(t.category)}</div>
                        <div style="font-size:12px; color:#4a5a4a; margin-top:2px;">${Fmt.truncate(t.description || '', 50)}</div>
                    </div>
                    <div style="font-size:13px; font-weight:700; white-space:nowrap; color:${isIncome ? '#2e7d32' : '#c0392b'};">
                        ${isIncome ? '+' : '−'} ${Fmt.currency(t.amount)}
                    </div>
                </li>
            `;
        }).join('');
    }

    function renderMarketPrices(prices) {
        const container = $('#market-prices');
        if (!container) return;
        if (!prices || !prices.length) {
            container.innerHTML = `<div style="padding:20px; text-align:center; color:#8a9c8c; font-size:13px;">No prices available</div>`;
            return;
        }
        container.innerHTML = prices.map((p) => `
            <li style="display:flex; gap:12px; padding:12px 0; border-bottom:1px dashed #eef1ea; align-items:center;">
                <div style="width:36px; height:36px; border-radius:10px; background:#e8f0e1; color:#2e7d32; display:flex; align-items:center; justify-content:center; font-size:14px; flex-shrink:0;">
                    <i class="fas fa-seedling"></i>
                </div>
                <div style="flex:1;">
                    <div style="font-weight:600; font-size:14px; color:#1a3c2e;">${p.crop}</div>
                    <div style="font-size:12px; color:#4a5a4a; margin-top:2px;">${p.market}</div>
                </div>
                <div style="font-size:14px; font-weight:700; color:#2e7d32; white-space:nowrap;">
                    ${Fmt.currency(p.price)}/${p.unit}
                </div>
            </li>
        `).join('');
    }

    function renderNotifications(notifications) {
        const container = $('#dashboard-notifications');
        if (!container) return;
        if (!notifications || !notifications.length) {
            container.innerHTML = `<div style="padding:20px; text-align:center; color:#8a9c8c; font-size:13px;">All caught up! No new notifications.</div>`;
            return;
        }
        container.innerHTML = notifications.map((n) => `
            <li style="display:flex; gap:12px; padding:12px 0; border-bottom:1px dashed #eef1ea; align-items:flex-start;">
                <div style="width:36px; height:36px; border-radius:10px; background:#fef3d0; color:#b8860b; display:flex; align-items:center; justify-content:center; font-size:14px; flex-shrink:0;">
                    <i class="fas fa-bell"></i>
                </div>
                <div style="flex:1;">
                    <div style="font-weight:600; font-size:14px; color:#1a3c2e;">${n.title}</div>
                    <div style="font-size:12px; color:#4a5a4a; margin-top:2px;">${n.message}</div>
                    <div style="font-size:11px; color:#8a9c8c; margin-top:4px;">${Fmt.dateRelative(n.created_at)}</div>
                </div>
            </li>
        `).join('');
    }

    async function updateTaskList(data) {
        const container = $('#task-list');
        if (!container) return;

        if (data.pending_tasks === 0) {
            container.innerHTML = `<div style="padding:20px; text-align:center; color:#8a9c8c; font-size:13px;">No pending tasks 🎉</div>`;
            return;
        }

        const tasksResult = await Api.listTasks({ status: 'pending' });
        if (!tasksResult.ok) return;
        const tasks = (tasksResult.data || []).slice(0, 5);

        if (!tasks.length) {
            container.innerHTML = `<div style="padding:20px; text-align:center; color:#8a9c8c; font-size:13px;">No pending tasks 🎉</div>`;
            return;
        }

        container.innerHTML = tasks.map((t) => `
            <li style="display:flex; align-items:center; gap:12px; padding:10px 0; border-bottom:1px dashed #eef1ea;">
                <div class="task-check" data-task-id="${t.id}" style="width:22px; height:22px; border-radius:6px; border:2px solid #e2e8dd; cursor:pointer; display:flex; align-items:center; justify-content:center; flex-shrink:0; transition:all 0.2s;">
                    <i class="fas fa-check" style="opacity:0; color:#fff; font-size:11px;"></i>
                </div>
                <div style="flex:1; font-size:14px; color:#1a3c2e;">${t.title}</div>
                <span style="font-size:10px; padding:2px 8px; border-radius:20px; font-weight:700; text-transform:uppercase; background:${t.priority === 'urgent' ? '#fde8e8' :
                t.priority === 'high' ? '#fde8e8' :
                    t.priority === 'medium' ? '#fef3d0' :
                        '#e8f0e1'
            }; color:${t.priority === 'urgent' ? '#c0392b' :
                t.priority === 'high' ? '#c0392b' :
                    t.priority === 'medium' ? '#b8860b' :
                        '#2e7d32'
            };">${t.priority}</span>
            </li>
        `).join('');

        // Wire checkbox clicks
        $$('.task-check').forEach((el) => {
            el.addEventListener('click', async () => {
                const taskId = el.dataset.taskId;
                el.style.background = '#2f5d3a';
                el.style.borderColor = '#2f5d3a';
                el.querySelector('i').style.opacity = '1';

                const result = await Api.completeTask(taskId);
                if (!result.ok) {
                    el.style.background = 'transparent';
                    el.style.borderColor = '#e2e8dd';
                    el.querySelector('i').style.opacity = '0';
                    Toast.error('Failed to complete task');
                    return;
                }
                Toast.success('Task completed!');
                setTimeout(() => loadDashboard(), 800);
            });
        });
    }

    // ============================================================
    // QUICK ACTION BUTTONS
    // ============================================================
    function initQuickActions() {
        $$('[data-quick-action]').forEach((btn) => {
            btn.addEventListener('click', async (e) => {
                e.preventDefault();
                const action = btn.dataset.quickAction;
                if (action === 'logout') return; // handled by app.js
                if (action) window.location.href = `${action}.html`;
            });
        });
    }

    // ============================================================
    // BOOT
    // ============================================================
    document.addEventListener('DOMContentLoaded', () => {
        loadDashboard();
        initQuickActions();
        // Refresh every 60s
        setInterval(loadDashboard, 60000);
    });
})();