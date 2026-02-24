"use client";

import { useState, useCallback } from "react";
import { Save, RefreshCw, RotateCcw } from "lucide-react";
import { devFetch } from "@/lib/api";

export function EnvironmentTab() {
  const [envRaw, setEnvRaw] = useState("");
  const [history, setHistory] = useState<Array<{ revision: string; timestamp?: string }>>([]);
  const [selectedHistory, setSelectedHistory] = useState("");
  const [status, setStatus] = useState("");

  const loadEnv = useCallback(async () => {
    setStatus("Loading...");
    try {
      const res = await devFetch("/api/dev/fs/read?path=backend/.env");
      if (res.ok) {
        const data = await res.json();
        setEnvRaw(data.content || "");
        setStatus("Loaded");
      } else setStatus("Error loading .env");
    } catch { setStatus("Error"); }
  }, []);

  async function saveEnv() {
    setStatus("Saving...");
    try {
      const res = await devFetch("/api/dev/fs/write", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: "backend/.env", content: envRaw }),
      });
      if (res.ok) setStatus("Saved! (.env.bak created automatically)");
      else setStatus("Save failed");
    } catch { setStatus("Save error"); }
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">Environment (.env)</h2>
      <p className="text-xs text-[var(--muted)]">แก้ไฟล์ `.env` ได้ทั้งไฟล์โดยตรงจากหน้านี้</p>

      <div className="flex gap-2">
        <button onClick={loadEnv} className="dev-btn"><RefreshCw className="w-4 h-4" /> Load .env</button>
        <button onClick={saveEnv} className="dev-btn-primary"><Save className="w-4 h-4" /> Save .env</button>
      </div>

      <p className="text-[10px] text-[var(--muted)]">เมื่อบันทึก ระบบจะสร้างไฟล์สำรอง `.env.bak` อัตโนมัติ และ reload ค่า env ใน process ปัจจุบัน</p>

      <div className="flex flex-col gap-1">
        <label className="text-xs text-[var(--muted)]">backend/.env</label>
        <textarea
          value={envRaw}
          onChange={(e) => setEnvRaw(e.target.value)}
          className="dev-input font-mono text-xs min-h-[400px] resize-y"
          spellCheck={false}
        />
      </div>

      {status && <p className="text-sm text-[var(--muted)]">{status}</p>}
    </div>
  );
}
