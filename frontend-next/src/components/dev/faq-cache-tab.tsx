"use client";

import { useState, useCallback } from "react";
import { RefreshCw, Save, Trash2, Plus } from "lucide-react";
import { devFetch } from "@/lib/api";

interface FaqEntry {
  question: string;
  original_question?: string;
  answer?: string;
  count?: number;
  time_sensitive?: boolean;
  ttl_seconds?: number;
  source?: string;
  expired?: boolean;
}

export function FaqCacheTab() {
  const [entries, setEntries] = useState<FaqEntry[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [includeExpired, setIncludeExpired] = useState(false);
  const [selectedQ, setSelectedQ] = useState("");
  const [form, setForm] = useState<FaqEntry>({ question: "", answer: "", original_question: "" });
  const [status, setStatus] = useState("");
  const [editStatus, setEditStatus] = useState("");
  const [summary, setSummary] = useState("");

  const loadEntries = useCallback(async () => {
    try {
      const params = new URLSearchParams({ limit: "300" });
      if (searchQuery) params.set("query", searchQuery);
      if (includeExpired) params.set("include_expired", "1");
      const res = await devFetch(`/api/dev/faq?${params}`);
      if (res.ok) {
        const data = await res.json();
        const items = data.items || data.entries || [];
        setEntries(items);
        setSummary(`${items.length} entries`);
      }
    } catch { setStatus("Load failed"); }
  }, [searchQuery, includeExpired]);

  async function loadEntry() {
    if (!selectedQ) return;
    try {
      const res = await devFetch(`/api/dev/faq/entry?question=${encodeURIComponent(selectedQ)}`);
      if (res.ok) {
        const data = await res.json();
        setForm(data);
        setEditStatus(`Loaded: ${selectedQ}`);
      } else setEditStatus("Not found");
    } catch { setEditStatus("Load error"); }
  }

  async function saveEntry() {
    if (!form.question) { setEditStatus("Question required"); return; }
    try {
      const res = await devFetch("/api/dev/faq/entry", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: form.question,
          answer: form.answer || "",
          original_question: form.original_question || form.question,
          count: form.count || 0,
          time_sensitive: form.time_sensitive || false,
          ttl_seconds: form.ttl_seconds || 86400,
          source: form.source || "dev-ui",
        }),
      });
      if (res.ok) { setEditStatus("Saved!"); loadEntries(); }
      else setEditStatus("Save failed");
    } catch { setEditStatus("Save error"); }
  }

  async function deleteEntry() {
    if (!selectedQ || !confirm(`Delete FAQ: ${selectedQ}?`)) return;
    try {
      const res = await devFetch(`/api/dev/faq/entry?question=${encodeURIComponent(selectedQ)}`, { method: "DELETE" });
      if (res.ok) { setStatus("Deleted"); setSelectedQ(""); loadEntries(); }
      else setStatus("Delete failed");
    } catch { setStatus("Delete error"); }
  }

  async function purgeExpired() {
    if (!confirm("Purge all expired FAQ entries?")) return;
    try {
      const res = await devFetch("/api/dev/faq/purge-expired", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setStatus(`Purged ${data.deleted || 0} entries`);
        loadEntries();
      }
    } catch { setStatus("Purge error"); }
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">FAQ Cache Review</h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* Left: FAQ List */}
        <div className="dev-panel space-y-3">
          <div className="flex items-center justify-between">
            <strong className="text-sm">FAQ List</strong>
            <button onClick={loadEntries} className="dev-btn text-xs"><RefreshCw className="w-3 h-3" /> Refresh</button>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[var(--muted)]">Search</label>
            <input value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="question or answer keyword" className="dev-input" />
          </div>
          <div className="flex items-center gap-3">
            <label className="text-xs flex items-center gap-1 cursor-pointer">
              <input type="checkbox" checked={includeExpired} onChange={() => setIncludeExpired(!includeExpired)} className="accent-[var(--accent)]" />
              include expired
            </label>
            <button onClick={purgeExpired} className="dev-btn-danger text-xs"><Trash2 className="w-3 h-3" /> Purge Expired</button>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[var(--muted)]">Entries</label>
            <select
              value={selectedQ}
              onChange={(e) => setSelectedQ(e.target.value)}
              size={14}
              className="dev-input font-mono text-xs min-h-[280px]"
            >
              {entries.map((e, i) => (
                <option key={i} value={e.question} className={e.expired ? "text-red-400" : ""}>
                  {e.expired ? "[EXP] " : ""}{e.question} ({e.count || 0})
                </option>
              ))}
            </select>
          </div>
          <div className="flex gap-2">
            <button onClick={() => { setForm({ question: "", answer: "", original_question: "" }); setSelectedQ(""); setEditStatus("New entry"); }} className="dev-btn text-xs"><Plus className="w-3 h-3" /> New</button>
            <button onClick={loadEntry} className="dev-btn text-xs">Load</button>
            <button onClick={deleteEntry} className="dev-btn-danger text-xs"><Trash2 className="w-3 h-3" /> Delete</button>
          </div>
          {status && <p className="text-xs text-[var(--muted)]">{status}</p>}
          {summary && <p className="text-[10px] text-[var(--muted)]">{summary}</p>}
        </div>

        {/* Right: Editor */}
        <div className="dev-panel space-y-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[var(--muted)]">original_question</label>
            <input value={form.original_question || ""} readOnly className="dev-input opacity-60" />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[var(--muted)]">question</label>
            <input value={form.question} onChange={(e) => setForm({ ...form, question: e.target.value })} placeholder="FAQ question" className="dev-input" />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[var(--muted)]">answer</label>
            <textarea value={form.answer || ""} onChange={(e) => setForm({ ...form, answer: e.target.value })} placeholder="FAQ answer" className="dev-input min-h-[200px] font-mono text-xs resize-y" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-[var(--muted)]">count</label>
              <input type="number" min={0} value={form.count || 0} onChange={(e) => setForm({ ...form, count: Number(e.target.value) })} className="dev-input" />
            </div>
            <div className="flex items-center gap-2 pt-4">
              <label className="text-xs flex items-center gap-1 cursor-pointer">
                <input type="checkbox" checked={form.time_sensitive || false} onChange={() => setForm({ ...form, time_sensitive: !form.time_sensitive })} className="accent-[var(--accent)]" />
                time_sensitive
              </label>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-[var(--muted)]">ttl_seconds</label>
              <input type="number" min={60} max={31536000} value={form.ttl_seconds || 86400} onChange={(e) => setForm({ ...form, ttl_seconds: Number(e.target.value) })} className="dev-input" />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-[var(--muted)]">source</label>
              <input value={form.source || ""} onChange={(e) => setForm({ ...form, source: e.target.value })} placeholder="dev-ui/manual" className="dev-input" />
            </div>
          </div>
          <button onClick={saveEntry} className="dev-btn-primary"><Save className="w-4 h-4" /> Save FAQ Entry</button>
          {editStatus && <p className="text-xs text-[var(--muted)]">{editStatus}</p>}
        </div>
      </div>
    </div>
  );
}
