/* ReefPilot — Cost Wizard & Dashboard */

let cwStep = 1;
let cwTotal = 10;
const cwData = {};   // {question_key: value}
const cwSkipped = new Set();
let cwDoughnut = null;
let cwUserDoses = false;  // set from user profile
let cwLightsData = null;  // loaded from /reef/api/lights
let cwLightsList = [];    // array of {brand, model, name, watts, qty, hours}
let cwCurrentLight = {};  // temp state for the light being configured

// ── Load cost dashboard on tab switch ──────────────────────────────────

async function loadCostDashboard() {
    try {
        const status = await api('/cost-wizard/status');
        if (status.completed) {
            document.getElementById('cost-wizard-prompt').classList.add('hidden');
            document.getElementById('cost-wizard-overlay').classList.add('hidden');
            document.getElementById('cost-dashboard').classList.remove('hidden');
            await renderCostDashboard();
        } else {
            document.getElementById('cost-wizard-prompt').classList.remove('hidden');
            document.getElementById('cost-dashboard').classList.add('hidden');
            document.getElementById('cost-wizard-overlay').classList.add('hidden');
        }
    } catch {
        document.getElementById('cost-wizard-prompt').classList.remove('hidden');
        document.getElementById('cost-dashboard').classList.add('hidden');
    }
}

async function renderCostDashboard() {
    try {
        const [recurringData, costsData] = await Promise.all([
            api('/recurring-costs'),
            api('/costs'),
        ]);
        const recurring = recurringData.recurring || [];
        const recurringTotal = recurringData.recurring_total || 0;

        // Calculate this month's purchases
        const costs = costsData.costs || [];
        const now = new Date();
        const thisMonthPurchases = costs.filter(c => {
            const d = new Date(c.purchase_date);
            return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
        });
        const purchaseTotal = thisMonthPurchases.reduce((sum, c) => sum + parseFloat(c.amount), 0);
        const grandTotal = recurringTotal + purchaseTotal;

        document.getElementById('cost-total-amount').textContent = formatCurrency(grandTotal);
        const subEl = document.getElementById('cost-total-sub');
        if (purchaseTotal > 0) {
            subEl.textContent = `${formatCurrency(recurringTotal)} recurring + ${formatCurrency(purchaseTotal)} purchases`;
        } else {
            subEl.textContent = 'recurring costs only';
        }

        // Doughnut chart
        renderCostDoughnut(recurring);

        // Line items
        const list = document.getElementById('cost-line-items');
        if (recurring.length === 0) {
            list.innerHTML = '<div class="empty-state">No recurring costs calculated</div>';
            return;
        }
        list.innerHTML = recurring.map(r => `
            <div class="cost-line-item">
                <div class="cost-line-info">
                    <div class="cost-line-category">${r.category}</div>
                    <div class="cost-line-desc">${r.description || ''}</div>
                </div>
                <div class="cost-line-right">
                    <div class="cost-line-amount">${formatCurrency(r.monthly_amount)}</div>
                    <span class="cost-badge cost-badge-${r.source === 'manual' ? 'actual' : 'estimated'}">${r.source === 'manual' ? 'Actual' : 'Estimated'}</span>
                </div>
                <button class="cost-line-edit" onclick="editRecurringCost(${r.id}, ${r.monthly_amount})" title="Edit">
                    <svg viewBox="0 0 24 24" width="16" height="16"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 000-1.41l-2.34-2.34a1 1 0 00-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z" fill="currentColor"/></svg>
                </button>
            </div>
        `).join('');

        // Also update home dashboard cost summary
        const homeAmount = document.getElementById('cost-summary-amount');
        if (homeAmount) homeAmount.textContent = formatCurrency(grandTotal);
    } catch {
        document.getElementById('cost-line-items').innerHTML = '<div class="empty-state">Could not load costs</div>';
    }
}

function renderCostDoughnut(recurring) {
    const canvas = document.getElementById('cost-doughnut-chart');
    if (!canvas) return;

    if (cwDoughnut) {
        cwDoughnut.destroy();
        cwDoughnut = null;
    }

    if (!recurring || recurring.length === 0) {
        canvas.parentElement.classList.add('hidden');
        return;
    }
    canvas.parentElement.classList.remove('hidden');

    const colors = ['#00B4D8', '#00C853', '#FFB300', '#FF5252', '#AB47BC', '#26A69A', '#FF7043'];
    cwDoughnut = new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: recurring.map(r => r.category),
            datasets: [{
                data: recurring.map(r => r.monthly_amount),
                backgroundColor: recurring.map((_, i) => colors[i % colors.length]),
                borderWidth: 0,
            }],
        },
        options: {
            cutout: '65%',
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#A8B8C8', font: { size: 11 }, padding: 12 },
                },
            },
        },
    });
}

function editRecurringCost(id, currentAmount) {
    const newVal = prompt('Enter new monthly amount:', currentAmount.toFixed(2));
    if (newVal === null) return;
    const num = parseFloat(newVal);
    if (isNaN(num) || num < 0) {
        showToast('Invalid amount', 'error');
        return;
    }
    api('/recurring-costs/' + id, {
        method: 'PUT',
        body: { monthly_amount: num },
    }).then(() => {
        showToast('Cost updated', 'success');
        renderCostDashboard();
    }).catch(err => showToast(err.message, 'error'));
}

function showManualCostModal() {
    // Switch to purchases view inline instead of opening modal
    switchCostView('purchases');
}

// ── Cost View Toggle ──────────────────────────────────────────────────

function switchCostView(view) {
    const monthlyView = document.getElementById('cost-view-monthly');
    const purchasesView = document.getElementById('cost-view-purchases');
    const segMonthly = document.getElementById('cost-seg-monthly');
    const segPurchases = document.getElementById('cost-seg-purchases');

    if (view === 'purchases') {
        monthlyView.classList.add('hidden');
        purchasesView.classList.remove('hidden');
        segMonthly.classList.remove('active');
        segPurchases.classList.add('active');
        document.getElementById('cost-quick-date').value = new Date().toISOString().split('T')[0];
        loadPurchasesList();
    } else {
        monthlyView.classList.remove('hidden');
        purchasesView.classList.add('hidden');
        segMonthly.classList.add('active');
        segPurchases.classList.remove('active');
    }
}

// ── Category Pills ────────────────────────────────────────────────────

function selectCostPill(btn) {
    document.querySelectorAll('.cost-pill').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
}

const PURCHASE_CATEGORY_ICONS = {
    'Livestock': { icon: '🐟', bg: 'rgba(0,180,216,0.12)' },
    'Equipment': { icon: '🔧', bg: 'rgba(255,179,0,0.12)' },
    'Supplements': { icon: '🔬', bg: 'rgba(171,71,188,0.12)' },
    'Food': { icon: '🍽️', bg: 'rgba(0,200,83,0.12)' },
    'Salt': { icon: '🧂', bg: 'rgba(38,166,154,0.12)' },
    'Testing': { icon: '📈', bg: 'rgba(255,82,82,0.12)' },
    'Other': { icon: '📦', bg: 'rgba(168,184,200,0.12)' },
};

// ── Quick Add Purchase ────────────────────────────────────────────────

async function handleQuickAddCost(e) {
    e.preventDefault();
    const activeCategory = document.querySelector('.cost-pill.active');
    const category = activeCategory ? activeCategory.dataset.cat : 'Other';
    const description = document.getElementById('cost-quick-desc').value.trim();
    const amount = parseFloat(document.getElementById('cost-quick-amount').value);
    const date = document.getElementById('cost-quick-date').value;

    if (!description || isNaN(amount) || amount <= 0) {
        showToast('Please fill in all fields', 'error');
        return false;
    }

    try {
        await api('/costs', {
            method: 'POST',
            body: { category, description, amount, purchase_date: date },
        });
        showToast('Purchase logged!', 'success');
        document.getElementById('cost-quick-desc').value = '';
        document.getElementById('cost-quick-amount').value = '';
        await loadPurchasesList();
        await updateCostTotals();
    } catch (err) {
        showToast(err.message, 'error');
    }
    return false;
}

// ── Load & Render Purchases ───────────────────────────────────────────

async function loadPurchasesList() {
    const list = document.getElementById('cost-purchases-list');
    const summaryEl = document.getElementById('cost-purchases-summary');

    try {
        const data = await api('/costs');
        const costs = data.costs || [];

        // Month total
        const now = new Date();
        const thisMonth = costs.filter(c => {
            const d = new Date(c.purchase_date);
            return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
        });
        const monthTotal = thisMonth.reduce((sum, c) => sum + parseFloat(c.amount), 0);

        summaryEl.innerHTML = `
            <div class="purchases-month-total">
                <span>Spent this month</span>
                <span>${formatCurrency(monthTotal)}</span>
            </div>
        `;

        if (costs.length === 0) {
            list.innerHTML = '<div class="empty-state" style="padding:32px 0;color:var(--text-muted)">No purchases yet — log your first one above!</div>';
            return;
        }

        list.innerHTML = costs.map(c => {
            const catInfo = PURCHASE_CATEGORY_ICONS[c.category] || PURCHASE_CATEGORY_ICONS['Other'];
            const dateStr = formatDateShort(c.purchase_date);
            return `
                <div class="purchase-item">
                    <div class="purchase-icon" style="background:${catInfo.bg}">${catInfo.icon}</div>
                    <div class="purchase-info">
                        <div class="purchase-desc">${c.description || c.category}</div>
                        <div class="purchase-meta">${c.category} · ${dateStr}</div>
                    </div>
                    <div class="purchase-amount">${formatCurrency(c.amount)}</div>
                    <button class="purchase-delete" onclick="deleteAndRefreshPurchase(${c.id})" title="Remove">&times;</button>
                </div>
            `;
        }).join('');
    } catch {
        list.innerHTML = '<div class="empty-state" style="color:var(--text-muted)">Could not load purchases</div>';
    }
}

async function deleteAndRefreshPurchase(id) {
    try {
        await api('/costs/' + id, { method: 'DELETE' });
        showToast('Purchase removed', 'success');
        await loadPurchasesList();
        await updateCostTotals();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function updateCostTotals() {
    try {
        const [recurringData, costsData] = await Promise.all([
            api('/recurring-costs'),
            api('/costs'),
        ]);
        const recurringTotal = recurringData.recurring_total || 0;
        const costs = costsData.costs || [];
        const now = new Date();
        const thisMonthPurchases = costs.filter(c => {
            const d = new Date(c.purchase_date);
            return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
        });
        const purchaseTotal = thisMonthPurchases.reduce((sum, c) => sum + parseFloat(c.amount), 0);
        const grandTotal = recurringTotal + purchaseTotal;

        document.getElementById('cost-total-amount').textContent = formatCurrency(grandTotal);
        const subEl = document.getElementById('cost-total-sub');
        if (purchaseTotal > 0) {
            subEl.textContent = `${formatCurrency(recurringTotal)} recurring + ${formatCurrency(purchaseTotal)} purchases`;
        } else {
            subEl.textContent = 'recurring costs only';
        }

        const homeAmount = document.getElementById('cost-summary-amount');
        if (homeAmount) homeAmount.textContent = formatCurrency(grandTotal);
    } catch {}
}


// ── Cost Wizard ────────────────────────────────────────────────────────

async function startCostWizard() {
    cwStep = 1;
    Object.keys(cwData).forEach(k => delete cwData[k]);
    cwSkipped.clear();

    // Check if user doses (from window.currentUserProfile set in reef-app.js)
    cwUserDoses = window.currentUserProfile && window.currentUserProfile.dosing &&
                  window.currentUserProfile.dosing !== 'none';
    cwTotal = cwUserDoses ? 10 : 9;

    // Try to load existing answers for re-run
    api('/cost-wizard/answers').then(data => {
        (data.answers || []).forEach(a => {
            if (a.skipped) {
                cwSkipped.add(a.question_key);
            } else {
                cwData[a.question_key] = a.answer_value;
            }
        });
    }).catch(() => {});

    // Load lights data and populate brand list
    cwLightsList = [];
    cwCurrentLight = {};
    if (!cwLightsData) {
        try {
            const resp = await api('/lights');
            cwLightsData = resp.lights || {};
        } catch { cwLightsData = {}; }
    }
    cwPopulateLightBrands();
    cwRenderLightsSummary();

    document.getElementById('cost-wizard-prompt').classList.add('hidden');
    document.getElementById('cost-dashboard').classList.add('hidden');
    document.getElementById('cost-wizard-overlay').classList.remove('hidden');
    document.getElementById('cw-loading').classList.add('hidden');
    document.getElementById('cw-nav').classList.remove('hidden');

    cwUpdateUI();
}

// ── Light management (multi-light support) ─────────────────────────────

function cwPopulateLightBrands() {
    const container = document.getElementById('cw-light-brands');
    if (!container || !cwLightsData) return;
    const brands = Object.entries(cwLightsData);
    container.innerHTML = brands.map(([key, data]) =>
        `<div class="cw-list-item" data-key="light_brand" data-val="${key}" onclick="cwSelectLightBrand(this, '${key}')">
            <span>${data.brand}</span>
            <span class="cw-list-item-sub">${Object.keys(data.models).length > 0 ? Object.keys(data.models).length + ' models' : 'Enter wattage'}</span>
        </div>`
    ).join('');
}

function cwSelectLightBrand(el, brandKey) {
    el.parentElement.querySelectorAll('.cw-list-item').forEach(e => e.classList.remove('selected'));
    el.classList.add('selected');
    cwCurrentLight = { brand: brandKey };
    cwPopulateLightModels(brandKey);
}

function cwPopulateLightModels(brandKey) {
    const container = document.getElementById('cw-light-models');
    const customWrap = document.getElementById('cw-light-custom-watts');
    const wattsDisplay = document.getElementById('cw-light-watts-display');
    if (!container) return;

    // Reset step 2 state
    customWrap.classList.add('hidden');
    wattsDisplay.classList.add('hidden');
    document.querySelectorAll('.cw-qty-btn').forEach(b => b.classList.remove('selected'));
    document.querySelector('.cw-qty-btn[data-qty="1"]').classList.add('selected');
    document.querySelectorAll('.cw-hours-btn').forEach(b => b.classList.remove('selected'));
    cwCurrentLight.qty = 1;
    cwCurrentLight.hours = null;

    const brandData = cwLightsData[brandKey];
    const brandName = brandData ? brandData.brand : 'Custom';
    document.getElementById('cw-model-title').textContent = brandName + ' — which model?';

    if (!brandData || Object.keys(brandData.models).length === 0) {
        container.classList.add('hidden');
        customWrap.classList.remove('hidden');
        cwCurrentLight.model = 'custom';
        cwCurrentLight.name = 'Custom Light';
        return;
    }

    container.classList.remove('hidden');
    const models = Object.entries(brandData.models);
    container.innerHTML = models.map(([key, model]) =>
        `<div class="cw-list-item" data-val="${key}" onclick="cwSelectLightModel(this, '${key}', '${model.name}', ${model.watts})">
            <span>${model.name}</span>
            <span class="cw-list-item-sub">${model.watts}W</span>
        </div>`
    ).join('');
}

function cwSelectLightModel(el, modelKey, modelName, watts) {
    el.parentElement.querySelectorAll('.cw-list-item').forEach(e => e.classList.remove('selected'));
    el.classList.add('selected');
    cwCurrentLight.model = modelKey;
    cwCurrentLight.name = modelName;
    cwCurrentLight.watts = watts;
    cwUpdateLightWattsDisplay();
}

function cwSelectLightQty(qty) {
    document.querySelectorAll('.cw-qty-btn').forEach(b => b.classList.remove('selected'));
    document.querySelector(`.cw-qty-btn[data-qty="${qty}"]`).classList.add('selected');
    cwCurrentLight.qty = qty;
    cwUpdateLightWattsDisplay();
}

function cwSelectLightHours(hours) {
    document.querySelectorAll('.cw-hours-btn').forEach(b => b.classList.remove('selected'));
    document.querySelector(`.cw-hours-btn[data-hours="${hours}"]`).classList.add('selected');
    cwCurrentLight.hours = hours;
}

function cwUpdateLightWattsDisplay() {
    const display = document.getElementById('cw-light-watts-display');
    const watts = cwCurrentLight.watts || 0;
    const qty = cwCurrentLight.qty || 1;
    if (watts > 0) {
        document.getElementById('cw-watts-value').textContent = (watts * qty);
        display.classList.remove('hidden');
    } else {
        display.classList.add('hidden');
    }
}

function cwFinalizeLightEntry() {
    // For custom/other lights, read wattage from input
    if (cwCurrentLight.model === 'custom') {
        const wInput = document.getElementById('cw-light-wattage');
        cwCurrentLight.watts = parseFloat(wInput.value) || 100;
        cwCurrentLight.name = 'Custom (' + cwCurrentLight.watts + 'W)';
    }
    if (!cwCurrentLight.hours) cwCurrentLight.hours = 8;
    if (!cwCurrentLight.qty) cwCurrentLight.qty = 1;
    if (!cwCurrentLight.watts) cwCurrentLight.watts = 100;

    cwLightsList.push({ ...cwCurrentLight });
    cwCurrentLight = {};
}

function cwAddLightAndPickAnother() {
    if (!cwCurrentLight.brand) {
        showToast('Select a model first', 'error');
        return;
    }
    cwFinalizeLightEntry();
    cwRenderLightsSummary();
    // Go back to step 1 (brand selection)
    cwStep = 1;
    cwUpdateUI();
    showToast('Light added! Pick another or continue.', 'success');
}

function cwRemoveLight(index) {
    cwLightsList.splice(index, 1);
    cwRenderLightsSummary();
}

function cwRenderLightsSummary() {
    const container = document.getElementById('cw-lights-added');
    if (!container) return;
    if (cwLightsList.length === 0) {
        container.classList.add('hidden');
        return;
    }
    container.classList.remove('hidden');
    container.innerHTML = '<div class="cw-lights-label">Your lights:</div>' +
        cwLightsList.map((l, i) =>
            `<div class="cw-light-chip">
                <span>${l.qty}x ${l.name} (${l.watts}W, ${l.hours}h/day)</span>
                <button class="cw-light-chip-remove" onclick="cwRemoveLight(${i})">&times;</button>
            </div>`
        ).join('');
}

function cwGetEffectiveStep(step) {
    // If user doesn't dose, skip step 7
    if (!cwUserDoses && step >= 7) return step + 1;
    return step;
}

function cwUpdateUI() {
    const effectiveStep = cwGetEffectiveStep(cwStep);

    // Hide all steps, show current
    document.querySelectorAll('[data-cw-step]').forEach(el => {
        el.classList.remove('active');
        if (parseInt(el.dataset.cwStep) === effectiveStep) {
            el.classList.add('active');
        }
    });

    // Progress bar
    const pct = Math.round((cwStep / cwTotal) * 100);
    document.getElementById('cw-progress-fill').style.width = pct + '%';
    document.getElementById('cw-step-label').textContent = `Step ${cwStep} of ${cwTotal}`;

    // Back button visibility
    document.getElementById('cw-back').style.visibility = cwStep === 1 ? 'hidden' : 'visible';

    // Next button text
    document.getElementById('cw-next').textContent = cwStep === cwTotal ? 'Calculate' : 'Continue';
}

function cwSelect(btn) {
    const key = btn.dataset.key;
    const val = btn.dataset.val;
    // Deselect siblings with same key
    btn.parentElement.querySelectorAll(`[data-key="${key}"]`).forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    cwData[key] = val;
    cwSkipped.delete(key);

    // Special: carbon/gfo toggle frequency visibility
    if (key === 'uses_carbon') {
        document.getElementById('cw-carbon-freq').classList.toggle('hidden', val !== 'yes');
        if (val === 'yes' && !cwData.carbon_frequency) cwData.carbon_frequency = 'monthly';
    }
    if (key === 'uses_gfo') {
        document.getElementById('cw-gfo-freq').classList.toggle('hidden', val !== 'yes');
        if (val === 'yes' && !cwData.gfo_frequency) cwData.gfo_frequency = 'monthly';
    }
}

function cwPreset(btn) {
    const key = btn.dataset.key;
    const val = btn.dataset.val;
    // Deselect siblings with same key
    btn.parentElement.querySelectorAll(`[data-key="${key}"]`).forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    cwData[key] = val;
    cwSkipped.delete(key);

    // Same carbon/gfo toggle logic
    if (key === 'uses_carbon') {
        document.getElementById('cw-carbon-freq').classList.toggle('hidden', val !== 'yes');
        if (val === 'yes' && !cwData.carbon_frequency) cwData.carbon_frequency = 'monthly';
    }
    if (key === 'uses_gfo') {
        document.getElementById('cw-gfo-freq').classList.toggle('hidden', val !== 'yes');
        if (val === 'yes' && !cwData.gfo_frequency) cwData.gfo_frequency = 'monthly';
    }
}

function cwInput(key, val) {
    cwData[key] = val;
    cwSkipped.delete(key);
}

function cwShowRodi(type) {
    document.getElementById('cw-rodi-own').classList.toggle('hidden', type !== 'own');
    document.getElementById('cw-rodi-buy').classList.toggle('hidden', type !== 'buy');
}

function cwNext() {
    if (cwStep >= cwTotal) {
        cwSubmit();
        return;
    }
    // Finalize current light entry when advancing past step 2 (model/qty/hours)
    const effectiveStep = cwGetEffectiveStep(cwStep);
    if (effectiveStep === 2 && cwCurrentLight.brand) {
        cwFinalizeLightEntry();
        cwRenderLightsSummary();
    }
    cwStep++;
    cwUpdateUI();
}

function cwPrev() {
    if (cwStep <= 1) return;
    cwStep--;
    cwUpdateUI();
}

function cwSkip() {
    const effectiveStep = cwGetEffectiveStep(cwStep);

    // If skipping light steps (1 or 2) and no lights added yet, mark lights as skipped
    if ((effectiveStep === 1 || effectiveStep === 2) && cwLightsList.length === 0) {
        cwSkipped.add('light_fixtures');
        cwCurrentLight = {};
        // Jump past both light steps
        if (effectiveStep === 1) {
            cwStep++;  // skip to step 2, then cwNext will advance to 3
        }
    } else {
        // Mark all keys for current step as skipped
        const stepEl = document.querySelector(`[data-cw-step="${effectiveStep}"]`);
        if (stepEl) {
            stepEl.querySelectorAll('[data-key]').forEach(el => {
                cwSkipped.add(el.dataset.key);
                delete cwData[el.dataset.key];
            });
            stepEl.querySelectorAll('input, select').forEach(el => {
                const oninput = el.getAttribute('oninput') || el.getAttribute('onchange') || '';
                const match = oninput.match(/cwInput\('([^']+)'/);
                if (match) cwSkipped.add(match[1]);
            });
        }
    }
    cwNext();
}

async function cwSubmit() {
    // Show loading
    document.querySelectorAll('[data-cw-step]').forEach(el => el.classList.remove('active'));
    document.getElementById('cw-nav').classList.add('hidden');
    document.getElementById('cw-loading').classList.remove('hidden');

    // Build answers array
    const allKeys = new Set([...Object.keys(cwData), ...cwSkipped]);
    const stepCategoryMap = {
        light_fixtures: 'lighting', light_brand: 'lighting', light_model: 'lighting',
        light_type: 'lighting', light_wattage: 'lighting', light_hours: 'lighting',
        heater_wattage: 'heating',
        return_pump_wattage: 'pumps', powerhead_count: 'pumps', powerhead_wattage: 'pumps',
        skimmer_wattage: 'skimmer',
        uses_carbon: 'filter_media', carbon_frequency: 'filter_media',
        uses_gfo: 'filter_media', gfo_frequency: 'filter_media',
        filter_sock_frequency: 'filter_media',
        dosing_type: 'dosing', dosing_brand: 'dosing', dosing_daily_ml: 'dosing',
        feedings_per_day: 'food', food_type: 'food',
        rodi_makes_own: 'rodi', rodi_stage: 'rodi', rodi_buy_price: 'rodi',
        salt_bucket_price: 'salt', electricity_rate: 'electricity',
    };

    const answers = [];

    // Serialize multi-light list as a single JSON answer
    if (cwLightsList.length > 0) {
        answers.push({
            category: 'lighting',
            question_key: 'light_fixtures',
            answer_value: JSON.stringify(cwLightsList),
            skipped: false,
        });
    } else if (cwSkipped.has('light_fixtures')) {
        answers.push({
            category: 'lighting',
            question_key: 'light_fixtures',
            answer_value: '',
            skipped: true,
        });
    }

    // Remove old flat light keys + light_fixtures from allKeys — we handle light_fixtures explicitly above
    const lightKeys = new Set(['light_brand', 'light_model', 'light_type', 'light_wattage', 'light_hours', 'light_fixtures']);

    allKeys.forEach(key => {
        if (lightKeys.has(key)) return;  // skip old flat light keys
        answers.push({
            category: stepCategoryMap[key] || 'other',
            question_key: key,
            answer_value: cwData[key] || '',
            skipped: cwSkipped.has(key),
        });
    });

    try {
        const result = await api('/cost-wizard/submit', {
            method: 'POST',
            body: { answers },
        });

        // Switch to dashboard
        document.getElementById('cost-wizard-overlay').classList.add('hidden');
        document.getElementById('cost-dashboard').classList.remove('hidden');
        await renderCostDashboard();
        showToast('Costs calculated!', 'success');
    } catch (err) {
        showToast(err.message || 'Failed to calculate costs', 'error');
        document.getElementById('cw-loading').classList.add('hidden');
        document.getElementById('cw-nav').classList.remove('hidden');
        cwUpdateUI();
    }
}
