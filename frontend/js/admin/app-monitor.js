/**
 * Real-Time Monitor Module — Admin Live Activity Dashboard
 * Shows live user/bot interactions, queue status, and system health
 */
function initMonitorModule(app) {
    const container = document.getElementById('monitor-container');
    if (!container) return;

    const state = {
        queue: {},
        recentActivity: [],
        activeSessionCount: 0,
        faqAnalytics: {},
        liveFeed: [],       // real-time events from Socket.IO
        maxFeed: 100,
        autoRefresh: null,
        socket: null,
        connected: false,
        lastRefresh: null,
    };

    function getToken() {
        return app.adminToken || localStorage.getItem('adminToken') || '';
    }

    async function fetchStats() {
        try {
            const res = await fetch('/api/admin/monitor/stats', {
                headers: { 'X-Admin-Token': getToken() }
            });
            if (!res.ok) throw new Error('API error');
            const data = await res.json();
            state.queue = data.queue || {};
            state.recentActivity = data.recent_activity || [];
            state.activeSessionCount = data.active_sessions || 0;
            state.faqAnalytics = data.faq_analytics || {};
            state.lastRefresh = new Date();
            render();
        } catch (e) {
            console.error('Monitor fetch error:', e);
        }
    }

    function initSocket() {
        try {
            state.socket = io();
            state.socket.on('connect', () => { state.connected = true; render(); });
            state.socket.on('disconnect', () => { state.connected = false; render(); });

            // Live feed: user messages
            state.socket.on('admin_new_message', (data) => {
                addFeedItem({
                    type: 'user',
                    platform: data.platform || 'web',
                    uid: data.uid || '',
                    name: data.user_name || data.uid || 'Unknown',
                    text: data.text || '',
                    time: new Date(),
                });
            });

            // Live feed: bot responses
            state.socket.on('admin_bot_reply', (data) => {
                addFeedItem({
                    type: 'bot',
                    platform: data.platform || 'web',
                    uid: data.uid || '',
                    text: data.text || '',
                    time: new Date(),
                });
            });
        } catch (e) {
            console.error('Monitor socket error:', e);
        }
    }

    function addFeedItem(item) {
        state.liveFeed.unshift(item);
        if (state.liveFeed.length > state.maxFeed) {
            state.liveFeed = state.liveFeed.slice(0, state.maxFeed);
        }
        render();
    }

    function startAutoRefresh() {
        stopAutoRefresh();
        fetchStats();
        state.autoRefresh = setInterval(fetchStats, 5000);
    }

    function stopAutoRefresh() {
        if (state.autoRefresh) {
            clearInterval(state.autoRefresh);
            state.autoRefresh = null;
        }
    }

    function formatTime(d) {
        if (!d) return '--:--:--';
        const dt = d instanceof Date ? d : new Date(d);
        return dt.toLocaleTimeString('th-TH');
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str || '';
        return div.innerHTML;
    }

    function render() {
        const q = state.queue;
        const cur = q.current || {};
        const totals = q.totals || {};
        const peaks = q.peaks || {};
        const cfg = q.config || {};

        // Queue capacity percentage
        const used = (cur.pending || 0) + (cur.active || 0);
        const maxSize = cfg.max_size || 200;
        const capPct = maxSize > 0 ? Math.round((used / maxSize) * 100) : 0;
        const capColor = capPct > 75 ? 'var(--danger)' : capPct > 50 ? 'var(--warning)' : 'var(--success)';

        // Live feed HTML
        const feedHtml = state.liveFeed.length === 0
            ? `<div class="p-8 text-center"><p class="text-sm font-medium" style="color: var(--text-tertiary);">รอข้อความ...</p></div>`
            : state.liveFeed.map(item => {
                const isUser = item.type === 'user';
                const icon = isUser ? '👤' : '🤖';
                const label = isUser ? (item.name || 'User') : 'Bot พี่เร็ก';
                const platformBadge = item.platform === 'facebook'
                    ? '<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-600">FB</span>'
                    : '<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-purple-100 text-purple-600">Web</span>';
                const borderColor = isUser ? 'border-l-blue-500' : 'border-l-emerald-500';
                const textPreview = (item.text || '').replace(/\[Bot พี่เร็ก\]\s*/g, '').replace(/\[Admin\]:\s*/g, '');

                return `
                    <div class="p-3 border-l-4 ${borderColor} rounded-r-lg mb-2 transition-all" style="background: var(--bg-tertiary);">
                        <div class="flex items-center justify-between mb-1">
                            <div class="flex items-center gap-2">
                                <span class="text-sm">${icon}</span>
                                <span class="text-xs font-bold" style="color: var(--text-primary);">${escapeHtml(label)}</span>
                                ${platformBadge}
                            </div>
                            <span class="text-[10px] font-medium" style="color: var(--text-tertiary);">${formatTime(item.time)}</span>
                        </div>
                        <p class="text-sm truncate" style="color: var(--text-secondary);">${escapeHtml(textPreview.substring(0, 150))}</p>
                    </div>
                `;
            }).join('');

        // Recent activity (from audit logs)
        const activityHtml = state.recentActivity.slice(0, 20).map(log => {
            const latency = log.latency || 0;
            const latColor = latency < 3 ? 'var(--success)' : latency < 8 ? 'var(--warning)' : 'var(--danger)';
            return `
                <div class="flex items-center justify-between py-2 border-b" style="border-color: var(--border-secondary);">
                    <div class="flex-1 min-w-0 mr-4">
                        <p class="text-sm font-medium truncate" style="color: var(--text-primary);">${escapeHtml(log.input || '')}</p>
                        <p class="text-xs truncate" style="color: var(--text-tertiary);">${escapeHtml((log.output || '').substring(0, 80))}</p>
                    </div>
                    <div class="flex items-center gap-2 shrink-0">
                        <span class="px-1.5 py-0.5 rounded text-[10px] font-bold ${log.platform === 'facebook' ? 'bg-blue-100 text-blue-600' : 'bg-purple-100 text-purple-600'}">${log.platform || 'web'}</span>
                        <span class="text-xs font-bold" style="color: ${latColor};">${latency}s</span>
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = `
            <div class="animate-in">
                <div class="flex flex-col md:flex-row md:items-center justify-between mb-6 gap-4">
                    <div>
                        <h1 class="text-4xl md:text-5xl font-black gradient-text-cmu mb-2">Live Monitor</h1>
                        <p class="font-medium" style="color: var(--text-secondary);">
                            Real-time System Activity
                            <span class="inline-flex items-center gap-1 ml-2">
                                <span class="w-2 h-2 rounded-full ${state.connected ? 'bg-emerald-500' : 'bg-red-500'} animate-pulse"></span>
                                <span class="text-xs font-bold">${state.connected ? 'Connected' : 'Disconnected'}</span>
                            </span>
                        </p>
                    </div>
                    <div class="flex items-center gap-2">
                        <button onclick="window._monRefresh()" class="px-4 py-2 rounded-xl font-bold text-sm transition-all flex items-center gap-2"
                                style="background: var(--bg-tertiary); color: var(--text-secondary);">
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/></svg>
                            Refresh
                        </button>
                        <span class="text-xs font-medium" style="color: var(--text-tertiary);">
                            ${state.lastRefresh ? 'Updated ' + formatTime(state.lastRefresh) : ''}
                        </span>
                    </div>
                </div>

                <!-- Queue Stats Cards -->
                <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-6">
                    <div class="card-enterprise stat-card p-4 rounded-2xl shadow-lg text-center">
                        <p class="text-[10px] font-black uppercase tracking-wider mb-1" style="color: var(--text-tertiary);">Pending</p>
                        <h3 class="text-3xl font-black" style="color: var(--warning);">${cur.pending || 0}</h3>
                    </div>
                    <div class="card-enterprise stat-card p-4 rounded-2xl shadow-lg text-center">
                        <p class="text-[10px] font-black uppercase tracking-wider mb-1" style="color: var(--text-tertiary);">Active</p>
                        <h3 class="text-3xl font-black" style="color: var(--success);">${cur.active || 0}</h3>
                    </div>
                    <div class="card-enterprise stat-card p-4 rounded-2xl shadow-lg text-center">
                        <p class="text-[10px] font-black uppercase tracking-wider mb-1" style="color: var(--text-tertiary);">Processed</p>
                        <h3 class="text-3xl font-black" style="color: var(--cmu-purple);">${totals.processed || 0}</h3>
                    </div>
                    <div class="card-enterprise stat-card p-4 rounded-2xl shadow-lg text-center">
                        <p class="text-[10px] font-black uppercase tracking-wider mb-1" style="color: var(--text-tertiary);">Errors</p>
                        <h3 class="text-3xl font-black" style="color: var(--danger);">${totals.errors || 0}</h3>
                    </div>
                    <div class="card-enterprise stat-card p-4 rounded-2xl shadow-lg text-center">
                        <p class="text-[10px] font-black uppercase tracking-wider mb-1" style="color: var(--text-tertiary);">Throughput</p>
                        <h3 class="text-2xl font-black" style="color: var(--cmu-purple);">${q.throughput_per_min || 0}<span class="text-xs font-bold">/min</span></h3>
                    </div>
                    <div class="card-enterprise stat-card p-4 rounded-2xl shadow-lg text-center">
                        <p class="text-[10px] font-black uppercase tracking-wider mb-1" style="color: var(--text-tertiary);">Capacity</p>
                        <h3 class="text-2xl font-black" style="color: ${capColor};">${capPct}%</h3>
                        <div class="w-full h-1.5 rounded-full mt-1" style="background: var(--bg-tertiary);">
                            <div class="h-full rounded-full transition-all" style="width: ${capPct}%; background: ${capColor};"></div>
                        </div>
                    </div>
                </div>

                <!-- Queue Info Bar -->
                <div class="card-enterprise p-4 rounded-2xl shadow-lg mb-6 flex flex-wrap items-center gap-4 text-xs font-bold" style="color: var(--text-secondary);">
                    <span>Workers: <span style="color: var(--text-primary);">${cfg.num_workers || '-'}</span></span>
                    <span>Max Size: <span style="color: var(--text-primary);">${cfg.max_size || '-'}</span></span>
                    <span>Per User Limit: <span style="color: var(--text-primary);">${cfg.per_user_limit || '-'}</span></span>
                    <span>Timeout: <span style="color: var(--text-primary);">${cfg.request_timeout || '-'}s</span></span>
                    <span>Peak Pending: <span style="color: var(--warning);">${peaks.max_pending || 0}</span></span>
                    <span>Peak Active: <span style="color: var(--success);">${peaks.max_active || 0}</span></span>
                    <span>Uptime: <span style="color: var(--text-primary);">${q.uptime_seconds ? Math.round(q.uptime_seconds / 60) + ' min' : '-'}</span></span>
                    <span>Sessions: <span style="color: var(--cmu-purple);">${state.activeSessionCount}</span></span>
                    <span>FAQ KB: <span style="color: var(--cmu-purple);">${state.faqAnalytics.total_knowledge_base || 0}</span></span>
                    <span>Rejected: <span style="color: var(--danger);">${totals.rejected || 0}</span></span>
                    <span>Timeouts: <span style="color: var(--danger);">${totals.timeouts || 0}</span></span>
                </div>

                <!-- Two-column: Live Feed + Recent Activity -->
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <!-- Live Feed -->
                    <div class="card-enterprise rounded-2xl shadow-lg overflow-hidden flex flex-col" style="max-height: 600px;">
                        <div class="p-4 border-b flex items-center justify-between" style="border-color: var(--border-primary); background: var(--bg-tertiary);">
                            <div class="flex items-center gap-2">
                                <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                                <h3 class="font-bold text-sm" style="color: var(--text-primary);">Live Feed</h3>
                            </div>
                            <span class="text-[10px] font-bold" style="color: var(--text-tertiary);">${state.liveFeed.length} events</span>
                        </div>
                        <div class="flex-1 overflow-y-auto p-3 custom-scrollbar" style="background: var(--bg-secondary);">
                            ${feedHtml}
                        </div>
                    </div>

                    <!-- Recent Activity (from audit logs) -->
                    <div class="card-enterprise rounded-2xl shadow-lg overflow-hidden flex flex-col" style="max-height: 600px;">
                        <div class="p-4 border-b flex items-center justify-between" style="border-color: var(--border-primary); background: var(--bg-tertiary);">
                            <h3 class="font-bold text-sm" style="color: var(--text-primary);">Recent Activity (Audit Log)</h3>
                            <span class="text-[10px] font-bold" style="color: var(--text-tertiary);">${state.recentActivity.length} entries</span>
                        </div>
                        <div class="flex-1 overflow-y-auto p-4 custom-scrollbar" style="background: var(--bg-secondary);">
                            ${activityHtml || '<div class="p-8 text-center"><p class="text-sm" style="color: var(--text-tertiary);">No activity yet</p></div>'}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    window._monRefresh = () => fetchStats();

    app.monitor = {
        render,
        start() { initSocket(); startAutoRefresh(); },
        stop() { stopAutoRefresh(); },
    };
}
