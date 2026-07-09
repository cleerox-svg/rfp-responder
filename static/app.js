/* ── NaughtRFP Frontend ───────────────────────────────────────────────────── */

const API = {
  get: (url) => fetch(url).then(r => r.json()),
  post: (url, body) => fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(r => r.json()),
  del: (url) => fetch(url, { method: 'DELETE' }).then(r => r.json()),
};

const state = {
  page: 'home',
  rfps: [],
  currentRfp: null,
  apiKeySet: false,
  processing: {},
  kbStats: { total: 0, source_rfps: 0 },
  filterCategory: 'all',
};

/* ── Toast ───────────────────────────────────────────────────────────────── */
function toast(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  el.style.cursor = 'pointer';
  el.title = 'Click to dismiss';
  el.addEventListener('click', () => el.remove());
  document.getElementById('toasts').appendChild(el);
  // Errors stay 8s, others 3.5s
  const delay = type === 'error' ? 8000 : 3500;
  setTimeout(() => el.remove(), delay);
}

/* ── Sidebar toggle ──────────────────────────────────────────────────────── */
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const app     = document.getElementById('app');
  const collapsed = sidebar.classList.toggle('collapsed');
  app.classList.toggle('sb-collapsed', collapsed);
  localStorage.setItem('sidebarCollapsed', collapsed ? '1' : '0');
}

function initSidebar() {
  if (localStorage.getItem('sidebarCollapsed') === '1') {
    document.getElementById('sidebar').classList.add('collapsed');
    document.getElementById('app').classList.add('sb-collapsed');
  }
}

/* ── Router ──────────────────────────────────────────────────────────────── */
function navigate(page, data = null) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.sidebar-btn').forEach(b => b.classList.remove('active'));

  const pageEl = document.getElementById(`page-${page}`);
  if (!pageEl) return;
  pageEl.classList.add('active');

  const btn = document.querySelector(`.sidebar-btn[data-page="${page}"]`);
  if (btn) btn.classList.add('active');

  state.page = page;

  if (page === 'home') renderHome();
  if (page === 'kb') renderKB();
  if (page === 'agents') renderAgents();
  if (page === 'demos') renderDemoLibrary();
  if (page === 'settings') { renderSettings(); loadUsage(); }
  if (page === 'discover') renderDiscover();
  // demo-detail is populated by openDemoDetail() directly — no render call needed
  if (page === 'rfp-detail' && data) renderRfpDetail(data);
}

/* ── Home Page ───────────────────────────────────────────────────────────── */
async function renderHome() {
  const grid = document.getElementById('rfp-grid');
  grid.innerHTML = '<div class="empty-state"><div class="empty-icon">⏳</div><div>Loading...</div></div>';

  const [rfps, settings] = await Promise.all([
    API.get('/api/rfps'),
    API.get('/api/settings'),
  ]);

  state.rfps = rfps;
  state.apiKeySet = settings.api_key_set;
  updateApiDot(settings.api_key_set);

  if (!rfps.length) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        <div class="empty-icon">📄</div>
        <div class="empty-title">No RFPs yet</div>
        <div class="empty-sub">Upload an RFP file above to get started</div>
      </div>`;
    return;
  }

  grid.innerHTML = rfps.map(rfp => rfpCard(rfp)).join('');
}

function parseJSON(val) {
  if (!val) return null;
  if (typeof val === 'object') return val;
  try { return JSON.parse(val); } catch { return null; }
}

function rfpCard(rfp) {
  const statusBadge = {
    pending:    '<span class="badge badge-muted">Pending</span>',
    processing: '<span class="badge badge-blue"><span class="spin">⟳</span> Processing</span>',
    complete:   '<span class="badge badge-green">✓ Complete</span>',
    error:      '<span class="badge badge-red">✗ Error</span>',
  }[rfp.status] || '';

  const fit  = rfp.fit_score  != null ? pips(rfp.fit_score, 'fit')   : '';
  const risk = rfp.risk_score != null ? pips(rfp.risk_score, 'risk')  : '';

  const rp = parseJSON(rfp.risk_profile);
  const ci = parseJSON(rfp.customer_info);

  // Customer identity line
  const customerLine = ci && ci.customer_name ? `
    <div class="rfp-customer-line">
      <span class="customer-badge">${esc(ci.customer_short || ci.customer_name)}</span>
      <span class="customer-project">${esc(ci.project_name || '')}</span>
      ${ci.industry ? `<span class="badge badge-muted" style="font-size:.65rem">${esc(ci.industry)}</span>` : ''}
    </div>` : '';

  const preRisk = rp && rfp.status === 'pending' ? `
    <div class="risk-indicator ${rp.risk_level.toLowerCase()} score-reveal" style="margin-bottom:8px;font-size:.7rem">
      ${rp.risk_level === 'High' ? '🔴' : rp.risk_level === 'Medium' ? '🟡' : '🟢'} ${rp.risk_level} Risk · ${rp.preliminary_risk_score}/5
    </div>` : '';

  const pb = rp ? rp.priority_breakdown : null;
  const priorityBar = pb ? buildPriorityBar(pb) : '';

  const flaggedBadge = rfp.flagged_count
    ? `<span style="color:var(--amber);font-weight:700" class="score-reveal">⚑ ${rfp.flagged_count} need review</span>`
    : '';

  return `
    <div class="rfp-card" onclick="openRfp(${rfp.id})">
      <div class="rfp-card-name" title="${esc(rfp.name)}">${esc(rfp.name)}</div>
      ${customerLine}
      <div class="rfp-card-date">${formatDate(rfp.created_at)} · ${statusBadge}</div>
      ${preRisk}
      ${priorityBar}
      ${rfp.fit_score != null ? `<div class="rfp-card-scores score-row" style="margin-bottom:8px">${fit}${risk}</div>` : ''}
      <div class="rfp-stats">
        <span><strong>${rfp.question_count || 0}</strong> requirements</span>
        ${rfp.answered_count ? `<span><strong>${rfp.answered_count}</strong> answered</span>` : ''}
        ${flaggedBadge}
      </div>
      <div class="rfp-card-actions" onclick="event.stopPropagation()">
        <button class="btn btn-primary btn-sm" onclick="openRfp(${rfp.id})">View</button>
        ${rfp.status === 'complete' ? `<button class="btn btn-secondary btn-sm" onclick="exportRfp(${rfp.id}, event)">Export</button>` : ''}
        ${rfp.status === 'pending' ? `<button class="btn btn-secondary btn-sm" onclick="startProcessing(${rfp.id}, '${esc(rfp.name)}', event)">▶ Run Agents</button>` : ''}
        <button class="btn btn-danger btn-sm" onclick="deleteRfp(${rfp.id}, event)">✕</button>
      </div>
    </div>`;
}

function buildPriorityBar(pb) {
  const total = (pb.Critical || 0) + (pb.High || 0) + (pb.Medium || 0) + (pb.Low || 0);
  if (!total) return '';
  const pct = (n) => `${Math.round((n / total) * 100)}%`;
  return `
    <div class="priority-bar">
      ${pb.Critical ? `<div class="priority-seg critical" style="width:${pct(pb.Critical)}"></div>` : ''}
      ${pb.High     ? `<div class="priority-seg high"     style="width:${pct(pb.High)}"></div>` : ''}
      ${pb.Medium   ? `<div class="priority-seg medium"   style="width:${pct(pb.Medium)}"></div>` : ''}
      ${pb.Low      ? `<div class="priority-seg low"      style="width:${pct(pb.Low)}"></div>` : ''}
    </div>
    <div class="priority-legend">
      ${pb.Critical ? `<span><span class="dot" style="background:var(--red)"></span>${pb.Critical} Critical</span>` : ''}
      ${pb.High     ? `<span><span class="dot" style="background:var(--amber)"></span>${pb.High} High</span>` : ''}
      ${pb.Medium   ? `<span><span class="dot" style="background:var(--okta-blue)"></span>${pb.Medium} Medium</span>` : ''}
      ${pb.Low      ? `<span><span class="dot" style="background:var(--green)"></span>${pb.Low} Low</span>` : ''}
    </div>`;
}

function pips(score, type) {
  const cls = type === 'fit' ? 'score-fit' : (score >= 4 ? 'score-risk-high' : 'score-risk');
  const label = type === 'fit' ? 'Fit' : 'Risk';
  const dots = Array.from({ length: 5 }, (_, i) =>
    `<span class="pip ${i < Math.round(score) ? 'on' : ''}"></span>`
  ).join('');
  return `
    <div class="score-pill ${cls}">
      <span>${label}</span>
      <span class="score-pip">${dots}</span>
      <span>${score}/5</span>
    </div>`;
}

/* ── Upload ──────────────────────────────────────────────────────────────── */
function initUpload() {
  const zone  = document.getElementById('upload-zone');
  const input = document.getElementById('upload-input');
  const list  = document.getElementById('upload-file-list');
  const text  = document.getElementById('upload-text');

  function showPending(files) {
    if (!files.length) return;
    list.style.display = '';
    list.innerHTML = Array.from(files).map(f => `
      <div class="file-chip">
        <span>📄</span>
        <span class="fc-name">${esc(f.name)}</span>
        <span class="fc-size">${(f.size/1024).toFixed(0)} KB</span>
      </div>`).join('');
    text.innerHTML = `<strong style="color:var(--okta-blue-lt)">${files.length} file${files.length > 1 ? 's' : ''} selected</strong> — drop more or click Upload`;
  }

  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const files = [...e.dataTransfer.files].filter(f => /\.(csv|xlsx|xls|xlsm|docx)$/i.test(f.name));
    if (files.length) { showPending(files); uploadFiles(files); }
  });

  input.addEventListener('change', () => {
    const files = [...input.files];
    if (files.length) { showPending(files); uploadFiles(files); }
    input.value = '';
  });
}

async function uploadFiles(files) {
  if (!Array.isArray(files)) files = [files];
  if (!state.apiKeySet) {
    toast('Set your API key in Settings first', 'error');
    navigate('settings');
    return;
  }

  const zone  = document.getElementById('upload-zone');
  const utext = document.getElementById('upload-text');
  zone.classList.add('uploading');
  utext.innerHTML = `<span class="spin">⟳</span> Uploading ${files.length} file${files.length > 1 ? 's' : ''}…`;

  const fd = new FormData();
  for (const f of files) fd.append('files', f);

  try {
    const res  = await fetch('/api/rfp/upload', { method: 'POST', body: fd });
    const data = await res.json();
    zone.classList.remove('uploading');
    document.getElementById('upload-file-list').style.display = 'none';
    utext.innerHTML = 'Drop one or more RFP files or <strong style="color:var(--okta-blue-lt)">click to browse</strong>';
    if (data.error) { toast(data.error, 'error'); return; }

    const rp = data.risk_profile || {};
    const docCount = (data.documents || []).length;
    toast(`"${data.name}" — ${docCount} document${docCount > 1 ? 's' : ''} uploaded${rp.risk_level ? ' · ' + rp.risk_level + ' risk' : ''}`, 'success');
    await renderHome();
    const rfp = await API.get(`/api/rfp/${data.id}`);
    state.currentRfp = rfp;
    navigate('rfp-detail', rfp);
  } catch (e) {
    zone.classList.remove('uploading');
    utext.innerHTML = 'Drop one or more RFP files or <strong style="color:var(--okta-blue-lt)">click to browse</strong>';
    toast('Upload failed: ' + e.message, 'error');
  }
}
// legacy compat
const uploadFile = f => uploadFiles([f]);

/* ── Google Doc Import ───────────────────────────────────────────────────── */
async function importGoogleDoc() {
  const input  = document.getElementById('gdoc-url-input');
  const btn    = document.getElementById('gdoc-import-btn');
  const status = document.getElementById('gdoc-import-status');

  const url = (input?.value || '').trim();
  if (!url) {
    setGdocStatus('error', 'Please paste a Google Doc URL or Doc ID.');
    return;
  }

  if (!state.apiKeySet) {
    setGdocStatus('error', 'Set your API key in Settings first.');
    navigate('settings');
    return;
  }

  btn.disabled = true;
  btn.textContent = '⟳ Importing…';
  setGdocStatus('loading', '⟳ Fetching Google Doc…');

  try {
    const res  = await fetch('/api/rfp/upload-gdoc', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ url }),
    });
    const data = await res.json();

    if (data.error) {
      setGdocStatus('error', data.error);
      return;
    }

    input.value = '';
    setGdocStatus('success', `"${data.name}" imported — open the RFP to run agents.`);
    toast(`Google Doc imported: "${data.name}"`, 'success');

    await renderHome();
    const rfp = await API.get(`/api/rfp/${data.id}`);
    state.currentRfp = rfp;
    navigate('rfp-detail', rfp);
  } catch (e) {
    setGdocStatus('error', 'Import failed: ' + e.message);
  } finally {
    btn.disabled    = false;
    btn.textContent = 'Import';
  }
}

function setGdocStatus(type, msg) {
  const el = document.getElementById('gdoc-import-status');
  if (!el) return;
  el.style.display = '';
  el.className     = `gdoc-status ${type}`;
  el.textContent   = msg;
  // Auto-hide success after 6s
  if (type === 'success') setTimeout(() => { el.style.display = 'none'; }, 6000);
}

async function startProcessing(rfpId, name, ev) {
  if (ev) ev.stopPropagation();

  // Switch to detail view with processing panel visible
  const rfp = await API.get(`/api/rfp/${rfpId}`);
  state.currentRfp = rfp;
  navigate('rfp-detail', rfp);
  scrollToProcessing();
  streamProcess(rfpId);
}

async function openRfp(rfpId) {
  const rfp = await API.get(`/api/rfp/${rfpId}`);
  state.currentRfp = rfp;
  navigate('rfp-detail', rfp);
}

async function deleteRfp(rfpId, ev) {
  ev.stopPropagation();
  if (!confirm('Delete this RFP?')) return;
  const res = await API.del(`/api/rfp/${rfpId}`);
  if (res && res.error) {
    toast('Delete failed: ' + res.error, 'error');
    return;
  }
  // Remove the card from the DOM immediately so the grid updates without
  // waiting for a full re-render round-trip
  const card = ev.target.closest('.rfp-card');
  if (card) {
    card.style.transition = 'opacity .2s ease, transform .2s ease';
    card.style.opacity = '0';
    card.style.transform = 'scale(.97)';
    setTimeout(() => card.remove(), 220);
  }
  toast('RFP deleted', 'success');
  // Await the full grid refresh so state.rfps stays accurate
  await renderHome();
}

function showRerunOptions(rfpId) {
  const panel = document.getElementById(`rerun-panel-${rfpId}`);
  if (panel) panel.style.display = panel.style.display === 'none' ? '' : 'none';
}

async function rerunRfp(rfpId, mode) {
  // Hide the options panel
  const panel = document.getElementById(`rerun-panel-${rfpId}`);
  if (panel) panel.style.display = 'none';

  const modeLabels = { all: 'all questions', flagged: 'flagged questions', unanswered: 'unanswered + flagged' };
  toast(`↺ Re-running agents on ${modeLabels[mode] || mode}…`);

  // Show the processing panel
  const pc = document.getElementById('processing-container');
  if (pc) pc.style.display = '';

  // Re-use the existing SSE processing display
  completedAgents = 0;
  const es = new EventSource(`/api/rfp/${rfpId}/rerun?mode=${mode}`);
  es.onmessage = e => {
    const ev = JSON.parse(e.data);
    handleProcessingEvent(ev, rfpId, es);
    if (ev.type === 'error') {
      toast('Re-run failed: ' + ev.message, 'error');
      es.close();
    }
  };
  es.onerror = () => es.close();
}

async function exportRfp(rfpId, ev) {
  if (ev) ev.stopPropagation();
  toast('Generating export…');
  try {
    const res = await fetch(`/api/rfp/${rfpId}/export`, { method: 'POST' });
    if (!res.ok) { const d = await res.json(); toast(d.error || 'Export failed', 'error'); return; }
    const blob = await res.blob();
    const cd = res.headers.get('Content-Disposition') || '';
    const m = cd.match(/filename="?([^"]+)"?/);
    const fname = m ? m[1] : `rfp_${rfpId}_export.xlsx`;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = fname;
    a.click();
    toast('Export downloaded', 'success');
  } catch (e) {
    toast('Export failed: ' + e.message, 'error');
  }
}

/* ── RFP Detail ──────────────────────────────────────────────────────────── */
function renderRfpDetail(rfp) {
  const el = document.getElementById('page-rfp-detail');

  const statusMap = {
    pending:    'badge-muted',
    processing: 'badge-blue',
    complete:   'badge-green',
    error:      'badge-red',
  };

  const ci = parseJSON(rfp.customer_info);
  const customerHeader = ci && ci.customer_name ? `
    <div class="customer-header-block">
      <div class="customer-header-name">${esc(ci.customer_name)}</div>
      <div class="customer-header-meta">
        ${ci.rfp_number ? `<span class="badge badge-muted">${esc(ci.rfp_number)}</span>` : ''}
        ${ci.industry   ? `<span class="badge badge-blue">${esc(ci.industry)}</span>` : ''}
        ${ci.estimated_scale ? `<span style="font-size:.75rem;color:var(--text-secondary)">📊 ${esc(ci.estimated_scale)}</span>` : ''}
        ${ci.issuing_department ? `<span style="font-size:.75rem;color:var(--text-secondary)">${esc(ci.issuing_department)}</span>` : ''}
      </div>
      ${ci.scope_summary ? `<div class="customer-scope">${esc(ci.scope_summary)}</div>` : ''}
    </div>` : '';

  el.innerHTML = `
    <div class="back-row">
      <button class="back-btn" onclick="navigate('home')">← Back</button>
    </div>
    ${customerHeader}
    <div class="rfp-detail-header">
      <div>
        <div class="rfp-detail-name">${esc(rfp.name)}</div>
        <div class="score-row" style="margin-top:6px">
          ${rfp.fit_score != null ? pips(rfp.fit_score, 'fit') : ''}
          ${rfp.risk_score != null ? pips(rfp.risk_score, 'risk') : ''}
          <span class="badge ${statusMap[rfp.status] || 'badge-muted'}">${rfp.status}</span>
          ${rfp.question_count ? `<span style="font-size:.75rem;color:var(--text-secondary)">${rfp.answered_count}/${rfp.question_count} answered · ${rfp.flagged_count || 0} flagged</span>` : ''}
        </div>
      </div>
      <div class="rfp-detail-actions">
        ${rfp.status === 'complete' ? `<button class="btn btn-secondary btn-sm" onclick="ingestToKB(${rfp.id})">→ KB</button>` : ''}
        ${rfp.status === 'complete' ? `<button class="btn btn-secondary btn-sm" onclick="generateDemoPrep(${rfp.id})">🎭 Demo Prep</button>` : ''}
        ${rfp.status === 'complete' ? `<button class="btn btn-secondary btn-sm" onclick="showRerunOptions(${rfp.id})" title="Re-run with updated knowledge base">↺ Re-run</button>` : ''}
        ${rfp.status === 'complete' ? `<button class="btn btn-primary btn-sm" onclick="exportRfp(${rfp.id})">↓ Export</button>` : ''}
        ${rfp.status === 'pending' ? `<button class="btn btn-primary" onclick="startProcessing(${rfp.id}, '${esc(rfp.name)}')">▶ Run Agents</button>` : ''}
      </div>
    </div>

    <!-- Re-run options panel (hidden until triggered) -->
    <div id="rerun-panel-${rfp.id}" style="display:none;margin-bottom:16px">
      <div class="card" style="border-color:rgba(0,125,193,.3);padding:16px 18px;animation:slideDown .2s ease">
        <div style="font-size:.8rem;font-weight:700;color:var(--okta-blue-lt);margin-bottom:10px">↺ Re-run Agents — choose scope</div>
        <div style="font-size:.78rem;color:var(--text-secondary);margin-bottom:14px;line-height:1.5">
          The agents will use the current knowledge base (${state.kbStats?.total || '640+'}  entries) including any data sources added since this RFP was last processed.
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <button class="btn btn-primary btn-sm" onclick="rerunRfp(${rfp.id},'all')">
            ↺ All Questions
            <span style="font-size:.68rem;opacity:.7;display:block;font-weight:400">Reset &amp; reprocess everything</span>
          </button>
          <button class="btn btn-secondary btn-sm" onclick="rerunRfp(${rfp.id},'flagged')">
            ⚑ Flagged Only
            <span style="font-size:.68rem;opacity:.7;display:block;font-weight:400">Re-run questions that need review</span>
          </button>
          <button class="btn btn-secondary btn-sm" onclick="rerunRfp(${rfp.id},'unanswered')">
            ○ Unanswered + Flagged
            <span style="font-size:.68rem;opacity:.7;display:block;font-weight:400">Skip already-answered questions</span>
          </button>
          <button class="btn btn-ghost btn-sm" onclick="document.getElementById('rerun-panel-${rfp.id}').style.display='none'">Cancel</button>
        </div>
      </div>
    </div>

    <div id="doc-list-container"></div>

    ${rfp.status === 'pending'    ? buildPreviewPanel(rfp)    : ''}
    ${rfp.status === 'error'     ? buildErrorPanel(rfp)     : ''}

    <div id="processing-container" style="${rfp.status === 'processing' ? '' : 'display:none'}">
      ${buildProcessingPanel(rfp.name)}
    </div>

    <div id="questions-container" style="${rfp.status === 'complete' ? '' : 'display:none'}">
      ${buildQuestionsView(rfp)}
    </div>

    <div id="demo-prep-container" style="display:none;margin-top:24px"></div>`;

  // Load document list async (multi-doc RFPs)
  loadDocumentList(rfp.id);
}

/* ── Document list ───────────────────────────────────────────────────────── */

async function loadDocumentList(rfpId) {
  const container = document.getElementById('doc-list-container');
  if (!container) return;
  const docs = await API.get(`/api/rfp/${rfpId}/documents`);
  if (!docs.length) { container.innerHTML = ''; return; }

  const docIcons = { csv: '📊', xlsx: '📗', xls: '📗', docx: '📝', pdf: '📕' };

  container.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;flex-wrap:wrap;gap:8px">
      <div style="font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--text-muted)">
        📁 ${docs.length} Document${docs.length > 1 ? 's' : ''}
      </div>
      <div style="display:flex;gap:6px">
        <label class="btn btn-secondary btn-sm" style="cursor:pointer">
          + Add Document
          <input type="file" accept=".csv,.xlsx,.xls,.xlsm,.docx" multiple style="display:none"
            onchange="addDocumentsToRfp(${rfpId}, this.files)">
        </label>
        ${docs.some(d => d.status === 'complete') ? `
        <button class="btn btn-secondary btn-sm" onclick="exportAllDocs(${rfpId})">
          ↓ Export All
        </button>` : ''}
      </div>
    </div>
    <div class="doc-list">
      ${docs.map(d => buildDocRow(d, rfpId, docIcons)).join('')}
    </div>`;
}

function buildDocRow(doc, rfpId, icons = {}) {
  const ext   = (doc.filename || '').split('.').pop().toLowerCase();
  const icon  = icons[ext] || '📄';
  const statusBadge = {
    pending:    '<span class="badge badge-muted">Pending</span>',
    processing: '<span class="badge badge-blue"><span class="spin">⟳</span> Processing</span>',
    complete:   '<span class="badge badge-green">✓ Done</span>',
    error:      '<span class="badge badge-red">✗ Error</span>',
  }[doc.status] || '';

  return `
    <div class="doc-row" id="doc-row-${doc.id}" onclick="showDocQuestions(${rfpId}, ${doc.id})">
      <div class="doc-icon">${icon}</div>
      <div class="doc-info">
        <div class="doc-name">${esc(doc.display_name)}</div>
        <div class="doc-meta">
          ${statusBadge}
          ${doc.question_count ? `<span style="margin-left:6px">${doc.answered_count}/${doc.question_count} answered${doc.flagged_count ? ` · <span style="color:var(--amber)">${doc.flagged_count} flagged</span>` : ''}</span>` : ''}
        </div>
      </div>
      <div class="doc-actions" onclick="event.stopPropagation()">
        ${doc.status === 'pending' || doc.status === 'error' ? `
        <button class="btn btn-secondary btn-sm" onclick="processDoc(${rfpId}, ${doc.id}, event)">▶ Process</button>` : ''}
        ${doc.status === 'complete' ? `
        <button class="btn btn-secondary btn-sm" onclick="exportDoc(${rfpId}, ${doc.id}, event)">↓ Export</button>` : ''}
        <button class="btn btn-danger btn-sm" onclick="deleteDoc(${rfpId}, ${doc.id}, event)">✕</button>
      </div>
    </div>`;
}

async function showDocQuestions(rfpId, docId) {
  // Highlight selected doc
  document.querySelectorAll('.doc-row').forEach(r => r.classList.remove('active'));
  const row = document.getElementById(`doc-row-${docId}`);
  if (row) row.classList.add('active');

  const rfp = await API.get(`/api/rfp/${rfpId}`);
  const docQuestions = rfp.questions.filter(q => q.document_id === docId);
  const qs = document.getElementById('questions-container');
  if (!qs) return;
  qs.style.display = '';

  // Build a minimal rfp-like object for the questions view
  const fakeRfp = {
    ...rfp,
    questions: docQuestions,
    flagged_count: docQuestions.filter(q => q.status === 'flagged').length,
    question_count: docQuestions.length,
    answered_count: docQuestions.filter(q => q.status === 'answered').length,
  };
  qs.innerHTML = buildQuestionsView(fakeRfp);
}

async function processDoc(rfpId, docId, ev) {
  ev.stopPropagation();
  const qs = await API.get(`/api/rfp/${rfpId}`);
  state.currentRfp = qs;

  // Show processing panel
  const pc = document.getElementById('processing-container');
  if (pc) { pc.style.display = ''; }
  streamProcessDoc(rfpId, docId);
}

function streamProcessDoc(rfpId, docId) {
  completedAgents = 0;
  const es = new EventSource(`/api/rfp/${rfpId}/document/${docId}/process`);
  es.onmessage = e => {
    const ev = JSON.parse(e.data);
    handleProcessingEvent(ev, rfpId, es);
    if (ev.type === 'processing_complete') {
      loadDocumentList(rfpId); // refresh doc list counts
    }
  };
  es.onerror = () => es.close();
}

async function exportDoc(rfpId, docId, ev) {
  ev.stopPropagation();
  toast('Generating export…');
  try {
    const res = await fetch(`/api/rfp/${rfpId}/document/${docId}/export`, { method: 'POST' });
    if (!res.ok) { const d = await res.json(); toast(d.error || 'Export failed', 'error'); return; }
    const blob = await res.blob();
    const cd   = res.headers.get('Content-Disposition') || '';
    const m    = cd.match(/filename[^;=\n]*=([^;\n]*)/);
    const fname = m ? m[1].replace(/['"]/g, '') : `doc_${docId}_export.xlsx`;
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = fname; a.click();
    toast('Export downloaded', 'success');
  } catch (e) { toast('Export failed: ' + e.message, 'error'); }
}

async function exportAllDocs(rfpId) {
  toast('Building ZIP export…');
  try {
    const res = await fetch(`/api/rfp/${rfpId}/export-all`, { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
    if (!res.ok) { toast('Export failed', 'error'); return; }
    const blob = await res.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `rfp_${rfpId}_export.zip`;
    a.click();
    toast('ZIP downloaded', 'success');
  } catch (e) { toast('Export failed: ' + e.message, 'error'); }
}

async function addDocumentsToRfp(rfpId, fileList) {
  const files = [...fileList];
  if (!files.length) return;
  toast(`Adding ${files.length} document${files.length > 1 ? 's' : ''}…`);
  const fd = new FormData();
  for (const f of files) fd.append('files', f);
  fd.append('rfp_id', rfpId);
  const res  = await fetch('/api/rfp/upload', { method: 'POST', body: fd });
  const data = await res.json();
  if (data.error) { toast(data.error, 'error'); return; }
  toast(`Added ${(data.documents || []).length} document(s)`, 'success');
  loadDocumentList(rfpId);
}

async function deleteDoc(rfpId, docId, ev) {
  ev.stopPropagation();
  if (!confirm('Delete this document and all its questions?')) return;
  await API.del(`/api/rfp/${rfpId}/document/${docId}`);
  toast('Document deleted');
  loadDocumentList(rfpId);
  // Re-render questions area
  const rfp = await API.get(`/api/rfp/${rfpId}`);
  state.currentRfp = rfp;
  const qs = document.getElementById('questions-container');
  if (qs && rfp.status === 'complete') qs.innerHTML = buildQuestionsView(rfp);
}

function buildPreviewPanel(rfp) {
  const rp = rfp.risk_profile ? (typeof rfp.risk_profile === 'string' ? JSON.parse(rfp.risk_profile) : rfp.risk_profile) : null;
  const up = rfp.upload_preview ? (typeof rfp.upload_preview === 'string' ? JSON.parse(rfp.upload_preview) : rfp.upload_preview) : null;

  if (!rp && !up) return '';

  const pb = (rp || up || {}).priority_breakdown || {};
  const cats = (up || {}).categories || {};
  const catEntries = Object.entries(cats).sort((a, b) => b[1] - a[1]);

  const riskLevel = (rp || {}).risk_level || 'Unknown';
  const riskScore = (rp || {}).preliminary_risk_score || 0;
  const keywords  = (rp || {}).risky_keywords || [];

  return `
    <div class="preview-panel">
      <div class="preview-panel-title">📋 RFP Preview — Ready to Process</div>
      <div class="preview-stats">
        <div class="preview-stat">
          <div class="preview-stat-num">${(up || {}).valid_requirements || rfp.question_count || '—'}</div>
          <div class="preview-stat-label">Requirements</div>
        </div>
        <div class="preview-stat">
          <div class="preview-stat-num">${Object.keys(cats).length || '—'}</div>
          <div class="preview-stat-label">Categories</div>
        </div>
        <div class="preview-stat">
          <div class="preview-stat-num" style="color:${riskLevel==='High'?'var(--red)':riskLevel==='Medium'?'var(--amber)':'var(--green)'}">${riskScore}</div>
          <div class="preview-stat-label">Risk Score /5</div>
        </div>
        <div class="preview-stat">
          <div class="preview-stat-num" style="color:var(--red)">${pb.Critical || 0}</div>
          <div class="preview-stat-label">Critical Items</div>
        </div>
      </div>

      ${buildPriorityBar(pb)}

      ${catEntries.length ? `
      <div style="margin-top:12px;font-size:.7rem;color:var(--text-muted);margin-bottom:6px;font-weight:600;text-transform:uppercase;letter-spacing:.4px">Categories Detected</div>
      <div class="category-chips">
        ${catEntries.map(([cat, n], i) => `<span class="category-chip" style="animation-delay:${i * 0.04}s">${esc(cat)} <strong style="color:var(--text-primary)">${n}</strong></span>`).join('')}
      </div>` : ''}

      ${keywords.length ? `
      <div style="margin-top:12px;font-size:.7rem;color:var(--text-muted);margin-bottom:6px;font-weight:600;text-transform:uppercase;letter-spacing:.4px">Risk Signals Detected</div>
      <div class="category-chips">
        ${keywords.map(k => `<span class="category-chip" style="border-color:rgba(224,49,49,.3);color:var(--red)">${esc(k)}</span>`).join('')}
      </div>` : ''}

      <div style="margin-top:18px">
        <button class="btn btn-primary" onclick="startProcessing(${rfp.id}, '${esc(rfp.name)}')">▶ Run Agents Now</button>
      </div>
    </div>`;
}

function buildErrorPanel(rfp) {
  const err = rfp.last_error || 'An unknown error occurred during agent processing.';
  const isAuthError = err.toLowerCase().includes('auth') || err.toLowerCase().includes('api key') || err.toLowerCase().includes('401') || err.toLowerCase().includes('unauthorized');
  const isNoKey = err.toLowerCase().includes('not configured');

  return `
    <div class="preview-panel" style="border-color:rgba(224,49,49,.35);background:rgba(224,49,49,.05)">
      <div class="preview-panel-title" style="color:var(--red)">✗ Processing Failed</div>
      <div style="font-size:.8125rem;color:var(--text-secondary);line-height:1.6;margin-bottom:16px;padding:12px;background:rgba(0,0,0,.2);border-radius:var(--radius);font-family:monospace;word-break:break-word">${esc(err)}</div>
      ${isAuthError || isNoKey ? `
      <div style="font-size:.8rem;color:var(--amber);margin-bottom:14px">
        💡 This looks like an API key issue. Check your key in <a href="#" onclick="navigate('settings')" style="color:var(--okta-blue-lt)">Settings</a>.
      </div>` : ''}
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn btn-primary" onclick="startProcessing(${rfp.id}, '${esc(rfp.name)}')">↺ Retry Agents</button>
        <button class="btn btn-secondary" onclick="navigate('settings')">⚙ Check Settings</button>
      </div>
    </div>`;
}

function buildProcessingPanel(rfpName) {
  const agents = [
    { id: 'customer', icon: '🏢', name: 'Customer Agent',  role: 'Identifying who issued this RFP' },
    { id: 'parser',   icon: '🗂', name: 'Parser Agent',    role: 'Detecting structure' },
    { id: 'analyzer', icon: '🔍', name: 'Analysis Agent',  role: 'Categorizing requirements' },
    { id: 'research', icon: '📚', name: 'Research Agent',  role: 'Searching knowledge base' },
    { id: 'answer',   icon: '✍️',  name: 'Answer Agent',   role: 'Drafting responses' },
    { id: 'scoring',  icon: '⭐', name: 'Scoring Agent',   role: 'Fit & risk scoring' },
    { id: 'review',   icon: '✅', name: 'Review Agent',    role: 'Quality assurance' },
  ];

  return `
    <div class="processing-panel" style="margin-bottom:20px">
      <div class="processing-header">
        <div class="processing-title">🤖 Agent Pipeline — <span style="color:var(--text-secondary)">${esc(rfpName)}</span></div>
        <div id="overall-progress" style="font-size:.75rem;color:var(--text-muted)">Starting…</div>
      </div>
      <div class="progress-bar-wrap"><div class="progress-bar-fill" id="progress-bar" style="width:0%"></div></div>
      <div class="agent-list" id="agent-list">
        ${agents.map(a => `
          <div class="agent-row waiting" id="agent-row-${a.id}" data-agent="${a.name}">
            <div class="agent-icon">${a.icon}</div>
            <div class="agent-info">
              <div class="agent-name">${a.name}</div>
              <div class="agent-msg" id="agent-msg-${a.id}">${a.role}</div>
            </div>
            <div class="agent-status-icon" id="agent-status-${a.id}">○</div>
          </div>`).join('')}
      </div>
      <div class="activity-feed" id="activity-feed"></div>
    </div>`;
}

const AGENT_ROW_MAP = {
  'Customer Agent': 'customer',
  'Parser Agent':   'parser',
  'Analysis Agent': 'analyzer',
  'Research Agent': 'research',
  'Answer Agent':   'answer',
  'Scoring Agent':  'scoring',
  'Review Agent':   'review',
};

let completedAgents = 0;

function streamProcess(rfpId) {
  completedAgents = 0;
  const es = new EventSource(`/api/rfp/${rfpId}/process`);

  es.onmessage = (e) => {
    const ev = JSON.parse(e.data);
    handleProcessingEvent(ev, rfpId, es);
  };

  es.onerror = () => {
    toast('Connection to agent stream lost', 'error');
    es.close();
  };
}

function handleProcessingEvent(ev, rfpId, es) {
  const feed = document.getElementById('activity-feed');
  const ts = new Date().toLocaleTimeString('en', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });

  if (feed && ev.message) {
    const item = document.createElement('div');
    item.className = 'activity-item';
    item.innerHTML = `<span class="ts">${ts}</span><span class="agent-tag">${esc(ev.agent || 'System')}</span>  ${esc(ev.message)}`;
    feed.appendChild(item);
    feed.scrollTop = feed.scrollHeight;
  }

  const agentKey = AGENT_ROW_MAP[ev.agent];

  if (ev.type === 'agent_start' && agentKey) {
    const row = document.getElementById(`agent-row-${agentKey}`);
    const msg = document.getElementById(`agent-msg-${agentKey}`);
    const st  = document.getElementById(`agent-status-${agentKey}`);
    if (row) { row.className = 'agent-row running'; }
    if (msg) msg.textContent = ev.message;
    if (st)  st.innerHTML = '<span class="spin">⟳</span>';
  }

  if ((ev.type === 'agent_complete' || ev.type === 'agent_progress') && agentKey) {
    const msg = document.getElementById(`agent-msg-${agentKey}`);
    if (msg) msg.textContent = ev.message;
  }

  if (ev.type === 'agent_complete' && agentKey) {
    completedAgents++;
    const row = document.getElementById(`agent-row-${agentKey}`);
    const st  = document.getElementById(`agent-status-${agentKey}`);
    if (row) row.className = 'agent-row complete';
    if (st)  st.textContent = '✓';
    updateProgress(completedAgents / 7);
  }

  if (ev.type === 'processing_complete') {
    updateProgress(1);
    document.getElementById('overall-progress').textContent = '✓ Complete';
    es.close();

    setTimeout(async () => {
      const rfp = await API.get(`/api/rfp/${rfpId}`);
      state.currentRfp = rfp;
      renderRfpDetail(rfp);
      scrollToQuestions();
    }, 800);
  }

  if (ev.type === 'error') {
    toast('Agent error: ' + ev.message, 'error');
    es.close();
    // Re-render the detail view to show the error state with retry
    setTimeout(async () => {
      const rfp = await API.get(`/api/rfp/${rfpId}`);
      state.currentRfp = rfp;
      renderRfpDetail(rfp);
    }, 400);
  }
}

function updateProgress(fraction) {
  const bar = document.getElementById('progress-bar');
  if (bar) bar.style.width = `${Math.round(fraction * 100)}%`;
  const label = document.getElementById('overall-progress');
  if (label) label.textContent = `${Math.round(fraction * 100)}% complete`;
}

function scrollToProcessing() {
  document.getElementById('processing-container')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
function scrollToQuestions() {
  document.getElementById('questions-container')?.scrollIntoView({ behavior: 'smooth' });
}

/* ── Questions View ──────────────────────────────────────────────────────── */
function buildQuestionsView(rfp) {
  const questions = rfp.questions || [];
  const flagged = questions.filter(q => q.status === 'flagged');
  const categories = ['all', ...new Set(questions.map(q => q.category).filter(Boolean))];

  const filterButtons = categories.map(c =>
    `<button class="filter-btn ${c === 'all' ? 'active' : ''}" onclick="filterQuestions('${esc(c)}')">${c === 'all' ? 'All' : esc(c)} ${c === 'all' ? `(${questions.length})` : `(${questions.filter(q => q.category === c).length})`}</button>`
  ).join('');

  const flaggedBtn = flagged.length
    ? `<button class="filter-btn" onclick="filterQuestions('flagged')" style="border-color:rgba(245,166,35,.5);color:var(--amber)">⚑ Needs Review (${flagged.length})</button>`
    : '';

  const reviewBanner = flagged.length ? `
    <div class="review-banner ${flagged.length >= 5 ? 'risk-pulse' : ''}" onclick="filterQuestions('flagged')">
      <div class="review-banner-icon">⚑</div>
      <div class="review-banner-text">
        <div class="review-banner-title">Human Review Required</div>
        <div class="review-banner-sub">${flagged.length} requirement${flagged.length > 1 ? 's' : ''} could not be answered with sufficient confidence and must be reviewed before submission. Click to filter.</div>
      </div>
      <div class="review-banner-count">${flagged.length} to review</div>
    </div>` : '';

  return `
    ${reviewBanner}
    <div class="question-filters">${filterButtons}${flaggedBtn}</div>
    <div id="questions-list">
      ${questions.map(q => questionCard(q, rfp.id)).join('')}
    </div>`;
}

function filterQuestions(category) {
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  state.filterCategory = category;

  document.querySelectorAll('.question-card').forEach(card => {
    if (category === 'all') { card.style.display = ''; return; }
    if (category === 'flagged') { card.style.display = card.dataset.status === 'flagged' ? '' : 'none'; return; }
    card.style.display = card.dataset.category === category ? '' : 'none';
  });
}

function questionCard(q, rfpId) {
  rfpId = rfpId || (state.currentRfp && state.currentRfp.id);
  const sources = JSON.parse(q.sources || '[]');
  const products = JSON.parse(q.okta_products || '[]');
  const statusBadge = {
    answered: `<span class="badge badge-green">✓ Answered</span>`,
    flagged:  `<span class="badge badge-amber">⚑ Review</span>`,
    pending:  `<span class="badge badge-muted">Pending</span>`,
  }[q.status] || '';

  const rcBadge = q.response_code
    ? `<span class="badge badge-blue">${q.response_code}</span>`
    : '';

  const confidencePct = Math.round((q.confidence || 0) * 100);
  const confColor = confidencePct >= 80 ? 'var(--green)' : confidencePct >= 60 ? 'var(--amber)' : 'var(--red)';

  return `
    <div class="question-card ${q.status}" data-status="${q.status}" data-category="${esc(q.category || '')}">
      <div class="q-header" onclick="toggleQuestion(this)" style="${q.status === 'flagged' ? 'background:rgba(245,166,35,.04)' : ''}">
        <div class="q-header-main">
          <div class="q-meta">
            ${q.category ? `<span class="badge badge-blue">${esc(q.category)}</span>` : ''}
            ${statusBadge} ${rcBadge}
            ${products.length ? products.map(p => `<span class="badge badge-teal">${esc(p)}</span>`).join('') : ''}
            ${pips(q.fit_score, 'fit')} ${pips(q.risk_score, 'risk')}
          </div>
          <div class="q-text collapsed">${esc(q.question_text)}</div>
        </div>
        <button class="q-expand-btn">▾</button>
      </div>
      ${q.answer || q.review_reason ? `
      <div class="q-body ${q.status === 'flagged' ? 'open' : ''}">
        ${q.answer ? `
          <div class="q-answer-label">Okta Response</div>
          <div class="q-answer-text">${esc(q.answer)}</div>
          ${sources.length ? `
          <div class="q-sources">
            <span style="font-size:.7rem;color:var(--text-muted);margin-right:4px">Sources:</span>
            ${sources.map(s => `<span class="q-source-tag">${esc(s)}</span>`).join('')}
          </div>` : ''}
          <div class="q-confidence">
            <span>Confidence</span>
            <div class="confidence-bar">
              <div class="confidence-fill" style="width:${confidencePct}%;background:${confColor}"></div>
            </div>
            <span style="color:${confColor}">${confidencePct}%</span>
          </div>` : ''}
        ${q.review_reason ? `
          <div class="q-answer-label" style="color:var(--amber);margin-bottom:6px">⚑ Why AI flagged this</div>
          <div class="q-answer-text" style="color:var(--text-muted);font-style:italic;margin-bottom:0">${esc(q.review_reason)}</div>` : ''}
      ${q.status === 'flagged' ? buildEditForm(q, rfpId) : ''}
      </div>` : ''}
    </div>`;
}

function buildEditForm(q, rfpId) {
  const codes = [
    { code: 'F',  label: 'F — Full' },
    { code: 'P',  label: 'P — Partial' },
    { code: 'C',  label: 'C — Custom' },
    { code: 'NE', label: 'NE — Planned' },
    { code: 'N',  label: 'N — Not Available' },
  ];
  const rcBtns = codes.map(c =>
    `<button class="rc-btn ${q.response_code === c.code ? 'selected' : ''}"
       onclick="selectRC(this, '${c.code}', ${q.id}, ${rfpId})">${c.label}</button>`
  ).join('');

  return `
    <div class="q-edit-form" id="edit-form-${q.id}">
      <div class="q-edit-label">Your Response Code</div>
      <div class="q-response-code" id="rc-${q.id}">${rcBtns}</div>

      <div class="q-edit-label">Vendor Response</div>
      <textarea class="q-edit-textarea" id="answer-${q.id}"
        placeholder="Optionally edit the response — or leave as-is and click Approve…">${esc(q.answer || '')}</textarea>

      <div class="q-edit-actions">
        <button class="btn btn-primary btn-sm" onclick="approveQuestion(${q.id}, ${rfpId})">
          ✓ Approve as-is
        </button>
        <button class="btn btn-secondary btn-sm" id="rerun-btn-${q.id}" onclick="rerunQuestion(${q.id}, ${rfpId})">
          ↺ Re-run AI
        </button>
        <span id="rerun-status-${q.id}" style="font-size:.72rem;color:var(--text-muted)"></span>
      </div>
    </div>`;
}

function selectRC(btn, code, qId, rfpId) {
  // Highlight selected button in the row
  const row = document.getElementById(`rc-${qId}`);
  if (row) row.querySelectorAll('.rc-btn').forEach(b => b.classList.remove('selected'));
  btn.classList.add('selected');
  btn.dataset.code = code;
}

function _getSelectedRC(qId) {
  const row = document.getElementById(`rc-${qId}`);
  if (!row) return null;
  const sel = row.querySelector('.rc-btn.selected');
  return sel ? sel.textContent.split(' — ')[0].trim() : null;
}

async function approveQuestion(qId, rfpId) {
  const rc     = _getSelectedRC(qId);
  const answer = (document.getElementById(`answer-${qId}`)?.value || '').trim();

  if (!rc) { toast('Please select a response code (F / P / C / NE / N)', 'error'); return; }

  const res = await fetch(`/api/rfp/${rfpId}/question/${qId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answer, response_code: rc, status: 'answered',
                           needs_review: 0, review_reason: null, confidence: 1.0 })
  });
  const data = await res.json();
  if (!data.success) { toast('Save failed', 'error'); return; }

  toast('✓ Response approved', 'success');

  // Refresh the RFP detail to show updated state
  const rfp = await API.get(`/api/rfp/${rfpId}`);
  state.currentRfp = rfp;
  const qs = document.getElementById('questions-container');
  if (qs) qs.innerHTML = buildQuestionsView(rfp);
  // Re-render header scores
  const rfpEl = document.getElementById('page-rfp-detail');
  if (rfpEl) {
    const scoreRow = rfpEl.querySelector('.score-row');
    if (scoreRow && rfp.fit_score != null) {
      scoreRow.innerHTML = `
        ${pips(rfp.fit_score, 'fit')} ${pips(rfp.risk_score, 'risk')}
        <span class="badge badge-green">✓ complete</span>
        <span style="font-size:.75rem;color:var(--text-secondary)">${rfp.answered_count}/${rfp.question_count} answered · ${rfp.flagged_count || 0} flagged</span>`;
    }
  }
}

async function rerunQuestion(qId, rfpId) {
  const btn    = document.getElementById(`rerun-btn-${qId}`);
  const status = document.getElementById(`rerun-status-${qId}`);
  if (btn) { btn.disabled = true; btn.textContent = '⟳ Running…'; }
  if (status) status.textContent = 'Agent processing…';

  const es = new EventSource(`/api/rfp/${rfpId}/question/${qId}/rerun`);
  es.onmessage = async e => {
    const ev = JSON.parse(e.data);

    if (ev.type === 'rerun_complete') {
      es.close();
      if (btn) { btn.disabled = false; btn.textContent = '↺ Re-run AI'; }
      const q = ev.question;
      if (!q) { if (status) status.textContent = 'No result'; return; }

      if (q.status === 'answered') {
        toast('AI generated a response — review and approve', 'success');
        // Populate the edit form with the new answer
        const ta = document.getElementById(`answer-${qId}`);
        if (ta) ta.value = q.answer || '';
        // Select the response code
        const rcRow = document.getElementById(`rc-${qId}`);
        if (rcRow && q.response_code) {
          rcRow.querySelectorAll('.rc-btn').forEach(b => {
            b.classList.toggle('selected', b.textContent.startsWith(q.response_code));
          });
        }
        if (status) status.textContent = `✓ Confidence: ${Math.round((q.confidence || 0) * 100)}%`;
      } else {
        if (status) status.textContent = `⚑ Still flagged: ${(q.review_reason || '').slice(0, 60)}`;
        if (btn) btn.disabled = false;
      }
    }

    if (ev.type === 'error') {
      es.close();
      toast('Re-run failed: ' + ev.message, 'error');
      if (btn) { btn.disabled = false; btn.textContent = '↺ Re-run AI'; }
      if (status) status.textContent = '';
    }
  };
  es.onerror = () => {
    es.close();
    if (btn) { btn.disabled = false; btn.textContent = '↺ Re-run AI'; }
  };
}

function toggleQuestion(header) {
  const card = header.closest('.question-card');
  const body = card.querySelector('.q-body');
  const text = card.querySelector('.q-text');
  const btn  = card.querySelector('.q-expand-btn');
  if (!body) return;
  const open = body.classList.toggle('open');
  text.classList.toggle('collapsed', !open);
  btn.textContent = open ? '▴' : '▾';
}

/* ── Demo Prep ───────────────────────────────────────────────────────────── */

async function generateDemoPrep(rfpId) {
  const container = document.getElementById('demo-prep-container');
  if (!container) return;
  container.style.display = '';
  container.innerHTML = `
    <div class="processing-panel">
      <div class="processing-header">
        <div class="processing-title">🎭 Demo Prep Agent — building your demo plan…</div>
      </div>
      <div class="progress-bar-wrap"><div class="progress-bar-fill" id="demo-progress" style="width:10%"></div></div>
      <div class="activity-feed" id="demo-feed"></div>
    </div>`;
  container.scrollIntoView({ behavior: 'smooth', block: 'start' });

  const es = new EventSource(`/api/rfp/${rfpId}/demo-prep`);
  let pct = 10;
  es.onmessage = e => {
    const ev = JSON.parse(e.data);
    const feed = document.getElementById('demo-feed');
    if (feed && ev.message) {
      const item = document.createElement('div');
      item.className = 'activity-item';
      item.innerHTML = `<span class="agent-tag">🎭 Demo Prep</span>  ${esc(ev.message)}`;
      feed.appendChild(item);
      feed.scrollTop = feed.scrollHeight;
    }
    if (ev.type === 'agent_start')    { pct = 30; }
    if (ev.type === 'agent_complete') { pct = 85; }
    const bar = document.getElementById('demo-progress');
    if (bar) bar.style.width = pct + '%';

    if (ev.type === 'demo_ready' && ev.data) {
      if (bar) bar.style.width = '100%';
      es.close();
      setTimeout(() => renderDemoPlan(rfpId, ev.data), 400);
    }
    if (ev.type === 'error') {
      toast('Demo prep failed: ' + ev.message, 'error');
      es.close();
    }
  };
  es.onerror = () => es.close();
}

function renderDemoPlan(rfpId, plan) {
  // Called from RFP detail view — target the rfp-scoped container
  const container = document.getElementById('demo-prep-container');
  if (!container) return;
  renderDemoPlanInto(container, rfpId, plan);
}

function renderDemoPlanInto(container, rfpId, plan) {
  if (!container) return;

  const sections   = JSON.parse(plan.sections || '[]');
  const notes      = JSON.parse(plan.notes || '{}');
  const questions  = notes.questions_to_address || [];
  const envNote    = notes.recommended_demo_env || '';
  const apex       = notes.apex_brief || {};
  const discovery  = notes.discovery_questions || [];
  const confirmed  = plan.status === 'confirmed';

  // ── APEX Brief card ────────────────────────────────────────────────────────
  const apexHtml = apex.mantra ? `
    <div class="apex-brief-card" style="margin-bottom:20px">
      <div class="apex-header">
        <div class="apex-label">⚡ APEX Brief — Command of the Message</div>
        <span style="font-size:.7rem;color:var(--text-muted)">Powered by APEX / CoM</span>
      </div>

      <div class="apex-mantra">"${esc(apex.mantra)}"</div>

      <div class="apex-grid">
        <div class="apex-block apex-before">
          <div class="apex-block-label">Before Scenario</div>
          <div class="apex-block-text">${esc(apex.before_scenario || '')}</div>
          ${(apex.negative_consequences || []).length ? `
          <div class="apex-block-label" style="margin-top:8px">Negative Consequences</div>
          ${(apex.negative_consequences || []).map(nc => `<div class="apex-nc">✗ ${esc(nc)}</div>`).join('')}` : ''}
        </div>
        <div class="apex-arrow">→</div>
        <div class="apex-block apex-after">
          <div class="apex-block-label">After Scenario</div>
          <div class="apex-block-text">${esc(apex.after_scenario || '')}</div>
          ${(apex.positive_business_outcomes || []).length ? `
          <div class="apex-block-label" style="margin-top:8px">Positive Business Outcomes</div>
          ${(apex.positive_business_outcomes || []).map(pbo => `<div class="apex-pbo">✓ ${esc(pbo)}</div>`).join('')}` : ''}
        </div>
      </div>

      ${(apex.required_capabilities || []).length ? `
      <div style="margin-top:12px">
        <div class="apex-block-label">Required Capabilities</div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:5px">
          ${(apex.required_capabilities || []).map(rc => `<span class="badge badge-blue">${esc(rc)}</span>`).join('')}
        </div>
      </div>` : ''}

      ${(apex.unique_differentiators || []).length ? `
      <div style="margin-top:10px">
        <div class="apex-block-label">Okta Differentiators</div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:5px">
          ${(apex.unique_differentiators || []).map(d => `<span class="badge badge-purple">${esc(d)}</span>`).join('')}
        </div>
      </div>` : ''}
    </div>` : '';

  container.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:8px">
      <div>
        <div style="font-size:1.1rem;font-weight:700">🎭 Demo Plan</div>
        <div style="font-size:.8rem;color:var(--text-secondary);margin-top:3px">${esc(plan.summary || '')}</div>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
        <span class="badge ${confirmed ? 'badge-green' : 'badge-muted'}">${confirmed ? '✓ Confirmed' : 'Draft'}</span>
        <span style="font-size:.75rem;color:var(--text-muted)">~${plan.total_minutes} min</span>
        ${!confirmed ? `<button class="btn btn-primary btn-sm" onclick="confirmDemoPlan(${rfpId})">✓ Confirm This Plan</button>` : ''}
      </div>
    </div>

    ${apexHtml}

    ${envNote ? `
    <div class="demo-env-box" style="margin-bottom:18px">
      <strong style="color:var(--okta-blue-lt);font-size:.75rem;text-transform:uppercase;letter-spacing:.4px">Demo Environment Setup</strong><br>
      ${esc(envNote)}
    </div>` : ''}

    <div class="demo-timeline">
      ${sections.map((s, i) => demoPlanSection(s, i)).join('')}
    </div>

    ${questions.length ? `
    <div class="card" style="margin-top:16px;border-color:rgba(245,166,35,.3)">
      <div style="font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.4px;color:var(--amber);margin-bottom:10px">⚑ Prepare to Address</div>
      ${questions.map(q => `<div style="font-size:.8rem;color:var(--text-secondary);padding:4px 0;border-bottom:1px solid var(--border)">${esc(q)}</div>`).join('')}
    </div>` : ''}

    ${discovery.length ? `
    <div class="card" style="margin-top:12px;border-color:rgba(0,125,193,.25)">
      <div style="font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.4px;color:var(--okta-blue-lt);margin-bottom:10px">🔍 Pre-Demo Discovery Questions</div>
      ${discovery.map((q, i) => `<div style="font-size:.8rem;color:var(--text-secondary);padding:5px 0;border-bottom:1px solid var(--border);display:flex;gap:8px"><span style="color:var(--okta-blue-lt);font-weight:700;flex-shrink:0">${i+1}.</span>${esc(q)}</div>`).join('')}
    </div>` : ''}`;
}

function demoPlanSection(s, i) {
  const priorityColor = { critical: 'var(--red)', high: 'var(--amber)', medium: 'var(--green)' }[s.priority] || 'var(--okta-blue)';
  const steps = (s.demo_steps || []).map((step, j) => `
    <div class="demo-step">
      <div class="demo-step-num">${j+1}</div>
      <div>${esc(step)}</div>
    </div>`).join('');
  // Use CoM talking points if available, fall back to legacy talking_points
  const tpList = s.com_talking_points || s.talking_points || [];
  const tps = tpList.map(tp => `
    <div class="demo-tp">💬 ${esc(tp)}</div>`).join('');
  const diffs = (s.differentiators || []).map(d => `
    <span class="badge badge-blue" style="font-size:.68rem">${esc(d)}</span>`).join(' ');
  const pboTag = s.pbo_addressed ? `<span class="badge badge-green" style="font-size:.65rem">PBO: ${esc(s.pbo_addressed)}</span>` : '';
  const rcTag  = s.required_capability ? `<span class="badge badge-purple" style="font-size:.65rem">RC: ${esc(s.required_capability)}</span>` : '';
  const products = (s.okta_products || []).map(p =>
    `<span class="badge badge-teal">${esc(p)}</span>`).join(' ');

  return `
    <div class="demo-section ${s.priority || ''}">
      <div class="demo-card">
        <div class="demo-card-header" onclick="toggleDemo(this)">
          <div class="demo-section-num" style="background:${priorityColor}22;color:${priorityColor}">${i+1}</div>
          <div class="demo-card-title">${esc(s.title)}</div>
          <div class="demo-card-meta">
            ${products}
            ${pboTag} ${rcTag}
            <span class="demo-time">⏱ ${s.estimated_minutes} min</span>
            <span style="color:var(--text-muted);font-size:.875rem">▾</span>
          </div>
        </div>
        <div class="demo-card-body">
          ${s.demo_scenario ? `
          <div class="demo-subsection">
            <div class="demo-subsection-label">Scenario</div>
            <div style="font-size:.8rem;color:var(--text-secondary);font-style:italic">${esc(s.demo_scenario)}</div>
          </div>` : ''}
          ${steps ? `<div class="demo-subsection"><div class="demo-subsection-label">Demo Steps</div>${steps}</div>` : ''}
          ${tps ? `<div class="demo-subsection"><div class="demo-subsection-label">Talking Points</div>${tps}</div>` : ''}
          ${diffs ? `<div class="demo-subsection"><div class="demo-subsection-label">Differentiators</div><div style="display:flex;gap:6px;flex-wrap:wrap">${diffs}</div></div>` : ''}
        </div>
      </div>
    </div>`;
}

function toggleDemo(header) {
  const body = header.nextElementSibling;
  const btn  = header.querySelector('span:last-child');
  const open = body.classList.toggle('open');
  if (btn) btn.textContent = open ? '▴' : '▾';
}

async function confirmDemoPlan(rfpId) {
  const res = await API.post(`/api/rfp/${rfpId}/demo-plan/confirm`, {});
  if (res.success) {
    toast('Demo plan confirmed — added to Demo Library ✓', 'success');
    const plan = await API.get(`/api/rfp/${rfpId}/demo-plan`);
    // Re-render in whichever container is currently visible
    const libInner = document.getElementById('demo-lib-inner');
    const rfpContainer = document.getElementById('demo-prep-container');
    if (libInner) renderDemoPlanInto(libInner, rfpId, plan);
    else if (rfpContainer) renderDemoPlanInto(rfpContainer, rfpId, plan);
  }
}

/* ── Demo Library ────────────────────────────────────────────────────────── */

async function renderDemoLibrary() {
  const grid = document.getElementById('demos-grid');
  grid.innerHTML = '<div class="empty-state" style="grid-column:1/-1"><div class="empty-icon">⏳</div><div>Loading…</div></div>';
  const demos = await API.get('/api/demos');
  if (!demos.length) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        <div class="empty-icon">🎭</div>
        <div class="empty-title">No confirmed demo plans yet</div>
        <div class="empty-sub">Open a completed RFP → click 🎭 Demo Prep → generate and confirm a plan</div>
      </div>`;
    return;
  }
  grid.innerHTML = demos.map(d => demoLibCard(d)).join('');
}

function demoLibCard(d) {
  const ci = parseJSON(d.customer_info);
  const customer = ci ? ci.customer_name : d.rfp_name;
  const industry = ci ? ci.industry : '';
  const sections = JSON.parse(d.sections || '[]');
  const confirmed = d.confirmed_at ? formatDate(JSON.parse(d.confirmed_at || '{}').ts || d.confirmed_at) : '';

  return `
    <div class="demo-lib-card" onclick="openDemoDetail(${d.id}, ${d.rfp_id})">
      <div class="demo-lib-customer">${esc(customer)}</div>
      <div class="demo-lib-rfp">${esc(d.rfp_name)} · Confirmed ${confirmed}</div>
      <div class="demo-lib-meta">
        ${industry ? `<span class="badge badge-blue">${esc(industry)}</span>` : ''}
        <span style="font-size:.75rem;color:var(--text-muted)">${sections.length} sections · ~${d.total_minutes} min</span>
        <span class="badge badge-green" style="margin-left:auto">✓ Ready</span>
      </div>
      <div style="font-size:.75rem;color:var(--text-secondary);margin-top:8px;line-height:1.5">${esc((d.summary || '').slice(0, 120))}${(d.summary || '').length > 120 ? '…' : ''}</div>
    </div>`;
}

async function openDemoDetail(planId, rfpId) {
  const plan = await API.get(`/api/rfp/${rfpId}/demo-plan`);
  navigate('demo-detail');
  const el = document.getElementById('page-demo-detail');
  el.innerHTML = `
    <div class="back-row">
      <button class="back-btn" onclick="navigate('demos')">← Demo Library</button>
    </div>
    <div id="demo-lib-inner"></div>`;
  renderDemoPlanInto(document.getElementById('demo-lib-inner'), rfpId, plan);
}

/* ── KB Page ─────────────────────────────────────────────────────────────── */

async function uploadToKB(file) {
  const progressEl = document.getElementById('kb-upload-progress');
  const resultEl   = document.getElementById('kb-upload-result');
  if (!progressEl) return;

  progressEl.innerHTML = `<div class="agent-log"><span class="spin">⟳</span> Uploading ${esc(file.name)}…</div>`;
  progressEl.style.display = 'block';
  if (resultEl) resultEl.textContent = '';

  const fd = new FormData();
  fd.append('file', file);

  try {
    const resp = await fetch('/api/kb/upload-document', { method: 'POST', body: fd });

    if (!resp.ok) {
      let errMsg = 'Upload failed';
      try { const err = await resp.json(); errMsg = err.error || errMsg; } catch { /* ignore */ }
      progressEl.innerHTML = `<div class="agent-log error">✗ ${esc(errMsg)}</div>`;
      return;
    }

    // Read SSE stream line by line
    const reader  = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE events are separated by double newlines
      const chunks = buffer.split('\n\n');
      buffer = chunks.pop(); // last chunk may be incomplete

      for (const chunk of chunks) {
        const line = chunk.trim();
        if (!line.startsWith('data: ')) continue;
        let ev;
        try { ev = JSON.parse(line.slice(6)); } catch { continue; }

        if (ev.type === 'agent_start' || ev.type === 'agent_progress') {
          progressEl.innerHTML += `<div class="agent-log">${esc(ev.message)}</div>`;
          progressEl.scrollTop = progressEl.scrollHeight;
        }
        if (ev.type === 'agent_complete') {
          const d = ev.data || {};
          progressEl.innerHTML += `<div class="agent-log success">✓ ${esc(ev.message)}</div>`;
          progressEl.scrollTop = progressEl.scrollHeight;
          if (resultEl) {
            resultEl.textContent = `Added ${d.inserted ?? 0} entries (${d.skipped ?? 0} duplicates skipped)`;
          }
          // Refresh KB stats + results to reflect new entries
          renderKB();
        }
        if (ev.type === 'error') {
          progressEl.innerHTML += `<div class="agent-log error">✗ ${esc(ev.message)}</div>`;
          progressEl.scrollTop = progressEl.scrollHeight;
        }
      }
    }
  } catch (err) {
    if (progressEl) {
      progressEl.innerHTML = `<div class="agent-log error">✗ ${esc(err.message)}</div>`;
    }
  }
}

async function renderKB() {
  const [stats] = await Promise.all([API.get('/api/kb/stats')]);
  state.kbStats = stats;

  document.getElementById('kb-stats').innerHTML = `
    <span style="color:var(--text-secondary);font-size:.875rem">
      <strong style="color:var(--text-primary)">${stats.total}</strong> entries from
      <strong style="color:var(--text-primary)">${stats.source_rfps}</strong> RFPs
    </span>`;

  // Inject upload card above search bar if not already present
  const pageKb = document.getElementById('page-kb');
  if (pageKb && !document.getElementById('kb-upload-zone')) {
    const uploadCard = document.createElement('div');
    uploadCard.id = 'kb-upload-card';
    uploadCard.className = 'card';
    uploadCard.style.marginBottom = '20px';
    uploadCard.innerHTML = `
      <div class="card-header" style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">
        <h3 style="margin:0;font-size:1rem;color:var(--text-primary)">Upload Document to Knowledge Base</h3>
        <span style="font-size:.8rem;color:var(--text-muted)">CSV · XLSX · XLSM · DOCX</span>
      </div>
      <div class="card-body">
        <div id="kb-upload-zone" class="upload-zone" style="min-height:80px;padding:20px;text-align:center;cursor:default">
          <input type="file" id="kb-upload-input" accept=".csv,.xlsx,.xls,.xlsm,.docx" style="display:none">
          <div style="color:var(--text-muted);font-size:.875rem">
            Drop a file here or
            <button class="btn btn-primary btn-sm" onclick="document.getElementById('kb-upload-input').click()">
              ⊕ Choose File
            </button>
          </div>
        </div>
        <div id="kb-upload-progress" style="display:none;margin-top:12px;max-height:150px;overflow-y:auto;font-size:.8rem"></div>
        <div id="kb-upload-result" style="margin-top:8px;font-size:.8rem;color:var(--accent-green,var(--green))"></div>
      </div>`;

    // Insert before the search bar (first child after page-header)
    const searchBar = pageKb.querySelector('.search-bar');
    if (searchBar) {
      pageKb.insertBefore(uploadCard, searchBar);
    } else {
      pageKb.appendChild(uploadCard);
    }

    // Wire up file input
    const inp  = document.getElementById('kb-upload-input');
    const zone = document.getElementById('kb-upload-zone');
    inp.onchange  = e => { if (e.target.files[0]) { uploadToKB(e.target.files[0]); inp.value = ''; } };
    zone.ondragover  = e => { e.preventDefault(); zone.classList.add('drag-over'); };
    zone.ondragleave = () => zone.classList.remove('drag-over');
    zone.ondrop      = e => {
      e.preventDefault();
      zone.classList.remove('drag-over');
      if (e.dataTransfer.files[0]) uploadToKB(e.dataTransfer.files[0]);
    };
  }

  await loadKBResults('');
}

function renderKBCard(r) {
  return `
    <div class="kb-card">
      <div class="kb-q">${esc(r.question)}</div>
      <div class="kb-a">${esc(r.answer)}</div>
      <div class="kb-meta">
        ${r.category ? `<span class="badge badge-blue">${esc(r.category)}</span>` : ''}
        ${JSON.parse(r.okta_products || '[]').map(p => `<span class="badge badge-teal">${esc(p)}</span>`).join('')}
        ${r.response_code ? `<span class="badge badge-muted">${esc(r.response_code)}</span>` : ''}
        ${r.ai_match ? `<span class="badge badge-purple">⚡ AI</span>` : ''}
        ${r.source_rfp_name ? `<span class="kb-source">From: ${esc(r.source_rfp_name)}</span>` : ''}
        ${r.use_count ? `<span class="kb-use">Used ${r.use_count}×</span>` : ''}
      </div>
      ${r.relevance ? `<div style="font-size:.72rem;color:var(--text-muted);margin-top:6px;font-style:italic">${esc(r.relevance)}</div>` : ''}
    </div>`;
}

async function loadKBResults(query, ai = false) {
  const list = document.getElementById('kb-list');
  list.innerHTML = `<div style="color:var(--text-muted);padding:20px;display:flex;align-items:center;gap:8px"><span class="spin">⟳</span> ${ai ? 'AI searching…' : 'Searching…'}</div>`;

  const url = `/api/kb/search?q=${encodeURIComponent(query)}&ai=${ai}&limit=30`;
  const data = await API.get(url);

  // AI search returns {bluf, results, query}; plain search returns array
  const results = Array.isArray(data) ? data : (data.results || []);
  const bluf    = Array.isArray(data) ? null  : data.bluf;

  if (!results.length && !bluf) {
    list.innerHTML = `<div class="empty-state"><div class="empty-icon">🔍</div><div class="empty-title">No results found</div><div class="empty-sub">Try different keywords or disable AI search</div></div>`;
    return;
  }

  const blufHtml = (bluf && query) ? `
    <div class="bluf-card">
      <div class="bluf-header">
        <div class="bluf-icon">⚡</div>
        <span class="bluf-label">BLUF — AI Synthesis</span>
        <span class="bluf-query">"${esc(query)}"</span>
      </div>
      <div class="bluf-text">${esc(bluf)}</div>
      <div class="bluf-count">${results.length} supporting ${results.length === 1 ? 'entry' : 'entries'} found in knowledge base</div>
    </div>` : '';

  list.innerHTML = blufHtml + results.map(renderKBCard).join('');
}

async function seedKB() {
  toast('Seeding Okta knowledge base…');
  const res = await API.post('/api/kb/seed', {});
  toast(res.message || 'Done', res.inserted > 0 ? 'success' : 'info');
  renderKB();
}

async function ingestToKB(rfpId) {
  toast('Ingesting to knowledge base…');
  const es = new EventSource(`/api/kb/ingest/${rfpId}`);
  es.onmessage = e => {
    const ev = JSON.parse(e.data);
    if (ev.type === 'agent_complete') {
      toast(ev.message, 'success');
      es.close();
    }
    if (ev.type === 'error') { toast(ev.message, 'error'); es.close(); }
  };
  es.onerror = () => es.close();
}

/* ── Agents Page ─────────────────────────────────────────────────────────── */
const AGENTS_DATA = [
  {
    id: 'customer', icon: '🏢', name: 'Customer Agent', color: '#00B4C8',
    model: 'claude-haiku-4-5', modelTier: 'fast',
    role: 'Customer & RFP Identification',
    description: 'Runs at the start of every pipeline. Reads the uploaded file content and uses Claude to extract the customer name, industry, RFP reference number, issuing department, scope summary, and estimated scale. Displayed in the RFP header and used to personalise agent prompts.',
    tools: ['Claude Haiku 4.5', 'openpyxl', 'csv'],
    inputs: ['Uploaded CSV or XLSX file', 'Filename'],
    outputs: ['customer_name', 'industry', 'rfp_number', 'scope_summary', 'estimated_scale'],
    interactions: [{ to: 'All downstream agents', via: 'Customer context injected into prompts' }],
    techDetail: 'Reads up to 3,000 characters of file content, sends to Claude with a JSON schema. Falls back to filename-derived name if parsing fails. Result cached in rfps.customer_info.',
  },
  {
    id: 'parser', icon: '🗂', name: 'Parser Agent', color: '#007DC1',
    model: 'claude-haiku-4-5', modelTier: 'fast',
    role: 'RFP Structure Detection',
    description: 'Intelligently detects which columns in a CSV or XLSX file contain requirements, categories, priorities, and vendor response fields — regardless of format variation between customers. Eliminates header rows and duplicate entries.',
    tools: ['Claude Haiku 4.5', 'openpyxl', 'csv'],
    inputs: ['CSV or XLSX file'],
    outputs: ['Structured requirement list', 'Column mapping'],
    interactions: [{ to: 'Analysis Agent', via: 'Passes extracted requirements' }],
    techDetail: 'Sends a sample of rows + all header names to Claude and asks it to identify each column\'s semantic meaning. Falls back to longest-text column heuristic if parsing fails.',
  },
  {
    id: 'analyzer', icon: '🔍', name: 'Analysis Agent', color: '#00A4E0',
    model: 'claude-sonnet-4-6', modelTier: 'sonnet',
    role: 'Categorisation & Product Mapping',
    description: 'Processes all requirements in a single batched API call for speed. Maps each requirement to relevant Okta product areas (OIG, LCM, SSO, MFA, PAM, Workflows, AI) and assigns a preliminary risk score.',
    tools: ['Claude Sonnet 4.6 (batch)'],
    inputs: ['Extracted requirements'],
    outputs: ['Refined categories', 'Okta product mapping', 'Risk pre-scores'],
    interactions: [{ to: 'Answer Agent', via: 'Enriched questions with product context' }],
    techDetail: 'Batches up to 40 questions into one API call. Structured JSON output schema. Identifies products: OIG, LCM, Workflows, SSO, MFA, PAM, Universal Directory, AI, OIN.',
  },
  {
    id: 'research', icon: '📚', name: 'Research Agent', color: '#9B6BFA',
    model: 'No LLM — local only', modelTier: 'none',
    role: 'Knowledge Base & Web Retrieval',
    description: 'A tool-calling agent embedded inside the Answer Agent\'s agentic loop. Searches the 640+ entry knowledge base (Okta SIG Core 2024 + past RFP answers) using SQLite FTS5, and optionally fetches live data from trust.okta.com and docs.okta.com.',
    tools: ['SQLite FTS5 (search_knowledge_base)', 'DuckDuckGo API', 'httpx (Okta page fetch)'],
    inputs: ['Search query from Answer Agent'],
    outputs: ['Relevant KB entries', 'Live Okta web content (if enabled)'],
    interactions: [
      { to: 'Answer Agent', via: 'Returns results as tool_result messages' },
      { to: 'trust.okta.com', via: 'Live compliance/uptime data fetch' },
    ],
    techDetail: 'FTS5 BM25 ranking for KB search. Web search: DuckDuckGo site:okta.com + targeted page fetch based on topic keyword. Claude summarises web content before returning. Web search can be disabled in Settings for faster processing.',
  },
  {
    id: 'answer', icon: '✍️', name: 'Answer Agent', color: '#00C58E',
    model: 'claude-sonnet-4-6', modelTier: 'sonnet',
    role: 'Response Generation (Agentic Loop)',
    description: 'The core agent. Runs a 4-iteration agentic loop with tool use. Searches the KB, optionally searches the web, and either flags a question for human review (confidence < 60%) or generates a professional vendor response with response code (F/P/C/NE/N), confidence score, and source citations. Runs in parallel across all requirements (6 workers).',
    tools: ['Claude Sonnet 4.6', 'search_knowledge_base', 'search_web', 'flag_for_review'],
    inputs: ['Requirement text', 'Category', 'Priority', 'Okta products', 'Customer context'],
    outputs: ['Vendor response', 'Response code F/P/C/NE/N', 'Confidence 0–1', 'Fit/risk scores', 'Source citations'],
    interactions: [
      { to: 'Research Agent', via: 'Calls search_knowledge_base and search_web tools' },
      { to: 'Scoring Agent', via: 'Passes per-question fit/risk scores' },
      { to: 'Review Agent', via: 'High-risk answers flagged for QA pass' },
    ],
    techDetail: '4 parallel ThreadPoolExecutor workers. Each worker runs up to 4 Claude API round-trips per question. System prompt includes full OKTA_KNOWLEDGE constant (15KB of product facts). JSON output validated; falls back to flag_for_review on parse failure.',
  },
  {
    id: 'scoring', icon: '⭐', name: 'Scoring Agent', color: '#F5A623',
    model: 'No LLM — aggregation', modelTier: 'none',
    role: 'Fit & Risk Score Aggregation',
    description: 'Aggregates per-question scores from the Answer Agent to produce overall RFP fit and risk scores shown on the dashboard card. Separates answered vs flagged counts.',
    tools: ['Statistical aggregation'],
    inputs: ['Per-question fit scores (1–5)', 'Per-question risk scores (1–5)'],
    outputs: ['Overall fit score /5', 'Overall risk score /5'],
    interactions: [{ to: 'Dashboard', via: 'RFP card fit/risk score display' }],
    techDetail: 'Mean aggregation of Answer Agent scores. Fit: how well Okta meets the requirement. Risk: legal/compliance/SLA sensitivity. Scores stored in rfps.fit_score and rfps.risk_score.',
  },
  {
    id: 'review', icon: '✅', name: 'Review Agent', color: '#E03131',
    model: 'No LLM — rule-based', modelTier: 'none',
    role: 'Quality Assurance',
    description: 'Final pass over all generated answers. Appends mandatory human-review warnings to any high-risk answers (risk_score ≥ 4) to ensure no sensitive commitments slip through. Warnings are displayed in the app but stripped from exports.',
    tools: ['Rule-based pattern matching'],
    inputs: ['All answered questions with risk scores'],
    outputs: ['Augmented answers with internal ⚠ warnings'],
    interactions: [{ to: 'Export', via: 'Internal warnings stripped on CSV/XLSX export' }],
    techDetail: 'Checks every answered question with risk_score ≥ 4. If no legal/commercial language present, appends "⚠ This requirement has been scored as high-risk. Review with your legal/commercial team." The ⚠ prefix is used by export_handler.py to strip the note.',
  },
  {
    id: 'kb', icon: '🧠', name: 'KB Ingestion Agent', color: '#007DC1',
    model: 'No LLM — local only', modelTier: 'none',
    role: 'Knowledge Base Builder',
    description: 'Ingests all answered questions from a completed RFP into the searchable knowledge base. Deduplicates using FTS5 search. Grows the shared answer library so every future RFP benefits from past responses. The KB currently holds 640+ entries from the Okta SIG Core 2024 and past RFPs.',
    tools: ['SQLite FTS5', 'Deduplication via search_knowledge_base'],
    inputs: ['Completed RFP with answered questions'],
    outputs: ['New KB entries', 'Updated FTS5 index'],
    interactions: [{ to: 'Research Agent', via: 'KB entries retrieved in all future RFPs' }],
    techDetail: 'Before inserting, runs FTS search on first 80 chars of each question. Skips if similar entry exists. Maintains kb_search FTS5 virtual table in sync via INSERT triggers. Source tagged as RFP name.',
  },
  {
    id: 'demo', icon: '🎭', name: 'Demo Prep Agent', color: '#F5A623',
    model: 'claude-sonnet-4-6', modelTier: 'sonnet',
    role: 'Demo Planning & Script Generation',
    description: 'Activated after RFP processing. Reads all answered requirements grouped by category, priority, and Okta product area, then generates an ordered demo plan with sections, time estimates, demo steps, talking points, differentiators, and environment setup notes. Confirmed plans are stored in the Demo Library.',
    tools: ['Claude Sonnet 4.6'],
    inputs: ['All answered RFP questions', 'Customer context', 'Optional: customer-provided demo format'],
    outputs: ['Ordered demo sections', 'Demo steps per section', 'Talking points', 'Differentiators', 'Prep notes', 'Estimated total time'],
    interactions: [
      { to: 'RFP Detail view', via: 'Live-streamed demo plan generation' },
      { to: 'Demo Library', via: 'Confirmed plans stored for team reuse' },
    ],
    techDetail: 'Single API call with compact JSON schema (max 8000 tokens). 4–6 sections ordered by customer priority (Critical first). Groups related requirements into logical demo flows. SE confirms the plan to add it to the Demo Library.',
  },
];

function renderAgents() {
  const pipeline = document.getElementById('agents-pipeline');
  const grid = document.getElementById('agents-grid');

  const pipelineSteps = ['Customer Agent', 'Parser Agent', 'Analysis Agent', 'Research Agent', 'Answer Agent', 'Scoring Agent', 'Review Agent'];
  pipeline.innerHTML = pipelineSteps.map((name, i) => `
    <div class="pipeline-step">
      <div class="pipeline-node" onclick="openAgentFlyout('${name}')">${name}</div>
      ${i < pipelineSteps.length - 1 ? '<span class="pipeline-arrow">→</span>' : ''}
    </div>`).join('') +
    '<span class="pipeline-arrow" style="margin:0 12px">+</span>' +
    '<div class="pipeline-node" onclick="openAgentFlyout(\'KB Ingestion Agent\')">KB Ingestion Agent</div>' +
    '<span class="pipeline-arrow" style="margin:0 12px">+</span>' +
    '<div class="pipeline-node" onclick="openAgentFlyout(\'Demo Prep Agent\')">Demo Prep Agent</div>';

  grid.innerHTML = AGENTS_DATA.map(a => {
    const modelColor = a.modelTier === 'sonnet' ? 'var(--okta-blue)' : a.modelTier === 'fast' ? 'var(--green)' : 'var(--text-muted)';
    const modelLabel = a.modelTier === 'sonnet' ? '⚡ Sonnet' : a.modelTier === 'fast' ? '🪶 Haiku' : '🔧 Local';
    return `
    <div class="agent-demo-card" style="--agent-color:${a.color}" onclick="openAgentFlyout('${a.name}')">
      <span class="view-detail">Details →</span>
      <div class="agent-demo-icon" style="border-color:${a.color};color:${a.color}">${a.icon}</div>
      <div class="agent-demo-name">${a.name}</div>
      <div class="agent-demo-role">${a.role}</div>
      <div style="font-size:.72rem;font-weight:600;color:${modelColor};margin:4px 0 8px;letter-spacing:.03em">${modelLabel}</div>
      <div class="agent-demo-tools">
        ${a.tools.map(t => `<span class="tool-chip">${esc(t)}</span>`).join('')}
      </div>
    </div>`;
  }).join('');
}

function openAgentFlyout(agentName) {
  const a = AGENTS_DATA.find(x => x.name === agentName);
  if (!a) return;

  const flyout = document.getElementById('agent-flyout');
  const overlay = document.getElementById('flyout-overlay');

  const modelColor = a.modelTier === 'sonnet' ? 'var(--okta-blue)' : a.modelTier === 'fast' ? 'var(--green)' : 'var(--text-muted)';
  const modelLabel = a.modelTier === 'sonnet' ? '⚡ Sonnet' : a.modelTier === 'fast' ? '🪶 Haiku' : '🔧 Local / No LLM';
  flyout.innerHTML = `
    <button class="flyout-close" onclick="closeFlyout()">✕</button>
    <div class="flyout-icon" style="border-color:${a.color};color:${a.color}">${a.icon}</div>
    <div class="flyout-name">${a.name}</div>
    <div class="flyout-role">${a.role}</div>
    <div style="font-size:.78rem;font-weight:600;color:${modelColor};margin:4px 0 14px;letter-spacing:.04em">${modelLabel} &nbsp;·&nbsp; <span style="font-weight:400;color:var(--text-muted)">${esc(a.model)}</span></div>

    <div class="flyout-section">
      <div class="flyout-section-title">What it does</div>
      <p>${a.description}</p>
    </div>

    <div class="flyout-section">
      <div class="flyout-section-title">Inputs</div>
      <ul>${a.inputs.map(i => `<li>${esc(i)}</li>`).join('')}</ul>
    </div>

    <div class="flyout-section">
      <div class="flyout-section-title">Outputs</div>
      <ul>${a.outputs.map(o => `<li>${esc(o)}</li>`).join('')}</ul>
    </div>

    <div class="flyout-section">
      <div class="flyout-section-title">Tools Used</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap">
        ${a.tools.map(t => `<span class="tool-chip" style="font-size:.75rem;padding:3px 10px">${esc(t)}</span>`).join('')}
      </div>
    </div>

    <div class="flyout-section">
      <div class="flyout-section-title">Agent Interactions</div>
      ${a.interactions.map(i => `
        <div class="interaction-row">
          <span class="int-arrow">→</span>
          <strong>${esc(i.to)}</strong>
          <span class="int-target">— ${esc(i.via)}</span>
        </div>`).join('')}
    </div>

    <div class="flyout-section">
      <div class="flyout-section-title">Technical Detail</div>
      <p>${esc(a.techDetail)}</p>
    </div>`;

  overlay.classList.add('open');
  flyout.classList.add('open');
}

function closeFlyout() {
  document.getElementById('agent-flyout').classList.remove('open');
  document.getElementById('flyout-overlay').classList.remove('open');
}

/* ── Discover RFPs ───────────────────────────────────────────────────────── */

async function renderDiscover() {
  const resultsEl = document.getElementById('discover-results');
  const statsEl   = document.getElementById('discover-stats');
  const lastEl    = document.getElementById('discover-last-refreshed');

  resultsEl.innerHTML = '<div class="empty-state" style="grid-column:1/-1"><div class="empty-icon"><span class="spin">⟳</span></div><div>Loading…</div></div>';

  let data;
  try {
    data = await API.get('/api/discover/results');
  } catch (e) {
    resultsEl.innerHTML = '<div class="empty-state" style="grid-column:1/-1"><div class="empty-icon">⚠</div><div class="empty-title">Could not load results</div><div class="empty-sub">Run Discovery to fetch fresh results.</div></div>';
    return;
  }

  const items = Array.isArray(data) ? data : (data.results || []);

  if (!items.length) {
    const portals = ['CanadaBuys', 'MERX', 'Alberta APC', 'BC Bid'];
    const portalList = portals.map(p => `<span class="badge badge-blue" style="font-size:.72rem">${esc(p)}</span>`).join(' ');
    resultsEl.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        <div class="empty-icon">🔍</div>
        <div class="empty-title">No results yet</div>
        <div class="empty-sub" style="max-width:480px;line-height:1.7">
          Discovery searches Canadian procurement portals for IAM, identity, and cybersecurity tenders that match your keyword groups.
          <div style="margin:10px 0 6px;display:flex;gap:6px;justify-content:center;flex-wrap:wrap">${portalList}</div>
          Click <strong>Run Discovery</strong> to search 12 targeted queries across these portals.
        </div>
      </div>`;
    statsEl.style.display = 'none';
    return;
  }

  // Update stats bar
  const newCount       = items.filter(r => r.status === 'new').length;
  const importedCount  = items.filter(r => r.status === 'imported').length;
  const dismissedCount = items.filter(r => r.status === 'dismissed').length;
  statsEl.style.display = '';
  statsEl.innerHTML = `
    <span class="discover-stat"><strong style="color:var(--okta-blue-lt)">${newCount}</strong> New</span>
    <span class="discover-stat-sep">·</span>
    <span class="discover-stat"><strong style="color:var(--green)">${importedCount}</strong> Imported</span>
    <span class="discover-stat-sep">·</span>
    <span class="discover-stat"><strong style="color:var(--text-muted)">${dismissedCount}</strong> Dismissed</span>`;

  if (lastEl && data.fetched_at) {
    lastEl.textContent = 'Last refreshed ' + formatDate(data.fetched_at);
  }

  resultsEl.innerHTML = items.map(item => buildDiscoveryCard(item)).join('');
}

function runDiscovery() {
  const feed      = document.getElementById('discover-feed');
  const resultsEl = document.getElementById('discover-results');
  const statsEl   = document.getElementById('discover-stats');
  const lastEl    = document.getElementById('discover-last-refreshed');

  // Show feed, clear previous progress
  feed.style.display = '';
  feed.innerHTML = '';
  resultsEl.innerHTML = '';

  const es = new EventSource('/api/discover/run');

  es.onmessage = e => {
    const ev = JSON.parse(e.data);
    const ts = new Date().toLocaleTimeString('en', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });

    if (ev.type === 'discovery_progress' && ev.message) {
      const item = document.createElement('div');
      item.className = 'activity-item';
      item.innerHTML = `<span class="ts">${ts}</span><span class="agent-tag">Discovery</span>  ${esc(ev.message)}`;
      feed.appendChild(item);
      feed.scrollTop = feed.scrollHeight;
    }

    if (ev.type === 'discovery_result' && ev.data) {
      const card = document.createElement('div');
      card.innerHTML = buildDiscoveryCard(ev.data);
      const cardEl = card.firstElementChild;
      if (resultsEl.querySelector('.empty-state')) resultsEl.innerHTML = '';
      resultsEl.prepend(cardEl);
    }

    if (ev.type === 'discovery_complete') {
      es.close();
      feed.style.display = 'none';

      // Update stats from completion payload
      const summary = ev.data || {};
      const newCount       = summary.new_count      ?? 0;
      const importedCount  = summary.imported_count ?? 0;
      const dismissedCount = summary.dismissed_count ?? 0;

      if (newCount + importedCount + dismissedCount > 0) {
        statsEl.style.display = '';
        statsEl.innerHTML = `
          <span class="discover-stat"><strong style="color:var(--okta-blue-lt)">${newCount}</strong> New</span>
          <span class="discover-stat-sep">·</span>
          <span class="discover-stat"><strong style="color:var(--green)">${importedCount}</strong> Imported</span>
          <span class="discover-stat-sep">·</span>
          <span class="discover-stat"><strong style="color:var(--text-muted)">${dismissedCount}</strong> Dismissed</span>`;
      }

      if (lastEl) lastEl.textContent = 'Last refreshed ' + new Date().toLocaleString('en', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });

      toast(`Discovery complete — ${newCount} new tender${newCount !== 1 ? 's' : ''} found`, 'success');

      if (!resultsEl.children.length) {
        resultsEl.innerHTML = '<div class="empty-state" style="grid-column:1/-1"><div class="empty-icon">🔍</div><div class="empty-title">No matching tenders found</div><div class="empty-sub">Try again later — procurement portals update daily.</div></div>';
      }
    }

    if (ev.type === 'error') {
      es.close();
      feed.style.display = 'none';
      toast('Discovery failed: ' + esc(ev.message || 'Unknown error'), 'error');
    }
  };

  es.onerror = () => {
    es.close();
    feed.style.display = 'none';
    toast('Discovery stream lost — check backend connection', 'error');
  };
}

function buildDiscoveryCard(item) {
  // Source badge colour
  const sourceLower = (item.source || '').toLowerCase();
  let badgeStyle = 'background:rgba(0,125,193,.2);color:#5ac8f5;border-color:rgba(0,125,193,.35)'; // CanadaBuys = Okta blue
  if (sourceLower.includes('merx')) {
    badgeStyle = 'background:rgba(155,107,250,.2);color:#c4a0ff;border-color:rgba(155,107,250,.35)'; // purple
  } else if (sourceLower.includes('alberta') || sourceLower.includes('apc') ||
             sourceLower.includes('bc bid') || sourceLower.includes('provincial')) {
    badgeStyle = 'background:rgba(0,197,142,.15);color:#00e8a8;border-color:rgba(0,197,142,.3)'; // green
  }

  // Title — truncate at 80 chars; apply strikethrough if closed
  const rawTitle = item.title || 'Untitled';
  const displayTitle = rawTitle.length > 80 ? rawTitle.slice(0, 77) + '…' : rawTitle;

  // Description snippet from raw_data JSON
  let snippetHtml = '';
  try {
    const rd = item.raw_data ? (typeof item.raw_data === 'string' ? JSON.parse(item.raw_data) : item.raw_data) : null;
    const snippet = rd && rd.snippet ? String(rd.snippet).trim() : '';
    if (snippet) {
      const truncated = snippet.length > 280 ? snippet.slice(0, 277) + '…' : snippet;
      snippetHtml = `<div class="discovery-card-desc">${esc(truncated)}</div>`;
    }
  } catch { snippetHtml = ''; }

  // Closing date — full human-readable status with days remaining
  let closingHtml = '';
  let isClosed = false;
  if (item.closing_date) {
    try {
      const closeDate = new Date(item.closing_date);
      if (!isNaN(closeDate.getTime())) {
        const daysLeft = Math.ceil((closeDate.getTime() - Date.now()) / 86400000);
        const dateStr  = formatDate(item.closing_date);
        if (daysLeft < 0) {
          isClosed = true;
          closingHtml = `<span style="color:var(--red);font-weight:600;text-decoration:line-through">${esc(dateStr)}</span> <span style="color:var(--red);font-weight:700">CLOSED</span>`;
        } else if (daysLeft < 7) {
          closingHtml = `<span style="color:var(--amber);font-weight:700">Closes in ${daysLeft} day${daysLeft !== 1 ? 's' : ''}</span> <span style="color:var(--text-muted);font-size:.68rem">(${esc(dateStr)})</span>`;
        } else {
          closingHtml = `<span>Closes in ${daysLeft} days</span> <span style="color:var(--text-muted);font-size:.68rem">(${esc(dateStr)})</span>`;
        }
      }
    } catch { closingHtml = `<span>${esc(formatDate(item.closing_date))}</span>`; }
  } else {
    closingHtml = `<span style="color:var(--text-muted);font-style:italic">Closing date TBD</span>`;
  }

  // Title style — strikethrough if closed
  const titleStyle = isClosed ? ' style="text-decoration:line-through;color:var(--text-muted)"' : '';

  // Est. value
  const valueHtml = item.est_value
    ? `<span style="color:var(--text-muted)">Est. ${esc(item.est_value)}</span>`
    : '';

  // Relevance score pill
  const score = item.relevance_score != null ? Math.round(item.relevance_score * 10) / 10 : null;
  const scoreHtml = score != null
    ? `<span class="discover-score-badge">${score}/10</span>`
    : '';

  // Relevance tags
  let tags = [];
  try { tags = JSON.parse(item.relevance_tags || '[]'); } catch { tags = []; }
  const tagsHtml = tags.length
    ? tags.map(t => `<span class="badge badge-blue" style="font-size:.65rem">${esc(t)}</span>`).join('')
    : '';

  // Card status class
  const statusCls = item.status === 'dismissed' ? ' discover-card-dismissed' : item.status === 'imported' ? ' discover-card-imported' : '';

  // Action buttons
  const importedBadge = item.status === 'imported'
    ? `<span class="badge badge-green" id="discover-status-${item.id}">✓ Imported</span>`
    : `<button class="btn btn-primary btn-sm" id="discover-status-${item.id}" onclick="importDiscoveredRfp(${item.id}, this)">Import →</button>`;

  // Portal button — hide entirely if no URL, show muted label instead
  const portalBtn = item.source_url
    ? `<a href="${esc(item.source_url)}" target="_blank" rel="noopener" class="btn btn-secondary btn-sm">View on Portal ↗</a>`
    : `<span style="font-size:.72rem;color:var(--text-muted);font-style:italic;align-self:center">No portal link</span>`;

  const dismissBtn = item.status !== 'dismissed'
    ? `<button class="btn btn-ghost btn-sm" onclick="dismissDiscoveredRfp(${item.id}, this.closest('.discovery-card'))">✕ Dismiss</button>`
    : `<button class="btn btn-ghost btn-sm" style="color:var(--text-muted);cursor:default" disabled>Dismissed</button>`;

  return `
    <div class="discovery-card${statusCls}" id="discover-card-${item.id}" data-tags='${JSON.stringify(tags).replace(/'/g, "&#39;")}' data-source="${esc(item.source || '')}">
      <div class="discovery-card-top">
        <span class="source-badge" style="${badgeStyle}">${esc(item.source || 'Unknown')}</span>
        ${scoreHtml}
      </div>
      <div class="discovery-card-title"${titleStyle} title="${esc(rawTitle)}">${esc(displayTitle)}</div>
      ${item.org_name ? `<div class="discovery-card-org">${esc(item.org_name)}</div>` : ''}
      ${item.solicitation_no ? `<div style="font-size:.72rem;color:var(--text-muted);margin-bottom:6px">#${esc(item.solicitation_no)}</div>` : ''}
      ${snippetHtml}
      <div class="discovery-card-meta">
        ${closingHtml}
        ${valueHtml}
      </div>
      ${tagsHtml ? `<div class="discovery-card-tags">${tagsHtml}</div>` : ''}
      <div class="discovery-card-actions">
        ${portalBtn}
        ${importedBadge}
        ${dismissBtn}
      </div>
    </div>`;
}

async function importDiscoveredRfp(id, btn) {
  if (btn) { btn.disabled = true; btn.textContent = '⟳ Importing…'; }
  try {
    const res = await API.post(`/api/discover/import/${id}`, {});
    if (res.error) {
      toast('Import failed: ' + res.error, 'error');
      if (btn) { btn.disabled = false; btn.textContent = 'Import →'; }
      return;
    }
    toast('Imported — open the RFP to upload documents', 'success');

    // Update card status display
    const statusEl = document.getElementById(`discover-status-${id}`);
    if (statusEl) {
      const newBadge = document.createElement('span');
      newBadge.className = 'badge badge-green';
      newBadge.id = `discover-status-${id}`;
      newBadge.textContent = '✓ Imported';
      statusEl.replaceWith(newBadge);
    }
    const card = document.getElementById(`discover-card-${id}`);
    if (card) card.classList.add('discover-card-imported');

    // Navigate to the newly created RFP
    if (res.rfp_id) {
      setTimeout(async () => {
        const rfp = await API.get(`/api/rfp/${res.rfp_id}`);
        state.currentRfp = rfp;
        navigate('rfp-detail', rfp);
      }, 400);
    }
  } catch (e) {
    toast('Import failed: ' + e.message, 'error');
    if (btn) { btn.disabled = false; btn.textContent = 'Import →'; }
  }
}

async function dismissDiscoveredRfp(id, card) {
  try {
    const res = await API.post(`/api/discover/dismiss/${id}`, {});
    if (res.error) { toast('Could not dismiss: ' + res.error, 'error'); return; }
    if (card) {
      card.style.transition = 'opacity .3s ease, transform .3s ease';
      card.style.opacity    = '0';
      card.style.transform  = 'scale(.95)';
      setTimeout(() => card.remove(), 320);
    }
  } catch (e) {
    toast('Dismiss failed: ' + e.message, 'error');
  }
}

function filterDiscovery(tag) {
  // Update active chip
  document.querySelectorAll('#discover-filters .filter-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.filter === tag);
  });

  document.querySelectorAll('#discover-results .discovery-card').forEach(card => {
    if (tag === 'all') { card.style.display = ''; return; }

    // Match against relevance_tags array or source
    let tags = [];
    try { tags = JSON.parse(card.dataset.tags || '[]'); } catch { tags = []; }
    const source = (card.dataset.source || '').toLowerCase();

    let visible = false;
    if (tag === 'Federal')   visible = source.includes('canadabuy') || source.includes('merx') || source.includes('federal');
    else if (tag === 'Provincial') visible = source.includes('alberta') || source.includes('apc') || source.includes('bc bid') || source.includes('provincial');
    else                     visible = tags.some(t => t.toLowerCase().includes(tag.toLowerCase()));

    card.style.display = visible ? '' : 'none';
  });
}

/* ── Settings Page ───────────────────────────────────────────────────────── */
async function loadUsage() {
  const panel = document.getElementById('usage-panel');
  if (!panel) return;
  panel.innerHTML = '<div style="color:var(--text-muted);font-size:.8rem"><span class="spin">⟳</span> Loading…</div>';

  const u = await API.get('/api/usage');
  const total = (u.total_input || 0) + (u.total_output || 0);

  // Cost estimate: claude-sonnet-4-6 pricing ~$3/$15 per 1M tokens
  const costIn  = ((u.total_input  || 0) / 1_000_000) * 3;
  const costOut = ((u.total_output || 0) / 1_000_000) * 15;
  const costEst = (costIn + costOut).toFixed(4);

  const litellm = u.litellm;
  const spendRow = litellm ? `
    <div class="usage-stat-row">
      <span class="usage-label">LiteLLM Spend</span>
      <span class="usage-value">$${Number(litellm.spend || 0).toFixed(6)}</span>
    </div>
    ${litellm.budget != null ? `<div class="usage-stat-row"><span class="usage-label">Budget</span><span class="usage-value">$${litellm.budget}</span></div>` : ''}
  ` : '';

  const byRfp = (u.by_rfp || []).map(r => `
    <div class="usage-rfp-row">
      <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:180px">${esc(r.name)}</span>
      <span style="color:var(--text-muted);font-size:.7rem">${fmt(r.inp + r.out)} tokens</span>
    </div>`).join('');

  panel.innerHTML = `
    <div class="usage-grid">
      <div class="usage-stat">
        <div class="usage-num">${fmt(u.total_input || 0)}</div>
        <div class="usage-lbl">Input Tokens</div>
      </div>
      <div class="usage-stat">
        <div class="usage-num">${fmt(u.total_output || 0)}</div>
        <div class="usage-lbl">Output Tokens</div>
      </div>
      <div class="usage-stat">
        <div class="usage-num">${fmt(total)}</div>
        <div class="usage-lbl">Total Tokens</div>
      </div>
      <div class="usage-stat">
        <div class="usage-num" style="color:var(--green)">~$${costEst}</div>
        <div class="usage-lbl">Est. Cost (USD)</div>
      </div>
    </div>
    ${spendRow ? `<div class="usage-section">${spendRow}</div>` : ''}
    ${byRfp ? `
    <div style="margin-top:14px">
      <div class="usage-section-title">By RFP</div>
      ${byRfp}
    </div>` : ''}
    ${u.total_calls ? `<div style="font-size:.7rem;color:var(--text-muted);margin-top:8px">${u.total_calls} API calls recorded</div>` : ''}
  `;
}

function fmt(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M';
  if (n >= 1_000)     return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}

async function renderSettings() {
  const s = await API.get('/api/settings');
  document.getElementById('api-key-indicator').textContent = s.api_key_set ? '✓ API key is set' : 'No API key configured';
  document.getElementById('api-key-indicator').style.color = s.api_key_set ? 'var(--green)' : 'var(--red)';
  document.getElementById('drive-folder-id').value = s.drive_folder_id || '';
  document.getElementById('drive-folder-name').value = s.drive_folder_name || '';
  document.getElementById('litellm-base-url').value = s.litellm_base_url || '';
  document.getElementById('web-search-toggle').checked = s.web_search_enabled !== false;
  document.getElementById('okta-domain').value = s.okta_domain || '';
  document.getElementById('okta-client-id').value = s.okta_client_id || '';
  document.getElementById('okta-redirect-uri').value = s.okta_redirect_uri || 'http://localhost:5000/auth/callback';
  document.getElementById('okta-auth-enabled').checked = s.okta_auth_enabled === true;
  updateApiDot(s.api_key_set);
}

async function saveOktaSettings() {
  const el = document.getElementById('okta-save-result');
  const payload = {
    okta_domain: document.getElementById('okta-domain').value.trim(),
    okta_client_id: document.getElementById('okta-client-id').value.trim(),
    okta_redirect_uri: document.getElementById('okta-redirect-uri').value.trim(),
    okta_auth_enabled: document.getElementById('okta-auth-enabled').checked,
  };
  const res = await API.post('/api/settings', payload);
  if (res.success) {
    el.style.color = 'var(--green)';
    el.textContent = '✓ Saved';
    setTimeout(() => { el.textContent = ''; }, 3000);
  } else {
    el.style.color = 'var(--red)';
    el.textContent = '✗ Failed to save';
  }
}

async function testConnection() {
  const el = document.getElementById('connection-result');
  el.style.color = 'var(--text-muted)';
  el.textContent = '⟳ Testing…';
  const key = document.getElementById('api-key-input').value.trim();
  const res = await API.post('/api/test-connection', key ? { api_key: key } : {});
  if (res.ok) {
    el.style.color = 'var(--green)';
    el.textContent = res.message;
  } else {
    el.style.color = 'var(--red)';
    el.textContent = '✗ ' + (res.error || 'Failed');
  }
}

async function saveSettings() {
  const key = document.getElementById('api-key-input').value.trim();
  const folderId = document.getElementById('drive-folder-id').value.trim();
  const folderName = document.getElementById('drive-folder-name').value.trim();
  const litellmUrl = document.getElementById('litellm-base-url').value.trim();

  const payload = {};
  if (key) payload.api_key = key;
  if (folderId !== undefined) payload.drive_folder_id = folderId;
  if (folderName !== undefined) payload.drive_folder_name = folderName;
  if (litellmUrl !== undefined) payload.litellm_base_url = litellmUrl;
  payload.web_search_enabled = document.getElementById('web-search-toggle').checked;

  const res = await API.post('/api/settings', payload);
  if (res.success) {
    toast('Settings saved', 'success');
    document.getElementById('api-key-input').value = '';
    renderSettings();
  }
}

function updateApiDot(ok) {
  document.querySelectorAll('.api-dot').forEach(d => d.classList.toggle('ok', ok));
  const label = document.getElementById('api-status-label');
  if (label) label.textContent = ok ? 'API Connected' : 'API Not Set';
}

/* ── Utilities ───────────────────────────────────────────────────────────── */
function esc(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatDate(dt) {
  if (!dt) return '';
  try { return new Date(dt).toLocaleDateString('en', { month: 'short', day: 'numeric', year: 'numeric' }); }
  catch { return dt; }
}

/* ── Boot ────────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  initUpload();
  initSidebar();

  document.querySelectorAll('.sidebar-btn').forEach(btn => {
    btn.addEventListener('click', () => navigate(btn.dataset.page));
  });

  document.getElementById('flyout-overlay').addEventListener('click', closeFlyout);

  document.getElementById('kb-search-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      const q = e.target.value.trim();
      const ai = document.getElementById('ai-search-toggle').checked;
      loadKBResults(q, ai);
    }
  });

  navigate('home');
});
