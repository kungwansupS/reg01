"use client";

import { useState, useCallback } from "react";
import { Terminal, Play, Settings, GitBranch, BarChart3, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";

const DEV_TABS = [
  { id: "traces", label: "Traces", icon: Terminal },
  { id: "flow", label: "Flow Config", icon: Settings },
  { id: "architecture", label: "Architecture", icon: GitBranch },
  { id: "benchmark", label: "Benchmark", icon: BarChart3 },
] as const;

type DevTab = (typeof DEV_TABS)[number]["id"];

export default function DevPage() {
  const [activeTab, setActiveTab] = useState<DevTab>("traces");
  const [devToken, setDevToken] = useState(() =>
    typeof window !== "undefined" ? localStorage.getItem("dev_token") || "" : ""
  );
  const [isLoggedIn, setIsLoggedIn] = useState(() => !!devToken);
  const [tokenInput, setTokenInput] = useState("");

  const handleLogin = useCallback(() => {
    if (!tokenInput.trim()) return;
    localStorage.setItem("dev_token", tokenInput.trim());
    setDevToken(tokenInput.trim());
    setIsLoggedIn(true);
  }, [tokenInput]);

  if (!isLoggedIn) {
    return (
      <div className="min-h-screen bg-[#060b16] flex items-center justify-center p-4">
        <div className="bg-[#111a2d] border border-[#2a3858] rounded-2xl p-8 w-full max-w-md shadow-2xl">
          <div className="text-center mb-8">
            <div className="bg-[#23c58f] w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <ShieldCheck className="text-white w-8 h-8" />
            </div>
            <h2 className="text-2xl font-black text-[#23c58f]">Dev Console</h2>
            <p className="text-sm text-[#9fb0cb] mt-1">REG-01 Developer Tools</p>
          </div>
          <div className="space-y-4">
            <input
              type="password"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleLogin()}
              placeholder="Dev Token"
              className="w-full px-4 py-3 bg-[#0a1222] border border-[#2a3858] rounded-xl text-center font-mono tracking-widest text-white outline-none focus:ring-2 focus:ring-[#23c58f]/50"
            />
            <button
              onClick={handleLogin}
              className="w-full bg-[#23c58f] text-white font-bold py-3 rounded-xl hover:bg-[#1aa379] transition"
            >
              Authenticate
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-[#060b16] text-[#e5edf8]">
      {/* Sidebar */}
      <aside className="w-56 bg-[#0d1424] border-r border-[#2a3858] flex flex-col">
        <div className="p-4 border-b border-[#2a3858]">
          <span className="font-black text-lg text-[#23c58f]">REG-01</span>
          <p className="text-[10px] text-[#9fb0cb]">Dev Console</p>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {DEV_TABS.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all",
                  activeTab === tab.id
                    ? "bg-[#23c58f]/15 text-[#23c58f]"
                    : "text-[#9fb0cb] hover:bg-[#18223a] hover:text-white"
                )}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto p-6">
        {activeTab === "traces" && <TracesPanel devToken={devToken} />}
        {activeTab === "flow" && <FlowPanel devToken={devToken} />}
        {activeTab === "architecture" && <ArchPanel devToken={devToken} />}
        {activeTab === "benchmark" && <BenchPanel devToken={devToken} />}
      </main>
    </div>
  );
}

function devFetch(path: string, token: string, init?: RequestInit) {
  const headers = new Headers(init?.headers);
  headers.set("X-Dev-Token", token);
  headers.set("Authorization", `Bearer ${token}`);
  return fetch(path, { ...init, headers });
}

function TracesPanel({ devToken }: { devToken: string }) {
  const [traces, setTraces] = useState<Array<{ trace_id: string; question?: string; timestamp?: string }>>([]);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const res = await devFetch("/api/dev/traces?limit=20", devToken);
      if (res.ok) {
        const data = await res.json();
        setTraces(data.traces || []);
      }
    } catch { /* ignore */ }
    setLoading(false);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Traces</h2>
        <button onClick={load} className="px-4 py-2 bg-[#23c58f] rounded-lg text-sm font-medium flex items-center gap-2">
          <Play className="w-4 h-4" /> Load
        </button>
      </div>
      {loading && <p className="text-[#9fb0cb]">Loading...</p>}
      <div className="space-y-2">
        {traces.map((t) => (
          <div key={t.trace_id} className="bg-[#111a2d] border border-[#2a3858] rounded-lg p-3 text-sm">
            <p className="font-mono text-xs text-[#9fb0cb]">{t.trace_id}</p>
            <p className="mt-1">{t.question}</p>
            <p className="text-[10px] text-[#9fb0cb] mt-1">{t.timestamp}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function FlowPanel({ devToken }: { devToken: string }) {
  const [config, setConfig] = useState<Record<string, unknown> | null>(null);

  async function load() {
    try {
      const res = await devFetch("/api/dev/flow", devToken);
      if (res.ok) setConfig(await res.json());
    } catch { /* ignore */ }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Flow Configuration</h2>
        <button onClick={load} className="px-4 py-2 bg-[#23c58f] rounded-lg text-sm font-medium">Load</button>
      </div>
      {config && (
        <pre className="bg-[#0a1222] border border-[#2a3858] rounded-lg p-4 text-xs overflow-auto max-h-[70vh] custom-scrollbar">
          {JSON.stringify(config, null, 2)}
        </pre>
      )}
    </div>
  );
}

function ArchPanel({ devToken }: { devToken: string }) {
  const [arch, setArch] = useState<string | null>(null);

  async function load() {
    try {
      const res = await devFetch("/api/dev/architecture", devToken);
      if (res.ok) {
        const data = await res.json();
        setArch(data.text || JSON.stringify(data, null, 2));
      }
    } catch { /* ignore */ }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Architecture</h2>
        <button onClick={load} className="px-4 py-2 bg-[#23c58f] rounded-lg text-sm font-medium">Load</button>
      </div>
      {arch && (
        <pre className="bg-[#0a1222] border border-[#2a3858] rounded-lg p-4 text-xs overflow-auto max-h-[70vh] whitespace-pre-wrap custom-scrollbar">
          {arch}
        </pre>
      )}
    </div>
  );
}

function BenchPanel({ devToken }: { devToken: string }) {
  const [result, setResult] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  async function runBench() {
    setRunning(true);
    setResult(null);
    try {
      const res = await devFetch("/api/dev/benchmark", devToken, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setResult(JSON.stringify(data, null, 2));
      }
    } catch { /* ignore */ }
    setRunning(false);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Benchmark</h2>
        <button onClick={runBench} disabled={running} className="px-4 py-2 bg-[#23c58f] rounded-lg text-sm font-medium disabled:opacity-50">
          {running ? "Running..." : "Run Benchmark"}
        </button>
      </div>
      {result && (
        <pre className="bg-[#0a1222] border border-[#2a3858] rounded-lg p-4 text-xs overflow-auto max-h-[70vh] custom-scrollbar">
          {result}
        </pre>
      )}
    </div>
  );
}
