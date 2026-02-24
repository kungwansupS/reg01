"use client";

import { useState, useCallback } from "react";
import { FolderOpen, File, ChevronRight, ChevronDown, RefreshCw, Save, Search, Play, ArrowUp } from "lucide-react";
import { devFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

interface TreeEntry {
  name: string;
  type: "file" | "dir";
  path: string;
  size?: number;
  children?: TreeEntry[];
}

export function WorkspaceTab() {
  const [tree, setTree] = useState<TreeEntry[]>([]);
  const [treePath, setTreePath] = useState("");
  const [treeStatus, setTreeStatus] = useState("");
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set());
  const [filePath, setFilePath] = useState("");
  const [fileContent, setFileContent] = useState("");
  const [fileLang, setFileLang] = useState("plaintext");
  const [fileDirty, setFileDirty] = useState(false);
  const [editorStatus, setEditorStatus] = useState("");
  const [runtimeSummary, setRuntimeSummary] = useState("");
  const [logPath, setLogPath] = useState("logs/user_audit.log");
  const [logContent, setLogContent] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchPath, setSearchPath] = useState("backend");
  const [searchCase, setSearchCase] = useState(false);
  const [searchRegex, setSearchRegex] = useState(false);
  const [searchResults, setSearchResults] = useState("");
  const [symbolName, setSymbolName] = useState("");
  const [symbolPath, setSymbolPath] = useState("backend");
  const [symbolResults, setSymbolResults] = useState("");
  const [shellCommand, setShellCommand] = useState("");
  const [shellCwd, setShellCwd] = useState("");
  const [shellTimeout, setShellTimeout] = useState(25);
  const [shellOutput, setShellOutput] = useState("");
  const [shellHistory, setShellHistory] = useState<string[]>([]);
  const [shellPreset, setShellPreset] = useState("");

  const loadTree = useCallback(async (path = treePath) => {
    setTreeStatus("Loading...");
    try {
      const res = await devFetch(`/api/dev/fs/tree?path=${encodeURIComponent(path)}&max_entries=200`);
      if (res.ok) {
        const data = await res.json();
        setTree(data.entries || []);
        setTreePath(data.path || path);
        setTreeStatus(`${(data.entries || []).length} items`);
      } else setTreeStatus("Error loading tree");
    } catch { setTreeStatus("Error"); }
  }, [treePath]);

  async function openFile(path: string) {
    setEditorStatus("Loading...");
    try {
      const res = await devFetch(`/api/dev/fs/read?path=${encodeURIComponent(path)}`);
      if (res.ok) {
        const data = await res.json();
        setFilePath(path);
        setFileContent(data.content || "");
        setFileLang(data.language || guessLang(path));
        setFileDirty(false);
        setEditorStatus(`Loaded: ${path}`);
      } else setEditorStatus("Error loading file");
    } catch { setEditorStatus("Error"); }
  }

  async function saveFile() {
    if (!filePath) return;
    setEditorStatus("Saving...");
    try {
      const res = await devFetch("/api/dev/fs/write", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: filePath, content: fileContent }),
      });
      if (res.ok) { setFileDirty(false); setEditorStatus("Saved!"); }
      else setEditorStatus("Save failed");
    } catch { setEditorStatus("Save error"); }
  }

  async function loadRuntime() {
    try {
      const res = await devFetch("/api/dev/runtime/summary");
      if (res.ok) setRuntimeSummary(JSON.stringify(await res.json(), null, 2));
      else setRuntimeSummary("Error loading runtime");
    } catch { setRuntimeSummary("Error"); }
  }

  async function tailLog() {
    try {
      const res = await devFetch(`/api/dev/logs/search?path=${encodeURIComponent(logPath)}&limit=50`);
      if (res.ok) {
        const data = await res.json();
        setLogContent(JSON.stringify(data.items || data, null, 2));
      }
    } catch { setLogContent("Error loading log"); }
  }

  async function doSearch() {
    if (!searchQuery) return;
    try {
      const params = new URLSearchParams({ q: searchQuery, path: searchPath });
      if (searchCase) params.set("case_sensitive", "1");
      if (searchRegex) params.set("regex", "1");
      const res = await devFetch(`/api/dev/fs/search?${params}`);
      if (res.ok) setSearchResults(JSON.stringify(await res.json(), null, 2));
      else setSearchResults("Error");
    } catch { setSearchResults("Error"); }
  }

  async function findSymbol() {
    if (!symbolName) return;
    try {
      const params = new URLSearchParams({ symbol: symbolName, path: symbolPath });
      const res = await devFetch(`/api/dev/fs/symbol?${params}`);
      if (res.ok) setSymbolResults(JSON.stringify(await res.json(), null, 2));
      else setSymbolResults("Error");
    } catch { setSymbolResults("Error"); }
  }

  async function runShell() {
    const cmd = shellCommand.trim();
    if (!cmd) return;
    setShellOutput("Running...");
    try {
      const res = await devFetch("/api/dev/shell/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: cmd, cwd: shellCwd || undefined, timeout_seconds: shellTimeout }),
      });
      if (res.ok) {
        const data = await res.json();
        setShellOutput(`Exit: ${data.exit_code}\n---\n${data.stdout || ""}${data.stderr ? `\n[STDERR]\n${data.stderr}` : ""}`);
        setShellHistory((prev) => [cmd, ...prev.filter((c) => c !== cmd)].slice(0, 20));
      } else setShellOutput(`Error: ${res.status}`);
    } catch (e) { setShellOutput(`Error: ${e}`); }
  }

  function toggleDir(path: string) {
    setExpandedDirs((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path); else next.add(path);
      return next;
    });
  }

  function guessLang(p: string) {
    if (p.endsWith(".py")) return "python";
    if (p.endsWith(".ts") || p.endsWith(".tsx")) return "typescript";
    if (p.endsWith(".js") || p.endsWith(".jsx")) return "javascript";
    if (p.endsWith(".json")) return "json";
    if (p.endsWith(".css")) return "css";
    if (p.endsWith(".html")) return "html";
    if (p.endsWith(".md")) return "markdown";
    return "plaintext";
  }

  function renderTree(entries: TreeEntry[], depth = 0) {
    return entries.map((e) => (
      <div key={e.path}>
        <div
          onClick={() => e.type === "dir" ? toggleDir(e.path) : openFile(e.path)}
          className={cn("flex items-center gap-1.5 py-1 px-1 rounded cursor-pointer text-xs hover:bg-[rgba(53,85,143,0.2)]", filePath === e.path && "bg-[var(--accent)]/10 border border-[var(--accent)]/40")}
          style={{ paddingLeft: `${depth * 16 + 4}px` }}
        >
          {e.type === "dir" ? (
            expandedDirs.has(e.path) ? <ChevronDown className="w-3 h-3 text-blue-400 shrink-0" /> : <ChevronRight className="w-3 h-3 text-blue-400 shrink-0" />
          ) : <span className="w-3" />}
          {e.type === "dir" ? <FolderOpen className="w-3.5 h-3.5 text-yellow-400 shrink-0" /> : <File className="w-3.5 h-3.5 text-gray-400 shrink-0" />}
          <span className="truncate">{e.name}</span>
        </div>
        {e.type === "dir" && expandedDirs.has(e.path) && e.children && renderTree(e.children, depth + 1)}
      </div>
    ));
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">Dev Workspace</h2>
      <p className="text-xs text-[var(--muted)]">จัดการไฟล์ backend/frontend, เขียนโค้ดแก้โค้ด, และดู runtime/logs ได้จากหน้า dev โดยตรง (local-only)</p>

      <div className="grid grid-cols-1 xl:grid-cols-[250px_1fr_1fr] gap-3">
        {/* File Explorer */}
        <div className="dev-panel space-y-2">
          <strong className="text-sm">Explorer</strong>
          <div className="flex gap-1">
            <button onClick={() => { setTreePath(""); loadTree(""); }} className="dev-btn text-xs">Root</button>
            <button onClick={() => { const p = treePath.split("/").slice(0, -1).join("/"); setTreePath(p); loadTree(p); }} className="dev-btn text-xs"><ArrowUp className="w-3 h-3" /></button>
            <button onClick={() => loadTree()} className="dev-btn text-xs"><RefreshCw className="w-3 h-3" /></button>
          </div>
          <p className="text-[10px] text-[var(--muted)]">{treeStatus}</p>
          <div className="dev-output min-h-[400px] max-h-[500px] overflow-auto font-mono text-xs">
            {tree.length > 0 ? renderTree(tree) : <p className="text-[var(--muted)] p-2">Click Root to load</p>}
          </div>
        </div>

        {/* Code Editor */}
        <div className="dev-panel space-y-2">
          <div className="grid grid-cols-[1fr_auto_auto_auto] gap-1">
            <input value={filePath} onChange={(e) => setFilePath(e.target.value)} placeholder="workspace relative path" className="dev-input text-xs" />
            <button onClick={() => openFile(filePath)} className="dev-btn text-xs">Open</button>
            <button onClick={() => openFile(filePath)} className="dev-btn text-xs"><RefreshCw className="w-3 h-3" /></button>
            <button onClick={saveFile} className="dev-btn-primary text-xs"><Save className="w-3 h-3" /> Save</button>
          </div>
          <p className="text-[10px] text-[var(--muted)]">{editorStatus || "No file opened"}</p>
          <div className="flex gap-2 text-[10px]">
            <span className="dev-chip text-blue-400 border-blue-500/40 bg-blue-500/10">{fileLang}</span>
            <span className={cn("dev-chip", fileDirty ? "text-red-400 border-red-500/40 bg-red-500/10" : "text-green-400 border-green-500/40 bg-green-500/10")}>{fileDirty ? "Unsaved" : "Saved"}</span>
          </div>
          <textarea
            value={fileContent}
            onChange={(e) => { setFileContent(e.target.value); setFileDirty(true); }}
            className="dev-input font-mono text-xs min-h-[500px] max-h-[600px] resize-y"
            spellCheck={false}
            placeholder="// Open file from explorer to edit code"
          />
        </div>

        {/* Runtime + Tools */}
        <div className="space-y-3">
          <div className="dev-panel space-y-2">
            <div className="flex items-center justify-between">
              <strong className="text-sm">Runtime Monitor</strong>
              <button onClick={loadRuntime} className="dev-btn text-xs"><RefreshCw className="w-3 h-3" /></button>
            </div>
            <pre className="dev-output text-xs max-h-32 overflow-auto">{runtimeSummary || "Click Refresh"}</pre>
            <div className="flex gap-1">
              <input value={logPath} onChange={(e) => setLogPath(e.target.value)} className="dev-input text-xs flex-1" />
              <button onClick={tailLog} className="dev-btn text-xs">Tail</button>
            </div>
            <pre className="dev-output text-xs max-h-40 overflow-auto">{logContent || "..."}</pre>
          </div>

          {/* Workspace Search */}
          <div className="dev-panel space-y-2">
            <div className="flex items-center justify-between">
              <strong className="text-sm">Workspace Search</strong>
              <button onClick={doSearch} className="dev-btn text-xs"><Search className="w-3 h-3" /> Search</button>
            </div>
            <input value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="search text or regex" className="dev-input text-xs" />
            <div className="flex gap-2 items-center">
              <input value={searchPath} onChange={(e) => setSearchPath(e.target.value)} placeholder="path scope" className="dev-input text-xs flex-1" />
              <label className="text-[10px] flex items-center gap-1"><input type="checkbox" checked={searchCase} onChange={() => setSearchCase(!searchCase)} /> case</label>
              <label className="text-[10px] flex items-center gap-1"><input type="checkbox" checked={searchRegex} onChange={() => setSearchRegex(!searchRegex)} /> regex</label>
            </div>
            <pre className="dev-output text-xs max-h-40 overflow-auto">{searchResults || "..."}</pre>
          </div>

          {/* Symbol Tools */}
          <div className="dev-panel space-y-2">
            <div className="flex items-center justify-between">
              <strong className="text-sm">Symbol Tools</strong>
              <button onClick={findSymbol} className="dev-btn text-xs">Find Symbol</button>
            </div>
            <div className="grid grid-cols-2 gap-1">
              <input value={symbolName} onChange={(e) => setSymbolName(e.target.value)} placeholder="function/class/variable" className="dev-input text-xs" />
              <input value={symbolPath} onChange={(e) => setSymbolPath(e.target.value)} placeholder="path scope" className="dev-input text-xs" />
            </div>
            <pre className="dev-output text-xs max-h-32 overflow-auto">{symbolResults || "..."}</pre>
          </div>

          {/* Command Runner */}
          <div className="dev-panel space-y-2">
            <div className="flex items-center justify-between">
              <strong className="text-sm">Command Runner</strong>
              <button onClick={runShell} className="dev-btn-primary text-xs"><Play className="w-3 h-3" /> Run</button>
            </div>
            <div className="flex gap-1">
              <select value={shellPreset} onChange={(e) => { setShellPreset(e.target.value); if (e.target.value) setShellCommand(e.target.value); }} className="dev-input text-xs flex-1">
                <option value="">-- presets --</option>
                <option value="python -m compileall backend">python -m compileall backend</option>
                <option value="python -m pytest -q">python -m pytest -q</option>
                <option value="git status --short">git status --short</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-1">
              <div className="flex flex-col gap-0.5">
                <label className="text-[10px] text-[var(--muted)]">Working Dir</label>
                <input value={shellCwd} onChange={(e) => setShellCwd(e.target.value)} placeholder="workspace root if empty" className="dev-input text-xs" />
              </div>
              <div className="flex flex-col gap-0.5">
                <label className="text-[10px] text-[var(--muted)]">Timeout (sec)</label>
                <input type="number" min={1} max={120} value={shellTimeout} onChange={(e) => setShellTimeout(Number(e.target.value))} className="dev-input text-xs" />
              </div>
            </div>
            <textarea value={shellCommand} onChange={(e) => setShellCommand(e.target.value)} placeholder="e.g. python -m pytest -q" className="dev-input text-xs min-h-[50px] font-mono resize-y" />
            <pre className="dev-output text-xs max-h-48 overflow-auto">{shellOutput || "..."}</pre>
            {shellHistory.length > 0 && (
              <div className="text-[10px] text-[var(--muted)]">
                <p>Recent:</p>
                {shellHistory.slice(0, 5).map((cmd, i) => (
                  <button key={i} onClick={() => setShellCommand(cmd)} className="block w-full text-left p-1 hover:bg-[rgba(53,85,143,0.2)] rounded truncate font-mono">{cmd}</button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
