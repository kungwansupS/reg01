"use client";

import { useState, useCallback } from "react";
import { RefreshCw, Play, Save, Trash2 } from "lucide-react";
import { devFetch } from "@/lib/api";

interface Scenario {
  id: string;
  name?: string;
  description?: string;
  message?: string;
  config_override?: Record<string, unknown>;
}

export function ScenariosTab() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selected, setSelected] = useState("");
  const [form, setForm] = useState<Scenario>({ id: "", name: "", description: "", message: "", config_override: {} });
  const [configText, setConfigText] = useState("{}");
  const [runOutput, setRunOutput] = useState("");
  const [runMeta, setRunMeta] = useState("");
  const [status, setStatus] = useState("");

  const loadScenarios = useCallback(async () => {
    try {
      const res = await devFetch("/api/dev/scenarios");
      if (res.ok) {
        const data = await res.json();
        setScenarios(data.items || []);
      }
    } catch { /* ignore */ }
  }, []);

  async function loadScenario() {
    if (!selected) return;
    try {
      const res = await devFetch(`/api/dev/scenarios/${selected}`);
      if (res.ok) {
        const data = await res.json();
        setForm(data);
        setConfigText(JSON.stringify(data.config_override || {}, null, 2));
        setStatus(`Loaded: ${data.name || selected}`);
      }
    } catch { setStatus("Load failed"); }
  }

  async function saveScenario() {
    let cfg = {};
    try { cfg = JSON.parse(configText); } catch { setStatus("Invalid JSON in config_override"); return; }
    const payload = { ...form, config_override: cfg };
    try {
      const res = await devFetch("/api/dev/scenarios", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) { setStatus("Saved!"); loadScenarios(); }
      else setStatus("Save failed");
    } catch { setStatus("Save error"); }
  }

  async function deleteScenario() {
    if (!selected || !confirm(`Delete scenario ${selected}?`)) return;
    try {
      const res = await devFetch(`/api/dev/scenarios/${selected}`, { method: "DELETE" });
      if (res.ok) { setStatus("Deleted"); setSelected(""); loadScenarios(); }
      else setStatus("Delete failed");
    } catch { setStatus("Delete error"); }
  }

  async function runScenario() {
    if (!selected) { setStatus("Select a scenario first"); return; }
    setRunOutput("Running...");
    setRunMeta("");
    try {
      const res = await devFetch(`/api/dev/scenarios/${selected}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (res.ok) {
        const data = await res.json();
        setRunOutput(JSON.stringify(data.result || data, null, 2));
        setRunMeta(`Latency: ${data.latency_ms || 0}ms | Status: ${data.status || "done"}`);
      } else {
        setRunOutput(`Error: ${res.status}`);
      }
    } catch (e) { setRunOutput(`Error: ${e}`); }
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">Scenarios + Replay</h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* Left: Scenario List */}
        <div className="dev-panel space-y-3">
          <div className="flex items-center justify-between">
            <strong className="text-sm">Scenario List</strong>
            <button onClick={loadScenarios} className="dev-btn text-xs"><RefreshCw className="w-3 h-3" /> Refresh</button>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[var(--muted)]">Scenario</label>
            <select value={selected} onChange={(e) => setSelected(e.target.value)} className="dev-input">
              <option value="">-- select --</option>
              {scenarios.map((s) => <option key={s.id} value={s.id}>{s.name || s.id}</option>)}
            </select>
          </div>
          <div className="flex gap-2">
            <button onClick={() => { setForm({ id: "", name: "", description: "", message: "" }); setConfigText("{}"); setStatus("New scenario"); }} className="dev-btn text-xs">New</button>
            <button onClick={loadScenario} className="dev-btn text-xs">Load</button>
            <button onClick={deleteScenario} className="dev-btn-danger text-xs"><Trash2 className="w-3 h-3" /> Delete</button>
          </div>
          {status && <p className="text-xs text-[var(--muted)]">{status}</p>}
          <p className="text-xs text-[var(--muted)]">Last Run Output</p>
          <pre className="dev-output text-xs max-h-48 overflow-auto">{runOutput || "..."}</pre>
          {runMeta && <p className="text-xs text-[var(--muted)]">{runMeta}</p>}
        </div>

        {/* Right: Scenario Editor */}
        <div className="dev-panel space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-[var(--muted)]">id</label>
              <input value={form.id} onChange={(e) => setForm({ ...form, id: e.target.value })} placeholder="scenario_id (optional)" className="dev-input" />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-[var(--muted)]">name</label>
              <input value={form.name || ""} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Scenario Name" className="dev-input" />
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[var(--muted)]">description</label>
            <textarea value={form.description || ""} onChange={(e) => setForm({ ...form, description: e.target.value })} className="dev-input min-h-[60px] resize-y" />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[var(--muted)]">message</label>
            <textarea value={form.message || ""} onChange={(e) => setForm({ ...form, message: e.target.value })} className="dev-input min-h-[60px] resize-y" />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[var(--muted)]">config_override (JSON)</label>
            <textarea value={configText} onChange={(e) => setConfigText(e.target.value)} className="dev-input min-h-[100px] resize-y font-mono text-xs" />
          </div>
          <div className="flex gap-2">
            <button onClick={saveScenario} className="dev-btn-primary text-xs"><Save className="w-3 h-3" /> Save Scenario</button>
            <button onClick={runScenario} className="dev-btn-primary text-xs"><Play className="w-3 h-3" /> Run Scenario</button>
          </div>
        </div>
      </div>
    </div>
  );
}
