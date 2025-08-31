// 터미널 명령어 자동완성 및 히스토리 기능
class TerminalEnhancer {
    constructor() {
        this.history = [];
        this.historyIndex = -1;
        this.commands = [
            'HELP', 'MODE', 'AUTO', 'STATUS', 'PORTFOLIO',
            'BUY', 'SELL', 'CANCEL', 'ORDERS', 'HISTORY', 'LOGS'
        ];
        this.init();
    }
    
    init() {
        const input = document.getElementById('terminal-input');
        
        // 히스토리 네비게이션
        input.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowUp') {
                e.preventDefault();
                this.navigateHistory('up', input);
            } else if (e.key === 'ArrowDown') {
                e.preventDefault();
                this.navigateHistory('down', input);
            } else if (e.key === 'Tab') {
                e.preventDefault();
                this.autocomplete(input);
            }
        });
        
        // 명령어 실행시 히스토리 추가
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && input.value.trim()) {
                this.addToHistory(input.value);
                this.historyIndex = -1;
            }
        });
    }
    
    navigateHistory(direction, input) {
        if (direction === 'up' && this.historyIndex < this.history.length - 1) {
            this.historyIndex++;
            input.value = this.history[this.history.length - 1 - this.historyIndex];
        } else if (direction === 'down' && this.historyIndex > 0) {
            this.historyIndex--;
            input.value = this.history[this.history.length - 1 - this.historyIndex];
        } else if (direction === 'down' && this.historyIndex === 0) {
            this.historyIndex = -1;
            input.value = '';
        }
    }
    
    addToHistory(command) {
        if (this.history[this.history.length - 1] !== command) {
            this.history.push(command);
            if (this.history.length > 100) {
                this.history.shift();
            }
        }
    }
    
    autocomplete(input) {
        const value = input.value.toUpperCase();
        if (!value) return;
        
        const matches = this.commands.filter(cmd => cmd.startsWith(value));
        
        if (matches.length === 1) {
            input.value = matches[0];
        } else if (matches.length > 1) {
            // 공통 접두사 찾기
            const commonPrefix = this.findCommonPrefix(matches);
            if (commonPrefix.length > value.length) {
                input.value = commonPrefix;
            }
            
            // 가능한 명령어 표시
            const terminal = document.getElementById('terminal-output');
            const suggestions = document.createElement('div');
            suggestions.className = 'terminal-line response';
            suggestions.textContent = '가능한 명령어: ' + matches.join(', ');
            terminal.appendChild(suggestions);
            terminal.scrollTop = terminal.scrollHeight;
        }
    }
    
    findCommonPrefix(strings) {
        if (!strings.length) return '';
        
        let prefix = strings[0];
        for (let i = 1; i < strings.length; i++) {
            while (!strings[i].startsWith(prefix)) {
                prefix = prefix.substring(0, prefix.length - 1);
            }
        }
        return prefix;
    }
}

// 초기화
document.addEventListener('DOMContentLoaded', () => {
    new TerminalEnhancer();
});