/**
 * Marcbantu Africa — Market & Sales page.
 */
(function () {
    'use strict';
    if (!window.Auth?.requireLogin()) return;

    const { $, $$, Fmt, Toast, Modal } = window.UI;

    let state = { farms: [], currentFarmId: null, prices: [], sales: [] };

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
        await loadAll();
    }

    async function loadAll() {
        await Promise.all([loadSummary(), loadPrices(), loadSales()]);
    }

    async function loadSummary() {
        const params = state.currentFarmId ? { farm_id: state.currentFarmId } : {};
        const r = await Api.salesSummary(params);
        if (!r.ok) return;
        const d = r.data || {};
        const container = $('#sales-summary');
        if (!container) return;
        const t = d.totals || {};
        container.innerHTML = `
            <div class="kpi"><div class="kpi-label">Total Sales</div><div class="kpi-value">${t.total_sales || 0}</div></div>
            <div class="kpi"><div class="kpi-label">Revenue</div><div class="kpi-value" style="color:#2e7d32;">${Fmt.currency(t.total_revenue)}</div></div>
            <div class="kpi"><div class="kpi-label">Collected</div><div class="kpi-value">${Fmt.currency(t.total_collected)}</div></div>
            <div class="kpi"><div class="kpi-label">Pending</div><div class="kpi-value" style="color:#b8860b;">${Fmt.currency(t.pending_amount)}</div></div>
        `;
    }

    async function loadPrices() {
        const r = await Api.marketPrices({ latest: 'true' });
        if (!r.ok) return;
        state.prices = r.data || [];
        renderPrices();
    }

    function renderPrices() {
        const container = $('#prices-grid');
        if (!container) return;
        if (!state.prices.length) {
            container.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:20px; color:#8a9c8c;">No market prices available yet.</div>';
            return;
        }
        container.innerHTML = state.prices.slice(0, 12).map((p) => `
            <div style="background:#fff; border:1px solid #e2e8dd; border-radius:14px; padding:1rem; border-left:4px solid #d4a017;">
                <div style="font-size:.8rem; color:#4a5a4a; text-transform:uppercase; font-weight:600;">${p.market || 'Market'}</div>
                <div style="font-weight:700; color:#1a3c2e; font-size:.95rem; margin:.2rem 0;">${p.crop}</div>
                <div style="font-size:1.3rem; font-weight:800; color:#2e7d32;">${Fmt.currency(p.price)}</div>
                <div style="font-size:.75rem; color:#8a9c8c;">per ${p.unit || 'kg'} · ${Fmt.date(p.price_date)}</div>
            </div>
        `).join('');
    }

    async function loadSales() {
        const params = state.currentFarmId ? { farm_id: state.currentFarmId, page_size: 20 } : { page_size: 20 };
        const r = await Api.listSales(params);
        if (!r.ok) return;
        state.sales = r.data || [];
        renderSales();
    }

    function renderSales() {
        const tbody = $('#sales-table-body');
        if (!tbody) return;
        if (!state.sales.length) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:30px; color:#8a9c8c;">No sales yet. <a href="#" data-action="new-sale" style="color:#1a3c2e; font-weight:600;">Record your first sale →</a></td></tr>';
            return;
        }
        tbody.innerHTML = state.sales.map((s) => `
            <tr style="border-bottom:1px solid #eef1ea;">
                <td style="padding:10px;">${Fmt.date(s.sale_date)}</td>
                <td style="padding:10px;">${s.product}</td>
                <td style="padding:10px;">${s.buyer_name || '—'}</td>
                <td style="padding:10px; text-align:right;">${s.quantity} ${s.unit || ''}</td>
                <td style="padding:10px; text-align:right; font-weight:700; color:#2e7d32;">${Fmt.currency(s.total)}</td>
                <td style="padding:10px;"><span style="font-size:11px; padding:3px 8px; border-radius:20px; font-weight:700; background:${s.payment_status === 'paid' ? '#e8f0e1' : s.payment_status === 'partial' ? '#fef3d0' : '#f5f5f5'}; color:${s.payment_status === 'paid' ? '#2e7d32' : s.payment_status === 'partial' ? '#b8860b' : '#616161'};">${s.payment_status || 'pending'}</span></td>
            </tr>
        `).join('');
        $$('[data-action="new-sale"]').forEach((el) =>
            el.addEventListener('click', (e) => { e.preventDefault(); openSaleModal(); }));
    }

    function openSaleModal() {
        if (!state.farms.length) { Toast.warning('Add a farm first'); return; }
        const modal = Modal.open(`
            <div style="padding:28px; max-width:560px;">
                <h2 style="margin:0 0 20px; color:#1a3c2e;"><i class="fas fa-plus-circle" style="color:#d4a017;"></i> Record Sale</h2>
                <form id="saleForm" style="display:flex; flex-direction:column; gap:14px;">
                    <label style="display:flex; flex-direction:column; gap:6px;"><span style="font-size:13px; font-weight:600; color:#1a3c2e;">Farm *</span><select name="farm_id" required style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">${state.farms.map((f) => `<option value="${f.id}">${f.name}</option>`).join('')}</select></label>
                    <div style="display:grid; grid-template-columns:2fr 1fr; gap:14px;">
                        <label style="display:flex; flex-direction:column; gap:6px;"><span style="font-size:13px; font-weight:600; color:#1a3c2e;">Product *</span><input name="product" required style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;"></label>
                        <label style="display:flex; flex-direction:column; gap:6px;"><span style="font-size:13px; font-weight:600; color:#1a3c2e;">Unit</span><input name="unit" value="kg" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;"></label>
                    </div>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">
                        <label style="display:flex; flex-direction:column; gap:6px;"><span style="font-size:13px; font-weight:600; color:#1a3c2e;">Quantity *</span><input type="number" step="0.01" name="quantity" required style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;"></label>
                        <label style="display:flex; flex-direction:column; gap:6px;"><span style="font-size:13px; font-weight:600; color:#1a3c2e;">Unit Price *</span><input type="number" step="0.01" name="unit_price" required style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;"></label>
                    </div>
                    <label style="display:flex; flex-direction:column; gap:6px;"><span style="font-size:13px; font-weight:600; color:#1a3c2e;">Sale Date *</span><input type="date" name="sale_date" required value="${new Date().toISOString().slice(0, 10)}" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;"></label>
                    <div style="display:flex; gap:12px; justify-content:flex-end;"><button type="button" class="btn-outline" data-action="cancel">Cancel</button><button type="submit" class="btn-primary">Save Sale</button></div>
                </form>
            </div>
        `);
        modal.querySelector('[data-action="cancel"]').addEventListener('click', () => Modal.close(modal));
        modal.querySelector('#saleForm').addEventListener('submit', async (ev) => {
            ev.preventDefault();
            const fd = new FormData(ev.target);
            const payload = {};
            for (const [k, v] of fd.entries()) payload[k] = ['quantity', 'unit_price'].includes(k) ? parseFloat(v) : v;
            payload.farm_id = parseInt(payload.farm_id);
            const r = await Api.createSale(payload);
            if (!r.ok) { Toast.error(r.error); return; }
            Toast.success('Sale recorded!');
            Modal.close(modal);
            loadAll();
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        loadFarms();
        $$('[data-action="new-sale"]').forEach((el) =>
            el.addEventListener('click', (e) => { e.preventDefault(); openSaleModal(); }));
    });
})();
