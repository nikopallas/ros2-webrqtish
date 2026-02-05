/**
 * Topic Panel - handles topic listing, subscription, and message display
 */
const TopicPanel = {
    topics: [],
    selectedTopic: null,
    subscribedTopics: new Set(),
    topicHandlers: {},  // Store handlers per topic
    messageCount: 0,
    lastMessageTime: 0,
    messageRateInterval: null,

    /**
     * Initialize the topic panel
     */
    init() {
        this.bindEvents();
        this.loadTopics();
        this.startMessageRateCounter();
    },

    /**
     * Bind UI events
     */
    bindEvents() {
        document.getElementById('refresh-topics').addEventListener('click', () => {
            this.loadTopics();
        });

        document.getElementById('topic-search').addEventListener('input', (e) => {
            this.filterTopics(e.target.value);
        });

        document.getElementById('subscribe-btn').addEventListener('click', () => {
            this.toggleSubscription();
        });

        document.getElementById('publish-btn').addEventListener('click', () => {
            this.publishMessage();
        });
    },

    /**
     * Load topics from the API
     */
    async loadTopics() {
        try {
            this.topics = await App.get('/topics');
            this.renderTopics();
        } catch (e) {
            console.error('Failed to load topics:', e);
        }
    },

    /**
     * Render the topic list
     */
    renderTopics(filter = '') {
        const container = document.getElementById('topic-list');
        const filterLower = filter.toLowerCase();

        const filteredTopics = this.topics.filter(topic =>
            topic.name.toLowerCase().includes(filterLower) ||
            topic.msg_type.toLowerCase().includes(filterLower)
        );

        container.innerHTML = filteredTopics.map(topic => `
            <div class="topic-item ${this.selectedTopic?.name === topic.name ? 'selected' : ''}"
                 data-topic="${topic.name}">
                <div class="topic-name">${topic.name}</div>
                <div class="topic-type">${topic.msg_type}</div>
                <div class="topic-stats">
                    ${topic.publishers.length} pub / ${topic.subscribers.length} sub
                </div>
            </div>
        `).join('');

        // Add click handlers
        container.querySelectorAll('.topic-item').forEach(item => {
            item.addEventListener('click', () => {
                this.selectTopic(item.dataset.topic);
            });
        });
    },

    /**
     * Filter topics by search term
     */
    filterTopics(term) {
        this.renderTopics(term);
    },

    /**
     * Select a topic
     */
    selectTopic(topicName) {
        const topic = this.topics.find(t => t.name === topicName);
        if (!topic) return;

        this.selectedTopic = topic;
        this.renderTopics(document.getElementById('topic-search').value);
        this.updateDetailsPanel();
    },

    /**
     * Update the details panel for the selected topic
     */
    updateDetailsPanel() {
        const nameEl = document.getElementById('selected-topic-name');
        const subscribeBtn = document.getElementById('subscribe-btn');
        const publishBtn = document.getElementById('publish-btn');
        const messageContent = document.getElementById('message-content');

        if (!this.selectedTopic) {
            nameEl.textContent = 'Select a topic';
            subscribeBtn.disabled = true;
            publishBtn.disabled = true;
            return;
        }

        nameEl.textContent = this.selectedTopic.name;
        subscribeBtn.disabled = false;
        publishBtn.disabled = false;

        // Update subscribe button state
        const isSubscribed = this.subscribedTopics.has(this.selectedTopic.name);
        subscribeBtn.textContent = isSubscribed ? 'Unsubscribe' : 'Subscribe';
        subscribeBtn.classList.toggle('subscribed', isSubscribed);

        // Set default publish data
        const publishData = document.getElementById('publish-data');
        if (!publishData.value || publishData.value === '{"data": "Hello"}') {
            publishData.value = this.getDefaultMessageData(this.selectedTopic.msg_type);
        }

        // Clear message display if not subscribed
        if (!isSubscribed) {
            messageContent.textContent = 'Subscribe to see messages';
            this.messageCount = 0;
        }
    },

    /**
     * Get default message data based on message type
     */
    getDefaultMessageData(msgType) {
        const defaults = {
            'std_msgs/msg/String': '{"data": "Hello from web GUI"}',
            'std_msgs/msg/Int32': '{"data": 0}',
            'std_msgs/msg/Float64': '{"data": 0.0}',
            'std_msgs/msg/Bool': '{"data": true}',
            'geometry_msgs/msg/Twist': '{"linear": {"x": 0.0, "y": 0.0, "z": 0.0}, "angular": {"x": 0.0, "y": 0.0, "z": 0.0}}',
            'geometry_msgs/msg/Pose': '{"position": {"x": 0.0, "y": 0.0, "z": 0.0}, "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}}'
        };
        return defaults[msgType] || '{}';
    },

    /**
     * Toggle subscription for the selected topic
     */
    toggleSubscription() {
        if (!this.selectedTopic) return;

        const topic = this.selectedTopic.name;
        const isSubscribed = this.subscribedTopics.has(topic);

        if (isSubscribed) {
            // Unsubscribe
            App.unsubscribe(topic);
            if (this.topicHandlers[topic]) {
                App.offTopicMessage(topic, this.topicHandlers[topic]);
                delete this.topicHandlers[topic];
            }
            this.subscribedTopics.delete(topic);
        } else {
            // Subscribe
            App.subscribe(topic);
            const subscribedTopic = topic;
            const handler = (data, topicName) => {
                if (topicName === subscribedTopic) {
                    this.displayMessage(data);
                }
            };
            this.topicHandlers[topic] = handler;
            App.onTopicMessage(topic, handler);
            this.subscribedTopics.add(topic);
        }

        this.updateDetailsPanel();
    },

    /**
     * Display a received message
     */
    displayMessage(data) {
        const messageContent = document.getElementById('message-content');
        messageContent.textContent = JSON.stringify(data, null, 2);
        this.messageCount++;
        this.lastMessageTime = Date.now();
    },

    /**
     * Start the message rate counter
     */
    startMessageRateCounter() {
        let lastCount = 0;

        this.messageRateInterval = setInterval(() => {
            const rate = this.messageCount - lastCount;
            lastCount = this.messageCount;
            document.getElementById('message-rate').textContent = `${rate} msg/s`;
        }, 1000);
    },

    /**
     * Publish a message to the selected topic
     */
    async publishMessage() {
        if (!this.selectedTopic) return;

        const publishData = document.getElementById('publish-data').value;
        let data;

        try {
            data = JSON.parse(publishData);
        } catch (e) {
            alert('Invalid JSON: ' + e.message);
            return;
        }

        try {
            await App.post(`/topics${this.selectedTopic.name}/publish`, {
                msg_type: this.selectedTopic.msg_type,
                data: data
            });
            console.log('Message published successfully');
        } catch (e) {
            alert('Failed to publish: ' + e.message);
        }
    }
};
