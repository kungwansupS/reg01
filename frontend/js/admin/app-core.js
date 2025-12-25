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
        
        // Data State
        stats: {
            recent_logs: [],
            bot_settings: {} // เพิ่มเข้ามาใน Phase 2 เพื่อเก็บสถานะการเปิด/ปิด Bot
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
                this.showNotification('กรุณาระบุ Security Token', 'warning');
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
                    this.showNotification('เข้าสู่ระบบสำเร็จ', 'success');
                } else {
                    this.showNotification('Security Token ไม่ถูกต้อง', 'error');
                    this.tokenInput = '';
                }
            } catch (e) {
                this.showNotification('ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ได้', 'error');
                console.error('Login error:', e);
            }
        },

        /**
         * Logout Handler
         */
        logout() {
            if (confirm('ต้องการออกจากระบบหรือไม่?')) {
                localStorage.removeItem('adminToken');
                this.isLoggedIn = false;
                this.adminToken = '';
                this.tokenInput = '';
                this.stopClock();
                this.showNotification('ออกจากระบบเรียบร้อย', 'success');
            }
        },

        /**
         * Switch Active Tab
         */
        switchTab(tab) {
            this.activeTab = tab;
            this.mobileMenuOpen = false;
            
            // Load tab-specific content
            if (tab === 'files' && window.loadFilesTab) {
                window.loadFilesTab();
            } else if (tab === 'logs' && window.loadLogsTab) {
                window.loadLogsTab();
            }
            // หมายเหตุ: Tab 'chat' จะถูกจัดการโดยคอมโพเนนต์ adminChat ในไฟล์ app-chat.js
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
            } catch (e) {
                console.error('Failed to load stats:', e);
                this.showNotification('ไม่สามารถโหลดข้อมูลได้', 'error');
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
            const days = ['อาทิตย์', 'จันทร์', 'อังคาร', 'พุธ', 'พฤหัสบดี', 'ศุกร์', 'เสาร์'];
            const months = ['มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน', 
                          'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม'];
            
            const dayName = days[now.getDay()];
            const day = now.getDate();
            const month = months[now.getMonth()];
            const year = now.getFullYear() + 543; // Buddhist Era
            
            this.currentDate = `วัน${dayName}ที่ ${day} ${month} ${year}`;
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
                alert('❌ ' + message);
            } else if (type === 'success') {
                alert('✅ ' + message);
            } else if (type === 'warning') {
                alert('⚠️ ' + message);
            } else {
                alert('ℹ️ ' + message);
            }
        }
    };
}