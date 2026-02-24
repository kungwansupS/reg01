"use client";

import { useState, useEffect, useCallback } from "react";
import { Send, RefreshCw } from "lucide-react";
import { adminFetch, adminFormPost } from "@/lib/api";

interface Session {
  session_id: string;
  user_name?: string;
  platform?: string;
  last_active?: string;
  message_count?: number;
}

interface Message {
  id: number;
  role: string;
  content: string;
  created_at?: string;
}

export function ChatTab() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [replyText, setReplyText] = useState("");
  const [loading, setLoading] = useState(false);

  const loadSessions = useCallback(async () => {
    try {
      const res = await adminFetch("/api/admin/chat/sessions");
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions || []);
      }
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadSessions(); }, [loadSessions]);

  async function loadMessages(sessionId: string) {
    setSelected(sessionId);
    setLoading(true);
    try {
      const res = await adminFetch(`/api/admin/database/sessions/${sessionId}/messages`);
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages || []);
      }
    } catch { /* ignore */ }
    setLoading(false);
  }

  async function sendReply() {
    if (!selected || !replyText.trim()) return;
    const form = new FormData();
    form.append("session_id", selected);
    form.append("text", replyText.trim());
    try {
      await adminFormPost("/api/admin/chat/send", form);
      setReplyText("");
      await loadMessages(selected);
    } catch { /* ignore */ }
  }

  function parseContent(content: string): string {
    try {
      const parsed = JSON.parse(content);
      if (Array.isArray(parsed)) {
        return parsed.map((p: { text?: string }) => p.text || "").join(" ");
      }
      return content;
    } catch {
      return content;
    }
  }

  return (
    <div className="flex h-full">
      {/* Session list */}
      <div className="w-72 border-r border-zinc-800 flex flex-col">
        <div className="p-3 border-b border-zinc-800 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-zinc-400">Sessions</h3>
          <button onClick={loadSessions} className="text-zinc-500 hover:text-zinc-300">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          {sessions.map((s) => (
            <button
              key={s.session_id}
              onClick={() => loadMessages(s.session_id)}
              className={`w-full text-left px-4 py-3 border-b border-zinc-800/50 hover:bg-zinc-800/50 transition ${
                selected === s.session_id ? "bg-zinc-800" : ""
              }`}
            >
              <p className="text-sm font-medium truncate">{s.user_name || s.session_id.slice(0, 12)}</p>
              <p className="text-[10px] text-zinc-500">{s.platform || "web"} · {s.message_count ?? 0} msgs</p>
            </button>
          ))}
          {sessions.length === 0 && <p className="p-4 text-zinc-600 text-sm">No sessions</p>}
        </div>
      </div>

      {/* Chat view */}
      <div className="flex-1 flex flex-col">
        {selected ? (
          <>
            <div className="flex-1 overflow-y-auto p-4 space-y-2 custom-scrollbar">
              {loading ? (
                <p className="text-zinc-500 text-sm">Loading...</p>
              ) : (
                messages.map((m) => (
                  <div
                    key={m.id}
                    className={`max-w-[75%] px-3 py-2 rounded-xl text-sm ${
                      m.role === "user"
                        ? "ml-auto bg-cmu-purple/30 text-white"
                        : "mr-auto bg-zinc-800 text-zinc-200"
                    }`}
                  >
                    <p>{parseContent(m.content)}</p>
                    <p className="text-[10px] text-zinc-500 mt-1">{m.created_at}</p>
                  </div>
                ))
              )}
            </div>
            <div className="p-3 border-t border-zinc-800 flex gap-2">
              <input
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && sendReply()}
                placeholder="Send admin reply..."
                className="flex-1 bg-zinc-800 rounded-lg px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-cmu-purple/50"
              />
              <button onClick={sendReply} className="gradient-cmu p-2 rounded-lg">
                <Send className="w-4 h-4" />
              </button>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-zinc-600">
            Select a session to view messages
          </div>
        )}
      </div>
    </div>
  );
}
