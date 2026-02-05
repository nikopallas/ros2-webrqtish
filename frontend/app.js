/**
 * Main application module - handles WebSocket connection and REST API calls
 */
const App = {
    ws: null,
    wsConnected: false,
    messageCallbacks: {},

    /**
     * Initialize the application
     */
    init() {
        this.connectWebSocket();
    },

    /**
     * Connect to the WebSocket server
     */
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/topics`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            this.wsConnected = true;
            this.updateConnectionStatus(true);
            console.log('WebSocket connected');
        };

        this.ws.onclose = () => {
            this.wsConnected = false;
            this.updateConnectionStatus(false);
            console.log('WebSocket disconnected, reconnecting...');
            // Reconnect after 2 seconds
            setTimeout(() => this.connectWebSocket(), 2000);
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (e) {
                console.error('Failed to parse WebSocket message:', e);
            }
        };
    },

    /**
     * Handle incoming WebSocket messages
     */
    handleMessage(data) {
        if (data.type === 'message' && data.topic) {
            // Dispatch to registered callbacks
            const callbacks = this.messageCallbacks[data.topic] || [];
            callbacks.forEach(cb => cb(data.data, data.topic));
        } else if (data.type === 'subscription') {
            // Subscription status update
            console.log(`Subscription ${data.status}: ${data.topic}`);
        }
    },

    /**
     * Register a callback for topic messages
     */
    onTopicMessage(topic, callback) {
        if (!this.messageCallbacks[topic]) {
            this.messageCallbacks[topic] = [];
        }
        this.messageCallbacks[topic].push(callback);
    },

    /**
     * Remove a callback for topic messages
     */
    offTopicMessage(topic, callback) {
        if (this.messageCallbacks[topic]) {
            this.messageCallbacks[topic] = this.messageCallbacks[topic].filter(cb => cb !== callback);
        }
    },

    /**
     * Subscribe to a topic via WebSocket
     */
    subscribe(topic) {
        if (this.ws && this.wsConnected) {
            this.ws.send(JSON.stringify({
                action: 'subscribe',
                topic: topic
            }));
            return true;
        }
        return false;
    },

    /**
     * Unsubscribe from a topic via WebSocket
     */
    unsubscribe(topic) {
        if (this.ws && this.wsConnected) {
            this.ws.send(JSON.stringify({
                action: 'unsubscribe',
                topic: topic
            }));
            return true;
        }
        return false;
    },

    /**
     * Update the connection status indicator
     */
    updateConnectionStatus(connected) {
        const statusEl = document.getElementById('connection-status');
        const dot = statusEl.querySelector('.status-dot');
        const text = statusEl.querySelector('.status-text');

        if (connected) {
            dot.classList.remove('disconnected');
            dot.classList.add('connected');
            text.textContent = 'Connected';
        } else {
            dot.classList.remove('connected');
            dot.classList.add('disconnected');
            text.textContent = 'Disconnected';
        }
    },

    /**
     * Make a REST API call
     */
    async api(endpoint, options = {}) {
        const url = `/api${endpoint}`;
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }

        try {
            return await response.json();
        } catch (e) {
            throw new Error('Failed to parse JSON response');
        }
    },

    /**
     * GET request helper
     */
    async get(endpoint) {
        return this.api(endpoint);
    },

    /**
     * POST request helper
     */
    async post(endpoint, data) {
        return this.api(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
};
