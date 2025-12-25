/**
 * File Explorer Module
 * จัดการ File System, Upload, และ File Operations
 */

// Global state for files
window.filesState = {
    fileSystem: {
        root: 'data',
        current_path: '',
        entries: []
    },
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
        <div x-data="filesModule()">
            <div class="mb-8 md:mb-10">
                <h1 class="text-4xl md:text-5xl font-black gradient-text mb-2">File Explorer</h1>
                <p class="text-gray-500 font-medium">จัดการไฟล์และโฟลเดอร์</p>
            </div>

            <!-- Toolbar -->
            <div class="card-base p-4 md:p-6 rounded-2xl shadow-lg mb-6">
                <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                    <!-- Root Selector -->
                    <div class="flex items-center space-x-2 overflow-x-auto">
                        <button @click="switchRoot('data')" 
                            :class="fileSystem.root === 'data' ? 'gradient-purple-orange text-white' : 'bg-gray-100 text-gray-700'"
                            class="px-4 py-2 rounded-lg font-bold text-sm whitespace-nowrap transition">
                            Data
                        </button>
                        <button @click="switchRoot('uploads')" 
                            :class="fileSystem.root === 'uploads' ? 'gradient-purple-orange text-white' : 'bg-gray-100 text-gray-700'"
                            class="px-4 py-2 rounded-lg font-bold text-sm whitespace-nowrap transition">
                            Uploads
                        </button>
                    </div>

                    <!-- Actions -->
                    <div class="flex items-center space-x-2 overflow-x-auto">
                        <button @click="createNewFolder()" 
                            class="px-4 py-2 bg-purple-500 text-white rounded-lg font-bold text-sm hover:bg-purple-600 transition whitespace-nowrap flex items-center">
                            <i data-lucide="folder-plus" class="w-4 h-4 mr-2"></i>
                            <span class="hidden md:inline">New Folder</span>
                        </button>
                        <label class="px-4 py-2 bg-orange-500 text-white rounded-lg font-bold text-sm hover:bg-orange-600 transition cursor-pointer whitespace-nowrap flex items-center">
                            <i data-lucide="upload" class="w-4 h-4 mr-2"></i>
                            <span class="hidden md:inline">Upload</span>
                            <input type="file" @change="uploadMultipleFiles" multiple class="hidden">
                        </label>
                        <button @click="processRAG()" :disabled="processing"
                            class="px-4 py-2 bg-green-500 text-white rounded-lg font-bold text-sm hover:bg-green-600 transition disabled:opacity-50 whitespace-nowrap flex items-center">
                            <i data-lucide="refresh-cw" class="w-4 h-4 mr-2" :class="{'animate-spin': processing}"></i>
                            <span class="hidden md:inline">Sync RAG</span>
                        </button>
                    </div>
                </div>

                <!-- Breadcrumb -->
                <div class="mt-4 flex items-center space-x-2 text-sm overflow-x-auto">
                    <button @click="navigate('')" class="text-purple-500 font-bold hover:underline whitespace-nowrap">
                        <i data-lucide="home" class="w-4 h-4 inline"></i> Root
                    </button>
                    <template x-for="(part, index) in fileSystem.current_path.split('/').filter(p => p)" :key="index">
                        <div class="flex items-center space-x-2">
                            <span class="text-gray-400">/</span>
                            <button @click="navigateByParts(index)" 
                                class="text-purple-500 font-bold hover:underline whitespace-nowrap"
                                x-text="part">
                            </button>
                        </div>
                    </template>
                </div>

                <!-- Search -->
                <div class="mt-4">
                    <div class="relative">
                        <i data-lucide="search" class="w-5 h-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400"></i>
                        <input type="text" x-model="searchQuery" 
                            placeholder="ค้นหาไฟล์..."
                            class="w-full pl-10 pr-4 py-3 rounded-xl border-2 border-gray-200 focus:border-purple-500 outline-none">
                    </div>
                </div>

                <!-- Batch Actions -->
                <div x-show="selectedPaths.length > 0" class="mt-4 flex items-center justify-between bg-purple-50 p-3 rounded-xl">
                    <span class="text-sm font-bold text-purple-600">เลือกแล้ว <span x-text="selectedPaths.length"></span> รายการ</span>
                    <div class="flex space-x-2">
                        <button @click="batchMove()" 
                            class="px-3 py-1.5 bg-orange-500 text-white rounded-lg text-sm font-bold hover:bg-orange-600">
                            ย้าย
                        </button>
                        <button @click="batchDelete()" 
                            class="px-3 py-1.5 bg-red-500 text-white rounded-lg text-sm font-bold hover:bg-red-600">
                            ลบ
                        </button>
                    </div>
                </div>
            </div>

            <!-- File List -->
            <div class="card-base rounded-2xl shadow-lg overflow-hidden">
                <!-- Upload Progress -->
                <div x-show="uploadStatus.total > 0 && uploadStatus.done < uploadStatus.total" 
                    class="bg-purple-50 p-4 border-b">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-sm font-bold text-purple-600">กำลังอัปโหลด...</span>
                        <span class="text-sm font-bold text-purple-600" 
                            x-text="uploadStatus.done + '/' + uploadStatus.total">
                        </span>
                    </div>
                    <div class="w-full bg-gray-200 rounded-full h-2">
                        <div class="gradient-purple-orange h-2 rounded-full transition-all" 
                            :style="'width: ' + (uploadStatus.done / uploadStatus.total * 100) + '%'">
                        </div>
                    </div>
                </div>

                <!-- Drag & Drop Zone -->
                <div @drop.prevent="handleDrop" 
                    @dragover.prevent="dragging = true" 
                    @dragleave.prevent="dragging = false"
                    :class="{'drag-over': dragging}"
                    class="p-6 transition-all">
                    
                    <!-- File Grid/List -->
                    <div class="space-y-2">
                        <!-- Select All -->
                        <div class="flex items-center p-3 bg-gray-50 rounded-lg">
                            <input type="checkbox" 
                                @change="toggleSelectAll()" 
                                :checked="isAllSelected()"
                                class="mr-3 w-5 h-5 rounded border-gray-300">
                            <span class="text-sm font-bold text-gray-600">เลือกทั้งหมด</span>
                        </div>

                        <!-- Files -->
                        <template x-for="entry in filteredEntries" :key="entry.path">
                            <div class="flex items-center p-4 hover:bg-gray-50 rounded-lg transition group">
                                <input type="checkbox" 
                                    :value="entry.path" 
                                    x-model="selectedPaths"
                                    class="mr-3 w-5 h-5 rounded border-gray-300">
                                
                                <div class="flex-1 flex items-center space-x-3 min-w-0">
                                    <i :data-lucide="entry.type === 'dir' ? 'folder' : 'file-text'" 
                                        :class="entry.type === 'dir' ? 'text-purple-500' : 'text-orange-500'"
                                        class="w-5 h-5 flex-shrink-0">
                                    </i>
                                    <div class="flex-1 min-w-0">
                                        <button @click="entry.type === 'dir' ? navigate(entry.path) : previewFile(entry)"
                                            class="text-left font-bold text-gray-800 hover:text-purple-500 truncate block w-full"
                                            x-text="entry.name">
                                        </button>
                                        <p class="text-xs text-gray-500" x-text="entry.size"></p>
                                    </div>
                                </div>

                                <div class="flex items-center space-x-2 opacity-0 group-hover:opacity-100 transition">
                                    <button @click="renameItem(entry)" 
                                        class="p-2 hover:bg-purple-100 rounded-lg">
                                        <i data-lucide="edit-2" class="w-4 h-4 text-purple-500"></i>
                                    </button>
                                    <button @click="deleteItem(entry)" 
                                        class="p-2 hover:bg-red-100 rounded-lg">
                                        <i data-lucide="trash-2" class="w-4 h-4 text-red-500"></i>
                                    </button>
                                </div>
                            </div>
                        </template>

                        <!-- Empty State -->
                        <div x-show="filteredEntries.length === 0" 
                            class="text-center py-12">
                            <i data-lucide="folder-open" class="w-16 h-16 mx-auto text-gray-300 mb-4"></i>
                            <p class="text-gray-500 font-medium">ไม่พบไฟล์</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Preview Modal -->
            <div x-show="preview.open" 
                @click.self="closePreview()"
                class="fixed inset-0 z-[2000] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
                <div class="card-base rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col">
                    <!-- Header -->
                    <div class="p-6 border-b flex items-center justify-between">
                        <div class="flex items-center space-x-3">
                            <i data-lucide="file-text" class="w-5 h-5 text-purple-500"></i>
                            <h3 class="font-bold text-lg truncate" x-text="preview.fileName"></h3>
                        </div>
                        <button @click="closePreview()" 
                            class="p-2 hover:bg-gray-100 rounded-lg">
                            <i data-lucide="x" class="w-5 h-5"></i>
                        </button>
                    </div>

                    <!-- Content -->
                    <div class="flex-1 overflow-auto p-6">
                        <div x-show="preview.loading" class="text-center py-12">
                            <i data-lucide="loader" class="w-12 h-12 mx-auto text-purple-500 animate-spin mb-4"></i>
                            <p class="text-gray-500 font-medium">กำลังโหลด...</p>
                        </div>

                        <div x-show="!preview.loading && preview.type === 'txt'">
                            <textarea x-model="preview.content" 
                                class="w-full h-96 p-4 border-2 border-gray-200 rounded-xl font-mono text-sm resize-none focus:border-purple-500 outline-none">
                            </textarea>
                        </div>

                        <div x-show="!preview.loading && preview.type === 'pdf'">
                            <iframe :src="preview.url" 
                                class="w-full h-96 border-2 border-gray-200 rounded-xl">
                            </iframe>
                        </div>
                    </div>

                    <!-- Footer -->
                    <div x-show="preview.type === 'txt'" 
                        class="p-6 border-t flex justify-end space-x-3">
                        <button @click="closePreview()" 
                            class="px-6 py-3 bg-gray-200 text-gray-700 rounded-xl font-bold hover:bg-gray-300">
                            ปิด
                        </button>
                        <button @click="saveContent()" :disabled="preview.saveLoading"
                            class="px-6 py-3 gradient-purple-orange text-white rounded-xl font-bold hover:shadow-lg disabled:opacity-50">
                            <span x-show="!preview.saveLoading">บันทึก</span>
                            <span x-show="preview.saveLoading">กำลังบันทึก...</span>
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
 * Files Module for Alpine.js
 */
window.filesModule = function() {
    return {
        ...window.filesState,

        get filteredEntries() {
            return this.fileSystem.entries.filter(e => 
                e.name.toLowerCase().includes(this.searchQuery.toLowerCase())
            );
        },

        async switchRoot(root) {
            this.fileSystem.root = root;
            this.fileSystem.current_path = '';
            await this.loadFiles();
        },

        async navigate(path) {
            this.fileSystem.current_path = path;
            await this.loadFiles();
        },

        navigateUp() {
            const parts = this.fileSystem.current_path.split('/').filter(p => p);
            parts.pop();
            this.navigate(parts.join('/'));
        },

        navigateByParts(index) {
            const parts = this.fileSystem.current_path.split('/').filter(p => p);
            this.navigate(parts.slice(0, index + 1).join('/'));
        },

        async loadFiles() {
            const app = Alpine.store ? Alpine : window;
            const token = localStorage.getItem('adminToken');
            
            try {
                const res = await fetch(
                    `/api/admin/files?root=${this.fileSystem.root}&subdir=${this.fileSystem.current_path}`,
                    { headers: { 'X-Admin-Token': token } }
                );
                const data = await res.json();
                this.fileSystem.entries = data.entries;
                this.fileSystem.current_path = data.current_path;
                this.selectedPaths = [];
                
                setTimeout(() => lucide.createIcons(), 100);
            } catch (e) {
                console.error('Failed to load files:', e);
            }
        },

        toggleSelectAll() {
            if (this.isAllSelected()) {
                this.selectedPaths = [];
            } else {
                this.selectedPaths = this.filteredEntries.map(e => e.path);
            }
        },

        isAllSelected() {
            return this.filteredEntries.length > 0 && 
                   this.selectedPaths.length === this.filteredEntries.length;
        },

        async batchDelete() {
            if (!confirm(`คุณต้องการลบ ${this.selectedPaths.length} รายการที่เลือกใช่หรือไม่?`)) return;
            
            const token = localStorage.getItem('adminToken');
            try {
                const res = await fetch(
                    `/api/admin/files?root=${this.fileSystem.root}&paths=${encodeURIComponent(JSON.stringify(this.selectedPaths))}`,
                    { 
                        method: 'DELETE', 
                        headers: { 'X-Admin-Token': token } 
                    }
                );
                const data = await res.json();
                alert(`ลบสำเร็จ ${data.count} รายการ`);
                await this.loadFiles();
            } catch(e) {
                alert('ไม่สามารถลบข้อมูลได้');
            }
        },

        async batchMove() {
            const dest = prompt("ระบุ Path ปลายทาง (เช่น 'folder1/sub'):", "");
            if (dest === null) return;
            
            const token = localStorage.getItem('adminToken');
            const fd = new FormData();
            fd.append('root', this.fileSystem.root);
            fd.append('src_paths', JSON.stringify(this.selectedPaths));
            fd.append('dest_dir', dest);
            
            try {
                await fetch('/api/admin/move', {
                    method: 'POST',
                    headers: { 'X-Admin-Token': token },
                    body: fd
                });
                alert("ย้ายข้อมูลเรียบร้อยแล้ว");
                await this.loadFiles();
            } catch(e) {
                alert("ไม่สามารถย้ายข้อมูลได้");
            }
        },

        async createNewFolder() {
            const name = prompt("ชื่อโฟลเดอร์ใหม่:");
            if (!name) return;
            
            const token = localStorage.getItem('adminToken');
            const fd = new FormData();
            fd.append('root', this.fileSystem.root);
            fd.append('path', this.fileSystem.current_path);
            fd.append('name', name);
            
            try {
                await fetch('/api/admin/mkdir', {
                    method: 'POST',
                    headers: { 'X-Admin-Token': token },
                    body: fd
                });
                await this.loadFiles();
            } catch(e) {
                alert('ไม่สามารถสร้างโฟลเดอร์ได้');
            }
        },

        async renameItem(entry) {
            const newName = prompt(`เปลี่ยนชื่อ "${entry.name}" เป็น:`, entry.name);
            if (!newName || newName === entry.name) return;
            
            const token = localStorage.getItem('adminToken');
            const fd = new FormData();
            fd.append('root', this.fileSystem.root);
            fd.append('old_path', entry.path);
            fd.append('new_name', newName);
            
            try {
                await fetch('/api/admin/rename', {
                    method: 'POST',
                    headers: { 'X-Admin-Token': token },
                    body: fd
                });
                await this.loadFiles();
            } catch(e) {
                alert('ไม่สามารถเปลี่ยนชื่อได้');
            }
        },

        async uploadMultipleFiles(e) {
            await this.executeUploadBatch(Array.from(e.target.files));
            e.target.value = '';
        },

        async handleDrop(e) {
            this.dragging = false;
            await this.executeUploadBatch(Array.from(e.dataTransfer.files));
        },

        async executeUploadBatch(uploadItems) {
            const token = localStorage.getItem('adminToken');
            this.uploadStatus = { total: uploadItems.length, done: 0 };
            
            for (const f of uploadItems) {
                const fd = new FormData();
                fd.append('file', f);
                fd.append('target_dir', this.fileSystem.current_path);
                
                try {
                    await fetch('/api/admin/upload', {
                        method: 'POST',
                        headers: { 'X-Admin-Token': token },
                        body: fd
                    });
                } catch(e) {
                    console.error('Upload failed:', e);
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
            
            const token = localStorage.getItem('adminToken');
            const url = `/api/admin/view?root=${this.fileSystem.root}&path=${entry.path}`;
            
            try {
                const res = await fetch(url, {
                    headers: { 'X-Admin-Token': token }
                });
                const blob = await res.blob();
                
                if (this.preview.type === 'pdf') {
                    if (this.preview.url) URL.revokeObjectURL(this.preview.url);
                    this.preview.url = URL.createObjectURL(blob);
                } else {
                    this.preview.content = await blob.text();
                }
            } catch(e) {
                alert('ไม่สามารถโหลดไฟล์ได้');
            } finally {
                this.preview.loading = false;
                setTimeout(() => lucide.createIcons(), 100);
            }
        },

        async saveContent() {
            this.preview.saveLoading = true;
            const token = localStorage.getItem('adminToken');
            const fd = new FormData();
            fd.append('root', this.fileSystem.root);
            fd.append('path', this.preview.entry.path);
            fd.append('content', this.preview.content);
            
            try {
                await fetch('/api/admin/edit', {
                    method: 'POST',
                    headers: { 'X-Admin-Token': token },
                    body: fd
                });
                alert('บันทึกสำเร็จ!');
            } catch(e) {
                alert('ไม่สามารถบันทึกได้');
            } finally {
                this.preview.saveLoading = false;
            }
        },

        closePreview() {
            this.preview.open = false;
            if (this.preview.url) {
                URL.revokeObjectURL(this.preview.url);
                this.preview.url = '';
            }
        },

        async deleteItem(entry) {
            if (confirm(`ลบ "${entry.name}"?`)) {
                const token = localStorage.getItem('adminToken');
                await fetch(
                    `/api/admin/files?root=${this.fileSystem.root}&paths=${encodeURIComponent(JSON.stringify([entry.path]))}`,
                    { 
                        method: 'DELETE', 
                        headers: { 'X-Admin-Token': token } 
                    }
                );
                await this.loadFiles();
            }
        },

        async processRAG() {
            this.processing = true;
            const token = localStorage.getItem('adminToken');
            
            try {
                await fetch('/api/admin/process-rag', {
                    method: 'POST',
                    headers: { 'X-Admin-Token': token }
                });
                alert('Sync ข้อมูล RAG สำเร็จ!');
                await this.loadFiles();
            } catch(e) {
                alert('ไม่สามารถ Sync RAG ได้');
            } finally {
                this.processing = false;
            }
        }
    };
};