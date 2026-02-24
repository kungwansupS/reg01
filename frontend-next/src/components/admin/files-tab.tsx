"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Upload, Trash2, Download, Eye, FolderOpen, FolderPlus, RefreshCw, X,
  ArrowLeft, Home, Search, Grid3X3, List, FileText, Database, Zap, ChevronRight, File, Folder,
} from "lucide-react";
import { adminFetch, adminFormPost } from "@/lib/api";
import { cn } from "@/lib/utils";

interface FileEntry {
  name: string;
  size: string;
  type: "file" | "dir";
  path: string;
  ext?: string;
}

export function FilesTab() {
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [root, setRoot] = useState<"data" | "uploads">("data");
  const [currentPath, setCurrentPath] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [viewing, setViewing] = useState<string | null>(null);
  const [viewContent, setViewContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [uploadProgress, setUploadProgress] = useState({ total: 0, done: 0 });

  const loadFiles = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ root });
      if (currentPath) params.set("path", currentPath);
      const res = await adminFetch(`/api/admin/files?${params}`);
      if (res.ok) {
        const data = await res.json();
        setEntries(data.entries || []);
      }
    } catch { /* ignore */ }
    setLoading(false);
  }, [root, currentPath]);

  useEffect(() => { loadFiles(); }, [loadFiles]);

  function navigate(path: string) { setCurrentPath(path); }
  function navigateBack() {
    const parts = currentPath.split("/").filter(Boolean);
    parts.pop();
    setCurrentPath(parts.join("/"));
  }
  function navigateByParts(index: number) {
    const parts = currentPath.split("/").filter(Boolean);
    setCurrentPath(parts.slice(0, index + 1).join("/"));
  }
  function switchRoot(r: "data" | "uploads") { setRoot(r); setCurrentPath(""); }

  function handleEntryClick(entry: FileEntry) {
    if (entry.type === "dir") {
      navigate(entry.path);
    } else {
      handleView(entry.path);
    }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setUploadProgress({ total: files.length, done: 0 });
    for (let i = 0; i < files.length; i++) {
      const form = new FormData();
      form.append("file", files[i]);
      form.append("root", root);
      form.append("target_dir", currentPath);
      try { await adminFormPost("/api/admin/upload", form); } catch { /* ignore */ }
      setUploadProgress((prev) => ({ ...prev, done: prev.done + 1 }));
    }
    setUploadProgress({ total: 0, done: 0 });
    await loadFiles();
    e.target.value = "";
  }

  async function createFolder() {
    const name = prompt("New folder name:");
    if (!name) return;
    const form = new FormData();
    form.append("root", root);
    form.append("path", currentPath ? `${currentPath}/${name}` : name);
    try {
      await adminFetch("/api/admin/mkdir", { method: "POST", body: form });
      await loadFiles();
    } catch { /* ignore */ }
  }

  async function handleDelete(entry: FileEntry) {
    if (!confirm(`Delete ${entry.name}?`)) return;
    try {
      const paths = JSON.stringify([entry.path]);
      await adminFetch(`/api/admin/files?root=${root}&paths=${encodeURIComponent(paths)}`, { method: "DELETE" });
      await loadFiles();
    } catch { /* ignore */ }
  }

  async function handleView(path: string) {
    try {
      const res = await adminFetch(`/api/admin/view?root=${root}&path=${encodeURIComponent(path)}`);
      if (res.ok) {
        const ct = res.headers.get("content-type") || "";
        if (ct.includes("json")) {
          const data = await res.json();
          setViewContent(typeof data === "string" ? data : JSON.stringify(data, null, 2));
        } else {
          setViewContent(await res.text());
        }
        setViewing(path);
      }
    } catch { /* ignore */ }
  }

  async function handleDownload(path: string, name: string) {
    try {
      const res = await adminFetch(`/api/admin/view?root=${root}&path=${encodeURIComponent(path)}`);
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url; a.download = name; a.click();
        URL.revokeObjectURL(url);
      }
    } catch { /* ignore */ }
  }

  async function processRAG() {
    if (root !== "data" || processing) return;
    setProcessing(true);
    try {
      await adminFetch("/api/admin/process-rag", { method: "POST" });
      await loadFiles();
    } catch { /* ignore */ }
    setProcessing(false);
  }

  function getFileIcon(entry: FileEntry) {
    if (entry.type === "dir") return Folder;
    const ext = entry.ext?.toLowerCase() || entry.name.split(".").pop()?.toLowerCase() || "";
    if (["pdf"].includes(ext)) return FileText;
    if (["txt", "md", "csv", "log"].includes(ext)) return File;
    return File;
  }

  const pathParts = currentPath.split("/").filter(Boolean);
  const filtered = searchQuery
    ? entries.filter((e) => e.name.toLowerCase().includes(searchQuery.toLowerCase()))
    : entries;
  const sorted = [...filtered].sort((a, b) => {
    if (a.type !== b.type) return a.type === "dir" ? -1 : 1;
    return a.name.localeCompare(b.name);
  });

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-6 pb-4">
        <h1 className="text-3xl md:text-4xl font-black gradient-text-cmu mb-1">File Explorer</h1>
        <p className="text-sm text-yt-text-muted">Modern Document Management System</p>
      </div>

      {/* Toolbar */}
      <div className="mx-6 yt-card rounded-2xl shadow-lg mb-4 overflow-hidden">
        {/* Navigation Bar */}
        <div className="p-4 border-b border-yt-border">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1">
              <button onClick={navigateBack} disabled={!currentPath} className="p-2 rounded-lg transition-all disabled:opacity-30 hover:bg-yt-surface-hover" title="Back">
                <ArrowLeft className="w-5 h-5" />
              </button>
              <button onClick={() => navigate("")} className="p-2 rounded-lg transition-all hover:bg-yt-surface-hover" title="Home">
                <Home className="w-5 h-5" />
              </button>
            </div>

            {/* Breadcrumb */}
            <div className="flex-1 flex items-center gap-2 px-4 py-2.5 rounded-lg overflow-x-auto custom-scrollbar bg-yt-surface-hover">
              <FolderOpen className="w-4 h-4 shrink-0 text-accent" />
              <button onClick={() => navigate("")} className="font-bold text-sm hover:underline text-accent shrink-0">Root</button>
              {pathParts.map((part, i) => (
                <div key={i} className="flex items-center gap-2 shrink-0">
                  <ChevronRight className="w-4 h-4 text-yt-text-muted" />
                  <button onClick={() => navigateByParts(i)} className="font-bold text-sm hover:underline text-accent">{part}</button>
                </div>
              ))}
            </div>

            {/* View Mode Toggle */}
            <div className="flex items-center gap-1 p-1 rounded-lg bg-yt-surface-hover">
              <button onClick={() => setViewMode("grid")} className={cn("p-2 rounded transition-all", viewMode === "grid" ? "bg-accent text-white shadow" : "text-yt-text-muted")} title="Grid">
                <Grid3X3 className="w-4 h-4" />
              </button>
              <button onClick={() => setViewMode("list")} className={cn("p-2 rounded transition-all", viewMode === "list" ? "bg-accent text-white shadow" : "text-yt-text-muted")} title="List">
                <List className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Action Bar */}
        <div className="p-4 flex flex-col md:flex-row gap-4">
          {/* Root Selector */}
          <div className="flex items-center gap-2 p-1 rounded-xl shrink-0 bg-yt-surface-hover">
            <button onClick={() => switchRoot("data")} className={cn("px-4 py-2.5 rounded-lg font-bold text-sm flex items-center gap-2 transition-all", root === "data" ? "bg-accent text-white shadow-lg" : "text-yt-text-muted")}>
              <FileText className="w-4 h-4" /> PDF Files
            </button>
            <button onClick={() => switchRoot("uploads")} className={cn("px-4 py-2.5 rounded-lg font-bold text-sm flex items-center gap-2 transition-all", root === "uploads" ? "bg-accent text-white shadow-lg" : "text-yt-text-muted")}>
              <Database className="w-4 h-4" /> RAG Database
            </button>
          </div>

          {/* Search */}
          <div className="flex-1 relative">
            <Search className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-yt-text-muted" />
            <input value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="ค้นหาไฟล์หรือโฟลเดอร์..." className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-yt-border bg-yt-surface-hover outline-none focus:ring-2 focus:ring-accent/50 text-sm" />
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2 shrink-0">
            <button onClick={createFolder} className="px-4 py-2.5 rounded-lg font-bold text-sm flex items-center gap-2 bg-accent text-white hover:bg-accent/90 shadow">
              <FolderPlus className="w-4 h-4" /> <span className="hidden lg:inline">New Folder</span>
            </button>
            <label className="px-4 py-2.5 rounded-lg font-bold text-sm flex items-center gap-2 bg-warning text-white hover:bg-warning/90 shadow cursor-pointer">
              <Upload className="w-4 h-4" /> <span className="hidden lg:inline">Upload Files</span>
              <input type="file" multiple className="hidden" onChange={handleUpload} />
            </label>
            <button onClick={processRAG} disabled={processing || root !== "data"} className={cn("px-4 py-2.5 rounded-lg font-bold text-sm flex items-center gap-2 transition-all disabled:opacity-40 disabled:cursor-not-allowed", processing ? "bg-yt-text-muted text-white" : "bg-success text-white hover:bg-success/90")} title={root !== "data" ? "Available only in PDF Files view" : "Auto convert PDF→TXT for RAG"}>
              <Zap className={cn("w-4 h-4", processing && "animate-spin")} /> <span className="hidden lg:inline">{processing ? "Processing..." : "Auto PDF→TXT"}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Upload Progress */}
      {uploadProgress.total > 0 && uploadProgress.done < uploadProgress.total && (
        <div className="mx-6 yt-card p-4 rounded-xl shadow-lg mb-4 border-l-4 border-l-accent">
          <div className="flex justify-between mb-2 font-bold text-sm text-accent">
            <span className="flex items-center gap-2"><Upload className="w-4 h-4" /> Uploading files...</span>
            <span>{uploadProgress.done}/{uploadProgress.total}</span>
          </div>
          <div className="w-full h-2 rounded-full bg-yt-surface-hover overflow-hidden">
            <div className="bg-accent h-2 transition-all" style={{ width: `${(uploadProgress.done / uploadProgress.total) * 100}%` }} />
          </div>
        </div>
      )}

      {/* File Grid/List */}
      <div className="mx-6 mb-6 yt-card rounded-2xl shadow-lg flex-1 overflow-hidden" style={{ minHeight: 400 }}>
        {loading ? (
          <div className="flex items-center justify-center h-full"><p className="text-yt-text-muted">Loading...</p></div>
        ) : viewMode === "grid" ? (
          <div className="p-6 overflow-y-auto h-full custom-scrollbar">
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
              {sorted.map((entry) => {
                const Icon = getFileIcon(entry);
                return (
                  <div key={entry.path} onClick={() => handleEntryClick(entry)} className="group cursor-pointer transition-all hover:scale-105">
                    <div className="yt-card p-4 rounded-xl hover:shadow-lg border-2 border-transparent hover:border-accent/30">
                      <div className={cn("w-full aspect-square rounded-lg mb-3 flex items-center justify-center", entry.type === "dir" ? "bg-accent/10" : "bg-warning/10")}>
                        <Icon className={cn("w-12 h-12 transition-transform group-hover:scale-110", entry.type === "dir" ? "text-accent" : "text-warning")} />
                      </div>
                      <p className="font-bold text-sm text-center truncate mb-1" title={entry.name}>{entry.name}</p>
                      <p className="text-xs text-center text-yt-text-muted">{entry.size}</p>
                    </div>
                  </div>
                );
              })}
            </div>
            {sorted.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full py-20">
                <FolderOpen className="w-16 h-16 text-yt-border mb-4" />
                <p className="text-lg font-bold text-yt-text-muted mb-1">No files found</p>
                <p className="text-sm text-yt-text-muted">{searchQuery ? "Try a different search term" : "Drag and drop files here or click Upload"}</p>
              </div>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto h-full">
            <table className="yt-table w-full">
              <thead>
                <tr>
                  <th className="text-left">Name</th>
                  <th className="text-left hidden md:table-cell">Type</th>
                  <th className="text-left w-32">Size</th>
                  <th className="text-right w-40">Actions</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((entry) => {
                  const Icon = getFileIcon(entry);
                  return (
                    <tr key={entry.path} className="group cursor-pointer hover:bg-yt-surface-hover" onClick={() => handleEntryClick(entry)}>
                      <td>
                        <div className="flex items-center gap-3">
                          <div className={cn("p-2 rounded-lg", entry.type === "dir" ? "bg-accent/10 text-accent" : "bg-warning/10 text-warning")}>
                            <Icon className="w-5 h-5" />
                          </div>
                          <span className="font-semibold">{entry.name}</span>
                        </div>
                      </td>
                      <td className="text-sm text-yt-text-muted hidden md:table-cell">
                        <span className={cn("yt-badge", entry.type === "dir" ? "yt-badge-purple" : "yt-badge-yellow")}>
                          {entry.type === "dir" ? "Folder" : (entry.ext || "File")}
                        </span>
                      </td>
                      <td className="text-sm text-yt-text-muted">{entry.size}</td>
                      <td className="text-right" onClick={(e) => e.stopPropagation()}>
                        {entry.type === "file" && (
                          <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition">
                            <button onClick={() => handleView(entry.path)} className="yt-btn-icon" title="View"><Eye className="w-4 h-4" /></button>
                            <button onClick={() => handleDownload(entry.path, entry.name)} className="yt-btn-icon" title="Download"><Download className="w-4 h-4" /></button>
                            <button onClick={() => handleDelete(entry)} className="yt-btn-icon text-danger" title="Delete"><Trash2 className="w-4 h-4" /></button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
                {sorted.length === 0 && (
                  <tr><td colSpan={4} className="text-center text-yt-text-muted py-20">No files found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* File viewer modal */}
      {viewing && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={() => setViewing(null)}>
          <div className="yt-card w-full max-w-5xl max-h-[85vh] flex flex-col rounded-3xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-yt-border bg-yt-surface-hover">
              <div className="flex items-center gap-3">
                <FileText className="w-5 h-5 text-accent" />
                <span className="font-bold text-sm">{viewing.split("/").pop()}</span>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => { const name = viewing.split("/").pop() || "file"; handleDownload(viewing, name); }} className="yt-btn yt-btn-secondary text-xs"><Download className="w-3.5 h-3.5" /> Download</button>
                <button onClick={() => setViewing(null)} className="yt-btn-icon"><X className="w-5 h-5" /></button>
              </div>
            </div>
            <pre className="flex-1 overflow-auto p-6 text-xs text-yt-text-secondary whitespace-pre-wrap custom-scrollbar font-mono leading-relaxed">{viewContent}</pre>
          </div>
        </div>
      )}
    </div>
  );
}
