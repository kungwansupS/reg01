/**
 * Enterprise File Explorer Module - Enhanced Edition
 * CMU Innovation Platform - Modern File Management System
 * Features: Drag & Drop, Grid/List View, Professional UI/UX
 * 
 * FIXES:
 * 1. Removed duplicate context menu
 * 2. Fixed move/copy API to handle root directory (empty path)
 * 3. Improved error handling with proper error messages
 */

// Global File System State
window.filesState = {
    fileSystem: { root: 'data', current_path: '', entries: [] },
    selectedPaths: [],
    searchQuery: '',
    dragging: false,
    dragCounter: 0,
    draggedItems: [],
    draggedOver: null,
    selectionMode: false,
    longPressTimer: null,
    longPressFired: false,
    uploadStatus: { total: 0, done: 0 },
    processing: false,
    viewMode: 'grid',
    sortBy: 'name',
    sortDesc: false,
    contextMenu: { show: false, x: 0, y: 0, entry: null },
    clipboard: { action: null, paths: [] },
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
        <div x-data="filesModule()" 
             x-init="init()" 
             @click.away="contextMenu.show = false"
             class="animate-in h-full flex flex-col">
            
            <!-- Header -->
            <div class="mb-6">
                <h1 class="text-4xl md:text-5xl font-black gradient-text-cmu mb-2">File Explorer</h1>
                <p class="font-medium" style="color: var(--text-secondary);">Modern Document Management System</p>
            </div>

            <!-- Toolbar -->
            <div class="card-enterprise rounded-2xl shadow-lg mb-4 overflow-hidden">
                <!-- Navigation Bar -->
                <div class="p-4 border-b" style="border-color: var(--border-secondary);">
                    <div class="flex items-center gap-3">
                        <!-- Back/Forward Buttons -->
                        <div class="flex items-center gap-1">
                            <button 
                                @click="navigateBack()" 
                                :disabled="fileSystem.current_path === ''"
                                class="p-2 rounded-lg transition-all disabled:opacity-30 disabled:cursor-not-allowed hover:scale-105"
                                :style="fileSystem.current_path !== '' ? 'background-color: var(--bg-tertiary); color: var(--text-primary);' : 'color: var(--text-tertiary);'"
                                title="เธขเนเธญเธเธเธฅเธฑเธ">
                                <i data-lucide="arrow-left" class="w-5 h-5"></i>
                            </button>
                            <button 
                                @click="navigate('')" 
                                class="p-2 rounded-lg transition-all hover:scale-105"
                                style="background-color: var(--bg-tertiary); color: var(--text-primary);"
                                title="เธเธฅเธฑเธเธซเธเนเธฒเนเธฃเธ">
                                <i data-lucide="home" class="w-5 h-5"></i>
                            </button>
                        </div>

                        <!-- Breadcrumb -->
                        <div class="flex-1 flex items-center gap-2 px-4 py-2.5 rounded-lg overflow-x-auto custom-scrollbar" style="background-color: var(--bg-tertiary);">
                            <i data-lucide="folder" class="w-4 h-4 shrink-0" style="color: var(--cmu-purple);"></i>
                            <button 
                                @click="navigate('')" 
                                class="font-bold text-sm hover:underline transition-colors shrink-0"
                                style="color: var(--cmu-purple);">
                                Root
                            </button>
                            <template x-for="(part, index) in fileSystem.current_path.split('/').filter(p => p)" :key="index">
                                <div class="flex items-center gap-2 shrink-0">
                                    <i data-lucide="chevron-right" class="w-4 h-4" style="color: var(--text-tertiary);"></i>
                                    <button 
                                        @click="navigateByParts(index)" 
                                        class="font-bold text-sm hover:underline transition-colors"
                                        style="color: var(--cmu-purple);"
                                        x-text="part">
                                    </button>
                                </div>
                            </template>
                        </div>

                        <!-- View Mode Toggle -->
                        <div class="flex items-center gap-1 p-1 rounded-lg" style="background-color: var(--bg-tertiary);">
                            <button 
                                @click="viewMode = 'grid'" 
                                class="p-2 rounded transition-all hover:scale-105"
                                :style="viewMode === 'grid' ? 'background-color: var(--cmu-purple); color: white; box-shadow: 0 2px 6px rgba(81,45,109,0.3);' : 'color: var(--text-secondary);'"
                                title="Grid View">
                                <i data-lucide="grid-3x3" class="w-4 h-4"></i>
                            </button>
                            <button 
                                @click="viewMode = 'list'" 
                                class="p-2 rounded transition-all hover:scale-105"
                                :style="viewMode === 'list' ? 'background-color: var(--cmu-purple); color: white; box-shadow: 0 2px 6px rgba(81,45,109,0.3);' : 'color: var(--text-secondary);'"
                                title="List View">
                                <i data-lucide="list" class="w-4 h-4"></i>
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Action Bar -->
                <div class="p-4 flex flex-col md:flex-row gap-4">
                    <!-- Root Selector -->
                    <div class="flex items-center gap-2 p-1 rounded-xl shrink-0" style="background-color: var(--bg-tertiary);">
                        <button 
                            @click="switchRoot('data')" 
                            class="px-4 py-2.5 rounded-lg font-bold text-sm transition-all flex items-center gap-2 hover:scale-105"
                            :style="fileSystem.root === 'data' ? 'background-color: var(--cmu-purple); color: white; box-shadow: 0 4px 12px rgba(81, 45, 109, 0.4);' : 'color: var(--text-secondary);'">
                            <i data-lucide="file-text" class="w-4 h-4"></i>
                            <span>PDF Files</span>
                        </button>
                        <button 
                            @click="switchRoot('uploads')" 
                            class="px-4 py-2.5 rounded-lg font-bold text-sm transition-all flex items-center gap-2 hover:scale-105"
                            :style="fileSystem.root === 'uploads' ? 'background-color: var(--cmu-purple); color: white; box-shadow: 0 4px 12px rgba(81, 45, 109, 0.4);' : 'color: var(--text-secondary);'">
                            <i data-lucide="database" class="w-4 h-4"></i>
                            <span>RAG Database</span>
                        </button>
                    </div>

                    <!-- Search -->
                    <div class="flex-1 relative">
                        <i data-lucide="search" class="w-5 h-5 absolute left-3 top-1/2 transform -translate-y-1/2" style="color: var(--text-tertiary);"></i>
                        <input 
                            type="text" 
                            x-model="searchQuery" 
                            placeholder="เธเนเธเธซเธฒเนเธเธฅเนเธซเธฃเธทเธญเนเธเธฅเน€เธ”เธญเธฃเน..."
                            class="w-full pl-10 pr-4 py-2.5 rounded-lg border transition-all focus:ring-2 focus:ring-purple-500 outline-none"
                            style="background-color: var(--bg-tertiary); border-color: var(--border-primary); color: var(--text-primary);">
                    </div>

                    <!-- Action Buttons -->
                    <div class="flex items-center gap-2 shrink-0 flex-wrap">
                        <button 
                            @click="createNewFolder()" 
                            class="px-4 py-2.5 rounded-lg font-bold text-sm btn-enterprise flex items-center gap-2 text-white transition-all hover:shadow-lg hover:scale-105"
                            style="background-color: var(--cmu-purple);">
                            <i data-lucide="folder-plus" class="w-4 h-4"></i>
                            <span class="hidden lg:inline">New Folder</span>
                        </button>
                        <label class="px-4 py-2.5 rounded-lg font-bold text-sm btn-enterprise cursor-pointer flex items-center gap-2 text-white transition-all hover:shadow-lg hover:scale-105"
                               style="background-color: var(--accent-gold);">
                            <i data-lucide="upload" class="w-4 h-4"></i>
                            <span class="hidden lg:inline">Upload Files</span>
                            <input type="file" @change="uploadMultipleFiles" multiple class="hidden">
                        </label>
                        <button 
                            @click="processRAG()" 
                            :disabled="processing || fileSystem.root !== 'data'" 
                            class="px-4 py-2.5 rounded-lg font-bold text-sm btn-enterprise disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2 transition-all hover:shadow-lg hover:scale-105 relative overflow-hidden"
                            :style="processing ? 'background-color: var(--text-tertiary); color: white;' : 'background-color: #10B981; color: white;'"
                            :title="fileSystem.root !== 'data' ? 'Available only in PDF Files view' : 'Auto convert PDF to TXT for RAG'">
                            <i :data-lucide="processing ? 'loader' : 'zap'" class="w-4 h-4" :class="{'animate-spin': processing}"></i>
                            <span class="hidden lg:inline" x-text="processing ? 'Processing...' : 'Auto PDFโ’TXT'"></span>
                            <template x-if="processing">
                                <div class="absolute inset-0 bg-gradient-to-r from-transparent via-white to-transparent opacity-20 animate-shimmer"></div>
                            </template>
                        </button>
                    </div>
                </div>

                <!-- Selection Info Bar -->
                <div 
                    x-show="selectedPaths.length > 0 || clipboard.paths.length > 0" 
                    class="px-4 py-3 border-t flex items-center justify-between"
                    style="background-color: rgba(81, 45, 109, 0.05); border-color: var(--border-secondary);">
                    <div class="flex items-center gap-3">
                        <div class="p-2 rounded-lg" :style="clipboard.paths.length > 0 ? 'background-color: rgba(16, 185, 129, 0.1);' : 'background-color: rgba(81, 45, 109, 0.1);'">
                            <i :data-lucide="clipboard.paths.length > 0 ? (clipboard.action === 'copy' ? 'copy' : 'scissors') : 'check-square'" 
                               class="w-5 h-5" 
                               :style="clipboard.paths.length > 0 ? 'color: #10B981;' : 'color: var(--cmu-purple);'"></i>
                        </div>
                        <span class="font-bold" style="color: var(--text-primary);">
                            <template x-if="clipboard.paths.length > 0">
                                <span>
                                    <span x-text="clipboard.action === 'copy' ? 'เธเธฑเธ”เธฅเธญเธเนเธฅเนเธง' : 'เธ•เธฑเธ”เนเธฅเนเธง'"></span>
                                    <span x-text="clipboard.paths.length"></span> เธฃเธฒเธขเธเธฒเธฃ
                                </span>
                            </template>
                            <template x-if="clipboard.paths.length === 0">
                                <span>
                                    เน€เธฅเธทเธญเธเนเธงเน <span x-text="selectedPaths.length"></span> เธฃเธฒเธขเธเธฒเธฃ
                                </span>
                            </template>
                        </span>
                    </div>
                    <div class="flex items-center gap-2 flex-wrap">
                        <!-- Clipboard Mode: Show only Paste and Cancel -->
                        <template x-if="clipboard.paths.length > 0">
                            <div class="flex items-center gap-2">
                                <button 
                                    @click="pasteFromClipboard()" 
                                    class="px-4 py-2 rounded-lg font-bold text-sm transition-all hover:shadow-lg hover:scale-105 flex items-center gap-2 text-white"
                                    style="background-color: #10B981;">
                                    <i data-lucide="clipboard-check" class="w-4 h-4"></i>
                                    <span>Paste Here</span>
                                </button>
                                <button 
                                    @click="clipboard = { action: null, paths: [] }; selectedPaths = []; selectionMode = false;" 
                                    class="px-4 py-2 rounded-lg font-bold text-sm transition-all hover:shadow-lg hover:scale-105"
                                    style="background-color: var(--danger); color: white;">
                                    <span>Cancel</span>
                                </button>
                            </div>
                        </template>

                        <!-- Normal Selection Mode: Show all buttons -->
                        <template x-if="clipboard.paths.length === 0 && selectedPaths.length > 0">
                            <div class="flex items-center gap-2 flex-wrap">
                                <button 
                                    @click="copyToClipboard()" 
                                    class="px-3 py-2 rounded-lg font-bold text-sm transition-all hover:shadow-lg hover:scale-105 flex items-center gap-2"
                                    style="background-color: var(--bg-tertiary); color: var(--text-primary);"
                                    title="Copy">
                                    <i data-lucide="copy" class="w-4 h-4"></i>
                                    <span class="hidden sm:inline">Copy</span>
                                </button>
                                <button 
                                    @click="cutToClipboard()" 
                                    class="px-3 py-2 rounded-lg font-bold text-sm transition-all hover:shadow-lg hover:scale-105 flex items-center gap-2"
                                    style="background-color: var(--bg-tertiary); color: var(--text-primary);"
                                    title="Cut">
                                    <i data-lucide="scissors" class="w-4 h-4"></i>
                                    <span class="hidden sm:inline">Cut</span>
                                </button>
                                <div class="w-px h-6 bg-gray-300"></div>
                                <button 
                                    @click="bulkDelete()" 
                                    class="px-3 py-2 rounded-lg font-bold text-sm transition-all hover:shadow-lg hover:scale-105 flex items-center gap-2 text-white"
                                    style="background-color: var(--danger);">
                                    <i data-lucide="trash-2" class="w-4 h-4"></i>
                                    <span class="hidden sm:inline">Delete</span>
                                </button>
                                <button 
                                    @click="selectedPaths = []; selectionMode = false;" 
                                    class="px-3 py-2 rounded-lg font-bold text-sm transition-all hover:bg-opacity-10"
                                    style="background-color: var(--bg-tertiary); color: var(--text-secondary);">
                                    <span>Clear</span>
                                </button>
                            </div>
                        </template>
                    </div>
                </div>
            </div>

            <!-- Upload Progress Bar -->
            <div x-show="uploadStatus.total > 0 && uploadStatus.done < uploadStatus.total" 
                 class="card-enterprise p-4 rounded-xl shadow-lg mb-4 animate-in"
                 style="border-left: 4px solid var(--cmu-purple);">
                <div class="flex justify-between mb-2 font-bold text-sm" style="color: var(--cmu-purple);">
                    <span class="flex items-center gap-2">
                        <i data-lucide="upload-cloud" class="w-4 h-4"></i>
                        Uploading files...
                    </span>
                    <span x-text="uploadStatus.done + '/' + uploadStatus.total"></span>
                </div>
                <div class="w-full h-2 rounded-full overflow-hidden" style="background-color: var(--bg-tertiary);">
                    <div class="gradient-cmu h-2 transition-all duration-300" 
                         :style="'width:'+(uploadStatus.done/uploadStatus.total*100)+'%'">
                    </div>
                </div>
            </div>

            <!-- File Grid/List Container with Drag & Drop -->
            <div 
                @drop.prevent="handleDrop($event)"
                @dragover.prevent="handleDragOver($event)"
                @dragenter.prevent="handleDragEnter($event)"
                @dragleave.prevent="handleDragLeave($event)"
                :class="dragging ? 'drag-active' : ''"
                class="card-enterprise rounded-2xl shadow-lg flex-1 overflow-hidden transition-all"
                style="min-height: 400px; position: relative;">
                
                <!-- Drag Overlay -->
                <div x-show="dragging" 
                     class="absolute inset-0 z-50 flex items-center justify-center pointer-events-none"
                     style="background-color: rgba(81, 45, 109, 0.95); backdrop-filter: blur(8px);">
                    <div class="text-center animate-in">
                        <div class="w-24 h-24 mx-auto mb-6 rounded-full flex items-center justify-center" 
                             style="background-color: rgba(255, 255, 255, 0.2);">
                            <i data-lucide="upload-cloud" class="w-12 h-12 text-white"></i>
                        </div>
                        <p class="text-2xl font-black text-white mb-2">Drop files here</p>
                        <p class="text-sm font-medium text-white opacity-80">Release to upload</p>
                    </div>
                </div>

                <!-- Grid View -->
                <div x-show="viewMode === 'grid'" class="p-6 overflow-y-auto h-full custom-scrollbar">
                    <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                        <template x-for="entry in sortedFilteredEntries" :key="entry.path">
                            <div 
                                @mousedown="handleItemMouseDown($event, entry)"
                                @mouseup="handleItemMouseUp($event, entry)"
                                @contextmenu.prevent="showContextMenu($event, entry)"
                                @dragstart="handleItemDragStart($event, entry)"
                                @dragend="handleItemDragEnd($event)"
                                @dragover.prevent="handleItemDragOver($event, entry)"
                                @dragleave="handleItemDragLeave($event, entry)"
                                @drop.prevent="handleItemDrop($event, entry)"
                                :draggable="selectionMode || selectedPaths.includes(entry.path)"
                                class="group cursor-pointer transition-all select-none"
                                :class="{
                                    'selected-item': selectedPaths.includes(entry.path),
                                    'hover:scale-105': clipboard.paths.length === 0,
                                    'opacity-50': clipboard.action === 'cut' && clipboard.paths.includes(entry.path)
                                }">
                                <div class="card-enterprise p-4 rounded-xl transition-all hover:shadow-lg relative"
                                     :class="draggedOver === entry.path && entry.type === 'dir' ? 'drag-over-folder' : ''"
                                     :style="selectedPaths.includes(entry.path) ? 'border: 2px solid var(--cmu-purple); background-color: rgba(81, 45, 109, 0.05);' : 'border: 2px solid transparent;'">
                                    <!-- Selection Badge -->
                                    <div x-show="selectedPaths.includes(entry.path)" 
                                         class="absolute -top-2 -right-2 w-6 h-6 rounded-full flex items-center justify-center shadow-lg z-10"
                                         style="background-color: var(--cmu-purple);">
                                        <i data-lucide="check" class="w-4 h-4 text-white"></i>
                                    </div>
                                    
                                    <!-- Icon -->
                                    <div class="w-full aspect-square rounded-lg mb-3 flex items-center justify-center transition-all"
                                         :style="entry.type === 'dir' ? 'background: linear-gradient(135deg, rgba(81, 45, 109, 0.1) 0%, rgba(107, 70, 148, 0.1) 100%);' : 'background: linear-gradient(135deg, rgba(196, 160, 82, 0.1) 0%, rgba(212, 176, 98, 0.1) 100%);'">
                                        <i :data-lucide="getFileIcon(entry)" 
                                           class="w-12 h-12 transition-transform group-hover:scale-110"
                                           :style="entry.type === 'dir' ? 'color: var(--cmu-purple);' : 'color: var(--accent-gold);'"></i>
                                    </div>
                                    <!-- Name -->
                                    <p class="font-bold text-sm text-center truncate mb-1" 
                                       style="color: var(--text-primary);" 
                                       x-text="entry.name"
                                       :title="entry.name"></p>
                                    <!-- Size -->
                                    <p class="text-xs text-center" 
                                       style="color: var(--text-tertiary);" 
                                       x-text="entry.size"></p>
                                </div>
                            </div>
                        </template>
                    </div>

                    <!-- Empty State -->
                    <div x-show="sortedFilteredEntries.length === 0" class="flex flex-col items-center justify-center h-full py-20">
                        <div class="w-32 h-32 rounded-full flex items-center justify-center mb-6"
                             style="background-color: var(--bg-tertiary);">
                            <i data-lucide="folder-open" class="w-16 h-16" style="color: var(--border-primary);"></i>
                        </div>
                        <p class="text-xl font-bold mb-2" style="color: var(--text-secondary);">No files found</p>
                        <p class="text-sm" style="color: var(--text-tertiary);">
                            <template x-if="searchQuery">
                                Try a different search term
                            </template>
                            <template x-if="!searchQuery">
                                Drag and drop files here or click Upload
                            </template>
                        </p>
                    </div>
                </div>

                <!-- List View -->
                <div x-show="viewMode === 'list'" class="overflow-x-auto h-full">
                    <table class="w-full table-enterprise">
                        <thead style="background-color: var(--bg-tertiary); border-bottom: 2px solid var(--border-primary); position: sticky; top: 0; z-10;">
                            <tr>
                                <th class="p-4 w-12">
                                    <input 
                                        type="checkbox" 
                                        @change="toggleSelectAll()" 
                                        :checked="isAllSelected()" 
                                        class="w-5 h-5 rounded cursor-pointer">
                                </th>
                                <th class="p-4 font-bold text-sm text-left" style="color: var(--text-secondary);">
                                    <button @click="toggleSort('name')" class="flex items-center gap-2 hover:text-purple-600 transition-colors">
                                        Name
                                        <i :data-lucide="sortBy === 'name' ? (sortDesc ? 'arrow-down' : 'arrow-up') : 'chevrons-up-down'" class="w-4 h-4"></i>
                                    </button>
                                </th>
                                <th class="p-4 font-bold text-sm text-left hidden md:table-cell" style="color: var(--text-secondary);">Type</th>
                                <th class="p-4 font-bold text-sm text-left w-32" style="color: var(--text-secondary);">
                                    <button @click="toggleSort('size')" class="flex items-center gap-2 hover:text-purple-600 transition-colors">
                                        Size
                                        <i :data-lucide="sortBy === 'size' ? (sortDesc ? 'arrow-down' : 'arrow-up') : 'chevrons-up-down'" class="w-4 h-4"></i>
                                    </button>
                                </th>
                                <th class="p-4 font-bold text-sm text-right w-40" style="color: var(--text-secondary);">Actions</th>
                            </tr>
                        </thead>
                        <tbody style="border-top: 1px solid var(--border-secondary);">
                            <template x-for="entry in sortedFilteredEntries" :key="entry.path">
                                <tr class="group transition-colors border-b cursor-pointer select-none" 
                                    style="border-color: var(--border-secondary);"
                                    :class="{
                                        'drag-over-folder': draggedOver === entry.path && entry.type === 'dir',
                                        'hover:bg-opacity-50': clipboard.paths.length === 0,
                                        'opacity-50': clipboard.action === 'cut' && clipboard.paths.includes(entry.path)
                                    }"
                                    :style="selectedPaths.includes(entry.path) ? 'background-color: rgba(81, 45, 109, 0.05);' : ''"
                                    @mousedown="handleItemMouseDown($event, entry)"
                                    @mouseup="handleItemMouseUp($event, entry)"
                                    @contextmenu.prevent="showContextMenu($event, entry)"
                                    @dragstart="handleItemDragStart($event, entry)"
                                    @dragend="handleItemDragEnd($event)"
                                    @dragover.prevent="handleItemDragOver($event, entry)"
                                    @dragleave="handleItemDragLeave($event, entry)"
                                    @drop.prevent="handleItemDrop($event, entry)"
                                    :draggable="selectionMode || selectedPaths.includes(entry.path)">
                                    <td class="p-4">
                                        <input 
                                            type="checkbox" 
                                            :value="entry.path" 
                                            :checked="selectedPaths.includes(entry.path)"
                                            @change="toggleSelection(entry)"
                                            @click.stop
                                            class="w-5 h-5 rounded cursor-pointer">
                                    </td>
                                    <td class="p-4">
                                        <div class="flex items-center gap-3">
                                            <div 
                                                class="p-2 rounded-lg transition-transform group-hover:scale-110"
                                                :style="entry.type === 'dir' ? 'background-color: rgba(81, 45, 109, 0.1); color: var(--cmu-purple);' : 'background-color: rgba(196, 160, 82, 0.1); color: var(--accent-gold);'">
                                                <i :data-lucide="getFileIcon(entry)" class="w-5 h-5"></i>
                                            </div>
                                            <span class="font-semibold transition-colors" style="color: var(--text-primary);" x-text="entry.name"></span>
                                        </div>
                                    </td>
                                    <td class="p-4 text-sm hidden md:table-cell" style="color: var(--text-secondary);">
                                        <span class="badge-enterprise" 
                                              :style="entry.type === 'dir' ? 'background-color: rgba(81, 45, 109, 0.1); color: var(--cmu-purple);' : 'background-color: rgba(196, 160, 82, 0.1); color: var(--accent-gold);'">
                                            <span x-text="entry.type === 'dir' ? 'Folder' : (entry.ext || 'File')"></span>
                                        </span>
                                    </td>
                                    <td class="p-4 text-sm font-medium" style="color: var(--text-secondary);" x-text="entry.size"></td>
                                    <td class="p-4 text-right">
                                        <div class="flex items-center justify-end gap-2">
                                            <button 
                                                @click.stop="renameItem(entry)" 
                                                class="p-2 rounded-lg transition-all hover:scale-110 opacity-0 group-hover:opacity-100"
                                                style="background-color: rgba(81, 45, 109, 0.1); color: var(--cmu-purple);"
                                                title="Rename">
                                                <i data-lucide="edit-3" class="w-4 h-4"></i>
                                            </button>
                                            <button 
                                                @click.stop="deleteItem(entry)" 
                                                class="p-2 rounded-lg transition-all hover:scale-110 opacity-0 group-hover:opacity-100"
                                                style="background-color: rgba(255, 59, 48, 0.1); color: var(--danger);"
                                                title="Delete">
                                                <i data-lucide="trash-2" class="w-4 h-4"></i>
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            </template>
                        </tbody>
                    </table>

                    <!-- Empty State for List View -->
                    <div x-show="sortedFilteredEntries.length === 0" class="flex flex-col items-center justify-center py-20">
                        <div class="w-32 h-32 rounded-full flex items-center justify-center mb-6"
                             style="background-color: var(--bg-tertiary);">
                            <i data-lucide="folder-open" class="w-16 h-16" style="color: var(--border-primary);"></i>
                        </div>
                        <p class="text-xl font-bold mb-2" style="color: var(--text-secondary);">No files found</p>
                        <p class="text-sm" style="color: var(--text-tertiary);">
                            <template x-if="searchQuery">
                                Try a different search term
                            </template>
                            <template x-if="!searchQuery">
                                Drag and drop files here or click Upload
                            </template>
                        </p>
                    </div>
                </div>
            </div>

            <!-- Preview Modal -->
            <div 
                x-show="preview.open" 
                x-cloak 
                class="preview-modal fixed inset-0 z-[2000] flex items-center justify-center p-4"
                style="background-color: var(--overlay); backdrop-filter: blur(4px);">
                <div class="preview-content card-enterprise rounded-3xl shadow-2xl w-full max-w-5xl h-[85vh] flex flex-col overflow-hidden animate-in">
                    <!-- Modal Header -->
                    <div class="p-6 border-b flex justify-between items-center" style="border-color: var(--border-primary); background-color: var(--bg-secondary);">
                        <div class="flex items-center gap-3">
                            <div class="p-2 rounded-lg" style="background-color: var(--bg-tertiary);">
                                <i :data-lucide="preview.type === 'pdf' ? 'file' : 'file-text'" class="w-5 h-5" style="color: var(--cmu-purple);"></i>
                            </div>
                            <span class="font-bold" style="color: var(--text-primary);" x-text="preview.fileName"></span>
                        </div>
                        <button 
                            @click="closePreview()" 
                            class="p-2 rounded-xl transition-all hover:bg-opacity-10 hover:rotate-90">
                            <i data-lucide="x" class="w-6 h-6" style="color: var(--text-secondary);"></i>
                        </button>
                    </div>

                    <!-- Modal Content -->
                    <div class="flex-1 overflow-hidden relative" style="background-color: var(--bg-tertiary);">
                        <!-- Loading State -->
                        <div x-show="preview.loading" class="h-full flex flex-col items-center justify-center">
                            <div class="w-16 h-16 border-4 rounded-full animate-spin mb-4" 
                                 style="border-color: var(--bg-tertiary); border-top-color: var(--cmu-purple);"></div>
                            <p class="text-lg font-bold" style="color: var(--text-secondary);">Loading...</p>
                        </div>

                        <!-- Text Editor -->
                        <textarea 
                            x-show="!preview.loading && preview.type === 'txt'" 
                            x-model="preview.content" 
                            class="w-full h-full p-6 font-mono text-sm outline-none resize-none"
                            style="background-color: var(--bg-secondary); color: var(--text-primary); border: none;">
                        </textarea>

                        <!-- PDF Viewer -->
                        <iframe 
                            x-show="!preview.loading && preview.type === 'pdf'" 
                            :src="preview.url" 
                            class="w-full h-full border-none">
                        </iframe>
                    </div>

                    <!-- Modal Footer -->
                    <div class="p-6 border-t flex justify-between items-center" style="border-color: var(--border-primary); background-color: var(--bg-secondary);">
                        <div class="flex items-center gap-2">
                            <span class="text-sm font-medium" style="color: var(--text-tertiary);">
                                <template x-if="preview.type === 'txt'">
                                    Press Ctrl+S to save
                                </template>
                            </span>
                        </div>
                        <div class="flex gap-3">
                            <button 
                                @click="closePreview()" 
                                class="px-6 py-2 font-bold rounded-lg transition-all hover:bg-opacity-10"
                                style="background-color: var(--bg-tertiary); color: var(--text-primary);">
                                Close
                            </button>
                            <button 
                                x-show="preview.type === 'txt'" 
                                @click="saveContent()" 
                                :disabled="preview.saveLoading" 
                                class="px-6 py-2 gradient-cmu text-white font-bold rounded-lg btn-enterprise disabled:opacity-50 flex items-center gap-2">
                                <i :data-lucide="preview.saveLoading ? 'loader' : 'save'" class="w-4 h-4" :class="{'animate-spin': preview.saveLoading}"></i>
                                <span x-text="preview.saveLoading ? 'Saving...' : 'Save Changes'"></span>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Context Menu (FIXED: Only ONE context menu, outside main container) -->
        <div 
            x-show="contextMenu.show" 
            @click.away="contextMenu.show = false"
            :style="'position: fixed; top: ' + contextMenu.y + 'px; left: ' + contextMenu.x + 'px; z-index: 9999;'"
            x-transition
            class="card-enterprise rounded-lg shadow-2xl py-2 min-w-48"
            style="border: 1px solid var(--border-primary);">
            
            <button 
                @click="contextMenu.entry && (contextMenu.entry.type === 'dir' ? navigate(contextMenu.entry.path) : previewFile(contextMenu.entry)); contextMenu.show = false" 
                class="w-full px-4 py-2 text-left text-sm font-medium hover:bg-opacity-10 transition-colors flex items-center gap-3"
                style="color: var(--text-primary);">
                <i :data-lucide="contextMenu.entry?.type === 'dir' ? 'folder-open' : 'eye'" class="w-4 h-4" style="color: var(--cmu-purple);"></i>
                <span x-text="contextMenu.entry?.type === 'dir' ? 'Open' : 'Preview'"></span>
            </button>
            
            <button 
                @click="contextMenu.entry && renameItem(contextMenu.entry); contextMenu.show = false"
                class="w-full px-4 py-2 text-left text-sm font-medium hover:bg-opacity-10 transition-colors flex items-center gap-3"
                style="color: var(--text-primary);">
                <i data-lucide="edit-3" class="w-4 h-4" style="color: var(--cmu-purple);"></i>
                <span>Rename</span>
            </button>
            
            <div class="h-px my-1" style="background-color: var(--border-secondary);"></div>
            
            <button 
                @click="copyToClipboard([contextMenu.entry.path]); contextMenu.show = false"
                class="w-full px-4 py-2 text-left text-sm font-medium hover:bg-opacity-10 transition-colors flex items-center gap-3"
                style="color: var(--text-primary);">
                <i data-lucide="copy" class="w-4 h-4" style="color: var(--cmu-purple);"></i>
                <span>Copy</span>
            </button>
            
            <button 
                @click="cutToClipboard([contextMenu.entry.path]); contextMenu.show = false"
                class="w-full px-4 py-2 text-left text-sm font-medium hover:bg-opacity-10 transition-colors flex items-center gap-3"
                style="color: var(--text-primary);">
                <i data-lucide="scissors" class="w-4 h-4" style="color: var(--cmu-purple);"></i>
                <span>Cut</span>
            </button>
            
            <div class="h-px my-1" style="background-color: var(--border-secondary);"></div>
            
            <button 
                @click="contextMenu.entry && deleteItem(contextMenu.entry); contextMenu.show = false"
                class="w-full px-4 py-2 text-left text-sm font-medium hover:bg-opacity-10 transition-colors flex items-center gap-3"
                style="color: var(--danger);">
                <i data-lucide="trash-2" class="w-4 h-4"></i>
                <span>Delete</span>
            </button>
        </div>

        <style>
            .drag-active {
                border: 3px dashed var(--cmu-purple) !important;
                background-color: rgba(81, 45, 109, 0.02) !important;
            }

            .drag-over-folder {
                background-color: rgba(81, 45, 109, 0.15) !important;
                border: 2px solid var(--cmu-purple) !important;
                transform: scale(1.02);
                box-shadow: 0 4px 20px rgba(81, 45, 109, 0.3) !important;
            }

            .selected-item {
                animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
            }

            @keyframes pulse {
                0%, 100% {
                    opacity: 1;
                }
                50% {
                    opacity: 0.85;
                }
            }

            @keyframes shimmer {
                0% {
                    transform: translateX(-100%);
                }
                100% {
                    transform: translateX(100%);
                }
            }

            .animate-shimmer {
                animation: shimmer 2s infinite;
            }

            .select-none {
                user-select: none;
                -webkit-user-select: none;
                -moz-user-select: none;
                -ms-user-select: none;
            }

            .custom-scrollbar::-webkit-scrollbar {
                width: 8px;
                height: 8px;
            }

            .custom-scrollbar::-webkit-scrollbar-track {
                background: var(--bg-tertiary);
                border-radius: 10px;
            }

            .custom-scrollbar::-webkit-scrollbar-thumb {
                background: var(--cmu-purple);
                border-radius: 10px;
            }

            .custom-scrollbar::-webkit-scrollbar-thumb:hover {
                background: var(--cmu-purple-dark);
            }
        </style>
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
            
            // Keyboard shortcuts
            document.addEventListener('keydown', (e) => {
                if (e.ctrlKey && e.key === 's' && this.preview.open && this.preview.type === 'txt') {
                    e.preventDefault();
                    this.saveContent();
                }
                
                if (e.key === 'Escape') {
                    if (this.preview.open) {
                        this.closePreview();
                    } else if (this.contextMenu.show) {
                        this.contextMenu.show = false;
                    } else if (this.selectedPaths.length > 0) {
                        this.selectedPaths = [];
                        this.selectionMode = false;
                    }
                }
                
                if (e.ctrlKey && e.key === 'a' && !this.preview.open) {
                    e.preventDefault();
                    this.selectedPaths = this.filteredEntries.map(e => e.path);
                    this.selectionMode = true;
                }
                
                if (e.ctrlKey && e.key === 'c' && this.selectedPaths.length > 0 && !this.preview.open) {
                    e.preventDefault();
                    this.copyToClipboard();
                }
                
                if (e.ctrlKey && e.key === 'x' && this.selectedPaths.length > 0 && !this.preview.open) {
                    e.preventDefault();
                    this.cutToClipboard();
                }
                
                if (e.ctrlKey && e.key === 'v' && this.clipboard.paths.length > 0 && !this.preview.open) {
                    e.preventDefault();
                    this.pasteFromClipboard();
                }
                
                if (e.key === 'Delete' && this.selectedPaths.length > 0 && !this.preview.open) {
                    this.bulkDelete();
                }
            });
        },

        // Mouse Event Handlers
        handleItemMouseDown(event, entry) {
            if (event.button === 2) return;
            if (this.clipboard.paths.length > 0) return;

            event.preventDefault();
            
            if (this.longPressTimer) {
                clearTimeout(this.longPressTimer);
                this.longPressTimer = null;
            }

            this.longPressFired = false;

            this.longPressTimer = setTimeout(() => {
                this.selectionMode = true;
                this.longPressFired = true;
                
                if (!this.selectedPaths.includes(entry.path)) {
                    this.selectedPaths.push(entry.path);
                }
                
                this.longPressTimer = null;
            }, 500);
        },

        handleItemMouseUp(event, entry) {
            if (event.button === 2) return;

            if (this.clipboard.paths.length > 0) {
                if (entry.type === 'dir') {
                    this.navigate(entry.path);
                }
                return;
            }

            if (this.longPressTimer) {
                clearTimeout(this.longPressTimer);
                this.longPressTimer = null;
            }

            if (this.longPressFired) {
                this.longPressFired = false;
                return;
            }

            if (this.selectionMode) {
                this.toggleSelection(entry);
                return;
            }

            if (this.selectedPaths.length > 0) {
                this.selectionMode = true;
                this.toggleSelection(entry);
                return;
            }

            if (entry.type === 'dir') {
                this.navigate(entry.path);
            } else {
                this.previewFile(entry);
            }
        },

        toggleSelection(entry) {
            const index = this.selectedPaths.indexOf(entry.path);
            if (index > -1) {
                this.selectedPaths.splice(index, 1);
            } else {
                this.selectedPaths.push(entry.path);
            }

            if (this.selectedPaths.length === 0) {
                this.selectionMode = false;
            }
        },

        // Item Drag & Drop
        handleItemDragStart(event, entry) {
            if (this.longPressTimer) {
                clearTimeout(this.longPressTimer);
                this.longPressTimer = null;
            }

            if (!this.selectedPaths.includes(entry.path)) {
                this.selectedPaths = [entry.path];
            }

            this.draggedItems = this.selectedPaths.map(path => 
                this.fileSystem.entries.find(e => e.path === path)
            ).filter(e => e);

            event.dataTransfer.effectAllowed = 'move';
            event.dataTransfer.setData('application/json', JSON.stringify({
                type: 'internal',
                paths: this.selectedPaths
            }));

            event.target.style.opacity = '0.5';
        },

        handleItemDragEnd(event) {
            event.target.style.opacity = '1';
            this.draggedItems = [];
            this.draggedOver = null;
        },

        handleItemDragOver(event, entry) {
            if (entry.type !== 'dir') return;
            
            if (this.draggedItems.some(item => item.path === entry.path)) {
                event.dataTransfer.dropEffect = 'none';
                return;
            }

            event.dataTransfer.dropEffect = 'move';
            this.draggedOver = entry.path;
        },

        handleItemDragLeave(event, entry) {
            if (this.draggedOver === entry.path) {
                this.draggedOver = null;
            }
        },

        async handleItemDrop(event, targetEntry) {
            this.draggedOver = null;

            if (targetEntry.type !== 'dir') return;

            try {
                const data = JSON.parse(event.dataTransfer.getData('application/json'));
                
                if (data.type === 'internal') {
                    await this.moveItems(data.paths, targetEntry.path);
                }
            } catch (e) {
                console.error('Drop error:', e);
            }
        },

        async moveItems(sourcePaths, targetPath) {
            if (!sourcePaths || sourcePaths.length === 0) return;

            const finalTargetPath = targetPath || ""; 

            const token = localStorage.getItem('adminToken');
            const fd = new FormData();
            fd.append('root', this.fileSystem.root);
            fd.append('source_paths', JSON.stringify(sourcePaths));
            fd.append('target_path', finalTargetPath);

            console.log("๐“ฆ Moving Items:", {
                root: this.fileSystem.root,
                source_paths: JSON.stringify(sourcePaths),
                target_path: finalTargetPath
            });

            try {
                const response = await fetch('/api/admin/move', {
                    method: 'POST',
                    headers: { 'X-Admin-Token': token },
                    body: fd
                });

                if (response.ok) {
                    this.selectedPaths = [];
                    this.selectionMode = false;
                    await this.loadFiles();
                    return true;
                } else {
                    const errorData = await response.json();
                    // เธเธฃเธฑเธเธเธฒเธฃเนเธชเธ”เธ Error เนเธซเนเธฅเธฐเน€เธญเธตเธขเธ”เธเธถเนเธ
                    const msg = Array.isArray(errorData.detail) 
                        ? errorData.detail.map(e => `${e.loc.join('.')}: ${e.msg}`).join(" | ")
                        : (errorData.detail || 'Move failed');
                    throw new Error(msg);
                }
            } catch (e) {
                console.error('Move error:', e);
                alert('เนเธกเนเธชเธฒเธกเธฒเธฃเธ–เธขเนเธฒเธขเนเธเธฅเนเนเธ”เน: ' + e.message);
                throw e;
            }
        },

        get filteredEntries() { 
            return this.fileSystem.entries.filter(e => 
                e.name.toLowerCase().includes(this.searchQuery.toLowerCase())
            ); 
        },

        get sortedFilteredEntries() {
            let entries = [...this.filteredEntries];
            
            entries.sort((a, b) => {
                if (a.type !== b.type) {
                    return a.type === 'dir' ? -1 : 1;
                }
                
                let aVal, bVal;
                
                if (this.sortBy === 'name') {
                    aVal = a.name.toLowerCase();
                    bVal = b.name.toLowerCase();
                } else if (this.sortBy === 'size') {
                    aVal = this.getSizeInBytes(a.size);
                    bVal = this.getSizeInBytes(b.size);
                } else if (this.sortBy === 'type') {
                    aVal = a.ext || '';
                    bVal = b.ext || '';
                }
                
                if (aVal < bVal) return this.sortDesc ? 1 : -1;
                if (aVal > bVal) return this.sortDesc ? -1 : 1;
                return 0;
            });
            
            return entries;
        },

        getSizeInBytes(sizeStr) {
            if (!sizeStr || sizeStr === 'N/A') return 0;
            
            const match = sizeStr.match(/^([\d.]+)\s*(\w+)$/);
            if (!match) return 0;
            
            const value = parseFloat(match[1]);
            const unit = match[2].toUpperCase();
            
            const multipliers = {
                'B': 1,
                'KB': 1024,
                'MB': 1024 * 1024,
                'GB': 1024 * 1024 * 1024,
                'TB': 1024 * 1024 * 1024 * 1024
            };
            
            return value * (multipliers[unit] || 0);
        },

        toggleSort(field) {
            if (this.sortBy === field) {
                this.sortDesc = !this.sortDesc;
            } else {
                this.sortBy = field;
                this.sortDesc = false;
            }
        },

        getFileIcon(entry) {
            if (entry.type === 'dir') return 'folder';
            
            const ext = entry.ext?.toLowerCase() || '';
            
            if (ext === '.pdf') return 'file-text';
            if (ext === '.txt') return 'file-type';
            if (['.jpg', '.jpeg', '.png', '.gif', '.webp'].includes(ext)) return 'image';
            if (['.doc', '.docx'].includes(ext)) return 'file-text';
            if (['.xls', '.xlsx'].includes(ext)) return 'sheet';
            if (['.zip', '.rar', '.7z'].includes(ext)) return 'archive';
            if (['.mp3', '.wav', '.ogg'].includes(ext)) return 'music';
            if (['.mp4', '.avi', '.mov'].includes(ext)) return 'video';
            
            return 'file';
        },

        showContextMenu(event, entry) {
            if (this.clipboard.paths.length > 0) return;

            this.contextMenu = {
                show: true,
                x: event.clientX,
                y: event.clientY,
                entry: entry
            };
        },

        // External File Drag & Drop
        handleDragEnter(e) {
            const hasFiles = e.dataTransfer.types.includes('Files');
            const isInternal = e.dataTransfer.types.includes('application/json');
            
            if (hasFiles && !isInternal) {
                this.dragCounter++;
                this.dragging = true;
            }
        },

        handleDragLeave(e) {
            this.dragCounter--;
            if (this.dragCounter === 0) {
                this.dragging = false;
            }
        },

        handleDragOver(e) {
            const hasFiles = e.dataTransfer.types.includes('Files');
            if (hasFiles) {
                e.dataTransfer.dropEffect = 'copy';
            }
        },

        handleDrop(e) {
            this.dragCounter = 0;
            this.dragging = false;
            
            const files = Array.from(e.dataTransfer.files);
            if (files.length > 0) {
                this.executeUploadBatch(files);
            }
        },

        async switchRoot(root) { 
            this.fileSystem.root = root; 
            this.fileSystem.current_path = ''; 
            this.selectedPaths = [];
            this.selectionMode = false;
            await this.loadFiles(); 
        },

        async navigate(path) { 
            this.fileSystem.current_path = path;
            this.selectedPaths = [];
            this.selectionMode = false;
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
            if (this.isAllSelected()) {
                this.selectedPaths = [];
                this.selectionMode = false;
            } else {
                this.selectedPaths = this.filteredEntries.map(e => e.path);
                this.selectionMode = true;
            }
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
            
            setTimeout(() => {
                this.uploadStatus = { total: 0, done: 0 };
            }, 2000);
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
                alert('เนเธซเธฅเธ”เนเธเธฅเนเนเธกเนเธชเธณเน€เธฃเนเธ'); 
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
                
                alert('เธเธฑเธเธ—เธถเธเธชเธณเน€เธฃเนเธ!');
            } catch(e) { 
                alert('เธเธฑเธเธ—เธถเธเนเธกเนเธชเธณเน€เธฃเนเธ'); 
            } finally { 
                this.preview.saveLoading = false; 
            }
        },

        closePreview() { 
            this.preview.open = false; 
            if (this.preview.url) URL.revokeObjectURL(this.preview.url); 
        },

        async createNewFolder() {
            const name = prompt("เธฃเธฐเธเธธเธเธทเนเธญเนเธเธฅเน€เธ”เธญเธฃเน:"); 
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
                alert('เธชเธฃเนเธฒเธเนเธเธฅเน€เธ”เธญเธฃเนเนเธกเนเธชเธณเน€เธฃเนเธ');
            }
        },

        async renameItem(entry) {
            const newName = prompt(`เน€เธเธฅเธตเนเธขเธเธเธทเนเธญ "${entry.name}" เน€เธเนเธ:`, entry.name); 
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
                alert('เน€เธเธฅเธตเนเธขเธเธเธทเนเธญเนเธกเนเธชเธณเน€เธฃเนเธ');
            }
        },

        async deleteItem(entry) {
            if (!confirm(`เธ•เนเธญเธเธเธฒเธฃเธฅเธ "${entry.name}"?`)) return;
            
            try {
                await fetch(`/api/admin/files?root=${this.fileSystem.root}&paths=${encodeURIComponent(JSON.stringify([entry.path]))}`, { 
                    method: 'DELETE', 
                    headers: { 'X-Admin-Token': localStorage.getItem('adminToken') } 
                });
                await this.loadFiles();
            } catch(e) {
                alert('เธฅเธเนเธเธฅเนเนเธกเนเธชเธณเน€เธฃเนเธ');
            }
        },

        async bulkDelete() {
            if (this.selectedPaths.length === 0) return;
            
            if (!confirm(`เธ•เนเธญเธเธเธฒเธฃเธฅเธ ${this.selectedPaths.length} เธฃเธฒเธขเธเธฒเธฃเธ—เธตเนเน€เธฅเธทเธญเธ?`)) return;
            
            try {
                await fetch(`/api/admin/files?root=${this.fileSystem.root}&paths=${encodeURIComponent(JSON.stringify(this.selectedPaths))}`, { 
                    method: 'DELETE', 
                    headers: { 'X-Admin-Token': localStorage.getItem('adminToken') } 
                });
                this.selectedPaths = [];
                this.selectionMode = false;
                await this.loadFiles();
                alert('เธฅเธเน€เธฃเธตเธขเธเธฃเนเธญเธขเนเธฅเนเธง!');
            } catch(e) {
                alert('เธฅเธเนเธกเนเธชเธณเน€เธฃเนเธ');
            }
        },

        // Clipboard Operations
        copyToClipboard(paths = null) {
            this.clipboard = {
                action: 'copy',
                paths: paths || [...this.selectedPaths]
            };
            
            this.selectedPaths = [];
            this.selectionMode = false;
            
            console.log(`๐“ Copied ${this.clipboard.paths.length} item(s) to clipboard`);
        },

        cutToClipboard(paths = null) {
            this.clipboard = {
                action: 'cut',
                paths: paths || [...this.selectedPaths]
            };
            
            this.selectedPaths = [];
            this.selectionMode = false;
            
            console.log(`โ๏ธ Cut ${this.clipboard.paths.length} item(s) to clipboard`);
        },

        async pasteFromClipboard() {
            if (this.clipboard.paths.length === 0) {
                alert('เนเธกเนเธกเธตเธฃเธฒเธขเธเธฒเธฃเนเธเธเธฅเธดเธเธเธญเธฃเนเธ”');
                return;
            }

            const action = this.clipboard.action;
            const sourcePaths = this.clipboard.paths;
            const targetPath = this.fileSystem.current_path;

            try {
                if (action === 'cut') {
                    const success = await this.moveItems(sourcePaths, targetPath);
                    if (success) alert(`โ… เธขเนเธฒเธข ${sourcePaths.length} เธฃเธฒเธขเธเธฒเธฃเน€เธฃเธตเธขเธเธฃเนเธญเธข!`);
                } else if (action === 'copy') {
                    const fd = new FormData();
                    fd.append('root', this.fileSystem.root);
                    fd.append('source_paths', JSON.stringify(sourcePaths));
                    fd.append('target_path', targetPath);

                    const response = await fetch('/api/admin/copy', {
                        method: 'POST',
                        headers: { 'X-Admin-Token': localStorage.getItem('adminToken') },
                        body: fd
                    });

                    if (response.ok) {
                        alert(`โ… เธเธฑเธ”เธฅเธญเธ ${sourcePaths.length} เธฃเธฒเธขเธเธฒเธฃเน€เธฃเธตเธขเธเธฃเนเธญเธข!`);
                    } else {
                        // Parse error response
                        let errorMessage = 'Copy failed';
                        try {
                            const errorData = await response.json();
                            errorMessage = errorData.detail || errorData.message || JSON.stringify(errorData);
                        } catch (jsonError) {
                            const errorText = await response.text();
                            errorMessage = errorText || `HTTP ${response.status}: ${response.statusText}`;
                        }
                        throw new Error(errorMessage);
                    }
                }

                this.clipboard = { action: null, paths: [] };
                
                await this.loadFiles();
                this.selectedPaths = [];
                this.selectionMode = false;
            } catch (e) {
                console.error('Paste error:', e);
                const errorMsg = e.message || String(e);
                alert('โ เธเธฒเธฃเธงเธฒเธ (Paste) เธฅเนเธกเน€เธซเธฅเธง: ' + errorMsg);
            }
        },

        async processRAG() {
            if (this.fileSystem.root !== 'data') {
                alert('เธเธฃเธธเธ“เธฒเน€เธเธฅเธตเนเธขเธเนเธเธ—เธตเน PDF Files เธเนเธญเธเธ—เธณเธเธฒเธฃเนเธเธฅเธเนเธเธฅเน');
                return;
            }
            
            if (!confirm('เธ•เนเธญเธเธเธฒเธฃเนเธเธฅเธเนเธเธฅเน PDF เธ—เธฑเนเธเธซเธกเธ”เน€เธเนเธ TXT เธชเธณเธซเธฃเธฑเธเธฃเธฐเธเธ RAG?\n\nเธเธฃเธฐเธเธงเธเธเธฒเธฃเธเธตเนเธญเธฒเธเนเธเนเน€เธงเธฅเธฒเธซเธฅเธฒเธขเธเธฒเธ—เธต')) {
                return;
            }
            
            this.processing = true;
            
            try {
                const response = await fetch('/api/admin/process-rag', { 
                    method: 'POST', 
                    headers: { 'X-Admin-Token': localStorage.getItem('adminToken') } 
                });
                
                if (response.ok) {
                    alert('โ… เนเธเธฅเธเนเธเธฅเน PDF เน€เธเนเธ TXT เธชเธณเน€เธฃเนเธ!\n\nเธฃเธฐเธเธ RAG เธเธฃเนเธญเธกเนเธเนเธเธฒเธเนเธฅเนเธง');
                } else {
                    throw new Error('Process failed');
                }
            } catch(e) { 
                alert('โ เธเธฒเธฃเนเธเธฅเธเนเธเธฅเนเธฅเนเธกเน€เธซเธฅเธง\n\nเธเธฃเธธเธ“เธฒเธฅเธญเธเนเธซเธกเนเธญเธตเธเธเธฃเธฑเนเธ'); 
                console.error('RAG processing error:', e);
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
