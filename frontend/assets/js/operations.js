/**
 * Marcbantu Africa — Operations page.
 * Tasks, workers, attendance, equipment.
 */
(function () {
    'use strict';
    if (!window.Auth?.requireLogin()) return;

    const { $, $$, Fmt, Toast, Modal } = window.UI;

    let state = {
        farms: [],
        currentFarmId: null,
        tasks: [],
        workers: [],
        equipment: [],
    };

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
        const params = state.currentFarmId ? { farm_id: state.currentFarmId } : {};
        await Promise.all([
            loadDashboard(params),
            loadTasks(params),
            loadWorkers(params),
            loadEquipment(params),
        ]);
    }

    // ============================================================
    // DASHBOARD
    // ============================================================
    async function loadDashboard(params) {
        const r = await Api.operationsDashboard(params);
        if (!r.ok) return;
        const d = r.data;
        const container = $('#ops-kpis');
        if (!container) return;

        container.innerHTML = `
            <div class="kpi">
                <div class="kpi-label">Pending Tasks <i class="fas fa-tasks"></i></div>
                <div class="kpi-value">${d.tasks?.pending || 0}</div>
                <div class="kpi-change" style="color:#4a5a4a;">${d.tasks?.overdue || 0} overdue</div>
            </div>
            <div class="kpi">
                <div class="kpi-label">Active Workers <i class="fas fa-users"></i></div>
                <div class="kpi-value">${d.workers?.active || 0}</div>
                <div class="kpi-change" style="color:#4a5a4a;">Present today: ${d.attendance_today?.present || 0}</div>
            </div>
            <div class="kpi">
                <div class="kpi-label">Equipment <i class="fas fa-tractor"></i></div>
                <div class="kpi-value">${d.equipment?.total || 0}</div>
                <div class="kpi-change ${(d.equipment?.overdue_service || 0) > 0 ? 'down' : 'up'}">
                    ${d.equipment?.overdue_service || 0} need service
                </div>
            </div>
            <div class="kpi">
                <div class="kpi-label">Completed <i class="fas fa-check-circle"></i></div>
                <div class="kpi-value">${d.tasks?.completed || 0}</div>
                <div class="kpi-change up">All time</div>
            </div>
        `;
    }

    // ============================================================
    // TASKS
    // ============================================================
    async function loadTasks(params) {
        const r = await Api.listTasks(params);
        if (!r.ok) return;
        state.tasks = r.data || [];
        renderTasks();
    }

    function renderTasks() {
        const container = $('#tasks-list');
        if (!container) return;
        if (!state.tasks.length) {
            container.innerHTML = '<div style="text-align:center; padding:30px; color:#8a9c8c;">No tasks yet. <a href="#" data-action="new-task" style="color:#1a3c2e; font-weight:600;">Create one →</a></div>';
            return;
        }

        container.innerHTML = state.tasks.map((t) => `
            <div style="display:flex; gap:12px; padding:12px 0; border-bottom:1px dashed #eef1ea; align-items:center;">
                <div class="task-check-${t.id}" data-task-id="${t.id}" style="width:22px; height:22px; border-radius:6px; border:2px solid ${t.status === 'completed' ? '#2f5d3a' : '#e2e8dd'}; background:${t.status === 'completed' ? '#2f5d3a' : 'transparent'}; cursor:pointer; display:flex; align-items:center; justify-content:center; flex-shrink:0;">
                    <i class="fas fa-check" style="opacity:${t.status === 'completed' ? 1 : 0}; color:#fff; font-size:11px;"></i>
                </div>
                <div style="flex:1;">
                    <div style="font-weight:600; color:#1a3c2e; font-size:14px; ${t.status === 'completed' ? 'text-decoration:line-through; color:#8a9c8c;' : ''}">${t.title}</div>
                    ${t.description ? `<div style="font-size:12px; color:#4a5a4a;">${Fmt.truncate(t.description, 60)}</div>` : ''}
                </div>
                <span style="font-size:10px; padding:2px 8px; border-radius:20px; font-weight:700; text-transform:uppercase; background:${priorityBg(t.priority)}; color:${priorityColor(t.priority)};">${t.priority}</span>
                <button class="btn-icon" data-action="delete-task" data-id="${t.id}" style="color:#c0392b;"><i class="fas fa-trash"></i></button>
            </div>
        `).join('');

        // Wire checkboxes
        $$('[class^="task-check-"]').forEach((el) => {
            el.addEventListener('click', async () => {
                const id = el.dataset.taskId;
                const r = await Api.completeTask(id);
                if (!r.ok) { Toast.error(r.error); return; }
                Toast.success('Task completed!');
                loadTasks(state.currentFarmId ? { farm_id: state.currentFarmId } : {});
            });
        });

        $$('[data-action="delete-task"]').forEach((el) =>
            el.addEventListener('click', async () => {
                const ok = await Modal.confirm('Delete this task?');
                if (!ok) return;
                await Api.deleteTask(el.dataset.id);
                Toast.success('Task deleted');
                loadTasks(state.currentFarmId ? { farm_id: state.currentFarmId } : {});
            }));
    }

    function priorityBg(p) { return { urgent: '#fde8e8', high: '#fde8e8', medium: '#fef3d0', low: '#e8f0e1' }[p] || '#f5f5f5'; }
    function priorityColor(p) { return { urgent: '#c0392b', high: '#c0392b', medium: '#b8860b', low: '#2e7d32' }[p] || '#616161'; }

    function openTaskModal() {
        if (!state.farms.length) { Toast.warning('Add a farm first'); return; }
        const modal = Modal.open(`
            <div style="padding:28px; max-width:520px;">
                <h2 style="margin:0 0 20px; color:#1a3c2e;"><i class="fas fa-plus-circle" style="color:#d4a017;"></i> New Task</h2>
                <form id="taskForm" style="display:flex; flex-direction:column; gap:14px;">
                    <label style="display:flex; flex-direction:column; gap:6px;">
                        <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Farm *</span>
                        <select name="farm_id" required style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                            ${state.farms.map((f) => `<option value="${f.id}">${f.name}</option>`).join('')}
                        </select>
                    </label>
                    <label style="display:flex; flex-direction:column; gap:6px;">
                        <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Title *</span>
                        <input name="title" required style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                    </label>
                    <label style="display:flex; flex-direction:column; gap:6px;">
                        <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Description</span>
                        <textarea name="description" rows="2" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd; font-family:inherit;"></textarea>
                    </label>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">
                        <label style="display:flex; flex-direction:column; gap:6px;">
                            <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Priority</span>
                            <select name="priority" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                                <option value="low">Low</option>
                                <option value="medium" selected>Medium</option>
                                <option value="high">High</option>
                                <option value="urgent">Urgent</option>
                            </select>
                        </label>
                        <label style="display:flex; flex-direction:column; gap:6px;">
                            <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Due Date</span>
                            <input type="date" name="due_date" style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                        </label>
                    </div>
                    <div style="display:flex; gap:12px; justify-content:flex-end;">
                        <button type="button" class="btn-outline" data-action="cancel">Cancel</button>
                        <button type="submit" class="btn-primary">Create Task</button>
                    </div>
                </form>
            </div>
        `);
        modal.querySelector('[data-action="cancel"]').addEventListener('click', () => Modal.close(modal));
        modal.querySelector('#taskForm').addEventListener('submit', async (ev) => {
            ev.preventDefault();
            const fd = new FormData(ev.target);
            const payload = {};
            for (const [k, v] of fd.entries()) if (v) payload[k] = v;
            payload.farm_id = parseInt(payload.farm_id);
            const r = await Api.createTask(payload);
            if (!r.ok) { Toast.error(r.error); return; }
            Toast.success('Task created!');
            Modal.close(modal);
            loadAll();
        });
    }

    // ============================================================
    // WORKERS
    // ============================================================
    async function loadWorkers(params) {
        const r = await Api.listWorkers(params);
        if (!r.ok) return;
        state.workers = r.data || [];
        renderWorkers();
    }

    function renderWorkers() {
        const container = $('#workers-list');
        if (!container) return;
        if (!state.workers.length) {
            container.innerHTML = '<div style="text-align:center; padding:20px; color:#8a9c8c;">No workers yet.</div>';
            return;
        }
        container.innerHTML = state.workers.map((w) => `
            <div style="display:flex; align-items:center; gap:12px; padding:12px 0; border-bottom:1px dashed #eef1ea;">
                <div style="width:38px; height:38px; border-radius:50%; background:#1a3c2e; color:#e6b422; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:13px; flex-shrink:0;">
                    ${Fmt.initials(w.name)}
                </div>
                <div style="flex:1;">
                    <div style="font-weight:600; color:#1a3c2e; font-size:14px;">${w.name}</div>
                    <div style="font-size:12px; color:#4a5a4a;">${w.role || 'Worker'} · ${w.wage_type}${w.wage_amount ? ' · ' + Fmt.currency(w.wage_amount) : ''}</div>
                </div>
                <button class="btn-icon" data-action="delete-worker" data-id="${w.id}" style="color:#c0392b;"><i class="fas fa-user-minus"></i></button>
            </div>
        `).join('');

        $$('[data-action="delete-worker"]').forEach((el) =>
            el.addEventListener('click', async () => {
                const ok = await Modal.confirm('Deactivate this worker?');
                if (!ok) return;
                await Api.deleteWorker(el.dataset.id);
                Toast.success('Worker deactivated');
                loadAll();
            }));
    }

    // ============================================================
    // EQUIPMENT
    // ============================================================
    async function loadEquipment(params) {
        const r = await Api.listEquipment(params);
        if (!r.ok) return;
        state.equipment = r.data || [];
        renderEquipment();
    }

    function renderEquipment() {
        const container = $('#equipment-list');
        if (!container) return;
        if (!state.equipment.length) {
            container.innerHTML = '<div style="text-align:center; padding:20px; color:#8a9c8c;">No equipment tracked yet.</div>';
            return;
        }
        container.innerHTML = state.equipment.map((e) => `
            <div style="display:flex; align-items:center; gap:12px; padding:12px 0; border-bottom:1px dashed #eef1ea;">
                <div style="width:38px; height:38px; border-radius:10px; background:#e8f0e1; color:#1a3c2e; display:flex; align-items:center; justify-content:center; flex-shrink:0;">
                    <i class="fas fa-tractor"></i>
                </div>
                <div style="flex:1;">
                    <div style="font-weight:600; color:#1a3c2e; font-size:14px;">${e.name}</div>
                    <div style="font-size:12px; color:#4a5a4a;">${e.type || '—'} · Status: ${e.status}</div>
                </div>
                <span style="font-size:10px; padding:3px 8px; border-radius:20px; font-weight:700; text-transform:uppercase; background:${e.service_urgency === 'overdue' ? '#fde8e8' : e.service_urgency === 'due_soon' ? '#fef3d0' : '#e8f0e1'}; color:${e.service_urgency === 'overdue' ? '#c0392b' : e.service_urgency === 'due_soon' ? '#b8860b' : '#2e7d32'};">
                    ${e.service_urgency}
                </span>
            </div>
        `).join('');
    }

    // ============================================================
    // BOOT
    // ============================================================
    document.addEventListener('DOMContentLoaded', () => {
        loadFarms();
        $$('[data-action="new-task"]').forEach((el) =>
            el.addEventListener('click', (e) => { e.preventDefault(); openTaskModal(); }));
    });
})();