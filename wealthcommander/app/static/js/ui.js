// /static/js/ui.js
import { apiCall } from './api.js';
import { translations } from './translations.js';

export class UIManager {
    constructor() {
        this.language = 'ko';
        this.elements = this.initElements();
        this.initializeUI();
    }

    initElements() {
        return {
            // Terminal
            terminalOutput: document.getElementById('terminal-output'),
            terminalInput: document.getElementById('terminal-input'),
            
            // Status
            connectionStatus: document.getElementById('connection-status'),
            marketStatus: document.getElementById('market-status'),
            marketStatusText: document.querySelector('#market-status .status-text'),
            
            // Account
            accountSelect: document.getElementById('account-select'),
            currentAccount: document.getElementById('current-account'),
            accountType: document.getElementById('account-type'),
            btnSwitchAccount: document.getElementById('btn-switch-account'),
            
            // Auto Trading
            autoToggle: document.getElementById('auto-toggle'),
            autoStatus: document.getElementById('auto-status'),
            strategySelect: document.getElementById('strategy-select'),
            intervalInput: document.getElementById('interval-input'),
            btnApply: document.getElementById('btn-apply'),
            
            // Quick Stats
            alpacaStatus: document.getElementById('alpaca-status'),
            buyingPower: document.getElementById('buying-power'),
            activeStrategy: document.getElementById('active-strategy'),
            
            // Time
            nyTime: document.getElementById('ny-time'),
            localTime: document.getElementById('local-time'),
            
            // Quick Commands
            quickCommands: document.querySelectorAll('.quick-cmd'),
            
            // Language
            langKo: document.getElementById('lang-ko'),
            langUs: document.getElementById('lang-us')
        };
    }

    initializeUI() {
        this.updateLabels();
        this.startTimeUpdate();
    }

    t(key) {
        return translations[this.language][key] || key;
    }

    updateLabels() {
        // Update all UI labels based on language
        const labels = {
            'label-current-account': this.t('currentAccount'),
            'label-account-type': this.t('accountType'),
            'label-auto-trading': this.t('autoTrading'),
            'label-strategy': this.t('strategy'),
            'label-interval': this.t('interval'),
            'label-alpaca': this.t('alpacaConnection'),
            'label-buying-power': this.t('buyingPower'),
            'label-active-strategy': this.t('activeStrategy')
        };

        Object.entries(labels).forEach(([id, text]) => {
            const element = document.getElementById(id);
            if (element) element.textContent = text;
        });

        // Update buttons
        if (this.elements.btnSwitchAccount) {
            this.elements.btnSwitchAccount.textContent = this.t('switchAccount');
        }
        if (this.elements.btnApply) {
            this.elements.btnApply.textContent = this.t('applySettings');
        }

        // Update quick command buttons
        const cmdTranslations = {
            'HELP': this.t('help'),
            'STATUS': this.t('status'),
            'PORTFOLIO': this.t('portfolio'),
            'ORDERS': this.t('orders'),
            'HISTORY': this.t('history')
        };

        this.elements.quickCommands.forEach(btn => {
            const cmd = btn.dataset.cmd;
            if (cmdTranslations[cmd]) {
                btn.textContent = cmdTranslations[cmd];
            }
        });
    }

    setLanguage(lang) {
        if (this.language === lang) return;
        
        this.language = lang;
        this.updateLabels();

        // Update active language button
        document.querySelectorAll('.language-toggle button').forEach(btn => {
            btn.classList.remove('active');
        });
        document.getElementById(`lang-${lang}`).classList.add('active');
        
        // Update color scheme
        const colors = (lang === 'us') 
            ? { up: '#10b981', down: '#ef4444' } 
            : { up: '#ef4444', down: '#0ea5e9' };
        
        document.documentElement.style.setProperty('--color-up', colors.up);
        document.documentElement.style.setProperty('--color-down', colors.down);

        // Save language preference
        apiCall('/api/settings', 'POST', { language: lang })
            .catch(err => console.error("Failed to save language setting:", err));
    }

    startTimeUpdate() {
        const updateTime = () => {
            const now = new Date();
            
            // NY Time (고정 폭 형식)
            const nyTime = now.toLocaleTimeString('en-US', {
                timeZone: 'America/New_York',
                hour12: false,
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            
            // Local Time (고정 폭 형식)
            const localTime = now.toLocaleTimeString('ko-KR', {
                timeZone: 'Asia/Seoul',
                hour12: false,
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            
            this.elements.nyTime.textContent = `${nyTime} ET`;
            this.elements.localTime.textContent = `${localTime} KST`;
        };
        
        updateTime();
        setInterval(updateTime, 1000);
    }

    appendToTerminal(message, type = 'normal') {
        const line = document.createElement('div');
        line.className = `log-${type}`;
        
        const pre = document.createElement('pre');
        const timestamp = new Date().toLocaleTimeString('en-US', {
            timeZone: 'America/New_York',
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        
        // 고정 폭 타임스탬프 형식
        pre.textContent = `[${timestamp}] ${message}`;
        line.appendChild(pre);
        
        this.elements.terminalOutput.appendChild(line);
        this.elements.terminalOutput.scrollTop = this.elements.terminalOutput.scrollHeight;
    }

    updateConnectionStatus(isConnected) {
        const text = isConnected ? this.t('connected') : this.t('disconnected');
        this.elements.connectionStatus.textContent = `● ${text}`;
        this.elements.connectionStatus.className = `status-indicator ${isConnected ? 'connected' : 'disconnected'}`;
    }

    updateMarketStatus(isOpen, isLoading = false) {
        const marketEl = this.elements.marketStatus;
        
        if (isLoading) {
            marketEl.className = 'market-status loading';
            this.elements.marketStatusText.textContent = this.t('checking');
        } else {
            marketEl.className = `market-status ${isOpen ? 'open' : 'closed'}`;
            this.elements.marketStatusText.textContent = isOpen 
                ? this.t('marketOpen') 
                : this.t('marketClosed');
        }
    }

    populateAccountSelector(accounts, currentAccountName) {
        const select = this.elements.accountSelect;
        select.innerHTML = '';
        
        accounts.forEach(acc => {
            const option = document.createElement('option');
            option.value = acc.name;
            option.textContent = `${acc.display_name || acc.name} (${acc.type})`;
            option.selected = acc.name === currentAccountName;
            select.appendChild(option);
        });
    }

    updateFullUI(status) {
        // Language
        if (status.language && this.language !== status.language) {
            this.setLanguage(status.language);
        }

        // Account Info
        this.elements.currentAccount.textContent = status.current_account;
        this.elements.accountType.textContent = status.mode;
        
        // Market Status
        this.updateMarketStatus(status.market?.is_open);

        // Auto-trading controls
        this.elements.autoToggle.checked = status.auto?.enabled || false;
        this.elements.autoStatus.textContent = status.auto?.enabled ? 'ON' : 'OFF';
        this.elements.intervalInput.value = status.auto?.interval_seconds || 60;
        
        // Strategy Selector
        const currentStrategy = this.elements.strategySelect.value;
        this.elements.strategySelect.innerHTML = `<option value="">${this.t('selectStrategy')}</option>`;
        
        if (status.strategies) {
            status.strategies.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s;
                opt.textContent = s;
                this.elements.strategySelect.appendChild(opt);
            });
        }
        
        this.elements.strategySelect.value = status.strategy || currentStrategy || "";
        
        // Quick Stats
        const alpacaOk = status.alpaca === 'OK';
        this.elements.alpacaStatus.textContent = alpacaOk 
            ? this.t('connected') 
            : this.t('disconnected');
        this.elements.alpacaStatus.style.color = alpacaOk 
            ? 'var(--accent-green)' 
            : 'var(--accent-red)';
        
        this.elements.buyingPower.textContent = Number(status.buying_power || 0)
            .toLocaleString('en-US', { 
                minimumFractionDigits: 2, 
                maximumFractionDigits: 2 
            });
        
        this.elements.activeStrategy.textContent = status.strategy || this.t('none');
    }
}