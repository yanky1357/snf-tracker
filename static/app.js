/* ═══════════════════════════════════════════════════════════════════════════ */
/*  NourishNY — Frontend Logic                                                */
/* ═══════════════════════════════════════════════════════════════════════════ */

// ── Application Form ────────────────────────────────────────────────────────

const appForm = document.getElementById('applicationForm');
if (appForm) {
  // Dynamic household members
  const numSelect = document.getElementById('num_members');
  const membersDiv = document.getElementById('householdMembers');

  numSelect.addEventListener('change', () => {
    const count = parseInt(numSelect.value);
    membersDiv.innerHTML = '';
    for (let i = 1; i <= count; i++) {
      const block = document.createElement('div');
      block.className = 'member-block';
      block.innerHTML = `
        <h4>Member ${i}</h4>
        <div class="form-grid">
          <div class="form-group">
            <label>First Name <span class="req">*</span></label>
            <input type="text" class="member-first" placeholder="First name" required />
          </div>
          <div class="form-group">
            <label>Last Name <span class="req">*</span></label>
            <input type="text" class="member-last" placeholder="Last name" required />
          </div>
          <div class="form-group">
            <label>Date of Birth <span class="req">*</span></label>
            <input type="text" class="member-dob" placeholder="MM/DD/YYYY" required />
          </div>
          <div class="form-group">
            <label>Medicaid ID <span class="req">*</span></label>
            <input type="text" class="member-medicaid" placeholder="AB12345C" maxlength="8" required />
          </div>
        </div>
      `;
      membersDiv.appendChild(block);
    }
  });

  // Submit handler
  appForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const errDiv = document.getElementById('formError');
    const submitBtn = document.getElementById('submitBtn');
    errDiv.style.display = 'none';

    // Clear previous error styles
    appForm.querySelectorAll('.error').forEach(el => el.classList.remove('error'));

    // Gather data
    const get = (id) => document.getElementById(id)?.value?.trim() || '';

    // Validate required fields
    const requiredFields = [
      'first_name', 'last_name', 'date_of_birth', 'medicaid_id',
      'cell_phone', 'email', 'street_address', 'city', 'zipcode',
      'is_employed', 'spouse_employed', 'has_wic', 'has_snap', 'is_new_applicant'
    ];

    let hasError = false;
    for (const f of requiredFields) {
      const el = document.getElementById(f);
      if (!el || !el.value.trim()) {
        if (el) el.classList.add('error');
        hasError = true;
      }
    }

    if (hasError) {
      errDiv.textContent = 'Please fill in all required fields.';
      errDiv.style.display = 'block';
      errDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }

    // Validate Medicaid ID
    const mid = get('medicaid_id').toUpperCase();
    if (!/^[A-Z]{2}\d{5}[A-Z]$/.test(mid)) {
      document.getElementById('medicaid_id').classList.add('error');
      errDiv.textContent = 'Invalid Medicaid ID format. Must be 2 letters + 5 numbers + 1 letter (e.g., AB12345C).';
      errDiv.style.display = 'block';
      errDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }

    // Gather health categories
    const healthCategories = [];
    appForm.querySelectorAll('input[name="health_categories"]:checked').forEach(cb => {
      healthCategories.push(cb.value);
    });

    // Gather household members
    const members = [];
    document.querySelectorAll('.member-block').forEach(block => {
      members.push({
        first_name: block.querySelector('.member-first')?.value?.trim() || '',
        last_name: block.querySelector('.member-last')?.value?.trim() || '',
        date_of_birth: block.querySelector('.member-dob')?.value?.trim() || '',
        medicaid_id: block.querySelector('.member-medicaid')?.value?.trim() || ''
      });
    });

    const payload = {
      first_name: get('first_name'),
      last_name: get('last_name'),
      date_of_birth: get('date_of_birth'),
      medicaid_id: mid,
      cell_phone: get('cell_phone'),
      home_phone: get('home_phone'),
      email: get('email'),
      street_address: get('street_address'),
      apt_unit: get('apt_unit'),
      city: get('city'),
      state: get('state'),
      zipcode: get('zipcode'),
      health_categories: healthCategories,
      is_employed: get('is_employed'),
      spouse_employed: get('spouse_employed'),
      has_wic: get('has_wic'),
      has_snap: get('has_snap'),
      food_allergies: get('food_allergies'),
      is_new_applicant: get('is_new_applicant'),
      household_members: members
    };

    submitBtn.disabled = true;
    submitBtn.textContent = 'Submitting...';

    try {
      const res = await fetch('/api/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (res.ok && data.success) {
        window.location.href = '/thank-you';
      } else {
        errDiv.textContent = data.error || 'Something went wrong. Please try again.';
        errDiv.style.display = 'block';
        errDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    } catch (err) {
      errDiv.textContent = 'Network error. Please check your connection and try again.';
      errDiv.style.display = 'block';
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Submit Application \u2192';
    }
  });
}


// ── Admin Dashboard ─────────────────────────────────────────────────────────

const loginForm = document.getElementById('loginForm');
if (loginForm) {
  const loginView = document.getElementById('loginView');
  const dashView = document.getElementById('dashboardView');
  const logoutBtn = document.getElementById('logoutBtn');
  let currentPage = 1;

  // Login
  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const pw = document.getElementById('adminPassword').value;
    const errDiv = document.getElementById('loginError');

    try {
      const res = await fetch('/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: pw })
      });
      const data = await res.json();

      if (res.ok && data.success) {
        loginView.style.display = 'none';
        dashView.style.display = 'block';
        logoutBtn.style.display = 'inline-block';
        loadStats();
        loadApplications();
      } else {
        errDiv.textContent = 'Invalid password.';
        errDiv.style.display = 'block';
      }
    } catch (err) {
      errDiv.textContent = 'Network error.';
      errDiv.style.display = 'block';
    }
  });

  // Search and filter
  const searchInput = document.getElementById('searchInput');
  const statusFilter = document.getElementById('statusFilter');
  let searchTimeout;

  searchInput.addEventListener('input', () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => { currentPage = 1; loadApplications(); }, 400);
  });

  statusFilter.addEventListener('change', () => { currentPage = 1; loadApplications(); });

  async function loadStats() {
    try {
      const res = await fetch('/api/admin/stats');
      const data = await res.json();
      document.getElementById('statTotal').textContent = data.total;
      document.getElementById('statNew').textContent = data.new;
      document.getElementById('statReviewed').textContent = data.reviewed;
      document.getElementById('statEnrolled').textContent = data.enrolled;
      document.getElementById('statRejected').textContent = data.rejected;
    } catch (err) {
      console.error('Failed to load stats', err);
    }
  }

  async function loadApplications() {
    const search = searchInput.value.trim();
    const status = statusFilter.value;
    const params = new URLSearchParams({ page: currentPage });
    if (search) params.set('search', search);
    if (status) params.set('status', status);

    try {
      const res = await fetch(`/api/admin/applications?${params}`);
      if (res.status === 401) {
        loginView.style.display = '';
        dashView.style.display = 'none';
        logoutBtn.style.display = 'none';
        return;
      }
      const data = await res.json();
      renderTable(data.applications);
      renderPagination(data.page, data.pages);
    } catch (err) {
      console.error('Failed to load applications', err);
    }
  }

  function renderTable(apps) {
    const tbody = document.getElementById('appTableBody');
    if (!apps.length) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#888;padding:32px;">No applications found.</td></tr>';
      return;
    }

    tbody.innerHTML = apps.map(a => `
      <tr>
        <td>#${a.id}</td>
        <td><strong>${esc(a.first_name)} ${esc(a.last_name)}</strong></td>
        <td>${esc(a.medicaid_id)}</td>
        <td>${esc(a.cell_phone)}</td>
        <td>${esc(a.city)}</td>
        <td><span class="badge badge-${a.status}">${a.status}</span></td>
        <td>${formatDate(a.created_at)}</td>
        <td><button class="btn-view" onclick="viewApplication(${a.id})">View</button></td>
      </tr>
    `).join('');
  }

  function renderPagination(page, pages) {
    const div = document.getElementById('pagination');
    if (pages <= 1) { div.innerHTML = ''; return; }
    let html = '';
    for (let i = 1; i <= pages; i++) {
      html += `<button class="page-btn ${i === page ? 'active' : ''}" onclick="goToPage(${i})">${i}</button>`;
    }
    div.innerHTML = html;
  }

  window.goToPage = (p) => { currentPage = p; loadApplications(); };

  window.viewApplication = async (id) => {
    try {
      const res = await fetch(`/api/admin/applications/${id}`);
      const a = await res.json();
      if (res.status === 401) return;

      const healthTags = (a.health_categories || [])
        .map(h => `<span class="detail-tag">${esc(h)}</span>`).join('') || '<span style="color:#888;">None selected</span>';

      const membersHtml = (a.household_members || []).map((m, i) => `
        <div class="detail-grid" style="margin-bottom:8px;">
          <div class="detail-item"><label>Name</label><span>${esc(m.first_name)} ${esc(m.last_name)}</span></div>
          <div class="detail-item"><label>DOB</label><span>${esc(m.date_of_birth)}</span></div>
          <div class="detail-item"><label>Medicaid ID</label><span>${esc(m.medicaid_id)}</span></div>
        </div>
      `).join('') || '<p style="color:#888;">No additional members</p>';

      document.getElementById('detailContent').innerHTML = `
        <h3 style="margin-bottom:4px;">${esc(a.first_name)} ${esc(a.last_name)}</h3>
        <p style="color:#888;margin-bottom:16px;">Application #${a.id} &mdash; ${formatDate(a.created_at)}</p>

        <div class="detail-section-title" style="border:none;padding:0;margin-top:0;">Personal Information</div>
        <div class="detail-grid">
          <div class="detail-item"><label>Date of Birth</label><span>${esc(a.date_of_birth)}</span></div>
          <div class="detail-item"><label>Medicaid ID</label><span>${esc(a.medicaid_id)}</span></div>
        </div>

        <div class="detail-section-title">Contact</div>
        <div class="detail-grid">
          <div class="detail-item"><label>Cell Phone</label><span>${esc(a.cell_phone)}</span></div>
          <div class="detail-item"><label>Home Phone</label><span>${esc(a.home_phone || 'N/A')}</span></div>
          <div class="detail-item"><label>Email</label><span>${esc(a.email)}</span></div>
        </div>

        <div class="detail-section-title">Address</div>
        <div class="detail-grid">
          <div class="detail-item"><label>Street</label><span>${esc(a.street_address)}${a.apt_unit ? ', ' + esc(a.apt_unit) : ''}</span></div>
          <div class="detail-item"><label>City/State/Zip</label><span>${esc(a.city)}, ${esc(a.state)} ${esc(a.zipcode)}</span></div>
        </div>

        <div class="detail-section-title">Health Categories</div>
        <div class="detail-tags">${healthTags}</div>

        <div class="detail-section-title">Benefits & Employment</div>
        <div class="detail-grid">
          <div class="detail-item"><label>Employed</label><span>${esc(a.is_employed)}</span></div>
          <div class="detail-item"><label>Spouse Employed</label><span>${esc(a.spouse_employed)}</span></div>
          <div class="detail-item"><label>WIC</label><span>${esc(a.has_wic)}</span></div>
          <div class="detail-item"><label>SNAP</label><span>${esc(a.has_snap)}</span></div>
          <div class="detail-item"><label>Food Allergies</label><span>${esc(a.food_allergies || 'None')}</span></div>
          <div class="detail-item"><label>New Applicant</label><span>${esc(a.is_new_applicant)}</span></div>
        </div>

        <div class="detail-section-title">Household Members</div>
        ${membersHtml}

        <div class="status-form">
          <h4>Update Status</h4>
          <select id="modalStatus">
            <option value="new" ${a.status === 'new' ? 'selected' : ''}>New</option>
            <option value="reviewed" ${a.status === 'reviewed' ? 'selected' : ''}>Reviewed</option>
            <option value="enrolled" ${a.status === 'enrolled' ? 'selected' : ''}>Enrolled</option>
            <option value="rejected" ${a.status === 'rejected' ? 'selected' : ''}>Rejected</option>
          </select>
          <textarea id="modalNotes" placeholder="Admin notes...">${esc(a.admin_notes || '')}</textarea>
          <button class="btn" onclick="updateStatus(${a.id})">Save Changes</button>
        </div>
      `;

      document.getElementById('detailModal').style.display = 'flex';
    } catch (err) {
      console.error('Failed to load application', err);
    }
  };

  window.updateStatus = async (id) => {
    const status = document.getElementById('modalStatus').value;
    const notes = document.getElementById('modalNotes').value;

    try {
      await fetch(`/api/admin/applications/${id}/status`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status, admin_notes: notes })
      });
      closeModal();
      loadStats();
      loadApplications();
    } catch (err) {
      console.error('Failed to update status', err);
    }
  };

  window.closeModal = () => {
    document.getElementById('detailModal').style.display = 'none';
  };

  window.adminLogout = async () => {
    await fetch('/api/admin/logout', { method: 'POST' });
    loginView.style.display = '';
    dashView.style.display = 'none';
    logoutBtn.style.display = 'none';
    document.getElementById('adminPassword').value = '';
  };
}

// ── Utilities ───────────────────────────────────────────────────────────────

function esc(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = String(str);
  return div.innerHTML;
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}
