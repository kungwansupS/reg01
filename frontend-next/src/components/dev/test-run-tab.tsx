"use client";

import { useState } from "react";
import { Play, Trash2 } from "lucide-react";
import { devFetch } from "@/lib/api";

export function TestRunTab() {
  const [message, setMessage] = useState("");
  const [output, setOutput] = useState("");
  const [meta, setMeta] = useState("");
  const [running, setRunning] = useState(false);

  async function runTest() {
    if (!message.trim()) return;
    setRunning(true);
    setOutput("Running...");
    setMeta("");
    try {
      const res = await devFetch("/api/dev/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: message.trim() }),
      });
      if (res.ok) {
        const data = await res.json();
        setOutput(JSON.stringify(data, null, 2));
        setMeta(`Latency: ${data.latency_ms || 0}ms | Session: ${data.session_id || "N/A"}`);
      } else {
        setOutput(`Error: ${res.status} ${res.statusText}`);
      }
    } catch (e) {
      setOutput(`Error: ${e}`);
    }
    setRunning(false);
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">Test Run (Draft Config)</h2>

      <div className="flex flex-col gap-1">
        <label className="text-xs text-[var(--muted)]">Message</label>
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="พิมพ์คำถามเพื่อทดสอบ flow ปัจจุบัน"
          className="dev-input min-h-[100px] resize-y"
        />
      </div>

      <div className="flex gap-2">
        <button onClick={runTest} disabled={running} className="dev-btn-primary">
          <Play className="w-4 h-4" /> {running ? "Running..." : "Run Test"}
        </button>
        <button onClick={() => { setOutput(""); setMeta(""); }} className="dev-btn-danger">
          <Trash2 className="w-4 h-4" /> Clear Output
        </button>
      </div>

      {meta && <p className="text-xs text-[var(--muted)]">{meta}</p>}

      <pre className="dev-output min-h-[200px] max-h-[60vh] overflow-auto text-xs">
        {output || "Output will appear here..."}
      </pre>
    </div>
  );
}
