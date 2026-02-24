function adminChat() {
    return {
        sessions: [],
        currentSession: null,
        messages: [],
        newMessage: '',
        socket: null,
        searchQuery: '',
        loading: false,
        error: null,

        async init() {
            console.log('๐€ Initializing Unified Chat...');
            
            this.initSocket();

            await this.refreshSessions();

            console.log('โ… Unified Chat initialized');
        },

        initSocket() {
            try {
                this.socket = io();
                
                this.socket.on('connect', () => {
                    console.log('โ… Socket.IO connected');
                });

                this.socket.on('disconnect', () => {
                    console.log('โ Socket.IO disconnected');
                });
                
                this.socket.on('admin_new_message', (data) => {
                    console.log('๐“ฉ New message from user:', data);
                    this.handleIncomingSocket(data, 'user');
                });

                this.socket.on('admin_bot_reply', (data) => {
                    console.log('๐ค– Bot reply:', data);
                    this.handleIncomingSocket(data, 'model');
                });

                this.socket.on('admin_error', (data) => {
                    console.error('โ Admin error:', data);
                    alert(data.message);
                });

                console.log('โ… Socket.IO listeners registered');
            } catch (e) {
                console.error('โ Failed to initialize socket:', e);
            }
        },

        async refreshSessions() {
            this.loading = true;
            this.error = null;
            
            try {
                console.log('๐” Refreshing sessions...');
                
                const token = localStorage.getItem('adminToken');
                const response = await fetch('/api/admin/chat/sessions', {
                    headers: {
                        'X-Admin-Token': token
                    }
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const data = await response.json();
                
                console.log('๐“ฆ Raw sessions data:', data);
                
                if (!Array.isArray(data)) {
                    console.error('โ Sessions API returned non-array:', typeof data, data);
                    this.error = 'เธเนเธญเธกเธนเธฅ Session เนเธกเนเธ–เธนเธเธ•เนเธญเธ';
                    this.sessions = [];
                    return;
                }
                
                const validSessions = data.filter(s => {
                    const isValid = s && s.id && s.platform && s.profile && s.profile.name;
                    if (!isValid) {
                        console.warn('โ ๏ธ Invalid session structure:', s);
                    }
                    return isValid;
                });
                
                this.sessions = validSessions;
                console.log(`โ… Loaded ${this.sessions.length} valid sessions`);
                
                if (this.sessions.length === 0) {
                    console.log('โน๏ธ No sessions available');
                }
            } catch (e) { 
                console.error('โ Refresh sessions failed:', e); 
                this.error = 'เนเธกเนเธชเธฒเธกเธฒเธฃเธ–เนเธซเธฅเธ” Sessions เนเธ”เน: ' + e.message;
                this.sessions = [];
            } finally {
                this.loading = false;
            }
        },

        async selectSession(session) {
            if (!session || !session.id) {
                console.error('โ Invalid session selected:', session);
                return;
            }

            console.log('๐‘ Selecting session:', session);
            this.currentSession = session;
            this.messages = [];
            this.loading = true;
            this.error = null;
            
            try {
                console.log(`๐“– Loading history for ${session.platform}/${session.id}`);
                
                const token = localStorage.getItem('adminToken');
                const response = await fetch(
                    `/api/admin/chat/history/${session.platform}/${session.id}`,
                    {
                        headers: {
                            'X-Admin-Token': token
                        }
                    }
                );
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const history = await response.json();
                
                console.log('๐“ฆ Raw history data:', history);
                
                if (!Array.isArray(history)) {
                    console.warn('โ ๏ธ History is not an array:', typeof history, history);
                    this.messages = [];
                    this.error = 'เธเนเธญเธกเธนเธฅเธเธฃเธฐเธงเธฑเธ•เธดเนเธกเนเธ–เธนเธเธ•เนเธญเธ';
                    return;
                }
                
                this.messages = history.filter(m => {
                    const isValid = m 
                        && m.parts 
                        && Array.isArray(m.parts) 
                        && m.parts[0] 
                        && m.parts[0].text
                        && (m.role === 'user' || m.role === 'model');
                    
                    if (!isValid && m) {
                        console.warn('โ ๏ธ Invalid message structure:', m);
                    }
                    return isValid;
                });
                
                console.log(`โ… Displaying ${this.messages.length} messages`);
                
                if (this.messages.length === 0) {
                    console.log('โน๏ธ No messages in this session');
                }
                
                this.scrollToBottom();
            } catch (e) { 
                console.error('โ Load history failed:', e); 
                this.messages = [];
                this.error = 'เนเธกเนเธชเธฒเธกเธฒเธฃเธ–เนเธซเธฅเธ”เธเธฃเธฐเธงเธฑเธ•เธดเธเธฒเธฃเธชเธเธ—เธเธฒเนเธ”เน: ' + e.message;
            } finally {
                this.loading = false;
            }
        },

        async sendMessage() {
            const text = this.newMessage.trim();
            
            if (!text) {
                console.log('โ ๏ธ Empty message, ignoring');
                return;
            }
            
            if (!this.currentSession) {
                console.error('โ No session selected');
                alert('เธเธฃเธธเธ“เธฒเน€เธฅเธทเธญเธ Session เธเนเธญเธเธชเนเธเธเนเธญเธเธงเธฒเธก');
                return;
            }
            
            if (this.currentSession.bot_enabled) {
                console.warn('โ ๏ธ Bot is enabled for session:', this.currentSession.id);
                alert('เธเธฃเธธเธ“เธฒเธเธดเธ” Auto Bot เธเธญเธ Session เธเธตเนเธเนเธญเธเธ•เธญเธเธเธฅเธฑเธ');
                return;
            }

            console.log('๐“ค Sending manual reply:', {
                uid: this.currentSession.id,
                platform: this.currentSession.platform,
                text: text
            });

            this.newMessage = '';
            const adminToken = localStorage.getItem('adminToken') || '';

            // เธชเนเธเธเนเธญเธเธงเธฒเธกเธเนเธฒเธ Socket
            this.socket.emit('admin_manual_reply', {
                uid: this.currentSession.id,
                platform: this.currentSession.platform,
                text: text,
                admin_token: adminToken
            });
        },

        async toggleBot(session) {
            const currentStatus = session.bot_enabled;
            const nextStatus = !currentStatus;
            
            console.log(`๐” Toggling bot for ${session.id}: ${currentStatus} โ’ ${nextStatus}`);
            
            const formData = new FormData();
            formData.append('session_id', session.id);
            formData.append('status', nextStatus);

            try {
                const token = localStorage.getItem('adminToken');
                const response = await fetch('/api/admin/bot-toggle', {
                    method: 'POST',
                    headers: {
                        'X-Admin-Token': token
                    },
                    body: formData
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const res = await response.json();
                
                if (res.status === 'success') {
                    session.bot_enabled = nextStatus;
                    
                    if (this.currentSession && this.currentSession.id === session.id) {
                        this.currentSession.bot_enabled = nextStatus;
                    }
                    
                    console.log('โ… Bot status updated:', res);
                } else {
                    console.error('โ Unexpected response:', res);
                }
            } catch (e) { 
                console.error('โ Failed to toggle bot:', e);
                alert('เนเธกเนเธชเธฒเธกเธฒเธฃเธ–เธชเธฅเธฑเธเธชเธ–เธฒเธเธฐ Bot เนเธ”เน'); 
            }
        },

        async toggleAllBots(status) {
            const action = status ? 'เน€เธเธดเธ”' : 'เธเธดเธ”';
            
            if (!confirm(`เธ•เนเธญเธเธเธฒเธฃ${action} Auto Bot เธ—เธฑเนเธเธซเธกเธ”เธ—เธธเธ Session เธซเธฃเธทเธญเนเธกเน?`)) {
                return;
            }
            
            console.log(`๐” Toggling ALL bots: ${status}`);
            
            const formData = new FormData();
            formData.append('status', status);

            try {
                const token = localStorage.getItem('adminToken');
                const response = await fetch('/api/admin/bot-toggle-all', {
                    method: 'POST',
                    headers: {
                        'X-Admin-Token': token
                    },
                    body: formData
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const res = await response.json();
                
                if (res.status === 'success') {
                    console.log(`โ… Updated ${res.updated_count} sessions`);
                    
                    // โ… เธญเธฑเธเน€เธ”เธ•เธ—เธธเธ session เนเธ list
                    this.sessions.forEach(s => {
                        s.bot_enabled = status;
                    });
                    
                    // โ… เธญเธฑเธเน€เธ”เธ• currentSession เธ–เนเธฒเธกเธต
                    if (this.currentSession) {
                        this.currentSession.bot_enabled = status;
                    }
                    
                    alert(`${action} Auto Bot เธ—เธฑเนเธเธซเธกเธ”เธชเธณเน€เธฃเนเธ (${res.updated_count} sessions)`);
                } else {
                    console.error('โ Unexpected response:', res);
                }
            } catch (e) { 
                console.error('โ Failed to toggle all bots:', e);
                alert('เนเธกเนเธชเธฒเธกเธฒเธฃเธ–เธชเธฅเธฑเธเธชเธ–เธฒเธเธฐ Bot เนเธ”เน'); 
            }
        },

        handleIncomingSocket(data, role) {
            console.log(`๐“จ Incoming socket (${role}):`, data);
            
            if (!data || !data.uid || !data.platform) {
                console.error('โ Invalid socket data:', data);
                return;
            }
            
            const sessionId = data.uid;
            
            // เธญเธฑเธเน€เธ”เธ•เธซเธฃเธทเธญเธชเธฃเนเธฒเธ Session เนเธซเธกเน
            const existingIndex = this.sessions.findIndex(s => s.id === sessionId);
            
            if (existingIndex !== -1) {
                // เธขเนเธฒเธข Session เนเธเธ”เนเธฒเธเธเธ
                const movedSession = this.sessions.splice(existingIndex, 1)[0];
                this.sessions.unshift(movedSession);
                console.log('๐“ Moved session to top:', sessionId);
            } else {
                // เธชเธฃเนเธฒเธ Session เนเธซเธกเน
                const newSession = {
                    id: sessionId,
                    platform: data.platform,
                    profile: {
                        name: data.user_name || `${data.platform} User`,
                        picture: data.user_pic || 'https://www.gravatar.com/avatar/?d=mp'
                    },
                    bot_enabled: true  // โ… Default เน€เธเธดเธ”
                };
                this.sessions.unshift(newSession);
                console.log('โจ Created new session:', newSession);
            }

            // เธ–เนเธฒ Session เธ—เธตเนเนเธ”เนเธฃเธฑเธเธเนเธญเธเธงเธฒเธกเธเธทเธญ Session เธ—เธตเนเน€เธเธดเธ”เธญเธขเธนเน เนเธซเนเน€เธเธดเนเธกเธเนเธญเธเธงเธฒเธกเน€เธเนเธฒเนเธ
            if (this.currentSession && this.currentSession.id === sessionId) {
                // เธ•เธฃเธงเธเธชเธญเธเธงเนเธฒเธกเธตเธเนเธญเธเธงเธฒเธกเธเนเธณเธซเธฃเธทเธญเนเธกเน
                const isDuplicate = this.messages.some(m => 
                    m.role === role 
                    && m.parts[0].text === data.text
                    && Math.abs((m.timestamp || 0) - Date.now()) < 2000
                );
                
                if (!isDuplicate) {
                    this.messages.push({
                        role: role,
                        parts: [{ text: data.text }],
                        timestamp: Date.now()
                    });
                    console.log(`โ… Added message to current session (${role})`);
                    this.scrollToBottom();
                } else {
                    console.log('โ ๏ธ Duplicate message detected, skipping');
                }
            }
        },

        scrollToBottom() {
            this.$nextTick(() => {
                setTimeout(() => {
                    const container = document.getElementById('message-container');
                    if (container) {
                        container.scrollTop = container.scrollHeight;
                        console.log('๐“ Scrolled to bottom');
                    }
                }, 100);
            });
        },
        
        get filteredSessions() {
            if (!this.searchQuery.trim()) {
                return this.sessions;
            }
            
            const query = this.searchQuery.toLowerCase();
            return this.sessions.filter(s => 
                s.profile.name.toLowerCase().includes(query) ||
                s.platform.toLowerCase().includes(query) ||
                s.id.toLowerCase().includes(query)
            );
        },

        getPlatformIcon(platform) {
            const icons = {
                facebook: '๐“',
                web: '๐',
                line: '๐’ฌ'
            };
            return icons[platform] || '๐’ฌ';
        },

        formatTimestamp(timestamp) {
            if (!timestamp) return '';
            const date = new Date(timestamp);
            return date.toLocaleTimeString('th-TH', { 
                hour: '2-digit', 
                minute: '2-digit' 
            });
        }
    };
}
