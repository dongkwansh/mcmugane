// app.js
class TradingApp {
    constructor() {
        this.ws = null;
        this.wsUrl = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/terminal`;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 3000;
        this.isConnected = false;
        this.language = 'ko';  // 기본값
        this.colors = {
            up: '#ef4444',    // 한국: 빨강
            down: '#0ea5e9'   // 한국: 파랑
        };
        
        this.init();
    }

    init() {
        this.setupWebSocket();
        this.setupEventListeners();
        this.startTimeUpdate();
        this.loadInitialStatus();
        this.loadAccounts();  // 계좌 목록 로드
    }

    // 시간 업데이트
    startTimeUpdate() {
        const updateTimes = () => {
            // 뉴욕 시간
            const nyTime = new Date().toLocaleString('en-US', {
                timeZone: 'America/New_York',
                hour12: false,
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            document.getElementById('ny-time').textContent = `${nyTime} ET`;
            
            // 로컬 시간 (한국)
            const localTime = new Date().toLocaleString('ko-KR', {
                timeZone: 'Asia/Seoul',
                hour12: false,
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            document.getElementById('local-time').textContent = `${localTime} KST`;
        };
        
        updateTimes();
        setInterval(updateTimes, 1000);
    }

    // 계좌 목록 로드
    async loadAccounts() {
        try {
            const response = await fetch('/api/accounts');
            const data = await response.json();
            
            const select = document.getElementById('account-select');
            if (!select) return;  // 요소가 없으면 종료
            
            select.innerHTML = '';
            
            data.accounts.forEach(acc => {
                const option = document.createElement('option');
                option.value = acc.name;
                option.textContent = acc.display_name;
                if (acc.current) {
                    option.selected = true;
                }
                select.appendChild(option);
            });
        } catch (error) {
            console.error('계좌 목록 로드 실패:', error);
        }
    }

    // 언어 설정 변경
    setLanguage(lang) {
        this.language = lang;
        
        // 버튼 활성화 상태 변경
        document.querySelectorAll('.language-toggle button').forEach(btn => {
            btn.classList.remove('active');
        });
        document.getElementById(`lang-${lang}`).classList.add('active');
        
        // 색상 변경
        if (lang === 'us') {
            this.colors = {
                up: '#10b981',    // 미국: 녹색
                down: '#ef4444'   // 미국: 빨강
            };
        } else {
            this.colors = {
                up: '#ef4444',    // 한국: 빨강
                down: '#0ea5e9'   // 한국: 파랑
            };
        }
        
        // CSS 변수 업데이트
        document.documentElement.style.setProperty('--color-up', this.colors.up);
        document.documentElement.style.setProperty('--color-down', this.colors.down);
        
        // 서버에 설정 저장
        this.saveLanguageSetting(lang);
        
        // UI 텍스트 업데이트
        this.updateUILanguage(lang);
    }

    // 서버에 언어 설정 저장
    async saveLanguageSetting(lang) {
        try {
            await fetch('/api/settings/language', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ language: lang })
            });
        } catch (error) {
            console.error('언어 설정 저장 실패:', error);
        }
    }

    // UI 텍스트 언어별 업데이트
    updateUILanguage(lang) {
        const translations = {
            ko: {
                control_title: '⚙️ 제어 센터',
                account_select: '💼 계좌 선택',
                trading_mode: '거래 모드',
                auto_trading: '🤖 자동매매',
                quick_stats: '📊 빠른 상태',
                terminal: '💻 터미널',
                help: '도움말',
                status: '상태',
                portfolio: '포트폴리오',
                orders: '주문내역',
                history: '거래내역',
                strategy_select: '전략 선택',
                interval: '실행 간격 (초)',
                apply: '적용하기',
                switch_account: '계좌 전환',
                current_account: '현재 계좌',
                account_type: '계좌 타입',
                buying_power: '매수력',
                alpaca_connection: 'Alpaca 연결',
                active_strategy: '활성 전략'
            },
            us: {
                control_title: '⚙️ Control Center',
                account_select: '💼 Account Selection',
                trading_mode: 'Trading Mode',
                auto_trading: '🤖 Auto Trading',
                quick_stats: '📊 Quick Stats',
                terminal: '💻 Terminal',
                help: 'Help',
                status: 'Status',
                portfolio: 'Portfolio',
                orders: 'Orders',
                history: 'History',
                strategy_select: 'Select Strategy',
                interval: 'Interval (sec)',
                apply: 'Apply',
                switch_account: 'Switch Account',
                current_account: 'Current Account',
                account_type: 'Account Type',
                buying_power: 'Buying Power',
                alpaca_connection: 'Alpaca Connection',
                active_strategy: 'Active Strategy'
            }
        };
        
        const t = translations[lang];
        
        // UI 텍스트 업데이트
        const elements = {
            '.control-panel h2': t.control_title,
            '.terminal-panel h2': t.terminal,
            '[data-cmd="HELP"]': t.help,
            '[data-cmd="STATUS"]': t.status,
            '[data-cmd="PORTFOLIO"]': t.portfolio,
            '[data-cmd="ORDERS"]': t.orders,
            '[data-cmd="HISTORY"]': t.history,
            '#btn-switch-account': t.switch_account
        };
        
        for (const [selector, text] of Object.entries(elements)) {
            const el = document.querySelector(selector);
            if (el) el.textContent = text;
        }
    }

    // WebSocket 연결
    setupWebSocket() {
        try {
            this.ws = new WebSocket(this.wsUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket 연결 성공');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.updateConnectionStatus(true);
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleWebSocketMessage(data);
                } catch (e) {
                    console.error('메시지 파싱 오류:', e);
                }
            };
            
            this.ws.onclose = () => {
                console.log('WebSocket 연결 종료');
                this.isConnected = false;
                this.updateConnectionStatus(false);
                this.attemptReconnect();
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket 오류:', error);
                this.isConnected = false;
                this.updateConnectionStatus(false);
            };
        } catch (error) {
            console.error('WebSocket 생성 실패:', error);
            this.attemptReconnect();
        }
    }

    // 재연결 시도
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`재연결 시도 ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
            
            setTimeout(() => {
                this.setupWebSocket();
            }, this.reconnectDelay);
        }
    }

    // WebSocket 메시지 처리
    handleWebSocketMessage(data) {
        if (data.type === 'terminal_output') {
            this.appendToTerminal(data.payload);
        } else if (data.type === 'status_update') {
            this.updateUI(data.payload);
        }
    }

    // UI 업데이트
    updateUI(status) {
        // 언어 설정 적용
        if (status.language && status.language !== this.language) {
            this.setLanguage(status.language);
        }
        
        // 계좌 정보 업데이트
        if (status.current_account) {
            const currentAccountEl = document.getElementById('current-account');
            const accountSelectEl = document.getElementById('account-select');
            const accountTypeEl = document.getElementById('account-type');
            
            if (currentAccountEl) {
                currentAccountEl.textContent = status.current_account;
            }
            if (accountSelectEl) {
                accountSelectEl.value = status.current_account;
            }
            if (accountTypeEl) {
                const accountType = status.current_account === 'LIVE' ? 'LIVE' : 'PAPER';
                accountTypeEl.textContent = accountType;
            }
        }
        
        // 시장 상태 업데이트
        if (status.market) {
            const marketStatus = document.getElementById('market-status');
            if (marketStatus) {
                const isOpen = status.market.is_open;
                
                marketStatus.className = `market-status ${isOpen ? 'open' : 'closed'}`;
                const statusText = marketStatus.querySelector('.status-text');
                if (statusText) {
                    statusText.textContent = isOpen ? 'Market Open' : 'Market Closed';
                }
                
                // 다음 개장 시간 표시
                if (!isOpen && status.market.next_open) {
                    const nextOpen = new Date(status.market.next_open);
                    const timeUntil = this.getTimeUntilOpen(nextOpen);
                    
                    this.appendToTerminal(
                        `시장 마감. 다음 개장: ${timeUntil}`,
                        'info'
                    );
                }
            }
        }
        
        // 모드 업데이트
        const currentModeEl = document.getElementById('current-mode');
        if (currentModeEl) {
            currentModeEl.textContent = status.mode;
        }
        
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        if (status.mode === 'PAPER') {
            const btnPaper = document.getElementById('btn-paper');
            if (btnPaper) btnPaper.classList.add('active');
        } else {
            const btnLive = document.getElementById('btn-live');
            if (btnLive) btnLive.classList.add('active');
        }
        
        // 자동매매 상태
        const autoToggle = document.getElementById('auto-toggle');
        const autoStatus = document.getElementById('auto-status');
        
        if (autoToggle && status.auto) {
            autoToggle.checked = status.auto.enabled;
        }
        if (autoStatus && status.auto) {
            autoStatus.textContent = status.auto.enabled ? 'ON' : 'OFF';
            autoStatus.style.color = status.auto.enabled ? 
                'var(--accent-green)' : 'var(--text-secondary)';
        }
        
        // 전략 선택
        const strategySelect = document.getElementById('strategy-select');
        if (strategySelect && status.strategies) {
            strategySelect.innerHTML = '<option value="">선택하세요</option>';
            status.strategies.forEach(strategy => {
                const option = document.createElement('option');
                option.value = strategy;
                option.textContent = strategy;
                if (strategy === status.strategy) {
                    option.selected = true;
                }
                strategySelect.appendChild(option);
            });
        }
        
        // 실행 간격
        const intervalInput = document.getElementById('interval-input');
        if (intervalInput && status.auto) {
            intervalInput.value = status.auto.interval_seconds;
        }
        
        // Alpaca 상태
        const alpacaStatus = document.getElementById('alpaca-status');
        if (alpacaStatus) {
            const alpacaText = this.language === 'ko' ? 
                (status.alpaca === 'OK' ? '연결됨' : '연결 안됨') :
                (status.alpaca === 'OK' ? 'Connected' : 'Disconnected');
            
            alpacaStatus.textContent = alpacaText;
            alpacaStatus.style.color = status.alpaca === 'OK' ? 
                'var(--accent-green)' : 'var(--accent-red)';
        }
        
        // 활성 전략
        const activeStrategy = document.getElementById('active-strategy');
        if (activeStrategy) {
            activeStrategy.textContent = 
                status.strategy || (this.language === 'ko' ? '없음' : 'None');
        }
        
        // 매수력
        const buyingPowerEl = document.getElementById('buying-power');
        if (buyingPowerEl && status.buying_power !== undefined) {
            const formattedBP = Number(status.buying_power).toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
            buyingPowerEl.textContent = formattedBP;
            
            // 색상 적용 (양수/음수)
            if (status.buying_power > 0) {
                buyingPowerEl.className = 'price-up';
            } else if (status.buying_power < 0) {
                buyingPowerEl.className = 'price-down';
            } else {
                buyingPowerEl.className = 'price-unchanged';
            }
        }
    }

    // 다음 개장까지 남은 시간 계산
    getTimeUntilOpen(nextOpenDate) {
        const now = new Date();
        const diff = nextOpenDate - now;
        const hours = Math.floor(diff / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        
        if (this.language === 'ko') {
            return `${hours}시간 ${minutes}분 후`;
        } else {
            return `in ${hours}h ${minutes}m`;
        }
    }

    // 터미널에 메시지 추가
    appendToTerminal(message, type = 'normal') {
        const terminal = document.getElementById('terminal-output');
        if (!terminal) return;
        
        const line = document.createElement('div');
        
        if (type === 'error') line.className = 'error';
        else if (type === 'success') line.className = 'success';
        else if (type === 'info') line.className = 'info';
        
        // 시간 표시 (뉴욕 시간)
        const nyTime = new Date().toLocaleString('en-US', {
            timeZone: 'America/New_York',
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        
        line.textContent = `[${nyTime} ET] ${message}`;
        
        terminal.appendChild(line);
        terminal.scrollTop = terminal.scrollHeight;
    }

    // 터미널 명령 전송
    sendCommand(command) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'terminal_input',
                payload: command
            }));
            
            // 입력한 명령을 터미널에 표시
            this.appendToTerminal(`> ${command}`, 'info');
        } else {
            const errorMsg = this.language === 'ko' ? 
                '연결되지 않았습니다. 잠시 후 다시 시도하세요.' :
                'Not connected. Please try again later.';
            this.appendToTerminal(errorMsg, 'error');
        }
    }

    // 연결 상태 업데이트
    updateConnectionStatus(connected) {
        const indicator = document.getElementById('connection-status');
        if (!indicator) return;
        
        if (connected) {
            const text = this.language === 'ko' ? '● 연결됨' : '● Connected';
            indicator.textContent = text;
            indicator.className = 'status-indicator connected';
        } else {
            const text = this.language === 'ko' ? '● 연결 끊김' : '● Disconnected';
            indicator.textContent = text;
            indicator.className = 'status-indicator disconnected';
        }
    }

    // 초기 상태 로드
    async loadInitialStatus() {
        try {
            const response = await fetch('/api/status');
            const status = await response.json();
            this.updateUI(status);
        } catch (error) {
            console.error('초기 상태 로드 실패:', error);
        }
    }

    // API 호출
    async apiCall(endpoint, method = 'GET', data = null) {
        try {
            const options = {
                method: method,
                headers: {
                    'Content-Type': 'application/json'
                }
            };
            
            if (data) {
                options.body = JSON.stringify(data);
            }
            
            const response = await fetch(endpoint, options);
            return await response.json();
        } catch (error) {
            console.error('API 호출 실패:', error);
            throw error;
        }
    }

    // 이벤트 리스너 설정
    setupEventListeners() {
        // 언어 전환 버튼
        const langKo = document.getElementById('lang-ko');
        const langUs = document.getElementById('lang-us');
        
        if (langKo) {
            langKo.addEventListener('click', () => {
                this.setLanguage('ko');
            });
        }
        
        if (langUs) {
            langUs.addEventListener('click', () => {
                this.setLanguage('us');
            });
        }
        
        // 계좌 전환 버튼
        const btnSwitchAccount = document.getElementById('btn-switch-account');
        if (btnSwitchAccount) {
            btnSwitchAccount.addEventListener('click', async () => {
                const accountSelect = document.getElementById('account-select');
                if (!accountSelect) return;
                
                const selectedAccount = accountSelect.value;
                
                const confirmMsg = this.language === 'ko' ? 
                    `${selectedAccount} 계좌로 전환하시겠습니까?` :
                    `Switch to ${selectedAccount} account?`;
                
                if (confirm(confirmMsg)) {
                    try {
                        const response = await this.apiCall('/api/account', 'POST', {
                            account: selectedAccount
                        });
                        
                        if (response.ok) {
                            const successMsg = this.language === 'ko' ?
                                `${selectedAccount} 계좌로 전환되었습니다.` :
                                `Switched to ${selectedAccount} account.`;
                            this.appendToTerminal(successMsg, 'success');
                            
                            // 계좌 목록 다시 로드
                            await this.loadAccounts();
                        }
                    } catch (error) {
                        const errorMsg = this.language === 'ko' ?
                            '계좌 전환 실패' :
                            'Failed to switch account';
                        this.appendToTerminal(`${errorMsg}: ${error}`, 'error');
                    }
                }
            });
        }
        
        // 터미널 입력
        const terminalInput = document.getElementById('terminal-input');
        if (terminalInput) {
            terminalInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && e.target.value.trim()) {
                    this.sendCommand(e.target.value.trim());
                    e.target.value = '';
                }
            });
        }
        
        // 빠른 명령 버튼
        document.querySelectorAll('.quick-cmd').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const cmd = e.target.dataset.cmd;
                if (cmd) {
                    this.sendCommand(cmd);
                }
            });
        });
        
        // 모드 전환 버튼
        const btnPaper = document.getElementById('btn-paper');
        const btnLive = document.getElementById('btn-live');
        
        if (btnPaper) {
            btnPaper.addEventListener('click', async () => {
                await this.apiCall('/api/mode', 'POST', { mode: 'PAPER' });
            });
        }
        
        if (btnLive) {
            btnLive.addEventListener('click', async () => {
                const confirmMsg = this.language === 'ko' ? 
                    '실거래 모드로 전환하시겠습니까?' :
                    'Switch to LIVE trading mode?';
                
                if (confirm(confirmMsg)) {
                    await this.apiCall('/api/mode', 'POST', { mode: 'LIVE' });
                }
            });
        }
        
        // 자동매매 토글
        const autoToggle = document.getElementById('auto-toggle');
        if (autoToggle) {
            autoToggle.addEventListener('change', async (e) => {
                const strategySelect = document.getElementById('strategy-select');
                const strategy = strategySelect ? strategySelect.value : '';
                
                if (e.target.checked && !strategy) {
                    const alertMsg = this.language === 'ko' ? 
                        '먼저 전략을 선택하세요.' :
                        'Please select a strategy first.';
                    alert(alertMsg);
                    e.target.checked = false;
                    return;
                }
                
                await this.apiCall('/api/auto', 'POST', {
                    enabled: e.target.checked,
                    strategy: strategy
                });
            });
        }
        
        // 적용 버튼
        const btnApply = document.getElementById('btn-apply');
        if (btnApply) {
            btnApply.addEventListener('click', async () => {
                const strategySelect = document.getElementById('strategy-select');
                const intervalInput = document.getElementById('interval-input');
                const autoToggle = document.getElementById('auto-toggle');
                
                const strategy = strategySelect ? strategySelect.value : '';
                const interval = intervalInput ? parseInt(intervalInput.value) : 60;
                
                if (!strategy) {
                    const alertMsg = this.language === 'ko' ? 
                        '전략을 선택하세요.' :
                        'Please select a strategy.';
                    alert(alertMsg);
                    return;
                }
                
                if (interval < 10) {
                    const alertMsg = this.language === 'ko' ? 
                        '실행 간격은 최소 10초 이상이어야 합니다.' :
                        'Interval must be at least 10 seconds.';
                    alert(alertMsg);
                    return;
                }
                
                await this.apiCall('/api/auto', 'POST', {
                    enabled: autoToggle ? autoToggle.checked : false,
                    strategy: strategy,
                    interval_seconds: interval
                });
                
                const successMsg = this.language === 'ko' ? 
                    '설정이 적용되었습니다.' :
                    'Settings applied successfully.';
                this.appendToTerminal(successMsg, 'success');
            });
        }
    }
}

// 앱 시작
document.addEventListener('DOMContentLoaded', () => {
    new TradingApp();
});