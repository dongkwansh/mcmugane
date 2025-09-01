document.addEventListener("DOMContentLoaded", () => {
  // --- DOM 요소를 쉽게 선택하기 위한 헬퍼 함수 ---
  const $ = (s) => document.querySelector(s);

  // --- 상태 관리 객체 ---
  const state = {
    ws: null,
    wsUrl: `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/terminal`,
    reconnectInterval: 3000, // 재연결 시도 간격 (3초)
  };

  // --- 백엔드 API 호출 함수 ---
  const api = (path, options = {}) =>
    fetch(path, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    }).then(res => {
      if (!res.ok) throw new Error(`HTTP 오류! 상태: ${res.status}`);
      return res.json();
    });

  // --- 터미널 UI 관리 객체 ---
  const term = {
    el: $("#term"),
    append(text, type = "normal") {
      const line = document.createElement("div");
      line.textContent = text;
      if (type === "system") line.style.color = "#6c7a89";
      if (type === "error") line.style.color = "#d91c1c";
      this.el.appendChild(line);
      this.el.scrollTop = this.el.scrollHeight; // 항상 맨 아래로 스크롤
    },
  };

  // --- WebSocket 연결 및 관리 ---
  const wsManager = {
    connect() {
      // 이미 연결된 상태면 중복 실행 방지
      if (state.ws && state.ws.readyState === WebSocket.OPEN) return;
      
      state.ws = new WebSocket(state.wsUrl);
      
      state.ws.onopen = () => {
        console.log("WebSocket 연결 성공.");
        term.append("[System] 터미널 서버에 연결되었습니다.", "system");
      };

      // 서버로부터 메시지를 받았을 때 처리
      state.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          // 서버가 상태 업데이트를 보냈을 경우 UI 전체를 갱신
          if (data.type === 'status_update') {
            updateUI(data.payload);
          } 
          // 일반적인 터미널 메시지일 경우 터미널에만 출력
          else if (data.type === 'terminal_output') {
            term.append(data.payload);
          }
        } catch (e) {
          // JSON 파싱 실패 시 일반 텍스트로 처리
          term.append(event.data);
        }
      };
      
      // 연결이 끊겼을 때 처리
      state.ws.onclose = () => {
        console.log("WebSocket 연결 끊김. 재연결 시도...");
        term.append("[System] 연결이 끊겼습니다. 3초 후 재연결합니다.", "error");
        setTimeout(() => this.connect(), state.reconnectInterval);
      };
      
      // 오류 발생 시 처리
      state.ws.onerror = (error) => {
        console.error("WebSocket 오류:", error);
        term.append("[System] WebSocket 오류가 발생했습니다.", "error");
        state.ws.close();
      };
    },
    // 서버로 메시지(터미널 명령어) 전송
    send(data) {
      if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify({ type: 'terminal_input', payload: data }));
      } else {
        term.append("[System] 서버와 연결되지 않아 명령을 보낼 수 없습니다.", "error");
      }
    }
  };

  // --- UI 상태를 업데이트하는 함수 ---
  function updateUI(status) {
    const modeDisplay = $("#modeDisplay");
    const autoDisplay = $("#autoDisplay");
    
    // 모드 UI 업데이트 (PAPER/LIVE)
    $("#modeVal").innerText = status.mode;
    modeDisplay.className = `status-display ${status.mode.toLowerCase()}`;
    
    // 자동매매 상태 UI 업데이트 (ON/OFF)
    $("#autoVal").innerText = status.auto.enabled ? "ON" : "OFF";
    autoDisplay.className = `status-display ${status.auto.enabled ? 'on' : 'off'}`;
    $("#intervalSec").value = status.auto.interval_seconds;

    // 현재 적용된 전략 텍스트 업데이트
    $("#curStrat").innerText = status.auto.strategy || "선택되지 않음";

    // 전략 선택 드롭다운 업데이트
    const strategySelect = $("#strategySel");
    const currentSelection = strategySelect.value;
    strategySelect.innerHTML = "";
    status.strategies.forEach(name => {
      const option = new Option(name, name);
      strategySelect.appendChild(option);
    });
    // 서버의 현재 전략을 기본값으로 선택
    strategySelect.value = status.auto.strategy || currentSelection || '';
  }

  // --- 각종 이벤트 리스너 설정 ---
  function setupEventListeners() {
    // 터미널에서 Enter 키 입력 시 명령어 전송
    $("#termInput").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && e.target.value.trim() !== "") {
        e.preventDefault();
        wsManager.send(e.target.value);
        e.target.value = "";
      }
    });

    // 모드 전환 버튼 클릭
    $("#btnMode").onclick = async () => {
      const nextMode = $("#modeVal").innerText === "PAPER" ? "LIVE" : "PAPER";
      await api(`/api/mode?mode=${nextMode}`, { method: "POST" });
    };

    // 자동매매 ON/OFF 버튼 클릭
    $("#btnAuto").onclick = async () => {
      const isEnabled = $("#autoVal").innerText === "ON";
      const strategy = $("#strategySel").value;
      await api(`/api/auto?enabled=${!isEnabled}&strategy=${encodeURIComponent(strategy)}`, { method: "POST" });
    };
    
    // 전략/간격 적용 버튼 클릭
    $("#btnApply").onclick = async () => {
      const strategy = $("#strategySel").value;
      if (!strategy) {
        term.append("[Error] 적용할 전략을 먼저 선택해주세요.", "error");
        return;
      }
      const interval = parseInt($("#intervalSec").value, 10) || 60;
      await api(`/api/auto?enabled=true&strategy=${encodeURIComponent(strategy)}&interval_seconds=${interval}`, { method: "POST" });
    };
  }

  // --- 애플리케이션 초기화 ---
  async function init() {
    term.append("[System] UI 초기화 중...", "system");
    setupEventListeners();
    // 초기 상태는 API로 한 번만 가져오고, 이후는 WebSocket으로 받음
    const initialStatus = await api("/api/status");
    updateUI(initialStatus);
    wsManager.connect();
    term.append("[System] mcmugane 클라이언트가 준비되었습니다.", "system");
  }

  init();
});