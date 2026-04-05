/* ReefPilot — More tab: Costs, Maintenance, Milestones, Settings */

// ── More Section Router ─────────────────────────────────────────────────

function openMoreSection(section) {
    switch (section) {
        case 'calculators':
            switchTab('calc');
            break;
        case 'costs':
            switchTab('costs');
            break;
        case 'maintenance':
            openMaintenance();
            break;
        case 'milestones':
            openMilestones();
            break;
        case 'settings':
            document.getElementById('settings-modal').classList.remove('hidden');
            break;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// COST TRACKER
// ═══════════════════════════════════════════════════════════════════════════

async function openCostTracker() {
    document.getElementById('cost-tracker-modal').classList.remove('hidden');
    document.getElementById('cost-add-form-wrap').classList.add('hidden');
    // Set default date to today
    document.getElementById('cost-date').value = new Date().toISOString().split('T')[0];
    await loadCosts();
    await loadCostSummary();
}

function showAddExpense() {
    const wrap = document.getElementById('cost-add-form-wrap');
    wrap.classList.toggle('hidden');
}

async function loadCosts() {
    const list = document.getElementById('cost-list');
    try {
        const data = await api('/costs');
        const costs = data.costs || [];
        if (costs.length === 0) {
            list.innerHTML = '<div class="empty-state">No expenses recorded</div>';
            return;
        }
        list.innerHTML = costs.map(c => `
            <div class="item-card">
                <div class="item-info">
                    <div class="item-name">$${parseFloat(c.amount).toFixed(2)} - ${c.category}</div>
                    <div class="item-detail">${c.description || ''} &middot; ${formatDateShort(c.purchase_date)}</div>
                </div>
                <button class="item-delete" onclick="deleteCost(${c.id})">&times;</button>
            </div>
        `).join('');
    } catch {
        list.innerHTML = '<div class="empty-state">Could not load expenses</div>';
    }
}

async function loadCostSummary() {
    const container = document.getElementById('cost-summary-breakdown');
    try {
        const data = await api('/costs/summary');
        const summary = data.summary || {};
        const categories = summary.categories || {};
        const total = summary.month_total || 0;

        let html = `<div class="cost-breakdown-header">Monthly Total: <strong>$${total.toFixed(2)}</strong></div>`;
        const catKeys = Object.keys(categories);
        if (catKeys.length > 0) {
            html += '<div class="cost-breakdown-cats">';
            catKeys.forEach(cat => {
                html += `<div class="cost-cat-row"><span>${cat}</span><span>$${categories[cat].toFixed(2)}</span></div>`;
            });
            html += '</div>';
        }
        container.innerHTML = html;
    } catch {
        container.innerHTML = '';
    }
}

async function handleAddCost(e) {
    e.preventDefault();
    try {
        await api('/costs', {
            method: 'POST',
            body: {
                category: document.getElementById('cost-category').value,
                description: document.getElementById('cost-description').value,
                amount: parseFloat(document.getElementById('cost-amount').value),
                purchase_date: document.getElementById('cost-date').value,
            },
        });
        showToast('Expense added', 'success');
        document.getElementById('cost-description').value = '';
        document.getElementById('cost-amount').value = '';
        document.getElementById('cost-add-form-wrap').classList.add('hidden');
        await loadCosts();
        await loadCostSummary();
    } catch (err) {
        showToast(err.message, 'error');
    }
    return false;
}

async function deleteCost(id) {
    try {
        await api('/costs/' + id, { method: 'DELETE' });
        showToast('Expense removed', 'success');
        await loadCosts();
        await loadCostSummary();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// MAINTENANCE (now in Tasks tab — keeping markMaintenanceDone for compat)
// ═══════════════════════════════════════════════════════════════════════════

function openMaintenance() {
    // Redirect to Tasks tab instead of modal
    switchTab('tasks');
}

async function markMaintenanceDone(id) {
    try {
        await api('/maintenance/' + id + '/done', { method: 'PUT' });
        showToast('Task completed', 'success');
        if (!document.getElementById('tab-home').classList.contains('hidden')) {
            loadDashboard();
        }
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// MILESTONES
// ═══════════════════════════════════════════════════════════════════════════

async function openMilestones() {
    document.getElementById('milestones-modal').classList.remove('hidden');
    await loadMilestonesFull();
}

async function loadMilestonesFull() {
    const list = document.getElementById('milestones-full-list');
    try {
        const data = await api('/milestones');
        const milestones = data.milestones || [];
        if (milestones.length === 0) {
            list.innerHTML = '<div class="empty-state">No milestones yet</div>';
            return;
        }
        list.innerHTML = milestones.map(m => {
            let badgeClass, badgeText;
            switch (m.status) {
                case 'completed':
                    badgeClass = 'completed';
                    badgeText = '\u2713 Completed';
                    break;
                case 'active':
                    badgeClass = 'active';
                    badgeText = 'In Progress';
                    break;
                default:
                    badgeClass = 'locked';
                    badgeText = 'Locked';
            }
            const completeBtn = m.status === 'active'
                ? `<button class="btn btn-small btn-primary" onclick="completeMilestone(${m.id})" style="margin-top:8px">Mark Complete</button>`
                : '';
            return `
                <div class="milestone-card ${m.status}">
                    <div class="milestone-status-badge ${badgeClass}">${badgeText}</div>
                    <div class="milestone-title">${m.title}</div>
                    ${m.description ? '<div class="milestone-desc">' + m.description + '</div>' : ''}
                    ${completeBtn}
                </div>
            `;
        }).join('');
    } catch {
        list.innerHTML = '<div class="empty-state">Could not load milestones</div>';
    }
}

async function completeMilestone(id) {
    try {
        await api('/milestones/' + id + '/complete', { method: 'PUT' });
        showToast('Milestone completed!', 'success');
        await loadMilestonesFull();
        if (!document.getElementById('tab-home').classList.contains('hidden')) {
            loadDashboard();
        }
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ── Helpers ─────────────────────────────────────────────────────────────

function formatDateShort(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}
