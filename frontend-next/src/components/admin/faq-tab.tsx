"use client";

import { useState, useEffect, useCallback } from "react";
import { Plus, Pencil, Trash2, Search, Clock } from "lucide-react";
import { adminFetch } from "@/lib/api";

interface FaqItem {
  question: string;
  answer_preview?: string;
  source?: string;
  ttl_remaining?: number;
  expired?: boolean;
}

export function FaqTab() {
  const [items, setItems] = useState<FaqItem[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<{ question: string; answer: string; ttl: number; isNew: boolean } | null>(null);

  const loadFaq = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: "100", include_expired: "true" });
      if (query) params.set("query", query);
      const res = await adminFetch(`/api/admin/faq?${params}`);
      if (res.ok) {
        const data = await res.json();
        setItems(data.items || []);
      }
    } catch { /* ignore */ }
    setLoading(false);
  }, [query]);

  useEffect(() => { loadFaq(); }, [loadFaq]);

  async function handleDelete(question: string) {
    if (!confirm(`Delete FAQ: "${question}"?`)) return;
    try {
      await adminFetch(`/api/admin/faq?question=${encodeURIComponent(question)}`, { method: "DELETE" });
      await loadFaq();
    } catch { /* ignore */ }
  }

  async function handleEdit(question: string) {
    try {
      const res = await adminFetch(`/api/admin/faq/entry?question=${encodeURIComponent(question)}`);
      if (res.ok) {
        const data = await res.json();
        setEditing({ question: data.question, answer: data.answer || "", ttl: 86400, isNew: false });
      }
    } catch { /* ignore */ }
  }

  async function handleSave() {
    if (!editing) return;
    const form = new FormData();
    form.append("question", editing.question);
    form.append("answer", editing.answer);
    form.append("ttl_seconds", String(editing.ttl));
    form.append("source", "admin");
    if (!editing.isNew) form.append("original_question", editing.question);
    try {
      await adminFetch("/api/admin/faq", { method: "PUT", body: form });
      setEditing(null);
      await loadFaq();
    } catch { /* ignore */ }
  }

  async function handlePurge() {
    if (!confirm("Purge all expired FAQ entries?")) return;
    try {
      await adminFetch("/api/admin/faq/purge-expired", { method: "POST" });
      await loadFaq();
    } catch { /* ignore */ }
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">FAQ Manager</h1>
        <div className="flex gap-2">
          <button onClick={handlePurge} className="flex items-center gap-2 px-3 py-2 bg-zinc-800 rounded-lg hover:bg-zinc-700 text-sm">
            <Clock className="w-4 h-4" /> Purge Expired
          </button>
          <button
            onClick={() => setEditing({ question: "", answer: "", ttl: 86400, isNew: true })}
            className="flex items-center gap-2 px-3 py-2 gradient-cmu text-white rounded-lg text-sm"
          >
            <Plus className="w-4 h-4" /> Add Entry
          </button>
        </div>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search FAQ..."
          className="w-full bg-zinc-800 rounded-lg pl-10 pr-4 py-2 text-sm outline-none focus:ring-1 focus:ring-cmu-purple/50"
        />
      </div>

      {loading ? (
        <p className="text-zinc-500">Loading...</p>
      ) : (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800 text-zinc-500 text-left">
                <th className="px-4 py-3">Question</th>
                <th className="px-4 py-3">Answer</th>
                <th className="px-4 py-3 w-24">Source</th>
                <th className="px-4 py-3 w-28">Status</th>
                <th className="px-4 py-3 w-24">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.question} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
                  <td className="px-4 py-3 font-medium max-w-48 truncate">{item.question}</td>
                  <td className="px-4 py-3 text-zinc-400 max-w-64 truncate">{item.answer_preview}</td>
                  <td className="px-4 py-3 text-xs text-zinc-500">{item.source}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${item.expired ? "bg-red-500/20 text-red-400" : "bg-green-500/20 text-green-400"}`}>
                      {item.expired ? "expired" : "active"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1">
                      <button onClick={() => handleEdit(item.question)} className="p-1.5 hover:bg-zinc-700 rounded">
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      <button onClick={() => handleDelete(item.question)} className="p-1.5 hover:bg-red-900/30 text-red-400 rounded">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-zinc-600">No FAQ entries</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-8" onClick={() => setEditing(null)}>
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-lg p-6 space-y-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold">{editing.isNew ? "Add FAQ" : "Edit FAQ"}</h3>
            <div>
              <label className="block text-xs text-zinc-500 mb-1">Question</label>
              <input
                value={editing.question}
                onChange={(e) => setEditing({ ...editing, question: e.target.value })}
                className="w-full bg-zinc-800 rounded-lg px-3 py-2 text-sm outline-none"
                disabled={!editing.isNew}
              />
            </div>
            <div>
              <label className="block text-xs text-zinc-500 mb-1">Answer</label>
              <textarea
                value={editing.answer}
                onChange={(e) => setEditing({ ...editing, answer: e.target.value })}
                rows={4}
                className="w-full bg-zinc-800 rounded-lg px-3 py-2 text-sm outline-none resize-none"
              />
            </div>
            <div>
              <label className="block text-xs text-zinc-500 mb-1">TTL (seconds)</label>
              <input
                type="number"
                value={editing.ttl}
                onChange={(e) => setEditing({ ...editing, ttl: parseInt(e.target.value) || 86400 })}
                className="w-full bg-zinc-800 rounded-lg px-3 py-2 text-sm outline-none"
              />
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setEditing(null)} className="px-4 py-2 bg-zinc-800 rounded-lg text-sm hover:bg-zinc-700">Cancel</button>
              <button onClick={handleSave} className="px-4 py-2 gradient-cmu text-white rounded-lg text-sm">Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
