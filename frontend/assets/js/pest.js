/**
 * Marcbantu Africa — Pest & Disease page.
 */
(function () {
    'use strict';
    if (!window.Auth?.requireLogin()) return;

    const { $, $$, Fmt, Toast, Modal } = window.UI;

    let state = {
        farms: [],
        currentFarmId: null,
        scouting: [],
        library: [],
    };

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
        await Promise.all([loadDashboard(), loadScouting(), loadLibrary(), loadRegionalAlerts()]);
    }

    async function loadAll() {
        await Promise.all([loadDashboard(), loadScouting(), loadRegionalAlerts()]);
    }

    async function loadDashboard() {
        const params = state.currentFarmId ? { farm_id: state.currentFarmId } : {};
        const r = await Api.pestDashboard(params);
        if (!r.ok) return;
        const d = r.data;
        const container = $('#pest-kpis');
        if (!container) return;

        container.innerHTML = `
            <div class="kpi"><div class="kpi-label">Scouting Records</div><div class="kpi-value">${d.scouting?.total || 0}</div><div class="kpi-change" style="color:#4a5a4a;">${d.scouting?.last_30_days || 0} last 30 days</div></div>
            <div class="kpi"><div class="kpi-label">Severe Cases</div><div class="kpi-value" style="color:#c0392b;">${d.scouting?.severe || 0}</div></div>
            <div class="kpi"><div class="kpi-label">Treatments</div><div class="kpi-value">${d.recent_treatments?.length || 0}</div></div>
            <div class="kpi"><div class="kpi-label">Expiring Chemicals</div><div class="kpi-value" style="color:#b8860b;">${d.expiring_chemicals?.length || 0}</div></div>
        `;
    }

    async function loadScouting() {
        const params = state.currentFarmId ? { farm_id: state.currentFarmId } : {};
        const r = await Api.listScouting(params);
        if (!r.ok) return;
        state.scouting = r.data || [];
        renderScouting();
    }

    function renderScouting() {
        const tbody = $('#scouting-table-body');
        if (!tbody) return;
        if (!state.scouting.length) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:30px; color:#8a9c8c;">No scouting records.</td></tr>';
            return;
        }
        tbody.innerHTML = state.scouting.map((s) => `
            <tr style="border-bottom:1px solid #eef1ea;">
                <td style="padding:10px;">${Fmt.date(s.scout_date)}</td>
                <td style="padding:10px;">${s.pest_name}</td>
                <td style="padding:10px;">${s.plot_name || '—'}</td>
                <td style="padding:10px;">
                    <span style="font-size:11px; padding:3px 8px; border-radius:20px; font-weight:700; background:${severityBg(s.severity)}; color:${severityColor(s.severity)};">
                        ${s.severity}
                    </span>
                </td>
                <td style="padding:10px; text-align:right;">
                    <button class="btn-icon" data-action="delete-scouting" data-id="${s.id}" style="color:#c0392b;"><i class="fas fa-trash"></i></button>
                </td>
            </tr>
        `).join('');

        $$('[data-action="delete-scouting"]').forEach((el) =>
            el.addEventListener('click', async () => {
                const ok = await Modal.confirm('Delete this scouting record?');
                if (!ok) return;
                await Api.deleteScouting(el.dataset.id);
                Toast.success('Deleted');
                loadScouting();
            }));
    }

    function severityBg(s) { return { low: '#e8f0e1', medium: '#fef3d0', high: '#fde8e8', critical: '#fde8e8' }[s] || '#f5f5f5'; }
    function severityColor(s) { return { low: '#2e7d32', medium: '#b8860b', high: '#c0392b', critical: '#c0392b' }[s] || '#616161'; }

    async function loadLibrary() {
        const r = await Api.pestLibrary({});
        if (!r.ok) return;
        state.library = r.data || [];
        renderLibrary();
    }

    function renderLibrary() {
        const container = $('#pest-library');
        if (!container) return;
        container.innerHTML = state.library.map((p) => `
            <div style="background:#fff; border:1px solid #e2e8dd; border-radius:14px; padding:1.2rem; margin-bottom:.8rem; cursor:pointer;" data-library-id="${p.id}">
                <h4 style="color:#1a3c2e; font-size:1rem; margin:0 0 .3rem;">
                    <i class="fas fa-bug" style="color:#d4a017;"></i> ${p.name}
                </h4>
                <div style="font-size:.8rem; color:#4a5a4a; font-style:italic; margin-bottom:.4rem;">${p.scientific_name || ''}</div>
                <div style="font-size:.85rem; color:#4a5a4a;">${Fmt.truncate(p.symptoms || '', 100)}</div>
            </div>
        `).join('');

        $$('[data-library-id]').forEach((el) =>
            el.addEventListener('click', () => showLibraryDetail(el.dataset.libraryId)));
    }

    function showLibraryDetail(id) {
        const p = state.library.find((x) => x.id == id);
        if (!p) return;
        Modal.open(`
            <div style="padding:28px; max-width:600px;">
                <h2 style="margin:0 0 4px; color:#1a3c2e;">${p.name}</h2>
                <div style="font-size:.85rem; color:#4a5a4a; font-style:italic; margin-bottom:16px;">${p.scientific_name || ''}</div>
                <div style="margin-bottom:14px;">
                    <div style="font-size:.75rem; color:#4a5a4a; text-transform:uppercase; font-weight:700; margin-bottom:4px;">Symptoms</div>
                    <p style="margin:0; color:#1a3c2e; font-size:.92rem;">${p.symptoms || '—'}</p>
                </div>
                <div style="margin-bottom:14px;">
                    <div style="font-size:.75rem; color:#2e7d32; text-transform:uppercase; font-weight:700; margin-bottom:4px;">Organic Treatment</div>
                    <p style="margin:0; color:#1a3c2e; font-size:.92rem;">${p.treatment_organic || '—'}</p>
                </div>
                <div style="margin-bottom:14px;">
                    <div style="font-size:.75rem; color:#c0392b; text-transform:uppercase; font-weight:700; margin-bottom:4px;">Chemical Treatment</div>
                    <p style="margin:0; color:#1a3c2e; font-size:.92rem;">${p.treatment_chemical || '—'}</p>
                </div>
                <div style="margin-bottom:14px;">
                    <div style="font-size:.75rem; color:#b8860b; text-transform:uppercase; font-weight:700; margin-bottom:4px;">Prevention</div>
                    <p style="margin:0; color:#1a3c2e; font-size:.92rem;">${p.prevention || '—'}</p>
                </div>
                <button class="btn-outline" style="width:100%;" onclick="this.closest('.modal-overlay').classList.remove('open')">Close</button>
            </div>
        `);
    }

    async function loadRegionalAlerts() {
        if (!state.currentFarmId) return;
        const r = await Api.pestAlerts(state.currentFarmId);
        if (!r.ok) return;
        const container = $('#regional-alerts');
        if (!container) return;
        const alerts = r.data?.alerts || [];
        if (!alerts.length) {
            container.innerHTML = '<div style="padding:14px; text-align:center; color:#2e7d32;"><i class="fas fa-check-circle"></i> No pest outbreaks reported nearby.</div>';
            return;
        }
        container.innerHTML = alerts.map((a) => `
            <div style="background:#fde8e8; border-left:4px solid #c0392b; padding:12px 14px; border-radius:10px; margin-bottom:8px;">
                <div style="font-weight:700; color:#c0392b;"><i class="fas fa-exclamation-triangle"></i> ${a.pest_name}</div>
                <div style="font-size:.85rem; color:#1a3c2e; margin-top:2px;">${a.report_count} reports in ${r.data.county} · Last seen ${Fmt.date(a.last_seen)}</div>
            </div>
        `).join('');
    }

    function openScoutingModal() {
        if (!state.farms.length) { Toast.warning('Add a farm first'); return; }
        const modal = Modal.open(`
            <div style="padding:28px; max-width:520px;">
                <h2 style="margin:0 0 20px; color:#1a3c2e;"><i class="fas fa-bug" style="color:#d4a017;"></i> Log Scouting</h2>
                <form id="scoutingForm" style="display:flex; flex-direction:column; gap:14px;">
                    <label style="display:flex; flex-direction:column; gap:6px;">
                        <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Farm *</span>
                        <select name="farm_id" required style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                            ${state.farms.map((f) => `<option value="${f.id}" ${f.id === state.currentFarmId ? 'selected' : ''}>${f.name}</option>`).join('')}
                        </select>
                    </label>
                    <label style="display:flex; flex-direction:column; gap:6px;">
                        <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Pest / Disease Name *</span>
                        <input name="pest_name" required style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                    </label>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">
                        <label style="display:flex; flex-direction:column; gap:6px;">
                            <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Severity *</span>
                            <select name="severity" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                                <option value="low">Low</option>
                                <option value="medium" selected>Medium</option>
                                <option value="high">High</option>
                                <option value="critical">Critical</option>
                            </select>
                        </label>
                        <label style="display:flex; flex-direction:column; gap:6px;">
                            <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Date *</span>
                            <input type="date" name="scout_date" required value="${new Date().toISOString().slice(0, 10)}" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                        </label>
                    </div>
                    <label style="display:flex; flex-direction:column; gap:6px;">
                        <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Symptoms / Notes</span>
                        <textarea name="symptoms" rows="3" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd; font-family:inherit;"></textarea>
                    </label>
                    <div style="display:flex; gap:12px; justify-content:flex-end;">
                        <button type="button" class="btn-outline" data-action="cancel">Cancel</button>
                        <button type="submit" class="btn-primary">Save Record</button>
                    </div>
                </form>
            </div>
        `);
        modal.querySelector('[data-action="cancel"]').addEventListener('click', () => Modal.close(modal));
        modal.querySelector('#scoutingForm').addEventListener('submit', async (ev) => {
            ev.preventDefault();
            const fd = new FormData(ev.target);
            const payload = {};
            for (const [k, v] of fd.entries()) if (v) payload[k] = v;
            payload.farm_id = parseInt(payload.farm_id);

            const r = await Api.createScouting(payload);
            if (!r.ok) { Toast.error(r.error); return; }
            Toast.success('Scouting logged!');
            Modal.close(modal);
            loadAll();
        });
    }

    async function runDiagnosis() {
        const crop = $('#diag-crop')?.value;
        const symptoms = $('#diag-symptoms')?.value;
        if (!symptoms) { Toast.warning('Add symptoms to diagnose'); return; }

        const container = $('#diagnosis-result');
        if (container) container.innerHTML = '<div style="text-align:center; padding:20px;"><i class="fas fa-spinner fa-spin"></i> Analyzing...</div>';

        const r = await Api.diagnosePest({ crop, symptoms });
        if (!r.ok) {
            if (container) container.innerHTML = `<div style="color:#c0392b; padding:16px;">${r.error}</div>`;
            return;
        }
        const d = r.data;
        if (!d.diagnosis) {
            if (container) container.innerHTML = `<div style="padding:16px; color:#8a9c8c;">${d.message || 'No matches found.'}</div>`;
            return;
        }
        const top = d.diagnosis;
        container.innerHTML = `
            <div style="background:#e8f0e1; border-left:5px solid #2e7d32; border-radius:12px; padding:16px;">
                <div style="font-size:.75rem; color:#2e7d32; text-transform:uppercase; font-weight:700;">Likely Diagnosis</div>
                <h4 style="margin:6px 0; color:#1a3c2e; font-size:1.1rem;">${top.pest_name}</h4>
                <div style="font-size:.85rem; color:#4a5a4a; margin-bottom:10px;">Confidence: ${top.confidence}%</div>
                <div style="font-size:.9rem; color:#1a3c2e; margin-bottom:8px;"><strong>Symptoms:</strong> ${Fmt.truncate(top.symptoms || '', 150)}</div>
                <div style="font-size:.9rem; color:#1a3c2e; margin-bottom:6px;"><strong>Organic:</strong> ${top.treatment_organic || '—'}</div>
                <div style="font-size:.9rem; color:#1a3c2e;"><strong>Chemical:</strong> ${top.treatment_chemical || '—'}</div>
            </div>
            ${d.alternatives?.length ? `
                <div style="margin-top:12px; font-size:.85rem; color:#4a5a4a;">
                    <strong>Other possibilities:</strong> ${d.alternatives.map((a) => a.pest_name).join(', ')}
                </div>
            ` : ''}
        `;
    }

    document.addEventListener('DOMContentLoaded', () => {
        loadFarms();
        $$('[data-action="new-scouting"]').forEach((el) =>
            el.addEventListener('click', openScoutingModal));
        $$('[data-action="diagnose"]').forEach((el) =>
            el.addEventListener('click', runDiagnosis));
    });
})();