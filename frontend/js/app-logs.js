/**
 * Audit Logs Module
 * จัดการการแสดงผล Audit Logs และ Analytics
 */

// Global state for logs
window.logsState = {
    logs: [],
    filteredLogs: [],
    searchQuery: '',
    sortBy: 'timestamp',
    sortDesc: true,
    currentPage: 1,
    itemsPerPage: 20
};

/**
 * Load Logs Tab Content
 */
window.loadLogsTab = function() {
    const container = document.getElementById('logs-container');
    if (!container) return;
    
    container.innerHTML = `
        <div x-data="logsModule()" x-init="loadLogs()">
            <div class="mb-8 md:mb-10">
                <h1 class="text-4xl md:text-5xl font-black gradient-text mb-2">Audit Logs</h1>
                <p class="text-gray-500 font-medium">ติดตามและวิเคราะห์กิจกรรมของระบบ</p>
            </div>

            <!-- Stats Summary -->
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4 md:gap-6 mb-8">
                <div class="card-base p-6 rounded-xl shadow-lg border-l-4 border-purple-500">
                    <p class="text-xs font-bold uppercase text-gray-500 mb-2">Total Queries</p>
                    <h3 class="text-3xl font-black text-gray-800" x-text="logs.length">0</h3>
                </div>
                
                <div class="card-base p-6 rounded-xl shadow-lg border-l-4 border-orange-500">
                    <p class="text-xs font-bold uppercase text-gray-500 mb-2">Avg Response Time</p>
                    <h3 class="text-3xl font-black gradient-text" x-text="calculateAvgLatency() + 'ms'">0ms</h3>
                </div>
                
                <div class="card-base p-6 rounded-xl shadow-lg border-l-4 border-green-500">
                    <p class="text-xs font-bold uppercase text-gray-500 mb-2">Success Rate</p>
                    <h3 class="text-3xl font-black text-green-600" x-text="calculateSuccessRate() + '%'">0%</h3>
                </div>
                
                <div class="card-base p-6 rounded-xl shadow-lg border-l-4 border-blue-500">
                    <p class="text-xs font-bold uppercase text-gray-500 mb-2">Today's Queries</p>
                    <h3 class="text-3xl font-black text-blue-600" x-text="getTodayCount()">0</h3>
                </div>
            </div>

            <!-- Filters & Search -->
            <div class="card-base p-4 md:p-6 rounded-2xl shadow-lg mb-6">
                <div class="flex flex-col md:flex-row gap-4">
                    <!-- Search -->
                    <div class="flex-1">
                        <div class="relative">
                            <i data-lucide="search" class="w-5 h-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400"></i>
                            <input type="text" 
                                x-model="searchQuery" 
                                @input="filterLogs()"
                                placeholder="ค้นหา query, response, user..."
                                class="w-full pl-10 pr-4 py-3 rounded-xl border-2 border-gray-200 focus:border-purple-500 outline-none">
                        </div>
                    </div>

                    <!-- Sort -->
                    <div class="flex items-center space-x-2">
                        <select x-model="sortBy" @change="filterLogs()"
                            class="px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-purple-500 outline-none font-bold">
                            <option value="timestamp">เวลา</option>
                            <option value="latency">Latency</option>
                            <option value="user_id">User ID</option>
                        </select>
                        
                        <button @click="sortDesc = !sortDesc; filterLogs()"
                            class="p-3 rounded-xl border-2 border-gray-200 hover:border-purple-500 transition">
                            <i :data-lucide="sortDesc ? 'arrow-down' : 'arrow-up'" class="w-5 h-5 text-gray-600"></i>
                        </button>
                        
                        <button @click="loadLogs()"
                            class="p-3 rounded-xl bg-purple-500 text-white hover:bg-purple-600 transition">
                            <i data-lucide="refresh-cw" class="w-5 h-5"></i>
                        </button>
                    </div>
                </div>
            </div>

            <!-- Logs Table -->
            <div class="card-base rounded-2xl shadow-lg overflow-hidden">
                <div class="overflow-x-auto">
                    <table class="w-full">
                        <thead class="bg-gray-50 border-b-2 border-gray-200">
                            <tr>
                                <th class="px-4 md:px-6 py-4 text-left text-xs font-black uppercase text-gray-600">เวลา</th>
                                <th class="px-4 md:px-6 py-4 text-left text-xs font-black uppercase text-gray-600">User</th>
                                <th class="px-4 md:px-6 py-4 text-left text-xs font-black uppercase text-gray-600">Query</th>
                                <th class="px-4 md:px-6 py-4 text-left text-xs font-black uppercase text-gray-600 hidden md:table-cell">Response</th>
                                <th class="px-4 md:px-6 py-4 text-left text-xs font-black uppercase text-gray-600">Latency</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-200">
                            <template x-for="log in paginatedLogs" :key="log.timestamp">
                                <tr class="hover:bg-gray-50 transition cursor-pointer" @click="showLogDetail(log)">
                                    <td class="px-4 md:px-6 py-4 text-sm font-medium text-gray-600">
                                        <div class="flex items-center space-x-2">
                                            <i data-lucide="clock" class="w-4 h-4 text-purple-500"></i>
                                            <span x-text="formatTimestamp(log.timestamp)"></span>
                                        </div>
                                    </td>
                                    <td class="px-4 md:px-6 py-4 text-sm">
                                        <span class="px-3 py-1 bg-purple-100 text-purple-700 rounded-full font-bold text-xs"
                                            x-text="log.user_id || 'Anonymous'">
                                        </span>
                                    </td>
                                    <td class="px-4 md:px-6 py-4 text-sm font-medium text-gray-800 max-w-xs truncate"
                                        x-text="log.query">
                                    </td>
                                    <td class="px-4 md:px-6 py-4 text-sm text-gray-600 max-w-xs truncate hidden md:table-cell"
                                        x-text="log.response">
                                    </td>
                                    <td class="px-4 md:px-6 py-4 text-sm">
                                        <span class="px-3 py-1 rounded-full font-bold text-xs"
                                            :class="log.latency < 1000 ? 'bg-green-100 text-green-700' : log.latency < 3000 ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700'"
                                            x-text="log.latency + 'ms'">
                                        </span>
                                    </td>
                                </tr>
                            </template>
                        </tbody>
                    </table>

                    <!-- Empty State -->
                    <div x-show="filteredLogs.length === 0" class="text-center py-12">
                        <i data-lucide="inbox" class="w-16 h-16 mx-auto text-gray-300 mb-4"></i>
                        <p class="text-gray-500 font-medium">ไม่พบข้อมูล</p>
                    </div>
                </div>

                <!-- Pagination -->
                <div x-show="totalPages > 1" class="border-t border-gray-200 px-4 md:px-6 py-4 flex items-center justify-between">
                    <div class="text-sm text-gray-600">
                        แสดง <span class="font-bold" x-text="((currentPage - 1) * itemsPerPage) + 1"></span>
                        - <span class="font-bold" x-text="Math.min(currentPage * itemsPerPage, filteredLogs.length)"></span>
                        จาก <span class="font-bold" x-text="filteredLogs.length"></span> รายการ
                    </div>
                    
                    <div class="flex items-center space-x-2">
                        <button @click="currentPage = Math.max(1, currentPage - 1)"
                            :disabled="currentPage === 1"
                            class="px-3 md:px-4 py-2 rounded-lg border-2 border-gray-200 font-bold text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:border-purple-500 transition">
                            <i data-lucide="chevron-left" class="w-4 h-4"></i>
                        </button>
                        
                        <span class="text-sm font-bold text-gray-600">
                            <span x-text="currentPage"></span> / <span x-text="totalPages"></span>
                        </span>
                        
                        <button @click="currentPage = Math.min(totalPages, currentPage + 1)"
                            :disabled="currentPage === totalPages"
                            class="px-3 md:px-4 py-2 rounded-lg border-2 border-gray-200 font-bold text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:border-purple-500 transition">
                            <i data-lucide="chevron-right" class="w-4 h-4"></i>
                        </button>
                    </div>
                </div>
            </div>

            <!-- Log Detail Modal -->
            <div x-show="selectedLog" 
                @click.self="selectedLog = null"
                class="fixed inset-0 z-[2000] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
                <div class="card-base rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col">
                    <!-- Header -->
                    <div class="p-6 border-b flex items-center justify-between">
                        <h3 class="font-black text-xl gradient-text">Log Details</h3>
                        <button @click="selectedLog = null" 
                            class="p-2 hover:bg-gray-100 rounded-lg">
                            <i data-lucide="x" class="w-5 h-5"></i>
                        </button>
                    </div>

                    <!-- Content -->
                    <div class="flex-1 overflow-auto p-6 space-y-4" x-show="selectedLog">
                        <div>
                            <label class="text-xs font-bold uppercase text-gray-500">Timestamp</label>
                            <p class="text-gray-800 font-medium mt-1" x-text="selectedLog && formatTimestamp(selectedLog.timestamp)"></p>
                        </div>
                        
                        <div>
                            <label class="text-xs font-bold uppercase text-gray-500">User ID</label>
                            <p class="text-gray-800 font-medium mt-1" x-text="selectedLog && (selectedLog.user_id || 'Anonymous')"></p>
                        </div>
                        
                        <div>
                            <label class="text-xs font-bold uppercase text-gray-500">Query</label>
                            <div class="mt-2 p-4 bg-purple-50 rounded-xl">
                                <p class="text-gray-800 font-medium whitespace-pre-wrap" x-text="selectedLog && selectedLog.query"></p>
                            </div>
                        </div>
                        
                        <div>
                            <label class="text-xs font-bold uppercase text-gray-500">Response</label>
                            <div class="mt-2 p-4 bg-orange-50 rounded-xl">
                                <p class="text-gray-800 whitespace-pre-wrap" x-text="selectedLog && selectedLog.response"></p>
                            </div>
                        </div>
                        
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="text-xs font-bold uppercase text-gray-500">Latency</label>
                                <p class="text-2xl font-black gradient-text mt-1" 
                                    x-text="selectedLog && selectedLog.latency + 'ms'"></p>
                            </div>
                            
                            <div x-show="selectedLog && selectedLog.context_used">
                                <label class="text-xs font-bold uppercase text-gray-500">Context Used</label>
                                <p class="text-2xl font-black text-green-600 mt-1">Yes</p>
                            </div>
                        </div>
                    </div>

                    <!-- Footer -->
                    <div class="p-6 border-t flex justify-end">
                        <button @click="selectedLog = null" 
                            class="px-6 py-3 gradient-purple-orange text-white rounded-xl font-bold hover:shadow-lg">
                            ปิด
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Re-initialize icons
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

        async loadLogs() {
            const token = localStorage.getItem('adminToken');
            
            try {
                const res = await fetch('/api/admin/stats', {
                    headers: { 'X-Admin-Token': token }
                });
                const data = await res.json();
                this.logs = data.recent_logs || [];
                this.filterLogs();
                
                setTimeout(() => lucide.createIcons(), 100);
            } catch (e) {
                console.error('Failed to load logs:', e);
            }
        },

        filterLogs() {
            let filtered = [...this.logs];

            // Search filter
            if (this.searchQuery) {
                const query = this.searchQuery.toLowerCase();
                filtered = filtered.filter(log => 
                    (log.query && log.query.toLowerCase().includes(query)) ||
                    (log.response && log.response.toLowerCase().includes(query)) ||
                    (log.user_id && log.user_id.toLowerCase().includes(query))
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
        },

        formatTimestamp(timestamp) {
            const date = new Date(timestamp);
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
            return (sum / this.logs.length).toFixed(0);
        },

        calculateSuccessRate() {
            if (this.logs.length === 0) return 100;
            const successCount = this.logs.filter(log => log.response && log.response.length > 0).length;
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
        }
    };
};