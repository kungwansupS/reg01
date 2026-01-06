// Database Management Module
function initDatabaseModule(app) {
    // Initialize contextMenu if not exists (fix for missing contextMenu error)
    if (!app.contextMenu) {
        app.contextMenu = {
            show: false,
            x: 0,
            y: 0,
            entry: null
        };
    }
    
    app.database = {
        sessions: [],
        selectedSession: null,
        messages: [],
        stats: {
            totalSessions: 0,
            totalMessages: 0,
            activeSessions: 0,
            platforms: {}
        },
        filters: {
            search: '',
            platform: 'all',
            botEnabled: 'all',
            sortBy: 'last_active',
            sortOrder: 'desc'
        },
        editMode: false,
        editingMessage: null,
        
        async loadSessions() {
            try {
                const response = await fetch('/admin/api/database/sessions', {
                    headers: { 'X-Admin-Token': app.adminToken }
                });
                const data = await response.json();
                
                if (data.success) {
                    this.sessions = data.sessions;
                    this.stats = data.stats;
                    this.renderSessionsList();
                }
            } catch (error) {
                console.error('Error loading sessions:', error);
                app.showToast('ไม่สามารถโหลดข้อมูล Session', 'error');
            }
        },
        
        async loadMessages(sessionId) {
            try {
                const response = await fetch(`/admin/api/database/sessions/${sessionId}/messages`, {
                    headers: { 'X-Admin-Token': app.adminToken }
                });
                const data = await response.json();
                
                if (data.success) {
                    this.messages = data.messages;
                    this.selectedSession = this.sessions.find(s => s.session_id === sessionId);
                    this.renderMessages();
                }
            } catch (error) {
                console.error('Error loading messages:', error);
                app.showToast('ไม่สามารถโหลดข้อความ', 'error');
            }
        },
        
        async updateSession(sessionId, updates) {
            try {
                const response = await fetch(`/admin/api/database/sessions/${sessionId}`, {
                    method: 'PATCH',
                    headers: {
                        'X-Admin-Token': app.adminToken,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(updates)
                });
                const data = await response.json();
                
                if (data.success) {
                    app.showToast('อัพเดท Session สำเร็จ', 'success');
                    await this.loadSessions();
                    if (this.selectedSession?.session_id === sessionId) {
                        await this.loadMessages(sessionId);
                    }
                }
            } catch (error) {
                console.error('Error updating session:', error);
                app.showToast('ไม่สามารถอัพเดท Session', 'error');
            }
        },
        
        async deleteSession(sessionId) {
            if (!confirm('คุณแน่ใจหรือไม่ที่จะลบ Session นี้? ข้อความทั้งหมดจะถูกลบด้วย')) {
                return;
            }
            
            try {
                const response = await fetch(`/admin/api/database/sessions/${sessionId}`, {
                    method: 'DELETE',
                    headers: { 'X-Admin-Token': app.adminToken }
                });
                const data = await response.json();
                
                if (data.success) {
                    app.showToast('ลบ Session สำเร็จ', 'success');
                    if (this.selectedSession?.session_id === sessionId) {
                        this.selectedSession = null;
                        this.messages = [];
                    }
                    await this.loadSessions();
                }
            } catch (error) {
                console.error('Error deleting session:', error);
                app.showToast('ไม่สามารถลบ Session', 'error');
            }
        },
        
        async updateMessage(messageId, content) {
            try {
                const response = await fetch(`/admin/api/database/messages/${messageId}`, {
                    method: 'PATCH',
                    headers: {
                        'X-Admin-Token': app.adminToken,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ content })
                });
                const data = await response.json();
                
                if (data.success) {
                    app.showToast('อัพเดทข้อความสำเร็จ', 'success');
                    await this.loadMessages(this.selectedSession.session_id);
                    this.editMode = false;
                    this.editingMessage = null;
                }
            } catch (error) {
                console.error('Error updating message:', error);
                app.showToast('ไม่สามารถอัพเดทข้อความ', 'error');
            }
        },
        
        async deleteMessage(messageId) {
            if (!confirm('คุณแน่ใจหรือไม่ที่จะลบข้อความนี้?')) {
                return;
            }
            
            try {
                const response = await fetch(`/admin/api/database/messages/${messageId}`, {
                    method: 'DELETE',
                    headers: { 'X-Admin-Token': app.adminToken }
                });
                const data = await response.json();
                
                if (data.success) {
                    app.showToast('ลบข้อความสำเร็จ', 'success');
                    await this.loadMessages(this.selectedSession.session_id);
                }
            } catch (error) {
                console.error('Error deleting message:', error);
                app.showToast('ไม่สามารถลบข้อความ', 'error');
            }
        },
        
        async cleanupOldSessions(days) {
            if (!confirm(`คุณแน่ใจหรือไม่ที่จะลบ Session ที่ไม่ได้ใช้งานมากกว่า ${days} วัน?`)) {
                return;
            }
            
            try {
                const response = await fetch(`/admin/api/database/cleanup?days=${days}`, {
                    method: 'POST',
                    headers: { 'X-Admin-Token': app.adminToken }
                });
                const data = await response.json();
                
                if (data.success) {
                    app.showToast(`ลบ ${data.deleted_count} Sessions สำเร็จ`, 'success');
                    await this.loadSessions();
                }
            } catch (error) {
                console.error('Error cleaning up sessions:', error);
                app.showToast('ไม่สามารถทำความสะอาดได้', 'error');
            }
        },
        
        async exportDatabase() {
            try {
                const response = await fetch('/admin/api/database/export', {
                    headers: { 'X-Admin-Token': app.adminToken }
                });
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `sessions_${new Date().toISOString().split('T')[0]}.db`;
                a.click();
                app.showToast('Export สำเร็จ', 'success');
            } catch (error) {
                console.error('Error exporting database:', error);
                app.showToast('ไม่สามารถ Export ได้', 'error');
            }
        },
        
        getFilteredSessions() {
            let filtered = [...this.sessions];
            
            if (this.filters.search) {
                const search = this.filters.search.toLowerCase();
                filtered = filtered.filter(s => 
                    s.session_id.toLowerCase().includes(search) ||
                    s.user_name?.toLowerCase().includes(search)
                );
            }
            
            if (this.filters.platform !== 'all') {
                filtered = filtered.filter(s => s.platform === this.filters.platform);
            }
            
            if (this.filters.botEnabled !== 'all') {
                const enabled = this.filters.botEnabled === 'enabled';
                filtered = filtered.filter(s => s.bot_enabled === enabled);
            }
            
            filtered.sort((a, b) => {
                const aVal = a[this.filters.sortBy];
                const bVal = b[this.filters.sortBy];
                const order = this.filters.sortOrder === 'asc' ? 1 : -1;
                return aVal > bVal ? order : -order;
            });
            
            return filtered;
        },
        
        renderSessionsList() {
            const container = document.getElementById('sessions-list');
            if (!container) return;
            
            const filtered = this.getFilteredSessions();
            
            container.innerHTML = filtered.map(session => `
                <div class="card-enterprise p-4 hover:shadow-lg transition-all cursor-pointer border-2 ${this.selectedSession?.session_id === session.session_id ? 'border-purple-500' : 'border-transparent'}"
                     onclick="app.database.loadMessages('${session.session_id}')">
                    <div class="flex items-start justify-between mb-3">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white font-bold">
                                ${session.user_name ? session.user_name[0].toUpperCase() : '?'}
                            </div>
                            <div>
                                <div class="font-semibold">${session.user_name || 'Unknown User'}</div>
                                <div class="text-xs text-gray-500">${session.session_id.substring(0, 12)}...</div>
                            </div>
                        </div>
                        <div class="flex gap-2">
                            <span class="px-2 py-1 text-xs rounded-full ${session.platform === 'line' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'}">
                                ${session.platform.toUpperCase()}
                            </span>
                            <span class="px-2 py-1 text-xs rounded-full ${session.bot_enabled ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-700'}">
                                ${session.bot_enabled ? 'Bot ON' : 'Bot OFF'}
                            </span>
                        </div>
                    </div>
                    <div class="flex justify-between text-xs text-gray-500">
                        <span>สร้าง: ${new Date(session.created_at).toLocaleDateString('th-TH')}</span>
                        <span>ใช้ล่าสุด: ${new Date(session.last_active).toLocaleString('th-TH')}</span>
                    </div>
                </div>
            `).join('');
        },
        
        renderMessages() {
            const container = document.getElementById('messages-list');
            if (!container) return;
            
            container.innerHTML = this.messages.map(msg => `
                <div class="card-enterprise p-4 mb-3" id="msg-${msg.id}">
                    <div class="flex items-start justify-between mb-2">
                        <div class="flex items-center gap-2">
                            <span class="px-2 py-1 text-xs font-semibold rounded ${msg.role === 'user' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'}">
                                ${msg.role.toUpperCase()}
                            </span>
                            <span class="text-xs text-gray-500">${new Date(msg.timestamp).toLocaleString('th-TH')}</span>
                        </div>
                        <div class="flex gap-2">
                            <button onclick="app.database.startEditMessage(${msg.id})" class="p-1 hover:bg-gray-100 rounded">
                                <i data-lucide="edit" class="w-4 h-4"></i>
                            </button>
                            <button onclick="app.database.deleteMessage(${msg.id})" class="p-1 hover:bg-red-100 text-red-600 rounded">
                                <i data-lucide="trash-2" class="w-4 h-4"></i>
                            </button>
                        </div>
                    </div>
                    <div id="content-${msg.id}" class="prose prose-sm max-w-none">
                        ${msg.content.replace(/\n/g, '<br>')}
                    </div>
                </div>
            `).join('');
            
            lucide.createIcons();
        },
        
        startEditMessage(messageId) {
            const message = this.messages.find(m => m.id === messageId);
            if (!message) return;
            
            const contentDiv = document.getElementById(`content-${messageId}`);
            contentDiv.innerHTML = `
                <textarea class="w-full p-2 border rounded" rows="4">${message.content}</textarea>
                <div class="flex gap-2 mt-2">
                    <button onclick="app.database.saveEditMessage(${messageId})" class="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700">
                        บันทึก
                    </button>
                    <button onclick="app.database.cancelEdit()" class="px-4 py-2 bg-gray-200 rounded hover:bg-gray-300">
                        ยกเลิก
                    </button>
                </div>
            `;
            contentDiv.querySelector('textarea').focus();
        },
        
        saveEditMessage(messageId) {
            const textarea = document.querySelector(`#content-${messageId} textarea`);
            if (textarea) {
                this.updateMessage(messageId, textarea.value);
            }
        },
        
        cancelEdit() {
            this.renderMessages();
        },
        
        render() {
            const container = document.getElementById('database-container');
            if (!container) return;
            
            container.innerHTML = `
                <div class="h-full flex flex-col">
                    <div class="flex items-center justify-between mb-6">
                        <div>
                            <h1 class="text-3xl font-black gradient-text-cmu">Database Management</h1>
                            <p class="text-sm text-gray-500 mt-1">จัดการ Sessions และ Messages</p>
                        </div>
                        <div class="flex gap-2">
                            <button onclick="app.database.exportDatabase()" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2">
                                <i data-lucide="download" class="w-4 h-4"></i>
                                Export DB
                            </button>
                            <button onclick="app.database.cleanupOldSessions(7)" class="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 flex items-center gap-2">
                                <i data-lucide="trash-2" class="w-4 h-4"></i>
                                Cleanup
                            </button>
                        </div>
                    </div>

                    <!-- Stats -->
                    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                        <div class="card-enterprise p-4">
                            <div class="text-2xl font-bold text-purple-600">${this.stats.totalSessions}</div>
                            <div class="text-sm text-gray-500">Total Sessions</div>
                        </div>
                        <div class="card-enterprise p-4">
                            <div class="text-2xl font-bold text-blue-600">${this.stats.totalMessages}</div>
                            <div class="text-sm text-gray-500">Total Messages</div>
                        </div>
                        <div class="card-enterprise p-4">
                            <div class="text-2xl font-bold text-green-600">${this.stats.activeSessions}</div>
                            <div class="text-sm text-gray-500">Active Today</div>
                        </div>
                        <div class="card-enterprise p-4">
                            <div class="text-sm text-gray-500 mb-2">Platforms</div>
                            <div class="flex gap-2">
                                ${Object.entries(this.stats.platforms || {}).map(([platform, count]) => 
                                    `<span class="px-2 py-1 text-xs rounded-full bg-gray-100">${platform}: ${count}</span>`
                                ).join('')}
                            </div>
                        </div>
                    </div>

                    <!-- Filters -->
                    <div class="card-enterprise p-4 mb-4">
                        <div class="grid grid-cols-1 md:grid-cols-5 gap-3">
                            <input type="text" placeholder="ค้นหา Session..." 
                                   class="px-3 py-2 border rounded-lg"
                                   oninput="app.database.filters.search = this.value; app.database.renderSessionsList()">
                            <select class="px-3 py-2 border rounded-lg" onchange="app.database.filters.platform = this.value; app.database.renderSessionsList()">
                                <option value="all">ทุก Platform</option>
                                <option value="line">LINE</option>
                                <option value="messenger">Messenger</option>
                            </select>
                            <select class="px-3 py-2 border rounded-lg" onchange="app.database.filters.botEnabled = this.value; app.database.renderSessionsList()">
                                <option value="all">ทุกสถานะ Bot</option>
                                <option value="enabled">Bot เปิด</option>
                                <option value="disabled">Bot ปิด</option>
                            </select>
                            <select class="px-3 py-2 border rounded-lg" onchange="app.database.filters.sortBy = this.value; app.database.renderSessionsList()">
                                <option value="last_active">เรียงตาม: ใช้ล่าสุด</option>
                                <option value="created_at">เรียงตาม: สร้าง</option>
                                <option value="user_name">เรียงตาม: ชื่อ</option>
                            </select>
                            <select class="px-3 py-2 border rounded-lg" onchange="app.database.filters.sortOrder = this.value; app.database.renderSessionsList()">
                                <option value="desc">มาก → น้อย</option>
                                <option value="asc">น้อย → มาก</option>
                            </select>
                        </div>
                    </div>

                    <!-- Main Content -->
                    <div class="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-4 overflow-hidden">
                        <!-- Sessions List -->
                        <div class="flex flex-col">
                            <h2 class="text-xl font-bold mb-3">Sessions (${this.getFilteredSessions().length})</h2>
                            <div id="sessions-list" class="flex-1 overflow-y-auto custom-scrollbar space-y-2 pr-2"></div>
                        </div>

                        <!-- Messages List -->
                        <div class="flex flex-col">
                            ${this.selectedSession ? `
                                <div class="mb-3">
                                    <div class="flex items-center justify-between">
                                        <h2 class="text-xl font-bold">Messages</h2>
                                        <div class="flex gap-2">
                                            <button onclick="app.database.updateSession('${this.selectedSession.session_id}', {bot_enabled: ${!this.selectedSession.bot_enabled}})" 
                                                    class="px-3 py-1 text-sm rounded ${this.selectedSession.bot_enabled ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}">
                                                ${this.selectedSession.bot_enabled ? 'ปิด Bot' : 'เปิด Bot'}
                                            </button>
                                            <button onclick="app.database.deleteSession('${this.selectedSession.session_id}')" class="px-3 py-1 text-sm bg-red-600 text-white rounded">
                                                ลบ Session
                                            </button>
                                        </div>
                                    </div>
                                    <div class="text-sm text-gray-500 mt-1">${this.selectedSession.user_name} • ${this.messages.length} ข้อความ</div>
                                </div>
                                <div id="messages-list" class="flex-1 overflow-y-auto custom-scrollbar pr-2"></div>
                            ` : `
                                <div class="flex-1 flex items-center justify-center text-gray-400">
                                    <div class="text-center">
                                        <i data-lucide="database" class="w-16 h-16 mx-auto mb-3 opacity-50"></i>
                                        <p>เลือก Session เพื่อดูข้อความ</p>
                                    </div>
                                </div>
                            `}
                        </div>
                    </div>
                </div>
            `;
            
            lucide.createIcons();
            this.renderSessionsList();
            if (this.selectedSession) {
                this.renderMessages();
            }
        }
    };
    
    // Load when database tab is active
    const originalSwitchTab = app.switchTab;
    app.switchTab = function(tab) {
        originalSwitchTab.call(this, tab);
        if (tab === 'database') {
            app.database.render();
            app.database.loadSessions();
        }
    };
}

// Auto-initialize if Alpine is already loaded
if (typeof window !== 'undefined') {
    document.addEventListener('alpine:initialized', () => {
        console.log('🔵 Alpine initialized, checking for app...');
        // Try to get app instance
        const appElement = document.querySelector('[x-data]');
        if (appElement && appElement.__x && appElement.__x.$data) {
            const app = appElement.__x.$data;
            if (!app.database) {
                console.log('🟢 Auto-initializing database module');
                initDatabaseModule(app);
            }
        }
    });
}