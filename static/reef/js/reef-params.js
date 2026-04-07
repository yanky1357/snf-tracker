/* ReefPilot — Parameter tracking dashboard + charts */

let paramChart = null;
let currentChartType = 'alkalinity';

async function loadParamStatus() {
    try {
        const data = await api('/params/status');
        renderParamGrid(data.params);
    } catch (err) {
        const grid = document.getElementById('param-grid');
        if (grid) grid.innerHTML = '<div class="empty-state">Could not load parameters. Pull down to retry.</div>';
    }
}

function renderParamGrid(params) {
    const grid = document.getElementById('param-grid');
    grid.innerHTML = '';

    params.forEach(p => {
        const card = document.createElement('div');
        card.className = 'param-card';
        card.onclick = () => openChart(p.type);

        const timeAgo = p.logged_at ? getTimeAgo(p.logged_at) : '';

        card.innerHTML = `
            <div class="param-card-header">
                <span class="param-icon">${p.icon}</span>
                <span class="param-status-dot ${p.status}"></span>
            </div>
            <div class="param-value ${p.value === null ? 'none' : ''}">${p.value !== null ? p.value : 'No data'}</div>
            <div class="param-label">${p.label}${p.unit ? ' (' + p.unit + ')' : ''}</div>
            ${timeAgo ? '<div class="param-time">' + timeAgo + '</div>' : ''}
        `;
        grid.appendChild(card);
    });
}

function getTimeAgo(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return diffMins + 'm ago';
    if (diffHours < 24) return diffHours + 'h ago';
    if (diffDays < 30) return diffDays + 'd ago';
    return date.toLocaleDateString();
}

// ── Chart ────────────────────────────────────────────────────────────────

function openChart(paramType) {
    currentChartType = paramType;
    document.getElementById('chart-modal').classList.remove('hidden');
    loadChart(paramType, 30);
}

function closeChart() {
    document.getElementById('chart-modal').classList.add('hidden');
    if (paramChart) {
        paramChart.destroy();
        paramChart = null;
    }
}

async function loadChart(paramType, days) {
    currentChartType = paramType;

    // Update active button
    document.querySelectorAll('.chart-range-btns .btn').forEach(btn => btn.classList.remove('btn-active'));
    document.querySelectorAll('.chart-range-btns .btn').forEach(btn => {
        if (btn.textContent.trim() === days + 'd') btn.classList.add('btn-active');
    });

    try {
        const data = await api(`/params/chart?type=${paramType}&days=${days}`);
        const info = data.param_info || {};
        document.getElementById('chart-title').textContent = (info.label || paramType) + ' History';

        renderChart(data.data, data.range, info);
    } catch (err) {
        showToast('Failed to load chart', 'error');
    }
}

function renderChart(points, range, info) {
    const canvas = document.getElementById('param-chart');
    if (paramChart) paramChart.destroy();

    const labels = points.map(p => {
        const d = new Date(p.logged_at);
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });
    const values = points.map(p => p.value);

    const datasets = [{
        label: info.label || '',
        data: values,
        borderColor: '#00B4D8',
        backgroundColor: 'rgba(0, 180, 216, 0.1)',
        fill: true,
        tension: 0.3,
        pointRadius: 4,
        pointBackgroundColor: '#00B4D8',
    }];

    // Add range bands if available
    const annotations = {};
    if (range && range.min !== undefined) {
        annotations.idealBand = {
            type: 'box',
            yMin: range.min,
            yMax: range.max,
            backgroundColor: 'rgba(0, 200, 83, 0.08)',
            borderWidth: 0,
        };
    }

    paramChart = new Chart(canvas, {
        type: 'line',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                annotation: annotations.idealBand ? { annotations } : undefined,
            },
            scales: {
                x: {
                    ticks: { color: '#8899AA', maxTicksLimit: 7 },
                    grid: { color: 'rgba(42, 58, 74, 0.5)' },
                },
                y: {
                    ticks: { color: '#8899AA' },
                    grid: { color: 'rgba(42, 58, 74, 0.5)' },
                },
            },
        },
    });
}

// ── Parameter Config (ranges, defaults, steps) ─────────────────────────

const PARAM_CONFIG = {
    alkalinity:  { min: 4.0,   max: 14.0,  step: 0.1,   default: 8.0,   unit: 'dKH', label: 'Alk',       decimals: 1 },
    calcium:     { min: 300,   max: 520,   step: 1,     default: 420,   unit: 'ppm', label: 'Calcium',   decimals: 0 },
    magnesium:   { min: 1100,  max: 1500,  step: 1,     default: 1350,  unit: 'ppm', label: 'Mag',       decimals: 0 },
    salinity:    { min: 1.018, max: 1.032, step: 0.001, default: 1.026, unit: 'SG',  label: 'Salinity',  decimals: 3 },
    ph:          { min: 7.4,   max: 8.8,   step: 0.1,   default: 8.2,   unit: '',    label: 'pH',        decimals: 1 },
    temperature: { min: 74,    max: 84,    step: 0.1,   default: 78.0,  unit: '°F',  label: 'Temp',      decimals: 1 },
    nitrate:     { min: 0,     max: 50,    step: 1,     default: 5,     unit: 'ppm', label: 'Nitrate',   decimals: 0 },
    nitrite:     { min: 0.00,  max: 2.00,  step: 0.05,  default: 0,     unit: 'ppm', label: 'Nitrite',   decimals: 2 },
    ammonia:     { min: 0.00,  max: 2.00,  step: 0.05,  default: 0,     unit: 'ppm', label: 'Ammonia',   decimals: 2 },
    phosphate:   { min: 0.00,  max: 1.00,  step: 0.01,  default: 0.03,  unit: 'ppm', label: 'Phosphate', decimals: 2 },
};

const PICKER_ITEM_H = 44;
const PICKER_VISIBLE = 5;

let entryValues = {};
let activePickerType = null;

// ── Manual Entry (card grid) ────────────────────────────────────────────

function showManualEntry() {
    entryValues = {};
    const grid = document.getElementById('entry-param-grid');
    grid.innerHTML = '';

    Object.entries(PARAM_CONFIG).forEach(([type, cfg]) => {
        const card = document.createElement('div');
        card.className = 'entry-card';
        card.id = `entry-card-${type}`;
        card.onclick = () => openPicker(type);
        card.innerHTML = `
            <div class="entry-card-label">${cfg.label}</div>
            <div class="entry-card-value" id="entry-val-${type}">&mdash;</div>
        `;
        grid.appendChild(card);
    });

    document.getElementById('manual-entry-modal').classList.remove('hidden');
}

async function saveManualEntry() {
    const params = Object.entries(entryValues).map(([type, value]) => ({ type, value }));

    if (params.length === 0) {
        showToast('Tap a parameter to set a value', 'error');
        return;
    }

    try {
        await api('/params', { method: 'POST', body: { params } });
        closeModal('manual-entry-modal');
        showToast(`Logged ${params.length} parameter(s)`, 'success');
        loadParamStatus();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ── Scroll Wheel Picker ─────────────────────────────────────────────────

function openPicker(type) {
    activePickerType = type;
    const cfg = PARAM_CONFIG[type];

    document.getElementById('picker-label').textContent = cfg.label;
    document.getElementById('picker-unit').textContent = cfg.unit;

    // Build wheel items
    const wheel = document.getElementById('picker-wheel');
    wheel.innerHTML = '';

    // Top spacers so first value can center
    for (let i = 0; i < Math.floor(PICKER_VISIBLE / 2); i++) {
        const sp = document.createElement('div');
        sp.className = 'picker-item picker-spacer';
        wheel.appendChild(sp);
    }

    const values = [];
    for (let v = cfg.min; v <= cfg.max + cfg.step / 2; v += cfg.step) {
        values.push(parseFloat(v.toFixed(cfg.decimals)));
    }

    values.forEach(v => {
        const el = document.createElement('div');
        el.className = 'picker-item';
        el.textContent = v.toFixed(cfg.decimals);
        el.dataset.value = v;
        wheel.appendChild(el);
    });

    // Bottom spacers
    for (let i = 0; i < Math.floor(PICKER_VISIBLE / 2); i++) {
        const sp = document.createElement('div');
        sp.className = 'picker-item picker-spacer';
        wheel.appendChild(sp);
    }

    // Show sheet
    const sheet = document.getElementById('picker-sheet');
    sheet.classList.remove('hidden');

    // Pre-scroll to default or previously entered value
    const target = entryValues[type] !== undefined ? entryValues[type] : cfg.default;
    const idx = values.findIndex(v => Math.abs(v - target) < cfg.step / 2);
    requestAnimationFrame(() => {
        wheel.scrollTop = (idx >= 0 ? idx : 0) * PICKER_ITEM_H;
    });

}

function confirmPickerValue() {
    const wheel = document.getElementById('picker-wheel');
    const idx = Math.round(wheel.scrollTop / PICKER_ITEM_H);
    const items = wheel.querySelectorAll('.picker-item:not(.picker-spacer)');
    const cfg = PARAM_CONFIG[activePickerType];

    if (items[idx]) {
        const value = parseFloat(items[idx].dataset.value);
        entryValues[activePickerType] = value;

        const valEl = document.getElementById(`entry-val-${activePickerType}`);
        valEl.textContent = value.toFixed(cfg.decimals);
        valEl.classList.add('has-value');
        document.getElementById(`entry-card-${activePickerType}`).classList.add('entry-card-set');
    }

    closePicker();
}

function clearPickerValue() {
    if (activePickerType) {
        delete entryValues[activePickerType];
        const valEl = document.getElementById(`entry-val-${activePickerType}`);
        valEl.textContent = '\u2014';
        valEl.classList.remove('has-value');
        document.getElementById(`entry-card-${activePickerType}`).classList.remove('entry-card-set');
    }
    closePicker();
}

function closePicker() {
    document.getElementById('picker-sheet').classList.add('hidden');
    activePickerType = null;
}
