"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { RefreshCw } from "lucide-react";
import { useSocket } from "@/providers/socket-provider";
import { adminFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

interface QueueData {
  current?: { pending?: number; active?: number };
  config?: { num_workers?: number; max_size?: number; per_user_limit?: number; request_timeout?: number };
  totals?: { processed?: number; errors?: number; rejected?: number; timeouts?: number };
  peaks?: { max_pending?: number; max_active?: number };
  throughput_per_min?: number;
  uptime_seconds?: number;
}

interface MonitorData {
  queue?: QueueData;
  recent_activity?: Array<{ input?: string; output?: string; platform?: string; latency?: number; timestamp?: string }>;
  active_sessions?: number;
  faq_analytics?: { total_knowledge_base?: number };
}

interface FeedItem {
  type: "user" | "bot";
  name: string;
  platform: string;
  text: string;
  time: Date;
}

export function MonitorTab() {
  const { socket } = useSocket();
  const [data, setData] = useState<MonitorData>({});
  const [liveFeed, setLiveFeed] = useState<FeedItem[]>([]);
  const [connected, setConnected] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const autoRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStats = useCallback(async () => {
    try {
      const res = await adminFetch("/api/admin/monitor/stats");
      if (res.ok) {
        setData(await res.json());
        setLastRefresh(new Date());
      }
    } catch { /* ignore */ }
  }, []);

  // Auto-refresh
  useEffect(() => {
    fetchStats();
    autoRef.current = setInterval(fetchStats, 5000);
    return () => { if (autoRef.current) clearInterval(autoRef.current); };
  }, [fetchStats]);

  // Socket live feed
  useEffect(() => {
    if (!socket) return;
    const onConnect = () => setConnected(true);
    const onDisconnect = () => setConnected(false);
    const onNewMsg = (d: { uid?: string; platform?: string; text?: string; user_name?: string }) => {
      setLiveFeed((prev) => [{ type: "user" as const, name: d.user_name || d.uid || "Unknown", platform: d.platform || "web", text: d.text || "", time: new Date() }, ...prev].slice(0, 100));
    };
    const onBotReply = (d: { uid?: string; platform?: string; text?: string }) => {
      setLiveFeed((prev) => [{ type: "bot" as const, name: "Bot พี่เร็ก", platform: d.platform || "web", text: (d.text || "").replace(/\[Bot พี่เร็ก\]\s*/g, "").replace(/\[Admin\]:\s*/g, ""), time: new Date() }, ...prev].slice(0, 100));
    };
    socket.on("connect", onConnect);
    socket.on("disconnect", onDisconnect);
    socket.on("admin_new_message", onNewMsg);
    socket.on("admin_bot_reply", onBotReply);
    if (socket.connected) setConnected(true);
    return () => { socket.off("connect", onConnect); socket.off("disconnect", onDisconnect); socket.off("admin_new_message", onNewMsg); socket.off("admin_bot_reply", onBotReply); };
  }, [socket]);

  const q = data.queue || {};
  const cur = q.current || {};
  const tot = q.totals || {};
  const cfg = q.config || {};
  const peaks = q.peaks || {};
  const used = (cur.pending || 0) + (cur.active || 0);
  const maxSize = cfg.max_size || 200;
  const capPct = maxSize > 0 ? Math.round((used / maxSize) * 100) : 0;
  const capColor = capPct > 75 ? "text-danger" : capPct > 50 ? "text-warning" : "text-success";
  const recent = data.recent_activity || [];
  const fmtTime = (d: Date) => d.toLocaleTimeString("th-TH");

  return (
    <div className="p-6 md:p-10 space-y-6 overflow-y-auto custom-scrollbar">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl md:text-4xl font-black gradient-text-cmu">Live Monitor</h1>
          <p className="text-sm text-yt-text-muted flex items-center gap-2">
            Real-time System Activity
            <span className="inline-flex items-center gap-1.5 ml-2">
              <span className={cn("w-2 h-2 rounded-full animate-pulse", connected ? "bg-emerald-500" : "bg-red-500")} />
              <span className="text-xs font-bold">{connected ? "Connected" : "Disconnected"}</span>
            </span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={fetchStats} className="yt-btn yt-btn-secondary text-xs">
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
          {lastRefresh && <span className="text-xs text-yt-text-muted">Updated {fmtTime(lastRefresh)}</span>}
        </div>
      </div>

      {/* Queue Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <StatBox label="Pending" value={cur.pending ?? 0} color="text-warning" />
        <StatBox label="Active" value={cur.active ?? 0} color="text-success" />
        <StatBox label="Processed" value={tot.processed ?? 0} color="text-accent" />
        <StatBox label="Errors" value={tot.errors ?? 0} color="text-danger" />
        <div className="yt-card p-4 text-center">
          <p className="text-[10px] font-black uppercase tracking-wider mb-1 text-yt-text-muted">Throughput</p>
          <h3 className="text-2xl font-black text-accent">{q.throughput_per_min ?? 0}<span className="text-xs font-bold">/min</span></h3>
        </div>
        <div className="yt-card p-4 text-center">
          <p className="text-[10px] font-black uppercase tracking-wider mb-1 text-yt-text-muted">Capacity</p>
          <h3 className={cn("text-2xl font-black", capColor)}>{capPct}%</h3>
          <div className="w-full h-1.5 rounded-full mt-1 bg-yt-surface-hover">
            <div className={cn("h-full rounded-full transition-all", capPct > 75 ? "bg-danger" : capPct > 50 ? "bg-warning" : "bg-success")} style={{ width: `${capPct}%` }} />
          </div>
        </div>
      </div>

      {/* Queue Info Bar */}
      <div className="yt-card p-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs font-bold text-yt-text-secondary">
        <span>Workers: <span className="text-yt-text">{cfg.num_workers ?? "-"}</span></span>
        <span>Max Size: <span className="text-yt-text">{cfg.max_size ?? "-"}</span></span>
        <span>Per User Limit: <span className="text-yt-text">{cfg.per_user_limit ?? "-"}</span></span>
        <span>Timeout: <span className="text-yt-text">{cfg.request_timeout ?? "-"}s</span></span>
        <span>Peak Pending: <span className="text-warning">{peaks.max_pending ?? 0}</span></span>
        <span>Peak Active: <span className="text-success">{peaks.max_active ?? 0}</span></span>
        <span>Uptime: <span className="text-yt-text">{q.uptime_seconds ? Math.round(q.uptime_seconds / 60) + " min" : "-"}</span></span>
        <span>Sessions: <span className="text-accent">{data.active_sessions ?? 0}</span></span>
        <span>FAQ KB: <span className="text-accent">{data.faq_analytics?.total_knowledge_base ?? 0}</span></span>
        <span>Rejected: <span className="text-danger">{tot.rejected ?? 0}</span></span>
        <span>Timeouts: <span className="text-danger">{tot.timeouts ?? 0}</span></span>
      </div>

      {/* Two-column: Live Feed + Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Live Feed */}
        <div className="yt-card overflow-hidden flex flex-col" style={{ maxHeight: 560 }}>
          <div className="px-4 py-3 border-b border-yt-border flex items-center justify-between bg-yt-surface-hover">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <h3 className="font-bold text-sm">Live Feed</h3>
            </div>
            <span className="text-[10px] font-bold text-yt-text-muted">{liveFeed.length} events</span>
          </div>
          <div className="flex-1 overflow-y-auto p-3 custom-scrollbar space-y-2">
            {liveFeed.length === 0 ? (
              <p className="text-sm text-yt-text-muted text-center py-8">รอข้อความ...</p>
            ) : liveFeed.map((item, i) => (
              <div key={i} className={cn("p-3 rounded-lg border-l-4 mb-1", item.type === "user" ? "border-l-blue-500" : "border-l-emerald-500", "bg-yt-surface-hover")}>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm">{item.type === "user" ? "👤" : "🤖"}</span>
                    <span className="text-xs font-bold">{item.name}</span>
                    <span className={cn("px-1.5 py-0.5 rounded text-[10px] font-bold", item.platform === "facebook" ? "bg-blue-500/10 text-blue-400" : "bg-accent/10 text-accent")}>{item.platform === "facebook" ? "FB" : "Web"}</span>
                  </div>
                  <span className="text-[10px] font-medium text-yt-text-muted">{fmtTime(item.time)}</span>
                </div>
                <p className="text-sm truncate text-yt-text-secondary">{item.text.substring(0, 150)}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Activity (Audit Log) */}
        <div className="yt-card overflow-hidden flex flex-col" style={{ maxHeight: 560 }}>
          <div className="px-4 py-3 border-b border-yt-border flex items-center justify-between bg-yt-surface-hover">
            <h3 className="font-bold text-sm">Recent Activity (Audit Log)</h3>
            <span className="text-[10px] font-bold text-yt-text-muted">{recent.length} entries</span>
          </div>
          <div className="flex-1 overflow-y-auto p-4 custom-scrollbar space-y-1">
            {recent.length === 0 ? (
              <p className="text-sm text-yt-text-muted text-center py-8">No activity yet</p>
            ) : recent.slice(0, 20).map((log, i) => {
              const lat = log.latency || 0;
              const latColor = lat < 3 ? "text-success" : lat < 8 ? "text-warning" : "text-danger";
              return (
                <div key={i} className="flex items-center justify-between py-2 border-b border-yt-border/50 last:border-0">
                  <div className="flex-1 min-w-0 mr-4">
                    <p className="text-sm font-medium truncate">{log.input}</p>
                    <p className="text-xs text-yt-text-muted truncate">{(log.output || "").substring(0, 80)}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className={cn("px-1.5 py-0.5 rounded text-[10px] font-bold", log.platform === "facebook" ? "bg-blue-500/10 text-blue-400" : "bg-accent/10 text-accent")}>{log.platform || "web"}</span>
                    <span className={cn("text-xs font-bold", latColor)}>{lat}s</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatBox({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="yt-card p-4 text-center">
      <p className="text-[10px] font-black uppercase tracking-wider mb-1 text-yt-text-muted">{label}</p>
      <h3 className={cn("text-3xl font-black", color)}>{value}</h3>
    </div>
  );
}
