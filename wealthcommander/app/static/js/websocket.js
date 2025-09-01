// /static/js/websocket.js
export class WebSocketManager {
    constructor(url, onMessageCallback) {
        this.ws = null;
        this.url = url;
        this.onMessage = onMessageCallback;
        this.reconnectAttempts = 0;
        this.maxAttempts = 10;
        this.delay = 3000;
        this.connect();
    }

    connect() {
        try {
            this.ws = new WebSocket(this.url);

            this.ws.onopen = () => {
                console.log('WebSocket connection established.');
                this.reconnectAttempts = 0;
                document.getElementById('connection-status').textContent = '● 연결됨';
                document.getElementById('connection-status').className = 'status-indicator connected';
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.onMessage(data);
                } catch (e) {
                    console.error('Failed to parse WebSocket message:', event.data, e);
                }
            };

            this.ws.onclose = () => {
                console.log('WebSocket connection closed.');
                document.getElementById('connection-status').textContent = '● 연결 끊김';
                document.getElementById('connection-status').className = 'status-indicator disconnected';
                this.attemptReconnect();
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.ws.close(); // Ensure connection is closed before reconnecting
            };
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            this.attemptReconnect();
        }
    }

    attemptReconnect() {
        if (this.reconnectAttempts < this.maxAttempts) {
            this.reconnectAttempts++;
            console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxAttempts})...`);
            setTimeout(() => this.connect(), this.delay);
        } else {
            console.error('Could not reconnect to the WebSocket server.');
            // Maybe display this error in the terminal UI
        }
    }

    sendCommand(command) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'terminal_input', payload: command }));
        } else {
            console.error('Cannot send command: WebSocket is not connected.');
            // Maybe display this error in the terminal UI
        }
    }
}