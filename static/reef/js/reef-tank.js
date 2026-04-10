/* ReefPilot — Tank profile, livestock, equipment management */

let tankData = null;

async function loadTankData() {
    try {
        const data = await api('/tank');
        tankData = data;
        renderTankProfile(data.profile, data.salt_brands, data.tank_types);
        renderLivestock(data.livestock);
        renderEquipment(data.equipment);
    } catch (err) {
        const card = document.getElementById('tank-profile-card');
        if (card) card.innerHTML = '<div class="empty-state">Could not load tank data.</div>';
    }
}

function renderTankProfile(profile, brands, types) {
    const card = document.getElementById('tank-profile-card');
    if (!profile) {
        card.innerHTML = '<div class="empty-state">Set up your tank profile</div>';
        return;
    }

    const typeName = (types && profile.tank_type) ? types[profile.tank_type] || profile.tank_type : 'Not set';
    const saltName = (brands && profile.salt_brand && brands[profile.salt_brand])
        ? brands[profile.salt_brand].name
        : profile.salt_brand || 'Not set';

    card.innerHTML = `
        <div class="tank-stat">
            <span class="tank-stat-label">Display Name</span>
            <span class="tank-stat-value">${profile.display_name || 'Not set'}</span>
        </div>
        <div class="tank-stat">
            <span class="tank-stat-label">Tank Size</span>
            <span class="tank-stat-value">${profile.tank_size_gallons ? profile.tank_size_gallons + ' gal' : 'Not set'}</span>
        </div>
        <div class="tank-stat">
            <span class="tank-stat-label">Tank Type</span>
            <span class="tank-stat-value">${typeName}</span>
        </div>
        <div class="tank-stat">
            <span class="tank-stat-label">Salt Brand</span>
            <span class="tank-stat-value">${saltName}</span>
        </div>
        <div class="tank-stat">
            <span class="tank-stat-label">Sump Size</span>
            <span class="tank-stat-value">${profile.sump_size_gallons ? profile.sump_size_gallons + ' gal' : 'None'}</span>
        </div>
    `;
}

function renderLivestock(livestock) {
    const list = document.getElementById('livestock-list');
    if (!livestock || livestock.length === 0) {
        list.innerHTML = '<div class="empty-state">No livestock added yet. Add your fish, corals, and inverts!</div>';
        return;
    }

    const categoryEmoji = { fish: '🐟', coral: '🪸', invertebrate: '🦐', anemone: '🌊' };

    list.innerHTML = livestock.map(l => {
        const name = l.nickname || l.common_name || l.species || 'Unknown';
        const emoji = categoryEmoji[l.category] || '🐠';
        const daysText = l.days_owned !== null && l.days_owned !== undefined
            ? (l.days_owned === 0 ? 'Added today' : l.days_owned === 1 ? '1 day' : l.days_owned < 30 ? l.days_owned + ' days' : Math.floor(l.days_owned / 30) + ' months')
            : '';
        const photoHtml = l.photo_url
            ? `<div class="ls-photo" style="background-image:url('${l.photo_url}')" onclick="event.stopPropagation()"></div>`
            : `<div class="ls-photo-placeholder" onclick="event.stopPropagation();uploadLivestockPhoto(${l.id})">
                <span style="font-size:20px">${emoji}</span>
                <span style="font-size:9px;color:var(--text-secondary)">+ photo</span>
               </div>`;
        return `<div class="ls-card">
            ${photoHtml}
            <div class="ls-info">
                <div class="ls-name">${name}${l.quantity > 1 ? ' <span style="color:var(--accent)">x' + l.quantity + '</span>' : ''}</div>
                <div class="ls-species">${l.category}${l.species ? ' · ' + l.species : ''}</div>
                ${daysText ? `<div class="ls-age" onclick="event.stopPropagation();editLivestockDate(${l.id}, '${l.added_date || ''}')" style="cursor:pointer">${daysText} ✏️</div>` : ''}
            </div>
            <div class="ls-actions">
                ${!l.photo_url ? '' : `<button class="ls-photo-btn" onclick="event.stopPropagation();uploadLivestockPhoto(${l.id})" title="Change photo">📷</button>`}
                <button class="item-delete" onclick="event.stopPropagation();deleteLivestock(${l.id})">&times;</button>
            </div>
        </div>`;
    }).join('');
}

function uploadLivestockPhoto(id) {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.onchange = async () => {
        const file = input.files[0];
        if (!file) return;
        try {
            showToast('Uploading...');
            const compressed = await compressImage(file, 800, 0.75);
            const formData = new FormData();
            formData.append('photo', compressed, 'livestock.jpg');
            const resp = await fetch('/reef/api/livestock/' + id + '/photo', {
                method: 'POST',
                body: formData,
                credentials: 'same-origin',
            });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.error || 'Upload failed');
            }
            showToast('Photo uploaded!', 'success');
            loadTankData();
            loadHomeLivestock();
        } catch (err) {
            showToast(err.message || 'Failed to upload photo', 'error');
        }
    };
    input.click();
}

function editLivestockDate(id, currentDate) {
    const input = document.createElement('input');
    input.type = 'date';
    input.value = currentDate || '';
    input.style.position = 'fixed';
    input.style.opacity = '0';
    input.style.top = '0';
    document.body.appendChild(input);
    input.addEventListener('change', async () => {
        if (input.value) {
            try {
                await api('/livestock/' + id, {
                    method: 'PUT',
                    body: { added_date: input.value }
                });
                showToast('Date updated!', 'success');
                loadTankData();
                if (typeof loadHomeLivestock === 'function') loadHomeLivestock();
            } catch (err) {
                showToast('Failed to update date', 'error');
            }
        }
        document.body.removeChild(input);
    });
    input.addEventListener('blur', () => {
        setTimeout(() => {
            if (document.body.contains(input)) document.body.removeChild(input);
        }, 300);
    });
    input.focus();
    input.click();
}

function renderEquipment(equipment) {
    const list = document.getElementById('equipment-list');
    if (!equipment || equipment.length === 0) {
        list.innerHTML = '<div class="empty-state">No equipment added yet</div>';
        return;
    }

    list.innerHTML = equipment.map(e => `
        <div class="item-card">
            <div class="item-info">
                <div class="item-name">${e.brand} ${e.model}</div>
                <div class="item-detail">${e.category}</div>
            </div>
            <button class="item-delete" onclick="deleteEquipment(${e.id})">&times;</button>
        </div>
    `).join('');
}

// ── CRUD ─────────────────────────────────────────────────────────────────

function showAddLivestock() {
    document.getElementById('add-livestock-modal').classList.remove('hidden');
}

async function handleAddLivestock(e) {
    e.preventDefault();
    try {
        await api('/livestock', {
            method: 'POST',
            body: {
                category: document.getElementById('ls-category').value,
                common_name: document.getElementById('ls-common-name').value,
                species: document.getElementById('ls-species').value,
                nickname: document.getElementById('ls-nickname').value,
                quantity: parseInt(document.getElementById('ls-quantity').value) || 1,
                added_date: document.getElementById('ls-date-added').value || new Date().toISOString().split('T')[0],
            },
        });
        closeModal('add-livestock-modal');
        showToast('Livestock added', 'success');
        loadTankData();
        if (typeof loadHomeLivestock === 'function') loadHomeLivestock();
        // Reset form
        document.getElementById('ls-common-name').value = '';
        document.getElementById('ls-species').value = '';
        document.getElementById('ls-nickname').value = '';
        document.getElementById('ls-quantity').value = '1';
        document.getElementById('ls-date-added').value = '';
    } catch (err) {
        showToast(err.message, 'error');
    }
    return false;
}

async function deleteLivestock(id) {
    if (!confirm('Are you sure you want to remove this livestock?')) return;
    try {
        await api('/livestock/' + id, { method: 'DELETE' });
        showToast('Removed', 'success');
        loadTankData();
        if (typeof loadHomeLivestock === 'function') loadHomeLivestock();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function showAddEquipment() {
    document.getElementById('add-equipment-modal').classList.remove('hidden');
}

async function handleAddEquipment(e) {
    e.preventDefault();
    try {
        await api('/equipment', {
            method: 'POST',
            body: {
                category: document.getElementById('eq-category').value,
                brand: document.getElementById('eq-brand').value,
                model: document.getElementById('eq-model').value,
            },
        });
        closeModal('add-equipment-modal');
        showToast('Equipment added', 'success');
        loadTankData();
        // Reset form
        document.getElementById('eq-brand').value = '';
        document.getElementById('eq-model').value = '';
    } catch (err) {
        showToast(err.message, 'error');
    }
    return false;
}

async function deleteEquipment(id) {
    try {
        await api('/equipment/' + id, { method: 'DELETE' });
        showToast('Removed', 'success');
        loadTankData();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ── Tank Edit ────────────────────────────────────────────────────────────

function showTankEdit() {
    const profile = tankData ? tankData.profile : {};
    document.getElementById('edit-display-name').value = profile.display_name || '';
    document.getElementById('edit-tank-size').value = profile.tank_size_gallons || '';
    document.getElementById('edit-tank-type').value = profile.tank_type || 'mixed_reef';
    document.getElementById('edit-sump-size').value = profile.sump_size_gallons || '';

    // Populate and set salt brand
    populateSaltDropdown('edit-salt-brand');
    document.getElementById('edit-salt-brand').value = profile.salt_brand || '';

    document.getElementById('tank-edit-modal').classList.remove('hidden');
}

async function handleTankEdit(e) {
    e.preventDefault();
    try {
        await api('/tank', {
            method: 'PUT',
            body: {
                display_name: document.getElementById('edit-display-name').value,
                tank_size_gallons: parseFloat(document.getElementById('edit-tank-size').value) || null,
                tank_type: document.getElementById('edit-tank-type').value,
                salt_brand: document.getElementById('edit-salt-brand').value || null,
                sump_size_gallons: parseFloat(document.getElementById('edit-sump-size').value) || null,
            },
        });
        closeModal('tank-edit-modal');
        showToast('Tank profile updated', 'success');
        // Refresh user data for other features
        currentUser = await api('/auth/me');
        loadTankData();
    } catch (err) {
        showToast(err.message, 'error');
    }
    return false;
}
