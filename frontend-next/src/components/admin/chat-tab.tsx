"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Send, Search, Power, PowerOff, MessageCircle, AlertTriangle, Globe, Facebook } from "lucide-react";
import { adminFetch, adminFormPost } from "@/lib/api";
import { useSocket } from "@/providers/socket-provider";
import { cn } from "@/lib/utils";

interface Session {
  id: string;
  platform?: string;
  profile?: { name?: string; picture?: string };
  bot_enabled?: boolean;
  last_active?: string;
}

interface ChatMsg {
  role: string;
  parts: { text: string }[];
  timestamp?: number;
}

export function ChatTab() {
  const { socket } = useSocket();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [current, setCurrent] = useState<Session | null>(null);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [newMessage, setNewMessage] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const msgEndRef = useRef<HTMLDivElement>(null);

  const scrollBottom = useCallback(() => {
    setTimeout(() => msgEndRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
  }, []);

  const loadSessions = useCallback(async () => {
    try {
      const res = await adminFetch("/api/admin/chat/sessions");
      if (res.ok) {
        const data = await res.json();
        setSessions(Array.isArray(data) ? data.filter((s: Session) => s && s.id && s.profile) : []);
      }
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadSessions(); }, [loadSessions]);

  // Socket real-time messages
  useEffect(() => {
    if (!socket) return;
    function handleNewMsg(data: { uid?: string; platform?: string; text?: string; user_name?: string; user_pic?: string }) {
      if (!data?.uid) return;
      handleIncoming(data, "user");
    }
    function handleBotReply(data: { uid?: string; session_id?: string; platform?: string; text?: string }) {
      if (!data) return;
      const uid = data.uid || data.session_id;
      if (uid) handleIncoming({ ...data, uid }, "model");
    }
    socket.on("admin_new_message", handleNewMsg);
    socket.on("admin_bot_reply", handleBotReply);
    return () => { socket.off("admin_new_message", handleNewMsg); socket.off("admin_bot_reply", handleBotReply); };
  });

  function handleIncoming(data: { uid?: string; platform?: string; text?: string; user_name?: string; user_pic?: string }, role: string) {
    const sid = data.uid;
    if (!sid) return;
    // Move or create session
    setSessions((prev) => {
      const idx = prev.findIndex((s) => s.id === sid);
      if (idx !== -1) {
        const moved = [...prev];
        const [s] = moved.splice(idx, 1);
        return [s, ...moved];
      }
      return [{ id: sid, platform: data.platform || "web", profile: { name: data.user_name || `${data.platform} User`, picture: data.user_pic || "https://www.gravatar.com/avatar/?d=mp" }, bot_enabled: true }, ...prev];
    });
    // Add message if viewing this session
    setCurrent((cur) => {
      if (cur && cur.id === sid) {
        setMessages((prev) => {
          const isDup = prev.some((m) => m.role === role && m.parts[0]?.text === data.text && Math.abs((m.timestamp || 0) - Date.now()) < 2000);
          if (isDup) return prev;
          return [...prev, { role, parts: [{ text: data.text || "" }], timestamp: Date.now() }];
        });
        scrollBottom();
      }
      return cur;
    });
  }

  async function selectSession(session: Session) {
    setCurrent(session);
    setMessages([]);
    setLoading(true);
    try {
      const res = await adminFetch(`/api/admin/chat/history/${session.platform || "web"}/${session.id}`);
      if (res.ok) {
        const data = await res.json();
        const msgs: ChatMsg[] = (Array.isArray(data) ? data : []).filter(
          (m: ChatMsg) => m && m.parts && Array.isArray(m.parts) && m.parts[0]?.text && (m.role === "user" || m.role === "model")
        );
        setMessages(msgs);
        scrollBottom();
      }
    } catch { /* ignore */ }
    setLoading(false);
  }

  function sendMessage() {
    if (!newMessage.trim() || !current) return;
    if (current.bot_enabled) { alert("กรุณาปิด Auto Bot ของ Session นี้ก่อนตอบกลับ"); return; }
    if (!socket) return;
    const adminToken = typeof window !== "undefined" ? localStorage.getItem("adminToken") || "" : "";
    socket.emit("admin_manual_reply", {
      uid: current.id,
      platform: current.platform,
      text: newMessage.trim(),
      admin_token: adminToken,
    });
    setMessages((prev) => [...prev, { role: "model", parts: [{ text: `[Admin]: ${newMessage.trim()}` }], timestamp: Date.now() }]);
    setNewMessage("");
    scrollBottom();
  }

  async function toggleBot(session: Session) {
    const next = !session.bot_enabled;
    const form = new FormData();
    form.append("session_id", session.id);
    form.append("status", String(next));
    try {
      const res = await adminFetch("/api/admin/bot-toggle", { method: "POST", body: form });
      if (res.ok) {
        setSessions((prev) => prev.map((s) => s.id === session.id ? { ...s, bot_enabled: next } : s));
        if (current?.id === session.id) setCurrent((c) => c ? { ...c, bot_enabled: next } : c);
      }
    } catch { /* ignore */ }
  }

  async function toggleAllBots(status: boolean) {
    const action = status ? "เปิด" : "ปิด";
    if (!confirm(`ต้องการ${action} Auto Bot ทั้งหมดทุก Session หรือไม่?`)) return;
    const form = new FormData();
    form.append("status", String(status));
    try {
      const res = await adminFetch("/api/admin/bot-toggle-all", { method: "POST", body: form });
      if (res.ok) {
        setSessions((prev) => prev.map((s) => ({ ...s, bot_enabled: status })));
        if (current) setCurrent((c) => c ? { ...c, bot_enabled: status } : c);
      }
    } catch { /* ignore */ }
  }

  const filtered = searchQuery.trim()
    ? sessions.filter((s) => (s.profile?.name || "").toLowerCase().includes(searchQuery.toLowerCase()) || s.platform?.toLowerCase().includes(searchQuery.toLowerCase()) || s.id.toLowerCase().includes(searchQuery.toLowerCase()))
    : sessions;

  function getMsgBubbleClass(msg: ChatMsg) {
    if (msg.role === "user") return "self-start bg-yt-surface-hover border border-yt-border";
    if (msg.parts[0]?.text.startsWith("[Admin]")) return "self-end bg-accent/20 border border-accent/30";
    return "self-end bg-yt-surface border border-yt-border";
  }

  function getMsgLabel(msg: ChatMsg) {
    if (msg.role === "user") return "Customer";
    if (msg.parts[0]?.text.startsWith("[Admin]")) return "Admin";
    return "Bot พี่เร็ก";
  }

  function getMsgText(msg: ChatMsg) {
    const t = msg.parts[0]?.text || "";
    return t.replace("[Admin]: ", "");
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between p-6 pb-4 gap-4">
        <div>
          <h1 className="text-3xl md:text-4xl font-black gradient-text-cmu">Unified Chat</h1>
          <p className="text-sm text-yt-text-muted">Unified Chat Facebook and other</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => toggleAllBots(true)} className="px-3 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white font-bold text-xs flex items-center gap-1.5 shadow-lg">
            <Power className="w-3.5 h-3.5" /> เปิด Bot ทั้งหมด
          </button>
          <button onClick={() => toggleAllBots(false)} className="px-3 py-2 rounded-xl bg-gray-500 hover:bg-gray-600 text-white font-bold text-xs flex items-center gap-1.5 shadow-lg">
            <PowerOff className="w-3.5 h-3.5" /> ปิด Bot ทั้งหมด
          </button>
        </div>
      </div>

      {/* Chat Panel */}
      <div className="flex-1 mx-6 mb-6 yt-card overflow-hidden flex rounded-2xl min-h-0">
        {/* Session List */}
        <div className="w-80 border-r border-yt-border flex flex-col bg-yt-surface-hover/50">
          <div className="p-3 border-b border-yt-border">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-yt-text-muted" />
              <input value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="Search customer name..." className="w-full pl-10 pr-4 py-2 rounded-xl text-sm bg-yt-surface border-none outline-none focus:ring-2 focus:ring-accent/50 text-yt-text" />
            </div>
          </div>
          <div className="flex-1 overflow-y-auto custom-scrollbar px-2 pt-2">
            {filtered.map((s) => (
              <div key={s.id} onClick={() => selectSession(s)} className={cn(
                "p-3 flex items-center gap-3 cursor-pointer rounded-2xl mb-1.5 transition-all",
                current?.id === s.id ? "bg-yt-surface shadow-md scale-[1.02] border-l-4 border-accent" : "opacity-70 hover:opacity-100"
              )}>
                <div className="relative shrink-0">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={s.profile?.picture || "https://www.gravatar.com/avatar/?d=mp"} alt="" className="w-11 h-11 rounded-full object-cover border-2 border-yt-border shadow-sm" />
                  <div className={cn("absolute -top-1 -right-1 w-5 h-5 border-2 border-yt-surface rounded-full flex items-center justify-center shadow-sm", s.platform === "facebook" ? "bg-blue-500" : s.platform === "line" ? "bg-[#06C755]" : "bg-green-500")}>
                    {s.platform === "facebook" ? <Facebook className="w-2.5 h-2.5 text-white" /> : <Globe className="w-2.5 h-2.5 text-white" />}
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-bold truncate text-sm">{s.profile?.name || s.id.slice(0, 12)}</p>
                  <div className="flex items-center gap-1">
                    <span className="text-[9px] uppercase font-black tracking-widest text-yt-text-muted">{s.platform}</span>
                    <span className={cn("ml-1 text-[9px] font-black px-1.5 py-0.5 rounded-full", s.bot_enabled ? "bg-emerald-500/20 text-emerald-500" : "bg-gray-400/20 text-gray-400")}>
                      {s.bot_enabled ? "🤖 ON" : "⏸ OFF"}
                    </span>
                  </div>
                </div>
              </div>
            ))}
            {filtered.length === 0 && <p className="p-4 text-yt-text-muted text-sm text-center">No sessions</p>}
          </div>
        </div>

        {/* Chat Area */}
        <div className="flex-1 flex flex-col min-w-0 bg-yt-surface-hover/30">
          {current ? (
            <>
              {/* Chat Header */}
              <div className="p-4 border-b border-yt-border flex items-center justify-between bg-yt-surface/80 shadow-sm z-10">
                <div className="flex items-center gap-3">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={current.profile?.picture || "https://www.gravatar.com/avatar/?d=mp"} alt="" className="w-10 h-10 rounded-full border border-yt-border shadow-sm" />
                  <div>
                    <h3 className="font-black text-base leading-tight">{current.profile?.name}</h3>
                    <p className="text-[10px] text-emerald-500 font-bold uppercase tracking-widest">Connected via {current.platform}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 px-4 py-2 rounded-2xl border border-yt-border bg-yt-surface-hover">
                  <div className="flex flex-col items-end">
                    <span className="text-[10px] font-black uppercase text-yt-text-muted">Auto Bot System</span>
                    <span className={cn("text-xs font-bold", current.bot_enabled ? "text-emerald-500" : "text-yt-text-muted")}>{current.bot_enabled ? "ACTIVE" : "DISABLED"}</span>
                  </div>
                  <button onClick={() => toggleBot(current)} className={cn("w-12 h-6 rounded-full relative transition-all duration-300", current.bot_enabled ? "bg-emerald-500" : "bg-yt-border")}>
                    <div className={cn("absolute top-1 w-4 h-4 bg-white rounded-full shadow-sm transition-transform duration-300", current.bot_enabled ? "translate-x-6" : "translate-x-1")} />
                  </button>
                </div>
              </div>

              {/* Messages */}
              <div className="flex-1 p-5 overflow-y-auto flex flex-col gap-3 custom-scrollbar">
                {loading ? (
                  <p className="text-yt-text-muted text-sm text-center py-8">Loading messages...</p>
                ) : (
                  messages.map((m, i) => (
                    <div key={i} className={cn("flex flex-col max-w-[80%]", m.role === "user" ? "self-start" : "self-end")}>
                      <div className={cn("px-4 py-3 rounded-2xl text-sm font-medium leading-relaxed", getMsgBubbleClass(m))}>
                        {getMsgText(m)}
                      </div>
                      <span className={cn("text-[9px] mt-1 font-bold uppercase text-yt-text-muted", m.role === "user" ? "text-left" : "text-right")}>{getMsgLabel(m)}</span>
                    </div>
                  ))
                )}
                {messages.length === 0 && !loading && <p className="text-yt-text-muted text-sm text-center py-8">No messages in this session</p>}
                <div ref={msgEndRef} />
              </div>

              {/* Input */}
              <div className="p-4 border-t border-yt-border bg-yt-surface/80">
                {current.bot_enabled && (
                  <div className="mb-3 px-4 py-2 text-xs font-bold rounded-xl flex items-center gap-2 bg-warning/10 text-warning border border-warning/20">
                    <AlertTriangle className="w-4 h-4 shrink-0" />
                    <span>กรุณาปิด Auto Bot ด้านบนก่อนเพื่อสลับมาแหมดตอบด้วยตนเอง</span>
                  </div>
                )}
                <div className="flex items-center gap-3">
                  <input
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && sendMessage()}
                    disabled={current.bot_enabled}
                    placeholder={current.bot_enabled ? "บอททำงานอยู่..." : "พิมพ์ข้อความตอบกลับผู้ใช้..."}
                    className={cn("flex-1 px-5 py-3 rounded-full text-sm font-medium bg-yt-surface-hover outline-none focus:ring-2 focus:ring-accent/50", current.bot_enabled && "opacity-50 cursor-not-allowed")}
                  />
                  <button onClick={sendMessage} disabled={current.bot_enabled} className={cn("p-3 rounded-full text-white transition-all", current.bot_enabled ? "bg-yt-border cursor-not-allowed" : "bg-accent hover:bg-accent/80 shadow-lg")}>
                    <Send className="w-5 h-5" />
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <div className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-4 bg-yt-surface-hover shadow-inner">
                  <MessageCircle className="w-10 h-10 text-yt-border" />
                </div>
                <h3 className="text-lg font-black text-yt-text-muted mb-1">No Conversation Selected</h3>
                <p className="text-sm text-yt-text-muted">เลือกรายชื่อผู้สนทนาจากรายการด้านซ้ายเพื่อเริ่มต้น</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
