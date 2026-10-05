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
