/* ReefPilot — Calculators (all client-side for offline use) */

function initCalcDefaults() {
    // Populate salt brand dropdown
    populateSaltDropdown('calc-salt-brand');

    // Pre-fill with user's settings
    if (currentUser) {
        if (currentUser.salt_brand) {
            const sel = document.getElementById('calc-salt-brand');
            if (sel) sel.value = currentUser.salt_brand;
        }
        if (currentUser.tank_size_gallons) {
            const vol = document.getElementById('calc-wc-volume');
            const doseVol = document.getElementById('calc-dose-volume');
            const totalVol = currentUser.tank_size_gallons + (currentUser.sump_size_gallons || 0);
            if (vol) vol.value = totalVol;
            if (doseVol) doseVol.value = totalVol;
        }
    }
}

// ── Salt Mix Calculator ──────────────────────────────────────────────────

function calcSaltMix() {
    const volumeGal = parseFloat(document.getElementById('calc-salt-volume').value);
    const targetSG = parseFloat(document.getElementById('calc-salt-sg').value);
    const brandKey = document.getElementById('calc-salt-brand').value;

    if (!volumeGal || volumeGal <= 0) {
        showToast('Enter a valid water volume', 'error');
        return;
    }

    const brand = saltBrands[brandKey];
    if (!brand) {
        showToast('Select a salt brand', 'error');
        return;
    }

    // Convert gallons to liters (1 gallon = 3.78541 liters)
    const volumeL = volumeGal * 3.78541;

    // Adjust for target SG (base data is for 1.026)
    const sgRatio = (targetSG - 1.0) / (1.026 - 1.0);
    const gramsPerLiter = brand.grams_per_liter * sgRatio;
    const totalGrams = gramsPerLiter * volumeL;

    // Convert to cups (roughly 280g per cup for most salts)
    const cups = totalGrams / 280;

    const resultEl = document.getElementById('salt-result');
    resultEl.classList.remove('hidden');
    resultEl.innerHTML = `
        <div class="calc-result-big">${Math.round(totalGrams)} grams</div>
        <div class="calc-result-detail">
            ~${cups.toFixed(1)} cups of ${brand.name}<br>
            for ${volumeGal} gallons at ${targetSG} SG<br>
            (${gramsPerLiter.toFixed(1)} g/L)
        </div>
    `;
}

// ── Water Change Calculator ──────────────────────────────────────────────

function calcWaterChange() {
    const totalVol = parseFloat(document.getElementById('calc-wc-volume').value);
    const percent = parseFloat(document.getElementById('calc-wc-percent').value);

    if (!totalVol || totalVol <= 0) {
        showToast('Enter your system volume', 'error');
        return;
    }
    if (!percent || percent <= 0 || percent > 100) {
        showToast('Enter a valid percentage (1-100)', 'error');
        return;
    }

    const changeVol = totalVol * (percent / 100);
    const liters = changeVol * 3.78541;

    const resultEl = document.getElementById('wc-result');
    resultEl.classList.remove('hidden');
    resultEl.innerHTML = `
        <div class="calc-result-big">${changeVol.toFixed(1)} gallons</div>
        <div class="calc-result-detail">
            ${liters.toFixed(1)} liters<br>
            ${percent}% of ${totalVol} gallon system
        </div>
    `;
}

// ── 2-Part Dosing Calculator ─────────────────────────────────────────────

function calcDosing() {
    const volume = parseFloat(document.getElementById('calc-dose-volume').value);
    const currentAlk = parseFloat(document.getElementById('calc-dose-current-alk').value);
    const targetAlk = parseFloat(document.getElementById('calc-dose-target-alk').value);

    if (!volume || volume <= 0) {
        showToast('Enter your system volume', 'error');
        return;
    }
    if (isNaN(currentAlk) || isNaN(targetAlk)) {
        showToast('Enter current and target alkalinity', 'error');
        return;
    }

    const alkDiff = targetAlk - currentAlk;

    // BRS 2-part: ~1ml per gallon per 1 dKH (soda ash solution at standard concentration)
    const alkDoseML = alkDiff * volume * 1.0;

    // Corresponding calcium dose (to maintain balance):
    // For every 1 dKH raised, Ca consumption is roughly 20ppm
    // 1ml of calcium chloride solution per gallon raises Ca by ~20ppm
    const caDoseML = Math.abs(alkDiff) * volume * 1.0;

    const resultEl = document.getElementById('dose-result');
    resultEl.classList.remove('hidden');

    if (alkDiff <= 0) {
        resultEl.innerHTML = `
            <div class="calc-result-big">No dosing needed</div>
            <div class="calc-result-detail">
                Your alkalinity (${currentAlk} dKH) is already at or above target (${targetAlk} dKH).
            </div>
        `;
        return;
    }

    resultEl.innerHTML = `
        <div class="calc-result-big">${alkDoseML.toFixed(0)} ml Alk</div>
        <div class="calc-result-detail">
            Soda Ash (Alk Part): ${alkDoseML.toFixed(1)} ml<br>
            Calcium Chloride (Ca Part): ${caDoseML.toFixed(1)} ml<br>
            <br>
            Raises Alk by ${alkDiff.toFixed(1)} dKH in ${volume} gallons<br>
            <small>Based on BRS standard 2-part concentration. Dose slowly over 24h. Do not dose both parts at the same time.</small>
        </div>
    `;
}
