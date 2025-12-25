// [FILE: frontend/js/admin/app-chat.js - FULLCODE ONLY]
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
            // โหลดรายการแชทเริ่มต้นและสถานะ Bot
            await this.refreshSessions();
            this.botSettings = this.$root.stats.bot_settings || {};

            // เชื่อมต่อ Socket.io
            this.socket = io();
            
            // รับเหตุการณ์เมื่อมีข้อความใหม่จากลูกค้า (ทุก Platform)
            this.socket.on('admin_new_message', (data) => {
                this.handleIncomingSocket(data, 'user');
            });

            // รับเหตุการณ์เมื่อ Bot ตอบกลับ หรือ Admin ตอบกลับ
            this.socket.on('admin_bot_reply', (data) => {
                this.handleIncomingSocket(data, 'model');
            });
            
            // คอยติดตามการเปลี่ยนสถานะ Bot จากหน้า Dashboard
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
                // กรองข้อความและป้องกันโครงสร้างข้อมูลผิดพลาด
                this.messages = history.filter(m => m.parts && m.parts[0] && m.parts[0].text);
                this.scrollToBottom();
            } catch (e) { console.error('Load history failed:', e); }
        },

        async sendMessage() {
            const text = this.newMessage.trim();
            if (!text || !this.currentSession) return;
            
            this.newMessage = '';

            // ส่งข้อมูลผ่าน Socket ไปยัง Backend เพื่อสื่อสารไปยังผู้ใช้ตาม Platform
            this.socket.emit('admin_manual_reply', {
                uid: this.currentSession.id,
                platform: this.currentSession.platform,
                text: text
            });

            // หมายเหตุ: ข้อความจะถูกอัปเดตผ่าน Socket event 'admin_bot_reply' โดยอัตโนมัติ 
            // เพื่อให้แอดมินทุกคนเห็นข้อมูลที่ตรงกัน
            this.scrollToBottom();
        },

        async toggleBot() {
            const currentStatus = this.botSettings[this.selectedPlatform];
            const nextStatus = !currentStatus;
            
            const formData = new FormData();
            formData.append('platform', this.selectedPlatform);
            formData.append('status', nextStatus);

            try {
                const res = await this.$root.apiCall('/api/admin/bot-toggle', 'POST', formData);
                if (res.status === 'success') {
                    this.botSettings = res.settings;
                    this.$root.stats.bot_settings = res.settings;
                }
            } catch (e) { alert('ไม่สามารถเปลี่ยนสถานะ Bot ได้'); }
        },

        handleIncomingSocket(data, role) {
            // อัปเดตรายการ Session ทางซ้ายมือ
            const exists = this.sessions.some(s => s.id === data.uid && s.platform === data.platform);
            if (!exists) {
                this.refreshSessions();
            }

            // หากหน้าต่างแชทปัจจุบันตรงกับลูกค้าคนนี้ ให้อัปเดตข้อความทันที
            if (this.currentSession && this.currentSession.id === data.uid && this.currentSession.platform === data.platform) {
                // ป้องกันข้อความซ้ำในกรณีที่แอดมินพิมพ์เองและได้รับ Echo กลับมา
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