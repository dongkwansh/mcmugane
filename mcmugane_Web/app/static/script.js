// base path 자동 인지(/cli 경로 프록시 대응)
const base = (location.pathname.startsWith('/cli')) ? '/cli' : '';

// 토큰 관리 및 인증 확인
function getToken() { return localStorage.getItem('authToken') || ''; }
async function authFetch(url, options={}) {
  options.headers = options.headers || {};
  options.headers['Authorization'] = 'Bearer ' + getToken();
  return fetch(base + url, options);
}
async function ensureAuth() {
  const t = getToken();
  if (!t) { window.location.href = base + '/login'; return false; }
  const res = await authFetch('/api/me');
  if (!res.ok) { window.location.href = base + '/login'; return false; }
  return true;
}

// UI 동작
async function loadAccounts() {
  const res = await authFetch('/api/accounts'); const data = await res.json();
  const sel = document.getElementById('accountSelect'); sel.innerHTML='';
  data.forEach(a => { const opt = document.createElement('option'); opt.value=a.id; opt.innerText=`${a.name} (${a.paper?'paper':'live'})`; sel.appendChild(opt); });
}
async function loadAlgos() {
  const res = await authFetch('/api/algorithms'); const data = await res.json();
  const sel = document.getElementById('algoSelect'); sel.innerHTML='';
  data.forEach(a => { const opt = document.createElement('option'); opt.value=a._file; opt.innerText=a.name; sel.appendChild(opt); });
}
async function refreshRuns() {
  const res = await authFetch('/api/runs'); const data = await res.json();
  document.getElementById('runsPane').innerText = JSON.stringify(data, null, 2);
}
async function startRun() {
  const account_id = document.getElementById('accountSelect').value;
  const algorithm_file = document.getElementById('algoSelect').value;
  const symbols = document.getElementById('symbolsInput').value;
  const sizing = {type: document.getElementById('sizeType').value, value: parseFloat(document.getElementById('sizeValue').value)};
  const res = await authFetch('/api/start', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({account_id, algorithm_file, symbols, sizing})
  });
  const out = await res.json(); log(`START -> ${JSON.stringify(out)}`); refreshRuns();
}
async function stopRun() {
  const rid = prompt('Run ID to stop?');
  if (!rid) return;
  const res = await authFetch('/api/stop', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({run_id: rid})
  });
  const out = await res.json(); log(`STOP -> ${JSON.stringify(out)}`); refreshRuns();
}
function log(t) { const pane = document.getElementById('logPane'); pane.innerText += `\n${t}`; pane.scrollTop = pane.scrollHeight; }

let ws, currentFmt='table';
function setupWS() {
  let wsProto = (location.protocol === 'https:') ? 'wss' : 'ws';
  ws = new WebSocket(`${wsProto}://${location.host}${base}/ws?token=${encodeURIComponent(getToken())}`);
  ws.onopen = () => { document.getElementById('wsStatus').innerText='WS: connected'; };
  ws.onclose = () => { document.getElementById('wsStatus').innerText='WS: disconnected'; setTimeout(setupWS, 2000); };
  ws.onmessage = (ev) => { log(ev.data); };
  const term = document.getElementById('terminalInput');
  term.addEventListener('keydown', (e) => { if (e.key === 'Enter') { ws.send(term.value); term.value=''; } });
  const fmtBtn = document.getElementById('fmtBtn');
  fmtBtn.addEventListener('click', () => {
    currentFmt = (currentFmt === 'table') ? 'json' : 'table';
    ws.send('FORMAT ' + currentFmt);
    fmtBtn.textContent = 'FORMAT: ' + currentFmt;
  });
}

document.getElementById('startBtn').addEventListener('click', startRun);
document.getElementById('stopBtn').addEventListener('click', stopRun);

ensureAuth().then(ok => { if (ok) { loadAccounts(); loadAlgos(); refreshRuns(); setupWS(); } });
