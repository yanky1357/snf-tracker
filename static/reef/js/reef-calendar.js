/* ReefPilot — Tasks: unified priority-ordered action list */

let tasksHasMaintenance = false;

const CAL_CATEGORY_ICONS = {
    water_change: '\u{1F4A7}',
    testing: '\u{1F52C}',
    cleaning: '\u2728',
    dosing: '\u2697\uFE0F',
    feeding: '\u{1F41F}',
    maintenance: '\u{1F527}',
    other: '\u{1F4DD}',
};

// ── Tasks Tab Entry ─────────────────────────────────────────────────────

async function loadTasksTab() {
    try {
        const status = await api('/maintenance/status');
        tasksHasMaintenance = status.has_tasks;
    } catch (err) { tasksHasMaintenance = false; }

    const setupEl = document.getElementById('tasks-setup');
    const mainEl = document.getElementById('tasks-main');

    if (!tasksHasMaintenance) {
        setupEl.classList.remove('hidden');
        mainEl.classList.add('hidden');
    } else {
        setupEl.classList.add('hidden');
        mainEl.classList.remove('hidden');
        await loadTasksList();
    }
}

// ── Single Unified Task List ──────────────────────────────────────────

async function loadTasksList() {
    const container = document.getElementById('tasks-list');
    try {
        const data = await api('/tasks/upcoming?days=7');
        const { overdue, today, upcoming } = data;

        if (overdue.length === 0 && today.length === 0 && upcoming.length === 0) {
            container.innerHTML = '<div class="empty-state" style="padding:40px 0;text-align:center">Nothing on the horizon. Enjoy the reef.</div>';
            return;
        }

        let html = '';

        // Overdue group
        if (overdue.length > 0) {
            html += `<div class="task-group-header overdue">Overdue (${overdue.length})</div>`;
            html += overdue.map(t => renderTaskCard(t, true, false)).join('');
        }

        // Today group
        if (today.length > 0) {
            html += `<div class="task-group-header today">Today (${today.length})</div>`;
            html += today.map(t => renderTaskCard(t, false, false)).join('');
        }

        // Upcoming group
        if (upcoming.length > 0) {
            html += '<div class="task-group-header upcoming">Coming Up</div>';
            let lastLabel = '';
            for (const t of upcoming) {
                if (t.due_label !== lastLabel) {
                    html += `<div class="task-day-label">${t.due_label}</div>`;
                    lastLabel = t.due_label;
                }
                html += renderTaskCard(t, false, true);
            }
        }

        container.innerHTML = html;
    } catch (err) {
        console.error('Tasks load error:', err);
        container.innerHTML = '<div class="empty-state">Could not load tasks</div>';
    }
}

function renderTaskCard(t, isOverdue, isUpcoming) {
    const icon = CAL_CATEGORY_ICONS[t.category] || CAL_CATEGORY_ICONS.other;
    const overdueClass = isOverdue ? ' overdue' : '';
    const upcomingClass = isUpcoming ? ' upcoming-task' : '';
    const subtext = isOverdue
        ? `${t.days_overdue} day${t.days_overdue > 1 ? 's' : ''} overdue`
        : '';

    const doneBtn = `<button class="cal-task-done-btn" onclick="completeUnifiedTask('${t.source}', ${t.id})">Done</button>`;

    return `
        <div class="cal-task-card${overdueClass}${upcomingClass}" id="task-${t.source}-${t.id}">
            <div class="cal-task-left">
                <span class="cal-task-icon">${icon}</span>
                <div class="cal-task-info">
                    <span class="cal-task-title">${t.title}</span>
                    ${subtext ? `<span class="cal-task-freq">${subtext}</span>` : ''}
                </div>
            </div>
            <div class="cal-task-right">
                <span class="task-freq-pill">${t.frequency}</span>
                ${doneBtn}
            </div>
        </div>
    `;
}

// ── Unified Task Actions ───────────────────────────────────────────────

async function completeUnifiedTask(source, id) {
    const card = document.getElementById('task-' + source + '-' + id);
    if (card) {
        card.classList.add('completing');
        const btn = card.querySelector('.cal-task-done-btn');
        if (btn) { btn.disabled = true; btn.textContent = '\u2713 Done'; }
        const pill = card.querySelector('.task-freq-pill');
        if (pill) { pill.textContent = 'Completed'; pill.classList.add('completed-pill'); }
    }

    try {
        const result = await api('/tasks/complete', { method: 'PUT', body: { source, id } });
        if (result.deleted) {
            showToast('Task completed!', 'success');
        } else {
            const nd = new Date(result.next_due + 'T00:00:00');
            const label = nd.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
            showToast(`Done! Next up ${label}`, 'success');
        }
        // Hold the strikethrough + green check so user clearly sees it worked
        await new Promise(r => setTimeout(r, 1200));
        if (card) card.classList.add('completed');
        await new Promise(r => setTimeout(r, 500));
        await loadTasksList();
    } catch (err) {
        showToast(err.message, 'error');
        if (card) {
            card.classList.remove('completing');
            const btn = card.querySelector('.cal-task-done-btn');
            if (btn) { btn.disabled = false; btn.textContent = 'Done'; }
        }
    }
}

async function deleteUnifiedTask(source, id) {
    try {
        await api('/tasks/delete', { method: 'DELETE', body: { source, id } });
        showToast('Task removed', 'success');
        loadTasksList();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// Keep old completeCalTask working for dashboard
async function completeCalTask(id) {
    await completeUnifiedTask('calendar', id);
}

// ── Add Task ───────────────────────────────────────────────────────────

function calAddTask() {
    const dateInput = document.getElementById('cal-task-date');
    dateInput.value = new Date().toISOString().split('T')[0];
    document.getElementById('cal-add-task-modal').classList.remove('hidden');
}

async function handleCalAddTask(e) {
    e.preventDefault();
    const title = document.getElementById('cal-task-name').value.trim();
    const next_due = document.getElementById('cal-task-date').value;
    const frequency = document.getElementById('cal-task-freq').value;

    if (!title) return false;

    // Auto-detect source: one-time → calendar, recurring → maintenance
    const source = (frequency === 'once') ? 'calendar' : 'maintenance';

    try {
        if (source === 'maintenance') {
            await api('/maintenance', {
                method: 'POST',
                body: { task_name: title, frequency, next_due },
            });
        } else {
            await api('/calendar/task', {
                method: 'POST',
                body: { title, next_due, frequency },
            });
        }
        closeModal('cal-add-task-modal');
        document.getElementById('cal-task-name').value = '';
        showToast('Task added', 'success');
        loadTasksList();
    } catch (err) {
        showToast(err.message, 'error');
    }
    return false;
}

// ── Setup Flow ─────────────────────────────────────────────────────────

function toggleSetupChip(el) {
    el.classList.toggle('selected');
}

function showCustomTaskSetup() {
    document.getElementById('setup-custom-form').classList.toggle('hidden');
}

function addCustomSetupChip() {
    const name = document.getElementById('setup-custom-name').value.trim();
    const freq = document.getElementById('setup-custom-freq').value;
    if (!name) return;

    const container = document.getElementById('setup-chips');
    const btn = document.createElement('button');
    btn.className = 'setup-chip selected';
    btn.dataset.task = name;
    btn.dataset.freq = freq;
    btn.textContent = name;
    btn.onclick = function() { toggleSetupChip(this); };
    container.appendChild(btn);

    document.getElementById('setup-custom-name').value = '';
    document.getElementById('setup-custom-form').classList.add('hidden');
}

async function saveSetupTasks() {
    const chips = document.querySelectorAll('.setup-chip.selected');
    if (chips.length === 0) {
        showToast('Pick at least one task', 'error');
        return;
    }

    const btn = document.getElementById('btn-save-setup');
    btn.disabled = true;
    btn.textContent = 'Setting up...';

    try {
        const tasks = Array.from(chips).map(chip => ({
            task_name: chip.dataset.task,
            frequency: chip.dataset.freq,
        }));
        await api('/maintenance/setup', {
            method: 'POST',
            body: { tasks },
        });
        showToast('Schedule created!', 'success');
        await loadTasksTab();
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Create My Schedule';
    }
}

function showTasksSetup() {
    document.getElementById('tasks-setup').classList.remove('hidden');
    document.getElementById('tasks-main').classList.add('hidden');
}

async function generateAIMaintenance() {
    const btn = document.getElementById('btn-gen-maint');
    btn.disabled = true;
    btn.textContent = 'Generating...';
    try {
        await api('/maintenance/generate', { method: 'POST' });
        showToast('AI maintenance plan generated!', 'success');
        await loadTasksTab();
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'AI Auto-Plan';
    }
}
