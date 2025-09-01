// /static/js/ui.js
import { apiCall } from './api.js';

const translations = {
    ko: { selectStrategy: '자동매매를 켜려면 먼저 전략을 선택하세요.', intervalWarning: '실행 간격은 최소 10초 이상이어야 합니다.', settingsApplied: '설정이 성공적으로 적용되었습니다.', settingsFailed: '설정 적용 실패' },
    us: { selectStrategy: 'Please select a strategy to enable auto trading.', intervalWarning: 'Interval must be at least 10 seconds.', settingsApplied: 'Settings applied successfully.', settingsFailed: 'Failed to apply settings' }
};

export class UIManager {
    constructor() {
        this.language = 'ko';
        this.elements = {
            terminalOutput: document.getElementById('terminal-output'),
            terminalInput: document.getElementById('terminal-input'),
            connectionStatus: document.getElementById('connection-status'),
            accountSelect: document.getElementById('account-select'),
            quickCommands: document.querySelectorAll('.quick-cmd'),
            btnSwitchAccount: document.getElementById('btn-switch-account'),
            btnApply: document.getElementById('btn-apply'),
            autoToggle: document.getElementById('auto-toggle'),
            strategySelect: document.getElementById('strategy-select'),
            intervalInput: document.getElementById('interval-input')
        };
    }

    getTranslation(key) {
        return translations[this.language][key] || key;
    }
    
    startTimeUpdate() {
        const nyTimeEl = document.getElementById('ny-time');
        const localTimeEl = document.getElementById('local-time');
        const update = () => {
            nyTimeEl.textContent = `${new Date().toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour12: false })} ET`;
            localTimeEl.textContent = `${new Date().toLocaleTimeString('ko-KR', { timeZone: 'Asia/Seoul', hour12: false })} KST`;
        };
        update();
        setInterval(update, 1000);
    }
    
    appendToTerminal(message, type = 'normal') {
        const line = document.createElement('div');
        line.className = `log-${type}`; // Use a prefix to avoid class conflicts
        const pre = document.createElement('pre');
        const timestamp = new Date().toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour12: false });
        pre.textContent = `[${timestamp}] ${message}`;
        line.appendChild(pre);
        this.elements.terminalOutput.appendChild(line);
        this.elements.terminalOutput.scrollTop = this.elements.terminalOutput.scrollHeight;
    }

    updateConnectionStatus(isConnected) {
        this.elements.connectionStatus.textContent = isConnected ? '● 연결됨' : '● 연결 끊김';
        this.elements.connectionStatus.className = `status-indicator ${isConnected ? 'connected' : 'disconnected'}`;
    }

    setLanguage(lang) {
        if (this.language === lang) return;
        this.language = lang;

        document.querySelectorAll('.language-toggle button').forEach(btn => btn.classList.remove('active'));
        document.getElementById(`lang-${lang}`).classList.add('active');
        
        const colors = (lang === 'us') ? { up: '#10b981', down: '#ef4444' } : { up: '#ef4444', down: '#0ea5e9' };
        document.documentElement.style.setProperty('--color-up', colors.up);
        document.documentElement.style.setProperty('--color-down', colors.down);

        apiCall('/api/settings/language', 'POST', { language: lang }).catch(err => console.error("Failed to save language setting:", err));
    }
    
    populateAccountSelector(accounts, currentAccountName) {
        const select = this.elements.accountSelect;
        select.innerHTML = '';
        accounts.forEach(acc => {
            const option = document.createElement('option');
            option.value = acc.name;
            option.textContent = `${acc.display_name} (${acc.type})`;
            option.selected = acc.name === currentAccountName;
            select.appendChild(option);
        });
    }

    updateFullUI(status) {
        if (status.language && this.language !== status.language) {
            this.setLanguage(status.language);
        }

        // Account Info
        document.getElementById('current-account').textContent = status.current_account;
        document.getElementById('account-type').textContent = status.mode;
        
        // Market Status
        const marketEl = document.getElementById('market-status');
        marketEl.classList.remove('loading');
        marketEl.className = `market-status ${status.market.is_open ? 'open' : 'closed'}`;
        marketEl.querySelector('.status-text').textContent = status.market.is_open ? 'Market Open' : 'Market Closed';

        // Auto-trading controls
        this.elements.autoToggle.checked = status.auto.enabled;
        document.getElementById('auto-status').textContent = status.auto.enabled ? 'ON' : 'OFF';
        this.elements.intervalInput.value = status.auto.interval_seconds;
        
        // Strategy Selector
        const currentStrategy = this.elements.strategySelect.value;
        this.elements.strategySelect.innerHTML = '<option value="">선택 안함</option>';
        status.strategies.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s;
            opt.textContent = s;
            this.elements.strategySelect.appendChild(opt);
        });
        this.elements.strategySelect.value = status.strategy || currentStrategy || "";
        
        // Quick Stats
        const alpacaOk = status.alpaca === 'OK';
        document.getElementById('alpaca-status').textContent = alpacaOk ? '연결됨' : '연결 안됨';
        document.getElementById('alpaca-status').style.color = alpacaOk ? 'var(--accent-green)' : 'var(--accent-red)';
        document.getElementById('buying-power').textContent = Number(status.buying_power).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        document.getElementById('active-strategy').textContent = status.strategy || '없음';
    }
}