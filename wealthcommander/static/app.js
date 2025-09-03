/**
 * WealthCommander - Optimized JavaScript for Synology NAS
 * Container-optimized with minimal dependencies
 */

class WealthCommanderApp {
    constructor() {
        this.websocket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectInterval = 3000;
        
        // State
        this.isConnected = false;
        this.textWrapEnabled = true;
        this.commandHistory = [];
        
        // Elements
        this.elements = {
            // Status indicators
            connectionStatus: document.getElementById('connection-status'),
            marketStatus: document.getElementById('market-status'),
            currentTime: document.getElementById('current-time'),
            
            // Account info (removed)
            // accountSelect: document.getElementById('account-select'),
            // btnSwitchAccount: document.getElementById('btn-switch-account'),
            // portfolioValue: document.getElementById('portfolio-value'),
            // buyingPower: document.getElementById('buying-power'),
            // cashValue: document.getElementById('cash-value'),
            
            // Auto trading
            autoStatus: document.getElementById('auto-status'),
            autoStatusText: document.getElementById('auto-status-text'),
            btnStartAuto: document.getElementById('btn-start-auto'),
            btnStopAuto: document.getElementById('btn-stop-auto'),
            currentStrategy: document.getElementById('current-strategy'),
            nextRun: document.getElementById('next-run'),
            
            // Terminal
            terminalOutput: document.getElementById('terminal-output'),
            terminalInput: document.getElementById('terminal-input'),
            btnSend: document.getElementById('btn-send'),
            btnClear: document.getElementById('btn-clear-terminal'),
            btnToggleWrap: document.getElementById('btn-toggle-wrap'),
            btnHelp: document.getElementById('btn-help'),
            
            // Command History
            commandHistory: document.getElementById('command-history'),
            
            // Quick buttons (removed from left panel)
            // tradeBtns: document.querySelectorAll('.trade-btn'),
            // infoBtns: document.querySelectorAll('.info-btn'),
            
            // Strategy elements
            strategySelect: document.getElementById('strategy-select'),
            btnStrategyInfo: document.getElementById('btn-strategy-info'),
            strategyCard: document.getElementById('strategy-card'),
            btnCloseCard: document.getElementById('btn-close-card'),
            strategyCardTitle: document.getElementById('strategy-card-title'),
            strategyDescription: document.getElementById('strategy-description'),
            strategyType: document.getElementById('strategy-type'),
            strategySymbols: document.getElementById('strategy-symbols'),
            strategyPositionSize: document.getElementById('strategy-position-size'),
            strategyRisk: document.getElementById('strategy-risk'),
            strategySchedule: document.getElementById('strategy-schedule'),
            strategyEnabled: document.getElementById('strategy-enabled'),
            
            // Shortcut buttons
            shortcutBtns: document.querySelectorAll('.shortcut-btn')
        };
        
        // Strategy data
        this.strategies = {};
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.connectWebSocket();
        this.loadInitialStatus();
        this.loadStrategies();
        this.startTimeUpdate();
        this.updateCommandHistoryDisplay();
        
        // Initial terminal message
        this.appendToTerminal('🚀 WealthCommander v2.0 시작됨 (NAS 최적화)', 'success');
        this.appendToTerminal('HELP 명령어로 도움말을 확인하세요.', 'info');
    }
    
    setupEventListeners() {
        // Terminal input
        this.elements.terminalInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.sendCommand();
            }
        });
        
        this.elements.btnSend.addEventListener('click', () => {
            this.sendCommand();
        });
        
        // Terminal controls
        this.elements.btnClear.addEventListener('click', () => {
            this.clearTerminal();
        });
        
        this.elements.btnToggleWrap.addEventListener('click', () => {
            this.toggleTextWrap();
        });
        
        this.elements.btnHelp.addEventListener('click', () => {
            this.sendWebSocketCommand('HELP');
        });
        
        // Account switching (removed)
        // this.elements.btnSwitchAccount.addEventListener('click', () => {
        //     this.switchAccount();
        // });
        
        // Auto trading controls
        this.elements.btnStartAuto.addEventListener('click', () => {
            this.sendWebSocketCommand('START');
        });
        
        this.elements.btnStopAuto.addEventListener('click', () => {
            this.sendWebSocketCommand('STOP');
        });
        
        // Quick trade buttons (removed from left panel)
        // this.elements.tradeBtns.forEach(btn => {
        //     btn.addEventListener('click', (e) => {
        //         const action = e.target.dataset.action;
        //         this.sendWebSocketCommand(action);
        //     });
        // });
        
        // Quick info buttons (removed from left panel)
        // this.elements.infoBtns.forEach(btn => {
        //     btn.addEventListener('click', (e) => {
        //         const cmd = e.target.dataset.cmd;
        //         this.sendWebSocketCommand(cmd);
        //     });
        // });
        
        // Strategy controls
        if (this.elements.btnStrategyInfo) {
            this.elements.btnStrategyInfo.addEventListener('click', () => {
                this.showStrategyCard();
            });
        }
        
        if (this.elements.btnCloseCard) {
            this.elements.btnCloseCard.addEventListener('click', () => {
                this.hideStrategyCard();
            });
        }
        
        if (this.elements.strategySelect) {
            this.elements.strategySelect.addEventListener('change', (e) => {
                this.onStrategyChange(e.target.value);
                this.showStrategyCard(); // 전략 변경 시 자동으로 카드 표시
            });
        }
        
        // Shortcut buttons removed
    }
    
    connectWebSocket() {
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = window.location.host;
            const wsUrl = `${protocol}//${host}/ws/terminal`;
            
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = () => {
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.updateConnectionStatus('🟢 연결됨');
                this.appendToTerminal('WebSocket 연결 성공', 'success');
            };
            
            this.websocket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleWebSocketMessage(data);
                } catch (e) {
                    console.error('WebSocket 메시지 파싱 오류:', e);
                }
            };
            
            this.websocket.onclose = () => {
                this.isConnected = false;
                this.updateConnectionStatus('🔴 연결끊김');
                this.appendToTerminal('WebSocket 연결이 끊어졌습니다.', 'error');
                this.scheduleReconnect();
            };
            
            this.websocket.onerror = (error) => {
                console.error('WebSocket 오류:', error);
                this.appendToTerminal('WebSocket 연결 오류', 'error');
            };
            
        } catch (error) {
            console.error('WebSocket 연결 실패:', error);
            this.scheduleReconnect();
        }
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            this.appendToTerminal(`재연결 시도 중... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`, 'warning');
            
            setTimeout(() => {
                this.connectWebSocket();
            }, this.reconnectInterval);
        } else {
            this.appendToTerminal('최대 재연결 시도 횟수를 초과했습니다. 페이지를 새로고침하세요.', 'error');
        }
    }
    
    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'terminal_output':
                this.appendToTerminal(data.payload);
                break;
                
            case 'status_update':
                this.updateStatus(data.payload);
                break;
                
            case 'auto_trading_status':
                this.updateAutoTradingStatus(data.payload);
                break;
                
            default:
                console.warn('알 수 없는 메시지 타입:', data.type);
        }
    }
    
    sendCommand() {
        const command = this.elements.terminalInput.value;
        const trimmedCommand = command.trim();
        
        if (this.isConnected) {
            // 빈 명령어(엔터만 입력)도 전송 - 시장가 주문을 위해
            if (trimmedCommand) {
                // 명령어를 히스토리에 추가 (터미널 출력에는 표시하지 않음)
                this.addToCommandHistory(trimmedCommand);
            }
            
            // 원본 명령어 전송 (공백 포함)
            this.sendWebSocketCommand(command);
            this.elements.terminalInput.value = '';
        }
    }
    
    sendWebSocketCommand(command) {
        if (this.isConnected && this.websocket) {
            this.websocket.send(command);
        } else {
            this.appendToTerminal('WebSocket이 연결되지 않았습니다.', 'error');
        }
    }
    
    addToCommandHistory(command) {
        // 최근 5개 명령어만 유지
        this.commandHistory.unshift({
            command: command,
            timestamp: new Date().toLocaleTimeString('ko-KR', { 
                hour12: false,
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            })
        });
        
        if (this.commandHistory.length > 5) {
            this.commandHistory = this.commandHistory.slice(0, 5);
        }
        
        this.updateCommandHistoryDisplay();
    }
    
    updateCommandHistoryDisplay() {
        const historyContainer = this.elements.commandHistory;
        
        if (this.commandHistory.length === 0) {
            historyContainer.innerHTML = '<div class="history-empty">명령어 입력 대기중...</div>';
            return;
        }
        
        historyContainer.innerHTML = this.commandHistory.map(item => 
            `<div class="history-item" onclick="app.fillCommand('${item.command}')">
                <span class="command-time">${item.timestamp}</span>
                ${item.command}
            </div>`
        ).join('');
    }
    
    fillCommand(command) {
        this.elements.terminalInput.value = command;
        this.elements.terminalInput.focus();
    }
    
    appendToTerminal(message, type = 'info') {
        const output = this.elements.terminalOutput;
        const line = document.createElement('div');
        line.className = `log-${type}`;
        
        // 시간 스탬프 추가
        const timestamp = new Date().toLocaleTimeString('ko-KR', { 
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        
        line.textContent = `[${timestamp}] ${message}`;
        output.appendChild(line);
        
        // 자동 스크롤
        output.scrollTop = output.scrollHeight;
        
        // 최대 라인 수 제한 (메모리 최적화)
        const maxLines = 1000;
        while (output.children.length > maxLines) {
            output.removeChild(output.firstChild);
        }
    }
    
    clearTerminal() {
        this.elements.terminalOutput.innerHTML = '';
        this.appendToTerminal('터미널이 지워졌습니다.', 'info');
    }
    
    toggleTextWrap() {
        this.textWrapEnabled = !this.textWrapEnabled;
        
        if (this.textWrapEnabled) {
            this.elements.terminalOutput.classList.remove('no-wrap');
            this.elements.terminalOutput.classList.add('wrap');
            this.elements.btnToggleWrap.textContent = '⇄';
            this.elements.btnToggleWrap.title = '가로 스크롤 모드';
        } else {
            this.elements.terminalOutput.classList.remove('wrap');
            this.elements.terminalOutput.classList.add('no-wrap');
            this.elements.btnToggleWrap.textContent = '↔️';
            this.elements.btnToggleWrap.title = '텍스트 줄바꿈 모드';
        }
    }
    
    updateConnectionStatus(status) {
        if (this.elements.connectionStatus) {
            this.elements.connectionStatus.textContent = status;
        }
    }
    
    async loadInitialStatus() {
        try {
            const response = await fetch('/api/status');
            if (response.ok) {
                const data = await response.json();
                this.updateStatus(data);
            }
        } catch (error) {
            console.error('초기 상태 로드 실패:', error);
        }
    }
    
    updateStatus(status) {
        // Market status
        if (status.market) {
            const marketText = status.market.is_open ? '🟢 개장' : '🔴 마감';
            if (this.elements.marketStatus) {
                this.elements.marketStatus.textContent = marketText;
            }
            
            const marketStatusText = document.getElementById('market-status-text');
            if (marketStatusText) {
                marketStatusText.textContent = status.market.is_open ? '개장' : '마감';
            }
        }
        
        // Account info (removed)
        // if (status.account) {
        //     if (this.elements.portfolioValue) {
        //         this.elements.portfolioValue.textContent = `$${Number(status.account.portfolio_value || 0).toLocaleString('en-US', {
        //             minimumFractionDigits: 2,
        //             maximumFractionDigits: 2
        //         })}`;
        //     }
        //     
        //     if (this.elements.buyingPower) {
        //         this.elements.buyingPower.textContent = `$${Number(status.account.buying_power || 0).toLocaleString('en-US', {
        //             minimumFractionDigits: 2,
        //             maximumFractionDigits: 2
        //         })}`;
        //     }
        //     
        //     if (this.elements.cashValue) {
        //         this.elements.cashValue.textContent = `$${Number(status.account.cash || 0).toLocaleString('en-US', {
        //             minimumFractionDigits: 2,
        //             maximumFractionDigits: 2
        //         })}`;
        //     }
        // }
        
        // Auto trading status
        if (status.auto) {
            this.updateAutoTradingStatus(status.auto);
        }
    }
    
    updateAutoTradingStatus(autoStatus) {
        if (autoStatus.enabled) {
            this.elements.autoStatus.textContent = '🟢';
            this.elements.autoStatusText.textContent = '실행중';
            this.elements.btnStartAuto.disabled = true;
            this.elements.btnStopAuto.disabled = false;
        } else {
            this.elements.autoStatus.textContent = '🔴';
            this.elements.autoStatusText.textContent = '중지';
            this.elements.btnStartAuto.disabled = false;
            this.elements.btnStopAuto.disabled = true;
        }
        
        if (this.elements.currentStrategy) {
            this.elements.currentStrategy.textContent = autoStatus.strategy || 'Simple_Buy';
        }
        
        if (this.elements.nextRun) {
            this.elements.nextRun.textContent = autoStatus.next_run || '--:--';
        }
    }
    
    async switchAccount() {
        const selectedAccount = this.elements.accountSelect.value;
        if (!selectedAccount) return;
        
        try {
            const response = await fetch('/api/account', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ account: selectedAccount })
            });
            
            if (response.ok) {
                this.appendToTerminal(`계좌를 ${selectedAccount}로 전환했습니다.`, 'success');
                this.loadInitialStatus(); // 상태 새로고침
            } else {
                const error = await response.json();
                this.appendToTerminal(`계좌 전환 실패: ${error.error}`, 'error');
            }
        } catch (error) {
            this.appendToTerminal(`계좌 전환 오류: ${error.message}`, 'error');
        }
    }
    
    async loadStrategies() {
        try {
            const response = await fetch('/api/strategies');
            if (response.ok) {
                this.strategies = await response.json();
                this.populateStrategySelect();
            }
        } catch (error) {
            console.error('전략 로드 실패:', error);
            // 기본 전략 데이터
            this.strategies = {
                "Simple_Buy": {
                    "name": "Simple_Buy",
                    "description": "단순 ETF 매수 전략 - NAS 환경 최적화",
                    "type": "simple_buy",
                    "symbols": ["VOO", "VTI", "QQQ"],
                    "allocation_percent": 30
                }
            };
            this.populateStrategySelect();
        }
    }
    
    populateStrategySelect() {
        if (!this.elements.strategySelect) return;
        
        // 기존 옵션 제거 (첫 번째 옵션 제외)
        while (this.elements.strategySelect.children.length > 1) {
            this.elements.strategySelect.removeChild(this.elements.strategySelect.lastChild);
        }
        
        // 전략 옵션 추가
        Object.keys(this.strategies).forEach(strategyKey => {
            if (strategyKey !== 'Simple_Buy') { // 이미 HTML에 있음
                const option = document.createElement('option');
                option.value = strategyKey;
                option.textContent = this.strategies[strategyKey].name || strategyKey;
                this.elements.strategySelect.appendChild(option);
            }
        });
    }
    
    showStrategyCard() {
        const selectedStrategy = this.elements.strategySelect.value;
        const strategy = this.strategies[selectedStrategy];
        
        if (!strategy) return;
        
        // 카드 내용 업데이트
        if (this.elements.strategyCardTitle) {
            this.elements.strategyCardTitle.textContent = strategy.name || selectedStrategy;
        }
        
        if (this.elements.strategyDescription) {
            this.elements.strategyDescription.textContent = strategy.description || '전략 설명이 없습니다.';
        }
        
        if (this.elements.strategyType) {
            this.elements.strategyType.textContent = this.getStrategyTypeDescription(strategy.type) || '-';
        }
        
        if (this.elements.strategySymbols) {
            const symbols = strategy.symbols || strategy.universe || [];
            this.elements.strategySymbols.textContent = Array.isArray(symbols) ? symbols.join(', ') : '-';
        }
        
        // 포지션 크기 정보
        if (this.elements.strategyPositionSize) {
            this.elements.strategyPositionSize.textContent = this.getPositionSizeText(strategy);
        }
        
        // 리스크 관리 정보
        if (this.elements.strategyRisk) {
            this.elements.strategyRisk.textContent = this.getRiskManagementText(strategy);
        }
        
        // 스케줄 정보
        if (this.elements.strategySchedule) {
            this.elements.strategySchedule.textContent = this.getScheduleText(strategy);
        }
        
        // 활성화 상태
        if (this.elements.strategyEnabled) {
            this.elements.strategyEnabled.textContent = strategy.enabled ? '🟢 활성화됨' : '🔴 비활성화됨';
            this.elements.strategyEnabled.style.color = strategy.enabled ? '#28a745' : '#dc3545';
        }
        
        // 카드 표시
        if (this.elements.strategyCard) {
            this.elements.strategyCard.style.display = 'block';
        }
    }
    
    getStrategyTypeDescription(type) {
        const typeDescriptions = {
            'simple_buy': '단순 매수 전략',
            'sma_crossover': 'SMA 교차 전략',
            'rsi_reversion': 'RSI 평균 회귀',
            'breakout': '돌파 전략'
        };
        return typeDescriptions[type] || type;
    }
    
    getPositionSizeText(strategy) {
        if (strategy.allocation_percent) {
            return `총 자금의 ${strategy.allocation_percent}%`;
        }
        if (strategy.position_sizing) {
            const sizing = strategy.position_sizing;
            if (sizing.type === 'bp_percent') {
                return `매수력의 ${sizing.value}%`;
            } else if (sizing.type === 'fixed_notional') {
                return `고정 $${sizing.value.toLocaleString()}`;
            }
        }
        return '-';
    }
    
    getRiskManagementText(strategy) {
        const risk = strategy.risk || strategy.risk_management;
        if (!risk) return '-';
        
        const riskItems = [];
        if (risk.stop_loss_percent || risk.stop_loss_pct) {
            riskItems.push(`손절: ${risk.stop_loss_percent || risk.stop_loss_pct}%`);
        }
        if (risk.take_profit_percent || risk.take_profit_pct) {
            riskItems.push(`익절: ${risk.take_profit_percent || risk.take_profit_pct}%`);
        }
        if (risk.trailing_stop_pct) {
            riskItems.push(`추적손절: ${risk.trailing_stop_pct}%`);
        }
        if (risk.max_positions) {
            riskItems.push(`최대 포지션: ${risk.max_positions}개`);
        }
        if (risk.max_daily_trades) {
            riskItems.push(`일일 최대 거래: ${risk.max_daily_trades}회`);
        }
        
        return riskItems.length > 0 ? riskItems.join(', ') : '기본 설정';
    }
    
    getScheduleText(strategy) {
        if (strategy.schedule) {
            const schedule = strategy.schedule;
            return `${schedule.frequency || '일일'} ${schedule.time || '10:00'} (${schedule.timezone || 'EST'})`;
        }
        if (strategy.timeframe) {
            return `시간프레임: ${strategy.timeframe}`;
        }
        return '실시간';
    }
    
    hideStrategyCard() {
        if (this.elements.strategyCard) {
            this.elements.strategyCard.style.display = 'none';
        }
    }
    
    onStrategyChange(strategyName) {
        // 전략 변경시 처리
        this.appendToTerminal(`전략 선택: ${strategyName}`, 'info');
        
        // 서버에 전략 변경 요청 (구현 필요)
        // this.sendWebSocketCommand(`SET_STRATEGY ${strategyName}`);
    }
    
    startTimeUpdate() {
        const updateTime = () => {
            const now = new Date();
            const timeString = now.toLocaleTimeString('ko-KR', {
                hour12: false,
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            
            if (this.elements.currentTime) {
                this.elements.currentTime.textContent = timeString;
            }
        };
        
        updateTime(); // 즉시 실행
        setInterval(updateTime, 1000); // 1초마다 업데이트
    }
}

// DOM이 로드되면 앱 시작
document.addEventListener('DOMContentLoaded', () => {
    window.wealthCommanderApp = new WealthCommanderApp();
});

// NAS 환경을 위한 전역 오류 처리
window.addEventListener('error', (event) => {
    console.error('전역 오류:', event.error);
});

window.addEventListener('unhandledrejection', (event) => {
    console.error('처리되지 않은 Promise 거부:', event.reason);
});