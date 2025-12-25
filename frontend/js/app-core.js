/**
 * Core Application Logic
 * จัดการ Authentication, State, และ Dashboard
 */

function adminApp() {
    return {
        // Authentication
        isLoggedIn: false,
        tokenInput: '',
        adminToken: '',
        
        // UI State
        activeTab: 'dashboard',
        mobileMenuOpen: false,
        settings: {
            darkMode: false
        },
        
        // Stats & Data
        stats: {
            recent_logs: []
        },
        
        // Clock
        currentTime: '',
        currentDate: '',
        clockInterval: null,

        /**
         * Initialize application
         */
        init() {
            this.checkAuth();
            this.startClock();
            this.loadSettings();
        },

        /**
         * Check if user is authenticated
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
         * Login function
         */
        async login() {
            if (!this.tokenInput.trim()) {
                alert('กรุณาระบุ Token');
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
                    await this.refreshAll();
                } else {
                    alert('Token ไม่ถูกต้อง');
                    this.tokenInput = '';
                }
            } catch (e) {
                alert('ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ได้');
            }
        },

        /**
         * Logout function
         */
        logout() {
            if (confirm('ต้องการออกจากระบบใช่หรือไม่?')) {
                localStorage.removeItem('adminToken');
                this.isLoggedIn = false;
                this.adminToken = '';
                this.tokenInput = '';
                this.stopClock();
            }
        },

        /**
         * Switch tab and close mobile menu
         */
        switchTab(tab) {
            this.activeTab = tab;
            this.mobileMenuOpen = false;
            
            // Load content for specific tabs
            if (tab === 'files' && window.loadFilesTab) {
                window.loadFilesTab();
            } else if (tab === 'logs' && window.loadLogsTab) {
                window.loadLogsTab();
            }
        },

        /**
         * API call helper
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
         * Refresh all data
         */
        async refreshAll() {
            try {
                this.stats = await this.apiCall('/api/admin/stats');
            } catch (e) {
                console.error('Failed to load stats:', e);
            }
        },

        /**
         * Calculate average latency
         */
        calculateAvgLatency() {
            if (this.stats.recent_logs.length === 0) return 0;
            const sum = this.stats.recent_logs.reduce((a, b) => a + (b.latency || 0), 0);
            return (sum / this.stats.recent_logs.length).toFixed(0);
        },

        /**
         * Start realtime clock
         */
        startClock() {
            this.updateClock();
            this.clockInterval = setInterval(() => {
                this.updateClock();
            }, 1000);
        },

        /**
         * Stop clock
         */
        stopClock() {
            if (this.clockInterval) {
                clearInterval(this.clockInterval);
                this.clockInterval = null;
            }
        },

        /**
         * Update clock display
         */
        updateClock() {
            const now = new Date();
            
            // Format time (HH:MM:SS)
            const hours = String(now.getHours()).padStart(2, '0');
            const minutes = String(now.getMinutes()).padStart(2, '0');
            const seconds = String(now.getSeconds()).padStart(2, '0');
            this.currentTime = `${hours}:${minutes}:${seconds}`;
            
            // Format date
            const days = ['อาทิตย์', 'จันทร์', 'อังคาร', 'พุธ', 'พฤหัสบดี', 'ศุกร์', 'เสาร์'];
            const months = ['มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน', 
                          'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม'];
            
            const dayName = days[now.getDay()];
            const day = now.getDate();
            const month = months[now.getMonth()];
            const year = now.getFullYear() + 543; // Thai year
            
            this.currentDate = `วัน${dayName}ที่ ${day} ${month} ${year}`;
        },

        /**
         * Load settings from localStorage
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
            
            // Watch for settings changes
            this.$watch('settings', (value) => {
                localStorage.setItem('adminSettings', JSON.stringify(value));
            }, { deep: true });
        }
    };
}