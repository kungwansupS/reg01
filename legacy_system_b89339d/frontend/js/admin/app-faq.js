/**
 * FAQ Manager Module — Admin FAQ Editor
 * CRUD operations for FAQ knowledge base
 */
function initFaqModule(app) {
    const container = document.getElementById('faq-container');
    if (!container) return;

    const state = {
        entries: [],
        total: 0,
        searchQuery: '',
        showExpired: false,
        loading: false,
        editingEntry: null,
        showAddForm: false,
        form: { question: '', answer: '', ttl_seconds: 86400 },
    };

    function getToken() {
        return app.adminToken || localStorage.getItem('adminToken') || '';
    }

    async function apiCall(url, method = 'GET', body = null) {
        const opts = { method, headers: { 'X-Admin-Token': getToken() } };
        if (body instanceof FormData) {
            opts.body = body;
        } else if (body) {
            opts.headers['Content-Type'] = 'application/json';
            opts.body = JSON.stringify(body);
        }
        const res = await fetch(url, opts);
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `API error ${res.status}`);
        }
        return res.json();
    }

    async function loadEntries() {
        state.loading = true;
        render();
        try {
            const params = new URLSearchParams({
                limit: '500',
                query: state.searchQuery,
                include_expired: state.showExpired,
            });
            const data = await apiCall(`/api/admin/faq?${params}`);
            state.entries = data.items || [];
            state.total = data.total || 0;
        } catch (e) {
            console.error('FAQ load error:', e);
            app.showNotification('โหลด FAQ ไม่สำเร็จ: ' + e.message, 'error');
        }
        state.loading = false;
        render();
    }

    async function saveEntry() {
        const form = new FormData();
        form.append('question', state.form.question.trim());
        form.append('answer', state.form.answer.trim());
        form.append('source', 'admin');
        if (state.form.ttl_seconds) form.append('ttl_seconds', state.form.ttl_seconds);
        if (state.editingEntry) {
            form.append('original_question', state.editingEntry.question);
        }

        try {
            await apiCall('/api/admin/faq', 'PUT', form);
            app.showNotification('บันทึก FAQ สำเร็จ', 'success');
            state.editingEntry = null;
            state.showAddForm = false;
            state.form = { question: '', answer: '', ttl_seconds: 86400 };
            await loadEntries();
        } catch (e) {
            app.showNotification('บันทึกไม่สำเร็จ: ' + e.message, 'error');
        }
    }

    async function deleteEntry(question) {
        if (!confirm(`ลบ FAQ: "${question.substring(0, 50)}..." ?`)) return;
        try {
            await apiCall(`/api/admin/faq?question=${encodeURIComponent(question)}`, 'DELETE');
            app.showNotification('ลบ FAQ สำเร็จ', 'success');
            await loadEntries();
        } catch (e) {
            app.showNotification('ลบไม่สำเร็จ: ' + e.message, 'error');
        }
    }

    async function purgeExpired() {
        if (!confirm('ลบ FAQ ที่หมดอายุทั้งหมด?')) return;
        try {
            const result = await apiCall('/api/admin/faq/purge-expired', 'POST');
            app.showNotification(`ลบ FAQ หมดอายุแล้ว ${result.removed} รายการ`, 'success');
            await loadEntries();
        } catch (e) {
            app.showNotification('ไม่สำเร็จ: ' + e.message, 'error');
        }
    }

    async function startEdit(entry) {
        // Fetch full entry (answer_preview may be truncated)
        try {
            const full = await apiCall(`/api/admin/faq/entry?question=${encodeURIComponent(entry.question)}`);
            state.editingEntry = entry;
            state.form = {
                question: full.question || entry.question,
                answer: full.answer || entry.answer_preview || '',
                ttl_seconds: full.ttl_seconds || entry.ttl_seconds || 86400,
            };
        } catch (e) {
            state.editingEntry = entry;
            state.form = {
                question: entry.question,
                answer: entry.answer_preview || '',
                ttl_seconds: entry.ttl_seconds || 86400,
            };
        }
        state.showAddForm = true;
        render();
        // Scroll to form
        setTimeout(() => {
            const formEl = container.querySelector('#faq-edit-form');
            if (formEl) formEl.scrollIntoView({ behavior: 'smooth' });
        }, 100);
    }

    function startAdd() {
        state.editingEntry = null;
        state.form = { question: '', answer: '', ttl_seconds: 86400 };
        state.showAddForm = true;
        render();
    }

    function cancelEdit() {
        state.editingEntry = null;
        state.showAddForm = false;
        state.form = { question: '', answer: '', ttl_seconds: 86400 };
        render();
    }

    function formatDate(iso) {
        if (!iso) return '-';
        try {
            const d = new Date(iso);
            return d.toLocaleString('th-TH', { dateStyle: 'short', timeStyle: 'short' });
        } catch { return iso; }
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function render() {
        const rows = state.entries.map((e, i) => `
            <tr class="faq-row" style="border-bottom: 1px solid var(--border-secondary);">
                <td class="px-4 py-3 text-sm font-medium" style="color: var(--text-primary); max-width: 280px;">
                    <div class="truncate" title="${escapeHtml(e.question)}">${escapeHtml(e.question)}</div>
                </td>
                <td class="px-4 py-3 text-sm" style="color: var(--text-secondary); max-width: 380px;">
                    <div class="truncate" title="${escapeHtml(e.answer_preview)}">${escapeHtml(e.answer_preview)}</div>
                </td>
                <td class="px-4 py-3 text-center text-sm font-bold" style="color: var(--cmu-purple);">${e.count || 0}</td>
                <td class="px-4 py-3 text-center">
                    <span class="px-2 py-0.5 rounded-full text-xs font-bold ${e.source === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'}">${escapeHtml(e.source || 'rag')}</span>
                    ${e.expired ? '<span class="ml-1 px-2 py-0.5 rounded-full text-xs font-bold bg-red-100 text-red-600">expired</span>' : ''}
                </td>
                <td class="px-4 py-3 text-xs text-center" style="color: var(--text-tertiary);">${formatDate(e.last_updated)}</td>
                <td class="px-4 py-3 text-center">
                    <div class="flex items-center justify-center gap-1">
                        <button onclick="window._faqEdit(${i})" class="p-1.5 rounded-lg hover:bg-purple-100 transition-colors" title="แก้ไข">
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--cmu-purple);"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>
                        </button>
                        <button onclick="window._faqDelete('${escapeHtml(e.question).replace(/'/g, "\\'")}')" class="p-1.5 rounded-lg hover:bg-red-100 transition-colors" title="ลบ">
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--danger);"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');

        const formHtml = state.showAddForm ? `
            <div id="faq-edit-form" class="card-enterprise p-6 rounded-2xl shadow-lg mb-6 animate-in" style="border: 2px solid var(--cmu-purple);">
                <h3 class="font-bold text-lg mb-4" style="color: var(--cmu-purple);">
                    ${state.editingEntry ? '✏️ แก้ไข FAQ' : '➕ เพิ่ม FAQ ใหม่'}
                </h3>
                <div class="space-y-4">
                    <div>
                        <label class="block text-sm font-bold mb-1" style="color: var(--text-secondary);">คำถาม</label>
                        <input id="faq-q" type="text" value="${escapeHtml(state.form.question)}" 
                               class="w-full px-4 py-2.5 rounded-xl border-2 text-sm font-medium focus:ring-2 focus:ring-purple-500 outline-none"
                               style="background: var(--bg-tertiary); color: var(--text-primary); border-color: var(--border-primary);"
                               placeholder="พิมพ์คำถาม...">
                    </div>
                    <div>
                        <label class="block text-sm font-bold mb-1" style="color: var(--text-secondary);">คำตอบ</label>
                        <textarea id="faq-a" rows="4"
                                  class="w-full px-4 py-2.5 rounded-xl border-2 text-sm font-medium focus:ring-2 focus:ring-purple-500 outline-none resize-y"
                                  style="background: var(--bg-tertiary); color: var(--text-primary); border-color: var(--border-primary);"
                                  placeholder="พิมพ์คำตอบ...">${escapeHtml(state.form.answer)}</textarea>
                    </div>
                    <div class="flex items-center gap-4">
                        <div>
                            <label class="block text-sm font-bold mb-1" style="color: var(--text-secondary);">TTL (วินาที)</label>
                            <input id="faq-ttl" type="number" value="${state.form.ttl_seconds}" min="60" max="31536000"
                                   class="w-40 px-4 py-2.5 rounded-xl border-2 text-sm font-medium focus:ring-2 focus:ring-purple-500 outline-none"
                                   style="background: var(--bg-tertiary); color: var(--text-primary); border-color: var(--border-primary);">
                        </div>
                        <div class="flex-1"></div>
                        <button onclick="window._faqSave()" class="px-6 py-2.5 rounded-xl gradient-cmu text-white font-bold text-sm shadow-lg hover:shadow-xl transition-all">
                            💾 บันทึก
                        </button>
                        <button onclick="window._faqCancel()" class="px-6 py-2.5 rounded-xl font-bold text-sm transition-all" 
                                style="background: var(--bg-tertiary); color: var(--text-secondary);">
                            ยกเลิก
                        </button>
                    </div>
                </div>
            </div>
        ` : '';

        container.innerHTML = `
            <div class="animate-in">
                <div class="flex flex-col md:flex-row md:items-center justify-between mb-6 gap-4">
                    <div>
                        <h1 class="text-4xl md:text-5xl font-black gradient-text-cmu mb-2">FAQ Manager</h1>
                        <p class="font-medium" style="color: var(--text-secondary);">จัดการฐานความรู้ FAQ (${state.total} รายการ)</p>
                    </div>
                    <div class="flex items-center gap-2">
                        <button onclick="window._faqAdd()" class="px-4 py-2 rounded-xl gradient-cmu text-white font-bold text-sm shadow-lg hover:shadow-xl transition-all flex items-center gap-2">
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                            เพิ่ม FAQ
                        </button>
                        <button onclick="window._faqPurge()" class="px-4 py-2 rounded-xl font-bold text-sm transition-all flex items-center gap-2"
                                style="background: var(--bg-tertiary); color: var(--danger);">
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/></svg>
                            ลบ Expired
                        </button>
                        <button onclick="window._faqRefresh()" class="px-4 py-2 rounded-xl font-bold text-sm transition-all flex items-center gap-2"
                                style="background: var(--bg-tertiary); color: var(--text-secondary);">
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/></svg>
                            รีเฟรช
                        </button>
                    </div>
                </div>

                <!-- Search -->
                <div class="card-enterprise p-4 rounded-2xl shadow-lg mb-6 flex items-center gap-4">
                    <div class="relative flex-1">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="absolute left-3 top-2.5" style="color: var(--text-tertiary);"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                        <input id="faq-search" type="text" value="${escapeHtml(state.searchQuery)}"
                               placeholder="ค้นหาคำถามหรือคำตอบ..."
                               class="w-full pl-10 pr-4 py-2 rounded-xl border-none text-sm font-medium focus:ring-2 focus:ring-purple-500 outline-none"
                               style="background: var(--bg-tertiary); color: var(--text-primary);">
                    </div>
                    <label class="flex items-center gap-2 cursor-pointer text-sm font-medium" style="color: var(--text-secondary);">
                        <input type="checkbox" id="faq-show-expired" ${state.showExpired ? 'checked' : ''} 
                               class="rounded" onchange="window._faqToggleExpired(this.checked)">
                        แสดง expired
                    </label>
                </div>

                ${formHtml}

                <!-- Table -->
                <div class="card-enterprise rounded-2xl shadow-lg overflow-hidden">
                    ${state.loading ? `
                        <div class="p-12 text-center">
                            <div class="animate-spin w-8 h-8 border-4 border-purple-500 border-t-transparent rounded-full mx-auto mb-4"></div>
                            <p class="text-sm font-medium" style="color: var(--text-tertiary);">กำลังโหลด...</p>
                        </div>
                    ` : state.entries.length === 0 ? `
                        <div class="p-12 text-center">
                            <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="mx-auto mb-4" style="color: var(--border-primary);"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/></svg>
                            <p class="font-bold" style="color: var(--text-tertiary);">ไม่พบ FAQ</p>
                        </div>
                    ` : `
                        <div class="overflow-x-auto">
                            <table class="w-full">
                                <thead>
                                    <tr style="background: var(--bg-tertiary); border-bottom: 2px solid var(--border-primary);">
                                        <th class="px-4 py-3 text-left text-xs font-black uppercase tracking-wider" style="color: var(--text-tertiary);">คำถาม</th>
                                        <th class="px-4 py-3 text-left text-xs font-black uppercase tracking-wider" style="color: var(--text-tertiary);">คำตอบ</th>
                                        <th class="px-4 py-3 text-center text-xs font-black uppercase tracking-wider" style="color: var(--text-tertiary);">Hits</th>
                                        <th class="px-4 py-3 text-center text-xs font-black uppercase tracking-wider" style="color: var(--text-tertiary);">Source</th>
                                        <th class="px-4 py-3 text-center text-xs font-black uppercase tracking-wider" style="color: var(--text-tertiary);">Updated</th>
                                        <th class="px-4 py-3 text-center text-xs font-black uppercase tracking-wider" style="color: var(--text-tertiary); width: 80px;">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>${rows}</tbody>
                            </table>
                        </div>
                    `}
                </div>
            </div>
        `;

        // Bind search input
        const searchEl = container.querySelector('#faq-search');
        if (searchEl) {
            let debounce;
            searchEl.addEventListener('input', (e) => {
                clearTimeout(debounce);
                debounce = setTimeout(() => {
                    state.searchQuery = e.target.value;
                    loadEntries();
                }, 400);
            });
        }
    }

    // Global handlers
    window._faqEdit = (i) => startEdit(state.entries[i]);
    window._faqDelete = (q) => deleteEntry(q);
    window._faqAdd = () => startAdd();
    window._faqCancel = () => cancelEdit();
    window._faqRefresh = () => loadEntries();
    window._faqPurge = () => purgeExpired();
    window._faqToggleExpired = (v) => { state.showExpired = v; loadEntries(); };
    window._faqSave = () => {
        const q = document.getElementById('faq-q');
        const a = document.getElementById('faq-a');
        const t = document.getElementById('faq-ttl');
        if (q) state.form.question = q.value;
        if (a) state.form.answer = a.value;
        if (t) state.form.ttl_seconds = parseInt(t.value) || 86400;
        saveEntry();
    };

    app.faq = { render, loadEntries };
    render();
}
