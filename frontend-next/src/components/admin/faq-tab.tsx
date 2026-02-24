"use client";

import { useState, useEffect, useCallback } from "react";
import { Plus, Pencil, Trash2, Search, Clock, X } from "lucide-react";
import { adminFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

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
        <h1 className="text-xl font-bold">FAQ</h1>
        <div className="flex gap-2">
          <button onClick={handlePurge} className="yt-btn yt-btn-secondary text-xs">
            <Clock className="w-3.5 h-3.5" /> Purge Expired
          </button>
          <button
            onClick={() => setEditing({ question: "", answer: "", ttl: 86400, isNew: true })}
            className="yt-btn yt-btn-primary text-xs"
          >
            <Plus className="w-3.5 h-3.5" /> Add Entry
          </button>
        </div>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-yt-text-muted" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search FAQ..."
          className="w-full yt-input pl-10 pr-4 py-2 text-sm"
        />
      </div>

      {loading ? (
        <p className="text-yt-text-muted">Loading...</p>
      ) : (
        <div className="yt-card overflow-hidden">
          <table className="yt-table">
            <thead>
              <tr>
                <th>Question</th>
                <th>Answer</th>
                <th className="w-24">Source</th>
                <th className="w-24">Status</th>
                <th className="w-24">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.question}>
                  <td className="font-medium max-w-48 truncate">{item.question}</td>
                  <td className="text-yt-text-secondary max-w-64 truncate">{item.answer_preview}</td>
                  <td className="text-yt-text-muted">{item.source}</td>
                  <td>
                    <span className={cn("yt-badge", item.expired ? "yt-badge-red" : "yt-badge-green")}>
                      {item.expired ? "expired" : "active"}
                    </span>
                  </td>
                  <td>
                    <div className="flex gap-1">
                      <button onClick={() => handleEdit(item.question)} className="yt-btn-icon">
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      <button onClick={() => handleDelete(item.question)} className="yt-btn-icon text-danger">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr><td colSpan={5} className="text-center text-yt-text-muted py-8">No FAQ entries</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Edit Modal */}
      {editing && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-8" onClick={() => setEditing(null)}>
          <div className="yt-card w-full max-w-lg p-6 space-y-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold">{editing.isNew ? "Add FAQ" : "Edit FAQ"}</h3>
              <button onClick={() => setEditing(null)} className="yt-btn-icon"><X className="w-4 h-4" /></button>
            </div>
            <div>
              <label className="block text-xs text-yt-text-muted mb-1">Question</label>
              <input
                value={editing.question}
                onChange={(e) => setEditing({ ...editing, question: e.target.value })}
                className="w-full yt-input text-sm"
                disabled={!editing.isNew}
              />
            </div>
            <div>
              <label className="block text-xs text-yt-text-muted mb-1">Answer</label>
              <textarea
                value={editing.answer}
                onChange={(e) => setEditing({ ...editing, answer: e.target.value })}
                rows={4}
                className="w-full yt-input text-sm resize-none"
              />
            </div>
            <div>
              <label className="block text-xs text-yt-text-muted mb-1">TTL (seconds)</label>
              <input
                type="number"
                value={editing.ttl}
                onChange={(e) => setEditing({ ...editing, ttl: parseInt(e.target.value) || 86400 })}
                className="w-full yt-input text-sm"
              />
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setEditing(null)} className="yt-btn yt-btn-secondary text-sm">Cancel</button>
              <button onClick={handleSave} className="yt-btn yt-btn-primary text-sm">Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
