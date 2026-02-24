"use client";

import { useState, useEffect, useCallback } from "react";
import { Search, Download, ChevronLeft, ChevronRight } from "lucide-react";
import { adminFetch } from "@/lib/api";

interface LogEntry {
  timestamp?: string;
  anon_id?: string;
  platform?: string;
  input?: string;
  output?: string;
  latency?: number;
  tokens?: { total?: number; cost_usd?: number };
}

export function LogsTab() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), limit: "50" });
      if (query) params.set("query", query);
      const res = await adminFetch(`/api/admin/logs?${params}`);
      if (res.ok) {
        const data = await res.json();
        setLogs(data.logs || []);
        setTotalPages(data.total_pages || 1);
      }
    } catch { /* ignore */ }
    setLoading(false);
  }, [page, query]);

  useEffect(() => { loadLogs(); }, [loadLogs]);

  async function handleExport() {
    try {
      const res = await adminFetch("/api/admin/logs/export");
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `audit_logs_${new Date().toISOString().slice(0, 10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch { /* ignore */ }
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Audit Logs</h1>
        <button onClick={handleExport} className="flex items-center gap-2 px-4 py-2 bg-zinc-800 rounded-lg hover:bg-zinc-700 text-sm">
          <Download className="w-4 h-4" /> Export
        </button>
      </div>

      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
          <input
            value={query}
            onChange={(e) => { setQuery(e.target.value); setPage(1); }}
            placeholder="Search logs..."
            className="w-full bg-zinc-800 rounded-lg pl-10 pr-4 py-2 text-sm outline-none focus:ring-1 focus:ring-cmu-purple/50"
          />
        </div>
      </div>

      {loading ? (
        <p className="text-zinc-500">Loading...</p>
      ) : (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-500 text-left">
                  <th className="px-3 py-2.5">Time</th>
                  <th className="px-3 py-2.5">User</th>
                  <th className="px-3 py-2.5">Platform</th>
                  <th className="px-3 py-2.5">Input</th>
                  <th className="px-3 py-2.5">Output</th>
                  <th className="px-3 py-2.5">Latency</th>
                  <th className="px-3 py-2.5">Tokens</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log, i) => (
                  <tr key={i} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
                    <td className="px-3 py-2 text-zinc-400 whitespace-nowrap">{log.timestamp}</td>
                    <td className="px-3 py-2 font-mono">{log.anon_id?.slice(0, 8)}</td>
                    <td className="px-3 py-2">{log.platform}</td>
                    <td className="px-3 py-2 max-w-48 truncate" title={log.input}>{log.input}</td>
                    <td className="px-3 py-2 max-w-48 truncate" title={log.output}>{log.output}</td>
                    <td className="px-3 py-2 text-zinc-400">{log.latency?.toFixed(2)}s</td>
                    <td className="px-3 py-2 text-zinc-400">{log.tokens?.total}</td>
                  </tr>
                ))}
                {logs.length === 0 && (
                  <tr><td colSpan={7} className="px-4 py-8 text-center text-zinc-600">No logs found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="flex items-center justify-center gap-4">
        <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="p-2 bg-zinc-800 rounded-lg disabled:opacity-30">
          <ChevronLeft className="w-4 h-4" />
        </button>
        <span className="text-sm text-zinc-400">Page {page} / {totalPages}</span>
        <button disabled={page >= totalPages} onClick={() => setPage(page + 1)} className="p-2 bg-zinc-800 rounded-lg disabled:opacity-30">
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
