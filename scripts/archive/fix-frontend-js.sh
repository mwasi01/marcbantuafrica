#!/usr/bin/env bash
set -e
cd /mnt/c/Users/hp/Desktop/marcbantu
JS=frontend/assets/js

echo "Filling empty JS files in $JS"

# ---------- market.js ----------
cat > "$JS/market.js" << 'JSEOF'
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
JSEOF

# ---------- weather.js ----------
cat > "$JS/weather.js" << 'JSEOF'
/**
 * Marcbantu Africa — Weather page.
 */
(function () {
    'use strict';
    if (!window.Auth?.requireLogin()) return;

    const { $, $$, Fmt, Toast } = window.UI;

    let state = { farms: [], currentFarmId: null, weather: null };

    async function loadFarms() {
        const r = await Api.listFarms();
        if (!r.ok) return;
        state.farms = r.data || [];
        const sel = $('#farm-selector');
        if (sel && state.farms.length) {
            sel.innerHTML = state.farms.map((f) => `<option value="${f.id}">${f.name}</option>`).join('');
            state.currentFarmId = state.farms[0].id;
            sel.addEventListener('change', () => {
                state.currentFarmId = parseInt(sel.value);
                loadAll();
            });
        }
        await loadAll();
    }

    async function loadAll() {
        const farm = state.farms.find((f) => f.id === state.currentFarmId);
        const params = farm?.latitude && farm?.longitude
            ? { lat: farm.latitude, lon: farm.longitude, location_name: farm.name }
            : (state.currentFarmId ? { farm_id: state.currentFarmId } : {});

        const [weather, alerts, rainfall] = await Promise.all([
            Api.weather(params),
            Api.weatherAlerts(params),
            Api.rainfall({ ...params, days: 30 }),
        ]);

        if (weather.ok) { state.weather = weather.data; renderCurrent(weather.data); renderForecast(weather.data); renderAdvice(weather.data); }
        if (alerts.ok) renderAlerts(alerts.data);
        if (rainfall.ok) renderRainfall(rainfall.data);
    }

    function renderCurrent(d) {
        const container = $('#current-weather');
        if (!container) return;
        const c = d.current || {};
        container.innerHTML = `
            <div class="panel" style="background:linear-gradient(135deg,#2f5d3a,#1a3c2e); color:#fff; border:none;">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:1rem;">
                    <div>
                        <div style="font-size:.85rem; color:#c8d6ca;">Current weather</div>
                        <div style="font-size:3rem; font-weight:800;">${Math.round(c.temperature || 0)}°C</div>
                        <div style="font-size:1rem; color:#e6b422; font-weight:600;"><i class="fas fa-${iconFor(c.icon)}"></i> ${c.condition || '—'}</div>
                    </div>
                    <div style="text-align:right; font-size:.9rem; color:#c8d6ca;">
                        <div>Humidity: <strong style="color:#fff;">${c.humidity || 0}%</strong></div>
                        <div>Wind: <strong style="color:#fff;">${c.wind_speed || 0} km/h</strong></div>
                    </div>
                </div>
            </div>
        `;
    }

    function renderForecast(d) {
        const container = $('#forecast-days');
        if (!container) return;
        const days = d.daily || [];
        if (!days.length) { container.innerHTML = '<div style="grid-column:1/-1; text-align:center; color:#8a9c8c;">No forecast data</div>'; return; }
        container.innerHTML = days.slice(0, 7).map((day) => `
            <div style="background:#fff; border:1px solid #e2e8dd; border-radius:14px; padding:1rem; text-align:center;">
                <div style="font-size:.78rem; color:#4a5a4a; font-weight:600;">${new Date(day.date).toLocaleDateString('en-KE', { weekday: 'short' })}</div>
                <div style="font-size:1.8rem; color:#d4a017; margin:.4rem 0;"><i class="fas fa-${iconFor(day.icon)}"></i></div>
                <div style="font-size:.95rem; font-weight:700; color:#1a3c2e;">${Math.round(day.temp_max || 0)}°</div>
                <div style="font-size:.8rem; color:#8a9c8c;">${Math.round(day.temp_min || 0)}°</div>
                <div style="font-size:.75rem; color:#1565c0; margin-top:.3rem;"><i class="fas fa-tint"></i> ${day.precipitation || 0}mm</div>
            </div>
        `).join('');
    }

    function renderAdvice(d) {
        const container = $('#weather-advice');
        if (!container) return;
        const advice = d.advice || [];
        if (!advice.length) { container.innerHTML = '<div style="padding:16px; color:#8a9c8c;">No specific advice for current conditions.</div>'; return; }
        container.innerHTML = advice.map((a) => {
            const colors = { ok: { bg: '#e8f0e1', border: '#2e7d32', icon: 'check-circle' },
                             warn: { bg: '#fef3d0', border: '#d4a017', icon: 'exclamation-triangle' },
                             urgent: { bg: '#fde8e8', border: '#c0392b', icon: 'exclamation-circle' } };
            const c = colors[a.priority] || colors.ok;
            return `
                <div style="background:${c.bg}; border-left:5px solid ${c.border}; border-radius:12px; padding:14px; margin-bottom:10px;">
                    <div style="font-weight:700; color:#1a3c2e; text-transform:capitalize; display:flex; align-items:center; gap:8px;">
                        <i class="fas fa-${c.icon}" style="color:${c.border};"></i> ${a.type}
                    </div>
                    <div style="color:#4a5a4a; font-size:.92rem; margin-top:4px;">${a.message}</div>
                </div>
            `;
        }).join('');
    }

    function renderAlerts(d) {
        const container = $('#weather-alerts');
        if (!container) return;
        const warnings = d.warnings || [];
        if (!warnings.length) { container.innerHTML = '<div style="padding:16px; color:#2e7d32;"><i class="fas fa-check-circle"></i> No weather alerts for your area.</div>'; return; }
        container.innerHTML = warnings.map((w) => `
            <div style="background:#fde8e8; border-left:5px solid #c0392b; border-radius:12px; padding:14px; margin-bottom:10px;">
                <div style="font-weight:700; color:#c0392b;">${w.title}</div>
                <div style="color:#1a3c2e; font-size:.92rem; margin-top:4px;">${w.message}</div>
            </div>
        `).join('');
    }

    function renderRainfall(d) {
        const container = $('#rainfall-history');
        if (!container) return;
        const history = d.history || [];
        if (!history.length) { container.innerHTML = '<div style="padding:16px; color:#8a9c8c;">No rainfall data</div>'; return; }
        const max = Math.max(...history.map((h) => h.precipitation_mm || 0), 1);
        container.innerHTML = `
            <div style="display:flex; align-items:flex-end; gap:2px; height:100px; margin-bottom:.6rem;">
                ${history.map((h) => `
                    <div style="flex:1; background:linear-gradient(to top,#1565c0,#42a5f5); height:${((h.precipitation_mm || 0) / max) * 100}%; border-radius:3px 3px 0 0; min-height:2px;" title="${h.date}: ${h.precipitation_mm}mm"></div>
                `).join('')}
            </div>
            <div style="display:flex; justify-content:space-between; font-size:.85rem; color:#4a5a4a;">
                <span>Total: <strong style="color:#1565c0;">${d.total_precipitation_mm}mm</strong></span>
                <span>Wet days: <strong>${d.summary?.wet_days || 0}</strong></span>
                <span>Dry days: <strong>${d.summary?.dry_days || 0}</strong></span>
            </div>
        `;
    }

    function iconFor(name) {
        return { sun: 'sun', 'cloud-sun': 'cloud-sun', cloud: 'cloud', 'cloud-rain': 'cloud-rain',
                 'cloud-drizzle': 'cloud-rain', 'cloud-showers-heavy': 'cloud-showers-heavy',
                 smog: 'smog', snowflake: 'snowflake', bolt: 'bolt' }[name] || 'cloud';
    }

    document.addEventListener('DOMContentLoaded', loadFarms);
})();
JSEOF

# ---------- register-sw.js ----------
cat > "$JS/register-sw.js" << 'JSEOF'
/**
 * Marcbantu Africa — register the service worker.
 */
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then((reg) => console.log('[SW] registered', reg.scope))
            .catch((err) => console.warn('[SW] registration failed', err));
    });
}
JSEOF

# ---------- notifications.js ----------
cat > "$JS/notifications.js" << 'JSEOF'
/**
 * Marcbantu Africa — Notifications helper.
 * The app.js already handles the topbar badge; this file is a placeholder
 * for a future dedicated notifications panel page.
 */
(function () {
    'use strict';
    // Reserved for a /notifications.html page in the future.
    if (window.UI?.Notifications?.updateBadge && window.Auth?.isLoggedIn()) {
        window.UI.Notifications.updateBadge();
    }
})();
JSEOF

echo ""
echo "Verifying:"
for f in market weather register-sw notifications; do
    SIZE=$(stat -c %s "$JS/$f.js" 2>/dev/null || echo 0)
    if [ "$SIZE" -gt 100 ]; then
        echo "  ✓ $f.js ($SIZE bytes)"
    else
        echo "  ✗ $f.js is still empty or too small ($SIZE bytes)"
    fi
done
