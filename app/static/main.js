const el = (id) => document.getElementById(id);
const fmt = (n) => (n===null||n===undefined) ? '-' : n;

let ws = null;
let historyBuf = [];
let histIdx = -1;

function appendTerm(s) {
  const t = el('terminal');
  const p = document.createElement('pre');
  p.textContent = s;
  t.appendChild(p);
  t.scrollTop = t.scrollHeight;
}

function appendSys(s) {
  const t = el('syslog');
  const p = document.createElement('div');
  p.textContent = s;
  t.appendChild(p);
  t.scrollTop = t.scrollHeight;
}

function setAutoLines(lines) {
  const t = el('autoStatus');
  t.innerHTML = '';
  (lines || []).forEach(line => {
    const p = document.createElement('div');
    p.textContent = line;
    t.appendChild(p);
  });
  t.scrollTop = t.scrollHeight;
}

async function loadAccounts() {
  const res = await fetch('/api/accounts');
  const data = await res.json();
  const sel = el('accountSelect');
  sel.innerHTML = '';
  data.accounts.forEach(a => {
    const opt = document.createElement('option');
    opt.value = a; opt.text = a;
    if (a === data.selected) opt.selected = true;
    sel.appendChild(opt);
  });
}

async function loadAccountInfo() {
  const res = await fetch('/api/account-info');
  const data = await res.json();
  if (data.error) {
    el('acctInfo').innerHTML = '계좌 정보를 불러오지 못했습니다: ' + data.error;
    return;
  }
  const acc = data;
  el('acctInfo').innerHTML =
    `계좌: ${fmt(acc.account_number)} / 상태: ${fmt(acc.status)}<br>` +
    `Buying Power: $${fmt(acc.buying_power)} / Equity: $${fmt(acc.equity)} / PV: $${fmt(acc.portfolio_value)}<br>` +
    `PDT: ${fmt(acc.pattern_day_trader)} / DayTrade Cnt: ${fmt(acc.daytrade_count)}`;
  const clk = data.clock || {};
  el('clockInfo').textContent = `시장: ${clk.is_open ? '열림' : '닫힘'} / 서버시각: ${clk.timestamp || ''}`;
}

async function loadStrategies() {
  const res = await fetch('/api/strategies');
  const data = await res.json();
  const sel = el('strategySelect');
  sel.innerHTML = '';
  (data.files || []).forEach(f => {
    const opt = document.createElement('option');
    opt.value = f; opt.text = f;
    sel.appendChild(opt);
  });
  el('autoState').textContent = data.running ? ('실행중: ' + data.current) : '(중지됨)';
}

async function loadMyETF() {
  const res = await fetch('/api/myetf');
  const data = await res.json();
  const bad = (data.myetf || []).filter(x => !x.valid);
  el('myetfInfo').textContent = bad.length ? `⚠ myETF ${bad.map(x=>x.name).join(', ')} 합계!=100 (비활성)` : 'myETF 정상';
}

async function reloadJSON() {
  await fetch('/api/strategies/reload', {method:'POST'});
  appendSys('전략/myETF JSON 재로딩 요청 완료.');
  await Promise.all([loadStrategies(), loadMyETF()]);
}

async function startAuto() {
  const f = el('strategySelect').value;
  if (!f) { appendSys('전략 파일을 선택하세요.'); return; }
  const res = await fetch('/api/autopilot/start', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({file:f})});
  const data = await res.json();
  if (data.error) { appendSys('오류: ' + data.error); return; }
  appendSys('자동매매 시작 요청 완료.');
  await loadStrategies();
}

async function stopAuto() {
  await fetch('/api/autopilot/stop', {method:'POST'});
  appendSys('자동매매 중지 요청 완료.');
  await loadStrategies();
}

async function pollAutoStatus() {
  const res = await fetch('/api/autopilot/status');
  const data = await res.json();
  setAutoLines(data.lines || []);
  el('autoState').textContent = data.running ? '실행중' : '(중지됨)';
}

function connectWS() {
  ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws/terminal');
  ws.onmessage = (ev) => appendTerm(ev.data);
  ws.onopen = () => appendTerm('연결됨.');
  ws.onclose = () => appendTerm('연결이 종료되었습니다.');
}

function sendCmd() {
  const v = el('cmdInput').value;
  if (!v) return;
  ws.send(v);
  appendTerm('>>> ' + v);
  historyBuf.push(v);
  if (historyBuf.length > 10) historyBuf.shift();
  histIdx = historyBuf.length;
  el('cmdInput').value = '';
}

function setupInputHistory() {
  el('cmdInput').addEventListener('keydown', (e) => {
    if (e.key === 'ArrowUp') {
      if (histIdx > 0) { histIdx--; el('cmdInput').value = historyBuf[histIdx] || ''; }
      e.preventDefault();
    } else if (e.key === 'ArrowDown') {
      if (histIdx < historyBuf.length) { histIdx++; el('cmdInput').value = historyBuf[histIdx] || ''; }
      e.preventDefault();
    } else if (e.key === 'Enter') {
      sendCmd();
    }
  });
  el('sendBtn').addEventListener('click', sendCmd);
}

async function main() {
  await loadAccounts();
  await loadAccountInfo();
  await loadStrategies();
  await loadMyETF();
  connectWS();
  setupInputHistory();
  el('accountSelect').addEventListener('change', async () => {
    const a = el('accountSelect').value;
    await fetch('/api/select-account', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({account:a})});
    appendSys('계좌 전환: ' + a);
    await Promise.all([loadAccountInfo(), loadStrategies(), loadMyETF()]);
  });
  el('reloadBtn').addEventListener('click', reloadJSON);
  el('startAutoBtn').addEventListener('click', startAuto);
  el('stopAutoBtn').addEventListener('click', stopAuto);
  el('extHoursToggle').addEventListener('change', async () => {
    await fetch('/api/extended-hours', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({enabled:el('extHoursToggle').checked})});
  });
  setInterval(loadAccountInfo, 15000);
  setInterval(pollAutoStatus, 3000);
}

main();
