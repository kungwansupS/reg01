"use client";

import { useEffect, useRef, useState } from "react";
import { Activity, Wifi, WifiOff } from "lucide-react";

import { adminFetch } from "@/lib/api";
import { useSocket } from "@/providers/socket-provider";

interface QueueStats {
  pending?: number;
  active?: number;
  processed?: number;
  errors?: number;
  throughput?: string;
  capacity?: string;
  workers?: number;
  peak_pending?: number;
  uptime?: string;
}

interface FeedItem {
  id: string;
  type: "message" | "reply";
  text: string;
  timestamp: string;
}

export function MonitorTab() {
  const { socket, connected } = useSocket();
  const [stats, setStats] = useState<QueueStats>({});
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [socketLive, setSocketLive] = useState(false);
  const feedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!socket) return;

    function handleStats(data: QueueStats) {
      setStats(data);
      setSocketLive(true);
    }

    function handleNewMessage(data: { anon_id?: string; input?: string }) {
      const item: FeedItem = {
        id: crypto.randomUUID(),
        type: "message",
        text: `[${data.anon_id?.slice(0, 8)}] ${data.input ?? ""}`,
        timestamp: new Date().toLocaleTimeString(),
      };
      setFeed((prev) => [item, ...prev].slice(0, 50));
    }

    function handleBotReply(data: { anon_id?: string; output?: string }) {
      const item: FeedItem = {
        id: crypto.randomUUID(),
        type: "reply",
        text: `[Bot -> ${data.anon_id?.slice(0, 8)}] ${(data.output ?? "").slice(0, 80)}`,
        timestamp: new Date().toLocaleTimeString(),
      };
      setFeed((prev) => [item, ...prev].slice(0, 50));
    }

    socket.on("admin_stats_update", handleStats);
    socket.on("admin_new_message", handleNewMessage);
    socket.on("admin_bot_reply", handleBotReply);

    return () => {
      socket.off("admin_stats_update", handleStats);
      socket.off("admin_new_message", handleNewMessage);
      socket.off("admin_bot_reply", handleBotReply);
    };
  }, [socket]);

  useEffect(() => {
    const timer = setTimeout(async () => {
      if (socketLive) return;
      try {
        const res = await adminFetch("/api/admin/monitor/stats");
        if (!res.ok) return;
        const data = await res.json();
        setStats(data.queue || {});
      } catch {
        // Ignore fallback polling errors.
      }
    }, 10000);
    return () => clearTimeout(timer);
  }, [socketLive]);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Activity className="w-6 h-6 text-cmu-purple-light" /> Live Monitor
        </h1>
        <div className="flex items-center gap-2 text-xs">
          {connected ? (
            <span className="flex items-center gap-1 text-green-400">
              <Wifi className="w-3.5 h-3.5" /> Live
            </span>
          ) : (
            <span className="flex items-center gap-1 text-red-400">
              <WifiOff className="w-3.5 h-3.5" /> Offline
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <MetricCard label="Pending" value={stats.pending ?? 0} />
        <MetricCard label="Active" value={stats.active ?? 0} />
        <MetricCard label="Processed" value={stats.processed ?? 0} />
        <MetricCard label="Errors" value={stats.errors ?? 0} color="red" />
        <MetricCard label="Workers" value={stats.workers ?? 0} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <p className="text-xs text-zinc-500">Throughput</p>
          <p className="text-lg font-bold">{stats.throughput || "0 req/min"}</p>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <p className="text-xs text-zinc-500">Capacity</p>
          <p className="text-lg font-bold">{stats.capacity || "0%"}</p>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <p className="text-xs text-zinc-500">Uptime</p>
          <p className="text-lg font-bold">{stats.uptime || "N/A"}</p>
        </div>
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
        <h3 className="text-sm font-semibold text-zinc-400 mb-3">Live Feed</h3>
        <div ref={feedRef} className="space-y-1 max-h-64 overflow-y-auto custom-scrollbar">
          {feed.length === 0 && <p className="text-zinc-600 text-xs">Waiting for activity...</p>}
          {feed.map((item) => (
            <div key={item.id} className="flex items-start gap-2 text-xs">
              <span className="text-zinc-600 shrink-0 w-16">{item.timestamp}</span>
              <span className={item.type === "reply" ? "text-cmu-purple-light" : "text-zinc-300"}>{item.text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  color = "default",
}: {
  label: string;
  value: number | string;
  color?: string;
}) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-3">
      <p className="text-[10px] text-zinc-500 uppercase tracking-wider">{label}</p>
      <p className={`text-xl font-bold ${color === "red" ? "text-red-400" : ""}`}>{value}</p>
    </div>
  );
}
