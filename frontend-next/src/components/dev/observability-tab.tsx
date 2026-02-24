"use client";

import { useState, useCallback } from "react";
import { RefreshCw, Play, Search, Send } from "lucide-react";
import { devFetch } from "@/lib/api";

interface TraceItem {
  trace_id: string;
  session_id?: string;
  question?: string;
  status?: string;
  timestamp?: string;
  latency_ms?: number;
  steps?: unknown[];
}

export function ObservabilityTab() {
  const [traces, setTraces] = useState<TraceItem[]>([]);
  const [selectedTrace, setSelectedTrace] = useState<TraceItem | null>(null);
  const [sessionFilter, setSessionFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [connOutput, setConnOutput] = useState("");
  const [routeOutput, setRouteOutput] = useState("");
  const [routeFilter, setRouteFilter] = useState("");
  const [probeMethod, setProbeMethod] = useState("GET");
  const [probePath, setProbePath] = useState("/api/dev/runtime/summary");
  const [probeQuery, setProbeQuery] = useState("{}");
  const [probeHeaders, setProbeHeaders] = useState("{}");
  const [probeBody, setProbeBody] = useState("");
  const [probeOutput, setProbeOutput] = useState("");
  const [logPath, setLogPath] = useState("logs/user_audit.log");
  const [logContains, setLogContains] = useState("");
  const [logPlatform, setLogPlatform] = useState("");
  const [logTraceId, setLogTraceId] = useState("");
  const [logSession, setLogSession] = useState("");
  const [logOutput, setLogOutput] = useState("");

  const loadTraces = useCallback(async () => {
    try {
      const params = new URLSearchParams({ limit: "80" });
      if (sessionFilter) params.set("session_id", sessionFilter);
      if (statusFilter) params.set("status", statusFilter);
      const res = await devFetch(`/api/dev/traces?${params}`);
      if (res.ok) {
        const data = await res.json();
        setTraces(data.items || []);
      }
    } catch { /* ignore */ }
  }, [sessionFilter, statusFilter]);

  async function loadTrace(t: TraceItem) {
    setSelectedTrace(t);
    try {
      const res = await devFetch(`/api/dev/traces/${t.trace_id}`);
      if (res.ok) setSelectedTrace(await res.json());
    } catch { /* ignore */ }
  }

  async function loadConnections() {
    try {
      const res = await devFetch("/api/dev/connections");
      if (res.ok) setConnOutput(JSON.stringify(await res.json(), null, 2));
    } catch { setConnOutput("Error loading connections"); }
  }

  async function loadRoutes() {
    try {
      const res = await devFetch("/api/dev/routes");
      if (res.ok) {
        const data = await res.json();
        const items = data.items || [];
        const filtered = routeFilter
          ? items.filter((r: { path?: string; method?: string; tags?: string[] }) =>
              (r.path || "").includes(routeFilter) || (r.method || "").includes(routeFilter) || (r.tags || []).join(",").includes(routeFilter))
          : items;
        setRouteOutput(JSON.stringify(filtered, null, 2));
      }
    } catch { setRouteOutput("Error loading routes"); }
  }

  async function sendProbe() {
    try {
      const res = await devFetch("/api/dev/http/probe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          method: probeMethod,
          path: probePath,
          query: JSON.parse(probeQuery || "{}"),
          headers: JSON.parse(probeHeaders || "{}"),
          body: probeBody || undefined,
        }),
      });
      if (res.ok) setProbeOutput(JSON.stringify(await res.json(), null, 2));
      else setProbeOutput(`Error: ${res.status}`);
    } catch (e) { setProbeOutput(`Error: ${e}`); }
  }

  async function searchLogs() {
    try {
      const params = new URLSearchParams({ path: logPath, limit: "120" });
      if (logContains) params.set("contains", logContains);
      if (logPlatform) params.set("platform", logPlatform);
      if (logTraceId) params.set("trace_id", logTraceId);
      if (logSession) params.set("session_id", logSession);
      const res = await devFetch(`/api/dev/logs/search?${params}`);
      if (res.ok) setLogOutput(JSON.stringify(await res.json(), null, 2));
      else setLogOutput(`Error: ${res.status}`);
    } catch (e) { setLogOutput(`Error: ${e}`); }
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">Observability</h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* Left: Trace Explorer */}
        <div className="dev-panel space-y-3">
          <div className="flex items-center justify-between">
            <strong className="text-sm">Trace Explorer</strong>
            <button onClick={loadTraces} className="dev-btn text-xs"><RefreshCw className="w-3 h-3" /> Refresh</button>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-[var(--muted)]">Session Filter</label>
              <input value={sessionFilter} onChange={(e) => setSessionFilter(e.target.value)} placeholder="session_id" className="dev-input" />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-[var(--muted)]">Status</label>
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="dev-input">
                <option value="">all</option>
                <option value="ok">ok</option>
                <option value="error">error</option>
              </select>
            </div>
          </div>
          <div className="dev-output max-h-64 overflow-auto">
            {traces.map((t) => (
              <div key={t.trace_id} onClick={() => loadTrace(t)} className={`p-2 rounded-lg mb-1 cursor-pointer border border-transparent hover:border-[var(--accent)]/50 ${selectedTrace?.trace_id === t.trace_id ? "border-[var(--accent)] bg-[var(--accent)]/10" : "bg-[rgba(7,13,26,0.7)]"}`}>
                <p className="text-xs font-mono truncate">{t.trace_id}</p>
                <p className="text-xs text-[var(--muted)] truncate">{t.question} — {t.status} ({t.latency_ms}ms)</p>
              </div>
            ))}
            {traces.length === 0 && <p className="text-xs text-[var(--muted)] text-center py-4">Click Refresh to load traces</p>}
          </div>
          {selectedTrace && (
            <>
              <p className="text-xs text-[var(--muted)]">Trace Steps</p>
              <pre className="dev-output text-xs max-h-40 overflow-auto">{JSON.stringify(selectedTrace.steps || [], null, 2)}</pre>
              <p className="text-xs text-[var(--muted)]">Trace Detail</p>
              <pre className="dev-output text-xs max-h-40 overflow-auto">{JSON.stringify(selectedTrace, null, 2)}</pre>
            </>
          )}
        </div>

        {/* Right: Connection Map, Route Map, API Probe, Log Search */}
        <div className="space-y-3">
          {/* Connection Map */}
          <div className="dev-panel space-y-2">
            <div className="flex items-center justify-between">
              <strong className="text-sm">Connection Map</strong>
              <button onClick={loadConnections} className="dev-btn text-xs"><RefreshCw className="w-3 h-3" /> Refresh</button>
            </div>
            <pre className="dev-output text-xs max-h-48 overflow-auto">{connOutput || "Click Refresh"}</pre>
          </div>

          {/* Route Map */}
          <div className="dev-panel space-y-2">
            <div className="flex items-center justify-between">
              <strong className="text-sm">Route Map</strong>
              <button onClick={loadRoutes} className="dev-btn text-xs"><RefreshCw className="w-3 h-3" /> Refresh</button>
            </div>
            <input value={routeFilter} onChange={(e) => setRouteFilter(e.target.value)} placeholder="path, method, tag" className="dev-input" />
            <pre className="dev-output text-xs max-h-48 overflow-auto">{routeOutput || "Click Refresh"}</pre>
          </div>

          {/* API Probe */}
          <div className="dev-panel space-y-2">
            <div className="flex items-center justify-between">
              <strong className="text-sm">API Probe</strong>
              <button onClick={sendProbe} className="dev-btn-primary text-xs"><Send className="w-3 h-3" /> Send</button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="flex flex-col gap-1">
                <label className="text-xs text-[var(--muted)]">Method</label>
                <select value={probeMethod} onChange={(e) => setProbeMethod(e.target.value)} className="dev-input">
                  {["GET", "POST", "PUT", "PATCH", "DELETE"].map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-[var(--muted)]">Path</label>
                <input value={probePath} onChange={(e) => setProbePath(e.target.value)} className="dev-input" />
              </div>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-[var(--muted)]">Query JSON</label>
              <textarea value={probeQuery} onChange={(e) => setProbeQuery(e.target.value)} className="dev-input min-h-[50px] font-mono text-xs" />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-[var(--muted)]">Body</label>
              <textarea value={probeBody} onChange={(e) => setProbeBody(e.target.value)} className="dev-input min-h-[50px] font-mono text-xs" />
            </div>
            <pre className="dev-output text-xs max-h-48 overflow-auto">{probeOutput || "..."}</pre>
          </div>

          {/* Log Search */}
          <div className="dev-panel space-y-2">
            <div className="flex items-center justify-between">
              <strong className="text-sm">Log Search</strong>
              <button onClick={searchLogs} className="dev-btn-primary text-xs"><Search className="w-3 h-3" /> Search</button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="flex flex-col gap-1">
                <label className="text-xs text-[var(--muted)]">Path</label>
                <input value={logPath} onChange={(e) => setLogPath(e.target.value)} className="dev-input" />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-[var(--muted)]">Contains</label>
                <input value={logContains} onChange={(e) => setLogContains(e.target.value)} className="dev-input" />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-[var(--muted)]">Platform</label>
                <select value={logPlatform} onChange={(e) => setLogPlatform(e.target.value)} className="dev-input">
                  <option value="">all</option>
                  <option value="web">web</option>
                  <option value="facebook">facebook</option>
                </select>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-[var(--muted)]">Session ID</label>
                <input value={logSession} onChange={(e) => setLogSession(e.target.value)} className="dev-input" />
              </div>
            </div>
            <pre className="dev-output text-xs max-h-48 overflow-auto">{logOutput || "..."}</pre>
          </div>
        </div>
      </div>
    </div>
  );
}
