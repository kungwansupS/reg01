"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import {
  ChevronDown, ChevronRight, ChevronLeft, Download, Trash2, Search, RefreshCw, X, Database as DbIcon,
} from "lucide-react";
import { adminFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

interface SessionRow {
  session_id: string;
  user_name?: string;
  platform?: string;
  bot_enabled?: boolean;
  created_at?: string;
  last_active?: string;
  message_count?: number;
}

interface MessageRow {
  id: number;
  role: string;
  content: string;
  created_at?: string;
}

export function DatabaseTab() {
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [stats, setStats] = useState({ totalSessions: 0, totalMessages: 0, activeSessions: 0 });
  const [expanded, setExpanded] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [platformFilter, setPlatformFilter] = useState("all");
  const [botFilter, setBotFilter] = useState("all");
  const [bulkSelection, setBulkSelection] = useState<Set<string>>(new Set());
  const [page, setPage] = useState(1);
  const perPage = 20;

  const loadSessions = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminFetch("/api/admin/database/sessions");
      if (res.ok) {
        const data = await res.json();
        const list = data.sessions || (Array.isArray(data) ? data : []);
        setSessions(list);
        if (data.stats) setStats(data.stats);
      }
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { loadSessions(); }, [loadSessions]);

  const filtered = useMemo(() => {
    let list = [...sessions];
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      list = list.filter((s) =>
        s.session_id.toLowerCase().includes(q) ||
        (s.user_name || "").toLowerCase().includes(q) ||
        (s.platform || "").toLowerCase().includes(q)
      );
    }
    if (platformFilter !== "all") list = list.filter((s) => s.platform === platformFilter);
    if (botFilter !== "all") list = list.filter((s) => (botFilter === "enabled") === !!s.bot_enabled);
    list.sort((a, b) => new Date(b.last_active || 0).getTime() - new Date(a.last_active || 0).getTime());
    return list;
  }, [sessions, searchQuery, platformFilter, botFilter]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / perPage));
  const paginated = filtered.slice((page - 1) * perPage, page * perPage);

  async function toggleExpand(sid: string) {
    if (expanded === sid) { setExpanded(null); return; }
    setExpanded(sid);
    try {
      const res = await adminFetch(`/api/admin/database/sessions/${sid}/messages`);
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages || []);
      }
    } catch { /* ignore */ }
  }

  async function deleteSession(sid: string) {
    if (!confirm(`ลบ Session ${sid.slice(0, 12)}... และข้อความทั้งหมด?`)) return;
    try {
      const res = await adminFetch(`/api/admin/database/sessions/${sid}`, { method: "DELETE" });
      if (res.ok) {
        if (expanded === sid) { setExpanded(null); setMessages([]); }
        await loadSessions();
      }
    } catch { /* ignore */ }
  }

  async function bulkDeleteSessions() {
    if (bulkSelection.size === 0) return;
    if (!confirm(`ลบ ${bulkSelection.size} Sessions?`)) return;
    for (const sid of bulkSelection) {
      try { await adminFetch(`/api/admin/database/sessions/${sid}`, { method: "DELETE" }); } catch { /* ignore */ }
    }
    setBulkSelection(new Set());
    await loadSessions();
  }

  function toggleBulk(sid: string) {
    setBulkSelection((prev) => {
      const next = new Set(prev);
      if (next.has(sid)) next.delete(sid); else next.add(sid);
      return next;
    });
  }

  async function handleExport() {
    try {
      const res = await adminFetch("/api/admin/database/export");
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `sessions_backup_${new Date().toISOString().slice(0, 10)}.db`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch { /* ignore */ }
  }

  async function handleCleanup() {
    const input = prompt("จำนวนวันที่ต้องการลบ (เช่น 7, 30, 90):", "7");
    if (!input) return;
    const days = parseInt(input);
    if (isNaN(days) || days < 1) return;
    if (!confirm(`ลบ Session ที่ไม่ได้ใช้งานมากกว่า ${days} วัน?`)) return;
    try {
      const res = await adminFetch(`/api/admin/database/cleanup?days=${days}`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        alert(`ลบ ${data.deleted_count || 0} Sessions สำเร็จ`);
        await loadSessions();
      }
    } catch { /* ignore */ }
  }

  function fmtDate(d?: string) { if (!d) return "--"; const dt = new Date(d); return `${dt.getDate()}/${dt.getMonth() + 1}/${dt.getFullYear()}`; }
  function fmtDateTime(d?: string) { if (!d) return "--"; const dt = new Date(d); return `${dt.getDate()}/${dt.getMonth() + 1}/${dt.getFullYear()} ${String(dt.getHours()).padStart(2, "0")}:${String(dt.getMinutes()).padStart(2, "0")}`; }

  const platforms = useMemo(() => [...new Set(sessions.map((s) => s.platform).filter(Boolean))], [sessions]);

  return (
    <div className="p-6 md:p-10 space-y-6 overflow-y-auto custom-scrollbar">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl md:text-4xl font-black gradient-text-cmu mb-1">Session Database</h1>
          <p className="text-sm text-yt-text-muted">จัดการ Session และประวัติการสนทนาทั้งหมด</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleExport} className="yt-btn yt-btn-secondary text-xs"><Download className="w-3.5 h-3.5" /> Export</button>
          <button onClick={handleCleanup} className="yt-btn yt-btn-danger text-xs"><Trash2 className="w-3.5 h-3.5" /> Cleanup</button>
          <button onClick={loadSessions} className="yt-btn yt-btn-secondary text-xs"><RefreshCw className="w-3.5 h-3.5" /></button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="yt-card p-4 text-center">
          <p className="text-[10px] font-black uppercase text-yt-text-muted mb-1">Total Sessions</p>
          <h3 className="text-2xl font-black">{sessions.length}</h3>
        </div>
        <div className="yt-card p-4 text-center">
          <p className="text-[10px] font-black uppercase text-yt-text-muted mb-1">Platforms</p>
          <h3 className="text-2xl font-black text-accent">{platforms.length}</h3>
        </div>
        <div className="yt-card p-4 text-center">
          <p className="text-[10px] font-black uppercase text-yt-text-muted mb-1">Filtered</p>
          <h3 className="text-2xl font-black text-warning">{filtered.length}</h3>
        </div>
      </div>

      {/* Filters */}
      <div className="yt-card p-4 rounded-2xl flex flex-col md:flex-row gap-3">
        <div className="flex-1 relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-yt-text-muted" />
          <input value={searchQuery} onChange={(e) => { setSearchQuery(e.target.value); setPage(1); }} placeholder="ค้นหา session, user, platform..." className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-yt-border bg-transparent outline-none focus:border-accent/50 text-sm" />
        </div>
        <select value={platformFilter} onChange={(e) => { setPlatformFilter(e.target.value); setPage(1); }} className="px-4 py-2.5 rounded-xl border border-yt-border bg-transparent text-sm font-bold outline-none">
          <option value="all">All Platforms</option>
          {platforms.map((p) => <option key={p} value={p}>{(p || "").toUpperCase()}</option>)}
        </select>
        <select value={botFilter} onChange={(e) => { setBotFilter(e.target.value); setPage(1); }} className="px-4 py-2.5 rounded-xl border border-yt-border bg-transparent text-sm font-bold outline-none">
          <option value="all">All Bot Status</option>
          <option value="enabled">Bot ON</option>
          <option value="disabled">Bot OFF</option>
        </select>
      </div>

      {/* Bulk Actions */}
      {bulkSelection.size > 0 && (
        <div className="yt-card p-3 rounded-xl flex items-center justify-between bg-accent/5 border border-accent/20">
          <span className="text-sm font-bold">เลือก {bulkSelection.size} รายการ</span>
          <div className="flex gap-2">
            <button onClick={bulkDeleteSessions} className="yt-btn yt-btn-danger text-xs"><Trash2 className="w-3.5 h-3.5" /> Delete Selected</button>
            <button onClick={() => setBulkSelection(new Set())} className="yt-btn yt-btn-secondary text-xs">Clear</button>
          </div>
        </div>
      )}

      {/* Session List */}
      {loading ? (
        <p className="text-yt-text-muted text-center py-8">Loading sessions...</p>
      ) : (
        <div className="space-y-2">
          {paginated.map((s) => (
            <div key={s.session_id} className={cn("yt-card overflow-hidden transition-all", expanded === s.session_id && "ring-2 ring-accent/50")}>
              <div className="flex items-center gap-3 px-4 py-3">
                <input type="checkbox" checked={bulkSelection.has(s.session_id)} onChange={() => toggleBulk(s.session_id)} onClick={(e) => e.stopPropagation()} className="w-4 h-4 rounded shrink-0 cursor-pointer" />
                <button onClick={() => toggleExpand(s.session_id)} className="flex-1 flex items-center gap-3 text-left min-w-0">
                  {expanded === s.session_id ? <ChevronDown className="w-4 h-4 text-yt-text-muted shrink-0" /> : <ChevronRight className="w-4 h-4 text-yt-text-muted shrink-0" />}
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-accent to-warning flex items-center justify-center text-white font-bold shrink-0">
                    {(s.user_name || "?")[0].toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold truncate">{s.user_name || "Unknown User"}</p>
                    <p className="text-[10px] text-yt-text-muted">{s.session_id.slice(0, 12)}...</p>
                  </div>
                </button>
                <div className="flex items-center gap-2 shrink-0">
                  <span className={cn("px-2 py-1 text-xs rounded-full font-bold", s.platform === "web" ? "bg-accent/10 text-accent" : s.platform === "facebook" ? "bg-blue-500/10 text-blue-400" : "bg-yt-surface-hover text-yt-text-muted")}>{(s.platform || "unknown").toUpperCase()}</span>
                  <span className={cn("px-2 py-1 text-xs rounded-full font-bold", s.bot_enabled ? "bg-accent/10 text-accent" : "bg-yt-surface-hover text-yt-text-muted")}>{s.bot_enabled ? "Bot ON" : "Bot OFF"}</span>
                  <button onClick={() => deleteSession(s.session_id)} className="yt-btn-icon text-danger opacity-0 group-hover:opacity-100" title="Delete Session"><Trash2 className="w-4 h-4" /></button>
                </div>
              </div>
              <div className="px-4 pb-2 flex justify-between text-[10px] text-yt-text-muted">
                <span>สร้าง: {fmtDate(s.created_at)}</span>
                <span>ใช้ล่าสุด: {fmtDateTime(s.last_active)}</span>
                <span>{s.message_count ?? 0} msgs</span>
              </div>

              {expanded === s.session_id && (
                <div className="border-t border-yt-border p-4 space-y-2 max-h-80 overflow-y-auto custom-scrollbar bg-yt-surface-hover/30">
                  {messages.map((m) => (
                    <div key={m.id} className={cn("p-3 rounded-xl text-sm", m.role === "user" ? "bg-blue-500/10 ml-8" : "bg-accent/10 mr-8")}>
                      <div className="flex items-center gap-2 mb-1">
                        <span className={cn("px-2 py-0.5 text-xs font-semibold rounded", m.role === "user" ? "bg-blue-500/20 text-blue-400" : "bg-accent/20 text-accent")}>{m.role === "user" ? "USER" : "BOT"}</span>
                        <span className="text-[10px] text-yt-text-muted">{m.created_at}</span>
                      </div>
                      <p className="text-yt-text whitespace-pre-wrap">{m.content}</p>
                    </div>
                  ))}
                  {messages.length === 0 && (
                    <div className="text-center py-8">
                      <DbIcon className="w-12 h-12 mx-auto mb-2 text-yt-border" />
                      <p className="text-sm text-yt-text-muted">ยังไม่มีข้อความในการสนทนานี้</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
          {paginated.length === 0 && (
            <div className="text-center py-16">
              <DbIcon className="w-16 h-16 mx-auto mb-4 text-yt-border" />
              <p className="text-yt-text-muted font-medium">{searchQuery || platformFilter !== "all" ? "ไม่พบ Session ที่ตรงกับเงื่อนไข" : "ยังไม่มี Session"}</p>
            </div>
          )}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-yt-text-muted">
            แสดง {(page - 1) * perPage + 1} - {Math.min(page * perPage, filtered.length)} จาก {filtered.length}
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1} className="px-3 py-1.5 rounded-lg border border-yt-border text-sm font-bold disabled:opacity-50"><ChevronLeft className="w-4 h-4" /></button>
            <span className="text-sm font-bold text-yt-text-muted">{page} / {totalPages}</span>
            <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page === totalPages} className="px-3 py-1.5 rounded-lg border border-yt-border text-sm font-bold disabled:opacity-50"><ChevronRight className="w-4 h-4" /></button>
          </div>
        </div>
      )}
    </div>
  );
}
