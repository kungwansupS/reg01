"use client";

import { useState, useEffect, useCallback } from "react";
import { Database, ChevronDown, ChevronRight, Download, Trash2 } from "lucide-react";
import { adminFetch } from "@/lib/api";

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
  const [expanded, setExpanded] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageRow[]>([]);
  const [loading, setLoading] = useState(true);

  const loadSessions = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminFetch("/api/admin/database/sessions");
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions || []);
      }
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { loadSessions(); }, [loadSessions]);

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

  async function handleExport() {
    try {
      const res = await adminFetch("/api/admin/database/export");
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `db_export_${new Date().toISOString().slice(0, 10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch { /* ignore */ }
  }

  async function handleCleanup() {
    if (!confirm("Delete sessions older than 30 days?")) return;
    try {
      await adminFetch("/api/admin/database/cleanup", { method: "POST" });
      await loadSessions();
    } catch { /* ignore */ }
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Database className="w-6 h-6 text-cmu-purple-light" /> Database
        </h1>
        <div className="flex gap-2">
          <button onClick={handleExport} className="flex items-center gap-2 px-3 py-2 bg-zinc-800 rounded-lg hover:bg-zinc-700 text-sm">
            <Download className="w-4 h-4" /> Export
          </button>
          <button onClick={handleCleanup} className="flex items-center gap-2 px-3 py-2 bg-red-900/30 text-red-400 rounded-lg hover:bg-red-900/50 text-sm">
            <Trash2 className="w-4 h-4" /> Cleanup
          </button>
        </div>
      </div>

      {loading ? (
        <p className="text-zinc-500">Loading sessions...</p>
      ) : (
        <div className="space-y-2">
          {sessions.map((s) => (
            <div key={s.session_id} className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
              <button
                onClick={() => toggleExpand(s.session_id)}
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-zinc-800/50 transition text-left"
              >
                {expanded === s.session_id ? <ChevronDown className="w-4 h-4 text-zinc-500" /> : <ChevronRight className="w-4 h-4 text-zinc-500" />}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{s.user_name || s.session_id.slice(0, 16)}</p>
                  <p className="text-[10px] text-zinc-500">{s.platform} · {s.message_count ?? 0} msgs · {s.last_active}</p>
                </div>
                <span className={`text-[10px] px-2 py-0.5 rounded-full ${s.bot_enabled ? "bg-green-500/20 text-green-400" : "bg-zinc-700 text-zinc-400"}`}>
                  {s.bot_enabled ? "bot on" : "bot off"}
                </span>
              </button>

              {expanded === s.session_id && (
                <div className="border-t border-zinc-800 p-4 space-y-2 max-h-64 overflow-y-auto custom-scrollbar">
                  {messages.map((m) => (
                    <div key={m.id} className={`text-xs px-3 py-2 rounded-lg ${m.role === "user" ? "bg-zinc-800 ml-8" : "bg-zinc-800/50 mr-8"}`}>
                      <span className="font-semibold text-zinc-400">{m.role}:</span>{" "}
                      <span className="text-zinc-300">{m.content.slice(0, 200)}</span>
                      <p className="text-[10px] text-zinc-600 mt-1">{m.created_at}</p>
                    </div>
                  ))}
                  {messages.length === 0 && <p className="text-zinc-600 text-xs">No messages</p>}
                </div>
              )}
            </div>
          ))}
          {sessions.length === 0 && <p className="text-zinc-600">No sessions found</p>}
        </div>
      )}
    </div>
  );
}
