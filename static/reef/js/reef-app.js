/* ReefPilot — Main app: auth, routing, API helpers, navigation */

// ── Dismiss keyboard on tap outside input fields ──────────────────────
document.addEventListener('touchstart', function(e) {
    const active = document.activeElement;
    if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || active.tagName === 'SELECT')) {
        if (!e.target.closest('input, textarea, select, button, a, .wizard-preset-btn, .wizard-card, .wizard-pill, .wizard-day-btn, .cw-preset, .cw-card, .nav-tab')) {
            active.blur();
        }
    }
});

let currentUser = null;
window.currentUserProfile = null;
let saltBrands = {};

// ── API Helper ──────────────────────────────────────────────────────────

async function api(path, opts = {}) {
    const url = '/reef/api' + path;
    const config = {
        headers: { 'Content-Type': 'application/json' },
        ...opts,
    };
    if (opts.body && typeof opts.body === 'object') {
        config.body = JSON.stringify(opts.body);
    }
    const res = await fetch(url, config);
    let data;
    try {
        data = await res.json();
    } catch {
        throw new Error('Connection error — please try again');
    }
    if (!res.ok) throw new Error(data.error || 'Request failed');
    return data;
}

// ── Client-side image compression ───────────────────────────────────────

function compressImage(file, maxDim = 1200, quality = 0.7) {
    return new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = (e) => {
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                let w = img.width, h = img.height;
                if (w > maxDim || h > maxDim) {
                    const ratio = Math.min(maxDim / w, maxDim / h);
                    w = Math.round(w * ratio);
                    h = Math.round(h * ratio);
                }
                canvas.width = w;
                canvas.height = h;
                canvas.getContext('2d').drawImage(img, 0, 0, w, h);
                canvas.toBlob((blob) => resolve(blob), 'image/jpeg', quality);
            };
            img.src = e.target.result;
        };
        reader.readAsDataURL(file);
    });
}

// ── User Preferences (units/currency) ───────────────────────────────────

var userPrefs = { units_volume: 'gallons', currency: 'USD' };

function loadPreferences() {
    if (window.currentUserProfile) {
        userPrefs.units_volume = window.currentUserProfile.units_volume || 'gallons';
        userPrefs.currency = window.currentUserProfile.currency || 'USD';
    }
    var volEl = document.getElementById('pref-volume');
    var curEl = document.getElementById('pref-currency');
    if (volEl) volEl.value = userPrefs.units_volume;
    if (curEl) curEl.value = userPrefs.currency;
}

async function savePreferences() {
    var vol = document.getElementById('pref-volume').value;
    var cur = document.getElementById('pref-currency').value;
    userPrefs.units_volume = vol;
    userPrefs.currency = cur;
    try {
        await api('/preferences', { method: 'PUT', body: { units_volume: vol, currency: cur } });
        showToast('Preferences saved', 'success');
        // Refresh displays
        if (typeof loadDashboard === 'function') loadDashboard();
        if (typeof loadTankData === 'function') loadTankData();
    } catch (e) {}
}

function formatVolume(gallons) {
    if (!gallons && gallons !== 0) return '—';
    if (userPrefs.units_volume === 'litres') {
        return Math.round(gallons * 3.785) + 'L';
    }
    return gallons + 'g';
}

function currencySymbol() {
    return { USD: '$', GBP: '£', EUR: '€' }[userPrefs.currency] || '$';
}

function formatCurrency(amount) {
    return currencySymbol() + (parseFloat(amount) || 0).toFixed(2);
}

// ── Toast ────────────────────────────────────────────────────────────────

function showToast(message, type = '') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast ' + type;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// ── Auth ─────────────────────────────────────────────────────────────────

function showLogin() {
    document.getElementById('login-form').classList.remove('hidden');
    document.getElementById('register-form').classList.add('hidden');
}

function showRegister() {
    document.getElementById('login-form').classList.add('hidden');
    document.getElementById('register-form').classList.remove('hidden');
}

async function handleLogin(e) {
    e.preventDefault();
    const errEl = document.getElementById('login-error');
    errEl.textContent = '';
    try {
        const data = await api('/auth/login', {
            method: 'POST',
            body: {
                email: document.getElementById('login-email').value,
                password: document.getElementById('login-password').value,
            },
        });
        currentUser = data;
        enterApp();
    } catch (err) {
        errEl.textContent = err.message;
    }
    return false;
}

async function handleRegister(e) {
    e.preventDefault();
    const errEl = document.getElementById('register-error');
    errEl.textContent = '';

    const password = document.getElementById('reg-password').value;
    if (password.length < 8 || !/[A-Z]/.test(password) || !/[a-z]/.test(password) || !/[0-9]/.test(password)) {
        errEl.textContent = 'Password needs 8+ characters with uppercase, lowercase, and a number';
        return false;
    }

    const consent = document.getElementById('reg-consent');
    if (consent && !consent.checked) {
        errEl.textContent = 'Please agree to the Terms and Privacy Policy';
        return false;
    }

    const email = document.getElementById('reg-email').value.trim().toLowerCase();

    try {
        const data = await api('/auth/register', {
            method: 'POST',
            body: {
                display_name: document.getElementById('reg-name').value,
                email: email,
                password: password,
            },
        });

        if (data.needs_verification) {
            showVerifyForm(email);
            showToast('Check your email for a verification code', 'success');
            return false;
        }

        currentUser = data;
        enterApp();
    } catch (err) {
        errEl.textContent = err.message;
    }
    return false;
}

async function handleLogout() {
    await api('/auth/logout', { method: 'POST' });
    currentUser = null;
    document.getElementById('auth-screen').classList.remove('hidden');
    document.getElementById('app-screen').classList.add('hidden');
    document.getElementById('onboarding-screen').classList.add('hidden');
    closeModal('settings-modal');
}

// ── App Entry ────────────────────────────────────────────────────────────

function enterApp() {
    document.getElementById('loading-splash').classList.add('hidden');
    document.getElementById('auth-screen').classList.add('hidden');

    if (!currentUser.onboarded) {
        showOnboarding();
        return;
    }

    document.getElementById('onboarding-screen').classList.add('hidden');
    document.getElementById('app-screen').classList.remove('hidden');
    document.getElementById('header-user').textContent = currentUser.display_name || '';
    document.getElementById('settings-email').textContent = currentUser.email || '';
    window.currentUserProfile = currentUser;
    loadPreferences();

    // Load initial data
    loadChatHistory();
    loadParamStatus();
    loadTankData();
    initCalcDefaults();

    // Route to correct tab — default to home
    const hash = location.hash.replace('#', '') || 'home';
    switchTab(hash);
}

// ── Tab Navigation ───────────────────────────────────────────────────────

function switchTab(tab) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('.nav-tab').forEach(el => el.classList.remove('active'));

    const tabEl = document.getElementById('tab-' + tab);
    const navEl = document.querySelector(`.nav-tab[data-tab="${tab}"]`);
    if (tabEl) tabEl.classList.remove('hidden');
    if (navEl) navEl.classList.add('active');

    location.hash = tab;

    // Refresh data when switching tabs
    if (tab === 'home') loadDashboard();
    if (tab === 'costs') loadCostDashboard();
    if (tab === 'params') loadParamStatus();
    if (tab === 'tank') loadTankData();
    if (tab === 'tasks') loadTasksTab();
}

// ── Onboarding Wizard ───────────────────────────────────────────────────

let wizardStep = 1;
const WIZARD_TOTAL = 12;
const wizardData = {
    tank_size_gallons: null,
    has_sump: false,
    sump_size_gallons: null,
    tank_type: null,
    experience: null,
    fish_count: 0,
    filtration: [],
    dosing: null,
    salt_brand: null,
    water_change: null,
    maintenance_day: null,
    goals: [],
    current_problems: '',
};

const WIZARD_QUESTIONS = {
    1: 'How big is your tank?',
    2: 'Do you have a sump?',
    3: 'What kind of reef do you keep?',
    4: 'How long have you been reefing?',
    5: 'How many fish do you have?',
    6: 'What filtration do you run?',
    7: 'Do you dose your tank?',
    8: 'What salt mix do you use?',
    9: 'How do you do water changes?',
    10: 'What day works best for maintenance?',
    11: 'What are your reefing goals?',
    12: 'Anything bugging your tank right now?',
};

function showOnboarding() {
    // Show welcome screen first instead of jumping to wizard
    const welcome = document.getElementById('welcome-screen');
    if (welcome) {
        document.querySelectorAll('.screen').forEach(s => s.classList.add('hidden'));
        welcome.classList.remove('hidden');
    } else {
        startOnboarding();
    }
}

function startOnboarding() {
    document.querySelectorAll('.screen').forEach(s => s.classList.add('hidden'));
    document.getElementById('onboarding-screen').classList.remove('hidden');
    document.getElementById('app-screen').classList.add('hidden');
    wizardStep = 1;
    updateWizardUI();
    populateWizardSalts();
}

function populateWizardSalts() {
    const list = document.getElementById('wizard-salt-list');
    if (!list) return;
    list.innerHTML = '';
    for (const [key, brand] of Object.entries(saltBrands)) {
        const btn = document.createElement('button');
        btn.className = 'wizard-salt-btn';
        btn.dataset.value = key;
        btn.textContent = brand.name;
        btn.onclick = () => selectSalt(btn);
        list.appendChild(btn);
    }
    // Add "Other" option
    const other = document.createElement('button');
    other.className = 'wizard-salt-btn';
    other.dataset.value = 'other';
    other.textContent = 'Other / Not Sure';
    other.onclick = () => selectSalt(other);
    list.appendChild(other);
}

function updateWizardUI() {
    // Progress bar
    const pct = (wizardStep / WIZARD_TOTAL) * 100;
    document.getElementById('wizard-progress-fill').style.width = pct + '%';
    document.getElementById('wizard-step-label').textContent = `Step ${wizardStep} of ${WIZARD_TOTAL}`;
    document.getElementById('wizard-question').textContent = WIZARD_QUESTIONS[wizardStep];

    // Show/hide steps
    document.querySelectorAll('.wizard-step').forEach(el => {
        el.classList.toggle('active', parseInt(el.dataset.step) === wizardStep);
    });

    // Back button visibility
    document.getElementById('wizard-back-btn').style.visibility = wizardStep > 1 ? 'visible' : 'hidden';

    // Next button text
    const nextBtn = document.getElementById('wizard-next-btn');
    if (wizardStep === WIZARD_TOTAL) {
        nextBtn.textContent = 'Generate My Plan';
    } else {
        nextBtn.textContent = 'Continue';
    }
}

function selectTankSize(size) {
    wizardData.tank_size_gallons = size;
    document.getElementById('wizard-tank-size').value = size;
    document.querySelectorAll('[data-step="1"] .wizard-preset-btn').forEach(b => b.classList.remove('selected'));
    event.target.classList.add('selected');
}

function selectSump(hasSump, el) {
    const step = el.closest('.wizard-step');
    step.querySelectorAll('.wizard-card').forEach(c => c.classList.remove('selected'));
    el.classList.add('selected');
    wizardData.has_sump = hasSump;
    document.getElementById('wizard-sump-size-wrap').classList.toggle('hidden', !hasSump);
    if (!hasSump) wizardData.sump_size_gallons = null;
}

function selectSumpSize(size) {
    wizardData.sump_size_gallons = size;
    document.getElementById('wizard-sump-size').value = size;
    document.querySelectorAll('[data-step="2"] .wizard-preset-btn').forEach(b => b.classList.remove('selected'));
    event.target.classList.add('selected');
}

function selectCard(el, field) {
    const step = el.closest('.wizard-step');
    step.querySelectorAll('.wizard-card').forEach(c => c.classList.remove('selected'));
    el.classList.add('selected');
    wizardData[field] = el.dataset.value;
}

function selectSalt(el) {
    document.querySelectorAll('.wizard-salt-btn').forEach(b => b.classList.remove('selected'));
    el.classList.add('selected');
    wizardData.salt_brand = el.dataset.value;
}

function selectDay(el) {
    document.querySelectorAll('.wizard-day-btn').forEach(b => b.classList.remove('selected'));
    el.classList.add('selected');
    wizardData.maintenance_day = el.dataset.value;
}

function toggleMulti(el, field) {
    el.classList.toggle('selected');
    const val = el.dataset.value;
    if (el.classList.contains('selected')) {
        if (!wizardData[field].includes(val)) wizardData[field].push(val);
    } else {
        wizardData[field] = wizardData[field].filter(v => v !== val);
    }
}

function togglePill(el) {
    el.classList.toggle('selected');
}

function adjustFishCount(delta) {
    const input = document.getElementById('wizard-fish-count');
    input.value = Math.max(0, parseInt(input.value || 0) + delta);
    wizardData.fish_count = parseInt(input.value);
}

function setFishCount(n) {
    document.getElementById('wizard-fish-count').value = n;
    wizardData.fish_count = n;
    document.querySelectorAll('[data-step="5"] .wizard-preset-btn').forEach(b => b.classList.remove('selected'));
    event.target.classList.add('selected');
}

function nextStep() {
    // Collect data from current step
    if (wizardStep === 1) {
        const custom = document.getElementById('wizard-tank-size').value;
        if (custom) wizardData.tank_size_gallons = parseFloat(custom);
        if (!wizardData.tank_size_gallons) { showToast('Please select or enter a tank size', 'error'); return; }
    }
    if (wizardStep === 2) {
        // Sump — must pick yes or no
        const sumpSelected = document.querySelector('[data-step="2"] .wizard-card.selected');
        if (!sumpSelected) { showToast('Please select yes or no', 'error'); return; }
        if (wizardData.has_sump) {
            const custom = document.getElementById('wizard-sump-size').value;
            if (custom) wizardData.sump_size_gallons = parseFloat(custom);
            if (!wizardData.sump_size_gallons) { showToast('Please enter your sump size', 'error'); return; }
        }
    }
    if (wizardStep === 3 && !wizardData.tank_type) { showToast('Please select a tank type', 'error'); return; }
    if (wizardStep === 4 && !wizardData.experience) { showToast('Please select your experience level', 'error'); return; }
    if (wizardStep === 5) {
        wizardData.fish_count = parseInt(document.getElementById('wizard-fish-count').value || 0);
    }
    // Step 6 (filtration) is optional multi-select
    if (wizardStep === 7 && !wizardData.dosing) { showToast('Please select a dosing option', 'error'); return; }
    if (wizardStep === 8 && !wizardData.salt_brand) { showToast('Please select your salt brand', 'error'); return; }
    if (wizardStep === 9 && !wizardData.water_change) { showToast('Please select a water change schedule', 'error'); return; }
    if (wizardStep === 10 && !wizardData.maintenance_day) { showToast('Please select a maintenance day', 'error'); return; }
    // Steps 11 & 12 are optional

    if (wizardStep === 12) {
        // Collect problems
        const pills = document.querySelectorAll('.wizard-pill.selected');
        const pillTexts = Array.from(pills).map(p => p.textContent);
        const freeText = (document.getElementById('wizard-problems-text').value || '').trim();
        wizardData.current_problems = [...pillTexts, freeText].filter(Boolean).join(', ');
        submitOnboarding();
        return;
    }

    wizardStep++;
    updateWizardUI();
}

function prevStep() {
    if (wizardStep > 1) {
        wizardStep--;
        updateWizardUI();
    }
}

async function submitOnboarding() {
    // Show loading
    document.querySelector('.wizard-steps-viewport').classList.add('hidden');
    document.querySelector('.wizard-nav').classList.add('hidden');
    document.querySelector('.wizard-progress-bar').classList.add('hidden');
    document.getElementById('wizard-step-label').classList.add('hidden');
    document.getElementById('wizard-question').classList.add('hidden');
    document.getElementById('wizard-loading').classList.remove('hidden');

    try {
        const data = await api('/onboard/submit', {
            method: 'POST',
            body: wizardData,
        });

        // Show plan ready
        document.getElementById('wizard-loading').classList.add('hidden');
        document.getElementById('wizard-plan-ready').classList.remove('hidden');

        const summary = document.getElementById('wizard-plan-summary');
        const plan = data.plan || {};
        summary.innerHTML = `
            <p class="plan-welcome">${plan.welcome_message || 'Your tank is set up!'}</p>
            ${plan.tips ? `<div class="plan-tips"><h4>Tips for You</h4><ul>${plan.tips.map(t => `<li>${t}</li>`).join('')}</ul></div>` : ''}
            ${plan.priority_focus ? `<div class="plan-focus"><h4>Priority Focus</h4><p>${plan.priority_focus}</p></div>` : ''}
            ${data.tasks ? `<div class="plan-tasks"><h4>Your Schedule (${data.tasks.length} tasks)</h4><ul>${data.tasks.map(t => `<li>${t.title} — ${t.frequency}</li>`).join('')}</ul></div>` : ''}
        `;
    } catch (err) {
        showToast('Setup failed: ' + err.message, 'error');
        // Show wizard again
        document.getElementById('wizard-loading').classList.add('hidden');
        document.querySelector('.wizard-steps-viewport').classList.remove('hidden');
        document.querySelector('.wizard-nav').classList.remove('hidden');
        document.querySelector('.wizard-progress-bar').classList.remove('hidden');
        document.getElementById('wizard-step-label').classList.remove('hidden');
        document.getElementById('wizard-question').classList.remove('hidden');
    }
}

async function finishOnboarding() {
    currentUser = await api('/auth/me');
    enterApp();
}

// ── Salt Brand Dropdown Helper ───────────────────────────────────────────

async function loadSaltBrands() {
    try {
        const data = await api('/data/salt-brands');
        saltBrands = data.brands;
    } catch {
        // Fallback
        saltBrands = {};
    }
}

function populateSaltDropdown(selectId) {
    const sel = document.getElementById(selectId);
    if (!sel) return;
    // Keep existing first option if it's a placeholder
    const placeholder = sel.options[0];
    sel.innerHTML = '';
    if (placeholder && !placeholder.value) sel.appendChild(placeholder);

    for (const [key, brand] of Object.entries(saltBrands)) {
        const opt = document.createElement('option');
        opt.value = key;
        opt.textContent = brand.name;
        sel.appendChild(opt);
    }
}

// ── Modal Helper ─────────────────────────────────────────────────────────

function closeModal(id) {
    document.getElementById(id).classList.add('hidden');
}

// ── Chat History Clear ───────────────────────────────────────────────────

async function clearChatHistory() {
    try {
        await api('/chat/history', { method: 'DELETE' });
        const msgs = document.getElementById('chat-messages');
        msgs.innerHTML = '';
        addChatWelcome();
        showToast('Chat history cleared', 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ── Account Deletion ────────────────────────────────────────────────────

async function confirmDeleteAccount() {
    const confirmed = confirm(
        'Are you sure you want to delete your account?\n\n' +
        'This will permanently remove ALL your data including:\n' +
        '- Tank profile and settings\n' +
        '- All water parameter history\n' +
        '- Livestock and equipment records\n' +
        '- Chat history\n' +
        '- Maintenance schedules\n' +
        '- Cost tracking data\n' +
        '- Tank photos\n\n' +
        'This action CANNOT be undone.'
    );
    if (!confirmed) return;

    const doubleConfirm = confirm(
        'FINAL WARNING: This is irreversible.\n\nType OK to permanently delete your account.'
    );
    if (!doubleConfirm) return;

    try {
        await api('/auth/delete-account', { method: 'DELETE' });
        currentUser = null;
        document.getElementById('auth-screen').classList.remove('hidden');
        document.getElementById('app-screen').classList.add('hidden');
        closeModal('settings-modal');
        showToast('Account deleted successfully', 'success');
    } catch (err) {
        showToast('Failed to delete account: ' + err.message, 'error');
    }
}

// ── Password Visibility Toggle ──────────────────────────────────────────

function togglePasswordVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    if (input.type === 'password') {
        input.type = 'text';
        btn.setAttribute('aria-label', 'Hide password');
    } else {
        input.type = 'password';
        btn.setAttribute('aria-label', 'Show password');
    }
}

// ── Password Strength Indicator ─────────────────────────────────────────

function checkPasswordStrength(password) {
    let score = 0;
    if (password.length >= 8) score++;
    if (/[A-Z]/.test(password)) score++;
    if (/[a-z]/.test(password)) score++;
    if (/[0-9]/.test(password)) score++;
    if (/[^A-Za-z0-9]/.test(password)) score++;
    return score; // 0-5
}

function updatePasswordStrength() {
    const pw = document.getElementById('reg-password').value;
    const el = document.getElementById('password-strength');
    if (!el) return;

    if (!pw) { el.innerHTML = ''; return; }

    const score = checkPasswordStrength(pw);
    const labels = ['', 'Weak', 'Weak', 'Fair', 'Strong', 'Very Strong'];
    const label = labels[score] || 'Weak';

    let bars = '';
    for (let i = 0; i < 4; i++) {
        let cls = '';
        if (score >= 4 && i < 4) cls = 'strong';
        else if (score >= 3 && i < 3) cls = 'medium';
        else if (score >= 1 && i < score) cls = 'weak';
        bars += `<div class="strength-bar ${cls}"></div>`;
    }
    el.innerHTML = bars + `<div class="password-strength-label">${label}</div>`;
}

// ── Auth Form Switching ─────────────────────────────────────────────────

let pendingVerifyEmail = '';
let pendingResetEmail = '';

function hideAllAuthForms() {
    ['login-form', 'register-form', 'verify-form', 'forgot-form', 'reset-form'].forEach(id => {
        document.getElementById(id).classList.add('hidden');
    });
}

function showForgotPassword() {
    hideAllAuthForms();
    document.getElementById('forgot-form').classList.remove('hidden');
}

function showVerifyForm(email) {
    pendingVerifyEmail = email;
    hideAllAuthForms();
    document.getElementById('verify-email-display').textContent = email;
    document.getElementById('verify-form').classList.remove('hidden');
}

function showResetForm(email) {
    pendingResetEmail = email;
    hideAllAuthForms();
    document.getElementById('reset-email-display').textContent = email;
    document.getElementById('reset-form').classList.remove('hidden');
}

// Override showLogin/showRegister to handle all forms
function showLogin() {
    hideAllAuthForms();
    document.getElementById('login-form').classList.remove('hidden');
}

function showRegister() {
    hideAllAuthForms();
    document.getElementById('register-form').classList.remove('hidden');
}

// ── Email Verification ──────────────────────────────────────────────────

async function handleVerifyEmail(e) {
    e.preventDefault();
    const errEl = document.getElementById('verify-error');
    errEl.textContent = '';
    const code = document.getElementById('verify-code').value.trim();

    try {
        const data = await api('/auth/verify-email', {
            method: 'POST',
            body: { email: pendingVerifyEmail, code },
        });
        currentUser = data;
        showToast('Email verified!', 'success');
        enterApp();
    } catch (err) {
        errEl.textContent = err.message;
    }
    return false;
}

async function resendVerification() {
    try {
        await api('/auth/send-verification', {
            method: 'POST',
            body: { email: pendingVerifyEmail },
        });
        showToast('New code sent!', 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ── Forgot / Reset Password ─────────────────────────────────────────────

async function handleForgotPassword(e) {
    e.preventDefault();
    const errEl = document.getElementById('forgot-error');
    errEl.textContent = '';
    const email = document.getElementById('forgot-email').value.trim().toLowerCase();

    try {
        await api('/auth/forgot-password', {
            method: 'POST',
            body: { email },
        });
        showToast('Reset code sent!', 'success');
        showResetForm(email);
    } catch (err) {
        errEl.textContent = err.message;
    }
    return false;
}

async function handleResetPassword(e) {
    e.preventDefault();
    const errEl = document.getElementById('reset-error');
    errEl.textContent = '';
    const code = document.getElementById('reset-code').value.trim();
    const password = document.getElementById('reset-password').value;

    if (password.length < 8) {
        errEl.textContent = 'Password must be at least 8 characters';
        return false;
    }

    try {
        await api('/auth/reset-password', {
            method: 'POST',
            body: { email: pendingResetEmail, code, password },
        });
        showToast('Password reset! Please sign in.', 'success');
        showLogin();
    } catch (err) {
        errEl.textContent = err.message;
    }
    return false;
}

// ── Init ─────────────────────────────────────────────────────────────────

// ── Offline Detection ────────────────────────────────────────────────────

function updateOnlineStatus() {
    const banner = document.getElementById('offline-banner');
    if (banner) {
        banner.classList.toggle('hidden', navigator.onLine);
    }
}

window.addEventListener('online', updateOnlineStatus);
window.addEventListener('offline', updateOnlineStatus);

// ── Init ─────────────────────────────────────────────────────────────────

async function init() {
    // Password strength indicator on registration
    const regPw = document.getElementById('reg-password');
    if (regPw) regPw.addEventListener('input', updatePasswordStrength);

    await loadSaltBrands();

    try {
        currentUser = await api('/auth/me');
        document.getElementById('loading-splash').classList.add('hidden');
        enterApp();
    } catch {
        // Not logged in — show auth screen
        document.getElementById('loading-splash').classList.add('hidden');
        document.getElementById('auth-screen').classList.remove('hidden');
    }

    // Register service worker and force update check
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js').then(reg => {
            reg.update();
        }).catch(() => {});
    }

    // Check initial online status
    updateOnlineStatus();
}

init();
