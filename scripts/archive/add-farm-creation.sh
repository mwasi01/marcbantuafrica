#!/usr/bin/env bash
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"
FE=frontend

# ============================================================
# 1. Create farms.js — shared create-farm modal
# ============================================================
cat > "$FE/assets/js/farms.js" << 'JSEOF'
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
JSEOF
echo "  created: $FE/assets/js/farms.js"

# ============================================================
# 2. Wire farms.js into pages that need it
# ============================================================
for page in dashboard.html planning.html records.html; do
    if ! grep -q 'assets/js/farms.js' "$FE/$page"; then
        # Insert farms.js right before register-sw.js
        sed -i 's|<script src="/assets/js/register-sw.js"></script>|<script src="/assets/js/farms.js"></script>\n    <script src="/assets/js/register-sw.js"></script>|' "$FE/$page"
        echo "  added farms.js to $page"
    fi
done

# ============================================================
# 3. Patch dashboard.js — show "create your first farm" CTA
# ============================================================
python3 - << 'PYEOF'
path = "frontend/assets/js/dashboard.js"
with open(path) as fh:
    src = fh.read()

old = """        const data = result.data;
        renderGreeting(data.farmer);"""

new = """        const data = result.data;

        // If the farmer has no farms, show a prominent setup CTA
        if (data.needs_setup) {
            renderGreeting(data.farmer);
            renderNeedsSetup(data);
            return;
        }

        renderGreeting(data.farmer);"""

src = src.replace(old, new, 1)

# Add renderNeedsSetup function before renderKPIs
marker = "    function renderKPIs(data) {"
helper = '''    function renderNeedsSetup(data) {
        const container = $('#kpi-container');
        if (!container) return;
        container.innerHTML = `
            <div class="kpi" style="grid-column:1/-1; background:linear-gradient(135deg,#2f5d3a,#1a3c2e); color:#fff; padding:2rem; border-radius:20px; border:2px solid #d4a017;">
                <div style="font-size:1.3rem; font-weight:800; margin-bottom:.5rem;">
                    <i class="fas fa-seedling" style="color:#e6b422;"></i> Welcome to Marcbantu!
                </div>
                <p style="color:#c8d6ca; margin:0 0 1.2rem; font-size:.95rem;">
                    You don't have any farms yet. Create your first farm to unlock records, planning, finance, weather, and the rest of your dashboard.
                </p>
                <button class="btn-primary" id="create-first-farm" style="font-size:1rem;">
                    <i class="fas fa-plus-circle"></i> Create Your First Farm
                </button>
            </div>
        `;
        const btn = document.getElementById('create-first-farm');
        if (btn) {
            btn.addEventListener('click', () => {
                window.Farm.openCreateModal(() => loadDashboard());
            });
        }
    }

    function renderKPIs(data) {'''

src = src.replace(marker, helper, 1)

with open(path, "w") as fh:
    fh.write(src)

print("  patched: dashboard.js")
PYEOF

# ============================================================
# 4. Patch planning.js — inline create-farm panel
# ============================================================
python3 - << 'PYEOF'
path = "frontend/assets/js/planning.js"
with open(path) as fh:
    src = fh.read()

old = """        state.farms = result.data || [];
        renderFarmSelector();
        if (state.farms.length) {
            state.currentFarmId = state.currentFarmId || state.farms[0].id;
            await Promise.all([
                loadEnterprises(),
                loadBudgets(),
                loadCashFlow(),
            ]);
        }
    }"""

new = """        state.farms = result.data || [];
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
    }"""

src = src.replace(old, new, 1)

with open(path, "w") as fh:
    fh.write(src)

print("  patched: planning.js")
PYEOF

# ============================================================
# 5. Patch records.js — create-farm modal instead of redirect
# ============================================================
python3 - << 'PYEOF'
path = "frontend/assets/js/records.js"
with open(path) as fh:
    src = fh.read()

old = """        const farms = state.farms;
        if (!farms.length) {
            Toast.warning('Please create a farm first');
            window.location.href = 'planning.html';
            return;
        }"""

new = """        const farms = state.farms;
        if (!farms.length) {
            Toast.info('Create a farm first');
            if (window.Farm) {
                window.Farm.openCreateModal(() => loadFarms());
            } else {
                window.location.href = 'planning.html';
            }
            return;
        }"""

src = src.replace(old, new, 1)

with open(path, "w") as fh:
    fh.write(src)

print("  patched: records.js")
PYEOF

echo ""
echo "Verify:"
for f in dashboard.html planning.html records.html; do
    if grep -q "assets/js/farms.js" "$FE/$f"; then
        echo "  ✓ $f includes farms.js"
    else
        echo "  ✗ $f MISSING farms.js"
    fi
done
grep -l "window.Farm" "$FE/assets/js/"*.js
