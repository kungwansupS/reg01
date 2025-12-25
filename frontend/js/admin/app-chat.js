function adminChat() {
    return {
        sessions: [],
        currentSession: null,
        messages: [],
        newMessage: '',
        selectedPlatform: 'facebook',
        botSettings: {},
        socket: null,

        async init() {
            // โหลดสถานะ Bot และรายการแชทเริ่มต้น
            await this.refreshSessions();
            this.botSettings = this.$root.stats.bot_settings || {};

            // เชื่อมต่อ Socket.io สำหรับการอัปเดตแบบเรียลไทม์
            this.socket = io();
            
            // รับเหตุการณ์เมื่อมีข้อความใหม่จากลูกค้า
            this.socket.on('admin_new_message', (data) => {
                this.handleIncomingSocket(data, 'user');
            });

            // รับเหตุการณ์เมื่อ Bot พี่เร็กตอบกลับ
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
                // ดึงประวัติการแชทรายบุคคล
                this.messages = await this.$root.apiCall(`/api/admin/chat/history/${session.platform}/${session.id}`);
                this.scrollToBottom();
            } catch (e) { console.error('Load history failed:', e); }
        },

        async sendMessage() {
            if (!this.newMessage.trim() || !this.currentSession) return;
            
            const text = this.newMessage;
            this.newMessage = '';

            // ส่งข้อมูลผ่าน Socket ไปยัง Backend เพื่อตอบกลับลูกค้าทันที
            this.socket.emit('admin_manual_reply', {
                uid: this.currentSession.id,
                platform: this.currentSession.platform,
                text: text
            });

            // อัปเดต UI ฝั่ง Admin ให้เห็นข้อความที่เพิ่งส่งไป (ในรูปแบบ Admin Role)
            this.messages.push({
                role: 'model',
                parts: [{ text: `[Admin]: ${text}` }]
            });
            
            this.scrollToBottom();
        },

        async toggleBot() {
            const currentStatus = this.botSettings[this.selectedPlatform];
            const nextStatus = !currentStatus;
            
            const formData = new FormData();
            formData.append('platform', this.selectedPlatform);
            formData.append('status', nextStatus);

            try {
                // ส่งคำสั่งเปิด/ปิดบอทไปยัง API
                const res = await this.$root.apiCall('/api/admin/bot-toggle', 'POST', formData);
                if (res.status === 'success') {
                    this.botSettings = res.settings;
                }
            } catch (e) { alert('ไม่สามารถเปลี่ยนสถานะ Bot ได้'); }
        },

        handleIncomingSocket(data, role) {
            // รีเฟรชรายการ Session เพื่อเลื่อนคนที่ทักมาใหม่ขึ้นบนสุด
            this.refreshSessions();

            // หากกำลังคุยกับคนนี้อยู่ ให้อัปเดตข้อความในกล่องแชททันที
            if (this.currentSession && this.currentSession.id === data.uid) {
                this.messages.push({
                    role: role,
                    parts: [{ text: data.text }]
                });
                this.scrollToBottom();
            }
        },

        scrollToBottom() {
            setTimeout(() => {
                const container = document.getElementById('message-container');
                if (container) container.scrollTop = container.scrollHeight;
            }, 50);
        }
    };
}