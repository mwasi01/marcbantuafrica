/**
 * Marcbantu Africa — Finance page.
 * P&L statement, transactions, expense breakdown, enterprise performance.
 */
(function () {
    'use strict';
    if (!window.Auth?.requireLogin()) return;


    // === Marcbantu UI guard ===
    if (!window.UI) {
        console.error('[finance.js] window.UI missing — app.js failed to load.');
        return;
    }
    // === end guard ===
    const { $, $$, Fmt, Toast, Modal } = window.UI;

    let state = {
        farms: [],
        currentFarmId: null,
        transactions: [],
        page: 1,
        filters: { type: '' },
    };

    // ============================================================
    // LOAD
    // ============================================================
    async function loadFarms() {
        const r = await Api.listFarms();
        if (!r.ok) return;
        state.farms = r.data || [];
        const sel = $('#farm-selector');
        if (sel) {
            sel.innerHTML = '<option value="">All farms</option>' +
                state.farms.map((f) => `<option value="${f.id}">${f.name}</option>`).join('');
            sel.addEventListener('change', () => {
                state.currentFarmId = sel.value ? parseInt(sel.value) : null;
                loadAll();
            });
        }
        loadAll();
    }

    async function loadAll() {
        await Promise.all([
            loadDashboard(),
            loadTransactions(),
            loadExpenseBreakdown(),
        ]);
    }

    // ============================================================
    // DASHBOARD KPIs
    // ============================================================
    async function loadDashboard() {
        const params = state.currentFarmId ? { farm_id: state.currentFarmId } : {};
        const r = await Api.financeDashboard(params);
        if (!r.ok) return;
        const d = r.data;

        const container = $('#finance-kpis');
        if (!container) return;

        const thisMonth = d.this_month || {};
        const allTime = d.all_time || {};

        container.innerHTML = `
            <div class="kpi">
                <div class="kpi-label">Income (Month) <i class="fas fa-arrow-up"></i></div>
                <div class="kpi-value">${Fmt.currency(thisMonth.income)}</div>
                <div class="kpi-change ${(thisMonth.income_change_pct || 0) >= 0 ? 'up' : 'down'}">
                    <i class="fas fa-caret-${(thisMonth.income_change_pct || 0) >= 0 ? 'up' : 'down'}"></i>
                    ${Math.abs(thisMonth.income_change_pct || 0)}% vs last month
                </div>
            </div>
            <div class="kpi">
                <div class="kpi-label">Expenses (Month) <i class="fas fa-arrow-down"></i></div>
                <div class="kpi-value">${Fmt.currency(thisMonth.expenses)}</div>
                <div class="kpi-change ${(thisMonth.expense_change_pct || 0) <= 0 ? 'up' : 'down'}">
                    <i class="fas fa-caret-${(thisMonth.expense_change_pct || 0) <= 0 ? 'down' : 'up'}"></i>
                    ${Math.abs(thisMonth.expense_change_pct || 0)}% vs last month
                </div>
            </div>
            <div class="kpi">
                <div class="kpi-label">Net Profit (Month) <i class="fas fa-coins"></i></div>
                <div class="kpi-value" style="color:${(thisMonth.profit || 0) >= 0 ? '#2e7d32' : '#c0392b'};">${Fmt.currency(thisMonth.profit)}</div>
                <div class="kpi-change ${(thisMonth.profit_change_pct || 0) >= 0 ? 'up' : 'down'}">
                    <i class="fas fa-caret-${(thisMonth.profit_change_pct || 0) >= 0 ? 'up' : 'down'}"></i>
                    ${Math.abs(thisMonth.profit_change_pct || 0)}% vs last month
                </div>
            </div>
            <div class="kpi">
                <div class="kpi-label">All-Time Profit <i class="fas fa-chart-line"></i></div>
                <div class="kpi-value" style="color:${(allTime.profit || 0) >= 0 ? '#2e7d32' : '#c0392b'};">${Fmt.currency(allTime.profit)}</div>
                <div class="kpi-change" style="color:#4a5a4a;">Total: ${Fmt.currency(allTime.income)} in, ${Fmt.currency(allTime.expenses)} out</div>
            </div>
        `;

        // Render monthly trend chart if container exists
        renderTrendChart(d.monthly_trend || []);
    }

    function renderTrendChart(months) {
        const container = $('#trend-chart');
        if (!container) return;
        if (!months.length) { container.innerHTML = '<div style="text-align:center; padding:30px; color:#8a9c8c;">No data yet</div>'; return; }

        const maxVal = Math.max(...months.map((m) => Math.max(m.income || 0, m.expenses || 0)), 1);

        container.innerHTML = `
            <div style="display:flex; align-items:flex-end; gap:12px; height:200px; padding-top:1rem;">
                ${months.map((m) => {
            const ih = ((m.income || 0) / maxVal) * 100;
            const eh = ((m.expenses || 0) / maxVal) * 100;
            return `
                        <div style="flex:1; display:flex; flex-direction:column; align-items:center; gap:4px; height:100%; justify-content:flex-end;">
                            <div style="display:flex; gap:3px; width:100%; align-items:flex-end; height:100%;">
                                <div style="flex:1; background:linear-gradient(to top,#2f5d3a,#1a3c2e); height:${ih}%; border-radius:6px 6px 0 0; min-height:4px;" title="Income: ${Fmt.currency(m.income)}"></div>
                                <div style="flex:1; background:linear-gradient(to top,#e74c3c,#c0392b); height:${eh}%; border-radius:6px 6px 0 0; min-height:4px;" title="Expenses: ${Fmt.currency(m.expenses)}"></div>
                            </div>
                            <div style="font-size:.75rem; color:#4a5a4a; font-weight:600;">${m.month.slice(5)}</div>
                        </div>
                    `;
        }).join('')}
            </div>
            <div style="display:flex; gap:1.5rem; justify-content:center; margin-top:.8rem; font-size:.85rem; color:#4a5a4a;">
                <span><span style="display:inline-block; width:12px; height:12px; background:#1a3c2e; border-radius:3px; vertical-align:middle;"></span> Income</span>
                <span><span style="display:inline-block; width:12px; height:12px; background:#c0392b; border-radius:3px; vertical-align:middle;"></span> Expenses</span>
            </div>
        `;
    }

    // ============================================================
    // TRANSACTIONS
    // ============================================================
    async function loadTransactions() {
        const params = { page: state.page, page_size: 20 };
        if (state.currentFarmId) params.farm_id = state.currentFarmId;
        if (state.filters.type) params.type = state.filters.type;

        const r = await Api.listTransactions(params);
        if (!r.ok) { Toast.error('Failed to load transactions'); return; }
        state.transactions = r.data || [];
        renderTransactions();
        renderTxPagination(r.meta);
    }

    function renderTransactions() {
        const tbody = $('#transactions-table-body');
        if (!tbody) return;

        if (!state.transactions.length) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:30px; color:#8a9c8c;">No transactions</td></tr>`;
            return;
        }

        tbody.innerHTML = state.transactions.map((t) => `
            <tr style="border-bottom:1px solid #eef1ea;">
                <td style="padding:10px;">${Fmt.date(t.transaction_date)}</td>
                <td style="padding:10px;">${Fmt.titleCase(t.category)}</td>
                <td style="padding:10px;">${Fmt.truncate(t.description || '—', 40)}</td>
                <td style="padding:10px;">${t.payment_method || '—'}</td>
                <td style="padding:10px; text-align:right; font-weight:600; color:${t.type === 'income' ? '#2e7d32' : '#c0392b'};">
                    ${t.type === 'income' ? '+' : '−'} ${Fmt.currency(t.amount)}
                </td>
                <td style="padding:10px; text-align:right;">
                    <button class="btn-icon" data-action="delete-tx" data-id="${t.id}" title="Delete" style="color:#c0392b;"><i class="fas fa-trash"></i></button>
                </td>
            </tr>
        `).join('');

        $$('[data-action="delete-tx"]').forEach((el) =>
            el.addEventListener('click', async () => {
                const ok = await Modal.confirm('Delete this transaction?', 'Confirm');
                if (!ok) return;
                const r = await Api.deleteTransaction(el.dataset.id);
                if (!r.ok) { Toast.error(r.error); return; }
                Toast.success('Deleted');
                loadAll();
            }));
    }

    function renderTxPagination(meta) {
        const container = $('#tx-pagination');
        if (!container || !meta) return;
        if (meta.pages <= 1) { container.innerHTML = ''; return; }
        container.innerHTML = `
            <button class="page-btn" data-page="${Math.max(1, meta.page - 1)}" ${meta.page === 1 ? 'disabled' : ''}><i class="fas fa-chevron-left"></i></button>
            <span style="margin:0 12px; color:#4a5a4a; font-size:13px;">Page ${meta.page} of ${meta.pages} (${meta.total} total)</span>
            <button class="page-btn" data-page="${Math.min(meta.pages, meta.page + 1)}" ${meta.page === meta.pages ? 'disabled' : ''}><i class="fas fa-chevron-right"></i></button>
        `;
        $$('#tx-pagination .page-btn').forEach((el) =>
            el.addEventListener('click', () => {
                const p = parseInt(el.dataset.page);
                if (p) { state.page = p; loadTransactions(); }
            }));
    }

    // ============================================================
    // EXPENSE BREAKDOWN
    // ============================================================
    async function loadExpenseBreakdown() {
        const params = state.currentFarmId ? { farm_id: state.currentFarmId } : {};
        const r = await Api.expenseBreakdown(params);
        if (!r.ok) return;
        const d = r.data;
        const container = $('#expense-breakdown');
        if (!container) return;

        if (!d.by_category?.length) {
            container.innerHTML = '<div style="text-align:center; padding:20px; color:#8a9c8c;">No expenses recorded</div>';
            return;
        }

        container.innerHTML = d.by_category.map((c) => `
            <div style="margin-bottom:1rem;">
                <div style="display:flex; justify-content:space-between; margin-bottom:.3rem; font-size:.9rem;">
                    <span style="color:#4a5a4a;">${Fmt.titleCase(c.category)}</span>
                    <strong style="color:#1a3c2e;">${Fmt.currency(c.total)} <span style="color:#8a9c8c; font-weight:400;">(${c.percent}%)</span></strong>
                </div>
                <div style="height:8px; background:#eef1ea; border-radius:20px; overflow:hidden;">
                    <div style="width:${c.percent}%; height:100%; background:linear-gradient(90deg,#2f5d3a,#d4a017); border-radius:20px; transition:width .4s;"></div>
                </div>
            </div>
        `).join('');
    }

    // ============================================================
    // ADD TRANSACTION MODAL
    // ============================================================
    function openTransactionModal() {
        if (!state.farms.length) {
            Toast.warning('Add a farm first');
            return;
        }

        const modal = Modal.open(`
            <div style="padding:28px; max-width:520px;">
                <h2 style="margin:0 0 20px; color:#1a3c2e;">
                    <i class="fas fa-plus-circle" style="color:#d4a017;"></i> Add Transaction
                </h2>
                <form id="txForm" style="display:flex; flex-direction:column; gap:14px;">
                    <label style="display:flex; flex-direction:column; gap:6px;">
                        <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Farm *</span>
                        <select name="farm_id" required style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                            ${state.farms.map((f) => `<option value="${f.id}">${f.name}</option>`).join('')}
                        </select>
                    </label>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">
                        <label style="display:flex; flex-direction:column; gap:6px;">
                            <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Type *</span>
                            <select name="type" required style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                                <option value="income">Income</option>
                                <option value="expense">Expense</option>
                            </select>
                        </label>
                        <label style="display:flex; flex-direction:column; gap:6px;">
                            <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Amount (KES) *</span>
                            <input type="number" step="0.01" name="amount" required style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                        </label>
                    </div>
                    <label style="display:flex; flex-direction:column; gap:6px;">
                        <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Category *</span>
                        <input name="category" required placeholder="e.g. feeds, milk_sales, labour" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                    </label>
                    <label style="display:flex; flex-direction:column; gap:6px;">
                        <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Description</span>
                        <input name="description" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                    </label>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">
                        <label style="display:flex; flex-direction:column; gap:6px;">
                            <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Payment Method</span>
                            <select name="payment_method" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                                <option value="cash">Cash</option>
                                <option value="mpesa">M-Pesa</option>
                                <option value="bank">Bank</option>
                                <option value="airtel">Airtel Money</option>
                            </select>
                        </label>
                        <label style="display:flex; flex-direction:column; gap:6px;">
                            <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Date *</span>
                            <input type="date" name="transaction_date" required value="${new Date().toISOString().slice(0, 10)}" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                        </label>
                    </div>
                    <div style="display:flex; gap:12px; justify-content:flex-end;">
                        <button type="button" class="btn-outline" data-action="cancel">Cancel</button>
                        <button type="submit" class="btn-primary">Save</button>
                    </div>
                </form>
            </div>
        `);

        modal.querySelector('[data-action="cancel"]').addEventListener('click', () => Modal.close(modal));
        modal.querySelector('#txForm').addEventListener('submit', async (ev) => {
            ev.preventDefault();
            const fd = new FormData(ev.target);
            const payload = {};
            for (const [k, v] of fd.entries()) payload[k] = k === 'amount' ? parseFloat(v) : v;
            payload.farm_id = parseInt(payload.farm_id);

            const r = await Api.createTransaction(payload);
            if (!r.ok) { Toast.error(r.error); return; }
            Toast.success('Transaction saved!');
            Modal.close(modal);
            loadAll();
        });
    }

    // ============================================================
    // BOOT
    // ============================================================
    document.addEventListener('DOMContentLoaded', () => {
        loadFarms();

        $$('[data-action="new-transaction"]').forEach((el) =>
            el.addEventListener('click', openTransactionModal));

        const typeFilter = $('#tx-type-filter');
        if (typeFilter) {
            typeFilter.addEventListener('change', () => {
                state.filters.type = typeFilter.value;
                state.page = 1;
                loadTransactions();
            });
        }
    });
})();