/**
 * Marcbantu Africa — Planning page.
 * Season calendar, enterprise budgets, cash flow forecast.
 */
(function () {
    'use strict';
    if (!window.Auth?.requireLogin()) return;

    const { $, $$, Fmt, Toast, Modal } = window.UI;

    let state = {
        farms: [],
        currentFarmId: null,
        enterprises: [],
        budgets: [],
        cashFlow: null,
    };

    // ============================================================
    // LOAD
    // ============================================================
    async function loadFarms() {
        const result = await Api.listFarms();
        if (!result.ok) { Toast.error('Failed to load farms'); return; }
        state.farms = result.data || [];
        renderFarmSelector();
        if (state.farms.length) {
            state.currentFarmId = state.currentFarmId || state.farms[0].id;
            await Promise.all([
                loadEnterprises(),
                loadBudgets(),
                loadCashFlow(),
            ]);
        } else {
            renderNoFarmsPanel();
        }
    }

    function renderNoFarmsPanel() {
        const container = $('#enterprises-list');
        if (container) {
            container.innerHTML = `
                <div style="text-align:center; padding:40px 20px; background:#fbfcf9; border:2px dashed #d4a017; border-radius:16px;">
                    <i class="fas fa-seedling" style="font-size:3rem; color:#d4a017;"></i>
                    <h3 style="color:#1a3c2e; margin:1rem 0 .5rem;">No farms yet</h3>
                    <p style="color:#4a5a4a; margin:0 0 1.2rem; font-size:.95rem;">
                        Create your first farm to start planning enterprises, budgets, and cash flow.
                    </p>
                    <button class="btn-primary" id="create-farm-planning">
                        <i class="fas fa-plus-circle"></i> Create Farm
                    </button>
                </div>
            `;
            const btn = document.getElementById('create-farm-planning');
            if (btn) {
                btn.addEventListener('click', () => {
                    window.Farm.openCreateModal(() => loadFarms());
                });
            }
        }
        const budg = $('#budgets-list');
        if (budg) budg.innerHTML = '<div style="text-align:center; padding:20px; color:#8a9c8c;">Create a farm first.</div>';
        const cf = $('#cash-flow');
        if (cf) cf.innerHTML = '<div style="text-align:center; padding:20px; color:#8a9c8c;">Create a farm first.</div>';
    }

    function renderFarmSelector() {
        const sel = $('#farm-selector');
        if (!sel) return;
        sel.innerHTML = state.farms.map((f) =>
            `<option value="${f.id}" ${f.id === state.currentFarmId ? 'selected' : ''}>${f.name}</option>`
        ).join('');
        sel.addEventListener('change', async () => {
            state.currentFarmId = parseInt(sel.value);
            await Promise.all([loadEnterprises(), loadBudgets(), loadCashFlow()]);
        });
    }

    // ============================================================
    // ENTERPRISES / SEASON PLANNER
    // ============================================================
    async function loadEnterprises() {
        if (!state.currentFarmId) return;
        const result = await Api.listEnterprises(state.currentFarmId);
        if (!result.ok) { Toast.error('Failed to load enterprises'); return; }
        state.enterprises = result.data || [];
        renderEnterprises();
    }

    function renderEnterprises() {
        const container = $('#enterprises-list');
        if (!container) return;

        if (!state.enterprises.length) {
            container.innerHTML = `<div style="text-align:center; padding:40px; color:#8a9c8c;">No enterprises yet. Add your first crop or livestock enterprise.</div>`;
            return;
        }

        container.innerHTML = state.enterprises.map((e) => `
            <div class="enterprise-card" style="background:#fff; border:1px solid #e2e8dd; border-radius:16px; padding:1.2rem; margin-bottom:1rem; border-left:5px solid ${e.status === 'active' ? '#2f5d3a' : '#d4a017'};">
                <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:.6rem;">
                    <div>
                        <h4 style="color:#1a3c2e; font-size:1rem; margin:0 0 .3rem; display:flex; align-items:center; gap:8px;">
                            <i class="fas fa-${enterpriseIcon(e.type)}" style="color:#d4a017;"></i>
                            ${e.name}
                        </h4>
                        <div style="font-size:.82rem; color:#4a5a4a;">
                            ${Fmt.titleCase(e.type)} · ${e.species_or_crop || '—'}
                            ${e.quantity ? ` · ${e.quantity} ${e.unit || ''}` : ''}
                        </div>
                    </div>
                    <span style="display:inline-block; padding:3px 10px; border-radius:20px; font-size:11px; font-weight:700; text-transform:uppercase; background:${statusBg(e.status)}; color:${statusColor(e.status)};">
                        ${e.status}
                    </span>
                </div>
                <div style="display:flex; gap:1.2rem; margin-top:.6rem; flex-wrap:wrap; font-size:.85rem;">
                    <span style="color:#4a5a4a;">Started: <strong style="color:#1a3c2e;">${Fmt.date(e.start_date)}</strong></span>
                    ${e.expected_end_date ? `<span style="color:#4a5a4a;">Ends: <strong style="color:#1a3c2e;">${Fmt.date(e.expected_end_date)}</strong></span>` : ''}
                    <span style="color:#4a5a4a;">Records: <strong style="color:#1a3c2e;">${e.record_count || 0}</strong></span>
                </div>
                <div style="margin-top:.8rem;">
                    <button class="btn-icon" data-action="edit-enterprise" data-id="${e.id}" title="Edit"><i class="fas fa-edit"></i></button>
                    <button class="btn-icon" data-action="enterprise-perf" data-id="${e.id}" title="Performance"><i class="fas fa-chart-line"></i></button>
                    <button class="btn-icon" data-action="delete-enterprise" data-id="${e.id}" title="Delete" style="color:#c0392b;"><i class="fas fa-trash"></i></button>
                </div>
            </div>
        `).join('');

        // Wire
        $$('[data-action="edit-enterprise"]').forEach((el) =>
            el.addEventListener('click', () => openEnterpriseModal(el.dataset.id)));
        $$('[data-action="delete-enterprise"]').forEach((el) =>
            el.addEventListener('click', () => deleteEnterprise(el.dataset.id)));
        $$('[data-action="enterprise-perf"]').forEach((el) =>
            el.addEventListener('click', () => viewEnterprisePerformance(el.dataset.id)));
    }

    function enterpriseIcon(type) {
        return { crop: 'seedling', livestock: 'cow', poultry: 'egg', horticulture: 'carrot', aquaculture: 'fish', mixed: 'layer-group' }[type] || 'layer-group';
    }
    function statusBg(s) { return { active: '#e8f0e1', planning: '#fef3d0', harvested: '#e3f2fd', sold: '#f3e5f5', closed: '#f5f5f5' }[s] || '#f5f5f5'; }
    function statusColor(s) { return { active: '#2e7d32', planning: '#b8860b', harvested: '#1565c0', sold: '#6a1b9a', closed: '#616161' }[s] || '#616161'; }

    function openEnterpriseModal(enterpriseId = null) {
        const isEdit = !!enterpriseId;
        const e = isEdit ? state.enterprises.find((x) => x.id == enterpriseId) : null;

        const modal = Modal.open(`
            <div style="padding:28px; max-width:560px;">
                <h2 style="margin:0 0 20px; color:#1a3c2e;">
                    <i class="fas fa-${isEdit ? 'edit' : 'plus-circle'}" style="color:#d4a017;"></i>
                    ${isEdit ? 'Edit Enterprise' : 'Add Enterprise'}
                </h2>
                <form id="enterpriseForm" style="display:flex; flex-direction:column; gap:14px;">
                    <label style="display:flex; flex-direction:column; gap:6px;">
                        <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Name *</span>
                        <input name="name" required value="${e?.name || ''}" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                    </label>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">
                        <label style="display:flex; flex-direction:column; gap:6px;">
                            <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Type *</span>
                            <select name="type" required style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                                ${['crop', 'livestock', 'poultry', 'horticulture', 'aquaculture', 'mixed', 'other'].map((t) =>
            `<option value="${t}" ${e?.type === t ? 'selected' : ''}>${Fmt.titleCase(t)}</option>`
        ).join('')}
                            </select>
                        </label>
                        <label style="display:flex; flex-direction:column; gap:6px;">
                            <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Species/Crop</span>
                            <input name="species_or_crop" value="${e?.species_or_crop || ''}" placeholder="e.g. Friesian, Maize" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                        </label>
                    </div>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">
                        <label style="display:flex; flex-direction:column; gap:6px;">
                            <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Quantity</span>
                            <input type="number" step="0.01" name="quantity" value="${e?.quantity || ''}" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                        </label>
                        <label style="display:flex; flex-direction:column; gap:6px;">
                            <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Unit</span>
                            <input name="unit" value="${e?.unit || ''}" placeholder="acres, cows, birds" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                        </label>
                    </div>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">
                        <label style="display:flex; flex-direction:column; gap:6px;">
                            <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Start Date</span>
                            <input type="date" name="start_date" value="${e?.start_date || ''}" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                        </label>
                        <label style="display:flex; flex-direction:column; gap:6px;">
                            <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Expected End</span>
                            <input type="date" name="expected_end_date" value="${e?.expected_end_date || ''}" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                        </label>
                    </div>
                    <div style="display:flex; gap:12px; justify-content:flex-end; margin-top:10px;">
                        <button type="button" class="btn-outline" data-action="cancel">Cancel</button>
                        <button type="submit" class="btn-primary">${isEdit ? 'Save' : 'Add'}</button>
                    </div>
                </form>
            </div>
        `);

        modal.querySelector('[data-action="cancel"]').addEventListener('click', () => Modal.close(modal));
        modal.querySelector('#enterpriseForm').addEventListener('submit', async (ev) => {
            ev.preventDefault();
            const formData = new FormData(ev.target);
            const payload = {};
            for (const [k, v] of formData.entries()) if (v) payload[k] = k === 'quantity' ? parseFloat(v) : v;

            const result = isEdit
                ? await Api.updateEnterprise(enterpriseId, payload)
                : await Api.createEnterprise(state.currentFarmId, payload);

            if (!result.ok) { Toast.error(result.error); return; }
            Toast.success(isEdit ? 'Enterprise updated!' : 'Enterprise added!');
            Modal.close(modal);
            await loadEnterprises();
        });
    }

    async function deleteEnterprise(id) {
        const ok = await Modal.confirm('Delete this enterprise? Records will be archived.', 'Confirm');
        if (!ok) return;
        const result = await Api.deleteEnterprise(id);
        if (!result.ok) { Toast.error(result.error); return; }
        Toast.success('Enterprise deleted');
        loadEnterprises();
    }

    async function viewEnterprisePerformance(id) {
        const result = await Api.enterprisePerformance(id);
        if (!result.ok) { Toast.error(result.error); return; }
        const d = result.data;

        Modal.open(`
            <div style="padding:28px; max-width:640px;">
                <h2 style="margin:0 0 16px; color:#1a3c2e;">${d.enterprise.name} — Performance</h2>
                <div style="display:grid; grid-template-columns:repeat(2,1fr); gap:12px; margin-bottom:20px;">
                    <div style="padding:14px; background:#e8f0e1; border-radius:12px;">
                        <div style="font-size:11px; color:#4a5a4a; text-transform:uppercase; font-weight:600;">Income</div>
                        <div style="font-size:1.4rem; font-weight:800; color:#2e7d32;">${Fmt.currency(d.totals.income)}</div>
                    </div>
                    <div style="padding:14px; background:#fef3d0; border-radius:12px;">
                        <div style="font-size:11px; color:#4a5a4a; text-transform:uppercase; font-weight:600;">Expenses</div>
                        <div style="font-size:1.4rem; font-weight:800; color:#b8860b;">${Fmt.currency(d.totals.expenses)}</div>
                    </div>
                    <div style="padding:14px; background:#fff; border:1px solid #e2e8dd; border-radius:12px; grid-column:span 2;">
                        <div style="font-size:11px; color:#4a5a4a; text-transform:uppercase; font-weight:600;">Net Profit</div>
                        <div style="font-size:1.6rem; font-weight:800; color:${d.totals.profit >= 0 ? '#2e7d32' : '#c0392b'};">${Fmt.currency(d.totals.profit)}</div>
                        <div style="font-size:12px; color:#4a5a4a; margin-top:4px;">Margin: ${d.totals.margin_percent}%</div>
                    </div>
                </div>
                <button class="btn-outline" style="width:100%;" onclick="this.closest('.modal-overlay').classList.remove('open')">Close</button>
            </div>
        `);
    }

    // ============================================================
    // BUDGETS
    // ============================================================
    async function loadBudgets() {
        if (!state.currentFarmId) return;
        const result = await Api.listBudgets({ farm_id: state.currentFarmId });
        if (!result.ok) return;
        state.budgets = result.data || [];
        renderBudgets();
    }

    function renderBudgets() {
        const container = $('#budgets-list');
        if (!container) return;
        if (!state.budgets.length) {
            container.innerHTML = `<div style="text-align:center; padding:30px; color:#8a9c8c;">No budgets yet.</div>`;
            return;
        }

        container.innerHTML = state.budgets.map((b) => {
            const profit = (b.total_income || 0) - (b.total_expenses || 0);
            return `
                <div style="background:#fff; border:1px solid #e2e8dd; border-radius:14px; padding:1.2rem; margin-bottom:1rem; border-left:5px solid #d4a017;">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:1rem; flex-wrap:wrap;">
                        <div>
                            <h4 style="color:#1a3c2e; margin:0 0 .3rem; font-size:1rem;">${b.name}</h4>
                            <div style="font-size:.82rem; color:#4a5a4a;">
                                ${Fmt.date(b.period_start)} → ${Fmt.date(b.period_end)}
                            </div>
                        </div>
                        <span style="font-size:.75rem; padding:2px 8px; border-radius:20px; background:#fef3d0; color:#b8860b; font-weight:700;">
                            ${b.item_count || 0} items
                        </span>
                    </div>
                    <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:1rem; margin-top:.8rem; font-size:.85rem;">
                        <div><span style="color:#4a5a4a;">Income:</span> <strong style="color:#2e7d32;">${Fmt.currency(b.total_income)}</strong></div>
                        <div><span style="color:#4a5a4a;">Expenses:</span> <strong style="color:#c0392b;">${Fmt.currency(b.total_expenses)}</strong></div>
                        <div><span style="color:#4a5a4a;">Profit:</span> <strong style="color:${profit >= 0 ? '#2e7d32' : '#c0392b'};">${Fmt.currency(profit)}</strong></div>
                    </div>
                    <div style="margin-top:.8rem;">
                        <button class="btn-icon" data-action="edit-budget" data-id="${b.id}" title="Edit"><i class="fas fa-edit"></i></button>
                        <button class="btn-icon" data-action="delete-budget" data-id="${b.id}" title="Delete" style="color:#c0392b;"><i class="fas fa-trash"></i></button>
                    </div>
                </div>
            `;
        }).join('');

        $$('[data-action="delete-budget"]').forEach((el) =>
            el.addEventListener('click', async () => {
                const ok = await Modal.confirm('Delete this budget?', 'Confirm');
                if (!ok) return;
                const r = await Api.deleteBudget(el.dataset.id);
                if (!r.ok) { Toast.error(r.error); return; }
                Toast.success('Budget deleted');
                loadBudgets();
            }));
    }

    // ============================================================
    // CASH FLOW FORECAST
    // ============================================================
    async function loadCashFlow() {
        if (!state.currentFarmId) return;
        const result = await Api.cashFlowForecast({ farm_id: state.currentFarmId, months: 6 });
        if (!result.ok) return;
        state.cashFlow = result.data;
        renderCashFlow();
    }

    function renderCashFlow() {
        const container = $('#cash-flow');
        if (!container || !state.cashFlow) return;

        const { forecast, averages } = state.cashFlow;
        container.innerHTML = `
            <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(140px, 1fr)); gap:1rem; margin-bottom:1rem;">
                <div style="padding:1rem; background:#e8f0e1; border-radius:12px;">
                    <div style="font-size:11px; color:#4a5a4a; text-transform:uppercase; font-weight:600;">Avg Monthly In</div>
                    <div style="font-size:1.2rem; font-weight:800; color:#2e7d32;">${Fmt.currency(averages.monthly_income)}</div>
                </div>
                <div style="padding:1rem; background:#fef3d0; border-radius:12px;">
                    <div style="font-size:11px; color:#4a5a4a; text-transform:uppercase; font-weight:600;">Avg Monthly Out</div>
                    <div style="font-size:1.2rem; font-weight:800; color:#b8860b;">${Fmt.currency(averages.monthly_expenses)}</div>
                </div>
                <div style="padding:1rem; background:#fff; border:1px solid #e2e8dd; border-radius:12px;">
                    <div style="font-size:11px; color:#4a5a4a; text-transform:uppercase; font-weight:600;">Avg Net</div>
                    <div style="font-size:1.2rem; font-weight:800; color:${averages.monthly_net >= 0 ? '#2e7d32' : '#c0392b'};">${Fmt.currency(averages.monthly_net)}</div>
                </div>
            </div>
            <div style="overflow-x:auto;">
                <table style="width:100%; border-collapse:collapse; font-size:.9rem;">
                    <thead>
                        <tr style="background:#e8f0e1;">
                            <th style="text-align:left; padding:10px; color:#1a3c2e;">Month</th>
                            <th style="text-align:right; padding:10px; color:#1a3c2e;">Projected In</th>
                            <th style="text-align:right; padding:10px; color:#1a3c2e;">Projected Out</th>
                            <th style="text-align:right; padding:10px; color:#1a3c2e;">Net</th>
                            <th style="text-align:right; padding:10px; color:#1a3c2e;">Balance</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${forecast.map((f) => `
                            <tr style="border-bottom:1px solid #eef1ea;">
                                <td style="padding:10px;">${f.month}</td>
                                <td style="padding:10px; text-align:right; color:#2e7d32;">${Fmt.currency(f.projected_income)}</td>
                                <td style="padding:10px; text-align:right; color:#c0392b;">${Fmt.currency(f.projected_expenses)}</td>
                                <td style="padding:10px; text-align:right; font-weight:600; color:${f.projected_net >= 0 ? '#2e7d32' : '#c0392b'};">${Fmt.currency(f.projected_net)}</td>
                                <td style="padding:10px; text-align:right; font-weight:600; color:#1a3c2e;">${Fmt.currency(f.projected_balance)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    // ============================================================
    // BOOT
    // ============================================================
    document.addEventListener('DOMContentLoaded', async () => {
        await loadFarms();
        $$('[data-action="new-enterprise"]').forEach((el) =>
            el.addEventListener('click', () => openEnterpriseModal()));
    });
})();