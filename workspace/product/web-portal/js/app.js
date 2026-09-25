const API = localStorage.getItem('nx_api') || 'http://127.0.0.1:8000';
let token = localStorage.getItem('nx_portal_token') || '';
let lastReportId = localStorage.getItem('nx_report_id') || null;

const el = (id) => document.getElementById(id);
if (el('apiBaseLabel')) el('apiBaseLabel').textContent = API;

async function api(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (token) headers.Authorization = 'Bearer ' + token;
  if (opts.json) {
    headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(opts.json);
  }
  const res = await fetch(API + path, { ...opts, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || res.statusText));
  if (data.session?.token) {
    token = data.session.token;
    localStorage.setItem('nx_portal_token', token);
  }
  if (data.report_id) {
    lastReportId = data.report_id;
    localStorage.setItem('nx_report_id', lastReportId);
  }
  return data;
}

function showMarketing() {
  el('view-marketing').classList.remove('hidden');
  el('view-app').classList.add('hidden');
}

function showApp(which) {
  el('view-marketing').classList.add('hidden');
  el('view-app').classList.remove('hidden');
  if (which === 'demo') {
    panel('health');
    runDemo();
  } else panel(which || 'health');
}

function panel(id) {
  ['health', 'upload', 'build', 'pay', 'login', 'chat', 'models'].forEach((p) => {
    const node = el('panel-' + p);
    if (node) node.classList.toggle('hidden', p !== id);
  });
  document.querySelectorAll('.side button[data-panel]').forEach((b) => {
    b.classList.toggle('on', b.dataset.panel === id);
  });
}

let lastUploadHoldings = null;
let lastPaymentId = null;

async function doLogin() {
  const out = el('loginOut');
  try {
    const r = await api('/api/login', {
      method: 'POST',
      json: {
        name: el('loginName')?.value || 'Guest',
        phone: el('loginPhone')?.value || '9999999999',
      },
    });
    out.textContent = JSON.stringify(r, null, 2);
  } catch (e) {
    out.textContent = e.message;
  }
}

async function uploadDoc() {
  const out = el('uploadOut');
  const f = el('docFile')?.files?.[0];
  if (!f) {
    out.textContent = 'Choose a file first';
    return;
  }
  out.textContent = 'Parsing ' + f.name + '…';
  try {
    const fd = new FormData();
    fd.append('file', f);
    const headers = {};
    if (token) headers.Authorization = 'Bearer ' + token;
    const res = await fetch(API + '/api/ingest/document', { method: 'POST', headers, body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    if (data.session?.token) {
      token = data.session.token;
      localStorage.setItem('nx_portal_token', token);
    }
    lastUploadHoldings = data.holdings || [];
    out.textContent = JSON.stringify(
      {
        kind: data.kind,
        count: data.count,
        holdings: data.holdings,
        validation_errors: data.validation_errors,
        source: data.canonical?.source,
      },
      null,
      2
    );
  } catch (e) {
    out.textContent = e.message;
  }
}

async function analyseUpload() {
  if (!lastUploadHoldings?.length) {
    alert('Upload a document first');
    return;
  }
  panel('health');
  el('holdingsJson').value = JSON.stringify(lastUploadHoldings, null, 2);
  await analyseMine();
}

async function createPay() {
  const out = el('payOut');
  try {
    const r = await api('/api/payments/create', {
      method: 'POST',
      json: { amount_inr: 99, method: 'dummy_upi' },
    });
    lastPaymentId = r.payment_id;
    out.textContent = JSON.stringify(r, null, 2);
  } catch (e) {
    out.textContent = e.message;
  }
}

async function confirmPay() {
  const out = el('payOut');
  if (!lastPaymentId) {
    out.textContent = 'Create an order first';
    return;
  }
  try {
    const r = await api('/api/payments/confirm', {
      method: 'POST',
      json: { payment_id: lastPaymentId },
    });
    out.textContent = JSON.stringify(r, null, 2);
  } catch (e) {
    out.textContent = e.message;
  }
}

async function doUnlockCode() {
  const code = el('unlockCodeWeb')?.value?.trim() || 'DEMO-UNLOCK';
  try {
    const r = await api('/api/unlock', { method: 'POST', json: { code } });
    el('payOut').textContent = JSON.stringify(r, null, 2);
    alert('Unlocked');
  } catch (e) {
    alert(e.message);
  }
}

function fmt(n) {
  if (n == null || isNaN(n)) return '—';
  return Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 });
}
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function renderHealth(r, mountId) {
  const s = r.story || {};
  const sample = r.is_sample;
  const issues = r.issues || [];
  const issuesHtml = issues
    .map(
      (iss, i) => `
    <div style="border:1px solid var(--border);border-left:3px solid ${iss.severity === 'high' || iss.severity === 'critical' ? 'var(--danger)' : 'var(--warning)'};border-radius:12px;padding:12px;margin:8px 0;background:var(--surface-2)">
      <div style="display:flex;justify-content:space-between;font-size:11px;font-weight:800;color:var(--text-3)">
        <span>ISSUE ${i + 1} · ${(iss.severity || '').toUpperCase()}</span>
        <span style="color:var(--danger)">${iss.annual_cost_rs > 0 ? '₹' + fmt(iss.annual_cost_rs) + '/yr' : '—'}</span>
      </div>
      <div style="font-weight:700;margin:6px 0">${esc(iss.title)}</div>
      <div style="color:var(--text-2);font-size:0.9rem">${esc(iss.description || '')}</div>
      ${iss.fix ? `<div style="margin-top:8px;padding:8px 10px;border-radius:8px;background:rgba(61,220,255,0.1);color:var(--accent);font-size:0.85rem;font-weight:600">Fix → ${esc(iss.fix)}</div>` : ''}
    </div>`
    )
    .join('');

  el(mountId).innerHTML = `
    ${sample ? `<div class="banner-sample">${esc(s.banner?.title || 'Illustrative sample — not your portfolio')}</div>` : ''}
    <p style="font-size:1.15rem;font-weight:700;margin:8px 0">${esc(s.headline || r.teaser_summary || '')}</p>
    <div class="kpis">
      <div class="kpi"><div class="l">Score</div><div class="v">${r.score ?? '—'}</div></div>
      <div class="kpi"><div class="l">Avoidable</div><div class="v danger">${esc(s.hero_metric?.display || '—')}</div></div>
      <div class="kpi"><div class="l">TER</div><div class="v">₹${fmt(r.ter_waste_annual_rs)}</div></div>
      <div class="kpi"><div class="l">Overlap</div><div class="v">₹${fmt(r.overlap_waste_annual_rs)}</div></div>
    </div>
    <h3 style="margin:12px 0 6px;font-size:0.95rem">Findings</h3>
    ${issuesHtml || '<p style="color:var(--text-3)">No issues listed.</p>'}
    <div style="margin-top:14px;padding:14px;border-radius:14px;background:linear-gradient(135deg,var(--navy-950),var(--navy-800));border:1px solid var(--border)">
      <strong>Unlock · ₹99</strong>
      <p style="color:var(--text-2);font-size:0.85rem;margin:6px 0">Codes: DEMO-UNLOCK · NXANCE-TEST</p>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <input id="unlockIn" placeholder="DEMO-UNLOCK" style="flex:1;min-width:140px;padding:10px 12px;border-radius:999px;border:1px solid var(--border);background:var(--surface-2);color:var(--text)" />
        <button class="btn btn-primary" onclick="doUnlock()">Unlock</button>
      </div>
    </div>
    <p style="color:var(--text-3);font-size:0.8rem;margin-top:10px">Stack: ${esc((r.intelligence_stack?.layers || []).join(' → '))}</p>
  `;
}

async function runDemo() {
  const box = el('healthOut');
  box.innerHTML = '<p style="color:var(--text-2)">Running labelled sample…</p>';
  try {
    const r = await api('/api/demo/run', { method: 'POST' });
    renderHealth(r, 'healthOut');
  } catch (e) {
    box.innerHTML = `<p style="color:var(--danger)">${esc(e.message)}. API at ${API}?</p>`;
  }
}

async function analyseMine() {
  const box = el('healthOut');
  const raw = el('holdingsJson')?.value?.trim();
  let holdings;
  try {
    holdings = raw ? JSON.parse(raw) : null;
  } catch {
    box.innerHTML = '<p style="color:var(--danger)">Holdings JSON invalid</p>';
    return;
  }
  if (!holdings?.length) {
    box.innerHTML = '<p style="color:var(--danger)">Add holdings JSON array first (or run sample demo).</p>';
    return;
  }
  box.innerHTML = '<p style="color:var(--text-2)">Diagnosing your holdings…</p>';
  try {
    const r = await api('/api/health-check', {
      method: 'POST',
      json: {
        holdings,
        questionnaire: {
          goal: el('hcGoal')?.value || 'Wealth Creation',
          target_amount: parseFloat(el('hcTarget')?.value || '5000000'),
          years: parseFloat(el('hcYears')?.value || '10'),
          monthly_sip: parseFloat(el('hcSip')?.value || '10000'),
          risk: el('hcRisk')?.value || 'moderate',
        },
      },
    });
    renderHealth(r, 'healthOut');
  } catch (e) {
    box.innerHTML = `<p style="color:var(--danger)">${esc(e.message)}</p>`;
  }
}

async function loadSampleJson() {
  try {
    const r = await api('/api/sample-portfolio');
    el('holdingsJson').value = JSON.stringify(r.holdings, null, 2);
  } catch (e) {
    alert(e.message);
  }
}

async function doUnlock() {
  const code = el('unlockIn')?.value?.trim();
  if (!code) return alert('Enter code');
  try {
    await api('/api/unlock', { method: 'POST', json: { code } });
    alert('Unlocked — re-run analysis for full detail');
  } catch (e) {
    alert(e.message);
  }
}

async function runBuild() {
  const box = el('buildOut');
  box.innerHTML = '<p style="color:var(--text-2)">Optimising…</p>';
  try {
    const r = await api('/api/construction', {
      method: 'POST',
      json: {
        questionnaire: {
          goal: el('cGoal')?.value || 'Wealth Creation',
          target_amount: parseFloat(el('cTarget')?.value || '5000000'),
          years: parseFloat(el('cYears').value) || 12,
          monthly_sip: parseFloat(el('cSip').value) || 15000,
          lumpsum: parseFloat(el('cLump')?.value || '100000'),
          risk: el('cRisk').value,
        },
      },
    });
    const a = r.allocation?.allocation_pct || {};
    const instruments = r.instruments || [];
    box.innerHTML = `
      <p style="font-weight:700">${esc(r.story?.headline || r.teaser_summary || '')}</p>
      <div class="kpis">
        <div class="kpi"><div class="l">Equity</div><div class="v">${a.equity ?? '—'}%</div></div>
        <div class="kpi"><div class="l">Debt</div><div class="v">${a.debt_mf ?? '—'}%</div></div>
        <div class="kpi"><div class="l">FD</div><div class="v">${a.fd ?? '—'}%</div></div>
        <div class="kpi"><div class="l">Expected</div><div class="v">${r.expected_return_pct ?? '—'}%</div></div>
      </div>
      <div style="margin-top:10px">
        ${instruments
          .map(
            (i) =>
              `<div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--border)"><span><strong>${esc(i.name)}</strong><br><small style="color:var(--text-3)">${esc(i.type)} · FIT ${i.fit_score ?? '—'}</small></span><strong style="color:var(--accent)">${i.allocation_pct}%</strong></div>`
          )
          .join('')}
      </div>
    `;
  } catch (e) {
    box.innerHTML = `<p style="color:var(--danger)">${esc(e.message)}</p>`;
  }
}

async function sendChat(preset) {
  const input = el('chatIn');
  const message = (preset || input.value || '').trim();
  if (!message) return;
  const log = el('chatLog');
  log.innerHTML += `<div style="text-align:right;margin:6px 0"><span style="display:inline-block;background:var(--navy-700);padding:8px 12px;border-radius:12px">${esc(message)}</span></div>`;
  input.value = '';
  try {
    const r = await api('/api/chat', { method: 'POST', json: { message, report_id: lastReportId } });
    log.innerHTML += `<div style="margin:6px 0"><span style="display:inline-block;background:var(--surface-2);border:1px solid var(--border);padding:8px 12px;border-radius:12px">${esc(r.text)}</span></div>`;
    log.scrollTop = log.scrollHeight;
  } catch (e) {
    log.innerHTML += `<div style="color:var(--danger)">${esc(e.message)}</div>`;
  }
}

async function loadStatus() {
  const out = el('statusOut');
  try {
    const r = await api('/api/training/status');
    out.textContent = JSON.stringify(r, null, 2);
  } catch (e) {
    out.textContent = e.message;
  }
}
