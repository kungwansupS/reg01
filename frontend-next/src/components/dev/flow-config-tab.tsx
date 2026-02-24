"use client";

import { useState, useEffect, useCallback } from "react";
import { Save, RotateCcw, RefreshCw } from "lucide-react";
import { devFetch } from "@/lib/api";

interface FlowConfig {
  rag_mode?: string;
  rag_top_k?: number;
  use_hybrid?: boolean;
  use_intent_analysis?: boolean;
  use_llm_rerank?: boolean;
  enable_summary?: boolean;
  recent_messages?: number;
  pose_enabled?: boolean;
  faq_auto_learn?: boolean;
  faq_lookup_enabled?: boolean;
  faq_block_time_sensitive?: boolean;
  faq_max_age_days?: number;
  faq_time_sensitive_ttl_hours?: number;
  faq_min_answer_chars?: number;
  faq_min_retrieval_score?: number;
  faq_similarity_threshold?: number;
  extra_context_instruction?: string;
}

interface HistoryItem {
  revision: string;
  updated_by?: string;
  timestamp?: string;
}

export function FlowConfigTab() {
  const [config, setConfig] = useState<FlowConfig>({});
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [selectedHistory, setSelectedHistory] = useState("");
  const [status, setStatus] = useState("");

  const loadFlow = useCallback(async () => {
    try {
      const res = await devFetch("/api/dev/flow");
      if (res.ok) {
        const data = await res.json();
        setConfig(data.config || data);
      }
    } catch { setStatus("Failed to load"); }
  }, []);

  const loadHistory = useCallback(async () => {
    try {
      const res = await devFetch("/api/dev/flow/history?limit=20");
      if (res.ok) {
        const data = await res.json();
        setHistory(Array.isArray(data) ? data : data.items || []);
      }
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadFlow(); loadHistory(); }, [loadFlow, loadHistory]);

  async function saveFlow() {
    setStatus("Saving...");
    try {
      const res = await devFetch("/api/dev/flow", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config, updated_by: "dev-ui" }),
      });
      if (res.ok) { setStatus("Saved!"); loadHistory(); }
      else setStatus("Save failed");
    } catch { setStatus("Save error"); }
  }

  async function rollback() {
    if (!selectedHistory) return;
    if (!confirm(`Rollback to revision ${selectedHistory}?`)) return;
    try {
      const res = await devFetch("/api/dev/flow/rollback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ revision: selectedHistory, updated_by: "dev-rollback" }),
      });
      if (res.ok) { setStatus("Rolled back!"); loadFlow(); loadHistory(); }
      else setStatus("Rollback failed");
    } catch { setStatus("Rollback error"); }
  }

  async function loadHistoryItem() {
    if (!selectedHistory) return;
    // Find history item and load that config
    const item = history.find((h) => h.revision === selectedHistory);
    if (item) setStatus(`Loaded revision ${selectedHistory}`);
  }

  function updateConfig<K extends keyof FlowConfig>(key: K, value: FlowConfig[K]) {
    setConfig((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">Flow Config (Active/Draft)</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Field label="RAG Mode">
          <select value={config.rag_mode || "keyword"} onChange={(e) => updateConfig("rag_mode", e.target.value)} className="dev-input">
            <option value="keyword">keyword (ใช้ query_request)</option>
            <option value="always">always (ทุกคำถาม)</option>
            <option value="never">never (ปิด RAG)</option>
          </select>
        </Field>
        <Field label="RAG top_k (1-20)">
          <input type="number" min={1} max={20} value={config.rag_top_k ?? 5} onChange={(e) => updateConfig("rag_top_k", Number(e.target.value))} className="dev-input" />
        </Field>
        <Check label="use_hybrid" checked={!!config.use_hybrid} onChange={(v) => updateConfig("use_hybrid", v)} />
        <Check label="use_intent_analysis" checked={!!config.use_intent_analysis} onChange={(v) => updateConfig("use_intent_analysis", v)} />
        <Check label="use_llm_rerank" checked={!!config.use_llm_rerank} onChange={(v) => updateConfig("use_llm_rerank", v)} />
        <Check label="enable_summary" checked={!!config.enable_summary} onChange={(v) => updateConfig("enable_summary", v)} />
        <Field label="recent_messages (1-30)">
          <input type="number" min={1} max={30} value={config.recent_messages ?? 10} onChange={(e) => updateConfig("recent_messages", Number(e.target.value))} className="dev-input" />
        </Field>
        <Check label="pose_enabled" checked={!!config.pose_enabled} onChange={(v) => updateConfig("pose_enabled", v)} />
        <Check label="faq_auto_learn" checked={!!config.faq_auto_learn} onChange={(v) => updateConfig("faq_auto_learn", v)} />
        <Check label="faq_lookup_enabled" checked={!!config.faq_lookup_enabled} onChange={(v) => updateConfig("faq_lookup_enabled", v)} />
        <Check label="faq_block_time_sensitive" checked={!!config.faq_block_time_sensitive} onChange={(v) => updateConfig("faq_block_time_sensitive", v)} />
        <Field label="faq_max_age_days (1-365)">
          <input type="number" min={1} max={365} value={config.faq_max_age_days ?? 30} onChange={(e) => updateConfig("faq_max_age_days", Number(e.target.value))} className="dev-input" />
        </Field>
        <Field label="faq_time_sensitive_ttl_hours (1-168)">
          <input type="number" min={1} max={168} value={config.faq_time_sensitive_ttl_hours ?? 24} onChange={(e) => updateConfig("faq_time_sensitive_ttl_hours", Number(e.target.value))} className="dev-input" />
        </Field>
        <Field label="faq_min_answer_chars (10-2000)">
          <input type="number" min={10} max={2000} value={config.faq_min_answer_chars ?? 50} onChange={(e) => updateConfig("faq_min_answer_chars", Number(e.target.value))} className="dev-input" />
        </Field>
        <Field label="faq_min_retrieval_score (0-1)">
          <input type="number" min={0} max={1} step={0.01} value={config.faq_min_retrieval_score ?? 0.5} onChange={(e) => updateConfig("faq_min_retrieval_score", Number(e.target.value))} className="dev-input" />
        </Field>
        <Field label="faq_similarity_threshold (0.5-0.99)">
          <input type="number" min={0.5} max={0.99} step={0.01} value={config.faq_similarity_threshold ?? 0.85} onChange={(e) => updateConfig("faq_similarity_threshold", Number(e.target.value))} className="dev-input" />
        </Field>
        <div className="col-span-full">
          <Field label="extra_context_instruction">
            <textarea value={config.extra_context_instruction || ""} onChange={(e) => updateConfig("extra_context_instruction", e.target.value)} placeholder="คำสั่งเพิ่มสำหรับปัญญา (ต่อท้าย prompt)" className="dev-input min-h-[80px] resize-y" />
          </Field>
        </div>
      </div>

      <div className="flex gap-2">
        <button onClick={saveFlow} className="dev-btn-primary"><Save className="w-4 h-4" /> Save Active Flow</button>
        <button onClick={loadFlow} className="dev-btn"><RefreshCw className="w-4 h-4" /> Reload</button>
      </div>

      <div className="grid grid-cols-[1fr_auto_auto] gap-2 items-center">
        <select value={selectedHistory} onChange={(e) => setSelectedHistory(e.target.value)} className="dev-input">
          <option value="">-- history --</option>
          {history.map((h) => (
            <option key={h.revision} value={h.revision}>{h.revision} ({h.updated_by}) {h.timestamp}</option>
          ))}
        </select>
        <button onClick={loadHistoryItem} className="dev-btn">Load History</button>
        <button onClick={rollback} className="dev-btn-danger"><RotateCcw className="w-4 h-4" /> Rollback</button>
      </div>

      {status && <p className="text-sm text-[var(--muted)]">{status}</p>}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-[var(--muted)]">{label}</label>
      {children}
    </div>
  );
}

function Check({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center gap-2">
      <label className="text-xs text-[var(--muted)] flex items-center gap-2 cursor-pointer">
        <input type="checkbox" checked={checked} onChange={() => onChange(!checked)} className="accent-[var(--accent)]" />
        {label}
      </label>
    </div>
  );
}
