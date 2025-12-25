function adminChat() {
    return {
        sessions: [],
        currentSession: null,
        messages: [],
        newMessage: '',
        botSettings: {},
        socket: null,

        async init() {
            await this.refreshSessions();
            this.botSettings = this.$root.stats.bot_settings || {};

            // เชื่อมต่อ Socket.io
            this.socket = io();
            
            // รับเหตุการณ์เมื่อมีข้อความใหม่จากลูกค้า
            this.socket.on('admin_new_message', (data) => {
                this.handleIncomingSocket(data, 'user');
            });

            // รับเหตุการณ์เมื่อ Bot หรือ Admin ตอบกลับ
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
                // ดึงประวัติการแชท
                const res = await this.$root.apiCall(`/api/admin/chat/history/${session.platform}/${session.id}`);
                // แก้ไข: เข้าถึง property 'history' ของ Object ที่ได้รับมา
                const historyArray = res.history || [];
                this.messages = historyArray.filter(m => m.parts && m.parts[0] && m.parts[0].text);
                this.scrollToBottom();
            } catch (e) { 
                console.error('Load history failed:', e);
                this.messages = [];
            }
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

        async toggleGlobalBot(platform) {
            const nextStatus = !this.botSettings[platform];
            const formData = new FormData();
            formData.append('platform', platform);
            formData.append('status', nextStatus.toString());

            try {
                const res = await this.$root.apiCall('/api/admin/bot-toggle', 'POST', formData);
                if (res.status === 'success') {
                    this.botSettings = res.settings;
                    this.$root.stats.bot_settings = res.settings;
                }
            } catch (e) { alert('ไม่สามารถเปลี่ยนสถานะ Bot รวมได้'); }
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
                    // อัปเดตสถานะในรายการ sessions ทันที
                    const idx = this.sessions.findIndex(s => s.id === this.currentSession.id && s.platform === this.currentSession.platform);
                    if (idx !== -1) this.sessions[idx].bot_enabled = nextStatus;
                }
            } catch (e) { alert('ไม่สามารถเปลี่ยนสถานะบอทรายบุคคลได้'); }
        },

        handleIncomingSocket(data, role) {
            // อัปเดตรายการ Session (ย้ายขึ้นบนสุดหรือเพิ่มใหม่)
            const idx = this.sessions.findIndex(s => s.id === data.uid && s.platform === data.platform);
            if (idx === -1) {
                this.refreshSessions();
            } else {
                const session = this.sessions.splice(idx, 1)[0];
                this.sessions.unshift(session);
            }

            // อัปเดตข้อความในหน้าต่างแชทปัจจุบัน
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