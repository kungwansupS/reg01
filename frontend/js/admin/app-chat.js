// [FILE: frontend/js/admin/app-chat.js - FULLCODE ONLY]
function adminChat() {
    return {
        sessions: [],
        currentSession: null,
        messages: [],
        newMessage: '',
        socket: null,

        async init() {
            await this.refreshSessions();
            
            // เชื่อมต่อ Socket.io
            this.socket = io();
            
            this.socket.on('admin_new_message', (data) => {
                this.handleIncomingSocket(data, 'user');
            });

            this.socket.on('admin_bot_reply', (data) => {
                this.handleIncomingSocket(data, 'model');
            });
        },

        async refreshSessions() {
            try {
                this.sessions = await this.$root.apiCall('/api/admin/chat/sessions');
            } catch (e) { console.error('Refresh sessions failed:', e); }
        },

        async selectSession(session) {
            this.currentSession = session;
            try {
                const history = await this.$root.apiCall(`/api/admin/chat/history/${session.platform}/${session.id}`);
                this.messages = history.history.filter(m => m.parts && m.parts[0] && m.parts[0].text);
                this.scrollToBottom();
            } catch (e) { console.error('Load history failed:', e); }
        },

        async sendMessage() {
            const text = this.newMessage.trim();
            if (!text || !this.currentSession) return;
            
            this.newMessage = '';
            this.socket.emit('admin_manual_reply', {
                uid: this.currentSession.id,
                platform: this.currentSession.platform,
                text: text
            });
            this.scrollToBottom();
        },

        async toggleUserBot() {
            if (!this.currentSession) return;
            
            const nextStatus = !this.currentSession.bot_enabled;
            const formData = new FormData();
            formData.append('platform', this.currentSession.platform);
            formData.append('uid', this.currentSession.id);
            formData.append('status', nextStatus.toString());

            try {
                const res = await this.$root.apiCall('/api/admin/bot-toggle', 'POST', formData);
                if (res.status === 'success') {
                    this.currentSession.bot_enabled = nextStatus;
                    // อัปเดตในรายการด้านข้างด้วย
                    const idx = this.sessions.findIndex(s => s.id === this.currentSession.id && s.platform === this.currentSession.platform);
                    if (idx !== -1) this.sessions[idx].bot_enabled = nextStatus;
                }
            } catch (e) { alert('ไม่สามารถเปลี่ยนสถานะบอทรายบุคคลได้'); }
        },

        async toggleGlobalBot(platform) {
            const currentStatus = this.$root.stats.bot_settings[platform];
            const nextStatus = !currentStatus;
            
            const formData = new FormData();
            formData.append('platform', platform);
            formData.append('status', nextStatus.toString());

            try {
                const res = await this.$root.apiCall('/api/admin/bot-toggle', 'POST', formData);
                if (res.status === 'success') {
                    this.$root.stats.bot_settings = res.settings;
                }
            } catch (e) { alert('ไม่สามารถเปลี่ยนสถานะบอทระดับโกลบอลได้'); }
        },

        handleIncomingSocket(data, role) {
            // อัปเดตสถานะ New Message หรือย้าย Session ขึ้นด้านบน
            const idx = this.sessions.findIndex(s => s.id === data.uid && s.platform === data.platform);
            if (idx === -1) {
                this.refreshSessions();
            } else {
                // ย้าย session ที่คุยล่าสุดขึ้นบนสุด
                const session = this.sessions.splice(idx, 1)[0];
                this.sessions.unshift(session);
            }

            if (this.currentSession && this.currentSession.id === data.uid && this.currentSession.platform === data.platform) {
                const isDuplicate = this.messages.some(m => m.parts[0].text === data.text);
                if (!isDuplicate || role === 'user') {
                    this.messages.push({
                        role: role,
                        parts: [{ text: data.text }]
                    });
                    this.scrollToBottom();
                }
            }
        },

        scrollToBottom() {
            setTimeout(() => {
                const container = document.getElementById('message-container');
                if (container) container.scrollTop = container.scrollHeight;
            }, 100);
        }
    };
}