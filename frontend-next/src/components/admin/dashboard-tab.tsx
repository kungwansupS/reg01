"use client";

import { useState, useEffect } from "react";
import { Users, MessageSquare, Zap, Clock, ToggleLeft, ToggleRight } from "lucide-react";
import { adminFetch } from "@/lib/api";

interface Stats {
  queue?: { pending?: number; active?: number; processed?: number; errors?: number };
  active_sessions?: number;
  faq_analytics?: { total_entries?: number; hit_rate?: string };
  recent_activity?: Array<{ timestamp?: string; anon_id?: string; input?: string; output?: string }>;
}

export function DashboardTab() {
  const [stats, setStats] = useState<Stats>({});
  const [botEnabled, setBotEnabled] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
    const interval = setInterval(loadStats, 10000);
    return () => clearInterval(interval);
  }, []);

  async function loadStats() {
    try {
      const res = await adminFetch("/api/admin/stats");
      if (res.ok) setStats(await res.json());
    } catch { /* ignore */ }
    try {
      const res = await adminFetch("/api/admin/bot-status");
      if (res.ok) {
        const data = await res.json();
        setBotEnabled(data.bot_enabled ?? true);
      }
    } catch { /* ignore */ }
    setLoading(false);
  }

  async function toggleBot() {
    const form = new FormData();
    form.append("enabled", String(!botEnabled));
    try {
      const res = await adminFetch("/api/admin/bot-toggle", { method: "POST", body: form });
      if (res.ok) setBotEnabled(!botEnabled);
    } catch { /* ignore */ }
  }

  if (loading) return <div className="p-8 text-zinc-500">Loading dashboard...</div>;

  const q = stats.queue || {};

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Users} label="Active Sessions" value={stats.active_sessions ?? 0} />
        <StatCard icon={MessageSquare} label="Processed" value={q.processed ?? 0} />
        <StatCard icon={Zap} label="Queue Pending" value={q.pending ?? 0} color="yellow" />
        <StatCard icon={Clock} label="Errors" value={q.errors ?? 0} color="red" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Bot Status */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-zinc-400 mb-4">Bot Status</h3>
          <div className="flex items-center justify-between">
            <span className="text-lg font-bold">{botEnabled ? "Active" : "Disabled"}</span>
            <button onClick={toggleBot} className="text-cmu-purple-light hover:opacity-80 transition">
              {botEnabled ? <ToggleRight className="w-8 h-8" /> : <ToggleLeft className="w-8 h-8 text-zinc-500" />}
            </button>
          </div>
        </div>

        {/* FAQ Stats */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-zinc-400 mb-4">FAQ Cache</h3>
          <p className="text-lg font-bold">{stats.faq_analytics?.total_entries ?? 0} entries</p>
          <p className="text-sm text-zinc-500 mt-1">Hit rate: {stats.faq_analytics?.hit_rate ?? "N/A"}</p>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-zinc-400 mb-4">Recent Activity</h3>
        <div className="space-y-2 max-h-64 overflow-y-auto custom-scrollbar">
          {(stats.recent_activity || []).slice(0, 10).map((item, i) => (
            <div key={i} className="flex items-start gap-3 text-xs border-b border-zinc-800 pb-2">
              <span className="text-zinc-500 shrink-0 w-32">{item.timestamp}</span>
              <span className="text-zinc-300 truncate flex-1">{item.input}</span>
            </div>
          ))}
          {(!stats.recent_activity || stats.recent_activity.length === 0) && (
            <p className="text-zinc-600 text-sm">No recent activity</p>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({
  icon: Icon, label, value, color = "purple",
}: { icon: React.ElementType; label: string; value: number | string; color?: string }) {
  const colors: Record<string, string> = {
    purple: "text-cmu-purple-light",
    yellow: "text-yellow-400",
    red: "text-red-400",
  };
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
      <div className="flex items-center gap-3">
        <Icon className={`w-5 h-5 ${colors[color] || colors.purple}`} />
        <div>
          <p className="text-xs text-zinc-500">{label}</p>
          <p className="text-xl font-bold">{value}</p>
        </div>
      </div>
    </div>
  );
}
