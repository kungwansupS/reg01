/**
 * Database Management Module - Production Ready
 * ระบบจัดการ Database แบบครบวงจร
 */

function initDatabaseModule(app) {
    // Initialize contextMenu if not exists
    if (!app.contextMenu) {
        app.contextMenu = {
            show: false,
            x: 0,
            y: 0,
            entry: null
        };
    }
    
    app.database = {
        // State Management
        sessions: [],
        selectedSession: null,
        messages: [],
        stats: {
            totalSessions: 0,
            totalMessages: 0,
            activeSessions: 0,
            platforms: {}
        },
        
        // Filters
        filters: {
            search: '',
            platform: 'all',
            botEnabled: 'all',
            sortBy: 'last_active',
            sortOrder: 'desc',
            dateFrom: '',
            dateTo: ''
        },
        
        // Pagination
        pagination: {
            currentPage: 1,
            itemsPerPage: 20,
            totalPages: 0
        },
        
        // UI State
        loading: false,
        error: null,
        editMode: false,
        editingMessage: null,
        bulkSelection: new Set(),
        
        /**
         * Load Sessions from API
         */
        async loadSessions() {
            this.loading = true;
            this.error = null;
            
            try {
                const response = await fetch('/admin/api/database/sessions', {
                    headers: { 'X-Admin-Token': app.adminToken }
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const data = await response.json();
                
                if (data.success) {
                    this.sessions = data.sessions || [];
                    this.stats = data.stats || this.stats;
                    this.renderSessionsList();
                    console.log(`✅ Loaded ${this.sessions.length} sessions`);
                } else {
                    throw new Error(data.message || 'Failed to load sessions');
                }
            } catch (error) {
                console.error('❌ Error loading sessions:', error);
                this.error = 'ไม่สามารถโหลดข้อมูล Session ได้: ' + error.message;
                app.showToast('ไม่สามารถโหลดข้อมูล Session', 'error');
            } finally {
                this.loading = false;
            }
        },
        
        /**
         * Load Messages for Specific Session
         */
        async loadMessages(sessionId) {
            if (!sessionId) {
                console.error('❌ Invalid session ID');
                return;
            }
            
            this.loading = true;
            this.error = null;
            
            try {
                const response = await fetch(`/admin/api/database/sessions/${sessionId}/messages`, {
                    headers: { 'X-Admin-Token': app.adminToken }
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const data = await response.json();
                
                if (data.success) {
                    this.messages = data.messages || [];
                    this.selectedSession = this.sessions.find(s => s.session_id === sessionId);
                    this.renderMessages();
                    console.log(`✅ Loaded ${this.messages.length} messages for session ${sessionId}`);
                } else {
                    throw new Error(data.message || 'Failed to load messages');
                }
            } catch (error) {
                console.error('❌ Error loading messages:', error);
                this.error = 'ไม่สามารถโหลดข้อความได้: ' + error.message;
                app.showToast('ไม่สามารถโหลดข้อความ', 'error');
            } finally {
                this.loading = false;
            }
        },
        
        /**
         * Update Session Information
         */
        async updateSession(sessionId, updates) {
            if (!sessionId || !updates) {
                console.error('❌ Invalid parameters for updateSession');
                return;
            }
            
            try {
                const response = await fetch(`/admin/api/database/sessions/${sessionId}`, {
                    method: 'PATCH',
                    headers: {
                        'X-Admin-Token': app.adminToken,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(updates)
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const data = await response.json();
                
                if (data.success) {
                    app.showToast('อัพเดท Session สำเร็จ', 'success');
                    await this.loadSessions();
                    
                    // Reload messages if this is the selected session
                    if (this.selectedSession?.session_id === sessionId) {
                        await this.loadMessages(sessionId);
                    }
                } else {
                    throw new Error(data.message || 'Failed to update session');
                }
            } catch (error) {
                console.error('❌ Error updating session:', error);
                app.showToast('ไม่สามารถอัพเดท Session: ' + error.message, 'error');
            }
        },
        
        /**
         * Delete Session
         */
        async deleteSession(sessionId) {
            if (!sessionId) {
                console.error('❌ Invalid session ID');
                return;
            }
            
            if (!confirm('คุณแน่ใจหรือไม่ที่จะลบ Session นี้? ข้อความทั้งหมดจะถูกลบด้วย')) {
                return;
            }
            
            try {
                const response = await fetch(`/admin/api/database/sessions/${sessionId}`, {
                    method: 'DELETE',
                    headers: { 'X-Admin-Token': app.adminToken }
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const data = await response.json();
                
                if (data.success) {
                    app.showToast('ลบ Session สำเร็จ', 'success');
                    
                    // Clear selection if this was the selected session
                    if (this.selectedSession?.session_id === sessionId) {
                        this.selectedSession = null;
                        this.messages = [];
                    }
                    
                    await this.loadSessions();
                } else {
                    throw new Error(data.message || 'Failed to delete session');
                }
            } catch (error) {
                console.error('❌ Error deleting session:', error);
                app.showToast('ไม่สามารถลบ Session: ' + error.message, 'error');
            }
        },
        
        /**
         * Update Message Content
         */
        async updateMessage(messageId, content) {
            if (!messageId || !content) {
                console.error('❌ Invalid parameters for updateMessage');
                return;
            }
            
            try {
                const response = await fetch(`/admin/api/database/messages/${messageId}`, {
                    method: 'PATCH',
                    headers: {
                        'X-Admin-Token': app.adminToken,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ content })
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const data = await response.json();
                
                if (data.success) {
                    app.showToast('อัพเดทข้อความสำเร็จ', 'success');
                    await this.loadMessages(this.selectedSession.session_id);
                    this.editMode = false;
                    this.editingMessage = null;
                } else {
                    throw new Error(data.message || 'Failed to update message');
                }
            } catch (error) {
                console.error('❌ Error updating message:', error);
                app.showToast('ไม่สามารถอัพเดทข้อความ: ' + error.message, 'error');
            }
        },
        
        /**
         * Delete Message
         */
        async deleteMessage(messageId) {
            if (!messageId) {
                console.error('❌ Invalid message ID');
                return;
            }
            
            if (!confirm('คุณแน่ใจหรือไม่ที่จะลบข้อความนี้?')) {
                return;
            }
            
            try {
                const response = await fetch(`/admin/api/database/messages/${messageId}`, {
                    method: 'DELETE',
                    headers: { 'X-Admin-Token': app.adminToken }
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const data = await response.json();
                
                if (data.success) {
                    app.showToast('ลบข้อความสำเร็จ', 'success');
                    await this.loadMessages(this.selectedSession.session_id);
                } else {
                    throw new Error(data.message || 'Failed to delete message');
                }
            } catch (error) {
                console.error('❌ Error deleting message:', error);
                app.showToast('ไม่สามารถลบข้อความ: ' + error.message, 'error');
            }
        },
        
        /**
         * Bulk Delete Sessions
         */
        async bulkDeleteSessions() {
            if (this.bulkSelection.size === 0) {
                app.showToast('กรุณาเลือก Session ที่ต้องการลบ', 'warning');
                return;
            }
            
            if (!confirm(`คุณแน่ใจหรือไม่ที่จะลบ ${this.bulkSelection.size} Sessions?`)) {
                return;
            }
            
            let successCount = 0;
            let errorCount = 0;
            
            for (const sessionId of this.bulkSelection) {
                try {
                    const response = await fetch(`/admin/api/database/sessions/${sessionId}`, {
                        method: 'DELETE',
                        headers: { 'X-Admin-Token': app.adminToken }
                    });
                    
                    if (response.ok) {
                        successCount++;
                    } else {
                        errorCount++;
                    }
                } catch (error) {
                    errorCount++;
                    console.error(`❌ Error deleting session ${sessionId}:`, error);
                }
            }
            
            this.bulkSelection.clear();
            app.showToast(`ลบสำเร็จ ${successCount} Sessions${errorCount > 0 ? `, ล้มเหลว ${errorCount} Sessions` : ''}`, 'success');
            await this.loadSessions();
        },
        
        /**
         * Cleanup Old Sessions
         */
        async cleanupOldSessions(days) {
            if (!days || days < 1) {
                app.showToast('กรุณาระบุจำนวนวันที่ถูกต้อง', 'warning');
                return;
            }
            
            if (!confirm(`คุณแน่ใจหรือไม่ที่จะลบ Session ที่ไม่ได้ใช้งานมากกว่า ${days} วัน?`)) {
                return;
            }
            
            try {
                const response = await fetch(`/admin/api/database/cleanup?days=${days}`, {
                    method: 'POST',
                    headers: { 'X-Admin-Token': app.adminToken }
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const data = await response.json();
                
                if (data.success) {
                    app.showToast(`ลบ ${data.deleted_count} Sessions สำเร็จ`, 'success');
                    await this.loadSessions();
                } else {
                    throw new Error(data.message || 'Failed to cleanup sessions');
                }
            } catch (error) {
                console.error('❌ Error cleaning up sessions:', error);
                app.showToast('ไม่สามารถทำความสะอาดได้: ' + error.message, 'error');
            }
        },
        
        /**
         * Export Database
         */
        async exportDatabase() {
            try {
                const response = await fetch('/admin/api/database/export', {
                    headers: { 'X-Admin-Token': app.adminToken }
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                
                const timestamp = new Date().toISOString().split('T')[0];
                a.download = `sessions_backup_${timestamp}.db`;
                
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                
                app.showToast('Export สำเร็จ', 'success');
            } catch (error) {
                console.error('❌ Error exporting database:', error);
                app.showToast('ไม่สามารถ Export ได้: ' + error.message, 'error');
            }
        },
        
        /**
         * Get Filtered Sessions
         */
        getFilteredSessions() {
            let filtered = [...this.sessions];
            
            // Search filter
            if (this.filters.search) {
                const search = this.filters.search.toLowerCase();
                filtered = filtered.filter(s => 
                    s.session_id.toLowerCase().includes(search) ||
                    (s.user_name && s.user_name.toLowerCase().includes(search)) ||
                    (s.platform && s.platform.toLowerCase().includes(search))
                );
            }
            
            // Platform filter
            if (this.filters.platform !== 'all') {
                filtered = filtered.filter(s => s.platform === this.filters.platform);
            }
            
            // Bot status filter
            if (this.filters.botEnabled !== 'all') {
                const enabled = this.filters.botEnabled === 'enabled';
                filtered = filtered.filter(s => Boolean(s.bot_enabled) === enabled);
            }
            
            // Date range filter
            if (this.filters.dateFrom) {
                const fromDate = new Date(this.filters.dateFrom);
                filtered = filtered.filter(s => new Date(s.last_active) >= fromDate);
            }
            
            if (this.filters.dateTo) {
                const toDate = new Date(this.filters.dateTo);
                toDate.setHours(23, 59, 59, 999);
                filtered = filtered.filter(s => new Date(s.last_active) <= toDate);
            }
            
            // Sort
            filtered.sort((a, b) => {
                let aVal = a[this.filters.sortBy];
                let bVal = b[this.filters.sortBy];
                
                // Handle date fields
                if (this.filters.sortBy === 'last_active' || this.filters.sortBy === 'created_at') {
                    aVal = new Date(aVal);
                    bVal = new Date(bVal);
                }
                
                const order = this.filters.sortOrder === 'asc' ? 1 : -1;
                
                if (aVal < bVal) return -order;
                if (aVal > bVal) return order;
                return 0;
            });
            
            return filtered;
        },
        
        /**
         * Get Paginated Sessions
         */
        getPaginatedSessions() {
            const filtered = this.getFilteredSessions();
            this.pagination.totalPages = Math.ceil(filtered.length / this.pagination.itemsPerPage);
            
            const start = (this.pagination.currentPage - 1) * this.pagination.itemsPerPage;
            const end = start + this.pagination.itemsPerPage;
            
            return filtered.slice(start, end);
        },
        
        /**
         * Render Sessions List
         */
        renderSessionsList() {
            const container = document.getElementById('sessions-list');
            if (!container) {
                console.warn('⚠️ Sessions list container not found');
                return;
            }
            
            const sessions = this.getPaginatedSessions();
            
            if (sessions.length === 0) {
                container.innerHTML = `
                    <div class="text-center py-12">
                        <i data-lucide="database" class="w-16 h-16 mx-auto mb-4 opacity-50" style="color: var(--border-primary);"></i>
                        <p class="text-sm font-medium" style="color: var(--text-tertiary);">
                            ${this.filters.search || this.filters.platform !== 'all' ? 'ไม่พบ Session ที่ตรงกับเงื่อนไข' : 'ยังไม่มี Session'}
                        </p>
                    </div>
                `;
                lucide.createIcons();
                return;
            }
            
            container.innerHTML = sessions.map(session => {
                const isSelected = this.selectedSession?.session_id === session.session_id;
                const isChecked = this.bulkSelection.has(session.session_id);
                const platformColors = {
                    line: 'bg-green-100 text-green-700',
                    messenger: 'bg-blue-100 text-blue-700',
                    facebook: 'bg-blue-100 text-blue-700',
                    web: 'bg-purple-100 text-purple-700'
                };
                
                return `
                    <div class="card-enterprise p-4 hover:shadow-lg transition-all cursor-pointer border-2 ${isSelected ? 'border-purple-500' : 'border-transparent'}"
                         onclick="if (!event.target.closest('.bulk-checkbox')) app.database.loadMessages('${session.session_id}')">
                        <div class="flex items-start justify-between mb-3">
                            <div class="flex items-center gap-3">
                                <input type="checkbox" 
                                       class="bulk-checkbox w-4 h-4 rounded"
                                       ${isChecked ? 'checked' : ''}
                                       onclick="event.stopPropagation(); app.database.toggleBulkSelection('${session.session_id}')">
                                <div class="w-10 h-10 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white font-bold">
                                    ${(session.user_name || '?')[0].toUpperCase()}
                                </div>
                                <div>
                                    <div class="font-semibold" style="color: var(--text-primary);">${session.user_name || 'Unknown User'}</div>
                                    <div class="text-xs" style="color: var(--text-tertiary);">${session.session_id.substring(0, 12)}...</div>
                                </div>
                            </div>
                            <div class="flex gap-2">
                                <span class="px-2 py-1 text-xs rounded-full ${platformColors[session.platform] || 'bg-gray-100 text-gray-700'}">
                                    ${(session.platform || 'unknown').toUpperCase()}
                                </span>
                                <span class="px-2 py-1 text-xs rounded-full ${session.bot_enabled ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-700'}">
                                    ${session.bot_enabled ? 'Bot ON' : 'Bot OFF'}
                                </span>
                            </div>
                        </div>
                        <div class="flex justify-between text-xs" style="color: var(--text-tertiary);">
                            <span>สร้าง: ${this.formatDate(session.created_at)}</span>
                            <span>ใช้ล่าสุด: ${this.formatDateTime(session.last_active)}</span>
                        </div>
                    </div>
                `;
            }).join('');
            
            // Render pagination
            this.renderPagination();
            
            lucide.createIcons();
        },
        
        /**
         * Render Pagination
         */
        renderPagination() {
            const container = document.getElementById('sessions-pagination');
            if (!container) return;
            
            const { currentPage, totalPages, itemsPerPage } = this.pagination;
            const filtered = this.getFilteredSessions();
            
            if (totalPages <= 1) {
                container.innerHTML = '';
                return;
            }
            
            const start = (currentPage - 1) * itemsPerPage + 1;
            const end = Math.min(currentPage * itemsPerPage, filtered.length);
            
            container.innerHTML = `
                <div class="flex items-center justify-between">
                    <div class="text-sm" style="color: var(--text-secondary);">
                        แสดง ${start} - ${end} จาก ${filtered.length} รายการ
                    </div>
                    <div class="flex items-center gap-2">
                        <button 
                            onclick="app.database.goToPage(${currentPage - 1})"
                            ${currentPage === 1 ? 'disabled' : ''}
                            class="px-3 py-1 rounded-lg border-2 font-bold text-sm disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                            style="border-color: var(--border-primary);">
                            <i data-lucide="chevron-left" class="w-4 h-4"></i>
                        </button>
                        <span class="text-sm font-bold" style="color: var(--text-secondary);">
                            ${currentPage} / ${totalPages}
                        </span>
                        <button 
                            onclick="app.database.goToPage(${currentPage + 1})"
                            ${currentPage === totalPages ? 'disabled' : ''}
                            class="px-3 py-1 rounded-lg border-2 font-bold text-sm disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                            style="border-color: var(--border-primary);">
                            <i data-lucide="chevron-right" class="w-4 h-4"></i>
                        </button>
                    </div>
                </div>
            `;
            
            lucide.createIcons();
        },
        
        /**
         * Toggle Bulk Selection
         */
        toggleBulkSelection(sessionId) {
            if (this.bulkSelection.has(sessionId)) {
                this.bulkSelection.delete(sessionId);
            } else {
                this.bulkSelection.add(sessionId);
            }
            this.renderSessionsList();
        },
        
        /**
         * Toggle All Bulk Selection
         */
        toggleAllBulkSelection() {
            const sessions = this.getPaginatedSessions();
            
            if (this.bulkSelection.size === sessions.length) {
                this.bulkSelection.clear();
            } else {
                sessions.forEach(s => this.bulkSelection.add(s.session_id));
            }
            
            this.renderSessionsList();
        },
        
        /**
         * Go to Page
         */
        goToPage(page) {
            if (page < 1 || page > this.pagination.totalPages) return;
            this.pagination.currentPage = page;
            this.renderSessionsList();
        },
        
        /**
         * Render Messages
         */
        renderMessages() {
            const container = document.getElementById('messages-list');
            if (!container) {
                console.warn('⚠️ Messages list container not found');
                return;
            }
            
            if (this.messages.length === 0) {
                container.innerHTML = `
                    <div class="text-center py-12">
                        <i data-lucide="message-square" class="w-16 h-16 mx-auto mb-4 opacity-50" style="color: var(--border-primary);"></i>
                        <p class="text-sm font-medium" style="color: var(--text-tertiary);">ยังไม่มีข้อความในการสนทนานี้</p>
                    </div>
                `;
                lucide.createIcons();
                return;
            }
            
            container.innerHTML = this.messages.map(msg => `
                <div class="card-enterprise p-4 mb-3" id="msg-${msg.id}">
                    <div class="flex items-start justify-between mb-2">
                        <div class="flex items-center gap-2">
                            <span class="px-2 py-1 text-xs font-semibold rounded ${msg.role === 'user' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'}">
                                ${msg.role === 'user' ? 'USER' : 'BOT'}
                            </span>
                            <span class="text-xs" style="color: var(--text-tertiary);">${this.formatDateTime(msg.created_at)}</span>
                        </div>
                        <div class="flex gap-2">
                            <button onclick="app.database.startEditMessage(${msg.id})" 
                                    class="p-1 hover:bg-gray-100 rounded transition-colors"
                                    title="แก้ไขข้อความ">
                                <i data-lucide="edit" class="w-4 h-4"></i>
                            </button>
                            <button onclick="app.database.deleteMessage(${msg.id})" 
                                    class="p-1 hover:bg-red-100 text-red-600 rounded transition-colors"
                                    title="ลบข้อความ">
                                <i data-lucide="trash-2" class="w-4 h-4"></i>
                            </button>
                        </div>
                    </div>
                    <div id="content-${msg.id}" class="prose prose-sm max-w-none" style="color: var(--text-primary);">
                        ${this.escapeHtml(msg.content).replace(/\n/g, '<br>')}
                    </div>
                </div>
            `).join('');
            
            lucide.createIcons();
        },
        
        /**
         * Start Edit Message
         */
        startEditMessage(messageId) {
            const message = this.messages.find(m => m.id === messageId);
            if (!message) {
                console.error('❌ Message not found:', messageId);
                return;
            }
            
            const contentDiv = document.getElementById(`content-${messageId}`);
            if (!contentDiv) {
                console.error('❌ Content div not found for message:', messageId);
                return;
            }
            
            contentDiv.innerHTML = `
                <textarea class="w-full p-3 border-2 rounded-lg transition-all focus:ring-2 focus:ring-purple-500" 
                          style="border-color: var(--border-primary);" 
                          rows="4">${this.escapeHtml(message.content)}</textarea>
                <div class="flex gap-2 mt-3">
                    <button onclick="app.database.saveEditMessage(${messageId})" 
                            class="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-all font-bold">
                        💾 บันทึก
                    </button>
                    <button onclick="app.database.cancelEdit()" 
                            class="px-4 py-2 bg-gray-200 rounded-lg hover:bg-gray-300 transition-all font-bold"
                            style="color: var(--text-primary);">
                        ✕ ยกเลิก
                    </button>
                </div>
            `;
            
            const textarea = contentDiv.querySelector('textarea');
            if (textarea) {
                textarea.focus();
                textarea.setSelectionRange(textarea.value.length, textarea.value.length);
            }
        },
        
        /**
         * Save Edit Message
         */
        saveEditMessage(messageId) {
            const textarea = document.querySelector(`#content-${messageId} textarea`);
            if (textarea) {
                const newContent = textarea.value.trim();
                if (newContent) {
                    this.updateMessage(messageId, newContent);
                } else {
                    app.showToast('ข้อความไม่สามารถเว้นว่างได้', 'warning');
                }
            }
        },
        
        /**
         * Cancel Edit
         */
        cancelEdit() {
            this.renderMessages();
        },
        
        /**
         * Format Date (Short)
         */
        formatDate(dateString) {
            if (!dateString) return 'N/A';
            const date = new Date(dateString);
            return date.toLocaleDateString('th-TH', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric'
            });
        },
        
        /**
         * Format DateTime (Full)
         */
        formatDateTime(dateString) {
            if (!dateString) return 'N/A';
            const date = new Date(dateString);
            return date.toLocaleString('th-TH', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        },
        
        /**
         * Escape HTML for security
         */
        escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },
        
        /**
         * Render Main UI
         */
        render() {
            const container = document.getElementById('database-container');
            if (!container) {
                console.error('❌ Database container not found');
                return;
            }
            
            container.innerHTML = `
                <div class="h-full flex flex-col animate-in">
                    <!-- Header -->
                    <div class="flex items-center justify-between mb-6">
                        <div>
                            <h1 class="text-3xl md:text-4xl font-black gradient-text-cmu mb-2">Database Management</h1>
                            <p class="text-sm font-medium" style="color: var(--text-secondary);">จัดการ Sessions และ Messages</p>
                        </div>
                        <div class="flex gap-2">
                            <button onclick="app.database.exportDatabase()" 
                                    class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2 font-bold transition-all shadow-lg">
                                <i data-lucide="download" class="w-4 h-4"></i>
                                <span class="hidden md:inline">Export</span>
                            </button>
                            <button onclick="app.database.cleanupOldSessions(7)" 
                                    class="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 flex items-center gap-2 font-bold transition-all shadow-lg">
                                <i data-lucide="trash-2" class="w-4 h-4"></i>
                                <span class="hidden md:inline">Cleanup</span>
                            </button>
                        </div>
                    </div>

                    <!-- Stats Cards -->
                    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                        <div class="card-enterprise p-4 rounded-xl shadow-lg">
                            <div class="flex items-center justify-between mb-2">
                                <div class="text-xs font-bold uppercase tracking-wider" style="color: var(--text-tertiary);">Total Sessions</div>
                                <i data-lucide="users" class="w-4 h-4" style="color: var(--cmu-purple);"></i>
                            </div>
                            <div class="text-3xl font-black" style="color: var(--cmu-purple);">${this.stats.totalSessions || 0}</div>
                        </div>
                        <div class="card-enterprise p-4 rounded-xl shadow-lg">
                            <div class="flex items-center justify-between mb-2">
                                <div class="text-xs font-bold uppercase tracking-wider" style="color: var(--text-tertiary);">Total Messages</div>
                                <i data-lucide="message-square" class="w-4 h-4" style="color: var(--accent-gold);"></i>
                            </div>
                            <div class="text-3xl font-black" style="color: var(--accent-gold);">${this.stats.totalMessages || 0}</div>
                        </div>
                        <div class="card-enterprise p-4 rounded-xl shadow-lg">
                            <div class="flex items-center justify-between mb-2">
                                <div class="text-xs font-bold uppercase tracking-wider" style="color: var(--text-tertiary);">Active Today</div>
                                <i data-lucide="activity" class="w-4 h-4" style="color: var(--success);"></i>
                            </div>
                            <div class="text-3xl font-black" style="color: var(--success);">${this.stats.activeSessions || 0}</div>
                        </div>
                        <div class="card-enterprise p-4 rounded-xl shadow-lg">
                            <div class="flex items-center justify-between mb-2">
                                <div class="text-xs font-bold uppercase tracking-wider" style="color: var(--text-tertiary);">Platforms</div>
                                <i data-lucide="globe" class="w-4 h-4" style="color: var(--text-secondary);"></i>
                            </div>
                            <div class="flex flex-wrap gap-1 mt-2">
                                ${Object.entries(this.stats.platforms || {}).map(([platform, count]) => 
                                    `<span class="px-2 py-1 text-xs rounded-full bg-gray-100 font-bold" style="color: var(--text-primary);">${platform}: ${count}</span>`
                                ).join('')}
                            </div>
                        </div>
                    </div>

                    <!-- Filters -->
                    <div class="card-enterprise p-4 rounded-2xl shadow-lg mb-4">
                        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
                            <input type="text" 
                                   placeholder="🔍 ค้นหา Session..." 
                                   class="px-3 py-2 border-2 rounded-lg transition-all focus:ring-2 focus:ring-purple-500"
                                   style="border-color: var(--border-primary);"
                                   oninput="app.database.filters.search = this.value; app.database.pagination.currentPage = 1; app.database.renderSessionsList()">
                            
                            <select class="px-3 py-2 border-2 rounded-lg font-bold transition-all focus:ring-2 focus:ring-purple-500"
                                    style="border-color: var(--border-primary);"
                                    onchange="app.database.filters.platform = this.value; app.database.pagination.currentPage = 1; app.database.renderSessionsList()">
                                <option value="all">ทุก Platform</option>
                                <option value="line">LINE</option>
                                <option value="facebook">Facebook</option>
                                <option value="web">Web</option>
                            </select>
                            
                            <select class="px-3 py-2 border-2 rounded-lg font-bold transition-all focus:ring-2 focus:ring-purple-500"
                                    style="border-color: var(--border-primary);"
                                    onchange="app.database.filters.botEnabled = this.value; app.database.pagination.currentPage = 1; app.database.renderSessionsList()">
                                <option value="all">ทุกสถานะ Bot</option>
                                <option value="enabled">Bot เปิด</option>
                                <option value="disabled">Bot ปิด</option>
                            </select>
                            
                            <select class="px-3 py-2 border-2 rounded-lg font-bold transition-all focus:ring-2 focus:ring-purple-500"
                                    style="border-color: var(--border-primary);"
                                    onchange="app.database.filters.sortBy = this.value; app.database.renderSessionsList()">
                                <option value="last_active">เรียง: ใช้ล่าสุด</option>
                                <option value="created_at">เรียง: สร้าง</option>
                                <option value="user_name">เรียง: ชื่อ</option>
                            </select>
                            
                            <select class="px-3 py-2 border-2 rounded-lg font-bold transition-all focus:ring-2 focus:ring-purple-500"
                                    style="border-color: var(--border-primary);"
                                    onchange="app.database.filters.sortOrder = this.value; app.database.renderSessionsList()">
                                <option value="desc">↓ มาก → น้อย</option>
                                <option value="asc">↑ น้อย → มาก</option>
                            </select>
                        </div>
                        
                        <!-- Bulk Actions -->
                        <div class="mt-3 pt-3 border-t flex items-center justify-between gap-3" style="border-color: var(--border-secondary);">
                            <div class="flex items-center gap-2">
                                <button onclick="app.database.toggleAllBulkSelection()" 
                                        class="px-3 py-1 text-sm rounded-lg border-2 font-bold transition-all"
                                        style="border-color: var(--border-primary); color: var(--text-secondary);">
                                    เลือกทั้งหมด
                                </button>
                                <span class="text-sm font-bold" style="color: var(--text-tertiary);">
                                    เลือกแล้ว <span class="text-purple-600">${this.bulkSelection.size}</span> รายการ
                                </span>
                            </div>
                            <button onclick="app.database.bulkDeleteSessions()" 
                                    class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 flex items-center gap-2 font-bold transition-all shadow-lg"
                                    ${this.bulkSelection.size === 0 ? 'disabled style="opacity: 0.5; cursor: not-allowed;"' : ''}>
                                <i data-lucide="trash-2" class="w-4 h-4"></i>
                                ลบที่เลือก
                            </button>
                        </div>
                    </div>

                    <!-- Main Content -->
                    <div class="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-4 overflow-hidden">
                        <!-- Sessions List -->
                        <div class="flex flex-col">
                            <div class="flex items-center justify-between mb-3">
                                <h2 class="text-xl font-bold" style="color: var(--text-primary);">
                                    Sessions (${this.getFilteredSessions().length})
                                </h2>
                                <button onclick="app.database.loadSessions()" 
                                        class="p-2 rounded-lg transition-all hover:bg-gray-100"
                                        title="รีเฟรช">
                                    <i data-lucide="refresh-cw" class="w-5 h-5" style="color: var(--text-secondary);"></i>
                                </button>
                            </div>
                            <div id="sessions-list" class="flex-1 overflow-y-auto custom-scrollbar space-y-2 pr-2 mb-3"></div>
                            <div id="sessions-pagination" class="pt-3 border-t" style="border-color: var(--border-secondary);"></div>
                        </div>

                        <!-- Messages List -->
                        <div class="flex flex-col">
                            ${this.selectedSession ? `
                                <div class="mb-3">
                                    <div class="flex items-center justify-between">
                                        <div>
                                            <h2 class="text-xl font-bold" style="color: var(--text-primary);">Messages</h2>
                                            <p class="text-sm" style="color: var(--text-tertiary);">
                                                ${this.selectedSession.user_name} • ${this.messages.length} ข้อความ
                                            </p>
                                        </div>
                                        <div class="flex gap-2">
                                            <button onclick="app.database.updateSession('${this.selectedSession.session_id}', {bot_enabled: ${!this.selectedSession.bot_enabled}})" 
                                                    class="px-3 py-1 text-sm rounded-lg font-bold transition-all shadow-lg ${this.selectedSession.bot_enabled ? 'bg-red-100 text-red-700 hover:bg-red-200' : 'bg-green-100 text-green-700 hover:bg-green-200'}">
                                                ${this.selectedSession.bot_enabled ? '⛔ ปิด Bot' : '🤖 เปิด Bot'}
                                            </button>
                                            <button onclick="app.database.deleteSession('${this.selectedSession.session_id}')" 
                                                    class="px-3 py-1 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 font-bold transition-all shadow-lg">
                                                🗑️ ลบ Session
                                            </button>
                                        </div>
                                    </div>
                                </div>
                                <div id="messages-list" class="flex-1 overflow-y-auto custom-scrollbar pr-2"></div>
                            ` : `
                                <div class="flex-1 flex items-center justify-center">
                                    <div class="text-center">
                                        <i data-lucide="database" class="w-16 h-16 mx-auto mb-3 opacity-50" style="color: var(--border-primary);"></i>
                                        <p class="font-semibold" style="color: var(--text-tertiary);">เลือก Session เพื่อดูข้อความ</p>
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
    
    // Override switchTab to auto-load when switching to database tab
    const originalSwitchTab = app.switchTab.bind(app);
    app.switchTab = function(tab) {
        originalSwitchTab(tab);
        if (tab === 'database') {
            app.database.render();
            app.database.loadSessions();
        }
    };
}

// Auto-initialize if Alpine is already loaded
if (typeof window !== 'undefined') {
    document.addEventListener('alpine:initialized', () => {
        console.log('🟢 Database module ready for initialization');
        const appElement = document.querySelector('[x-data]');
        if (appElement && appElement.__x && appElement.__x.$data) {
            const app = appElement.__x.$data;
            if (!app.database) {
                console.log('🔵 Auto-initializing database module');
                initDatabaseModule(app);
            }
        }
    });
}