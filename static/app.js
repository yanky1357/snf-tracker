/* ── State ────────────────────────────────────────────────────────────────── */
const state = {
  query:     '',
  filterState: '',
  filterType:  '',
  page:      1,
  totalPages: 1,
  mapStatePage: 1,
  mapStateTotalPages: 1,
  selectedMapState: null,
};

/* ── Badge helpers ─────────────────────────────────────────────────────────── */
const BADGE_CLASS = {
  'Private Equity':  'pe',
  'LLC':             'llc',
  'Corporation':     'corp',
  'Holding Co.':     'holding',
  'Investment Firm': 'investment',
  'Non-Profit':      'nonprofit',
  'REIT':            'reit',
  'Trust/Trustee':   'trust',
  'For-Profit':      'forprofit',
  'Chain Office':    'chain',
  'Mgmt. Co.':       'mgmt',
};

function makeBadge(label) {
  const cls = BADGE_CLASS[label] || 'default';
  return `<span class="badge badge-${cls}">${label}</span>`;
}

function badgeRow(typesStr) {
  if (!typesStr) return '';
  return typesStr.split(',').filter(Boolean).map(makeBadge).join('');
}

/* ── API calls ─────────────────────────────────────────────────────────────── */
async function apiFetch(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/* ── Tab switching ─────────────────────────────────────────────────────────── */
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => {
      p.classList.remove('active');
      p.hidden = true;
    });
    btn.classList.add('active');
    const panel = document.getElementById(`tab-${tab}`);
    panel.hidden = false;
    panel.classList.add('active');
    if (tab === 'map') initMap();
  });
});

/* ── Search ────────────────────────────────────────────────────────────────── */
const searchInput = document.getElementById('search-input');
const clearBtn    = document.getElementById('clear-btn');
const filterState = document.getElementById('filter-state');
const filterType  = document.getElementById('filter-type');

let debounceTimer = null;
searchInput.addEventListener('input', () => {
  clearBtn.hidden = searchInput.value.length === 0;
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    state.page = 1;
    performSearch();
  }, 400);
});

searchInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') { clearTimeout(debounceTimer); state.page = 1; performSearch(); }
});

clearBtn.addEventListener('click', () => {
  searchInput.value = '';
  clearBtn.hidden = true;
  state.page = 1;
  performSearch();
});

filterState.addEventListener('change', () => { state.page = 1; performSearch(); });
filterType.addEventListener('change',  () => { state.page = 1; performSearch(); });

document.getElementById('prev-btn').addEventListener('click', () => {
  if (state.page > 1) { state.page--; performSearch(false); }
});
document.getElementById('next-btn').addEventListener('click', () => {
  if (state.page < state.totalPages) { state.page++; performSearch(false); }
});

async function performSearch(scrollTop = true) {
  const q     = searchInput.value.trim();
  const sState = filterState.value;
  const sType  = filterType.value;

  const welcome = document.getElementById('welcome');
  const resultsHeader = document.getElementById('results-header');
  const resultsList   = document.getElementById('results-list');
  const pagination    = document.getElementById('pagination');

  // Show loading in list
  welcome.hidden = true;
  resultsHeader.hidden = true;
  pagination.hidden = true;
  resultsList.innerHTML = '<div class="loading-state"><div class="spinner"></div><span>Searching...</span></div>';

  const params = new URLSearchParams({ page: state.page });
  if (q)      params.set('q', q);
  if (sState) params.set('state', sState);
  if (sType)  params.set('owner_type', sType);

  try {
    const data = await apiFetch(`/api/search?${params}`);
    state.totalPages = data.total_pages;

    if (data.facilities.length === 0) {
      resultsList.innerHTML = `
        <div class="empty-state">
          <h3>No facilities found</h3>
          <p>Try a different search term or remove a filter.</p>
        </div>`;
      resultsHeader.hidden = false;
      document.getElementById('results-count').textContent =
        `0 results${q ? ` for "${q}"` : ''}`;
      return;
    }

    // Results header
    const from  = (state.page - 1) * data.per_page + 1;
    const to    = Math.min(state.page * data.per_page, data.total);
    resultsHeader.hidden = false;
    document.getElementById('results-count').textContent =
      `Showing ${from}–${to} of ${data.total.toLocaleString()} facilities${q ? ` matching "${q}"` : ''}`;

    // Cards
    resultsList.innerHTML = data.facilities.map(f => `
      <div class="result-card">
        <div class="result-main">
          <div class="result-name" title="${esc(f.organization_name)}">${esc(f.organization_name)}</div>
          <div class="result-meta">
            <span>${f.facility_state || 'Unknown state'}</span>
            <span>${f.owner_count} ownership record${f.owner_count !== 1 ? 's' : ''}</span>
            <span>${f.enrollment_id}</span>
          </div>
          <div class="badge-row">${badgeRow(f.owner_types)}</div>
        </div>
        <button class="chain-btn" data-eid="${esc(f.enrollment_id)}"
                data-name="${esc(f.organization_name)}">
          View Ownership Chain
        </button>
      </div>
    `).join('');

    // Attach chain button handlers
    resultsList.querySelectorAll('.chain-btn').forEach(btn => {
      btn.addEventListener('click', () => openChainModal(btn.dataset.eid, btn.dataset.name));
    });

    // Pagination
    pagination.hidden = data.total_pages <= 1;
    document.getElementById('prev-btn').disabled = state.page <= 1;
    document.getElementById('next-btn').disabled = state.page >= state.totalPages;
    document.getElementById('page-info').textContent =
      `Page ${state.page} of ${state.totalPages}`;

    if (scrollTop) window.scrollTo({ top: 0, behavior: 'smooth' });
  } catch (err) {
    resultsList.innerHTML = `<div class="empty-state"><h3>Error loading results</h3><p>${err.message}</p></div>`;
  }
}

function esc(str) {
  return String(str ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/* ── State filter population ─────────────────────────────────────────────── */
async function populateStateFilter() {
  try {
    const states = await apiFetch('/api/states');
    const US_NAMES = {
      AL:'Alabama', AK:'Alaska', AZ:'Arizona', AR:'Arkansas', CA:'California',
      CO:'Colorado', CT:'Connecticut', DE:'Delaware', DC:'D.C.', FL:'Florida',
      GA:'Georgia', HI:'Hawaii', ID:'Idaho', IL:'Illinois', IN:'Indiana',
      IA:'Iowa', KS:'Kansas', KY:'Kentucky', LA:'Louisiana', ME:'Maine',
      MD:'Maryland', MA:'Massachusetts', MI:'Michigan', MN:'Minnesota',
      MS:'Mississippi', MO:'Missouri', MT:'Montana', NE:'Nebraska', NV:'Nevada',
      NH:'New Hampshire', NJ:'New Jersey', NM:'New Mexico', NY:'New York',
      NC:'North Carolina', ND:'North Dakota', OH:'Ohio', OK:'Oklahoma',
      OR:'Oregon', PA:'Pennsylvania', RI:'Rhode Island', SC:'South Carolina',
      SD:'South Dakota', TN:'Tennessee', TX:'Texas', UT:'Utah', VT:'Vermont',
      VA:'Virginia', WA:'Washington', WV:'West Virginia', WI:'Wisconsin', WY:'Wyoming',
    };
    const opts = states.map(s =>
      `<option value="${s.state}">${US_NAMES[s.state] || s.state} (${s.count.toLocaleString()})</option>`
    ).join('');
    filterState.innerHTML = '<option value="">All States</option>' + opts;
  } catch (_) {}
}

/* ── Ownership Chain Modal ────────────────────────────────────────────────── */
const modal     = document.getElementById('chain-modal');
const modalTitle= document.getElementById('modal-title');
const modalState= document.getElementById('modal-state-badge');
const chainTree = document.getElementById('chain-tree');
const chainLoad = document.getElementById('chain-loading');

function openChainModal(enrollmentId, facilityName) {
  modal.hidden = false;
  document.body.style.overflow = 'hidden';
  modalTitle.textContent = facilityName || enrollmentId;
  modalState.textContent = '';
  chainTree.innerHTML = '';
  chainLoad.style.display = 'flex';
  loadChain(enrollmentId);
}

function closeModal() {
  modal.hidden = true;
  document.body.style.overflow = '';
}

document.getElementById('modal-close').addEventListener('click', closeModal);
document.getElementById('modal-backdrop').addEventListener('click', closeModal);
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

async function loadChain(enrollmentId) {
  try {
    const data = await apiFetch(`/api/chain/${encodeURIComponent(enrollmentId)}`);
    chainLoad.style.display = 'none';

    if (data.state) {
      modalState.textContent = `State: ${data.state}`;
    }

    if (!data.owners || data.owners.length === 0) {
      chainTree.innerHTML = '<div class="no-chain">No ownership records found for this facility.</div>';
      return;
    }

    chainTree.innerHTML = '';
    const rootLabel = document.createElement('div');
    rootLabel.className = 'chain-root-label';
    rootLabel.textContent = 'Ownership structure (facility → owners → parent companies)';
    chainTree.appendChild(rootLabel);

    const facilityEl = document.createElement('div');
    facilityEl.className = 'chain-facility';
    facilityEl.textContent = data.display_name;
    chainTree.appendChild(facilityEl);

    const group = buildOwnerGroup(data.owners, 0);
    chainTree.appendChild(group);
  } catch (err) {
    chainLoad.style.display = 'none';
    chainTree.innerHTML = `<div class="no-chain">Error loading chain: ${err.message}</div>`;
  }
}

function buildOwnerGroup(owners, depth) {
  const group = document.createElement('div');
  group.className = 'chain-group';

  // Separate ownership-interest rows from management/officer rows
  const ownershipRoles = owners.filter(o =>
    /ownership|partnership|trustee|interest/i.test(o.role) || o.children.length > 0
  );
  const otherRoles = owners.filter(o =>
    !/ownership|partnership|trustee|interest/i.test(o.role) && o.children.length === 0
  );
  const sorted = [...ownershipRoles, ...otherRoles];

  sorted.forEach(owner => {
    const node = document.createElement('div');
    node.className = 'chain-node';

    const card = document.createElement('div');
    card.className = 'chain-node-card' + (
      !owner.owned_by_another && owner.children.length === 0 && depth > 0 ? ' ultimate' : ''
    );

    const nameRow = document.createElement('div');
    nameRow.className = 'chain-node-name';
    nameRow.textContent = owner.display_name;
    if (owner.percentage && parseFloat(owner.percentage) > 0) {
      const pct = document.createElement('span');
      pct.className = 'chain-node-pct';
      pct.textContent = `${parseFloat(owner.percentage).toFixed(0)}%`;
      nameRow.appendChild(pct);
    }
    card.appendChild(nameRow);

    if (owner.role) {
      const roleEl = document.createElement('div');
      roleEl.className = 'chain-node-role';
      roleEl.textContent = owner.role + (owner.state ? ` · ${owner.state}` : '');
      card.appendChild(roleEl);
    }

    if (owner.types && owner.types.length > 0) {
      const badges = document.createElement('div');
      badges.className = 'badge-row';
      badges.style.marginTop = '.3rem';
      badges.innerHTML = owner.types.map(makeBadge).join('');
      card.appendChild(badges);
    }

    if (!owner.owned_by_another && owner.children.length === 0 && depth > 0) {
      const ult = document.createElement('div');
      ult.className = 'ultimate-label';
      ult.textContent = 'Ultimate Owner';
      card.appendChild(ult);
    }

    node.appendChild(card);

    if (owner.children && owner.children.length > 0) {
      const arrow = document.createElement('div');
      arrow.className = 'chain-arrow';
      arrow.textContent = 'Owned by:';
      node.appendChild(arrow);
      node.appendChild(buildOwnerGroup(owner.children, depth + 1));
    }

    group.appendChild(node);
  });

  return group;
}

/* ── Map ──────────────────────────────────────────────────────────────────── */
let mapInitialized = false;

const STATE_FIPS = {
  '01':'AL','02':'AK','04':'AZ','05':'AR','06':'CA','08':'CO','09':'CT',
  '10':'DE','11':'DC','12':'FL','13':'GA','15':'HI','16':'ID','17':'IL',
  '18':'IN','19':'IA','20':'KS','21':'KY','22':'LA','23':'ME','24':'MD',
  '25':'MA','26':'MI','27':'MN','28':'MS','29':'MO','30':'MT','31':'NE',
  '32':'NV','33':'NH','34':'NJ','35':'NM','36':'NY','37':'NC','38':'ND',
  '39':'OH','40':'OK','41':'OR','42':'PA','44':'RI','45':'SC','46':'SD',
  '47':'TN','48':'TX','49':'UT','50':'VT','51':'VA','53':'WA','54':'WV',
  '55':'WI','56':'WY',
};

const STATE_NAMES = {
  AL:'Alabama', AK:'Alaska', AZ:'Arizona', AR:'Arkansas', CA:'California',
  CO:'Colorado', CT:'Connecticut', DE:'Delaware', DC:'Washington D.C.',
  FL:'Florida', GA:'Georgia', HI:'Hawaii', ID:'Idaho', IL:'Illinois',
  IN:'Indiana', IA:'Iowa', KS:'Kansas', KY:'Kentucky', LA:'Louisiana',
  ME:'Maine', MD:'Maryland', MA:'Massachusetts', MI:'Michigan', MN:'Minnesota',
  MS:'Mississippi', MO:'Missouri', MT:'Montana', NE:'Nebraska', NV:'Nevada',
  NH:'New Hampshire', NJ:'New Jersey', NM:'New Mexico', NY:'New York',
  NC:'North Carolina', ND:'North Dakota', OH:'Ohio', OK:'Oklahoma',
  OR:'Oregon', PA:'Pennsylvania', RI:'Rhode Island', SC:'South Carolina',
  SD:'South Dakota', TN:'Tennessee', TX:'Texas', UT:'Utah', VT:'Vermont',
  VA:'Virginia', WA:'Washington', WV:'West Virginia', WI:'Wisconsin', WY:'Wyoming',
};

async function initMap() {
  if (mapInitialized) return;
  mapInitialized = true;

  const svgEl   = document.getElementById('us-map');
  const tooltip = document.getElementById('map-tooltip');

  try {
    const [statesData, usTopoJson] = await Promise.all([
      apiFetch('/api/states'),
      fetch('https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json').then(r => r.json()),
    ]);

    const countByState = {};
    statesData.forEach(d => { countByState[d.state] = d.count; });
    const maxCount = Math.max(...Object.values(countByState));

    const colorScale = d3.scaleSequentialLog(d3.interpolateBlues)
      .domain([1, maxCount]);

    const width  = 960;
    const height = 600;

    const svg = d3.select('#us-map')
      .attr('viewBox', `0 0 ${width} ${height}`)
      .attr('preserveAspectRatio', 'xMidYMid meet');

    const projection = d3.geoAlbersUsa()
      .scale(1300)
      .translate([width / 2, height / 2]);

    const path   = d3.geoPath().projection(projection);
    const states = topojson.feature(usTopoJson, usTopoJson.objects.states);

    svg.selectAll('path.map-state')
      .data(states.features)
      .join('path')
      .attr('class', 'map-state')
      .attr('d', path)
      .attr('fill', d => {
        const abbr  = STATE_FIPS[String(d.id).padStart(2, '0')];
        const count = abbr && countByState[abbr];
        return count ? colorScale(count) : '#e5e7eb';
      })
      .attr('stroke', '#fff')
      .attr('stroke-width', .5)
      .on('mousemove', (event, d) => {
        const abbr  = STATE_FIPS[String(d.id).padStart(2, '0')];
        const count = abbr && countByState[abbr];
        const name  = abbr ? (STATE_NAMES[abbr] || abbr) : 'Unknown';
        const rect  = svgEl.getBoundingClientRect();
        tooltip.hidden = false;
        tooltip.textContent = `${name}: ${count ? count.toLocaleString() + ' facilities' : 'No data'}`;
        tooltip.style.left = (event.clientX - rect.left + 12) + 'px';
        tooltip.style.top  = (event.clientY - rect.top  - 10) + 'px';
      })
      .on('mouseleave', () => { tooltip.hidden = true; })
      .on('click', (event, d) => {
        const abbr = STATE_FIPS[String(d.id).padStart(2, '0')];
        if (!abbr || !countByState[abbr]) return;

        svg.selectAll('path.map-state').classed('selected', false);
        d3.select(event.currentTarget).classed('selected', true);

        state.selectedMapState = abbr;
        state.mapStatePage = 1;
        loadStatePanel(abbr);
      });

    // State borders
    svg.append('path')
      .datum(topojson.mesh(usTopoJson, usTopoJson.objects.states, (a, b) => a !== b))
      .attr('fill', 'none')
      .attr('stroke', '#fff')
      .attr('stroke-width', .5)
      .attr('d', path);

  } catch (err) {
    document.getElementById('us-map').insertAdjacentHTML('afterend',
      `<p style="color:#b91c1c;padding:1rem">Map failed to load: ${err.message}</p>`);
  }
}

/* ── State panel ─────────────────────────────────────────────────────────── */
async function loadStatePanel(abbr, page = 1) {
  const panel    = document.getElementById('state-panel');
  const header   = document.getElementById('state-panel-header');
  const list     = document.getElementById('state-facilities');
  const pagDiv   = document.getElementById('state-pagination');
  const pageInfo = document.getElementById('state-page-info');

  panel.hidden = false;
  header.textContent = `Loading ${STATE_NAMES[abbr] || abbr}...`;
  list.innerHTML = '<div class="loading-state"><div class="spinner"></div></div>';
  pagDiv.hidden = true;

  try {
    const data = await apiFetch(`/api/states/${abbr}?page=${page}`);
    state.mapStateTotalPages = data.total_pages;
    state.mapStatePage = data.page;

    header.textContent = `${STATE_NAMES[abbr] || abbr} — ${data.total.toLocaleString()} facilities`;

    list.innerHTML = data.facilities.map(f => `
      <div class="state-facility-item">
        <span class="state-facility-name" data-eid="${esc(f.enrollment_id)}" data-name="${esc(f.organization_name)}">
          ${esc(f.organization_name)}
        </span>
        <div class="state-facility-meta badge-row">${badgeRow(f.owner_types)}</div>
      </div>
    `).join('');

    list.querySelectorAll('.state-facility-name').forEach(el => {
      el.addEventListener('click', () => openChainModal(el.dataset.eid, el.dataset.name));
    });

    if (data.total_pages > 1) {
      pagDiv.hidden = false;
      pageInfo.textContent = `${page} / ${data.total_pages}`;
      document.getElementById('state-prev').disabled = page <= 1;
      document.getElementById('state-next').disabled = page >= data.total_pages;
    }
  } catch (err) {
    list.innerHTML = `<p style="color:#b91c1c;font-size:.8rem">${err.message}</p>`;
  }
}

document.getElementById('state-prev').addEventListener('click', () => {
  if (state.mapStatePage > 1)
    loadStatePanel(state.selectedMapState, --state.mapStatePage);
});
document.getElementById('state-next').addEventListener('click', () => {
  if (state.mapStatePage < state.mapStateTotalPages)
    loadStatePanel(state.selectedMapState, ++state.mapStatePage);
});

/* ── Init ──────────────────────────────────────────────────────────────────── */
populateStateFilter();
