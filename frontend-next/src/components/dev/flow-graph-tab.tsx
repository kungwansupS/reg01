"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { RefreshCw, Save, RotateCcw, Trash2, Plus, Layout } from "lucide-react";
import { devFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

interface GraphNode {
  id: string;
  title?: string;
  group?: string;
  description?: string;
  enabled?: boolean;
  badges?: string[];
  files?: string[];
  lane?: number;
  order?: number;
  x?: number;
  y?: number;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  enabled?: boolean;
  conditional?: boolean;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export function FlowGraphTab() {
  const [graph, setGraph] = useState<GraphData>({ nodes: [], edges: [] });
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [nodeForm, setNodeForm] = useState<GraphNode>({ id: "", title: "", group: "", description: "", enabled: true, badges: [], files: [], lane: 0, order: 0 });
  const [edgeForm, setEdgeForm] = useState<GraphEdge>({ id: "", source: "", target: "", label: "", enabled: true, conditional: false });
  const [selectedEdgeId, setSelectedEdgeId] = useState("");
  const [zoom, setZoom] = useState(100);
  const [status, setStatus] = useState("");
  const [history, setHistory] = useState<Array<{ revision: string; timestamp?: string }>>([]);
  const [selectedHistory, setSelectedHistory] = useState("");
  const boardRef = useRef<HTMLDivElement>(null);

  const loadGraph = useCallback(async () => {
    try {
      const res = await devFetch("/api/dev/graph");
      if (res.ok) {
        const data = await res.json();
        setGraph({ nodes: data.nodes || [], edges: data.edges || [] });
        setStatus(`Loaded: ${(data.nodes || []).length} nodes, ${(data.edges || []).length} edges`);
      }
    } catch { setStatus("Failed to load graph"); }
  }, []);

  const loadModel = useCallback(async () => {
    try {
      const res = await devFetch("/api/dev/graph/model");
      if (res.ok) {
        const data = await res.json();
        if (data.model) {
          // Merge positions from model
          setGraph((prev) => ({
            ...prev,
            nodes: prev.nodes.map((n) => {
              const pos = data.model.positions?.[n.id];
              return pos ? { ...n, x: pos.x, y: pos.y } : n;
            }),
          }));
        }
      }
    } catch { /* ignore */ }
  }, []);

  const loadHistory = useCallback(async () => {
    try {
      const res = await devFetch("/api/dev/graph/model/history?limit=20");
      if (res.ok) {
        const data = await res.json();
        setHistory(Array.isArray(data) ? data : data.items || []);
      }
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadGraph(); loadModel(); loadHistory(); }, [loadGraph, loadModel, loadHistory]);

  async function previewDraft() {
    try {
      const res = await devFetch("/api/dev/graph/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (res.ok) {
        const data = await res.json();
        setGraph({ nodes: data.nodes || [], edges: data.edges || [] });
        setStatus("Preview loaded");
      }
    } catch { setStatus("Preview failed"); }
  }

  async function saveModel() {
    const positions: Record<string, { x: number; y: number }> = {};
    graph.nodes.forEach((n) => { positions[n.id] = { x: n.x || 0, y: n.y || 0 }; });
    try {
      const res = await devFetch("/api/dev/graph/model", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: { positions }, updated_by: "dev-ui" }),
      });
      if (res.ok) { setStatus("Model saved!"); loadHistory(); }
      else setStatus("Save failed");
    } catch { setStatus("Save error"); }
  }

  async function resetModel() {
    if (!confirm("Reset graph model?")) return;
    try {
      const res = await devFetch("/api/dev/graph/model/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ updated_by: "dev-ui" }),
      });
      if (res.ok) { setStatus("Model reset!"); loadGraph(); }
    } catch { setStatus("Reset error"); }
  }

  function selectNode(node: GraphNode) {
    setSelectedNode(node);
    setNodeForm({ ...node, badges: node.badges || [], files: node.files || [] });
  }

  function autoLayout() {
    const laneWidth = 260;
    const orderHeight = 120;
    setGraph((prev) => ({
      ...prev,
      nodes: prev.nodes.map((n, i) => ({
        ...n,
        x: (n.lane ?? (i % 4)) * laneWidth + 40,
        y: (n.order ?? Math.floor(i / 4)) * orderHeight + 40,
      })),
    }));
    setStatus("Auto layout applied");
  }

  // Simple node rendering
  const nodeWidth = 220;

  return (
    <div className="space-y-3">
      <h2 className="text-xl font-bold">Flow Graph</h2>
      <p className="text-xs text-[var(--muted)]">มุมมองการเชื่อมต่อ pipeline ใน visual สำหรับ dev เพื่อดูเส้นทาง runtime และลอง preview จาก draft config ก่อน save</p>

      {/* Toolbar */}
      <div className="flex flex-wrap gap-2">
        <button onClick={loadGraph} className="dev-btn text-xs"><RefreshCw className="w-3 h-3" /> Reload Graph</button>
        <button onClick={previewDraft} className="dev-btn-primary text-xs">Preview Draft Graph</button>
        <button onClick={loadModel} className="dev-btn text-xs">Load Model</button>
        <button onClick={saveModel} className="dev-btn-primary text-xs"><Save className="w-3 h-3" /> Save Model</button>
        <button onClick={resetModel} className="dev-btn-danger text-xs"><RotateCcw className="w-3 h-3" /> Reset Model</button>
        <button onClick={autoLayout} className="dev-btn text-xs"><Layout className="w-3 h-3" /> Auto Layout</button>
        <span className="flex-1" />
        <button onClick={() => setZoom((z) => Math.max(50, z - 10))} className="dev-btn text-xs">-</button>
        <span className="dev-chip font-mono text-xs">Zoom {zoom}%</span>
        <button onClick={() => setZoom((z) => Math.min(200, z + 10))} className="dev-btn text-xs">+</button>
      </div>

      {/* History */}
      <div className="grid grid-cols-[1fr_auto_auto] gap-2 items-center">
        <select value={selectedHistory} onChange={(e) => setSelectedHistory(e.target.value)} className="dev-input text-xs">
          <option value="">-- model history --</option>
          {history.map((h) => <option key={h.revision} value={h.revision}>{h.revision} {h.timestamp}</option>)}
        </select>
        <button className="dev-btn text-xs">Load History</button>
        <button className="dev-btn-danger text-xs"><RotateCcw className="w-3 h-3" /> Rollback</button>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[2fr_1fr] gap-3">
        {/* Graph Board */}
        <div ref={boardRef} className="relative min-h-[540px] rounded-lg overflow-auto" style={{
          border: "1px solid var(--border)",
          background: "radial-gradient(circle at 1px 1px, rgba(159,176,203,0.12) 1px, transparent 0), linear-gradient(180deg, rgba(10,18,34,0.88), rgba(7,13,26,0.92))",
          backgroundSize: "22px 22px, 100% 100%",
          transform: `scale(${zoom / 100})`,
          transformOrigin: "top left",
        }}>
          {/* Edges (simple lines) */}
          <svg className="absolute inset-0 pointer-events-none overflow-visible z-[1]" style={{ width: "3000px", height: "2000px" }}>
            {graph.edges.map((e) => {
              const src = graph.nodes.find((n) => n.id === e.source);
              const tgt = graph.nodes.find((n) => n.id === e.target);
              if (!src || !tgt) return null;
              const x1 = (src.x || 0) + nodeWidth / 2;
              const y1 = (src.y || 0) + 50;
              const x2 = (tgt.x || 0) + nodeWidth / 2;
              const y2 = (tgt.y || 0);
              const mx = (x1 + x2) / 2;
              const my = (y1 + y2) / 2;
              return (
                <g key={e.id}>
                  <path d={`M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}`} fill="none" stroke={e.enabled === false ? "rgba(93,107,132,0.5)" : "rgba(154,178,211,0.65)"} strokeWidth={2} strokeDasharray={e.conditional ? "6 5" : "none"} />
                  {e.label && <text x={mx} y={my - 6} fill="#b9cadf" fontSize={11} textAnchor="middle">{e.label}</text>}
                </g>
              );
            })}
          </svg>

          {/* Nodes */}
          <div className="absolute inset-0 z-[2]" style={{ width: "3000px", height: "2000px" }}>
            {graph.nodes.map((node) => (
              <div
                key={node.id}
                onClick={() => selectNode(node)}
                className={cn(
                  "absolute w-[220px] rounded-lg p-2.5 cursor-pointer border transition-all text-xs",
                  node.enabled === false ? "opacity-45 border-dashed border-[#2d3e64]" : "border-[#2d3e64]",
                  selectedNode?.id === node.id ? "border-[var(--accent)] shadow-[0_0_0_2px_rgba(35,197,143,0.24)]" : ""
                )}
                style={{
                  left: `${node.x || 0}px`,
                  top: `${node.y || 0}px`,
                  background: "rgba(16,26,44,0.95)",
                  boxShadow: "0 14px 30px rgba(0,0,0,0.34)",
                }}
              >
                <div className="flex items-center justify-between gap-1 mb-1">
                  <span className="font-semibold text-sm truncate">{node.title || node.id}</span>
                  {node.group && <span className="text-[10px] px-1.5 py-0.5 border border-blue-500/40 rounded-full text-blue-300 bg-blue-500/10 uppercase tracking-wider shrink-0">{node.group}</span>}
                </div>
                <p className="text-[var(--muted)] text-[11px] leading-snug min-h-[28px]">{node.description || ""}</p>
                {node.badges && node.badges.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {node.badges.map((b, i) => <span key={i} className="dev-chip text-[10px]">{b}</span>)}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Inspector */}
        <div className="dev-panel space-y-3 min-h-[540px]">
          <h3 className="text-sm font-bold">{selectedNode ? selectedNode.title || selectedNode.id : "Node Inspector"}</h3>
          {selectedNode ? (
            <>
              <p className="text-xs text-[var(--muted)]">{selectedNode.description}</p>
              {selectedNode.badges && selectedNode.badges.length > 0 && (
                <div className="flex flex-wrap gap-1">{selectedNode.badges.map((b, i) => <span key={i} className="dev-chip text-[10px]">{b}</span>)}</div>
              )}
              {selectedNode.files && selectedNode.files.length > 0 && (
                <div>
                  <p className="text-[10px] text-[var(--muted)] mb-1">Code files</p>
                  {selectedNode.files.map((f, i) => (
                    <p key={i} className="text-xs font-mono text-blue-300 truncate">{f}</p>
                  ))}
                </div>
              )}
            </>
          ) : (
            <p className="text-xs text-[var(--muted)]">คลิก node ในกราฟเพื่อดูรายละเอียด</p>
          )}

          {/* Node Editor */}
          <div className="border-t border-[var(--border)] pt-3 space-y-2">
            <h4 className="text-xs font-bold text-[var(--muted)] uppercase tracking-wider">Node Editor</h4>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-[var(--muted)]">node id</label>
              <input value={nodeForm.id} onChange={(e) => setNodeForm({ ...nodeForm, id: e.target.value })} className="dev-input text-xs" />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-[var(--muted)]">title</label>
              <input value={nodeForm.title || ""} onChange={(e) => setNodeForm({ ...nodeForm, title: e.target.value })} className="dev-input text-xs" />
            </div>
            <div className="grid grid-cols-2 gap-1">
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-[var(--muted)]">group</label>
                <input value={nodeForm.group || ""} onChange={(e) => setNodeForm({ ...nodeForm, group: e.target.value })} className="dev-input text-xs" />
              </div>
              <div className="flex items-center pt-3">
                <label className="text-[10px] flex items-center gap-1"><input type="checkbox" checked={nodeForm.enabled !== false} onChange={() => setNodeForm({ ...nodeForm, enabled: !nodeForm.enabled })} /> enabled</label>
              </div>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-[var(--muted)]">description</label>
              <textarea value={nodeForm.description || ""} onChange={(e) => setNodeForm({ ...nodeForm, description: e.target.value })} className="dev-input text-xs min-h-[40px] resize-y" />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-[var(--muted)]">badges (comma separated)</label>
              <input value={(nodeForm.badges || []).join(",")} onChange={(e) => setNodeForm({ ...nodeForm, badges: e.target.value.split(",").map((b) => b.trim()).filter(Boolean) })} className="dev-input text-xs" />
            </div>
          </div>

          {/* Edge Editor */}
          <div className="border-t border-[var(--border)] pt-3 space-y-2">
            <h4 className="text-xs font-bold text-[var(--muted)] uppercase tracking-wider">Edge Editor</h4>
            <select value={selectedEdgeId} onChange={(e) => {
              setSelectedEdgeId(e.target.value);
              const edge = graph.edges.find((ed) => ed.id === e.target.value);
              if (edge) setEdgeForm({ ...edge });
            }} className="dev-input text-xs">
              <option value="">-- select edge --</option>
              {graph.edges.map((e) => <option key={e.id} value={e.id}>{e.id}: {e.source} → {e.target}</option>)}
            </select>
            <div className="grid grid-cols-2 gap-1">
              <div className="flex flex-col gap-0.5">
                <label className="text-[10px] text-[var(--muted)]">source</label>
                <input value={edgeForm.source} onChange={(e) => setEdgeForm({ ...edgeForm, source: e.target.value })} className="dev-input text-xs" />
              </div>
              <div className="flex flex-col gap-0.5">
                <label className="text-[10px] text-[var(--muted)]">target</label>
                <input value={edgeForm.target} onChange={(e) => setEdgeForm({ ...edgeForm, target: e.target.value })} className="dev-input text-xs" />
              </div>
            </div>
            <div className="flex flex-col gap-0.5">
              <label className="text-[10px] text-[var(--muted)]">label</label>
              <input value={edgeForm.label || ""} onChange={(e) => setEdgeForm({ ...edgeForm, label: e.target.value })} className="dev-input text-xs" />
            </div>
            <div className="flex gap-4">
              <label className="text-[10px] flex items-center gap-1"><input type="checkbox" checked={edgeForm.enabled !== false} onChange={() => setEdgeForm({ ...edgeForm, enabled: !edgeForm.enabled })} /> enabled</label>
              <label className="text-[10px] flex items-center gap-1"><input type="checkbox" checked={!!edgeForm.conditional} onChange={() => setEdgeForm({ ...edgeForm, conditional: !edgeForm.conditional })} /> conditional</label>
            </div>
          </div>
        </div>
      </div>

      {status && <p className="text-xs text-[var(--muted)]">{status}</p>}
    </div>
  );
}
