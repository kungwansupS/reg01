/**
 * Enterprise File Explorer Module
 * CMU Innovation Platform - File Management System
 */

// Global File System State
window.filesState = {
    fileSystem: { root: 'data', current_path: '', entries: [] },
    selectedPaths: [],
    searchQuery: '',
    dragging: false,
    uploadStatus: { total: 0, done: 0 },
    processing: false,
    preview: { 
        open: false, 
        type: 'txt', 
        fileName: '', 
        content: '', 
        url: '', 
        loading: false, 
        saveLoading: false, 
        entry: null 
    }
};

/**
 * Load Files Tab Content
 */
window.loadFilesTab = function() {
    const container = document.getElementById('files-container');
    if (!container) return;
    
    container.innerHTML = `
        <div x-data="filesModule()" x-init="init()" class="animate-in">
            <!-- Header -->
            <div class="mb-8">
                <h1 class="text-4xl md:text-5xl font-black gradient-text-cmu mb-2">File Explorer</h1>
                <p class="font-medium" style="color: var(--text-secondary);">Document Management & RAG System</p>
            </div>

            <!-- Control Panel -->
            <div class="card-enterprise p-6 rounded-2xl shadow-lg mb-6">
                <div class="flex flex-col md:flex-row justify-between gap-4 mb-6">
                    <!-- Root Selector -->
                    <div class="flex items-center gap-2 p-1 rounded-xl" style="background-color: var(--bg-tertiary);">
                        <button 
                            @click="switchRoot('data')" 
                            :class="fileSystem.root === 'data' ? 'active-root' : ''"
                            class="px-6 py-2 rounded-lg font-bold text-sm transition-all"
                            :style="fileSystem.root === 'data' ? 'background-color: var(--bg-secondary); color: var(--cmu-purple); box-shadow: 0 2px 8px rgba(0,0,0,0.1);' : 'color: var(--text-secondary);'">
                            Data (PDF)
                        </button>
                        <button 
                            @click="switchRoot('uploads')" 
                            :class="fileSystem.root === 'uploads' ? 'active-root' : ''"
                            class="px-6 py-2 rounded-lg font-bold text-sm transition-all"
                            :style="fileSystem.root === 'uploads' ? 'background-color: var(--bg-secondary); color: var(--cmu-purple); box-shadow: 0 2px 8px rgba(0,0,0,0.1);' : 'color: var(--text-secondary);'">
                            RAG (TXT)
                        </button>
                    </div>

                    <!-- Action Buttons -->
                    <div class="flex items-center gap-2">
                        <button 
                            @click="createNewFolder()" 
                            class="px-4 py-2 rounded-lg font-bold text-sm btn-enterprise flex items-center gap-2 text-white"
                            style="background-color: var(--cmu-purple);">
                            <i data-lucide="folder-plus" class="w-4 h-4"></i>
                            <span class="hidden md:inline">New Folder</span>
                        </button>
                        <label class="px-4 py-2 rounded-lg font-bold text-sm btn-enterprise cursor-pointer flex items-center gap-2 text-white"
                               style="background-color: var(--accent-gold);">
                            <i data-lucide="upload" class="w-4 h-4"></i>
                            <span class="hidden md:inline">Upload</span>
                            <input type="file" @change="uploadMultipleFiles" multiple class="hidden">
                        </label>
                        <button 
                            @click="processRAG()" 
                            :disabled="processing" 
                            class="px-4 py-2 rounded-lg font-bold text-sm btn-enterprise disabled:opacity-50 flex items-center gap-2 text-white"
                            style="background-color: var(--success);">
                            <i data-lucide="refresh-cw" class="w-4 h-4" :class="{'animate-spin': processing}"></i>
                            <span class="hidden md:inline">Sync RAG</span>
                        </button>
                    </div>
                </div>

                <!-- Breadcrumb with Back Button -->
                <div class="flex items-center gap-4 mb-4">
                    <!-- Back Button -->
                    <button 
                        x-show="fileSystem.current_path !== ''"
                        @click="navigateBack()" 
                        class="p-2 rounded-lg font-bold hover:bg-opacity-10 flex items-center gap-2 transition-all shrink-0"
                        style="background-color: var(--bg-tertiary); color: var(--cmu-purple);"
                        title="ย้อนกลับ">
                        <i data-lucide="arrow-left" class="w-5 h-5"></i>
                        <span class="hidden md:inline">ย้อนกลับ</span>
                    </button>
                    
                    <!-- Breadcrumb Path -->
                    <div class="flex items-center gap-2 text-sm flex-wrap" style="color: var(--text-tertiary);">
                        <button 
                            @click="navigate('')" 
                            class="font-bold hover:underline flex items-center gap-1 transition-colors"
                            style="color: var(--cmu-purple);">
                            <i data-lucide="home" class="w-4 h-4"></i>
                            <span>Root</span>
                        </button>
                        <template x-for="(part, index) in fileSystem.current_path.split('/').filter(p => p)" :key="index">
                            <div class="flex items-center gap-2">
                                <i data-lucide="chevron-right" class="w-4 h-4"></i>
                                <button 
                                    @click="navigateByParts(index)" 
                                    class="font-bold hover:underline transition-colors"
                                    style="color: var(--cmu-purple);"
                                    x-text="part">
                                </button>
                            </div>
                        </template>
                    </div>
                </div>

                <!-- Search Bar -->
                <div class="relative">
                    <i data-lucide="search" class="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2" style="color: var(--text-tertiary);"></i>
                    <input 
                        type="text" 
                        x-model="searchQuery" 
                        placeholder="ค้นหาไฟล์หรือโฟลเดอร์..."
                        class="w-full pl-12 pr-4 py-3 rounded-xl border-2 transition-all">
                </div>
            </div>

            <!-- Bulk Actions Bar -->
            <div 
                x-show="selectedPaths.length > 0" 
                class="card-enterprise p-4 rounded-xl shadow-lg mb-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-4"
                style="border-left: 4px solid var(--cmu-purple);">
                <div class="flex items-center gap-3">
                    <div class="p-2 rounded-lg" style="background-color: rgba(81, 45, 109, 0.1);">
                        <i data-lucide="check-square" class="w-5 h-5" style="color: var(--cmu-purple);"></i>
                    </div>
                    <span class="font-bold" style="color: var(--text-primary);">
                        เลือกไว้ <span x-text="selectedPaths.length"></span> รายการ
                    </span>
                </div>
                <div class="flex items-center gap-2">
                    <button 
                        @click="bulkDelete()" 
                        class="px-4 py-2 rounded-lg font-bold text-sm btn-enterprise flex items-center gap-2 text-white"
                        style="background-color: var(--danger);">
                        <i data-lucide="trash-2" class="w-4 h-4"></i>
                        <span>ลบที่เลือก</span>
                    </button>
                    <button 
                        @click="selectedPaths = []" 
                        class="px-4 py-2 rounded-lg font-bold text-sm transition-all"
                        style="background-color: var(--bg-tertiary); color: var(--text-secondary);">
                        <i data-lucide="x" class="w-4 h-4"></i>
                        <span class="hidden md:inline">ยกเลิก</span>
                    </button>
                </div>
            </div>

            <!-- Upload Progress -->
            <div x-show="uploadStatus.total > 0 && uploadStatus.done < uploadStatus.total" 
                 class="card-enterprise p-4 rounded-xl shadow-lg mb-6"
                 style="border-left: 4px solid var(--cmu-purple);">
                <div class="flex justify-between mb-2 font-bold text-sm" style="color: var(--cmu-purple);">
                    <span>Uploading files...</span>
                    <span x-text="Math.round((uploadStatus.done/uploadStatus.total)*100)+'%'"></span>
                </div>
                <div class="w-full h-2 rounded-full overflow-hidden" style="background-color: var(--bg-tertiary);">
                    <div class="gradient-cmu h-2 transition-all duration-300" 
                         :style="'width:'+(uploadStatus.done/uploadStatus.total*100)+'%'">
                    </div>
                </div>
            </div>

            <!-- File Table -->
            <div class="card-enterprise rounded-2xl shadow-lg overflow-hidden">
                <div class="overflow-x-auto">
                    <table class="w-full table-enterprise">
                        <thead style="background-color: var(--bg-tertiary); border-bottom: 1px solid var(--border-primary);">
                            <tr>
                                <th class="p-4 w-12">
                                    <input 
                                        type="checkbox" 
                                        @change="toggleSelectAll()" 
                                        :checked="isAllSelected()" 
                                        class="w-5 h-5 rounded">
                                </th>
                                <th class="p-4 font-bold text-sm text-left" style="color: var(--text-secondary);">ชื่อ</th>
                                <th class="p-4 font-bold text-sm text-left w-32" style="color: var(--text-secondary);">ขนาด</th>
                                <th class="p-4 font-bold text-sm text-right w-40" style="color: var(--text-secondary);">จัดการ</th>
                            </tr>
                        </thead>
                        <tbody style="border-top: 1px solid var(--border-secondary);">
                            <template x-for="entry in filteredEntries" :key="entry.path">
                                <tr class="group transition-colors border-b hover:bg-opacity-50" 
                                    style="border-color: var(--border-secondary);"
                                    :style="'background-color: transparent;'">
                                    <td class="p-4">
                                        <input 
                                            type="checkbox" 
                                            :value="entry.path" 
                                            x-model="selectedPaths" 
                                            @click.stop
                                            class="w-5 h-5 rounded">
                                    </td>
                                    <td class="p-4">
                                        <div 
                                            class="flex items-center gap-3 cursor-pointer" 
                                            @click="entry.type === 'dir' ? navigate(entry.path) : previewFile(entry)">
                                            <div 
                                                class="p-2 rounded-lg transition-transform"
                                                :style="entry.type === 'dir' ? 'background-color: rgba(81, 45, 109, 0.1); color: var(--cmu-purple);' : 'background-color: rgba(196, 160, 82, 0.1); color: var(--accent-gold);'">
                                                <i :data-lucide="entry.type === 'dir' ? 'folder' : 'file-text'" class="w-5 h-5"></i>
                                            </div>
                                            <span class="font-semibold transition-colors" style="color: var(--text-primary);" x-text="entry.name"></span>
                                        </div>
                                    </td>
                                    <td class="p-4 text-sm" style="color: var(--text-secondary);" x-text="entry.size"></td>
                                    <td class="p-4 text-right">
                                        <div class="flex items-center justify-end gap-2">
                                            <button 
                                                @click.stop="renameItem(entry)" 
                                                class="p-2 rounded-lg transition-all hover:scale-110"
                                                style="background-color: rgba(81, 45, 109, 0.1); color: var(--cmu-purple);"
                                                title="เปลี่ยนชื่อ">
                                                <i data-lucide="edit-3" class="w-4 h-4"></i>
                                            </button>
                                            <button 
                                                @click.stop="deleteItem(entry)" 
                                                class="p-2 rounded-lg transition-all hover:scale-110"
                                                style="background-color: rgba(255, 59, 48, 0.1); color: var(--danger);"
                                                title="ลบ">
                                                <i data-lucide="trash-2" class="w-4 h-4"></i>
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            </template>
                        </tbody>
                    </table>
                </div>

                <!-- Empty State -->
                <div x-show="filteredEntries.length === 0" class="text-center py-20">
                    <i data-lucide="folder-open" class="w-16 h-16 mx-auto mb-4" style="color: var(--border-primary);"></i>
                    <p class="font-semibold" style="color: var(--text-tertiary);">ไม่พบไฟล์หรือโฟลเดอร์</p>
                </div>
            </div>

            <!-- Preview Modal -->
            <div 
                x-show="preview.open" 
                x-cloak 
                class="preview-modal fixed inset-0 z-[2000] flex items-center justify-center p-4"
                style="background-color: var(--overlay);">
                <div class="preview-content card-enterprise rounded-3xl shadow-2xl w-full max-w-5xl h-[85vh] flex flex-col overflow-hidden animate-in">
                    <!-- Modal Header -->
                    <div class="p-6 border-b flex justify-between items-center" style="border-color: var(--border-primary);">
                        <div class="flex items-center gap-3">
                            <div class="p-2 rounded-lg" style="background-color: var(--bg-tertiary);">
                                <i :data-lucide="preview.type === 'pdf' ? 'file' : 'file-text'" class="w-5 h-5" style="color: var(--cmu-purple);"></i>
                            </div>
                            <span class="font-bold" style="color: var(--text-primary);" x-text="preview.fileName"></span>
                        </div>
                        <button 
                            @click="closePreview()" 
                            class="p-2 rounded-xl transition-all hover:bg-opacity-10">
                            <i data-lucide="x" class="w-6 h-6" style="color: var(--text-secondary);"></i>
                        </button>
                    </div>

                    <!-- Modal Content -->
                    <div class="flex-1 overflow-hidden relative" style="background-color: var(--bg-tertiary);">
                        <!-- Loading State -->
                        <div x-show="preview.loading" class="h-full flex flex-col items-center justify-center">
                            <div class="w-10 h-10 border-4 rounded-full animate-spin" 
                                 style="border-color: var(--bg-tertiary); border-top-color: var(--cmu-purple);"></div>
                            <p class="mt-4 font-medium" style="color: var(--text-secondary);">Loading...</p>
                        </div>

                        <!-- Text Editor -->
                        <textarea 
                            x-show="!preview.loading && preview.type === 'txt'" 
                            x-model="preview.content" 
                            class="w-full h-full p-6 font-mono text-sm outline-none resize-none"
                            style="background-color: var(--bg-tertiary); color: var(--text-secondary);">
                        </textarea>

                        <!-- PDF Viewer -->
                        <iframe 
                            x-show="!preview.loading && preview.type === 'pdf'" 
                            :src="preview.url" 
                            class="w-full h-full border-none">
                        </iframe>
                    </div>

                    <!-- Modal Footer -->
                    <div class="p-6 border-t flex justify-end gap-3" style="border-color: var(--border-primary);">
                        <button 
                            @click="closePreview()" 
                            class="px-6 py-2 font-bold rounded-lg transition-all"
                            style="background-color: var(--bg-tertiary); color: var(--text-primary);">
                            ปิด
                        </button>
                        <button 
                            x-show="preview.type === 'txt'" 
                            @click="saveContent()" 
                            :disabled="preview.saveLoading" 
                            class="px-6 py-2 gradient-cmu text-white font-bold rounded-lg btn-enterprise disabled:opacity-50">
                            <span x-text="preview.saveLoading ? 'กำลังบันทึก...' : 'บันทึก'"></span>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    setTimeout(() => lucide.createIcons(), 50);
};

/**
 * Files Module for Alpine.js
 */
window.filesModule = function() {
    return {
        ...window.filesState,
        
        init() { 
            this.loadFiles(); 
        },

        get filteredEntries() { 
            return this.fileSystem.entries.filter(e => 
                e.name.toLowerCase().includes(this.searchQuery.toLowerCase())
            ); 
        },

        async switchRoot(root) { 
            this.fileSystem.root = root; 
            this.fileSystem.current_path = ''; 
            this.selectedPaths = [];
            await this.loadFiles(); 
        },

        async navigate(path) { 
            this.fileSystem.current_path = path;
            this.selectedPaths = [];
            await this.loadFiles(); 
        },

        navigateBack() {
            const parts = this.fileSystem.current_path.split('/').filter(p => p);
            if (parts.length > 0) {
                parts.pop();
                this.navigate(parts.join('/'));
            }
        },

        navigateByParts(index) { 
            this.navigate(
                this.fileSystem.current_path
                    .split('/')
                    .filter(p => p)
                    .slice(0, index + 1)
                    .join('/')
            ); 
        },

        async loadFiles() {
            const token = localStorage.getItem('adminToken');
            try {
                const url = `/api/admin/files?root=${this.fileSystem.root}&subdir=${encodeURIComponent(this.fileSystem.current_path)}`;
                const res = await fetch(url, { 
                    headers: { 'X-Admin-Token': token } 
                });
                const data = await res.json();
                this.fileSystem.entries = data.entries || [];
                setTimeout(() => lucide.createIcons(), 50);
            } catch (e) { 
                console.error('Load files failed', e); 
            }
        },

        toggleSelectAll() { 
            this.selectedPaths = this.isAllSelected() 
                ? [] 
                : this.filteredEntries.map(e => e.path); 
        },

        isAllSelected() { 
            return this.filteredEntries.length > 0 && 
                   this.selectedPaths.length === this.filteredEntries.length; 
        },

        async uploadMultipleFiles(e) { 
            await this.executeUploadBatch(Array.from(e.target.files)); 
            e.target.value = ''; 
        },

        async executeUploadBatch(items) {
            const token = localStorage.getItem('adminToken');
            this.uploadStatus = { total: items.length, done: 0 };
            
            for (const f of items) {
                const fd = new FormData();
                fd.append('file', f); 
                fd.append('root', this.fileSystem.root); 
                fd.append('target_dir', this.fileSystem.current_path);
                
                try {
                    await fetch('/api/admin/upload', { 
                        method: 'POST', 
                        headers: { 'X-Admin-Token': token }, 
                        body: fd 
                    });
                } catch(e) { 
                    console.error('Upload failed', e); 
                }
                
                this.uploadStatus.done++;
            }
            
            await this.loadFiles();
        },

        async previewFile(entry) {
            this.preview.open = true; 
            this.preview.fileName = entry.name; 
            this.preview.loading = true; 
            this.preview.entry = entry;
            this.preview.type = entry.ext === '.pdf' ? 'pdf' : 'txt';
            
            const url = `/api/admin/view?root=${this.fileSystem.root}&path=${encodeURIComponent(entry.path)}`;
            
            try {
                const res = await fetch(url, { 
                    headers: { 'X-Admin-Token': localStorage.getItem('adminToken') } 
                });
                const blob = await res.blob();
                
                if (this.preview.type === 'pdf') {
                    if (this.preview.url) URL.revokeObjectURL(this.preview.url);
                    this.preview.url = URL.createObjectURL(blob);
                } else { 
                    this.preview.content = await blob.text(); 
                }
            } catch(e) { 
                alert('โหลดไฟล์ไม่สำเร็จ'); 
            } finally { 
                this.preview.loading = false; 
                setTimeout(() => lucide.createIcons(), 50); 
            }
        },

        async saveContent() {
            this.preview.saveLoading = true;
            const fd = new FormData();
            fd.append('root', this.fileSystem.root); 
            fd.append('path', this.preview.entry.path); 
            fd.append('content', this.preview.content);
            
            try {
                await fetch('/api/admin/edit', { 
                    method: 'POST', 
                    headers: { 'X-Admin-Token': localStorage.getItem('adminToken') }, 
                    body: fd 
                });
                alert('บันทึกสำเร็จ!');
            } catch(e) { 
                alert('บันทึกไม่สำเร็จ'); 
            } finally { 
                this.preview.saveLoading = false; 
            }
        },

        closePreview() { 
            this.preview.open = false; 
            if (this.preview.url) URL.revokeObjectURL(this.preview.url); 
        },

        async createNewFolder() {
            const name = prompt("ระบุชื่อโฟลเดอร์:"); 
            if (!name) return;
            
            const fd = new FormData(); 
            fd.append('root', this.fileSystem.root); 
            fd.append('path', this.fileSystem.current_path); 
            fd.append('name', name);
            
            try {
                await fetch('/api/admin/mkdir', { 
                    method: 'POST', 
                    headers: { 'X-Admin-Token': localStorage.getItem('adminToken') }, 
                    body: fd 
                });
                await this.loadFiles();
            } catch(e) {
                alert('สร้างโฟลเดอร์ไม่สำเร็จ');
            }
        },

        async renameItem(entry) {
            const newName = prompt(`เปลี่ยนชื่อ "${entry.name}" เป็น:`, entry.name); 
            if (!newName || newName === entry.name) return;
            
            const fd = new FormData(); 
            fd.append('root', this.fileSystem.root); 
            fd.append('old_path', entry.path); 
            fd.append('new_name', newName);
            
            try {
                await fetch('/api/admin/rename', { 
                    method: 'POST', 
                    headers: { 'X-Admin-Token': localStorage.getItem('adminToken') }, 
                    body: fd 
                });
                await this.loadFiles();
            } catch(e) {
                alert('เปลี่ยนชื่อไม่สำเร็จ');
            }
        },

        async deleteItem(entry) {
            if (!confirm(`ต้องการลบ "${entry.name}"?`)) return;
            
            try {
                await fetch(`/api/admin/files?root=${this.fileSystem.root}&paths=${encodeURIComponent(JSON.stringify([entry.path]))}`, { 
                    method: 'DELETE', 
                    headers: { 'X-Admin-Token': localStorage.getItem('adminToken') } 
                });
                await this.loadFiles();
            } catch(e) {
                alert('ลบไฟล์ไม่สำเร็จ');
            }
        },

        async bulkDelete() {
            if (this.selectedPaths.length === 0) return;
            
            if (!confirm(`ต้องการลบ ${this.selectedPaths.length} รายการที่เลือก?`)) return;
            
            try {
                await fetch(`/api/admin/files?root=${this.fileSystem.root}&paths=${encodeURIComponent(JSON.stringify(this.selectedPaths))}`, { 
                    method: 'DELETE', 
                    headers: { 'X-Admin-Token': localStorage.getItem('adminToken') } 
                });
                this.selectedPaths = [];
                await this.loadFiles();
                alert('ลบเรียบร้อยแล้ว!');
            } catch(e) {
                alert('ลบไม่สำเร็จ');
            }
        },

        async processRAG() {
            this.processing = true;
            
            try {
                await fetch('/api/admin/process-rag', { 
                    method: 'POST', 
                    headers: { 'X-Admin-Token': localStorage.getItem('adminToken') } 
                });
                alert('ประมวลผล RAG สำเร็จ!');
            } catch(e) { 
                alert('Sync RAG ล้มเหลว'); 
            } finally { 
                this.processing = false; 
                await this.loadFiles(); 
            }
        }
    };
};

// Auto-bootstrap
(function() {
    const bootstrap = () => {
        if (document.getElementById('files-container')) {
            window.loadFilesTab();
        } else { 
            setTimeout(bootstrap, 100); 
        }
    };
    bootstrap();
})();