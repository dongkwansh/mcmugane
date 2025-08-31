class McMuganeTerminal {
    constructor() {
        this.socket = null;
        this.token = localStorage.getItem('access_token');
        this.mode = 'PAPER';
        this.autoTrading = false;
        this.interactiveMode = null;
        this.init();
    }
    
    init() {
        if (!this.token) {
            window.location.href = '/login.html';
            return;
        }
        
        this.connectSocket();
        this.setupEventListeners();
        this.loadPortfolio();
        this.loadStrategies();
    }
    
    connectSocket() {
        this.socket = io({
            auth: {
                token: this.token
            }
        });
        
        this.socket.on('connect', () => {
            console.log('Connected to server');
            document.getElementById('connection-status').textContent = '● Connected';
            document.getElementById('connection-status').style.color = 'var(--accent-green)';
        });
        
        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
            document.getElementById('connection-status').textContent = '● Disconnected';
            document.getElementById('connection-status').style.color = 'var(--accent-red)';
        });
        
        this.socket.on('terminal_response', (data) => {
            this.handleTerminalResponse(data);
        });
        
        this.socket.on('portfolio_update', (data) => {
            this.updatePortfolio(data);
        });
    }
    
    setupEventListeners() {
        // 터미널 입력
        const terminalInput = document.getElementById('terminal-input');
        terminalInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.sendCommand(terminalInput.value);
                terminalInput.value = '';
            }
        });
        
        // 전략 카드 토글
        document.querySelectorAll('.toggle-strategy').forEach(button => {
            button.addEventListener('click', (e) => {
                const card = e.target.closest('.strategy-card');
                const strategy = card.dataset.strategy;
                this.toggleStrategy(strategy, button);
            });
        });
    }
    
    sendCommand(command) {
        if (!command.trim()) return;
        
        // 명령어를 터미널에 표시
        this.appendToTerminal(`mcmugane> ${command}`, 'command');
        
        // 대화형 모드 처리
        if (this.interactiveMode) {
            this.handleInteractiveInput(command);
        } else {
            this.socket.emit('terminal_command', { command });
        }
    }
    
    handleTerminalResponse(data) {
        if (data.error) {
            this.appendToTerminal(data.error, 'error');
        } else if (data.interactive) {
            this.interactiveMode = data;
            this.appendToTerminal(data.message, 'response');
        } else if (data.message) {
            this.appendToTerminal(data.message, 'response');
        } else if (data.success) {
            this.appendToTerminal(JSON.stringify(data, null, 2), 'response');
        }
    }
    
    handleInteractiveInput(input) {
        const step = this.interactiveMode.step;
        const command = { ...this.interactiveMode, input };
        
        this.socket.emit('terminal_command_interactive', command);
        this.interactiveMode = null;
    }
    
    appendToTerminal(text, type = 'response') {
        const terminal = document.getElementById('terminal-output');
        const line = document.createElement('div');
        line.className = `terminal-line ${type}`;
        line.textContent = text;
        terminal.appendChild(line);
        terminal.scrollTop = terminal.scrollHeight;
    }
    
    loadPortfolio() {
        fetch('/api/portfolio', {
            headers: {
                'Authorization': `Bearer ${this.token}`
            }
        })
        .then(res => res.json())
        .then(data => this.updatePortfolio(data));
    }
    
    updatePortfolio(data) {
        const content = document.getElementById('portfolio-content');
        
        if (!data.positions || data.positions.length === 0) {
            content.innerHTML = '<p>포지션 없음</p>';
            return;
        }
        
        let html = '';
        data.positions.forEach(pos => {
            const plClass = pos.unrealized_pl >= 0 ? 'profit' : 'loss';
            html += `
                <div class="portfolio-item">
                    <span class="symbol">${pos.symbol}</span>
                    <span class="value">${pos.qty}주 @ $${pos.avg_entry_price}</span>
                    <span class="${plClass}">$${pos.unrealized_pl.toFixed(2)} (${pos.unrealized_plpc.toFixed(2)}%)</span>
                </div>
            `;
        });
        
        content.innerHTML = html;
    }
    
    loadStrategies() {
        fetch('/api/strategies', {
            headers: {
                'Authorization': `Bearer ${this.token}`
            }
        })
        .then(res => res.json())
        .then(data => {
            data.strategies.forEach(strategy => {
                const card = document.querySelector(`[data-strategy="${strategy.id}"]`);
                if (card && strategy.enabled) {
                    card.querySelector('.toggle-strategy').classList.add('active');
                    card.querySelector('.toggle-strategy').textContent = '활성화됨';
                }
            });
        });
    }
    
    toggleStrategy(strategyId, button) {
        const isActive = button.classList.contains('active');
        
        fetch(`/api/strategy/${strategyId}/toggle`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ enabled: !isActive })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                button.classList.toggle('active');
                button.textContent = isActive ? '활성화' : '활성화됨';
                this.appendToTerminal(`전략 ${strategyId} ${!isActive ? '활성화' : '비활성화'}됨`, 'response');
            }
        });
    }
}

// 페이지 로드시 초기화
document.addEventListener('DOMContentLoaded', () => {
    new McMuganeTerminal();
});