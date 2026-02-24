function adminApp() {
    return {
        // Authentication State
        isLoggedIn: false,
        tokenInput: '',
        adminToken: '',
        
        // UI State
        activeTab: 'dashboard',
        mobileMenuOpen: false,
        settings: {
            darkMode: false
        },
        
        // Context Menu (for files module)
        contextMenu: {
            show: false,
            x: 0,
            y: 0,
            entry: null
        },
        
        // Module instances
        chat: null,
        files: null,
        logs: null,
        database: null,
        faq: null,
        monitor: null,
        
        // Data State
        stats: {
            recent_logs: [],
            bot_settings: {},
            faq_analytics: {}
        },
        
        sessionStats: {
            botEnabled: 0,
            botDisabled: 0
        },
        
        // Clock State
        currentTime: '',
        currentDate: '',
        clockInterval: null,

        /**
         * Initialize Application
         */
        init() {
            this.checkAuth();
            this.loadSettings();
            if (this.isLoggedIn) {
                this.startClock();
            }
            
            // Initialize modules
            if (typeof initChatModule === 'function') {
                initChatModule(this);
            }
            if (typeof initFilesModule === 'function') {
                initFilesModule(this);
            }
            if (typeof initLogsModule === 'function') {
                initLogsModule(this);
            }
            if (typeof initDatabaseModule === 'function') {
                initDatabaseModule(this);
            }
            if (typeof initFaqModule === 'function') {
                initFaqModule(this);
            }
            if (typeof initMonitorModule === 'function') {
                initMonitorModule(this);
            }
        },

        /**
         * Check Authentication Status
         */
        checkAuth() {
            const token = localStorage.getItem('adminToken');
            if (token) {
                this.adminToken = token;
                this.isLoggedIn = true;
                this.refreshAll();
            }
        },

        /**
         * Login Handler
         */
        async login() {
            if (!this.tokenInput.trim()) {
                this.showNotification('เธเธฃเธธเธ“เธฒเธฃเธฐเธเธธ Security Token', 'warning');
                return;
            }

            try {
                const res = await fetch('/api/admin/stats', {
                    headers: { 'X-Admin-Token': this.tokenInput }
                });

                if (res.ok) {
                    this.adminToken = this.tokenInput;
                    localStorage.setItem('adminToken', this.adminToken);
                    this.isLoggedIn = true;
                    this.startClock();
                    await this.refreshAll();
                    this.showNotification('เน€เธเนเธฒเธชเธนเนเธฃเธฐเธเธเธชเธณเน€เธฃเนเธ', 'success');
                } else {
                    this.showNotification('Security Token เนเธกเนเธ–เธนเธเธ•เนเธญเธ', 'error');
                    this.tokenInput = '';
                }
            } catch (e) {
                this.showNotification('เนเธกเนเธชเธฒเธกเธฒเธฃเธ–เน€เธเธทเนเธญเธกเธ•เนเธญเธเธฑเธเน€เธเธดเธฃเนเธเน€เธงเธญเธฃเนเนเธ”เน', 'error');
                console.error('Login error:', e);
            }
        },

        /**
         * Logout Handler
         */
        logout() {
            if (confirm('เธ•เนเธญเธเธเธฒเธฃเธญเธญเธเธเธฒเธเธฃเธฐเธเธเธซเธฃเธทเธญเนเธกเน?')) {
                localStorage.removeItem('adminToken');
                this.isLoggedIn = false;
                this.adminToken = '';
                this.tokenInput = '';
                this.stopClock();
                this.showNotification('เธญเธญเธเธเธฒเธเธฃเธฐเธเธเน€เธฃเธตเธขเธเธฃเนเธญเธข', 'success');
            }
        },

        /**
         * Switch Active Tab
         */
        switchTab(tab) {
            this.activeTab = tab;
            this.mobileMenuOpen = false;
            
            // Load tab-specific content
            if (tab === 'chat' && this.chat) {
                this.chat.loadSessions();
            } else if (tab === 'files') {
                if (this.files) {
                    this.files.render();
                } else if (window.loadFilesTab) {
                    window.loadFilesTab();
                }
            } else if (tab === 'logs') {
                if (this.logs) {
                    this.logs.render();
                } else if (window.loadLogsTab) {
                    window.loadLogsTab();
                }
            } else if (tab === 'database' && this.database) {
                this.database.render();
                this.database.loadSessions();
            } else if (tab === 'faq' && this.faq) {
                this.faq.loadEntries();
            } else if (tab === 'monitor' && this.monitor) {
                this.monitor.start();
            }

            // Stop monitor auto-refresh when leaving
            if (tab !== 'monitor' && this.monitor && this.monitor.stop) {
                this.monitor.stop();
            }
        },

        /**
         * API Call Helper
         */
        async apiCall(endpoint, method = 'GET', body = null) {
            const config = {
                method,
                headers: { 'X-Admin-Token': this.adminToken }
            };
            
            if (body && !(body instanceof FormData)) {
                config.headers['Content-Type'] = 'application/json';
                config.body = JSON.stringify(body);
            }
            
            if (body instanceof FormData) {
                config.body = body;
            }
            
            const res = await fetch(endpoint, config);
            if (!res.ok) throw new Error('API Error');
            return res.json();
        },

        /**
         * Refresh All Dashboard Data
         */
        async refreshAll() {
            try {
                this.stats = await this.apiCall('/api/admin/stats');
                
                // เนเธซเธฅเธ”เธเนเธญเธกเธนเธฅ Session Stats
                await this.loadSessionStats();
            } catch (e) {
                console.error('Failed to load stats:', e);
                this.showNotification('เนเธกเนเธชเธฒเธกเธฒเธฃเธ–เนเธซเธฅเธ”เธเนเธญเธกเธนเธฅเนเธ”เน', 'error');
            }
        },

        /**
         * Load Session Stats
         */
        async loadSessionStats() {
            try {
                const sessions = await this.apiCall('/api/admin/chat/sessions');
                
                if (Array.isArray(sessions)) {
                    this.sessionStats.botEnabled = sessions.filter(s => s.bot_enabled).length;
                    this.sessionStats.botDisabled = sessions.filter(s => !s.bot_enabled).length;
                }
            } catch (e) {
                console.error('Failed to load session stats:', e);
            }
        },

        /**
         * Calculate Average Latency
         */
        calculateAvgLatency() {
            if (!this.stats.recent_logs || this.stats.recent_logs.length === 0) return 0;
            const sum = this.stats.recent_logs.reduce((a, b) => a + (b.latency || 0), 0);
            return (sum / this.stats.recent_logs.length).toFixed(0);
        },

        /**
         * Get Active Sessions Count
         */
        getActiveSessionsCount() {
            // เธเธฑเธเธเธณเธเธงเธ unique sessions
            if (!this.stats.recent_logs) return 0;
            const uniqueSessions = new Set(this.stats.recent_logs.map(log => log.anon_id));
            return uniqueSessions.size;
        },

        /**
         * Get Platform Count
         */
        getPlatformCount(platform) {
            if (!this.stats.recent_logs) return 0;
            return this.stats.recent_logs.filter(log => log.platform === platform).length;
        },

        /**
         * Get Bot Enabled Count
         */
        getBotEnabledCount() {
            return this.sessionStats?.botEnabled || 0;
        },

        /**
         * Get Bot Disabled Count
         */
        getBotDisabledCount() {
            return this.sessionStats?.botDisabled || 0;
        },

        /**
         * Get Auto Response Rate
         */
        getAutoResponseRate() {
            const total = this.getBotEnabledCount() + this.getBotDisabledCount();
            if (total === 0) return 100;
            return ((this.getBotEnabledCount() / total) * 100).toFixed(0);
        },

        /**
         * Get Cache Hit Rate
         */
        getCacheHitRate() {
            if (!this.stats.faq_analytics?.total_knowledge_base) return 0;
            const totalKB = this.stats.faq_analytics.total_knowledge_base;
            const topHits = this.stats.faq_analytics.top_faqs?.reduce((sum, faq) => sum + faq.hits, 0) || 0;
            if (totalKB === 0) return 0;
            return Math.min(100, ((topHits / totalKB) * 10).toFixed(0));
        },

        /**
         * Format Time
         */
        formatTime(timestamp) {
            const date = new Date(timestamp);
            const hours = String(date.getHours()).padStart(2, '0');
            const minutes = String(date.getMinutes()).padStart(2, '0');
            return `${hours}:${minutes}`;
        },

        /**
         * Start Real-time Clock
         */
        startClock() {
            this.updateClock();
            this.clockInterval = setInterval(() => {
                this.updateClock();
            }, 1000);
        },

        /**
         * Stop Clock
         */
        stopClock() {
            if (this.clockInterval) {
                clearInterval(this.clockInterval);
                this.clockInterval = null;
            }
        },

        /**
         * Update Clock Display
         */
        updateClock() {
            const now = new Date();
            
            // Format time (HH:MM:SS)
            const hours = String(now.getHours()).padStart(2, '0');
            const minutes = String(now.getMinutes()).padStart(2, '0');
            const seconds = String(now.getSeconds()).padStart(2, '0');
            this.currentTime = `${hours}:${minutes}:${seconds}`;
            
            // Format date (Thai)
            const days = ['เธญเธฒเธ—เธดเธ•เธขเน', 'เธเธฑเธเธ—เธฃเน', 'เธญเธฑเธเธเธฒเธฃ', 'เธเธธเธ', 'เธเธคเธซเธฑเธชเธเธ”เธต', 'เธจเธธเธเธฃเน', 'เน€เธชเธฒเธฃเน'];
            const months = ['เธกเธเธฃเธฒเธเธก', 'เธเธธเธกเธ เธฒเธเธฑเธเธเน', 'เธกเธตเธเธฒเธเธก', 'เน€เธกเธฉเธฒเธขเธ', 'เธเธคเธฉเธ เธฒเธเธก', 'เธกเธดเธ–เธธเธเธฒเธขเธ', 
                          'เธเธฃเธเธเธฒเธเธก', 'เธชเธดเธเธซเธฒเธเธก', 'เธเธฑเธเธขเธฒเธขเธ', 'เธ•เธธเธฅเธฒเธเธก', 'เธเธคเธจเธเธดเธเธฒเธขเธ', 'เธเธฑเธเธงเธฒเธเธก'];
            
            const dayName = days[now.getDay()];
            const day = now.getDate();
            const month = months[now.getMonth()];
            const year = now.getFullYear() + 543; // Buddhist Era
            
            this.currentDate = `เธงเธฑเธ${dayName}เธ—เธตเน ${day} ${month} ${year}`;
        },

        /**
         * Load Settings from LocalStorage
         */
        loadSettings() {
            const savedSettings = localStorage.getItem('adminSettings');
            if (savedSettings) {
                try {
                    this.settings = JSON.parse(savedSettings);
                } catch (e) {
                    console.error('Failed to load settings:', e);
                }
            }
            
            // Watch for settings changes and persist
            this.$watch('settings', (value) => {
                localStorage.setItem('adminSettings', JSON.stringify(value));
            }, { deep: true });
        },

        /**
         * Show Notification (Simple alert for now, can be enhanced)
         */
        showNotification(message, type = 'info') {
            if (type === 'error') {
                alert('โ ' + message);
            } else if (type === 'success') {
                alert('โ… ' + message);
            } else if (type === 'warning') {
                alert('โ ๏ธ ' + message);
            } else {
                alert('โน๏ธ ' + message);
            }
        },
        
        /**
         * Show Toast (alias for modules that use showToast)
         */
        showToast(message, type = 'info') {
            this.showNotification(message, type);
        }
    };
}
