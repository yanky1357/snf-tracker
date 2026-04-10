/* ReefPilot — Home Dashboard */

let dashboardData = null;

async function loadDashboard() {
    try {
        const data = await api('/dashboard');
        dashboardData = data;
        renderTankHero(data.tank_photo_url);
        renderHealthScore(data.health_score);
        renderParamChips(data.param_status);
        renderInsights(data.insights);
        renderDashDueToday(data.due_today);
        renderDashUpcoming(data.upcoming_tasks);
        renderDashSetupPrompt(data.has_maintenance);
        renderDashMilestones(data.active_milestones);
        renderCostSummary(data.cost_summary);
        renderRecentActivity();
        loadRoutinePresets();
        loadJournal();
    } catch (err) {
        if (!navigator.onLine) {
            showToast('You\'re offline — dashboard data may be stale', 'error');
        }
    }
}

// ── Tank Hero Photo ─────────────────────────────────────────────────────

function renderTankHero(photoUrl) {
    const hero = document.getElementById('tank-hero');
    const img = document.getElementById('tank-hero-img');

    hero.classList.remove('has-photo', 'no-photo');

    if (photoUrl) {
        img.src = photoUrl;
        hero.classList.add('has-photo');
    } else {
        img.src = '';
        hero.classList.add('no-photo');
    }
}

function initTankPhotoUpload() {
    const btn = document.getElementById('tank-hero-upload-btn');
    const input = document.getElementById('tank-photo-input');
    const hero = document.getElementById('tank-hero');

    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        input.click();
    });

    // Also allow clicking the whole placeholder area
    hero.addEventListener('click', () => {
        if (hero.classList.contains('no-photo')) {
            input.click();
        }
    });

    input.addEventListener('change', async () => {
        const file = input.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('photo', file);

        try {
            const res = await fetch('/reef/api/tank-photo', {
                method: 'POST',
                body: formData,
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Upload failed');
            renderTankHero(data.tank_photo_url);
            showToast('Tank photo updated!');
        } catch (err) {
            showToast(err.message, 'error');
        }

        input.value = '';
    });
}

// Init on load
document.addEventListener('DOMContentLoaded', initTankPhotoUpload);

// ── Health Score ─────────────────────────────────────────────────────────

function renderHealthScore(score) {
    if (score === undefined || score === null) score = 0;

    const circle = document.getElementById('health-score-circle');
    const valueEl = document.getElementById('health-score-value');
    const labelEl = document.getElementById('health-score-label');

    let color;
    let label;
    if (score < 40) {
        color = 'var(--danger)';
        label = 'Needs Attention';
    } else if (score < 70) {
        color = 'var(--warning)';
        label = 'Getting There';
    } else {
        color = 'var(--success)';
        label = 'Looking Great';
    }

    circle.setAttribute('stroke', color);
    labelEl.textContent = label;
    labelEl.style.color = color;

    const circumference = 2 * Math.PI * 52;
    const targetOffset = circumference - (circumference * score / 100);
    let current = 0;
    const duration = 1000;
    const startTime = performance.now();

    function animate(now) {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - (1 - progress) * (1 - progress);
        current = Math.round(score * eased);

        valueEl.textContent = current;
        const currentOffset = circumference - (circumference * current / 100);
        circle.setAttribute('stroke-dashoffset', currentOffset);

        if (progress < 1) {
            requestAnimationFrame(animate);
        }
    }

    requestAnimationFrame(animate);
}

// ── Param Chips ─────────────────────────────────────────────────────────

function renderParamChips(params) {
    const container = document.getElementById('param-chips-scroll');
    if (!params || params.length === 0) {
        container.innerHTML = '';
        return;
    }

    container.innerHTML = params.map(p => {
        const dotClass = p.status || 'none';
        const displayVal = p.value !== null && p.value !== undefined ? p.value : '--';
        return `
            <div class="param-chip">
                <span class="param-chip-dot ${dotClass}"></span>
                <span class="param-chip-label">${p.label || p.type}</span>
                <span class="param-chip-value">${displayVal}</span>
            </div>
        `;
    }).join('');
}

// ── Insights ────────────────────────────────────────────────────────────

function renderInsights(insights) {
    const container = document.getElementById('insights-list');
    if (!insights || insights.length === 0) {
        container.innerHTML = '<div class="empty-state">No insights yet</div>';
        return;
    }

    // Filter out dismissed insights
    const dismissed = JSON.parse(localStorage.getItem('reef_dismissed_insights') || '[]');
    const visible = insights.filter(i => !dismissed.includes(i.id || i.message));

    if (visible.length === 0) {
        container.innerHTML = '<div class="empty-state">No insights yet</div>';
        return;
    }

    container.innerHTML = visible.map(i => {
        let borderColor, icon;
        switch (i.type) {
            case 'danger':
            case 'alert':
                borderColor = 'var(--danger)';
                icon = '!';
                break;
            case 'warning':
                borderColor = 'var(--warning)';
                icon = '!';
                break;
            case 'success':
                borderColor = 'var(--success)';
                icon = '\u2713';
                break;
            default:
                borderColor = 'var(--accent)';
                icon = 'i';
        }
        const insightKey = i.id || i.message;
        return `
            <div class="insight-card" style="border-left-color:${borderColor}" data-insight-key="${insightKey.replace(/"/g, '&quot;')}">
                <div class="insight-icon" style="background:${borderColor}">${icon}</div>
                <div class="insight-message">${i.message}</div>
                <button class="insight-dismiss-btn" onclick="dismissInsight(this)" title="Dismiss">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
                </button>
            </div>
        `;
    }).join('');
}

function dismissInsight(btn) {
    const card = btn.closest('.insight-card');
    const key = card.dataset.insightKey;
    const dismissed = JSON.parse(localStorage.getItem('reef_dismissed_insights') || '[]');
    if (!dismissed.includes(key)) {
        dismissed.push(key);
        localStorage.setItem('reef_dismissed_insights', JSON.stringify(dismissed));
    }
    card.style.opacity = '0';
    card.style.transform = 'translateX(40px)';
    card.style.transition = 'opacity 0.3s, transform 0.3s';
    setTimeout(() => card.remove(), 300);
}

// ── Dashboard Due Today (unified) ──────────────────────────────────────

const DASH_CATEGORY_ICONS = {
    water_change: '\u{1F4A7}',
    testing: '\u{1F52C}',
    cleaning: '\u2728',
    dosing: '\u2697\uFE0F',
    feeding: '\u{1F41F}',
    maintenance: '\u{1F527}',
    other: '\u{1F4DD}',
};

function renderDashDueToday(tasks) {
    const container = document.getElementById('dash-due-list');
    const titleEl = document.getElementById('dash-due-title');

    if (!tasks || tasks.length === 0) {
        container.innerHTML = '<div class="empty-state" style="padding:8px 0">All caught up!</div>';
        titleEl.textContent = 'Due Today';
        return;
    }

    const overdueCount = tasks.filter(t => t.overdue).length;
    if (overdueCount > 0) {
        titleEl.innerHTML = `Due Today <span class="due-overdue-badge">${overdueCount} overdue</span>`;
    } else {
        titleEl.textContent = `Due Today (${tasks.length})`;
    }

    container.innerHTML = tasks.map(t => {
        const icon = DASH_CATEGORY_ICONS[t.category] || DASH_CATEGORY_ICONS.other;
        return `
            <div class="dash-due-card ${t.overdue ? 'overdue' : ''}">
                <div class="dash-due-left">
                    <span class="dash-due-icon">${icon}</span>
                    <div>
                        <div class="dash-due-title-text">${t.title}</div>
                        <div class="dash-due-freq">${t.frequency}${t.overdue ? ' &middot; Overdue' : ''}</div>
                    </div>
                </div>
                <button class="cal-task-done-btn" onclick="completeDashTask('${t.source}', ${t.id}, this)">Done</button>
            </div>
        `;
    }).join('');
}

async function completeDashTask(source, id, btn) {
    btn.disabled = true;
    btn.textContent = '\u2713';
    const card = btn.closest('.dash-due-card');
    if (card) card.classList.add('completing');
    try {
        await api('/tasks/complete', { method: 'PUT', body: { source, id } });
        if (card) card.classList.add('completed');
        showToast('Task completed!', 'success');
        setTimeout(() => loadDashboard(), 800);
    } catch (err) {
        showToast(err.message, 'error');
        btn.disabled = false;
        btn.textContent = 'Done';
        if (card) card.classList.remove('completing');
    }
}

// ── Setup Prompt ────────────────────────────────────────────────────────

function renderDashSetupPrompt(hasMaintenance) {
    const el = document.getElementById('dash-setup-prompt');
    if (hasMaintenance) {
        el.classList.add('hidden');
    } else {
        el.classList.remove('hidden');
    }
}

// ── Dashboard Upcoming ─────────────────────────────────────────────────

function renderDashUpcoming(tasks) {
    const container = document.getElementById('dash-upcoming-list');
    if (!tasks || tasks.length === 0) {
        container.innerHTML = '<div class="empty-state">No upcoming tasks</div>';
        return;
    }

    container.innerHTML = tasks.map(t => {
        const icon = DASH_CATEGORY_ICONS[t.category] || DASH_CATEGORY_ICONS.other;
        return `
            <div class="dash-due-card">
                <div class="dash-due-left">
                    <span class="dash-due-icon">${icon}</span>
                    <div>
                        <div class="dash-due-title-text">${t.title}</div>
                        <div class="dash-due-freq">${formatDate(t.next_due)} &middot; ${t.frequency}</div>
                    </div>
                </div>
                <button class="cal-task-done-btn" onclick="completeDashTask('${t.source}', ${t.id}, this)">Done</button>
            </div>
        `;
    }).join('');
}

// ── Dashboard Milestones ────────────────────────────────────────────────

function renderDashMilestones(milestones) {
    const container = document.getElementById('dash-milestones-list');
    if (!milestones || milestones.length === 0) {
        container.innerHTML = '<div class="empty-state">No active milestones</div>';
        return;
    }

    const active = milestones.filter(m => m.status === 'active');
    if (active.length === 0) {
        container.innerHTML = '<div class="empty-state">No active milestones</div>';
        return;
    }

    container.innerHTML = active.slice(0, 3).map(m => `
        <div class="milestone-card active">
            <div class="milestone-status-badge active">In Progress</div>
            <div class="milestone-title">${m.title}</div>
            ${m.description ? '<div class="milestone-desc">' + m.description + '</div>' : ''}
        </div>
    `).join('');
}

// ── Cost Summary ────────────────────────────────────────────────────────

function renderCostSummary(summary) {
    const amountEl = document.getElementById('cost-summary-amount');
    Promise.all([api('/recurring-costs'), api('/costs')]).then(([recurringData, costsData]) => {
        const recurringTotal = recurringData.recurring_total || 0;
        const costs = costsData.costs || [];
        const now = new Date();
        const thisMonthPurchases = costs.filter(c => {
            const d = new Date(c.purchase_date);
            return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
        });
        const purchaseTotal = thisMonthPurchases.reduce((sum, c) => sum + parseFloat(c.amount), 0);
        const grandTotal = recurringTotal + purchaseTotal;
        amountEl.textContent = '$' + grandTotal.toFixed(2);
    }).catch(() => {
        const total = (summary && summary.month_total !== undefined) ? summary.month_total : 0;
        amountEl.textContent = '$' + total.toFixed(2);
    });
}

// ── Helpers ─────────────────────────────────────────────────────────────

function formatDate(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// ── Recent Activity ────────────────────────────────────────────────────

async function renderRecentActivity() {
    const container = document.getElementById('dash-activity-list');
    const activities = [];

    try {
        // Gather recent completed tasks
        const tasksRes = await api('/tasks/history');
        const history = tasksRes.history || [];
        history.slice(0, 5).forEach(h => {
            activities.push({
                icon: DASH_CATEGORY_ICONS[h.category] || DASH_CATEGORY_ICONS.other,
                text: `Completed: ${h.title}`,
                time: h.completed_at || h.date,
                type: 'task'
            });
        });
    } catch {}

    try {
        // Gather recent purchases
        const costsRes = await api('/costs');
        const costs = costsRes.costs || [];
        costs.slice(0, 5).forEach(c => {
            activities.push({
                icon: '\uD83D\uDCB0',
                text: `${c.description} — $${parseFloat(c.amount).toFixed(2)}`,
                time: c.purchase_date,
                type: 'purchase'
            });
        });
    } catch {}

    try {
        // Gather recent param logs
        const paramsRes = await api('/params/history');
        const params = paramsRes.entries || paramsRes.history || [];
        params.slice(0, 5).forEach(p => {
            activities.push({
                icon: '\uD83E\uDDEA',
                text: `Logged ${p.type || p.param}: ${p.value}`,
                time: p.date || p.logged_at,
                type: 'param'
            });
        });
    } catch {}

    // Sort by most recent and take top 5
    activities.sort((a, b) => new Date(b.time) - new Date(a.time));
    const recent = activities.slice(0, 5);

    if (recent.length === 0) {
        container.innerHTML = '<div class="empty-state">No recent activity</div>';
        return;
    }

    container.innerHTML = recent.map(a => {
        const timeAgo = getTimeAgo(a.time);
        return `
            <div class="activity-item">
                <span class="activity-icon">${a.icon}</span>
                <div class="activity-info">
                    <div class="activity-text">${a.text}</div>
                    <div class="activity-time">${timeAgo}</div>
                </div>
            </div>
        `;
    }).join('');
}

function getTimeAgo(dateStr) {
    const now = new Date();
    const d = new Date(dateStr);
    const diff = Math.floor((now - d) / 1000);
    if (diff < 60) return 'Just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    if (diff < 604800) return Math.floor(diff / 86400) + 'd ago';
    return formatDate(dateStr);
}


// ── Dosing/Food Presets ───────────────────────────────────────────────────

async function loadRoutinePresets() {
    try {
        const data = await api('/dosing-presets');
        const section = document.getElementById('routine-section');
        const container = document.getElementById('routine-presets');
        if (!data.presets || data.presets.length === 0) {
            section.style.display = 'none';
            return;
        }
        section.style.display = 'block';
        container.innerHTML = data.presets.map(p => {
            const icon = p.preset_type === 'food' ? '🍽️' : p.preset_type === 'supplement' ? '💊' : '💧';
            const logged = p.logged_today;
            return `<button class="routine-btn ${logged ? 'logged' : ''}" onclick="togglePresetLog(${p.id}, ${logged})" data-id="${p.id}">
                <span class="routine-icon">${logged ? '✅' : icon}</span>
                <span class="routine-name">${p.name}</span>
                ${p.amount ? `<span class="routine-amount">${p.amount}</span>` : ''}
            </button>`;
        }).join('');
    } catch (e) {}
}

async function togglePresetLog(id, isLogged) {
    try {
        if (isLogged) {
            await api(`/dosing-presets/${id}/unlog`, { method: 'DELETE' });
        } else {
            await api(`/dosing-presets/${id}/log`, { method: 'POST' });
        }
        loadRoutinePresets();
    } catch (e) {
        showToast('Failed to log preset', 'error');
    }
}

function openPresetManager() {
    openModal('preset-modal');
    loadPresetList();
}

async function loadPresetList() {
    try {
        const data = await api('/dosing-presets');
        const list = document.getElementById('preset-list');
        if (!data.presets || data.presets.length === 0) {
            list.innerHTML = '<div style="text-align:center;color:var(--text-secondary);padding:20px;font-size:13px">No presets yet. Add one above!</div>';
            return;
        }
        list.innerHTML = data.presets.map(p => {
            const icon = p.preset_type === 'food' ? '🍽️' : p.preset_type === 'supplement' ? '💊' : '💧';
            return `<div style="display:flex;align-items:center;gap:12px;padding:12px;background:var(--bg-deep);border-radius:10px;margin-bottom:8px">
                <span style="font-size:20px">${icon}</span>
                <div style="flex:1">
                    <div style="font-size:14px;font-weight:600;color:var(--text-primary)">${p.name}</div>
                    <div style="font-size:11px;color:var(--text-secondary)">${p.preset_type} ${p.amount ? '· ' + p.amount : ''} · ${p.frequency}</div>
                </div>
                <button onclick="deletePreset(${p.id})" style="background:none;border:none;color:var(--danger);cursor:pointer;padding:6px">
                    <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>
                </button>
            </div>`;
        }).join('');
    } catch (e) {}
}

async function addPreset() {
    const name = document.getElementById('preset-name').value.trim();
    if (!name) { showToast('Enter a preset name', 'error'); return; }
    const presetType = document.getElementById('preset-type').value;
    const amount = document.getElementById('preset-amount').value.trim();
    try {
        await api('/dosing-presets', {
            method: 'POST',
            body: { name, preset_type: presetType, amount, frequency: 'daily' }
        });
        document.getElementById('preset-name').value = '';
        document.getElementById('preset-amount').value = '';
        showToast('Preset added!', 'success');
        loadPresetList();
        loadRoutinePresets();
    } catch (e) {
        showToast('Failed to add preset', 'error');
    }
}

async function deletePreset(id) {
    try {
        await api(`/dosing-presets/${id}`, { method: 'DELETE' });
        showToast('Preset removed', 'success');
        loadPresetList();
        loadRoutinePresets();
    } catch (e) {
        showToast('Failed to delete preset', 'error');
    }
}


// ── Daily Journal ─────────────────────────────────────────────────────────

async function loadJournal() {
    try {
        const data = await api('/journal');
        const input = document.getElementById('journal-input');
        const saveBtn = document.getElementById('journal-save-btn');
        const history = document.getElementById('journal-history');

        // Show today's note if exists
        const today = new Date().toISOString().split('T')[0];
        const todayEntry = (data.entries || []).find(e => e.log_date === today);
        if (todayEntry) {
            input.value = todayEntry.notes;
        }

        // Show save button on input
        input.addEventListener('input', () => {
            saveBtn.style.display = input.value.trim() ? 'block' : 'none';
        });

        // Render recent entries (exclude today)
        const past = (data.entries || []).filter(e => e.log_date !== today).slice(0, 5);
        if (past.length > 0) {
            history.innerHTML = past.map(e => {
                const d = new Date(e.log_date + 'T12:00:00');
                const dayName = d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
                return `<div style="padding:10px 12px;background:var(--card-solid);border-radius:10px;margin-bottom:6px;border-left:3px solid var(--accent)">
                    <div style="font-size:11px;color:var(--accent);font-weight:600;margin-bottom:4px">${dayName}</div>
                    <div style="font-size:13px;color:var(--text-primary);line-height:1.4">${e.notes}</div>
                </div>`;
            }).join('');
        } else {
            history.innerHTML = '';
        }
    } catch (e) {}
}

async function saveJournal() {
    const notes = document.getElementById('journal-input').value.trim();
    if (!notes) return;
    try {
        await api('/journal', { method: 'POST', body: { notes } });
        showToast('Note saved!', 'success');
        document.getElementById('journal-save-btn').style.display = 'none';
    } catch (e) {
        showToast('Failed to save note', 'error');
    }
}
