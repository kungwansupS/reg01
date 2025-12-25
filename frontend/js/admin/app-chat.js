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
            console.log('🚀 Initializing Unified Chat...');
            
            // เชื่อมต่อ Socket.IO
            this.initSocket();

            // โหลด Sessions ครั้งแรก
            await this.refreshSessions();

            console.log('✅ Unified Chat initialized');
        },

        initSocket() {
            try {
                this.socket = io();
                
                this.socket.on('connect', () => {
                    console.log('✅ Socket.IO connected');
                });

                this.socket.on('disconnect', () => {
                    console.log('❌ Socket.IO disconnected');
                });
                
                this.socket.on('admin_new_message', (data) => {
                    console.log('📩 New message from user:', data);
                    this.handleIncomingSocket(data, 'user');
                });

                this.socket.on('admin_bot_reply', (data) => {
                    console.log('🤖 Bot reply:', data);
                    this.handleIncomingSocket(data, 'model');
                });

                this.socket.on('admin_error', (data) => {
                    console.error('❌ Admin error:', data);
                    alert(data.message);
                });

                console.log('✅ Socket.IO listeners registered');
            } catch (e) {
                console.error('❌ Failed to initialize socket:', e);
            }
        },

        async refreshSessions() {
            this.loading = true;
            this.error = null;
            
            try {
                console.log('🔄 Refreshing sessions...');
                
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
                
                console.log('📦 Raw sessions data:', data);
                
                if (!Array.isArray(data)) {
                    console.error('❌ Sessions API returned non-array:', typeof data, data);
                    this.error = 'ข้อมูล Session ไม่ถูกต้อง';
                    this.sessions = [];
                    return;
                }
                
                // กรองเฉพาะ Sessions ที่มีข้อมูลครบถ้วน
                const validSessions = data.filter(s => {
                    const isValid = s && s.id && s.platform && s.profile && s.profile.name;
                    if (!isValid) {
                        console.warn('⚠️ Invalid session structure:', s);
                    }
                    return isValid;
                });
                
                this.sessions = validSessions;
                console.log(`✅ Loaded ${this.sessions.length} valid sessions`);
                
                if (this.sessions.length === 0) {
                    console.log('ℹ️ No sessions available');
                }
            } catch (e) { 
                console.error('❌ Refresh sessions failed:', e); 
                this.error = 'ไม่สามารถโหลด Sessions ได้: ' + e.message;
                this.sessions = [];
            } finally {
                this.loading = false;
            }
        },

        async selectSession(session) {
            if (!session || !session.id) {
                console.error('❌ Invalid session selected:', session);
                return;
            }

            console.log('👆 Selecting session:', session);
            this.currentSession = session;
            this.messages = [];
            this.loading = true;
            this.error = null;
            
            try {
                console.log(`📖 Loading history for ${session.platform}/${session.id}`);
                
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
                
                console.log('📦 Raw history data:', history);
                
                if (!Array.isArray(history)) {
                    console.warn('⚠️ History is not an array:', typeof history, history);
                    this.messages = [];
                    this.error = 'ข้อมูลประวัติไม่ถูกต้อง';
                    return;
                }
                
                // กรองเฉพาะข้อความที่ถูกต้อง
                this.messages = history.filter(m => {
                    const isValid = m 
                        && m.parts 
                        && Array.isArray(m.parts) 
                        && m.parts[0] 
                        && m.parts[0].text
                        && (m.role === 'user' || m.role === 'model');
                    
                    if (!isValid && m) {
                        console.warn('⚠️ Invalid message structure:', m);
                    }
                    return isValid;
                });
                
                console.log(`✅ Displaying ${this.messages.length} messages`);
                
                if (this.messages.length === 0) {
                    console.log('ℹ️ No messages in this session');
                }
                
                this.scrollToBottom();
            } catch (e) { 
                console.error('❌ Load history failed:', e); 
                this.messages = [];
                this.error = 'ไม่สามารถโหลดประวัติการสนทนาได้: ' + e.message;
            } finally {
                this.loading = false;
            }
        },

        async sendMessage() {
            const text = this.newMessage.trim();
            
            if (!text) {
                console.log('⚠️ Empty message, ignoring');
                return;
            }
            
            if (!this.currentSession) {
                console.error('❌ No session selected');
                alert('กรุณาเลือก Session ก่อนส่งข้อความ');
                return;
            }
            
            // ✅ ตรวจสอบสถานะ Bot ของ Session นี้
            if (this.currentSession.bot_enabled) {
                console.warn('⚠️ Bot is enabled for session:', this.currentSession.id);
                alert('กรุณาปิด Auto Bot ของ Session นี้ก่อนตอบกลับ');
                return;
            }

            console.log('📤 Sending manual reply:', {
                uid: this.currentSession.id,
                platform: this.currentSession.platform,
                text: text
            });

            this.newMessage = '';

            // ส่งข้อความผ่าน Socket
            this.socket.emit('admin_manual_reply', {
                uid: this.currentSession.id,
                platform: this.currentSession.platform,
                text: text
            });
        },

        async toggleBot(session) {
            const currentStatus = session.bot_enabled;
            const nextStatus = !currentStatus;
            
            console.log(`🔄 Toggling bot for ${session.id}: ${currentStatus} → ${nextStatus}`);
            
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
                    // ✅ อัปเดต session ใน list
                    session.bot_enabled = nextStatus;
                    
                    // ✅ อัปเดต currentSession ถ้าเป็น session เดียวกัน
                    if (this.currentSession && this.currentSession.id === session.id) {
                        this.currentSession.bot_enabled = nextStatus;
                    }
                    
                    console.log('✅ Bot status updated:', res);
                } else {
                    console.error('❌ Unexpected response:', res);
                }
            } catch (e) { 
                console.error('❌ Failed to toggle bot:', e);
                alert('ไม่สามารถสลับสถานะ Bot ได้'); 
            }
        },

        async toggleAllBots(status) {
            const action = status ? 'เปิด' : 'ปิด';
            
            if (!confirm(`ต้องการ${action} Auto Bot ทั้งหมดทุก Session หรือไม่?`)) {
                return;
            }
            
            console.log(`🔄 Toggling ALL bots: ${status}`);
            
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
                    console.log(`✅ Updated ${res.updated_count} sessions`);
                    
                    // ✅ อัปเดตทุก session ใน list
                    this.sessions.forEach(s => {
                        s.bot_enabled = status;
                    });
                    
                    // ✅ อัปเดต currentSession ถ้ามี
                    if (this.currentSession) {
                        this.currentSession.bot_enabled = status;
                    }
                    
                    alert(`${action} Auto Bot ทั้งหมดสำเร็จ (${res.updated_count} sessions)`);
                } else {
                    console.error('❌ Unexpected response:', res);
                }
            } catch (e) { 
                console.error('❌ Failed to toggle all bots:', e);
                alert('ไม่สามารถสลับสถานะ Bot ได้'); 
            }
        },

        handleIncomingSocket(data, role) {
            console.log(`📨 Incoming socket (${role}):`, data);
            
            if (!data || !data.uid || !data.platform) {
                console.error('❌ Invalid socket data:', data);
                return;
            }
            
            const sessionId = data.uid;
            
            // อัปเดตหรือสร้าง Session ใหม่
            const existingIndex = this.sessions.findIndex(s => s.id === sessionId);
            
            if (existingIndex !== -1) {
                // ย้าย Session ไปด้านบน
                const movedSession = this.sessions.splice(existingIndex, 1)[0];
                this.sessions.unshift(movedSession);
                console.log('📌 Moved session to top:', sessionId);
            } else {
                // สร้าง Session ใหม่
                const newSession = {
                    id: sessionId,
                    platform: data.platform,
                    profile: {
                        name: data.user_name || `${data.platform} User`,
                        picture: data.user_pic || 'https://www.gravatar.com/avatar/?d=mp'
                    },
                    bot_enabled: true  // ✅ Default เปิด
                };
                this.sessions.unshift(newSession);
                console.log('✨ Created new session:', newSession);
            }

            // ถ้า Session ที่ได้รับข้อความคือ Session ที่เปิดอยู่ ให้เพิ่มข้อความเข้าไป
            if (this.currentSession && this.currentSession.id === sessionId) {
                // ตรวจสอบว่ามีข้อความซ้ำหรือไม่
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
                    console.log(`✅ Added message to current session (${role})`);
                    this.scrollToBottom();
                } else {
                    console.log('⚠️ Duplicate message detected, skipping');
                }
            }
        },

        scrollToBottom() {
            this.$nextTick(() => {
                setTimeout(() => {
                    const container = document.getElementById('message-container');
                    if (container) {
                        container.scrollTop = container.scrollHeight;
                        console.log('📜 Scrolled to bottom');
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
                facebook: '📘',
                web: '🌐',
                line: '💬'
            };
            return icons[platform] || '💬';
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