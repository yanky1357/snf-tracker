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
        list.innerHTML = '<div class="empty-state">No livestock added yet</div>';
        return;
    }

    const categoryIcons = {
        fish: 'F',
        coral: 'C',
        invertebrate: 'I',
        anemone: 'A',
    };

    list.innerHTML = livestock.map(l => `
        <div class="item-card">
            <div class="item-info">
                <div class="item-name">
                    ${l.nickname || l.common_name || l.species || 'Unknown'}
                    ${l.quantity > 1 ? ' x' + l.quantity : ''}
                </div>
                <div class="item-detail">
                    ${l.category} ${l.species ? '- ' + l.species : ''}
                </div>
            </div>
            <button class="item-delete" onclick="deleteLivestock(${l.id})">&times;</button>
        </div>
    `).join('');
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
            },
        });
        closeModal('add-livestock-modal');
        showToast('Livestock added', 'success');
        loadTankData();
        // Reset form
        document.getElementById('ls-common-name').value = '';
        document.getElementById('ls-species').value = '';
        document.getElementById('ls-nickname').value = '';
        document.getElementById('ls-quantity').value = '1';
    } catch (err) {
        showToast(err.message, 'error');
    }
    return false;
}

async function deleteLivestock(id) {
    try {
        await api('/livestock/' + id, { method: 'DELETE' });
        showToast('Removed', 'success');
        loadTankData();
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
