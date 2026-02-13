window.logsState = {
    logs: [],
    filteredLogs: [],
    searchQuery: '',
    sortBy: 'timestamp',
    sortDesc: true,
    currentPage: 1,
    itemsPerPage: 20,
    loading: false,
    error: null
};

/**
 * Load Logs Tab Content
 */
window.loadLogsTab = function() {
    const container = document.getElementById('logs-container');
    if (!container) return;
    
    container.innerHTML = `
        <div x-data="logsModule()" x-init="init()" class="animate-in">
            <!-- Header -->
            <div class="mb-8">
                <h1 class="text-4xl md:text-5xl font-black gradient-text-cmu mb-2">Audit Logs</h1>
                <p class="font-medium" style="color: var(--text-secondary);">System Activity Monitoring & Analytics</p>
            </div>

            <!-- Error Alert -->
            <div x-show="error" class="mb-6 card-enterprise p-4 rounded-xl border-2 border-red-500 bg-red-50">
                <div class="flex items-center gap-3">
                    <i data-lucide="alert-triangle" class="w-5 h-5 text-red-600"></i>
                    <div>
                        <p class="font-bold text-red-800">เกิดข้อผิดพลาด</p>
                        <p class="text-sm text-red-600" x-text="error"></p>
                    </div>
                </div>
            </div>

            <!-- Stats Summary -->
            <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                <!-- Total Queries -->
                <div class="card-enterprise stat-card p-6 rounded-xl shadow-lg">
                    <p class="text-xs font-bold uppercase tracking-wider mb-2" style="color: var(--text-tertiary);">Total Queries</p>
                    <h3 class="text-3xl font-black" style="color: var(--text-primary);" x-text="logs.length">0</h3>
                </div>
                
                <!-- Avg Response Time -->
                <div class="card-enterprise stat-card p-6 rounded-xl shadow-lg">
                    <p class="text-xs font-bold uppercase tracking-wider mb-2" style="color: var(--text-tertiary);">Avg Response Time</p>
                    <h3 class="text-3xl font-black gradient-text-cmu" x-text="calculateAvgLatency() + 's'">0s</h3>
                </div>
                
                <!-- Total Tokens -->
                <div class="card-enterprise stat-card p-6 rounded-xl shadow-lg">
                    <p class="text-xs font-bold uppercase tracking-wider mb-2" style="color: var(--text-tertiary);">Total Tokens</p>
                    <h3 class="text-3xl font-black" style="color: var(--accent-gold);" x-text="calculateTotalTokens().toLocaleString()">0</h3>
                </div>
                
                <!-- Success Rate -->
                <div class="card-enterprise stat-card p-6 rounded-xl shadow-lg">
                    <p class="text-xs font-bold uppercase tracking-wider mb-2" style="color: var(--text-tertiary);">Success Rate</p>
                    <h3 class="text-3xl font-black" style="color: var(--success);" x-text="calculateSuccessRate() + '%'">100%</h3>
                </div>
            </div>

            <!-- Filters & Search -->
            <div class="card-enterprise p-6 rounded-2xl shadow-lg mb-6">
                <div class="flex flex-col md:flex-row gap-4">
                    <!-- Search -->
                    <div class="flex-1">
                        <div class="relative">
                            <i data-lucide="search" class="w-5 h-5 absolute left-3 top-1/2 transform -translate-y-1/2" style="color: var(--text-tertiary);"></i>
                            <input 
                                type="text" 
                                x-model="searchQuery" 
                                @input="filterLogs()"
                                placeholder="ค้นหา query, response, user..."
                                class="w-full pl-10 pr-4 py-3 rounded-xl border-2 transition-all"
                                style="border-color: var(--border-primary); background-color: var(--bg-secondary); color: var(--text-primary);">
                        </div>
                    </div>

                    <!-- Sort Controls -->
                    <div class="flex items-center gap-2">
                        <select 
                            x-model="sortBy" 
                            @change="filterLogs()"
                            class="px-4 py-3 rounded-xl border-2 font-bold transition-all"
                            style="border-color: var(--border-primary); background-color: var(--bg-secondary); color: var(--text-primary);">
                            <option value="timestamp">เวลา</option>
                            <option value="latency">Latency</option>
                            <option value="anon_id">User ID</option>
                            <option value="platform">Platform</option>
                        </select>
                        
                        <button 
                            @click="sortDesc = !sortDesc; filterLogs()"
                            class="p-3 rounded-xl border-2 transition-all"
                            style="border-color: var(--border-primary);">
                            <i :data-lucide="sortDesc ? 'arrow-down' : 'arrow-up'" class="w-5 h-5" style="color: var(--text-secondary);"></i>
                        </button>
                        
                        <button 
                            @click="loadLogs()"
                            :disabled="loading"
                            class="p-3 rounded-xl text-white btn-enterprise disabled:opacity-50"
                            style="background-color: var(--cmu-purple);">
                            <i :data-lucide="loading ? 'loader' : 'refresh-cw'" class="w-5 h-5" :class="{'animate-spin': loading}"></i>
                        </button>
                    </div>
                </div>
            </div>

            <!-- Loading State -->
            <div x-show="loading && logs.length === 0" class="text-center py-12">
                <div class="w-16 h-16 border-4 rounded-full animate-spin mx-auto mb-4" 
                     style="border-color: var(--bg-tertiary); border-top-color: var(--cmu-purple);"></div>
                <p class="text-lg font-bold" style="color: var(--text-secondary);">กำลังโหลด logs...</p>
            </div>

            <!-- Logs Table -->
            <div x-show="!loading || logs.length > 0" class="card-enterprise rounded-2xl shadow-lg overflow-hidden">
                <div class="overflow-x-auto">
                    <table class="w-full table-enterprise">
                        <thead style="background-color: var(--bg-tertiary); border-bottom: 2px solid var(--border-primary);">
                            <tr>
                                <th class="px-6 py-4 text-left text-xs font-bold uppercase tracking-wider" style="color: var(--text-secondary);">เวลา</th>
                                <th class="px-6 py-4 text-left text-xs font-bold uppercase tracking-wider" style="color: var(--text-secondary);">Platform</th>
                                <th class="px-6 py-4 text-left text-xs font-bold uppercase tracking-wider" style="color: var(--text-secondary);">User</th>
                                <th class="px-6 py-4 text-left text-xs font-bold uppercase tracking-wider" style="color: var(--text-secondary);">Query</th>
                                <th class="px-6 py-4 text-left text-xs font-bold uppercase tracking-wider hidden md:table-cell" style="color: var(--text-secondary);">Response</th>
                                <th class="px-6 py-4 text-left text-xs font-bold uppercase tracking-wider" style="color: var(--text-secondary);">Latency</th>
                                <th class="px-6 py-4 text-left text-xs font-bold uppercase tracking-wider hidden lg:table-cell" style="color: var(--text-secondary);">Tokens/Cost</th>
                            </tr>
                        </thead>
                        <tbody style="border-top: 1px solid var(--border-secondary);">
                            <template x-for="log in paginatedLogs" :key="log.timestamp + log.anon_id + Math.random()">
                                <tr class="cursor-pointer transition-colors border-b hover:bg-opacity-50" 
                                    style="border-color: var(--border-secondary);"
                                    @click="showLogDetail(log)">
                                    
                                    <td class="px-6 py-4 text-sm font-medium" style="color: var(--text-secondary);">
                                        <div class="flex items-center gap-2">
                                            <i data-lucide="clock" class="w-4 h-4" style="color: var(--cmu-purple);"></i>
                                            <span x-text="formatTimestamp(log.timestamp)"></span>
                                        </div>
                                    </td>
                                    
                                    <td class="px-6 py-4 text-sm">
                                        <span class="badge-enterprise" 
                                              :style="log.platform === 'web' ? 'background-color: rgba(81, 45, 109, 0.1); color: var(--cmu-purple);' : 
                                                      log.platform === 'facebook' ? 'background-color: rgba(24, 119, 242, 0.1); color: #1877F2;' : 
                                                      'background-color: var(--bg-tertiary); color: var(--text-secondary);'"
                                              x-text="log.platform || 'unknown'">
                                        </span>
                                    </td>
                                    
                                    <td class="px-6 py-4 text-sm">
                                        <span class="badge-enterprise" 
                                              style="background-color: rgba(81, 45, 109, 0.1); color: var(--cmu-purple);"
                                              x-text="log.anon_id ? log.anon_id.substring(0, 8) + '...' : 'Anonymous'">
                                        </span>
                                    </td>
                                    
                                    <td class="px-6 py-4 text-sm font-medium max-w-xs truncate" 
                                        style="color: var(--text-primary);"
                                        x-text="log.input">
                                    </td>
                                    
                                    <td class="px-6 py-4 text-sm max-w-xs truncate hidden md:table-cell" 
                                        style="color: var(--text-secondary);"
                                        x-text="log.output">
                                    </td>
                                    
                                    <td class="px-6 py-4 text-sm">
                                        <span class="badge-enterprise"
                                            :style="log.latency < 1 ? 'background-color: rgba(52, 199, 89, 0.1); color: var(--success);' : 
                                                    log.latency < 3 ? 'background-color: rgba(255, 149, 0, 0.1); color: var(--warning);' : 
                                                    'background-color: rgba(255, 59, 48, 0.1); color: var(--danger);'"
                                            x-text="log.latency.toFixed(2) + 's'">
                                        </span>
                                    </td>

                                    <td class="px-6 py-4 text-sm hidden lg:table-cell">
                                        <template x-if="log.tokens">
                                            <div class="flex flex-col gap-1">
                                                <span class="badge-enterprise text-xs" 
                                                      style="background-color: rgba(81, 45, 109, 0.1); color: var(--cmu-purple);"
                                                      x-text="log.tokens.total.toLocaleString() + ' tokens'">
                                                </span>
                                                <template x-if="log.tokens.cost_usd">
                                                    <span class="badge-enterprise text-xs" 
                                                          style="background-color: rgba(196, 160, 82, 0.1); color: var(--accent-gold);"
                                                          x-text="'$' + log.tokens.cost_usd.toFixed(6)">
                                                    </span>
                                                </template>
                                            </div>
                                        </template>
                                        <template x-if="!log.tokens">
                                            <span class="text-xs" style="color: var(--text-tertiary);">N/A</span>
                                        </template>
                                    </td>
                                </tr>
                            </template>
                        </tbody>
                    </table>

                    <!-- Empty State -->
                    <div x-show="filteredLogs.length === 0 && !loading" class="text-center py-20">
                        <i data-lucide="inbox" class="w-16 h-16 mx-auto mb-4" style="color: var(--border-primary);"></i>
                        <p class="font-semibold text-lg mb-2" style="color: var(--text-secondary);">ไม่พบข้อมูล</p>
                        <p class="text-sm" style="color: var(--text-tertiary);">
                            <template x-if="searchQuery">
                                ลองค้นหาด้วยคำอื่น หรือกดปุ่มรีเฟรช
                            </template>
                            <template x-if="!searchQuery">
                                ยังไม่มี logs ในระบบ หรือกดปุ่มรีเฟรชเพื่อโหลดข้อมูล
                            </template>
                        </p>
                    </div>
                </div>

                <!-- Pagination -->
                <div x-show="totalPages > 1" 
                     class="border-t px-6 py-4 flex items-center justify-between"
                     style="border-color: var(--border-primary);">
                    <div class="text-sm" style="color: var(--text-secondary);">
                        แสดง <span class="font-bold" x-text="((currentPage - 1) * itemsPerPage) + 1"></span>
                        - <span class="font-bold" x-text="Math.min(currentPage * itemsPerPage, filteredLogs.length)"></span>
                        จาก <span class="font-bold" x-text="filteredLogs.length"></span> รายการ
                    </div>
                    
                    <div class="flex items-center gap-2">
                        <button 
                            @click="currentPage = Math.max(1, currentPage - 1)"
                            :disabled="currentPage === 1"
                            class="px-4 py-2 rounded-lg border-2 font-bold text-sm disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                            style="border-color: var(--border-primary);">
                            <i data-lucide="chevron-left" class="w-4 h-4"></i>
                        </button>
                        
                        <span class="text-sm font-bold" style="color: var(--text-secondary);">
                            <span x-text="currentPage"></span> / <span x-text="totalPages"></span>
                        </span>
                        
                        <button 
                            @click="currentPage = Math.min(totalPages, currentPage + 1)"
                            :disabled="currentPage === totalPages"
                            class="px-4 py-2 rounded-lg border-2 font-bold text-sm disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                            style="border-color: var(--border-primary);">
                            <i data-lucide="chevron-right" class="w-4 h-4"></i>
                        </button>
                    </div>
                </div>
            </div>

            <!-- Log Detail Modal -->
            <div 
                x-show="selectedLog" 
                x-cloak 
                class="preview-modal fixed inset-0 z-[2000] flex items-center justify-center p-4"
                style="background-color: var(--overlay);">
                <div class="preview-content card-enterprise rounded-3xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto animate-in">
                    <!-- Modal Header -->
                    <div class="p-6 border-b flex justify-between items-center sticky top-0 z-10"
                         style="border-color: var(--border-primary); background-color: var(--bg-secondary);">
                        <div class="flex items-center gap-3">
                            <div class="p-2 rounded-lg" style="background-color: var(--bg-tertiary);">
                                <i data-lucide="file-text" class="w-5 h-5" style="color: var(--cmu-purple);"></i>
                            </div>
                            <span class="font-bold" style="color: var(--text-primary);">Log Details</span>
                        </div>
                        <button 
                            @click="selectedLog = null" 
                            class="p-2 rounded-xl transition-all">
                            <i data-lucide="x" class="w-6 h-6" style="color: var(--text-secondary);"></i>
                        </button>
                    </div>

                    <!-- Modal Content -->
                    <div class="p-6 space-y-6">
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="text-xs font-bold uppercase tracking-wider" style="color: var(--text-tertiary);">Timestamp</label>
                                <p class="font-semibold mt-1" style="color: var(--text-primary);" 
                                   x-text="selectedLog && formatTimestamp(selectedLog.timestamp)"></p>
                            </div>
                            
                            <div>
                                <label class="text-xs font-bold uppercase tracking-wider" style="color: var(--text-tertiary);">Platform</label>
                                <p class="font-semibold mt-1" style="color: var(--text-primary);" 
                                   x-text="selectedLog && (selectedLog.platform || 'unknown')"></p>
                            </div>
                        </div>
                        
                        <div>
                            <label class="text-xs font-bold uppercase tracking-wider" style="color: var(--text-tertiary);">User ID</label>
                            <p class="font-semibold mt-1 font-mono text-xs" style="color: var(--text-primary);" 
                               x-text="selectedLog && (selectedLog.anon_id || 'Anonymous')"></p>
                        </div>
                        
                        <div>
                            <label class="text-xs font-bold uppercase tracking-wider mb-2 block" style="color: var(--text-tertiary);">Query</label>
                            <div class="p-4 rounded-xl" style="background-color: rgba(81, 45, 109, 0.05);">
                                <p class="font-medium whitespace-pre-wrap" style="color: var(--text-primary);" 
                                   x-text="selectedLog && selectedLog.input"></p>
                            </div>
                        </div>
                        
                        <div>
                            <label class="text-xs font-bold uppercase tracking-wider mb-2 block" style="color: var(--text-tertiary);">Response</label>
                            <div class="p-4 rounded-xl" style="background-color: rgba(196, 160, 82, 0.05);">
                                <p class="whitespace-pre-wrap" style="color: var(--text-secondary);" 
                                   x-text="selectedLog && selectedLog.output"></p>
                            </div>
                        </div>
                        
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="text-xs font-bold uppercase tracking-wider" style="color: var(--text-tertiary);">Latency</label>
                                <p class="text-2xl font-black gradient-text-cmu mt-1" 
                                   x-text="selectedLog && selectedLog.latency.toFixed(2) + 's'"></p>
                            </div>
                            
                            <div x-show="selectedLog && selectedLog.rating && selectedLog.rating !== 'none'">
                                <label class="text-xs font-bold uppercase tracking-wider" style="color: var(--text-tertiary);">Rating</label>
                                <p class="text-2xl font-black mt-1" style="color: var(--success);" 
                                   x-text="selectedLog && selectedLog.rating"></p>
                            </div>
                        </div>
                        
                        <!-- Token Information -->
                        <div x-show="selectedLog && selectedLog.tokens" class="mt-4">
                            <label class="text-xs font-bold uppercase tracking-wider mb-3 block" style="color: var(--text-tertiary);">Token Usage & Cost</label>
                            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                                <div class="p-4 rounded-xl" style="background-color: rgba(81, 45, 109, 0.05);">
                                    <p class="text-xs font-bold mb-1" style="color: var(--text-tertiary);">Prompt</p>
                                    <p class="text-xl font-black" style="color: var(--cmu-purple);" 
                                       x-text="selectedLog && selectedLog.tokens && selectedLog.tokens.prompt.toLocaleString() || 0"></p>
                                </div>
                                <div class="p-4 rounded-xl" style="background-color: rgba(52, 199, 89, 0.05);">
                                    <p class="text-xs font-bold mb-1" style="color: var(--text-tertiary);">Completion</p>
                                    <p class="text-xl font-black" style="color: var(--success);" 
                                       x-text="selectedLog && selectedLog.tokens && selectedLog.tokens.completion.toLocaleString() || 0"></p>
                                </div>
                                <div class="p-4 rounded-xl" style="background-color: rgba(196, 160, 82, 0.05);">
                                    <p class="text-xs font-bold mb-1" style="color: var(--text-tertiary);">Total</p>
                                    <p class="text-xl font-black" style="color: var(--accent-gold);" 
                                       x-text="selectedLog && selectedLog.tokens && selectedLog.tokens.total.toLocaleString() || 0"></p>
                                </div>
                                <div class="p-4 rounded-xl" style="background-color: rgba(255, 149, 0, 0.05);" 
                                     x-show="selectedLog && selectedLog.tokens && selectedLog.tokens.cost_usd">
                                    <p class="text-xs font-bold mb-1" style="color: var(--text-tertiary);">Cost (USD)</p>
                                    <p class="text-xl font-black" style="color: var(--warning);" 
                                       x-text="selectedLog && selectedLog.tokens && selectedLog.tokens.cost_usd ? '$' + selectedLog.tokens.cost_usd.toFixed(6) : '$0'"></p>
                                </div>
                            </div>
                            <div x-show="selectedLog && selectedLog.tokens && selectedLog.tokens.cached" 
                                 class="mt-3 px-4 py-2 rounded-xl flex items-center gap-2"
                                 style="background-color: rgba(52, 199, 89, 0.1);">
                                <i data-lucide="zap" class="w-4 h-4" style="color: var(--success);"></i>
                                <span class="text-sm font-bold" style="color: var(--success);">Cached Response (Faster & Cheaper)</span>
                            </div>
                        </div>
                    </div>

                    <!-- Modal Footer -->
                    <div class="p-6 border-t flex justify-end" style="border-color: var(--border-primary);">
                        <button 
                            @click="selectedLog = null" 
                            class="px-6 py-3 gradient-cmu text-white rounded-xl font-bold btn-enterprise">
                            ปิด
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;

    setTimeout(() => lucide.createIcons(), 100);
};

/**
 * Logs Module for Alpine.js
 */
window.logsModule = function() {
    return {
        ...window.logsState,
        selectedLog: null,

        get paginatedLogs() {
            const start = (this.currentPage - 1) * this.itemsPerPage;
            const end = start + this.itemsPerPage;
            return this.filteredLogs.slice(start, end);
        },

        get totalPages() {
            return Math.ceil(this.filteredLogs.length / this.itemsPerPage);
        },

        init() {
            console.log('🚀 [Logs] Initializing Logs Module...');
            this.loadLogs();
        },

        async loadLogs() {
            const token = localStorage.getItem('adminToken');
            
            if (!token) {
                console.error('❌ [Logs] No admin token found');
                this.error = 'ไม่พบ Admin Token - กรุณา Login ใหม่';
                return;
            }
            
            this.loading = true;
            this.error = null;
            
            try {
                console.log('📡 [Logs] Fetching from /api/admin/stats...');
                
                const res = await fetch('/api/admin/stats', {
                    headers: { 'X-Admin-Token': token }
                });
                
                if (!res.ok) {
                    throw new Error(`HTTP ${res.status}: ${res.statusText}`);
                }
                
                const data = await res.json();
                
                console.log('📦 [Logs] Response:', {
                    hasRecentLogs: !!data.recent_logs,
                    logsCount: data.recent_logs?.length || 0,
                    sampleLog: data.recent_logs?.[0]
                });
                
                if (!data.recent_logs) {
                    console.warn('⚠️ [Logs] No recent_logs in response');
                    this.logs = [];
                } else {
                    this.logs = data.recent_logs;
                    console.log(`✅ [Logs] Loaded ${this.logs.length} logs successfully`);
                }
                
                this.filterLogs();
                
                setTimeout(() => lucide.createIcons(), 100);
            } catch (e) {
                console.error('❌ [Logs] Failed to load:', e);
                this.error = `ไม่สามารถโหลด logs: ${e.message}`;
                this.logs = [];
                this.filteredLogs = [];
            } finally {
                this.loading = false;
            }
        },

        filterLogs() {
            let filtered = [...this.logs];

            // Search filter
            if (this.searchQuery) {
                const query = this.searchQuery.toLowerCase();
                filtered = filtered.filter(log => 
                    (log.input && log.input.toLowerCase().includes(query)) ||
                    (log.output && log.output.toLowerCase().includes(query)) ||
                    (log.anon_id && log.anon_id.toLowerCase().includes(query)) ||
                    (log.platform && log.platform.toLowerCase().includes(query))
                );
            }

            // Sort
            filtered.sort((a, b) => {
                let aVal = a[this.sortBy];
                let bVal = b[this.sortBy];
                
                if (this.sortBy === 'timestamp') {
                    aVal = new Date(aVal);
                    bVal = new Date(bVal);
                }
                
                if (aVal < bVal) return this.sortDesc ? 1 : -1;
                if (aVal > bVal) return this.sortDesc ? -1 : 1;
                return 0;
            });

            this.filteredLogs = filtered;
            this.currentPage = 1;
            
            console.log(`🔍 [Logs] Filtered to ${filtered.length} logs`);
        },

        formatTimestamp(timestamp) {
            if (!timestamp) return 'N/A';
            
            const date = new Date(timestamp);
            
            if (isNaN(date.getTime())) {
                return timestamp;
            }
            
            const day = String(date.getDate()).padStart(2, '0');
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const year = date.getFullYear();
            const hours = String(date.getHours()).padStart(2, '0');
            const minutes = String(date.getMinutes()).padStart(2, '0');
            const seconds = String(date.getSeconds()).padStart(2, '0');
            
            return `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`;
        },

        showLogDetail(log) {
            this.selectedLog = log;
            setTimeout(() => lucide.createIcons(), 100);
        },

        calculateAvgLatency() {
            if (this.logs.length === 0) return 0;
            const sum = this.logs.reduce((a, b) => a + (b.latency || 0), 0);
            return (sum / this.logs.length).toFixed(1);
        },

        calculateSuccessRate() {
            if (this.logs.length === 0) return 100;
            const successCount = this.logs.filter(log => log.output && log.output.length > 0).length;
            return ((successCount / this.logs.length) * 100).toFixed(1);
        },

        getTodayCount() {
            const today = new Date();
            today.setHours(0, 0, 0, 0);
            
            return this.logs.filter(log => {
                const logDate = new Date(log.timestamp);
                logDate.setHours(0, 0, 0, 0);
                return logDate.getTime() === today.getTime();
            }).length;
        },

        calculateTotalTokens() {
            if (this.logs.length === 0) return 0;
            return this.logs.reduce((sum, log) => {
                return sum + (log.tokens?.total || 0);
            }, 0);
        }
    };
};