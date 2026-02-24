"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Activity, Zap, Users, Server, RefreshCw,
  BookOpen, TrendingUp, Eye,
} from "lucide-react";
import { adminFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

interface LogEntry {
  timestamp?: string;
  anon_id?: string;
  platform?: string;
  input?: string;
  output?: string;
  latency?: number;
  session_id?: string;
  tokens?: { total?: number; cached?: boolean };
}

interface FaqAnalytics {
  total_knowledge_base?: number;
  auto_learned_count?: number;
  expired_entries?: number;
  top_faqs?: Array<{ question: string; hits: number }>;
}

interface Stats {
  recent_logs?: LogEntry[];
  faq_analytics?: FaqAnalytics;
  bot_settings?: Record<string, boolean>;
  token_analytics?: { cache_hit_rate?: number; total_tokens?: number };
  system_time?: string;
}

interface SessionItem {
  id: string;
  bot_enabled?: boolean;
  platform?: string;
}

export function DashboardTab() {
  const [stats, setStats] = useState<Stats>({});
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [clock, setClock] = useState({ time: "", date: "" });

  const updateClock = useCallback(() => {
    const now = new Date();
    const h = String(now.getHours()).padStart(2, "0");
    const m = String(now.getMinutes()).padStart(2, "0");
    const s = String(now.getSeconds()).padStart(2, "0");
    const days = ["อาทิตย์", "จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์"];
    const months = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"];
    setClock({
      time: `${h}:${m}:${s}`,
      date: `วัน${days[now.getDay()]}ที่ ${now.getDate()} ${months[now.getMonth()]} ${now.getFullYear() + 543}`,
    });
  }, []);

  const loadAll = useCallback(async () => {
    try {
      const res = await adminFetch("/api/admin/stats");
      if (res.ok) setStats(await res.json());
    } catch { /* ignore */ }
    try {
      const res = await adminFetch("/api/admin/chat/sessions");
      if (res.ok) {
        const data = await res.json();
        setSessions(Array.isArray(data) ? data : []);
      }
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadAll();
    updateClock();
    const statsIv = setInterval(loadAll, 15000);
    const clockIv = setInterval(updateClock, 1000);
    return () => { clearInterval(statsIv); clearInterval(clockIv); };
  }, [loadAll, updateClock]);

  if (loading) return <div className="p-8 text-yt-text-muted">Loading dashboard...</div>;

  const logs = stats.recent_logs || [];
  const avgLatency = logs.length > 0 ? (logs.reduce((a, b) => a + (b.latency || 0), 0) / logs.length).toFixed(1) : "0";
  const uniqueSessions = new Set(logs.map((l) => l.anon_id)).size;
  const platformCount = (p: string) => logs.filter((l) => l.platform === p).length;
  const botEnabled = sessions.filter((s) => s.bot_enabled).length;
  const botDisabled = sessions.filter((s) => !s.bot_enabled).length;
  const autoRate = sessions.length > 0 ? ((botEnabled / sessions.length) * 100).toFixed(0) : "100";
  const faq = stats.faq_analytics || {};

  return (
    <div className="p-6 md:p-10 space-y-6 overflow-y-auto custom-scrollbar">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl md:text-4xl font-black gradient-text-cmu">Dashboard</h1>
          <p className="text-sm text-yt-text-muted">System Overview &amp; Real-time Analytics</p>
        </div>
        <button onClick={loadAll} className="yt-btn yt-btn-secondary text-xs">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {/* Clock */}
      <div className="yt-card p-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wider text-yt-text-muted mb-1">Current Time</p>
            <div className="text-3xl md:text-4xl font-black gradient-text-cmu font-mono">{clock.time}</div>
          </div>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wider text-yt-text-muted mb-1">Date</p>
            <div className="text-lg md:text-xl font-bold text-yt-text-secondary">{clock.date}</div>
          </div>
        </div>
      </div>

      {/* Main Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Activity} label="Total Activities" value={logs.length} sub="Total queries processed" color="purple" />
        <StatCard icon={Zap} label="Avg Latency" value={`${avgLatency}s`} sub="Response time average" color="gold" />
        <StatCard icon={Users} label="Active Sessions" value={uniqueSessions} sub="Total user sessions" color="green" />
        <StatCard icon={Server} label="System Status" value="ONLINE" sub="All systems running" color="green" isStatus />
      </div>

      {/* Platform / Bot Stats / FAQ KB */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Platform Usage */}
        <div className="yt-card p-5">
          <h3 className="font-bold text-base mb-4">Platform Usage</h3>
          <div className="space-y-3">
            {[
              { name: "Facebook", count: platformCount("facebook"), color: "bg-blue-500" },
              { name: "Web", count: platformCount("web"), color: "bg-green-500" },
              { name: "Line", count: platformCount("line"), color: "bg-[#06C755]" },
            ].map((p) => (
              <div key={p.name} className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={cn("w-3 h-3 rounded-full", p.color)} />
                  <span className="text-sm font-semibold text-yt-text-secondary">{p.name}</span>
                </div>
                <span className="font-black">{p.count}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Bot Statistics */}
        <div className="yt-card p-5">
          <h3 className="font-bold text-base mb-4">Bot Statistics</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-3 h-3 rounded-full bg-emerald-500" />
                <span className="text-sm font-semibold text-yt-text-secondary">Bot Enabled</span>
              </div>
              <span className="font-black text-emerald-500">{botEnabled}</span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-3 h-3 rounded-full bg-danger" />
                <span className="text-sm font-semibold text-yt-text-secondary">Bot Disabled</span>
              </div>
              <span className="font-black text-danger">{botDisabled}</span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-3 h-3 rounded-full bg-accent" />
                <span className="text-sm font-semibold text-yt-text-secondary">Auto Response Rate</span>
              </div>
              <span className="font-black text-accent">{autoRate}%</span>
            </div>
          </div>
        </div>

        {/* FAQ Knowledge Base */}
        <div className="yt-card p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-base">FAQ Knowledge Base</h3>
            <BookOpen className="w-5 h-5 text-yt-text-muted" />
          </div>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-yt-text-secondary">Total KB</span>
              <span className="font-black">{faq.total_knowledge_base ?? 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-yt-text-secondary">Auto Learned</span>
              <span className="font-black text-blue-500">{faq.auto_learned_count ?? 0}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-yt-text-secondary">Cache Hit Rate</span>
              <span className="font-black text-green-500">{stats.token_analytics?.cache_hit_rate ?? 0}%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Activity & Top FAQs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Recent Activity */}
        <div className="yt-card p-5">
          <h3 className="font-bold text-base mb-4">Recent Activity</h3>
          <div className="space-y-2 max-h-80 overflow-y-auto custom-scrollbar">
            {logs.slice(0, 10).map((log, i) => (
              <div key={i} className="p-3 rounded-xl bg-yt-surface-hover">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className={cn(
                      "text-[10px] font-black px-2 py-0.5 rounded-full uppercase",
                      log.platform === "web" ? "bg-accent/10 text-accent" :
                      log.platform === "facebook" ? "bg-blue-500/10 text-blue-400" :
                      log.platform === "line" ? "bg-[#06C755]/10 text-[#06C755]" :
                      "bg-yt-surface-active text-yt-text-muted"
                    )}>{log.platform}</span>
                    <span className="text-[10px] font-bold text-yt-text-muted">{formatTime(log.timestamp)}</span>
                  </div>
                  <span className={cn(
                    "text-[10px] font-bold px-2 py-0.5 rounded-full",
                    (log.latency || 0) < 1 ? "bg-success/10 text-success" :
                    (log.latency || 0) < 3 ? "bg-warning/10 text-warning" :
                    "bg-danger/10 text-danger"
                  )}>{log.latency?.toFixed(1)}s</span>
                </div>
                <p className="text-sm font-medium truncate">{log.input}</p>
                <p className="text-xs text-yt-text-muted truncate mt-0.5">{log.output}</p>
              </div>
            ))}
            {logs.length === 0 && (
              <p className="text-yt-text-muted text-sm py-8 text-center">No recent activity</p>
            )}
          </div>
        </div>

        {/* Top FAQs */}
        <div className="yt-card p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-base">Top FAQs</h3>
            <TrendingUp className="w-5 h-5 text-success" />
          </div>
          <div className="space-y-2 max-h-80 overflow-y-auto custom-scrollbar">
            {(faq.top_faqs || []).map((f, i) => (
              <div key={i} className="p-3 rounded-xl bg-yt-surface-hover">
                <div className="flex items-start justify-between mb-1">
                  <span className="text-2xl font-black text-accent">#{i + 1}</span>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-500 flex items-center gap-1">
                    <Eye className="w-3 h-3" /> {f.hits} hits
                  </span>
                </div>
                <p className="text-sm font-semibold leading-relaxed">{f.question}</p>
              </div>
            ))}
            {(!faq.top_faqs || faq.top_faqs.length === 0) && (
              <p className="text-yt-text-muted text-sm py-8 text-center">No FAQ data available</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function formatTime(ts?: string) {
  if (!ts) return "";
  try {
    const d = new Date(ts);
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  } catch { return ts; }
}

function StatCard({
  icon: Icon, label, value, sub, color = "blue", isStatus = false,
}: { icon: React.ElementType; label: string; value: number | string; sub: string; color?: string; isStatus?: boolean }) {
  const colorMap: Record<string, string> = {
    purple: "text-accent",
    gold: "gradient-text-cmu",
    green: "text-success",
  };
  const valCls = colorMap[color] || "text-yt-text";
  return (
    <div className="yt-card p-5">
      <div className="flex items-center justify-between mb-3">
        <p className="text-[10px] font-bold uppercase tracking-wider text-yt-text-muted">{label}</p>
        <div className="p-2 rounded-lg bg-yt-surface-hover">
          <Icon className="w-5 h-5 text-yt-text-muted" />
        </div>
      </div>
      {isStatus ? (
        <div className="flex items-center gap-3 mt-1">
          <div className="w-3 h-3 rounded-full bg-success animate-pulse" />
          <span className="font-black text-xl text-success">{value}</span>
        </div>
      ) : (
        <h3 className={cn("text-3xl md:text-4xl font-black", valCls)}>{value}</h3>
      )}
      <p className="text-xs text-yt-text-muted mt-1">{sub}</p>
    </div>
  );
}
