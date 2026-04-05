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

// ── Manual Entry ─────────────────────────────────────────────────────────

function showManualEntry() {
    const fieldsEl = document.getElementById('manual-entry-fields');
    fieldsEl.innerHTML = '';

    const paramTypes = [
        { type: 'salinity', label: 'Salinity (SG)', placeholder: '1.026' },
        { type: 'ph', label: 'pH', placeholder: '8.2' },
        { type: 'alkalinity', label: 'Alkalinity (dKH)', placeholder: '8.0' },
        { type: 'calcium', label: 'Calcium (ppm)', placeholder: '430' },
        { type: 'magnesium', label: 'Magnesium (ppm)', placeholder: '1320' },
        { type: 'nitrate', label: 'Nitrate (ppm)', placeholder: '5' },
        { type: 'nitrite', label: 'Nitrite (ppm)', placeholder: '0' },
        { type: 'ammonia', label: 'Ammonia (ppm)', placeholder: '0' },
        { type: 'phosphate', label: 'Phosphate (ppm)', placeholder: '0.03' },
        { type: 'temperature', label: 'Temperature (F)', placeholder: '78' },
    ];

    paramTypes.forEach(p => {
        const div = document.createElement('div');
        div.className = 'form-group';
        div.innerHTML = `
            <label>${p.label}</label>
            <input type="number" step="any" data-type="${p.type}" placeholder="${p.placeholder}">
        `;
        fieldsEl.appendChild(div);
    });

    document.getElementById('manual-entry-modal').classList.remove('hidden');
}

async function handleManualEntry(e) {
    e.preventDefault();
    const inputs = document.querySelectorAll('#manual-entry-fields input[data-type]');
    const params = [];

    inputs.forEach(input => {
        if (input.value) {
            params.push({
                type: input.dataset.type,
                value: parseFloat(input.value),
            });
        }
    });

    if (params.length === 0) {
        showToast('Enter at least one parameter', 'error');
        return false;
    }

    try {
        await api('/params', {
            method: 'POST',
            body: { params },
        });
        closeModal('manual-entry-modal');
        showToast(`Logged ${params.length} parameter(s)`, 'success');
        loadParamStatus();
    } catch (err) {
        showToast(err.message, 'error');
    }
    return false;
}
