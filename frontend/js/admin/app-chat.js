function adminChat() {
    return {
        sessions: [],
        currentSession: null,
        messages: [],
        newMessage: '',
        botSettings: {},
        socket: null,

        async init() {
            // โหลดรายการแชทและสถานะบอท
            await this.refreshSessions();
            this.botSettings = this.$root.stats.bot_settings || {};

            // เชื่อมต่อ Socket.io
            this.socket = io();
            
            // รับเหตุการณ์เมื่อมีข้อความใหม่จากผู้ใช้
            this.socket.on('admin_new_message', (data) => {
                this.handleIncomingSocket(data, 'user');
            });

            // รับเหตุการณ์เมื่อ Bot หรือ Admin ตอบกลับ
            this.socket.on('admin_bot_reply', (data) => {
                this.handleIncomingSocket(data, 'model');
            });

            // รับ Error จาก Server
            this.socket.on('admin_error', (data) => {
                alert(data.message);
            });
            
            // ตรวจสอบการเปลี่ยนสถานะบอทจาก Dashboard
            this.$watch('$root.stats.bot_settings', (val) => {
                this.botSettings = val || {};
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
                // กรองข้อมูลประวัติที่ถูกต้อง
                this.messages = history.filter(m => m.parts && m.parts[0] && m.parts[0].text);
                this.scrollToBottom();
            } catch (e) { console.error('Load history failed:', e); }
        },

        async sendMessage() {
            const text = this.newMessage.trim();
            if (!text || !this.currentSession) return;
            
            // ตรวจสอบสถานะบอทก่อนส่งในฝั่ง Client
            if (this.botSettings[this.currentSession.platform]) {
                alert('กรุณาปิด Auto Bot ของแพลตฟอร์มนี้ก่อนตอบกลับ');
                return;
            }

            this.newMessage = '';

            // ส่งข้อมูลผ่าน Socket ไปยัง Backend
            this.socket.emit('admin_manual_reply', {
                uid: this.currentSession.id,
                platform: this.currentSession.platform,
                text: text
            });
        },

        async toggleBot(platform) {
            const currentStatus = this.botSettings[platform];
            const nextStatus = !currentStatus;
            
            const formData = new FormData();
            formData.append('platform', platform);
            formData.append('status', nextStatus);

            try {
                const res = await this.$root.apiCall('/api/admin/bot-toggle', 'POST', formData);
                if (res.status === 'success') {
                    this.botSettings = res.settings;
                    this.$root.stats.bot_settings = res.settings;
                }
            } catch (e) { alert('ไม่สามารถสลับสถานะ Bot ได้'); }
        },

        handleIncomingSocket(data, role) {
            // ค้นหาว่า Session นี้มีอยู่ในรายการหรือไม่
            const sessionIndex = this.sessions.findIndex(s => s.id === data.uid && s.platform === data.platform);
            
            if (sessionIndex !== -1) {
                // หากมีอยู่แล้ว ให้อัปเดตข้อมูล (เช่น ชื่อ/รูป) และย้ายขึ้นมาบนสุด
                const existingSession = this.sessions[sessionIndex];
                if (data.user_name) existingSession.profile.name = data.user_name;
                if (data.user_pic) existingSession.profile.picture = data.user_pic;
                
                // ดัน Session นี้ขึ้นบนสุด
                const movedSession = this.sessions.splice(sessionIndex, 1)[0];
                this.sessions.unshift(movedSession);
            } else {
                // หากเป็น Session ใหม่ ให้ดึงรายการใหม่ทั้งหมดจาก API
                this.refreshSessions();
            }

            // หากกำลังเปิดหน้าแชทของคนนี้อยู่ ให้อัปเดตข้อความทันที
            if (this.currentSession && this.currentSession.id === data.uid && this.currentSession.platform === data.platform) {
                // ป้องกันการเพิ่มข้อความซ้ำ (กรณีเป็น Echo จาก Admin เอง)
                const isDuplicate = this.messages.some(m => m.role === role && m.parts[0].text === data.text);
                if (!isDuplicate) {
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
            }, 150);
        }
    };
}