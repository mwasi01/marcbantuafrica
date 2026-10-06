/**
 * Marcbantu Africa — Market & Sales page.
 * Shows nearest-market prices using the farm's GPS coordinates.
 */
(function () {
    'use strict';
    if (!window.Auth?.requireLogin()) return;

    // === Marcbantu UI guard ===
    if (!window.UI) {
        console.error('[market.js] window.UI missing — app.js failed to load.');
        return;
    }
    // === end guard ===

    const { $, $$, Fmt, Toast, Modal } = window.UI;

    let state = {
        farms: [],
        currentFarmId: null,
        markets: [],
        sales: [],
    };

    // ============================================================
    // FARMS
    // ============================================================
    async function loadFarms() {
        const r = await Api.listFarms();
        if (!r.ok) return;
        state.farms = r.data || [];

        // Auto-select first farm if none selected
        if (!state.currentFarmId && state.farms.length) {
            state.currentFarmId = state.farms[0].id;
        }

        const sel = $('#farm-selector');
        if (sel) {
            sel.innerHTML = state.farms
                .map((f) => `<option value="${f.id}" ${f.id === state.currentFarmId ? 'selected' : ''}>${f.name}</option>`)
                .join('');
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

    // ============================================================
    // SUMMARY KPIs
    // ============================================================
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

    // ============================================================
    // NEAREST-MARKET PRICES
    // ============================================================
    async function loadPrices() {
        const grid = $('#prices-grid');
        if (!grid) return;

        if (!state.currentFarmId) {
            grid.innerHTML = `
                <div style="grid-column:1/-1; text-align:center; padding:30px; color:#8a9c8c; background:#fbfcf9; border-radius:14px;">
                    <i class="fas fa-map-marker-alt" style="font-size:2rem; color:#d4a017; margin-bottom:.6rem; display:block;"></i>
                    <div style="font-weight:600; color:#1a3c2e; margin-bottom:.4rem;">Select a farm above</div>
                    <div style="font-size:.85rem;">Market prices are shown for the market nearest to your selected farm.</div>
                </div>`;
            return;
        }

        const farm = state.farms.find((f) => f.id === state.currentFarmId);
        const hasGPS = farm && farm.latitude != null && farm.longitude != null;

        if (!hasGPS) {
            grid.innerHTML = `
                <div style="grid-column:1/-1; text-align:center; padding:30px; color:#8a9c8c; background:#fbfcf9; border-radius:14px;">
                    <i class="fas fa-map-marked-alt" style="font-size:2rem; color:#d4a017; margin-bottom:.6rem; display:block;"></i>
                    <div style="font-weight:600; color:#1a3c2e; margin-bottom:.4rem;">This farm has no GPS coordinates</div>
                    <div style="font-size:.85rem; max-width:520px; margin:0 auto;">
                        Edit the farm on the <a href="/planning.html" style="color:#1a3c2e; font-weight:600;">Planning page</a> and add latitude/longitude
                        (or use "Use my current location") to see prices from nearby markets.
                    </div>
                </div>`;
            return;
        }

        grid.innerHTML = `
            <div style="grid-column:1/-1; text-align:center; padding:20px; color:#8a9c8c;">
                <i class="fas fa-spinner fa-spin"></i> Finding markets near ${farm.name}...
            </div>`;

        const url = `${window.MarcbantuAPI}/api/market/prices/near-me?farm_id=${state.currentFarmId}&limit=5&radius_km=300`;
        const r = await fetch(url, {
            headers: { 'Authorization': 'Bearer ' + localStorage.getItem('marcbantu_token') }
        });

        let body;
        try {
            body = await r.json();
        } catch (e) {
            grid.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:20px; color:#c0392b;">Failed to load prices.</div>`;
            return;
        }

        const markets = body?.data?.markets || [];

        // Case 1: no markets within radius
        if (!markets.length) {
            grid.innerHTML = `
                <div style="grid-column:1/-1; text-align:center; padding:30px; color:#8a9c8c; background:#fbfcf9; border-radius:14px;">
                    <i class="fas fa-map-marked-alt" style="font-size:2rem; color:#d4a017; margin-bottom:.6rem; display:block;"></i>
                    <div style="font-weight:600; color:#1a3c2e; margin-bottom:.4rem;">No markets within 300 km of this farm</div>
                    <div style="font-size:.85rem; max-width:520px; margin:0 auto;">
                        Prices refresh daily at 6 AM from FEWS NET, WFP VAM, and FAO GIEWS.
                        You can also submit prices you see at your local market.
                    </div>
                </div>`;
            return;
        }

        // Case 2: markets found but no prices yet (ingest hasn't run)
        const anyPrices = markets.some((m) => (m.prices || []).length > 0);

        if (!anyPrices) {
            grid.innerHTML = `
                <div style="grid-column:1/-1; background:#fbfcf9; border-radius:14px; padding:1rem 1.2rem; margin-bottom:.6rem; border-left:4px solid #d4a017; font-size:.85rem; color:#4a5a4a;">
                    <i class="fas fa-info-circle" style="color:#d4a017;"></i>
                    Showing <strong>${markets.length}</strong> markets near your farm.
                    <strong>Prices will populate at 6 AM tomorrow</strong> after the first data ingest from FEWS NET, WFP, and FAO.
                </div>
                ${markets.map(renderMarketCard).join('')}
            `;
            return;
        }

        // Case 3: full data
        grid.innerHTML = markets.map(renderMarketCard).join('');
    }

    function renderMarketCard(m) {
        const hasPrices = (m.prices || []).length > 0;

        return `
            <div style="background:#fff; border:1px solid #e2e8dd; border-radius:14px; padding:1.2rem; border-left:4px solid #d4a017;">
                <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:.6rem;">
                    <div>
                        <div style="font-weight:800; color:#1a3c2e; font-size:1rem; line-height:1.2;">${m.name}</div>
                        <div style="font-size:.78rem; color:#4a5a4a; margin-top:.15rem;">
                            ${m.county_or_region ? m.county_or_region + ', ' : ''}${m.country}
                            · <strong style="color:#2e7d32;">${m.distance_km} km</strong>
                        </div>
                    </div>
                    <span style="font-size:.7rem; background:${hasPrices ? '#e8f0e1' : '#fef3d0'}; color:${hasPrices ? '#2e7d32' : '#b8860b'}; padding:2px 8px; border-radius:20px; font-weight:700; white-space:nowrap;">
                        ${hasPrices ? m.prices.length + ' crops' : 'No data yet'}
                    </span>
                </div>
                ${hasPrices
                    ? `<div style="margin-top:.8rem;">${m.prices.slice(0, 8).map(renderPriceRow).join('')}</div>`
                    : `<div style="margin-top:.8rem; padding:.6rem 0; font-size:.82rem; color:#8a9c8c; font-style:italic;">
                           Prices for this market will appear after the next ingest.
                       </div>`}
            </div>
        `;
    }

    function renderPriceRow(p) {
        const trend = p.trend_7d_pct;
        const trendColor = trend == null ? '#8a9c8c' : trend >= 0 ? '#2e7d32' : '#c0392b';
        const trendArrow = trend == null ? '' : trend >= 0 ? '▲' : '▼';
        return `
            <div style="display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px dashed #eef1ea;">
                <span style="color:#1a3c2e; font-size:.9rem;">${p.crop}</span>
                <div style="text-align:right;">
                    <div style="font-weight:700; color:#1a3c2e;">${p.currency} ${Math.round(p.price).toLocaleString()}/${p.unit}</div>
                    ${trend != null ? `<div style="font-size:.72rem; color:${trendColor};">${trendArrow} ${Math.abs(trend)}% 7d</div>` : ''}
                </div>
            </div>
        `;
    }

    // ============================================================
    // RECENT SALES
    // ============================================================
    async function loadSales() {
        const params = state.currentFarmId
            ? { farm_id: state.currentFarmId, page_size: 20 }
            : { page_size: 20 };
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
            bindNewSaleButtons();
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
        bindNewSaleButtons();
    }

    function bindNewSaleButtons() {
        $$('[data-action="new-sale"]').forEach((el) =>
            el.addEventListener('click', (e) => { e.preventDefault(); openSaleModal(); }));
    }

    // ============================================================
    // RECORD SALE MODAL
    // ============================================================
    function openSaleModal() {
        if (!state.farms.length) { Toast.warning('Add a farm first'); return; }
        const modal = Modal.open(`
            <div style="padding:28px; max-width:560px;">
                <h2 style="margin:0 0 20px; color:#1a3c2e;"><i class="fas fa-plus-circle" style="color:#d4a017;"></i> Record Sale</h2>
                <form id="saleForm" style="display:flex; flex-direction:column; gap:14px;">
                    <label style="display:flex; flex-direction:column; gap:6px;"><span style="font-size:13px; font-weight:600; color:#1a3c2e;">Farm *</span><select name="farm_id" required style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">${state.farms.map((f) => `<option value="${f.id}" ${f.id === state.currentFarmId ? 'selected' : ''}>${f.name}</option>`).join('')}</select></label>
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

    // ============================================================
    // BOOT
    // ============================================================
    document.addEventListener('DOMContentLoaded', () => {
        loadFarms();
        bindNewSaleButtons();
    });
})();