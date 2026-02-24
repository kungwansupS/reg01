"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { Search, Download, RefreshCw, Clock, ArrowUp, ArrowDown, ChevronsUpDown, ChevronLeft, ChevronRight, X, Zap } from "lucide-react";
import { adminFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

interface LogEntry {
  timestamp?: string;
  anon_id?: string;
  platform?: string;
  input?: string;
  output?: string;
  latency?: number;
  rating?: number;
  tokens?: { prompt?: number; completion?: number; total?: number; cost_usd?: number; cached?: boolean };
}

export function LogsTab() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [query, setQuery] = useState("");
  const [sortBy, setSortBy] = useState<"timestamp" | "latency" | "anon_id">("timestamp");
  const [sortDesc, setSortDesc] = useState(true);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<LogEntry | null>(null);
  const perPage = 20;

  const loadLogs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminFetch("/api/admin/stats");
      if (res.ok) {
        const data = await res.json();
        setLogs(data.recent_logs || data.recent_activity || []);
      }
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { loadLogs(); }, [loadLogs]);

  const filtered = useMemo(() => {
    let list = [...logs];
    if (query) {
      const q = query.toLowerCase();
      list = list.filter((l) =>
        (l.input || "").toLowerCase().includes(q) ||
        (l.output || "").toLowerCase().includes(q) ||
        (l.anon_id || "").toLowerCase().includes(q) ||
        (l.platform || "").toLowerCase().includes(q)
      );
    }
    list.sort((a, b) => {
      let aVal: string | number | Date = (a as Record<string, unknown>)[sortBy] as string | number;
      let bVal: string | number | Date = (b as Record<string, unknown>)[sortBy] as string | number;
      if (sortBy === "timestamp") { aVal = new Date(aVal as string); bVal = new Date(bVal as string); }
      if (aVal < bVal) return sortDesc ? 1 : -1;
      if (aVal > bVal) return sortDesc ? -1 : 1;
      return 0;
    });
    return list;
  }, [logs, query, sortBy, sortDesc]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / perPage));
  const paginated = filtered.slice((page - 1) * perPage, page * perPage);

  const avgLatency = logs.length > 0 ? (logs.reduce((s, l) => s + (l.latency || 0), 0) / logs.length).toFixed(0) : "0";
  const totalTokens = logs.reduce((s, l) => s + (l.tokens?.total || 0), 0);

  function fmtTimestamp(ts?: string) {
    if (!ts) return "--";
    const d = new Date(ts);
    return `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}/${d.getFullYear()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;
  }

  function handleExport() {
    const blob = new Blob([JSON.stringify(logs, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `audit_logs_${new Date().toISOString().slice(0, 10)}.json`; a.click();
    URL.revokeObjectURL(url);
  }

  function toggleSort(col: typeof sortBy) {
    if (sortBy === col) setSortDesc(!sortDesc);
    else { setSortBy(col); setSortDesc(true); }
    setPage(1);
  }

  function SortIcon({ col }: { col: typeof sortBy }) {
    if (sortBy !== col) return <ChevronsUpDown className="w-4 h-4" />;
    return sortDesc ? <ArrowDown className="w-4 h-4" /> : <ArrowUp className="w-4 h-4" />;
  }

  return (
    <div className="p-6 md:p-10 space-y-6 overflow-y-auto custom-scrollbar">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl md:text-4xl font-black gradient-text-cmu mb-1">Audit Logs</h1>
          <p className="text-sm text-yt-text-muted">System Activity Monitoring & Analytics</p>
        </div>
        <button onClick={handleExport} className="yt-btn yt-btn-secondary text-xs shrink-0">
          <Download className="w-3.5 h-3.5" /> Export JSON
        </button>
      </div>

      {/* Stats Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="yt-card p-6">
          <p className="text-xs font-bold uppercase tracking-wider text-yt-text-muted mb-2">Total Queries</p>
          <h3 className="text-3xl font-black">{logs.length}</h3>
        </div>
        <div className="yt-card p-6">
          <p className="text-xs font-bold uppercase tracking-wider text-yt-text-muted mb-2">Avg Response Time</p>
          <h3 className="text-3xl font-black gradient-text-cmu">{avgLatency}s</h3>
        </div>
        <div className="yt-card p-6">
          <p className="text-xs font-bold uppercase tracking-wider text-yt-text-muted mb-2">Total Tokens</p>
          <h3 className="text-3xl font-black text-warning">{totalTokens.toLocaleString()}</h3>
        </div>
      </div>

      {/* Filters & Search */}
      <div className="yt-card p-6 rounded-2xl">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-yt-text-muted" />
            <input value={query} onChange={(e) => { setQuery(e.target.value); setPage(1); }} placeholder="ค้นหา query, response, user..." className="w-full pl-10 pr-4 py-3 rounded-xl border-2 border-yt-border bg-transparent outline-none focus:border-accent/50 text-sm" />
          </div>
          <div className="flex items-center gap-2">
            <select value={sortBy} onChange={(e) => { setSortBy(e.target.value as typeof sortBy); setPage(1); }} className="px-4 py-3 rounded-xl border-2 border-yt-border font-bold text-sm bg-transparent outline-none">
              <option value="timestamp">เวลา</option>
              <option value="latency">Latency</option>
              <option value="anon_id">User ID</option>
            </select>
            <button onClick={() => { setSortDesc(!sortDesc); setPage(1); }} className="p-3 rounded-xl border-2 border-yt-border">
              {sortDesc ? <ArrowDown className="w-5 h-5 text-yt-text-muted" /> : <ArrowUp className="w-5 h-5 text-yt-text-muted" />}
            </button>
            <button onClick={loadLogs} className="p-3 rounded-xl bg-accent text-white">
              <RefreshCw className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>

      {/* Logs Table */}
      {loading ? (
        <p className="text-yt-text-muted text-center py-8">Loading...</p>
      ) : (
        <div className="yt-card rounded-2xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="yt-table w-full">
              <thead>
                <tr>
                  <th className="text-left"><button onClick={() => toggleSort("timestamp")} className="flex items-center gap-1 hover:text-accent"><Clock className="w-4 h-4" /> เวลา <SortIcon col="timestamp" /></button></th>
                  <th className="text-left">Platform</th>
                  <th className="text-left">User</th>
                  <th className="text-left">Query</th>
                  <th className="text-left hidden md:table-cell">Response</th>
                  <th className="text-left"><button onClick={() => toggleSort("latency")} className="flex items-center gap-1 hover:text-accent">Latency <SortIcon col="latency" /></button></th>
                  <th className="text-left hidden lg:table-cell">Tokens/Cost</th>
                </tr>
              </thead>
              <tbody>
                {paginated.map((log, i) => {
                  const lat = log.latency || 0;
                  const latColor = lat < 1 ? "text-success bg-success/10" : lat < 3 ? "text-warning bg-warning/10" : "text-danger bg-danger/10";
                  return (
                    <tr key={i} className="cursor-pointer hover:bg-yt-surface-hover transition" onClick={() => setSelected(log)}>
                      <td className="text-sm text-yt-text-muted whitespace-nowrap">
                        <div className="flex items-center gap-2"><Clock className="w-4 h-4 text-accent shrink-0" />{fmtTimestamp(log.timestamp)}</div>
                      </td>
                      <td className="text-sm">
                        <span className={cn("yt-badge", log.platform === "web" ? "yt-badge-purple" : log.platform === "facebook" ? "yt-badge-blue" : "yt-badge-gray")}>{log.platform || "unknown"}</span>
                      </td>
                      <td className="text-sm"><span className="yt-badge yt-badge-purple">{log.anon_id || "Anonymous"}</span></td>
                      <td className="text-sm font-medium max-w-48 truncate">{log.input}</td>
                      <td className="text-sm max-w-48 truncate text-yt-text-muted hidden md:table-cell">{log.output}</td>
                      <td className="text-sm"><span className={cn("yt-badge", latColor)}>{lat}s</span></td>
                      <td className="text-sm hidden lg:table-cell">
                        {log.tokens ? (
                          <div className="flex flex-col gap-1">
                            <span className="yt-badge yt-badge-purple text-xs">{log.tokens.total} tokens</span>
                            {log.tokens.cost_usd != null && <span className="yt-badge yt-badge-yellow text-xs">${log.tokens.cost_usd.toFixed(6)}</span>}
                          </div>
                        ) : <span className="text-xs text-yt-text-muted">N/A</span>}
                      </td>
                    </tr>
                  );
                })}
                {paginated.length === 0 && (
                  <tr><td colSpan={7} className="text-center text-yt-text-muted py-16">ไม่มีข้อมูล</td></tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="border-t border-yt-border px-6 py-4 flex items-center justify-between">
              <div className="text-sm text-yt-text-muted">
                แสดง <span className="font-bold">{(page - 1) * perPage + 1}</span> - <span className="font-bold">{Math.min(page * perPage, filtered.length)}</span> จาก <span className="font-bold">{filtered.length}</span> รายการ
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1} className="px-4 py-2 rounded-lg border-2 border-yt-border font-bold text-sm disabled:opacity-50 disabled:cursor-not-allowed">
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="text-sm font-bold text-yt-text-muted">{page} / {totalPages}</span>
                <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page === totalPages} className="px-4 py-2 rounded-lg border-2 border-yt-border font-bold text-sm disabled:opacity-50 disabled:cursor-not-allowed">
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Log Detail Modal */}
      {selected && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={() => setSelected(null)}>
          <div className="yt-card w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-3xl" onClick={(e) => e.stopPropagation()}>
            <div className="p-6 border-b border-yt-border flex justify-between items-center sticky top-0 z-10 bg-yt-surface">
              <span className="font-bold">Log Details</span>
              <button onClick={() => setSelected(null)} className="yt-btn-icon"><X className="w-5 h-5" /></button>
            </div>
            <div className="p-6 space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div><label className="text-xs font-bold uppercase text-yt-text-muted">Timestamp</label><p className="font-semibold mt-1">{fmtTimestamp(selected.timestamp)}</p></div>
                <div><label className="text-xs font-bold uppercase text-yt-text-muted">Platform</label><p className="font-semibold mt-1">{selected.platform || "unknown"}</p></div>
              </div>
              <div><label className="text-xs font-bold uppercase text-yt-text-muted">User ID</label><p className="font-semibold mt-1">{selected.anon_id || "Anonymous"}</p></div>
              <div>
                <label className="text-xs font-bold uppercase text-yt-text-muted mb-2 block">Query</label>
                <div className="p-4 rounded-xl bg-accent/5"><p className="font-medium whitespace-pre-wrap">{selected.input}</p></div>
              </div>
              <div>
                <label className="text-xs font-bold uppercase text-yt-text-muted mb-2 block">Response</label>
                <div className="p-4 rounded-xl bg-warning/5"><p className="whitespace-pre-wrap text-yt-text-secondary">{selected.output}</p></div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div><label className="text-xs font-bold uppercase text-yt-text-muted">Latency</label><p className="text-2xl font-black gradient-text-cmu mt-1">{selected.latency}s</p></div>
                {selected.rating != null && <div><label className="text-xs font-bold uppercase text-yt-text-muted">Rating</label><p className="text-2xl font-black text-success mt-1">{selected.rating}</p></div>}
              </div>
              {selected.tokens && (
                <div>
                  <label className="text-xs font-bold uppercase text-yt-text-muted mb-3 block">Token Usage & Cost</label>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="p-4 rounded-xl bg-accent/5"><p className="text-xs font-bold text-yt-text-muted mb-1">Prompt</p><p className="text-xl font-black text-accent">{selected.tokens.prompt || 0}</p></div>
                    <div className="p-4 rounded-xl bg-success/5"><p className="text-xs font-bold text-yt-text-muted mb-1">Completion</p><p className="text-xl font-black text-success">{selected.tokens.completion || 0}</p></div>
                    <div className="p-4 rounded-xl bg-warning/5"><p className="text-xs font-bold text-yt-text-muted mb-1">Total</p><p className="text-xl font-black text-warning">{selected.tokens.total || 0}</p></div>
                    {selected.tokens.cost_usd != null && <div className="p-4 rounded-xl bg-warning/5"><p className="text-xs font-bold text-yt-text-muted mb-1">Cost (USD)</p><p className="text-xl font-black text-warning">${selected.tokens.cost_usd.toFixed(6)}</p></div>}
                  </div>
                  {selected.tokens.cached && (
                    <div className="mt-3 px-4 py-2 rounded-xl flex items-center gap-2 bg-success/10">
                      <Zap className="w-4 h-4 text-success" />
                      <span className="text-sm font-bold text-success">Cached Response (Faster & Cheaper)</span>
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="p-6 border-t border-yt-border flex justify-end">
              <button onClick={() => setSelected(null)} className="yt-btn yt-btn-primary">ปิด</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
