/**
 * Marcbantu Africa — Farm creation helper.
 * Provides Farm.openCreateModal() used by dashboard, planning, and records.
 */
(function () {
    'use strict';

    const { Toast, Modal } = window.UI;

    async function openCreateModal(onCreated) {
        const modal = Modal.open(`
            <div style="padding:28px; max-width:520px;">
                <h2 style="margin:0 0 6px; color:#1a3c2e; display:flex; align-items:center; gap:10px;">
                    <i class="fas fa-seedling" style="color:#d4a017;"></i> Create Your Farm
                </h2>
                <p style="margin:0 0 20px; color:#4a5a4a; font-size:.9rem;">
                    Add your first farm to start tracking records, planning seasons, and seeing profit.
                </p>
                <form id="createFarmForm" style="display:flex; flex-direction:column; gap:14px;">
                    <label style="display:flex; flex-direction:column; gap:6px;">
                        <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Farm Name *</span>
                        <input name="name" required placeholder="e.g. Home Farm, Kieni Plot"
                            style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                    </label>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">
                        <label style="display:flex; flex-direction:column; gap:6px;">
                            <span style="font-size:13px; font-weight:600; color:#1a3c2e;">Size (acres)</span>
                            <input type="number" step="0.01" name="size_acres" placeholder="e.g. 5"
                                style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                        </label>
                        <label style="display:flex; flex-direction:column; gap:6px;">
                            <span style="font-size:13px; font-weight:600; color:#1a3c2e;">County</span>
                            <input name="county" placeholder="e.g. Nyeri"
                                style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                        </label>
                    </div>
                    <details style="border:1px solid #e2e8dd; border-radius:10px; padding:12px;">
                        <summary style="cursor:pointer; font-weight:600; color:#1a3c2e; font-size:14px;">
                            Optional: GPS coordinates (for weather)
                        </summary>
                        <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-top:12px;">
                            <label style="display:flex; flex-direction:column; gap:6px;">
                                <span style="font-size:12px; font-weight:600; color:#1a3c2e;">Latitude</span>
                                <input type="number" step="0.0001" name="latitude" placeholder="-1.2864"
                                    style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                            </label>
                            <label style="display:flex; flex-direction:column; gap:6px;">
                                <span style="font-size:12px; font-weight:600; color:#1a3c2e;">Longitude</span>
                                <input type="number" step="0.0001" name="longitude" placeholder="36.8172"
                                    style="padding:10px; border-radius:10px; border:1.5px solid #e2e8dd;">
                            </label>
                        </div>
                        <button type="button" id="useMyLocation" class="btn-outline"
                            style="margin-top:10px; width:100%; justify-content:center; font-size:13px;">
                            <i class="fas fa-location-arrow"></i> Use my current location
                        </button>
                    </details>
                    <div style="display:flex; gap:12px; justify-content:flex-end; margin-top:6px;">
                        <button type="button" class="btn-outline" data-action="cancel">Cancel</button>
                        <button type="submit" class="btn-primary">Create Farm</button>
                    </div>
                </form>
            </div>
        `);

        modal.querySelector('[data-action="cancel"]').addEventListener('click', () => Modal.close(modal));

        // "Use my location" — fills lat/lon from browser geolocation
        modal.querySelector('#useMyLocation').addEventListener('click', () => {
            if (!navigator.geolocation) {
                Toast.warning('Geolocation not supported by this browser');
                return;
            }
            Toast.info('Getting your location...');
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    modal.querySelector('[name="latitude"]').value = pos.coords.latitude.toFixed(4);
                    modal.querySelector('[name="longitude"]').value = pos.coords.longitude.toFixed(4);
                    Toast.success('Location set!');
                },
                (err) => Toast.error('Could not get location: ' + err.message),
                { timeout: 10000 }
            );
        });

        const form = modal.querySelector('#createFarmForm');
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const fd = new FormData(form);
            const payload = {};
            for (const [k, v] of fd.entries()) {
                if (v !== '') {
                    payload[k] = ['size_acres', 'latitude', 'longitude'].includes(k) ? parseFloat(v) : v;
                }
            }

            const btn = form.querySelector('button[type="submit"]');
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating...';

            const r = await Api.createFarm(payload);
            if (!r.ok) {
                Toast.error(r.error || 'Failed to create farm');
                btn.disabled = false;
                btn.textContent = 'Create Farm';
                return;
            }

            Toast.success('Farm created!');
            Modal.close(modal);
            if (typeof onCreated === 'function') onCreated(r.data);
        });

        return modal;
    }

    window.Farm = { openCreateModal };
})();
