"use client";

import { useState, useEffect, useCallback } from "react";
import { Upload, Trash2, Download, Eye, FolderOpen, RefreshCw } from "lucide-react";
import { adminFetch, adminFormPost } from "@/lib/api";

interface FileItem {
  name: string;
  size: number;
  modified?: string;
  type?: string;
}

export function FilesTab() {
  const [files, setFiles] = useState<{ docs: FileItem[]; quick_use: FileItem[] }>({ docs: [], quick_use: [] });
  const [activeFolder, setActiveFolder] = useState<"docs" | "quick_use">("docs");
  const [viewing, setViewing] = useState<string | null>(null);
  const [viewContent, setViewContent] = useState("");
  const [loading, setLoading] = useState(true);

  const loadFiles = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminFetch("/api/admin/files");
      if (res.ok) {
        const data = await res.json();
        setFiles({ docs: data.docs || [], quick_use: data.quick_use || [] });
      }
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { loadFiles(); }, [loadFiles]);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("folder", activeFolder);
    try {
      await adminFormPost("/api/admin/files/upload", form);
      await loadFiles();
    } catch { /* ignore */ }
    e.target.value = "";
  }

  async function handleDelete(filename: string) {
    if (!confirm(`Delete ${filename}?`)) return;
    try {
      await adminFetch(`/api/admin/files/${activeFolder}/${encodeURIComponent(filename)}`, { method: "DELETE" });
      await loadFiles();
    } catch { /* ignore */ }
  }

  async function handleView(filename: string) {
    try {
      const res = await adminFetch(`/api/admin/files/${activeFolder}/${encodeURIComponent(filename)}`);
      if (res.ok) {
        const text = await res.text();
        setViewContent(text);
        setViewing(filename);
      }
    } catch { /* ignore */ }
  }

  async function handleDownload(filename: string) {
    try {
      const res = await adminFetch(`/api/admin/files/${activeFolder}/${encodeURIComponent(filename)}`);
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch { /* ignore */ }
  }

  const currentFiles = activeFolder === "docs" ? files.docs : files.quick_use;

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">File Explorer</h1>
        <div className="flex gap-2">
          <button onClick={loadFiles} className="p-2 bg-zinc-800 rounded-lg hover:bg-zinc-700">
            <RefreshCw className="w-4 h-4" />
          </button>
          <label className="gradient-cmu text-white px-4 py-2 rounded-lg cursor-pointer flex items-center gap-2 text-sm font-medium">
            <Upload className="w-4 h-4" /> Upload
            <input type="file" className="hidden" onChange={handleUpload} />
          </label>
        </div>
      </div>

      <div className="flex gap-2">
        {(["docs", "quick_use"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setActiveFolder(f)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition ${
              activeFolder === f ? "bg-cmu-purple/20 text-cmu-purple-light" : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
            }`}
          >
            <FolderOpen className="w-4 h-4" /> {f === "docs" ? "Documents" : "Quick Use"}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-zinc-500">Loading files...</p>
      ) : (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800 text-zinc-500 text-left">
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3 w-28">Size</th>
                <th className="px-4 py-3 w-40">Actions</th>
              </tr>
            </thead>
            <tbody>
              {currentFiles.map((f) => (
                <tr key={f.name} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
                  <td className="px-4 py-3 font-mono text-xs">{f.name}</td>
                  <td className="px-4 py-3 text-zinc-500 text-xs">{(f.size / 1024).toFixed(1)} KB</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1">
                      <button onClick={() => handleView(f.name)} className="p-1.5 hover:bg-zinc-700 rounded" title="View">
                        <Eye className="w-3.5 h-3.5" />
                      </button>
                      <button onClick={() => handleDownload(f.name)} className="p-1.5 hover:bg-zinc-700 rounded" title="Download">
                        <Download className="w-3.5 h-3.5" />
                      </button>
                      <button onClick={() => handleDelete(f.name)} className="p-1.5 hover:bg-red-900/30 text-red-400 rounded" title="Delete">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {currentFiles.length === 0 && (
                <tr><td colSpan={3} className="px-4 py-8 text-center text-zinc-600">No files</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {viewing && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-8" onClick={() => setViewing(null)}>
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-3xl max-h-[80vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
              <span className="font-mono text-sm">{viewing}</span>
              <button onClick={() => setViewing(null)} className="text-zinc-400 hover:text-white">✕</button>
            </div>
            <pre className="flex-1 overflow-auto p-4 text-xs text-zinc-300 whitespace-pre-wrap custom-scrollbar">{viewContent}</pre>
          </div>
        </div>
      )}
    </div>
  );
}
