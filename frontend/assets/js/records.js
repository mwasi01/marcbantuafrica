/**
 * Marcbantu Africa — Records page.
 * Full record management: list, create, update, delete.
 */

(function () {
    'use strict';

    if (!window.Auth?.requireLogin()) return;

    const { $, $$, Fmt, Toast, Modal } = window.UI;

    let state = {
        farms: [],
        records: [],
        page: 1,
        page_size: 20,
        filters: {},
    };

    // ============================================================
    // LOAD
    // ============================================================
    async function loadFarms() {
        const result = await Api.listFarms();
        if (!result.ok) {
            Toast.error('Failed to load farms');
            return;
        }
        state.farms = result.data || [];
        renderFarmSelects();
    }

    function renderFarmSelects() {
        $$('select[name="farm_id"]').forEach((sel) => {
            const current = sel.value;
            sel.innerHTML = '<option value="">Select farm</option>' +
                state.farms.map((f) =>
                    `<option value="${f.id}" ${f.id == current ? 'selected' : ''}>${f.name}</option>`
                ).join('');
        });
    }

    async function loadRecords() {
        const container = $('#records-table-body');
        if (container) {
            container.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:40px; color:#8a9c8c;"><i class="fas fa-spinner fa-spin"></i> Loading...</td></tr>`;
        }

        const result = await Api.listRecords({
            page: state.page,
            page_size: state.page_size,
            ...state.filters,
        });

        if (!result.ok) {
            Toast.error('Failed to load records');
            if (container) container.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:40px; color:#c0392b;">Failed to load</td></tr>`;
            return;
        }

        state.records = result.data || [];
        renderRecords();
        renderPagination(result.meta);
    }

    function renderRecords() {
        const tbody = $('#records-table-body');
        if (!tbody) return;

        if (!state.records.length) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:40px; color:#8a9c8c;">No records found. <a href="#" data-action="new-record" style="color:#1a3c2e; font-weight:600;">Add your first record →</a></td></tr>`;
            return;
        }

        tbody.innerHTML = state.records.map((r) => `
            <tr data-record-id="${r.id}">
                <td>${Fmt.date(r.record_date)}</td>
                <td>${r.farm_name || '—'}</td>
                <td><span style="display:inline-block; padding:2px 8px; border-radius:20px; font-size:11px; font-weight:700; background:#e8f0e1; color:#1a3c2e;">${Fmt.titleCase(r.record_type)}</span></td>
                <td>${Fmt.titleCase(r.activity || '')}</td>
                <td>${Fmt.truncate(r.description || '', 40)}</td>
                <td style="font-weight:600; color:${(r.cost || 0) > 0 ? '#c0392b' : (r.revenue || 0) > 0 ? '#2e7d32' : '#4a5a4a'};">
                    ${(r.cost || 0) > 0 ? '−' + Fmt.currency(r.cost) : (r.revenue || 0) > 0 ? '+' + Fmt.currency(r.revenue) : '—'}
                </td>
                <td style="text-align:right; white-space:nowrap;">
                    <button class="btn-icon" data-action="edit-record" data-id="${r.id}" title="Edit"><i class="fas fa-edit"></i></button>
                    <button class="btn-icon" data-action="delete-record" data-id="${r.id}" title="Delete" style="color:#c0392b;"><i class="fas fa-trash"></i></button>
                </td>
            </tr>
        `).join('');

        // Wire actions
        $$('[data-action="edit-record"]').forEach((el) => {
            el.addEventListener('click', () => openRecordModal(el.dataset.id));
        });
        $$('[data-action="delete-record"]').forEach((el) => {
            el.addEventListener('click', () => deleteRecord(el.dataset.id));
        });
        $$('[data-action="new-record"]').forEach((el) => {
            el.addEventListener('click', (e) => {
                e.preventDefault();
                openRecordModal();
            });
        });
    }

    function renderPagination(meta) {
        const container = $('#pagination');
        if (!container || !meta) return;

        const { page, pages, total } = meta;
        if (pages <= 1) {
            container.innerHTML = `<span style="color:#4a5a4a; font-size:13px;">${total} record${total === 1 ? '' : 's'}</span>`;
            return;
        }

        let buttons = '';
        for (let i = 1; i <= pages; i++) {
            if (i === 1 || i === pages || Math.abs(i - page) <= 1) {
                buttons += `<button class="page-btn ${i === page ? 'active' : ''}" data-page="${i}">${i}</button>`;
            } else if (Math.abs(i - page) === 2) {
                buttons += `<span style="padding:0 6px; color:#8a9c8c;">…</span>`;
            }
        }

        container.innerHTML = `
            <button class="page-btn" data-page="${Math.max(1, page - 1)}" ${page === 1 ? 'disabled' : ''}><i class="fas fa-chevron-left"></i></button>
            ${buttons}
            <button class="page-btn" data-page="${Math.min(pages, page + 1)}" ${page === pages ? 'disabled' : ''}><i class="fas fa-chevron-right"></i></button>
            <span style="margin-left:12px; color:#4a5a4a; font-size:13px;">${total} total</span>
        `;

        $$('.page-btn').forEach((el) => {
            el.addEventListener('click', () => {
                const p = parseInt(el.dataset.page);
                if (p && p !== state.page) {
                    state.page = p;
                    loadRecords();
                }
            });
        });
    }

    // ============================================================
    // CREATE / EDIT MODAL
    // ============================================================
    async function openRecordModal(recordId = null) {
        const isEdit = !!recordId;
        let record = null;

        if (isEdit) {
            const result = await Api.getRecord(recordId);
            if (!result.ok) {
                Toast.error('Failed to load record');
                return;
            }
            record = result.data;
        }

        const farms = state.farms;
        if (!farms.length) {
            Toast.warning('Please create a farm first');
            window.location.href = 'planning.html';
            return;
        }

        const modal = Modal.open(`
            <div style="padding:28px; max-width:600px;">
                <h2 style="margin:0 0 20px; color:#1a3c2e; display:flex; align-items:center; gap:10px;">
                    <i class="fas fa-${isEdit ? 'edit' : 'plus-circle'}" style="color:#d4a017;"></i>
                    ${isEdit ? 'Edit Record' : 'Add New Record'}
                </h2>

                <form id="recordForm" style="display:flex; flex-direction:column; gap:14px;">
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">
                        <label style="display:flex; flex-direction:column; gap:6px;">
                            <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Farm *</span>
                            <select name="farm_id" required style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                                <option value="">Select farm</option>
                                ${farms.map((f) => `<option value="${f.id}" ${record?.farm_id == f.id ? 'selected' : ''}>${f.name}</option>`).join('')}
                            </select>
                        </label>
                        <label style="display:flex; flex-direction:column; gap:6px;">
                            <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Record Type *</span>
                            <select name="record_type" required style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                                <option value="">Select type</option>
                                ${['crop_activity', 'livestock', 'poultry', 'input', 'harvest', 'sale', 'expense', 'observation'].map((t) =>
            `<option value="${t}" ${record?.record_type === t ? 'selected' : ''}>${Fmt.titleCase(t)}</option>`
        ).join('')}
                            </select>
                        </label>
                    </div>

                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">
                        <label style="display:flex; flex-direction:column; gap:6px;">
                            <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Activity</span>
                            <input type="text" name="activity" placeholder="e.g. planting, milking" value="${record?.activity || ''}" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                        </label>
                        <label style="display:flex; flex-direction:column; gap:6px;">
                            <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Date *</span>
                            <input type="date" name="record_date" required value="${record?.record_date || new Date().toISOString().slice(0, 10)}" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                        </label>
                    </div>

                    <label style="display:flex; flex-direction:column; gap:6px;">
                        <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Description</span>
                        <input type="text" name="description" placeholder="Brief note" value="${record?.description || ''}" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                    </label>

                    <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:14px;">
                        <label style="display:flex; flex-direction:column; gap:6px;">
                            <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Quantity</span>
                            <input type="number" step="0.01" name="quantity" value="${record?.quantity || ''}" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                        </label>
                        <label style="display:flex; flex-direction:column; gap:6px;">
                            <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Unit</span>
                            <input type="text" name="unit" placeholder="kg, L, acres" value="${record?.unit || ''}" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                        </label>
                        <label style="display:flex; flex-direction:column; gap:6px;">
                            <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Cost (KES)</span>
                            <input type="number" step="0.01" name="cost" value="${record?.cost || ''}" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                        </label>
                    </div>

                    <label style="display:flex; flex-direction:column; gap:6px;">
                        <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Revenue (KES)</span>
                        <input type="number" step="0.01" name="revenue" value="${record?.revenue || ''}" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                    </label>

                    <label style="display:flex; flex-direction:column; gap:6px;">
                        <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Notes</span>
                        <textarea name="notes" rows="2" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd; font-family:inherit;">${record?.notes || ''}</textarea>
                    </label>

                    <div style="display:flex; gap:12px; justify-content:flex-end; margin-top:10px;">
                        <button type="button" class="btn-outline" data-action="cancel">Cancel</button>
                        <button type="submit" class="btn-primary">${isEdit ? 'Save Changes' : 'Create Record'}</button>
                    </div>
                </form>
            </div>
        `);

        // Wire cancel
        modal.querySelector('[data-action="cancel"]').addEventListener('click', () => {
            Modal.close(modal);
        });

        // Wire submit
        const form = modal.querySelector('#recordForm');
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const submitBtn = form.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';

            const formData = new FormData(form);
            const payload = {};
            for (const [k, v] of formData.entries()) {
                if (v !== '') {
                    if (['quantity', 'cost', 'revenue'].includes(k)) {
                        payload[k] = parseFloat(v);
                    } else {
                        payload[k] = v;
                    }
                }
            }
            // farm_id to int
            payload.farm_id = parseInt(payload.farm_id);

            const result = isEdit
                ? await Api.updateRecord(recordId, payload)
                : await Api.createRecord(payload);

            if (!result.ok) {
                Toast.error(result.error || 'Failed to save');
                submitBtn.disabled = false;
                submitBtn.textContent = isEdit ? 'Save Changes' : 'Create Record';
                return;
            }

            Toast.success(isEdit ? 'Record updated!' : 'Record created!');
            Modal.close(modal);
            loadRecords();
        });
    }

    // ============================================================
    // DELETE
    // ============================================================
    async function deleteRecord(id) {
        const ok = await Modal.confirm(
            'Delete this record? This cannot be undone.',
            'Confirm deletion'
        );
        if (!ok) return;

        const result = await Api.deleteRecord(id);
        if (!result.ok) {
            Toast.error(result.error || 'Failed to delete');
            return;
        }
        Toast.success('Record deleted');
        loadRecords();
    }

    // ============================================================
    // FILTERS
    // ============================================================
    function initFilters() {
        const filterForm = $('#filter-form');
        if (!filterForm) return;

        filterForm.addEventListener('change', () => {
            const formData = new FormData(filterForm);
            state.filters = {};
            for (const [k, v] of formData.entries()) {
                if (v) state.filters[k] = v;
            }
            state.page = 1;
            loadRecords();
        });
    }

    // ============================================================
    // BOOT
    // ============================================================
    document.addEventListener('DOMContentLoaded', async () => {
        await loadFarms();
        await loadRecords();
        initFilters();

        // Add record button in topbar
        $$('[data-action="new-record"]').forEach((el) => {
            el.addEventListener('click', (e) => {
                e.preventDefault();
                openRecordModal();
            });
        });
    });
})();