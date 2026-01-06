/**
 * Professional Database Manager
 * เน้นความเรียบง่าย ประสิทธิภาพสูง และดูข้อมูลได้อย่างอิสระ
 */

function initDatabaseModule(app) {
    app.database = {
        // Data
        sessions: [],
        selectedSession: null,
        messages: [],
        stats: { totalSessions: 0, totalMessages: 0, activeSessions: 0, platforms: {} },
        
        // Filters
        filters: { search: '', platform: 'all', botEnabled: 'all', sortBy: 'last_active', sortOrder: 'desc' },
        
        // Pagination
        currentPage: 1,
        itemsPerPage: 15,
        
        // UI State
        loading: false,
        viewMode: 'split', // split, full-messages
        
        /**
         * Load Sessions
         */
        async loadSessions() {
            this.loading = true;
            try {
                const res = await fetch('/admin/api/database/sessions', {
                    headers: { 'X-Admin-Token': app.adminToken }
                });
                const data = await res.json();
                
                if (data.success) {
                    this.sessions = data.sessions || [];
                    this.stats = data.stats || this.stats;
                    this.render();
                }
            } catch (e) {
                console.error('Load failed:', e);
                app.showToast('โหลดข้อมูลล้มเหลว', 'error');
            } finally {
                this.loading = false;
            }
        },
        
        /**
         * Load Messages
         */
        async loadMessages(sessionId) {
            if (!sessionId) return;
            
            try {
                const res = await fetch(`/admin/api/database/sessions/${sessionId}/messages`, {
                    headers: { 'X-Admin-Token': app.adminToken }
                });
                const data = await res.json();
                
                if (data.success) {
                    this.messages = data.messages || [];
                    this.selectedSession = this.sessions.find(s => s.session_id === sessionId);
                    this.render();
                    setTimeout(() => {
                        const el = document.getElementById('messages-list');
                        if (el) el.scrollTop = el.scrollHeight;
                    }, 100);
                }
            } catch (e) {
                console.error('Load messages failed:', e);
                app.showToast('โหลดข้อความล้มเหลว', 'error');
            }
        },
        
        /**
         * Update Session
         */
        async updateSession(sessionId, updates) {
            try {
                const res = await fetch(`/admin/api/database/sessions/${sessionId}`, {
                    method: 'PATCH',
                    headers: { 'X-Admin-Token': app.adminToken, 'Content-Type': 'application/json' },
                    body: JSON.stringify(updates)
                });
                
                if (res.ok) {
                    app.showToast('อัพเดทสำเร็จ', 'success');
                    await this.loadSessions();
                    if (this.selectedSession?.session_id === sessionId) {
                        await this.loadMessages(sessionId);
                    }
                }
            } catch (e) {
                app.showToast('อัพเดทล้มเหลว', 'error');
            }
        },
        
        /**
         * Delete Session
         */
        async deleteSession(sessionId) {
            if (!confirm('ลบ Session? ข้อความจะถูกลบด้วย')) return;
            
            try {
                const res = await fetch(`/admin/api/database/sessions/${sessionId}`, {
                    method: 'DELETE',
                    headers: { 'X-Admin-Token': app.adminToken }
                });
                
                if (res.ok) {
                    app.showToast('ลบสำเร็จ', 'success');
                    if (this.selectedSession?.session_id === sessionId) {
                        this.selectedSession = null;
                        this.messages = [];
                    }
                    await this.loadSessions();
                }
            } catch (e) {
                app.showToast('ลบล้มเหลว', 'error');
            }
        },
        
        /**
         * Update Message
         */
        async updateMessage(msgId, content) {
            try {
                const res = await fetch(`/admin/api/database/messages/${msgId}`, {
                    method: 'PATCH',
                    headers: { 'X-Admin-Token': app.adminToken, 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content })
                });
                
                if (res.ok) {
                    app.showToast('แก้ไขสำเร็จ', 'success');
                    await this.loadMessages(this.selectedSession.session_id);
                }
            } catch (e) {
                app.showToast('แก้ไขล้มเหลว', 'error');
            }
        },
        
        /**
         * Delete Message
         */
        async deleteMessage(msgId) {
            if (!confirm('ลบข้อความ?')) return;
            
            try {
                const res = await fetch(`/admin/api/database/messages/${msgId}`, {
                    method: 'DELETE',
                    headers: { 'X-Admin-Token': app.adminToken }
                });
                
                if (res.ok) {
                    app.showToast('ลบสำเร็จ', 'success');
                    await this.loadMessages(this.selectedSession.session_id);
                }
            } catch (e) {
                app.showToast('ลบล้มเหลว', 'error');
            }
        },
        
        /**
         * Cleanup Old Sessions
         */
        async cleanup(days = 7) {
            if (!confirm(`ลบ Session ไม่ใช้งาน ${days} วัน?`)) return;
            
            try {
                const res = await fetch(`/admin/api/database/cleanup?days=${days}`, {
                    method: 'POST',
                    headers: { 'X-Admin-Token': app.adminToken }
                });
                const data = await res.json();
                
                if (data.success) {
                    app.showToast(`ลบ ${data.deleted_count} Sessions`, 'success');
                    await this.loadSessions();
                }
            } catch (e) {
                app.showToast('Cleanup ล้มเหลว', 'error');
            }
        },
        
        /**
         * Export Database
         */
        async export() {
            try {
                const res = await fetch('/admin/api/database/export', {
                    headers: { 'X-Admin-Token': app.adminToken }
                });
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `db_${new Date().toISOString().split('T')[0]}.db`;
                a.click();
                URL.revokeObjectURL(url);
                app.showToast('Export สำเร็จ', 'success');
            } catch (e) {
                app.showToast('Export ล้มเหลว', 'error');
            }
        },
        
        /**
         * Filter Sessions
         */
        getFiltered() {
            let list = [...this.sessions];
            
            if (this.filters.search) {
                const q = this.filters.search.toLowerCase();
                list = list.filter(s => 
                    (s.session_id || '').toLowerCase().includes(q) ||
                    (s.user_name || '').toLowerCase().includes(q)
                );
            }
            
            if (this.filters.platform !== 'all') {
                list = list.filter(s => s.platform === this.filters.platform);
            }
            
            if (this.filters.botEnabled !== 'all') {
                const enabled = this.filters.botEnabled === 'enabled';
                list = list.filter(s => Boolean(s.bot_enabled) === enabled);
            }
            
            list.sort((a, b) => {
                let aVal = a[this.filters.sortBy];
                let bVal = b[this.filters.sortBy];
                
                if (['last_active', 'created_at'].includes(this.filters.sortBy)) {
                    aVal = new Date(aVal);
                    bVal = new Date(bVal);
                }
                
                return this.filters.sortOrder === 'desc' ? (aVal > bVal ? -1 : 1) : (aVal > bVal ? 1 : -1);
            });
            
            return list;
        },
        
        /**
         * Paginate
         */
        getPaginated() {
            const filtered = this.getFiltered();
            const start = (this.currentPage - 1) * this.itemsPerPage;
            return filtered.slice(start, start + this.itemsPerPage);
        },
        
        goToPage(page) {
            const totalPages = Math.ceil(this.getFiltered().length / this.itemsPerPage);
            if (page >= 1 && page <= totalPages) {
                this.currentPage = page;
                this.render();
            }
        },
        
        /**
         * Edit Message UI
         */
        editMsg(msgId) {
            const msg = this.messages.find(m => m.id === msgId);
            if (!msg) return;
            
            const el = document.getElementById(`msg-${msgId}`);
            if (!el) return;
            
            el.innerHTML = `
                <textarea id="edit-${msgId}" class="w-full p-3 border rounded" rows="4">${this.esc(msg.content)}</textarea>
                <div class="flex gap-2 mt-2">
                    <button onclick="app.database.saveMsg(${msgId})" class="px-3 py-1 bg-purple-600 text-white rounded font-bold">บันทึก</button>
                    <button onclick="app.database.loadMessages('${this.selectedSession.session_id}')" class="px-3 py-1 bg-gray-200 rounded font-bold">ยกเลิก</button>
                </div>
            `;
            document.getElementById(`edit-${msgId}`).focus();
        },
        
        saveMsg(msgId) {
            const textarea = document.getElementById(`edit-${msgId}`);
            if (!textarea) return;
            const content = textarea.value.trim();
            if (content) this.updateMessage(msgId, content);
        },
        
        /**
         * Toggle View
         */
        toggleView() {
            this.viewMode = this.viewMode === 'split' ? 'full-messages' : 'split';
            this.render();
        },
        
        /**
         * Format
         */
        fmt(d) {
            return d ? new Date(d).toLocaleDateString('th-TH', { day: '2-digit', month: 'short', year: 'numeric' }) : 'N/A';
        },
        
        fmtTime(d) {
            return d ? new Date(d).toLocaleString('th-TH', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : 'N/A';
        },
        
        esc(txt) {
            const div = document.createElement('div');
            div.textContent = txt;
            return div.innerHTML;
        },
        
        /**
         * Main Render
         */
        render() {
            const container = document.getElementById('database-container');
            if (!container) return;
            
            const filtered = this.getFiltered();
            const paginated = this.getPaginated();
            const totalPages = Math.ceil(filtered.length / this.itemsPerPage);
            
            container.innerHTML = `
                <div class="h-full flex flex-col">
                    <!-- Header -->
                    <div class="flex justify-between items-center mb-4">
                        <div>
                            <h1 class="text-3xl font-black gradient-text-cmu">Database</h1>
                            <p class="text-sm text-gray-500">จัดการ Sessions & Messages</p>
                        </div>
                        <div class="flex gap-2">
                            <button onclick="app.database.loadSessions()" class="btn-icon" title="รีเฟรช">
                                <i data-lucide="refresh-cw" class="w-4 h-4"></i>
                            </button>
                            <button onclick="app.database.export()" class="btn-icon" title="Export">
                                <i data-lucide="download" class="w-4 h-4"></i>
                            </button>
                            <button onclick="app.database.cleanup(7)" class="btn-icon" title="Cleanup">
                                <i data-lucide="trash-2" class="w-4 h-4"></i>
                            </button>
                        </div>
                    </div>

                    <!-- Stats -->
                    <div class="grid grid-cols-4 gap-3 mb-4">
                        ${this.renderStat('Sessions', this.stats.totalSessions, 'users', 'purple')}
                        ${this.renderStat('Messages', this.stats.totalMessages, 'message-square', 'blue')}
                        ${this.renderStat('Active', this.stats.activeSessions, 'activity', 'green')}
                        <div class="card-enterprise p-3 rounded-lg">
                            <div class="text-xs font-bold text-gray-500 mb-1">Platforms</div>
                            <div class="flex gap-1 flex-wrap">
                                ${Object.entries(this.stats.platforms || {}).map(([p, c]) => 
                                    `<span class="text-xs px-2 py-0.5 bg-gray-100 rounded font-bold">${p}:${c}</span>`
                                ).join('')}
                            </div>
                        </div>
                    </div>

                    <!-- Filters -->
                    <div class="card-enterprise p-3 rounded-lg mb-4">
                        <div class="grid grid-cols-5 gap-2">
                            <input type="text" placeholder="🔍 ค้นหา" class="input-sm" 
                                   oninput="app.database.filters.search = this.value; app.database.currentPage = 1; app.database.render()">
                            <select class="input-sm" onchange="app.database.filters.platform = this.value; app.database.currentPage = 1; app.database.render()">
                                <option value="all">Platform: ทั้งหมด</option>
                                <option value="line">LINE</option>
                                <option value="facebook">Facebook</option>
                                <option value="web">Web</option>
                            </select>
                            <select class="input-sm" onchange="app.database.filters.botEnabled = this.value; app.database.currentPage = 1; app.database.render()">
                                <option value="all">Bot: ทั้งหมด</option>
                                <option value="enabled">เปิด</option>
                                <option value="disabled">ปิด</option>
                            </select>
                            <select class="input-sm" onchange="app.database.filters.sortBy = this.value; app.database.render()">
                                <option value="last_active">เรียง: ใช้ล่าสุด</option>
                                <option value="created_at">เรียง: สร้าง</option>
                                <option value="user_name">เรียง: ชื่อ</option>
                            </select>
                            <select class="input-sm" onchange="app.database.filters.sortOrder = this.value; app.database.render()">
                                <option value="desc">↓ ใหม่→เก่า</option>
                                <option value="asc">↑ เก่า→ใหม่</option>
                            </select>
                        </div>
                    </div>

                    ${this.viewMode === 'full-messages' && this.selectedSession ? 
                        this.renderFullMessages() : 
                        this.renderSplit(paginated, filtered, totalPages)
                    }
                </div>

                <style>
                    .btn-icon { padding: 0.5rem; border-radius: 0.5rem; background: white; border: 1px solid #e5e7eb; font-weight: 600; transition: all 0.2s; }
                    .btn-icon:hover { background: #f3f4f6; }
                    .input-sm { padding: 0.5rem; border: 1px solid #e5e7eb; border-radius: 0.5rem; font-size: 0.875rem; font-weight: 600; }
                    .input-sm:focus { outline: none; border-color: #8b5cf6; }
                </style>
            `;
            
            lucide.createIcons();
        },
        
        renderStat(label, value, icon, color) {
            const colors = {
                purple: '#8b5cf6',
                blue: '#3b82f6',
                green: '#10b981'
            };
            return `
                <div class="card-enterprise p-3 rounded-lg">
                    <div class="text-xs font-bold text-gray-500 mb-1">${label}</div>
                    <div class="text-2xl font-black" style="color: ${colors[color]}">${value}</div>
                </div>
            `;
        },
        
        renderSplit(paginated, filtered, totalPages) {
            return `
                <div class="flex-1 grid grid-cols-2 gap-4 overflow-hidden">
                    <!-- Sessions -->
                    <div class="flex flex-col">
                        <div class="flex justify-between mb-2">
                            <h3 class="font-bold">Sessions (${filtered.length})</h3>
                        </div>
                        <div class="flex-1 overflow-y-auto custom-scrollbar space-y-2">
                            ${paginated.map(s => `
                                <div class="card-enterprise p-3 cursor-pointer hover:shadow transition ${this.selectedSession?.session_id === s.session_id ? 'ring-2 ring-purple-500' : ''}"
                                     onclick="app.database.loadMessages('${s.session_id}')">
                                    <div class="flex justify-between mb-2">
                                        <div class="flex gap-2 items-center">
                                            <div class="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white text-sm font-bold">
                                                ${(s.user_name || '?')[0].toUpperCase()}
                                            </div>
                                            <div>
                                                <div class="font-bold text-sm">${s.user_name || 'Unknown'}</div>
                                                <div class="text-xs text-gray-500">${s.session_id.substring(0, 10)}...</div>
                                            </div>
                                        </div>
                                        <div class="flex gap-1">
                                            <span class="text-xs px-2 py-0.5 rounded ${s.platform === 'line' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'}">${s.platform.toUpperCase()}</span>
                                            <span class="text-xs px-2 py-0.5 rounded ${s.bot_enabled ? 'bg-purple-100 text-purple-700' : 'bg-gray-100'}">${s.bot_enabled ? 'ON' : 'OFF'}</span>
                                        </div>
                                    </div>
                                    <div class="text-xs text-gray-500 flex justify-between">
                                        <span>${this.fmt(s.created_at)}</span>
                                        <span>${this.fmt(s.last_active)}</span>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                        ${totalPages > 1 ? `
                            <div class="mt-2 pt-2 border-t flex justify-between text-sm">
                                <span class="text-gray-500">หน้า ${this.currentPage}/${totalPages}</span>
                                <div class="flex gap-1">
                                    <button onclick="app.database.goToPage(${this.currentPage - 1})" ${this.currentPage === 1 ? 'disabled' : ''} class="px-2 py-1 border rounded font-bold disabled:opacity-50">←</button>
                                    <button onclick="app.database.goToPage(${this.currentPage + 1})" ${this.currentPage === totalPages ? 'disabled' : ''} class="px-2 py-1 border rounded font-bold disabled:opacity-50">→</button>
                                </div>
                            </div>
                        ` : ''}
                    </div>

                    <!-- Messages -->
                    <div class="flex flex-col">
                        ${this.selectedSession ? `
                            <div class="flex justify-between mb-2">
                                <div>
                                    <h3 class="font-bold">${this.selectedSession.user_name}</h3>
                                    <p class="text-xs text-gray-500">${this.messages.length} ข้อความ</p>
                                </div>
                                <div class="flex gap-1">
                                    <button onclick="app.database.toggleView()" class="btn-icon" title="ขยาย">
                                        <i data-lucide="maximize-2" class="w-3 h-3"></i>
                                    </button>
                                    <button onclick="app.database.updateSession('${this.selectedSession.session_id}', {bot_enabled: ${!this.selectedSession.bot_enabled}})" 
                                            class="px-2 py-1 text-xs ${this.selectedSession.bot_enabled ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'} rounded font-bold">
                                        ${this.selectedSession.bot_enabled ? 'ปิดBot' : 'เปิดBot'}
                                    </button>
                                    <button onclick="app.database.deleteSession('${this.selectedSession.session_id}')" 
                                            class="px-2 py-1 text-xs bg-red-600 text-white rounded font-bold">ลบ</button>
                                </div>
                            </div>
                            <div id="messages-list" class="flex-1 overflow-y-auto custom-scrollbar space-y-2">
                                ${this.messages.map(m => `
                                    <div class="card-enterprise p-2">
                                        <div class="flex justify-between mb-1">
                                            <span class="text-xs px-2 py-0.5 rounded ${m.role === 'user' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'} font-bold">
                                                ${m.role === 'user' ? 'USER' : 'BOT'}
                                            </span>
                                            <div class="flex gap-2 items-center">
                                                <span class="text-xs text-gray-500">${this.fmtTime(m.created_at)}</span>
                                                <button onclick="app.database.editMsg(${m.id})" class="text-gray-400 hover:text-purple-600">
                                                    <i data-lucide="edit" class="w-3 h-3"></i>
                                                </button>
                                                <button onclick="app.database.deleteMessage(${m.id})" class="text-gray-400 hover:text-red-600">
                                                    <i data-lucide="trash-2" class="w-3 h-3"></i>
                                                </button>
                                            </div>
                                        </div>
                                        <div id="msg-${m.id}" class="text-sm">${this.esc(m.content).replace(/\n/g, '<br>')}</div>
                                    </div>
                                `).join('')}
                            </div>
                        ` : `
                            <div class="flex-1 flex items-center justify-center text-gray-400">
                                <div class="text-center">
                                    <i data-lucide="message-square" class="w-12 h-12 mx-auto mb-2 opacity-50"></i>
                                    <p class="text-sm">เลือก Session</p>
                                </div>
                            </div>
                        `}
                    </div>
                </div>
            `;
        },
        
        renderFullMessages() {
            return `
                <div class="flex-1 flex flex-col">
                    <div class="flex justify-between pb-3 mb-3 border-b">
                        <div class="flex gap-2 items-center">
                            <button onclick="app.database.toggleView()" class="btn-icon">
                                <i data-lucide="minimize-2" class="w-4 h-4"></i>
                            </button>
                            <div>
                                <h3 class="font-bold text-lg">${this.selectedSession.user_name}</h3>
                                <p class="text-xs text-gray-500">${this.selectedSession.platform.toUpperCase()} • ${this.messages.length} ข้อความ</p>
                            </div>
                        </div>
                        <div class="flex gap-2">
                            <button onclick="app.database.updateSession('${this.selectedSession.session_id}', {bot_enabled: ${!this.selectedSession.bot_enabled}})" 
                                    class="px-3 py-2 ${this.selectedSession.bot_enabled ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'} rounded font-bold text-sm">
                                ${this.selectedSession.bot_enabled ? '⛔ ปิด Bot' : '🤖 เปิด Bot'}
                            </button>
                            <button onclick="app.database.deleteSession('${this.selectedSession.session_id}')" 
                                    class="px-3 py-2 bg-red-600 text-white rounded font-bold text-sm">🗑️ ลบ</button>
                        </div>
                    </div>
                    <div id="messages-list" class="flex-1 overflow-y-auto custom-scrollbar space-y-3">
                        ${this.messages.map(m => `
                            <div class="card-enterprise p-4">
                                <div class="flex justify-between mb-2">
                                    <div class="flex gap-2 items-center">
                                        <span class="text-xs px-3 py-1 rounded-full ${m.role === 'user' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'} font-bold">
                                            ${m.role === 'user' ? '👤 USER' : '🤖 BOT'}
                                        </span>
                                        <span class="text-sm text-gray-500">${this.fmtTime(m.created_at)}</span>
                                    </div>
                                    <div class="flex gap-2">
                                        <button onclick="app.database.editMsg(${m.id})" class="p-1 hover:bg-gray-100 rounded">
                                            <i data-lucide="edit" class="w-4 h-4"></i>
                                        </button>
                                        <button onclick="app.database.deleteMessage(${m.id})" class="p-1 hover:bg-red-100 text-red-600 rounded">
                                            <i data-lucide="trash-2" class="w-4 h-4"></i>
                                        </button>
                                    </div>
                                </div>
                                <div id="msg-${m.id}" class="leading-relaxed">${this.esc(m.content).replace(/\n/g, '<br>')}</div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }
    };
    
    // Auto-load
    const origSwitch = app.switchTab.bind(app);
    app.switchTab = function(tab) {
        origSwitch(tab);
        if (tab === 'database') {
            app.database.render();
            app.database.loadSessions();
        }
    };
}

// Auto-init
if (typeof window !== 'undefined') {
    document.addEventListener('alpine:initialized', () => {
        const el = document.querySelector('[x-data]');
        if (el?.__x?.$data && !el.__x.$data.database) {
            initDatabaseModule(el.__x.$data);
        }
    });
}