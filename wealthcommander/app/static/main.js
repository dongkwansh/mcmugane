// Enhanced Wealth Commander v0.2 Client
const el = (id) => document.getElementById(id);

// 천단위 콤마 포맷터 개선
const fmt = (n) => {
  if (n === null || n === undefined) return '-';
  if (typeof n === 'string') {
    // 이미 포맷된 경우
    if (n.includes(',')) return n;
    // 숫자 문자열인 경우
    const num = parseFloat(n);
    if (!isNaN(num)) {
      return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    return n;
  }
  if (typeof n === 'number') {
    return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  return n;
};

let ws = null;
let wsRetryCount = 0;
let wsRetryTimer = null;
let historyBuf = [];
let histIdx = -1;

// 터미널 출력 - 테이블 형식 지원
function appendTerm(s) {
  const t = el('terminal');
  const pre = document.createElement('pre');
  
  // 컬러 코딩 (미국식 - 상승 녹색, 하락 적색)
  if (s.startsWith('>>>')) {
    pre.style.color = '#3b82f6';
    pre.style.fontWeight = '500';
  } else if (s.startsWith('✅')) {
    pre.style.color = '#10b981';
  } else if (s.startsWith('❌')) {
    pre.style.color = '#ef4444';
  } else if (s.startsWith('⚠️')) {
    pre.style.color = '#f59e0b';
  } else if (s.startsWith('🟢')) {
    pre.style.color = '#10b981';
  } else if (s.startsWith('🔴')) {
    pre.style.color = '#ef4444';
  } else if (s.includes('=====')) {
    pre.style.color = '#6b7280';
    pre.style.borderTop = '1px solid #374151';
    pre.style.paddingTop = '0.5rem';
    pre.style.marginTop = '0.5rem';
  }
  
  pre.textContent = s;
  t.appendChild(pre);
  t.scrollTop = t.scrollHeight;
}

// 시스템 로그 출력
function appendSys(s) {
  const t = el('syslog');
  const div = document.createElement('div');
  div.className = 'system-message';
  
  // 타임스탬프 추가
  const now = new Date();
  const time = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  div.textContent = `[${time}] ${s}`;
  
  t.appendChild(div);
  
  // 최대 50개 메시지 유지
  while (t.children.length > 50) {
    t.removeChild(t.firstChild);
  }
  
  t.scrollTop = t.scrollHeight;
}

// 터미널 클리어
function clearTerminal() {
  el('terminal').innerHTML = '';
  appendTerm('🧹 터미널 클리어됨');
}

// 자동매매 상태 업데이트
function setAutoLines(lines) {
  const t = el('autoStatus');
  t.innerHTML = '';
  (lines || []).forEach(line => {
    const div = document.createElement('div');
    div.className = 'status-line';
    
    // 시간 표시 강조
    if (line.includes('[') && line.includes(']')) {
      const timeMatch = line.match(/\[(.*?)\]/);
      if (timeMatch) {
        const [time, ...rest] = line.split(']');
        div.innerHTML = `<span style="color: var(--text-muted)">${time}]</span>${rest.join(']')}`;
      } else {
        div.textContent = line;
      }
    } else {
      div.textContent = line;
    }
    
    t.appendChild(div);
  });
  t.scrollTop = t.scrollHeight;
}

// 계좌 목록 로드
async function loadAccounts() {
  try {
    const res = await fetch('/api/accounts');
    const data = await res.json();
    const sel = el('accountSelect');
    sel.innerHTML = '';
    
    data.accounts.forEach(a => {
      const opt = document.createElement('option');
      opt.value = a;
      opt.text = a.toUpperCase();
      if (a === data.selected) opt.selected = true;
      sel.appendChild(opt);
    });
  } catch (e) {
    console.error('계좌 목록 로드 실패:', e);
    appendSys('계좌 목록 로드 실패');
  }
}

// 계좌 정보 로드
async function loadAccountInfo() {
  try {
    const res = await fetch('/api/account-info');
    const data = await res.json();
    
    if (data.error) {
      appendSys('계좌 정보 로드 실패: ' + data.error);
      return;
    }
    
    // 계좌 정보 업데이트 (천단위 콤마 적용)
    el('buyingPower').textContent = '$' + fmt(data.buying_power);
    el('equity').textContent = '$' + fmt(data.equity);
    el('portfolioValue').textContent = '$' + fmt(data.portfolio_value);
    el('dayTradeCount').textContent = data.daytrade_count || '0';
    
    // PDT 상태에 따라 색상 변경
    if (data.pattern_day_trader) {
      el('dayTradeCount').classList.add('danger');
    } else {
      el('dayTradeCount').classList.remove('danger');
    }
    
    // 시장 상태 업데이트
    const clock = data.clock || {};
    const isOpen = clock.is_open;
    const marketDot = el('marketDot');
    const marketStatus = el('marketStatus');
    
    if (isOpen) {
      marketDot.className = 'status-dot open';
      marketStatus.textContent = '시장 열림';
      marketStatus.style.color = 'var(--success)';
    } else {
      marketDot.className = 'status-dot closed';
      marketStatus.textContent = '시장 닫힘';
      marketStatus.style.color = 'var(--danger)';
    }
    
    // 뉴욕 시간 표시
    if (clock.timestamp) {
      const serverTime = new Date(clock.timestamp);
      const nyTime = serverTime.toLocaleTimeString('en-US', { 
        timeZone: 'America/New_York',
        hour: '2-digit', 
        minute: '2-digit',
        second: '2-digit'
      });
      el('serverTime').textContent = 'NY: ' + nyTime;
    }
    
  } catch (e) {
    console.error('계좌 정보 로드 실패:', e);
  }
}

// 전략 목록 로드
async function loadStrategies() {
  try {
    const res = await fetch('/api/strategies');
    const data = await res.json();
    const sel = el('strategySelect');
    sel.innerHTML = '';
    
    if (data.files && data.files.length > 0) {
      (data.files || []).forEach(f => {
        const opt = document.createElement('option');
        opt.value = f;
        // 파일명을 더 읽기 쉽게 표시
        const displayName = f.replace(/_/g, ' ').replace('.json', '');
        opt.text = displayName;
        sel.appendChild(opt);
      });
    } else {
      const opt = document.createElement('option');
      opt.value = '';
      opt.text = '(전략 없음)';
      sel.appendChild(opt);
    }
    
    // 자동매매 상태 업데이트
    const indicator = el('autoIndicator');
    const state = el('autoState');
    
    if (data.running) {
      indicator.className = 'status-indicator running';
      indicator.querySelector('.status-dot').className = 'status-dot open';
      state.textContent = '실행중: ' + (data.current || '');
    } else {
      indicator.className = 'status-indicator stopped';
      indicator.querySelector('.status-dot').className = 'status-dot closed';
      state.textContent = '대기중';
    }
    
  } catch (e) {
    console.error('전략 로드 실패:', e);
    appendSys('전략 목록 로드 실패');
  }
}

// myETF 정보 로드
async function loadMyETF() {
  try {
    const res = await fetch('/api/myetf');
    const data = await res.json();
    const info = el('myetfInfo');
    
    const invalid = (data.myetf || []).filter(x => !x.valid);
    
    if (invalid.length > 0) {
      info.className = 'myetf-info warning';
      info.textContent = `⚠️ myETF 오류: ${invalid.map(x => x.name).join(', ')} (비중 합 ≠ 100%)`;
    } else {
      info.className = 'myetf-info';
      const count = (data.myetf || []).length;
      info.textContent = `✅ myETF ${count}개 정상`;
    }
    
  } catch (e) {
    console.error('myETF 로드 실패:', e);
  }
}

// JSON 재로딩
async function reloadJSON() {
  try {
    appendSys('전략/myETF JSON 재로딩 중...');
    await fetch('/api/strategies/reload', { method: 'POST' });
    await Promise.all([loadStrategies(), loadMyETF()]);
    appendSys('전략/myETF JSON 재로딩 완료');
  } catch (e) {
    appendSys('재로딩 실패: ' + e.message);
  }
}

// 자동매매 시작
async function startAuto() {
  const f = el('strategySelect').value;
  if (!f) {
    appendSys('전략 파일을 선택하세요.');
    return;
  }
  
  try {
    const res = await fetch('/api/autopilot/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file: f })
    });
    
    const data = await res.json();
    if (data.error) {
      appendSys('자동매매 시작 실패: ' + data.error);
      return;
    }
    
    appendSys('자동매매 시작됨');
    await loadStrategies();
  } catch (e) {
    appendSys('자동매매 시작 오류: ' + e.message);
  }
}

// 자동매매 중지
async function stopAuto() {
  try {
    await fetch('/api/autopilot/stop', { method: 'POST' });
    appendSys('자동매매 중지됨');
    await loadStrategies();
  } catch (e) {
    appendSys('자동매매 중지 오류: ' + e.message);
  }
}

// 자동매매 상태 폴링
async function pollAutoStatus() {
  try {
    const res = await fetch('/api/autopilot/status');
    const data = await res.json();
    setAutoLines(data.lines || []);
    
    // 상태 인디케이터 업데이트
    const indicator = el('autoIndicator');
    const state = el('autoState');
    
    if (data.running) {
      indicator.className = 'status-indicator running';
      indicator.querySelector('.status-dot').className = 'status-dot open';
      if (!state.textContent.includes('실행중')) {
        state.textContent = '실행중';
      }
    } else {
      indicator.className = 'status-indicator stopped';
      indicator.querySelector('.status-dot').className = 'status-dot closed';
      if (state.textContent !== '대기중') {
        state.textContent = '대기중';
      }
    }
  } catch (e) {
    console.error('자동매매 상태 폴링 실패:', e);
  }
}

// WebSocket 연결
function connectWS() {
  const protocol = location.protocol === 'https:' ? 'wss://' : 'ws://';
  const wsUrl = protocol + location.host + '/ws/terminal';
  
  try {
    ws = new WebSocket(wsUrl);
    
    ws.onmessage = (ev) => {
      // 시스템 메시지는 터미널에 표시하지 않음
      if (!ev.data.startsWith('[시스템]')) {
        appendTerm(ev.data);
      }
    };
    
    ws.onopen = () => {
      appendTerm('🔗 터미널 연결됨');
      wsRetryCount = 0;
      
      // 재연결 타이머 클리어
      if (wsRetryTimer) {
        clearTimeout(wsRetryTimer);
        wsRetryTimer = null;
      }
    };
    
    ws.onclose = () => {
      appendTerm('⚠️ 터미널 연결 끊김');
      
      // 자동 재연결 (최대 5회)
      if (wsRetryCount < 5) {
        wsRetryCount++;
        const delay = Math.min(1000 * Math.pow(2, wsRetryCount), 10000);
        appendTerm(`🔄 ${delay/1000}초 후 재연결 시도... (${wsRetryCount}/5)`);
        
        wsRetryTimer = setTimeout(() => {
          connectWS();
        }, delay);
      } else {
        appendTerm('❌ 재연결 실패. 페이지를 새로고침하세요.');
      }
    };
    
    ws.onerror = (err) => {
      console.error('WebSocket 오류:', err);
      appendTerm('❌ 연결 오류 발생');
    };
    
  } catch (e) {
    console.error('WebSocket 연결 실패:', e);
    appendTerm('❌ 터미널 연결 실패');
  }
}

// 명령 전송 함수 개선
function sendCmd() {
  const input = el('cmdInput');
  let v = input.value.trim();
  
  // 빈 입력 또는 공백만 입력된 경우 처리
  if (!v || v === ' ') {
    // 대화형 모드에서 Enter 키 대신 Space 처리
    if (v === ' ') {
      v = '';  // 빈 문자열로 전송
    } else {
      return;
    }
  }
  
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    appendTerm('⚠️ 터미널이 연결되지 않았습니다. 재연결 중...');
    connectWS();
    return;
  }
  
  try {
    ws.send(v);
    if (v) {
      appendTerm('>>> ' + v);
    } else {
      appendTerm('>>> [Enter]');
    }
    
    // 히스토리에 추가 (중복 제거, 빈 문자열 제외)
    if (v && (historyBuf.length === 0 || historyBuf[historyBuf.length - 1] !== v)) {
      historyBuf.push(v);
      if (historyBuf.length > 20) historyBuf.shift();
    }
    histIdx = historyBuf.length;
    
    // 입력 필드 초기화
    input.value = '';
    
    // 포커스 유지
    input.focus();
  } catch (e) {
    console.error('명령 전송 실패:', e);
    appendTerm('❌ 명령 전송 실패');
  }
}

// Help 표시
function showHelp() {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    appendTerm('⚠️ 터미널이 연결되지 않았습니다.');
    return;
  }
  
  try {
    ws.send('help');
    appendTerm('>>> help');
  } catch (e) {
    console.error('Help 명령 실패:', e);
  }
}

// 입력 히스토리 설정
function setupInputHistory() {
  const input = el('cmdInput');
  
  // Enter 키 이벤트를 input 요소에 직접 바인딩
  input.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendCmd();
    }
  });
  
  // 화살표 키는 keydown으로 처리
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (histIdx > 0) {
        histIdx--;
        input.value = historyBuf[histIdx] || '';
        // 커서를 끝으로 이동
        setTimeout(() => {
          input.setSelectionRange(input.value.length, input.value.length);
        }, 0);
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (histIdx < historyBuf.length - 1) {
        histIdx++;
        input.value = historyBuf[histIdx] || '';
      } else {
        histIdx = historyBuf.length;
        input.value = '';
      }
      // 커서를 끝으로 이동
      setTimeout(() => {
        input.setSelectionRange(input.value.length, input.value.length);
      }, 0);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      input.value = '';
      histIdx = historyBuf.length;
    }
  });
  
  // 버튼 클릭 이벤트
  el('sendBtn').addEventListener('click', (e) => {
    e.preventDefault();
    sendCmd();
  });
  
  el('clearBtn').addEventListener('click', (e) => {
    e.preventDefault();
    clearTerminal();
  });
  
  el('helpBtn').addEventListener('click', (e) => {
    e.preventDefault();
    showHelp();
  });
}

// 이벤트 리스너 설정
function setupEventListeners() {
  // 계좌 선택
  el('accountSelect').addEventListener('change', async () => {
    const account = el('accountSelect').value;
    try {
      const res = await fetch('/api/select-account', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account })
      });
      
      const data = await res.json();
      if (data.error) {
        appendSys('계좌 전환 실패: ' + data.error);
        return;
      }
      
      appendSys(`계좌 전환: ${account.toUpperCase()}`);
      await Promise.all([loadAccountInfo(), loadStrategies(), loadMyETF()]);
      
    } catch (e) {
      appendSys('계좌 전환 오류: ' + e.message);
    }
  });
  
  // JSON 재로딩
  el('reloadBtn').addEventListener('click', reloadJSON);
  
  // 자동매매 제어
  el('startAutoBtn').addEventListener('click', startAuto);
  el('stopAutoBtn').addEventListener('click', stopAuto);
  
  // Extended Hours 토글
  el('extHoursToggle').addEventListener('change', async () => {
    const enabled = el('extHoursToggle').checked;
    try {
      await fetch('/api/extended-hours', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
      });
      appendSys(`Extended Hours ${enabled ? 'ON' : 'OFF'}`);
    } catch (e) {
      appendSys('Extended Hours 설정 실패');
    }
  });
  
  // 키보드 단축키
  document.addEventListener('keydown', (e) => {
    // Ctrl+L: 터미널 클리어
    if (e.ctrlKey && e.key === 'l') {
      e.preventDefault();
      clearTerminal();
    }
    
    // Ctrl+K: 시스템 로그 클리어
    if (e.ctrlKey && e.key === 'k') {
      e.preventDefault();
      el('syslog').innerHTML = '';
      appendSys('시스템 로그 클리어됨');
    }
    
    // Ctrl+/: 터미널 입력 포커스
    if (e.ctrlKey && e.key === '/') {
      e.preventDefault();
      el('cmdInput').focus();
    }
    
    // Ctrl+H: Help
    if (e.ctrlKey && e.key === 'h') {
      e.preventDefault();
      showHelp();
    }
  });
}

// 초기화
async function init() {
  try {
    appendSys('Wealth Commander v0.2 시작');
    
    // 초기 데이터 로드
    await Promise.all([
      loadAccounts(),
      loadAccountInfo(),
      loadStrategies(),
      loadMyETF()
    ]);
    
    // WebSocket 연결
    connectWS();
    
    // 입력 히스토리 설정
    setupInputHistory();
    
    // 이벤트 리스너 설정
    setupEventListeners();
    
    // 주기적 업데이트
    setInterval(loadAccountInfo, 15000);  // 15초마다 계좌 정보
    setInterval(pollAutoStatus, 3000);    // 3초마다 자동매매 상태
    
    // 5분마다 전략 목록 갱신
    setInterval(async () => {
      await loadStrategies();
    }, 300000);
    
    appendSys('초기화 완료');
    
    // 터미널 입력에 포커스
    el('cmdInput').focus();
    
  } catch (e) {
    console.error('초기화 실패:', e);
    appendSys('초기화 실패: ' + e.message);
  }
}

// 페이지 로드 시 실행
document.addEventListener('DOMContentLoaded', init);

// 페이지 언로드 시 WebSocket 정리
window.addEventListener('beforeunload', () => {
  if (ws) {
    ws.close();
  }
  if (wsRetryTimer) {
    clearTimeout(wsRetryTimer);
  }
});