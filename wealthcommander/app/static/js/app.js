// /static/js/app.js
import { apiCall } from './api.js';
import { UIManager } from './ui.js';
import { WebSocketManager } from './websocket.js';

class TradingApp {
    constructor() {
        this.ui = new UIManager();
        this.ws = new WebSocketManager(
            `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/terminal`,
            this.handleWebSocketMessage.bind(this)
        );
        this.init();
    }

    async init() {
        this.ui.startTimeUpdate();
        this.setupEventListeners();
        
        try {
            const status = await apiCall('/api/status');
            this.ui.updateFullUI(status);
            this.loadAccounts(status.current_account);
        } catch (error) {
            console.error('Failed to load initial status:', error);
            this.ui.appendToTerminal('초기 상태 정보를 불러오는 데 실패했습니다.', 'error');
        }
    }
    
    handleWebSocketMessage(data) {
        if (data.type === 'terminal_output') {
            this.ui.appendToTerminal(data.payload);
        } else if (data.type === 'status_update') {
            this.ui.updateFullUI(data.payload);
            this.loadAccounts(data.payload.current_account);
        }
    }

    async loadAccounts(currentAccount) {
        try {
            const data = await apiCall('/api/accounts');
            this.ui.populateAccountSelector(data.accounts, currentAccount);
        } catch (error) {
            console.error('Failed to load accounts:', error);
            this.ui.appendToTerminal('계좌 목록을 불러오는 데 실패했습니다.', 'error');
        }
    }

    setupEventListeners() {
        // Language Toggle
        document.getElementById('lang-ko')?.addEventListener('click', () => this.ui.setLanguage('ko'));
        document.getElementById('lang-us')?.addEventListener('click', () => this.ui.setLanguage('us'));

        // Terminal Input
        this.ui.elements.terminalInput?.addEventListener('keypress', (e) => {
            const command = e.target.value.trim();
            if (e.key === 'Enter' && command) {
                this.ws.sendCommand(command);
                this.ui.appendToTerminal(`> ${command}`, 'info');
                e.target.value = '';
            }
        });

        // Quick Commands
        this.ui.elements.quickCommands.forEach(btn => {
            btn.addEventListener('click', (e) => this.ws.sendCommand(e.target.dataset.cmd));
        });

        // Switch Account
        this.ui.elements.btnSwitchAccount?.addEventListener('click', async () => {
            const selectedAccount = this.ui.elements.accountSelect.value;
            const confirmMsg = this.ui.language === 'ko' ? `${selectedAccount} 계좌로 전환하시겠습니까?` : `Switch to ${selectedAccount} account?`;
            
            if (confirm(confirmMsg)) {
                try {
                    await apiCall('/api/account', 'POST', { account: selectedAccount });
                    this.ui.appendToTerminal(`${selectedAccount} 계좌로 성공적으로 전환되었습니다.`, 'success');
                } catch (error) {
                    this.ui.appendToTerminal(`계좌 전환 실패: ${error.message}`, 'error');
                }
            }
        });

        // Apply Auto-Trading Settings
        this.ui.elements.btnApply?.addEventListener('click', async () => {
            const payload = {
                enabled: this.ui.elements.autoToggle.checked,
                strategy: this.ui.elements.strategySelect.value,
                interval_seconds: parseInt(this.ui.elements.intervalInput.value)
            };

            if (payload.enabled && !payload.strategy) {
                alert(this.ui.getTranslation('selectStrategy'));
                return;
            }
            if (payload.interval_seconds < 10) {
                alert(this.ui.getTranslation('intervalWarning'));
                return;
            }

            try {
                await apiCall('/api/auto', 'POST', payload);
                this.ui.appendToTerminal(this.ui.getTranslation('settingsApplied'), 'success');
            } catch (error) {
                this.ui.appendToTerminal(`${this.ui.getTranslation('settingsFailed')}: ${error.message}`, 'error');
            }
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new TradingApp();
});