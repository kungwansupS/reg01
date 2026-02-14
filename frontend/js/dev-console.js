(function () {
  const $ = (id) => document.getElementById(id);

  const refs = {
    token: $("dev-token"),
    connectBtn: $("connect-btn"),
    loadBtn: $("load-btn"),
    saveBtn: $("save-btn"),
    testBtn: $("test-btn"),
    clearBtn: $("clear-btn"),
    envLoadBtn: $("env-load-btn"),
    envSaveBtn: $("env-save-btn"),
    graphLoadBtn: $("graph-load-btn"),
    graphPreviewBtn: $("graph-preview-btn"),
    graphModelLoadBtn: $("graph-model-load-btn"),
    graphModelSaveBtn: $("graph-model-save-btn"),
    graphModelResetBtn: $("graph-model-reset-btn"),
    graphLayoutBtn: $("graph-layout-btn"),
    graphZoomOutBtn: $("graph-zoom-out-btn"),
    graphZoomResetBtn: $("graph-zoom-reset-btn"),
    graphZoomInBtn: $("graph-zoom-in-btn"),
    graphZoomIndicator: $("graph-zoom-indicator"),
    tabButtons: Array.from(document.querySelectorAll("[data-dev-tab-btn]")),
    tabPanels: Array.from(document.querySelectorAll("[data-dev-tab-panel]")),

    authStatus: $("auth-status"),
    flowStatus: $("flow-status"),
    envStatus: $("env-status"),
    testMeta: $("test-meta"),
    testOutput: $("test-output"),
    graphStatus: $("graph-status"),
    flowHistorySelect: $("flow-history-select"),
    flowHistoryLoadBtn: $("flow-history-load-btn"),
    flowRollbackBtn: $("flow-rollback-btn"),
    graphHistorySelect: $("graph-history-select"),
    graphHistoryLoadBtn: $("graph-history-load-btn"),
    graphRollbackBtn: $("graph-rollback-btn"),
    envHistorySelect: $("env-history-select"),
    envHistoryLoadBtn: $("env-history-load-btn"),
    envRollbackBtn: $("env-rollback-btn"),

    graphBoard: $("graph-board"),
    graphNodes: $("graph-nodes"),
    graphEdges: $("graph-edges"),
    inspectorTitle: $("inspector-title"),
    inspectorDesc: $("inspector-desc"),
    inspectorBadges: $("inspector-badges"),
    inspectorFiles: $("inspector-files"),
    graphNodeId: $("graph-node-id"),
    graphNodeTitle: $("graph-node-title"),
    graphNodeGroup: $("graph-node-group"),
    graphNodeDescription: $("graph-node-description"),
    graphNodeLane: $("graph-node-lane"),
    graphNodeOrder: $("graph-node-order"),
    graphNodeEnabled: $("graph-node-enabled"),
    graphNodeBadges: $("graph-node-badges"),
    graphNodeFiles: $("graph-node-files"),
    graphNodeNewBtn: $("graph-node-new-btn"),
    graphNodeApplyBtn: $("graph-node-apply-btn"),
    graphNodeDeleteBtn: $("graph-node-delete-btn"),
    graphEdgeSelect: $("graph-edge-select"),
    graphEdgeId: $("graph-edge-id"),
    graphEdgeSource: $("graph-edge-source"),
    graphEdgeTarget: $("graph-edge-target"),
    graphEdgeLabel: $("graph-edge-label"),
    graphEdgeEnabled: $("graph-edge-enabled"),
    graphEdgeConditional: $("graph-edge-conditional"),
    graphEdgeNewBtn: $("graph-edge-new-btn"),
    graphEdgeApplyBtn: $("graph-edge-apply-btn"),
    graphEdgeDeleteBtn: $("graph-edge-delete-btn"),

    ideRootBtn: $("ide-root-btn"),
    ideUpBtn: $("ide-up-btn"),
    ideRefreshTreeBtn: $("ide-refresh-tree-btn"),
    ideTreeStatus: $("ide-tree-status"),
    ideTree: $("ide-tree"),
    ideOpenPath: $("ide-open-path"),
    ideOpenBtn: $("ide-open-btn"),
    ideReloadBtn: $("ide-reload-btn"),
    ideSaveBtn: $("ide-save-btn"),
    ideEditorHost: $("ide-editor-host"),
    ideEditorMonaco: $("ide-editor-monaco"),
    ideEditor: $("ide-editor"),
    ideEditorMeta: $("ide-editor-meta"),
    ideEditorStatus: $("ide-editor-status"),
    ideLangBadge: $("ide-lang-badge"),
    ideCursorPos: $("ide-cursor-pos"),
    ideDirtyBadge: $("ide-dirty-badge"),
    ideRuntimeRefreshBtn: $("ide-runtime-refresh-btn"),
    ideRuntimeSummary: $("ide-runtime-summary"),
    ideRuntimeLog: $("ide-runtime-log"),
    ideRuntimeStatus: $("ide-runtime-status"),
    ideLogPath: $("ide-log-path"),
    ideLogRefreshBtn: $("ide-log-refresh-btn"),
    ideSearchQuery: $("ide-search-query"),
    ideSearchPath: $("ide-search-path"),
    ideSearchCase: $("ide-search-case"),
    ideSearchRegex: $("ide-search-regex"),
    ideSearchBtn: $("ide-search-btn"),
    ideSearchStatus: $("ide-search-status"),
    ideSearchResults: $("ide-search-results"),
    symbolName: $("symbol-name"),
    symbolPath: $("symbol-path"),
    symbolCase: $("symbol-case"),
    symbolFindBtn: $("symbol-find-btn"),
    symbolStatus: $("symbol-status"),
    symbolResults: $("symbol-results"),
    shellCwd: $("shell-cwd"),
    shellTimeout: $("shell-timeout"),
    shellCommand: $("shell-command"),
    shellRunBtn: $("shell-run-btn"),
    shellPreset: $("shell-preset"),
    shellHistory: $("shell-history"),
    shellHistoryClearBtn: $("shell-history-clear-btn"),
    shellStatus: $("shell-status"),
    shellOutput: $("shell-output"),
    traceRefreshBtn: $("trace-refresh-btn"),
    traceSessionFilter: $("trace-session-filter"),
    traceStatusFilter: $("trace-status-filter"),
    traceList: $("trace-list"),
    traceMeta: $("trace-meta"),
    traceSteps: $("trace-steps"),
    traceData: $("trace-data"),
    traceApplyGraphBtn: $("trace-apply-graph-btn"),
    traceClearGraphBtn: $("trace-clear-graph-btn"),
    connRefreshBtn: $("conn-refresh-btn"),
    connOutput: $("conn-output"),
    routeRefreshBtn: $("route-refresh-btn"),
    routeFilter: $("route-filter"),
    routeOutput: $("route-output"),
    probeMethod: $("probe-method"),
    probePath: $("probe-path"),
    probeQuery: $("probe-query"),
    probeHeaders: $("probe-headers"),
    probeBody: $("probe-body"),
    probeSendBtn: $("probe-send-btn"),
    probeStatus: $("probe-status"),
    probeOutput: $("probe-output"),
    monitorInterval: $("monitor-interval"),
    monitorAutoTraces: $("monitor-auto-traces"),
    monitorAutoLogSearch: $("monitor-auto-log-search"),
    monitorAutoRuntimeLog: $("monitor-auto-runtime-log"),
    monitorAutoRuntimeSummary: $("monitor-auto-runtime-summary"),
    monitorStartBtn: $("monitor-start-btn"),
    monitorStopBtn: $("monitor-stop-btn"),
    monitorStatus: $("monitor-status"),
    logSearchPath: $("log-search-path"),
    logSearchContains: $("log-search-contains"),
    logSearchPlatform: $("log-search-platform"),
    logSearchTrace: $("log-search-trace"),
    logSearchSession: $("log-search-session"),
    logSearchBtn: $("log-search-btn"),
    logSearchStatus: $("log-search-status"),
    logSearchOutput: $("log-search-output"),
    scenarioRefreshBtn: $("scenario-refresh-btn"),
    scenarioSelect: $("scenario-select"),
    scenarioNewBtn: $("scenario-new-btn"),
    scenarioLoadBtn: $("scenario-load-btn"),
    scenarioDeleteBtn: $("scenario-delete-btn"),
    scenarioId: $("scenario-id"),
    scenarioName: $("scenario-name"),
    scenarioDescription: $("scenario-description"),
    scenarioMessage: $("scenario-message"),
    scenarioConfig: $("scenario-config"),
    scenarioSaveBtn: $("scenario-save-btn"),
    scenarioRunBtn: $("scenario-run-btn"),
    scenarioStatus: $("scenario-status"),
    scenarioRunMeta: $("scenario-run-meta"),
    scenarioRunOutput: $("scenario-run-output"),
  };

  const fields = {
    ragMode: $("rag-mode"),
    ragTopK: $("rag-top-k"),
    ragHybrid: $("rag-hybrid"),
    ragIntent: $("rag-intent"),
    ragRerank: $("rag-rerank"),
    memorySummary: $("memory-summary"),
    memoryRecent: $("memory-recent"),
    poseEnabled: $("pose-enabled"),
    faqAutoLearn: $("faq-auto-learn"),
    extraInstruction: $("extra-instruction"),
    testMessage: $("test-message"),
    envRaw: $("env-raw"),
  };

  const TOKEN_KEY = "reg01_dev_token";
  const GRAPH_LAYOUT_KEY = "reg01_dev_graph_layout_v1";
  const GRAPH_VIEW_KEY = "reg01_dev_graph_view_v1";
  const DEV_TAB_KEY = "reg01_dev_active_tab_v1";
  const SHELL_HISTORY_KEY = "reg01_dev_shell_history_v1";
  const MONITOR_SETTINGS_KEY = "reg01_dev_monitor_settings_v1";
  const SHELL_HISTORY_MAX = 40;
  const SVG_NS = "http://www.w3.org/2000/svg";
  const GRAPH_ZOOM_MIN = 0.45;
  const GRAPH_ZOOM_MAX = 2.4;
  const GRAPH_ZOOM_STEP = 0.12;

  const state = {
    graph: {
      data: null,
      selected: null,
      selectedEdge: null,
      drag: null,
      pan: null,
      pos: loadGraphLayout(),
      view: loadGraphView(),
      bounds: { width: 0, height: 0 },
      runtime: {
        traceId: "",
        nodes: [],
        edges: [],
        nodeLatency: {},
      },
      modelState: null,
    },
    observability: {
      traces: [],
      selectedTraceId: "",
      selectedTrace: null,
      connections: null,
      routes: [],
      monitor: {
        timer: null,
        running: false,
      },
    },
    scenarios: {
      items: [],
      selectedId: "",
    },
    history: {
      flow: [],
      graph: [],
      env: [],
    },
    ide: {
      tree: new Map(),
      expanded: new Set([""]),
      selectedPath: "",
      selectedType: "",
      currentDir: "",
      openPath: "",
      lastContent: "",
      dirty: false,
      fileMeta: null,
      searchResults: [],
      symbolResults: [],
      shellHistory: [],
      editor: {
        mode: "textarea",
        loading: false,
        suppressChange: false,
        monacoEditor: null,
        model: null,
      },
    },
  };

  function token() {
    return (refs.token.value || "").trim();
  }

  function setStatus(el, text) {
    if (el) {
      el.textContent = text || "";
    }
  }

  function getGraphZoom() {
    const value = Number(state.graph.view && state.graph.view.zoom);
    if (!Number.isFinite(value)) {
      return 1;
    }
    return clamp(value, GRAPH_ZOOM_MIN, GRAPH_ZOOM_MAX);
  }

  function setGraphZoomIndicator() {
    if (!refs.graphZoomIndicator) {
      return;
    }
    refs.graphZoomIndicator.textContent = `Zoom ${Math.round(getGraphZoom() * 100)}%`;
  }

  function applyNodeVisualPosition(el, pos) {
    const zoom = getGraphZoom();
    const x = Number(pos && pos.x) || 0;
    const y = Number(pos && pos.y) || 0;
    el.style.left = `${x * zoom}px`;
    el.style.top = `${y * zoom}px`;
    el.style.transform = `scale(${zoom})`;
    el.style.transformOrigin = "top left";
  }

  function refreshGraphViewport() {
    if (!state.graph.data || !Array.isArray(state.graph.data.nodes)) {
      setGraphZoomIndicator();
      return;
    }
    setGraphBoardSize(state.graph.pos);
    refs.graphNodes.querySelectorAll(".graph-node").forEach((el) => {
      const nodeId = el.dataset.nodeId;
      if (!nodeId) {
        return;
      }
      const pos = state.graph.pos[nodeId];
      if (!pos) {
        return;
      }
      applyNodeVisualPosition(el, pos);
    });
    drawGraphEdges(state.graph.data);
    setGraphZoomIndicator();
  }

  function clearGraphRuntimeHighlight() {
    state.graph.runtime.traceId = "";
    state.graph.runtime.nodes = [];
    state.graph.runtime.edges = [];
    state.graph.runtime.nodeLatency = {};
    if (state.graph.data && Array.isArray(state.graph.data.nodes)) {
      renderGraph(state.graph.data);
    }
  }

  function setGraphRuntimeHighlight(payload) {
    const nodes = Array.isArray(payload && payload.active_nodes) ? payload.active_nodes : [];
    const edges = Array.isArray(payload && payload.active_edges) ? payload.active_edges : [];
    const nodeLatency = (payload && typeof payload.node_latency_ms === "object" && payload.node_latency_ms) || {};
    state.graph.runtime.traceId = String((payload && payload.trace_id) || "");
    state.graph.runtime.nodes = nodes.slice();
    state.graph.runtime.edges = edges.slice();
    state.graph.runtime.nodeLatency = { ...nodeLatency };
    if (state.graph.data && Array.isArray(state.graph.data.nodes)) {
      renderGraph(state.graph.data);
    }
  }

  function setGraphZoom(rawZoom, anchor) {
    const previousZoom = getGraphZoom();
    const nextZoom = clamp(Number(rawZoom) || 1, GRAPH_ZOOM_MIN, GRAPH_ZOOM_MAX);
    if (Math.abs(nextZoom - previousZoom) < 0.0001) {
      setGraphZoomIndicator();
      return;
    }

    const board = refs.graphBoard;
    let focusX = board.clientWidth / 2;
    let focusY = board.clientHeight / 2;
    if (anchor && Number.isFinite(Number(anchor.clientX)) && Number.isFinite(Number(anchor.clientY))) {
      const rect = board.getBoundingClientRect();
      focusX = clamp(Number(anchor.clientX) - rect.left, 0, board.clientWidth || 0);
      focusY = clamp(Number(anchor.clientY) - rect.top, 0, board.clientHeight || 0);
    }

    const worldX = (board.scrollLeft + focusX) / previousZoom;
    const worldY = (board.scrollTop + focusY) / previousZoom;

    state.graph.view.zoom = nextZoom;
    refreshGraphViewport();

    board.scrollLeft = worldX * nextZoom - focusX;
    board.scrollTop = worldY * nextZoom - focusY;
    saveGraphView();
  }

  function changeGraphZoom(direction, anchor) {
    const current = getGraphZoom();
    const delta = direction > 0 ? GRAPH_ZOOM_STEP : -GRAPH_ZOOM_STEP;
    setGraphZoom(current + delta, anchor || null);
  }

  function resetGraphZoom() {
    setGraphZoom(1);
  }

  function setActiveTab(rawTabId, persist) {
    const buttons = Array.isArray(refs.tabButtons) ? refs.tabButtons : [];
    const panels = Array.isArray(refs.tabPanels) ? refs.tabPanels : [];
    if (!buttons.length || !panels.length) {
      return;
    }

    const available = buttons
      .map((btn) => (btn && btn.dataset ? btn.dataset.devTabBtn : ""))
      .filter(Boolean);
    const fallback = available[0] || "flow-config";
    const tabId = available.includes(rawTabId) ? rawTabId : fallback;

    buttons.forEach((btn) => {
      const active = btn.dataset.devTabBtn === tabId;
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-selected", active ? "true" : "false");
    });

    panels.forEach((panel) => {
      const active = panel.dataset.devTabPanel === tabId;
      panel.classList.toggle("active", active);
      panel.hidden = !active;
      panel.setAttribute("aria-hidden", active ? "false" : "true");
    });

    if (persist) {
      localStorage.setItem(DEV_TAB_KEY, tabId);
    }

    requestAnimationFrame(() => {
      if (tabId === "flow-graph" && state.graph.data && Array.isArray(state.graph.data.nodes)) {
        refreshGraphViewport();
      }

      if (tabId === "workspace") {
        if (usingMonaco() && state.ide.editor.monacoEditor) {
          state.ide.editor.monacoEditor.layout();
        }
        updateEditorIndicators();
      }

      if (tabId === "observability") {
        if (refs.traceList && !refs.traceList.textContent.trim()) {
          loadTraces().catch((error) => setStatus(refs.traceMeta, `Trace refresh failed: ${error.message}`));
        }
        if (refs.connOutput && !refs.connOutput.textContent.trim()) {
          loadConnections().catch((error) => {
            refs.connOutput.textContent = `Connection map load failed: ${error.message}`;
          });
        }
        if (refs.routeOutput && !refs.routeOutput.textContent.trim()) {
          loadRoutes().catch((error) => {
            refs.routeOutput.textContent = `Route map load failed: ${error.message}`;
          });
        }
      }

      if (tabId === "scenarios") {
        if (refs.scenarioSelect && refs.scenarioSelect.options.length <= 1) {
          loadScenarios().catch((error) => setStatus(refs.scenarioStatus, `Scenario refresh failed: ${error.message}`));
        }
      }
    });
  }

  function initTabs() {
    const buttons = Array.isArray(refs.tabButtons) ? refs.tabButtons : [];
    if (!buttons.length) {
      return;
    }

    buttons.forEach((btn) => {
      btn.addEventListener("click", () => {
        setActiveTab(btn.dataset.devTabBtn || "", true);
      });
    });

    const saved = localStorage.getItem(DEV_TAB_KEY) || "";
    setActiveTab(saved, false);
  }

  function normPath(path) {
    let p = String(path || "").trim().replace(/\\/g, "/");
    p = p.replace(/^\/+/, "").replace(/\/+/g, "/");
    if (p === ".") {
      return "";
    }
    if (p.endsWith("/") && p.length > 1) {
      p = p.slice(0, -1);
    }
    return p;
  }

  function parentPath(path) {
    const p = normPath(path);
    if (!p.includes("/")) {
      return "";
    }
    return p.split("/").slice(0, -1).join("/");
  }

  function usingMonaco() {
    return state.ide.editor.mode === "monaco" && !!state.ide.editor.model && !!state.ide.editor.monacoEditor;
  }

  function getEditorValue() {
    if (usingMonaco()) {
      return state.ide.editor.model.getValue();
    }
    return refs.ideEditor.value || "";
  }

  function setEditorValue(value) {
    const text = value || "";
    if (usingMonaco()) {
      state.ide.editor.suppressChange = true;
      state.ide.editor.model.setValue(text);
      state.ide.editor.suppressChange = false;
      return;
    }
    refs.ideEditor.value = text;
  }

  function editorCursor() {
    if (usingMonaco()) {
      const position = state.ide.editor.monacoEditor.getPosition();
      return {
        line: (position && position.lineNumber) || 1,
        col: (position && position.column) || 1,
      };
    }

    const content = refs.ideEditor.value || "";
    const idx = Number(refs.ideEditor.selectionStart || 0);
    const safeIdx = Math.max(0, Math.min(content.length, idx));
    const head = content.slice(0, safeIdx);
    const lines = head.split("\n");
    return {
      line: lines.length || 1,
      col: (lines[lines.length - 1] || "").length + 1,
    };
  }

  function query(url, params) {
    const sp = new URLSearchParams();
    Object.entries(params || {}).forEach(([k, v]) => {
      if (v === undefined || v === null || String(v).trim() === "") {
        return;
      }
      sp.set(k, String(v));
    });
    const s = sp.toString();
    return s ? `${url}?${s}` : url;
  }

  async function api(url, opts) {
    const t = token();
    if (!t) {
      throw new Error("Missing Dev Token");
    }
    const options = { ...(opts || {}) };
    const headers = { ...(options.headers || {}), "X-Dev-Token": t };
    if (options.body && !Object.keys(headers).some((k) => k.toLowerCase() === "content-type")) {
      headers["Content-Type"] = "application/json";
    }
    options.headers = headers;

    const res = await fetch(url, options);
    const raw = await res.text();
    let data = {};
    if (raw) {
      try {
        data = JSON.parse(raw);
      } catch (e) {
        data = { raw };
      }
    }
    if (!res.ok) {
      throw new Error(data.detail || data.message || data.raw || `HTTP ${res.status}`);
    }
    return data;
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const existing = document.querySelector(`script[data-src="${src}"]`);
      if (existing) {
        existing.addEventListener("load", () => resolve());
        existing.addEventListener("error", () => reject(new Error(`Failed to load ${src}`)));
        if (existing.getAttribute("data-loaded") === "1") {
          resolve();
        }
        return;
      }

      const script = document.createElement("script");
      script.src = src;
      script.async = true;
      script.setAttribute("data-src", src);
      script.onload = () => {
        script.setAttribute("data-loaded", "1");
        resolve();
      };
      script.onerror = () => reject(new Error(`Failed to load ${src}`));
      document.head.appendChild(script);
    });
  }

  function monacoLanguage(lang) {
    const name = String(lang || "plaintext").toLowerCase();
    if (name === "dotenv") return "ini";
    if (name === "batch") return "bat";
    if (name === "powershell") return "powershell";
    if (name === "plaintext") return "plaintext";
    return name;
  }

  async function loadMonacoLibrary() {
    if (window.monaco && window.monaco.editor) {
      return window.monaco;
    }

    if (window.__regMonacoPromise) {
      return window.__regMonacoPromise;
    }

    window.__regMonacoPromise = (async () => {
      const loaderSrc = "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.52.2/min/vs/loader.min.js";
      await loadScript(loaderSrc);
      if (!window.require || !window.require.config) {
        throw new Error("Monaco loader not available");
      }

      window.require.config({
        paths: {
          vs: "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.52.2/min/vs",
        },
      });

      await new Promise((resolve, reject) => {
        window.require(["vs/editor/editor.main"], resolve, reject);
      });

      return window.monaco;
    })();

    return window.__regMonacoPromise;
  }

  async function ensureMonacoEditor() {
    if (usingMonaco() || state.ide.editor.loading) {
      return;
    }

    state.ide.editor.loading = true;
    try {
      await loadMonacoLibrary();
      if (!window.monaco || !window.monaco.editor || !refs.ideEditorMonaco) {
        throw new Error("Monaco editor is unavailable");
      }

      const initialValue = refs.ideEditor.value || "";
      const model = window.monaco.editor.createModel(
        initialValue,
        monacoLanguage((state.ide.fileMeta && state.ide.fileMeta.language) || detectLanguage(state.ide.openPath))
      );

      const editor = window.monaco.editor.create(refs.ideEditorMonaco, {
        model,
        theme: "vs-dark",
        automaticLayout: true,
        minimap: { enabled: true },
        fontSize: 13,
        lineHeight: 20,
        smoothScrolling: true,
        scrollBeyondLastLine: false,
        wordWrap: "off",
      });

      editor.onDidChangeModelContent(() => {
        if (state.ide.editor.suppressChange) {
          return;
        }
        state.ide.dirty = getEditorValue() !== state.ide.lastContent;
        renderEditorMeta();
      });

      editor.onDidChangeCursorPosition(() => {
        updateEditorIndicators();
      });

      editor.addCommand(window.monaco.KeyMod.CtrlCmd | window.monaco.KeyCode.KeyS, () => {
        saveFile().catch((error) => {
          setStatus(refs.ideEditorStatus, `Save failed: ${error.message}`);
        });
      });

      state.ide.editor.mode = "monaco";
      state.ide.editor.model = model;
      state.ide.editor.monacoEditor = editor;
      refs.ideEditorHost.classList.add("monaco-ready");
      updateEditorIndicators();
      setStatus(refs.ideEditorStatus, "Monaco editor ready");
    } catch (error) {
      setStatus(refs.ideEditorStatus, `Monaco unavailable, fallback textarea: ${error.message}`);
    } finally {
      state.ide.editor.loading = false;
    }
  }

  function setEditorLanguage(language) {
    const lang = String(language || detectLanguage(state.ide.openPath) || "plaintext").toLowerCase();
    if (usingMonaco() && window.monaco && window.monaco.editor && state.ide.editor.model) {
      window.monaco.editor.setModelLanguage(state.ide.editor.model, monacoLanguage(lang));
    }
  }

  function collectConfig() {
    return {
      rag: {
        mode: fields.ragMode.value,
        top_k: Number(fields.ragTopK.value || 5),
        use_hybrid: !!fields.ragHybrid.checked,
        use_intent_analysis: !!fields.ragIntent.checked,
        use_llm_rerank: !!fields.ragRerank.checked,
      },
      memory: {
        enable_summary: !!fields.memorySummary.checked,
        recent_messages: Number(fields.memoryRecent.value || 10),
      },
      pose: { enabled: !!fields.poseEnabled.checked },
      faq: { auto_learn: !!fields.faqAutoLearn.checked },
      prompt: { extra_context_instruction: fields.extraInstruction.value || "" },
    };
  }

  function applyConfig(config) {
    const rag = (config && config.rag) || {};
    const memory = (config && config.memory) || {};
    const pose = (config && config.pose) || {};
    const faq = (config && config.faq) || {};
    const prompt = (config && config.prompt) || {};
    fields.ragMode.value = rag.mode || "keyword";
    fields.ragTopK.value = Number(rag.top_k || 5);
    fields.ragHybrid.checked = !!rag.use_hybrid;
    fields.ragIntent.checked = !!rag.use_intent_analysis;
    fields.ragRerank.checked = !!rag.use_llm_rerank;
    fields.memorySummary.checked = !!memory.enable_summary;
    fields.memoryRecent.value = Number(memory.recent_messages || 10);
    fields.poseEnabled.checked = !!pose.enabled;
    fields.faqAutoLearn.checked = !!faq.auto_learn;
    fields.extraInstruction.value = prompt.extra_context_instruction || "";
  }

  async function loadFlow() {
    setStatus(refs.flowStatus, "Loading flow config...");
    const data = await api("/api/dev/flow", { method: "GET" });
    applyConfig(data.config || {});
    await loadFlowHistory();
    setStatus(
      refs.flowStatus,
      `Loaded revision ${data.revision} | updated_by=${data.updated_by} | updated_at=${data.updated_at}`
    );
  }

  async function saveFlow() {
    setStatus(refs.flowStatus, "Saving flow config...");
    const data = await api("/api/dev/flow", {
      method: "PUT",
      body: JSON.stringify({ config: collectConfig(), updated_by: "dev-ui" }),
    });
    await loadFlowHistory();
    setStatus(
      refs.flowStatus,
      `Saved revision ${data.revision} | updated_by=${data.updated_by} | updated_at=${data.updated_at}`
    );
  }

  async function runTest() {
    const msg = (fields.testMessage.value || "").trim();
    if (!msg) {
      setStatus(refs.testMeta, "Please enter a test message");
      return;
    }
    setStatus(refs.testMeta, "Running test...");
    refs.testOutput.textContent = "";
    const data = await api("/api/dev/test", {
      method: "POST",
      body: JSON.stringify({ message: msg, config_override: collectConfig(), include_debug: true }),
    });
    const result = data.result || {};
    const tokens = result.tokens || {};
    setStatus(
      refs.testMeta,
      `session_id=${data.session_id} | trace_id=${data.trace_id || "-"} | latency=${data.latency_seconds}s | tokens=${tokens.total_tokens || 0}`
    );
    refs.testOutput.textContent = result.text || "";
    if (data.trace_id) {
      state.observability.selectedTraceId = data.trace_id;
      await loadTraces();
    }
  }

  async function loadEnv() {
    setStatus(refs.envStatus, "Loading .env...");
    const data = await api("/api/dev/env/raw", { method: "GET" });
    fields.envRaw.value = data.content || "";
    await loadEnvHistory();
    setStatus(refs.envStatus, `Loaded ${data.path}`);
  }

  async function saveEnv() {
    setStatus(refs.envStatus, "Saving .env...");
    const data = await api("/api/dev/env/raw", {
      method: "PUT",
      body: JSON.stringify({ content: fields.envRaw.value || "", updated_by: "dev-ui" }),
    });
    await loadEnvHistory();
    setStatus(refs.envStatus, `Saved ${data.path} (${data.size} chars) | backup=${data.backup_path}`);
  }

  async function loadGraph() {
    setStatus(refs.graphStatus, "Loading runtime graph...");
    const data = await api("/api/dev/graph", { method: "GET" });
    renderGraph(data);
    const mode = (data.meta && data.meta.mode) || "unknown";
    setStatus(refs.graphStatus, `Loaded graph | nodes=${(data.nodes || []).length} edges=${(data.edges || []).length} mode=${mode}`);
  }

  async function previewGraph() {
    if (state.graph.modelState && state.graph.modelState.model) {
      await renderGraphFromModelDraft(true);
      return;
    }
    setStatus(refs.graphStatus, "Previewing draft graph...");
    const data = await api("/api/dev/graph/preview", {
      method: "POST",
      body: JSON.stringify({ config_override: collectConfig() }),
    });
    renderGraph(data);
    const mode = (data.meta && data.meta.mode) || "unknown";
    setStatus(refs.graphStatus, `Preview graph | nodes=${(data.nodes || []).length} edges=${(data.edges || []).length} mode=${mode}`);
  }

  async function ensureGraphModelLoaded() {
    if (state.graph.modelState && state.graph.modelState.model) {
      return state.graph.modelState;
    }
    const data = await api("/api/dev/graph/model", { method: "GET" });
    state.graph.modelState = data;
    refreshGraphEditorControls();
    return data;
  }

  async function loadGraphModel() {
    setStatus(refs.graphStatus, "Loading graph model...");
    const data = await api("/api/dev/graph/model", { method: "GET" });
    state.graph.modelState = data;
    refreshGraphEditorControls();
    await renderGraphFromModelDraft(false);
    await loadGraphHistory();
    setStatus(
      refs.graphStatus,
      `Loaded graph model rev=${data.revision} by=${data.updated_by} | nodes=${(data.model && data.model.nodes ? data.model.nodes.length : 0)} edges=${(data.model && data.model.edges ? data.model.edges.length : 0)}`
    );
  }

  function graphModel() {
    return state.graph.modelState && state.graph.modelState.model ? state.graph.modelState.model : null;
  }

  function syncNodePositionsIntoModel() {
    const model = graphModel();
    if (!model || !Array.isArray(model.nodes)) {
      return;
    }
    model.nodes.forEach((node) => {
      const pos = state.graph.pos[node.id];
      if (!pos) {
        return;
      }
      node.x = Number(pos.x) || 0;
      node.y = Number(pos.y) || 0;
    });
  }

  async function renderGraphFromModelDraft(useDraftConfig) {
    const model = graphModel();
    if (!model) {
      await loadGraph();
      return;
    }
    setStatus(refs.graphStatus, "Rendering graph draft...");
    const payload = {
      model_override: model,
    };
    if (useDraftConfig) {
      payload.config_override = collectConfig();
    }
    const data = await api("/api/dev/graph/preview", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderGraph(data);
    refreshGraphEditorControls();
    const mode = (data.meta && data.meta.mode) || "unknown";
    setStatus(
      refs.graphStatus,
      `Draft graph | mode=${mode} nodes=${(data.nodes || []).length} edges=${(data.edges || []).length}`
    );
  }

  async function saveGraphModel() {
    await ensureGraphModelLoaded();
    syncNodePositionsIntoModel();
    const payload = {
      model: graphModel(),
      updated_by: "dev-ui",
    };
    const data = await api("/api/dev/graph/model", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    state.graph.modelState = data;
    refreshGraphEditorControls();
    await renderGraphFromModelDraft(false);
    await loadGraphHistory();
    setStatus(
      refs.graphStatus,
      `Saved graph model rev=${data.revision} by=${data.updated_by}`
    );
  }

  async function resetGraphModel() {
    const data = await api("/api/dev/graph/model/reset", {
      method: "POST",
      body: JSON.stringify({ updated_by: "dev-ui" }),
    });
    state.graph.modelState = data;
    state.graph.selected = null;
    state.graph.selectedEdge = null;
    refreshGraphEditorControls();
    await renderGraphFromModelDraft(false);
    await loadGraphHistory();
    setStatus(refs.graphStatus, `Graph model reset to default rev=${data.revision}`);
  }

  function renderGraph(data) {
    if (!data || !Array.isArray(data.nodes)) {
      refs.graphNodes.innerHTML = "";
      refs.graphEdges.innerHTML = "";
      renderInspector(null);
      return;
    }

    state.graph.data = data;
    const defaults = buildGraphDefaultPos(data.nodes);
    state.graph.pos = mergeGraphPos(data.nodes, defaults, state.graph.pos);
    setGraphBoardSize(state.graph.pos);
    refs.graphNodes.innerHTML = "";

    data.nodes.forEach((n) => {
      const p = state.graph.pos[n.id] || { x: 40, y: 40 };
      const el = document.createElement("div");
      el.className = "graph-node";
      if (n.enabled === false) {
        el.classList.add("disabled");
      }
      if (state.graph.runtime.nodes.includes(n.id)) {
        el.classList.add("runtime-active");
      }
      el.dataset.nodeId = n.id;
      applyNodeVisualPosition(el, p);
      const badges = Array.isArray(n.badges) ? n.badges : [];
      const latency = state.graph.runtime.nodeLatency[n.id];
      const runtimeBadge = Number.isFinite(Number(latency)) ? [`runtime ${Number(latency).toFixed(0)}ms`] : [];
      const mergedBadges = badges.concat(runtimeBadge);
      el.innerHTML = `
        <div class="graph-node-head">
          <div class="graph-node-title">${esc(n.title || n.id)}</div>
          <div class="graph-node-group">${esc(n.group || "node")}</div>
        </div>
        <div class="graph-node-desc">${esc(n.description || "")}</div>
        <div class="graph-node-badges">${mergedBadges.map((b) => `<span class="graph-chip">${esc(String(b))}</span>`).join("")}</div>
      `;
      el.addEventListener("click", () => {
        state.graph.selected = n.id;
        paintGraphSelection();
      });
      el.addEventListener("pointerdown", onGraphPointerDown);
      refs.graphNodes.appendChild(el);
    });

    drawGraphEdges(data);
    requestAnimationFrame(() => {
      drawGraphEdges(data);
    });
    setTimeout(() => {
      if (state.graph.data === data) {
        drawGraphEdges(data);
      }
    }, 80);
    if (!data.nodes.some((n) => n.id === state.graph.selected)) {
      state.graph.selected = data.nodes[0] ? data.nodes[0].id : null;
    }
    paintGraphSelection();
    refreshGraphEditorControls();
    saveGraphLayout();
    setGraphZoomIndicator();
  }

  function paintGraphSelection() {
    const runtimeNodes = new Set(state.graph.runtime.nodes || []);
    refs.graphNodes.querySelectorAll(".graph-node").forEach((el) => {
      el.classList.toggle("selected", el.dataset.nodeId === state.graph.selected);
      el.classList.toggle("runtime-active", runtimeNodes.has(el.dataset.nodeId));
    });
    const node = state.graph.data && Array.isArray(state.graph.data.nodes)
      ? state.graph.data.nodes.find((n) => n.id === state.graph.selected)
      : null;
    renderInspector(node);
  }

  function renderInspector(node) {
    if (!node) {
      refs.inspectorTitle.textContent = "Node Inspector";
      refs.inspectorDesc.textContent = "Click node to inspect";
      refs.inspectorBadges.innerHTML = "";
      refs.inspectorFiles.innerHTML = "";
      populateNodeEditor("");
      return;
    }
    refs.inspectorTitle.textContent = `${node.title || node.id}${node.enabled === false ? " (disabled)" : ""}`;
    refs.inspectorDesc.textContent = node.description || "No description";
    const latency = state.graph.runtime.nodeLatency[node.id];
    const runtimeExtra = Number.isFinite(Number(latency)) ? [`runtime ${Number(latency).toFixed(0)}ms`] : [];
    refs.inspectorBadges.innerHTML = ((node.badges || []).concat(runtimeExtra))
      .map((b) => `<span class="graph-chip">${esc(String(b))}</span>`)
      .join("");
    const files = Array.isArray(node.file_refs) ? node.file_refs : [];
    refs.inspectorFiles.innerHTML = files.length
      ? files.map((f) => `<li><button class="inspector-file-btn" data-open-file="${escAttr(f)}">${esc(f)}</button></li>`).join("")
      : "<li>no file refs</li>";
    populateNodeEditor(node.id);
  }

  function normalizeGraphId(value, fallback) {
    const raw = String(value || "").trim().toLowerCase();
    const normalized = raw
      .replace(/[^a-z0-9_\-\s.]/g, "")
      .replace(/[\s.]+/g, "_")
      .replace(/^_+|_+$/g, "");
    return normalized || (fallback || "");
  }

  function splitCommaList(value) {
    return String(value || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function splitLineList(value) {
    return String(value || "")
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function fillNodeEditorBlank() {
    refs.graphNodeId.value = "";
    refs.graphNodeTitle.value = "";
    refs.graphNodeGroup.value = "";
    refs.graphNodeDescription.value = "";
    refs.graphNodeLane.value = 0;
    refs.graphNodeOrder.value = 0;
    refs.graphNodeEnabled.checked = true;
    refs.graphNodeBadges.value = "";
    refs.graphNodeFiles.value = "";
  }

  function populateNodeEditor(nodeId) {
    const model = graphModel();
    if (!model || !Array.isArray(model.nodes) || !nodeId) {
      fillNodeEditorBlank();
      return;
    }

    const node = model.nodes.find((item) => item.id === nodeId);
    if (!node) {
      fillNodeEditorBlank();
      return;
    }
    refs.graphNodeId.value = node.id || "";
    refs.graphNodeTitle.value = node.title || "";
    refs.graphNodeGroup.value = node.group || "";
    refs.graphNodeDescription.value = node.description || "";
    refs.graphNodeLane.value = Number(node.lane || 0);
    refs.graphNodeOrder.value = Number(node.order || 0);
    refs.graphNodeEnabled.checked = node.enabled !== false;
    refs.graphNodeBadges.value = Array.isArray(node.badges) ? node.badges.join(", ") : "";
    refs.graphNodeFiles.value = Array.isArray(node.file_refs) ? node.file_refs.join("\n") : "";
  }

  function readNodeEditor() {
    const lane = Number.parseInt(refs.graphNodeLane.value || "0", 10);
    const order = Number.parseInt(refs.graphNodeOrder.value || "0", 10);
    const id = normalizeGraphId(refs.graphNodeId.value, "");
    return {
      id,
      title: (refs.graphNodeTitle.value || "").trim() || id,
      group: (refs.graphNodeGroup.value || "").trim() || "node",
      description: (refs.graphNodeDescription.value || "").trim(),
      lane: Number.isFinite(lane) ? lane : 0,
      order: Number.isFinite(order) ? order : 0,
      enabled: !!refs.graphNodeEnabled.checked,
      badges: splitCommaList(refs.graphNodeBadges.value),
      file_refs: splitLineList(refs.graphNodeFiles.value),
    };
  }

  async function newGraphNode() {
    await ensureGraphModelLoaded();
    const model = graphModel();
    const index = (model && Array.isArray(model.nodes) ? model.nodes.length : 0) + 1;
    fillNodeEditorBlank();
    refs.graphNodeId.value = `node_${index}`;
    refs.graphNodeTitle.value = `Node ${index}`;
    refs.graphNodeGroup.value = "custom";
    refs.graphNodeLane.value = 0;
    refs.graphNodeOrder.value = 0;
    refs.graphNodeEnabled.checked = true;
    state.graph.selected = null;
  }

  async function applyGraphNode() {
    await ensureGraphModelLoaded();
    const model = graphModel();
    if (!model || !Array.isArray(model.nodes)) {
      throw new Error("Graph model is unavailable");
    }

    const draft = readNodeEditor();
    if (!draft.id) {
      throw new Error("Node id is required");
    }

    const selectedId = state.graph.selected || "";
    let index = model.nodes.findIndex((node) => node.id === draft.id);
    let previousId = "";

    if (index < 0 && selectedId) {
      const selectedIndex = model.nodes.findIndex((node) => node.id === selectedId);
      if (selectedIndex >= 0) {
        index = selectedIndex;
        previousId = selectedId;
      }
    }

    if (index >= 0 && !previousId) {
      previousId = model.nodes[index].id;
    }

    if (index >= 0) {
      const existing = model.nodes[index];
      model.nodes[index] = {
        ...existing,
        ...draft,
        x: existing.x,
        y: existing.y,
      };
    } else {
      model.nodes.push(draft);
    }

    if (previousId && previousId !== draft.id && Array.isArray(model.edges)) {
      model.edges.forEach((edge) => {
        if (edge.source === previousId) edge.source = draft.id;
        if (edge.target === previousId) edge.target = draft.id;
      });
      if (state.graph.pos[previousId]) {
        state.graph.pos[draft.id] = state.graph.pos[previousId];
        delete state.graph.pos[previousId];
      }
    }

    state.graph.selected = draft.id;
    await renderGraphFromModelDraft(false);
  }

  async function deleteGraphNode() {
    await ensureGraphModelLoaded();
    const model = graphModel();
    if (!model || !Array.isArray(model.nodes)) {
      throw new Error("Graph model is unavailable");
    }

    const nodeId = normalizeGraphId(refs.graphNodeId.value, state.graph.selected || "");
    if (!nodeId) {
      throw new Error("Node id is required");
    }

    const nextNodes = model.nodes.filter((node) => node.id !== nodeId);
    if (nextNodes.length === model.nodes.length) {
      throw new Error(`Node not found: ${nodeId}`);
    }
    model.nodes = nextNodes;
    if (Array.isArray(model.edges)) {
      model.edges = model.edges.filter((edge) => edge.source !== nodeId && edge.target !== nodeId);
    }
    delete state.graph.pos[nodeId];
    state.graph.selected = model.nodes[0] ? model.nodes[0].id : null;
    state.graph.selectedEdge = null;
    await renderGraphFromModelDraft(false);
  }

  function refreshEdgeSelectOptions() {
    const model = graphModel();
    if (!refs.graphEdgeSelect) {
      return;
    }
    const selected = state.graph.selectedEdge || refs.graphEdgeSelect.value || "";
    refs.graphEdgeSelect.innerHTML = "";
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "-- select edge --";
    refs.graphEdgeSelect.appendChild(blank);

    if (!model || !Array.isArray(model.edges)) {
      populateEdgeEditor("");
      return;
    }

    model.edges.forEach((edge) => {
      const option = document.createElement("option");
      option.value = edge.id;
      option.textContent = edge.id;
      refs.graphEdgeSelect.appendChild(option);
    });

    const exists = model.edges.some((edge) => edge.id === selected);
    const nextId = exists ? selected : (model.edges[0] ? model.edges[0].id : "");
    state.graph.selectedEdge = nextId || null;
    refs.graphEdgeSelect.value = nextId || "";
    populateEdgeEditor(nextId || "");
  }

  function fillEdgeEditorBlank() {
    refs.graphEdgeId.value = "";
    refs.graphEdgeSource.value = "";
    refs.graphEdgeTarget.value = "";
    refs.graphEdgeLabel.value = "";
    refs.graphEdgeEnabled.checked = true;
    refs.graphEdgeConditional.checked = false;
  }

  function populateEdgeEditor(edgeId) {
    const model = graphModel();
    if (!model || !Array.isArray(model.edges) || !edgeId) {
      fillEdgeEditorBlank();
      return;
    }
    const edge = model.edges.find((item) => item.id === edgeId);
    if (!edge) {
      fillEdgeEditorBlank();
      return;
    }
    refs.graphEdgeId.value = edge.id || "";
    refs.graphEdgeSource.value = edge.source || "";
    refs.graphEdgeTarget.value = edge.target || "";
    refs.graphEdgeLabel.value = edge.label || "";
    refs.graphEdgeEnabled.checked = edge.enabled !== false;
    refs.graphEdgeConditional.checked = !!edge.conditional;
  }

  function readEdgeEditor() {
    return {
      id: normalizeGraphId(refs.graphEdgeId.value, ""),
      source: normalizeGraphId(refs.graphEdgeSource.value, ""),
      target: normalizeGraphId(refs.graphEdgeTarget.value, ""),
      label: (refs.graphEdgeLabel.value || "").trim(),
      enabled: !!refs.graphEdgeEnabled.checked,
      conditional: !!refs.graphEdgeConditional.checked,
    };
  }

  async function newGraphEdge() {
    await ensureGraphModelLoaded();
    const model = graphModel();
    const index = (model && Array.isArray(model.edges) ? model.edges.length : 0) + 1;
    fillEdgeEditorBlank();
    refs.graphEdgeId.value = `edge_${index}`;
    const firstNode = model && Array.isArray(model.nodes) && model.nodes[0] ? model.nodes[0].id : "";
    refs.graphEdgeSource.value = state.graph.selected || firstNode;
    refs.graphEdgeTarget.value = firstNode;
    refs.graphEdgeEnabled.checked = true;
    refs.graphEdgeConditional.checked = false;
    state.graph.selectedEdge = null;
    refs.graphEdgeSelect.value = "";
  }

  async function applyGraphEdge() {
    await ensureGraphModelLoaded();
    const model = graphModel();
    if (!model || !Array.isArray(model.nodes) || !Array.isArray(model.edges)) {
      throw new Error("Graph model is unavailable");
    }
    const draft = readEdgeEditor();
    if (!draft.id) {
      throw new Error("Edge id is required");
    }
    if (!draft.source || !draft.target) {
      throw new Error("Edge source and target are required");
    }
    const nodeIds = new Set(model.nodes.map((node) => node.id));
    if (!nodeIds.has(draft.source) || !nodeIds.has(draft.target)) {
      throw new Error("Edge source/target must reference existing node ids");
    }

    const selectedEdgeId = state.graph.selectedEdge || "";
    let index = model.edges.findIndex((edge) => edge.id === draft.id);
    if (index < 0 && selectedEdgeId) {
      const selectedIndex = model.edges.findIndex((edge) => edge.id === selectedEdgeId);
      if (selectedIndex >= 0) {
        index = selectedIndex;
      }
    }

    if (index >= 0) {
      model.edges[index] = {
        ...model.edges[index],
        ...draft,
      };
    } else {
      model.edges.push(draft);
    }

    state.graph.selectedEdge = draft.id;
    await renderGraphFromModelDraft(false);
  }

  async function deleteGraphEdge() {
    await ensureGraphModelLoaded();
    const model = graphModel();
    if (!model || !Array.isArray(model.edges)) {
      throw new Error("Graph model is unavailable");
    }
    const edgeId = normalizeGraphId(refs.graphEdgeId.value, state.graph.selectedEdge || "");
    if (!edgeId) {
      throw new Error("Edge id is required");
    }

    const nextEdges = model.edges.filter((edge) => edge.id !== edgeId);
    if (nextEdges.length === model.edges.length) {
      throw new Error(`Edge not found: ${edgeId}`);
    }
    model.edges = nextEdges;
    state.graph.selectedEdge = model.edges[0] ? model.edges[0].id : null;
    await renderGraphFromModelDraft(false);
  }

  function refreshGraphEditorControls() {
    refreshEdgeSelectOptions();
    populateNodeEditor(state.graph.selected || "");
  }

  function buildGraphDefaultPos(nodes) {
    const pos = {};
    const used = new Set();
    const laneCount = {};
    nodes.forEach((n, i) => {
      const explicitX = Number(n.x);
      const explicitY = Number(n.y);
      if (Number.isFinite(explicitX) && Number.isFinite(explicitY)) {
        pos[n.id] = { x: explicitX, y: explicitY };
        return;
      }
      const lane = Number.isFinite(Number(n.lane)) ? Number(n.lane) : Math.floor(i / 2);
      let row = Number.isFinite(Number(n.order)) ? Number(n.order) : (laneCount[lane] || 0);
      while (used.has(`${lane}:${row}`)) row += 1;
      used.add(`${lane}:${row}`);
      laneCount[lane] = row + 1;
      pos[n.id] = { x: 44 + lane * 255, y: 36 + row * 165 };
    });
    return pos;
  }

  function mergeGraphPos(nodes, defaults, prev) {
    const merged = {};
    nodes.forEach((n) => {
      const p = prev && prev[n.id];
      merged[n.id] = p && Number.isFinite(Number(p.x)) && Number.isFinite(Number(p.y))
        ? { x: Number(p.x), y: Number(p.y) }
        : (defaults[n.id] || { x: 40, y: 40 });
    });
    return merged;
  }

  function setGraphBoardSize(pos) {
    const zoom = getGraphZoom();
    let maxX = 0;
    let maxY = 0;
    Object.values(pos || {}).forEach((p) => {
      maxX = Math.max(maxX, Number(p.x) + 220);
      maxY = Math.max(maxY, Number(p.y) + 130);
    });
    const logicalWidth = Math.max(900, maxX + 80);
    const logicalHeight = Math.max(540, maxY + 80);
    state.graph.bounds.width = logicalWidth;
    state.graph.bounds.height = logicalHeight;

    const width = Math.max(refs.graphBoard.clientWidth || 900, Math.ceil(logicalWidth * zoom));
    const height = Math.max(540, Math.ceil(logicalHeight * zoom));
    refs.graphNodes.style.width = `${width}px`;
    refs.graphNodes.style.height = `${height}px`;
    refs.graphEdges.style.width = `${width}px`;
    refs.graphEdges.style.height = `${height}px`;
    refs.graphEdges.setAttribute("viewBox", `0 0 ${width} ${height}`);
    refs.graphEdges.setAttribute("preserveAspectRatio", "none");
    refs.graphEdges.setAttribute("width", String(width));
    refs.graphEdges.setAttribute("height", String(height));
  }

  function nodeAnchorFromDom(nodeId, side) {
    const nodeEl = refs.graphNodes.querySelector(`[data-node-id="${nodeId}"]`);
    if (!(nodeEl instanceof HTMLElement)) {
      return null;
    }
    const boardRect = refs.graphBoard.getBoundingClientRect();
    const nodeRect = nodeEl.getBoundingClientRect();
    const scrollLeft = Number(refs.graphBoard.scrollLeft) || 0;
    const scrollTop = Number(refs.graphBoard.scrollTop) || 0;
    const x = side === "right"
      ? nodeRect.right - boardRect.left + scrollLeft
      : nodeRect.left - boardRect.left + scrollLeft;
    const y = nodeRect.top - boardRect.top + scrollTop + nodeRect.height / 2;
    return { x, y };
  }

  function nodeAnchorFromModel(nodeId, side, nodeIndex) {
    const pos = state.graph.pos[nodeId];
    if (!pos) {
      return null;
    }
    const zoom = getGraphZoom();
    const nodeMeta = nodeIndex.get(nodeId) || {};
    const width = Number(nodeMeta.width) || 220;
    const height = Number(nodeMeta.height) || 130;
    return {
      x: (Number(pos.x) + (side === "right" ? width : 0)) * zoom,
      y: (Number(pos.y) + height / 2) * zoom,
    };
  }

  function drawGraphEdges(data) {
    refs.graphEdges.innerHTML = "";
    if (!data || !Array.isArray(data.edges)) return;
    const nodeIndex = new Map((data.nodes || []).map((node) => [node.id, node]));
    data.edges.forEach((e) => {
      const start = nodeAnchorFromDom(e.source, "right") || nodeAnchorFromModel(e.source, "right", nodeIndex);
      const end = nodeAnchorFromDom(e.target, "left") || nodeAnchorFromModel(e.target, "left", nodeIndex);
      if (!start || !end) {
        return;
      }

      const x1 = Number(start.x) || 0;
      const y1 = Number(start.y) || 0;
      const x2 = Number(end.x) || 0;
      const y2 = Number(end.y) || 0;
      const c = Math.max(60, Math.abs(x2 - x1) * 0.42);
      const c1x = x1 + c;
      const c2x = x2 - c;

      const path = document.createElementNS(SVG_NS, "path");
      path.setAttribute("d", `M ${x1} ${y1} C ${c1x} ${y1}, ${c2x} ${y2}, ${x2} ${y2}`);
      path.setAttribute("class", "edge-path");
      if (e.conditional) path.classList.add("edge-conditional");
      if (e.enabled === false) path.classList.add("edge-disabled");
      if (state.graph.runtime.edges.includes(e.id)) path.classList.add("edge-runtime");
      refs.graphEdges.appendChild(path);

      if (e.label) {
        const l = bezier(x1, y1, c1x, y1, c2x, y2, x2, y2, 0.5);
        const text = document.createElementNS(SVG_NS, "text");
        text.setAttribute("x", String(l.x));
        text.setAttribute("y", String(l.y - 6));
        text.setAttribute("class", "edge-label");
        text.textContent = String(e.label);
        refs.graphEdges.appendChild(text);
      }
    });
  }

  function bezier(x0, y0, x1, y1, x2, y2, x3, y3, t) {
    const inv = 1 - t;
    return {
      x: (inv ** 3) * x0 + 3 * (inv ** 2) * t * x1 + 3 * inv * (t ** 2) * x2 + (t ** 3) * x3,
      y: (inv ** 3) * y0 + 3 * (inv ** 2) * t * y1 + 3 * inv * (t ** 2) * y2 + (t ** 3) * y3,
    };
  }

  function onGraphPointerDown(ev) {
    const el = ev.currentTarget;
    if (!(el instanceof HTMLElement) || !el.dataset.nodeId) return;
    if (ev.button !== 0 || ev.altKey) return;
    state.graph.selected = el.dataset.nodeId;
    paintGraphSelection();
    const pos = state.graph.pos[el.dataset.nodeId] || { x: 40, y: 40 };
    state.graph.drag = {
      id: el.dataset.nodeId,
      pointerId: ev.pointerId,
      x0: ev.clientX,
      y0: ev.clientY,
      ox: Number(pos.x) || 0,
      oy: Number(pos.y) || 0,
      el,
    };
    el.classList.add("dragging");
    el.setPointerCapture(ev.pointerId);
    ev.preventDefault();
  }

  function onGraphPointerMove(ev) {
    const d = state.graph.drag;
    if (!d || d.pointerId !== ev.pointerId) return;
    const zoom = getGraphZoom();
    const dx = (ev.clientX - d.x0) / zoom;
    const dy = (ev.clientY - d.y0) / zoom;
    const bw = Number(state.graph.bounds && state.graph.bounds.width) || 1100;
    const bh = Number(state.graph.bounds && state.graph.bounds.height) || 540;
    const x = clamp(d.ox + dx, 10, Math.max(10, bw - 230));
    const y = clamp(d.oy + dy, 10, Math.max(10, bh - 120));
    state.graph.pos[d.id] = { x, y };
    const model = graphModel();
    if (model && Array.isArray(model.nodes)) {
      const node = model.nodes.find((item) => item.id === d.id);
      if (node) {
        node.x = x;
        node.y = y;
      }
    }
    applyNodeVisualPosition(d.el, { x, y });
    drawGraphEdges(state.graph.data);
  }

  function onGraphPointerEnd(ev) {
    const d = state.graph.drag;
    if (!d || d.pointerId !== ev.pointerId) return;
    d.el.classList.remove("dragging");
    try { d.el.releasePointerCapture(ev.pointerId); } catch (e) {}
    state.graph.drag = null;
    saveGraphLayout();
  }

  function clamp(v, mn, mx) {
    return Math.min(mx, Math.max(mn, v));
  }

  function loadGraphView() {
    const fallback = { zoom: 1 };
    try {
      const raw = localStorage.getItem(GRAPH_VIEW_KEY);
      if (!raw) {
        return fallback;
      }
      const parsed = JSON.parse(raw) || {};
      return {
        zoom: clamp(Number(parsed.zoom) || 1, GRAPH_ZOOM_MIN, GRAPH_ZOOM_MAX),
      };
    } catch (e) {
      return fallback;
    }
  }

  function saveGraphView() {
    const payload = {
      zoom: getGraphZoom(),
    };
    localStorage.setItem(GRAPH_VIEW_KEY, JSON.stringify(payload));
  }

  function onGraphWheel(ev) {
    if (!refs.graphBoard) {
      return;
    }

    if (ev.ctrlKey || ev.metaKey) {
      ev.preventDefault();
      if (ev.deltaY === 0) {
        return;
      }
      const direction = ev.deltaY < 0 ? 1 : -1;
      changeGraphZoom(direction, { clientX: ev.clientX, clientY: ev.clientY });
      return;
    }

    ev.preventDefault();
    refs.graphBoard.scrollLeft += Number(ev.deltaX) || 0;
    refs.graphBoard.scrollTop += Number(ev.deltaY) || 0;
  }

  function onGraphBoardPointerDown(ev) {
    if (!(ev.target instanceof HTMLElement)) {
      return;
    }
    if (ev.button !== 1 && !(ev.altKey && ev.button === 0)) {
      return;
    }
    state.graph.pan = {
      pointerId: ev.pointerId,
      x0: ev.clientX,
      y0: ev.clientY,
      scrollLeft: refs.graphBoard.scrollLeft,
      scrollTop: refs.graphBoard.scrollTop,
    };
    refs.graphBoard.classList.add("panning");
    refs.graphBoard.setPointerCapture(ev.pointerId);
    ev.preventDefault();
  }

  function onGraphPanPointerMove(ev) {
    const pan = state.graph.pan;
    if (!pan || pan.pointerId !== ev.pointerId) {
      return;
    }
    const dx = ev.clientX - pan.x0;
    const dy = ev.clientY - pan.y0;
    refs.graphBoard.scrollLeft = pan.scrollLeft - dx;
    refs.graphBoard.scrollTop = pan.scrollTop - dy;
  }

  function onGraphPanPointerEnd(ev) {
    const pan = state.graph.pan;
    if (!pan || pan.pointerId !== ev.pointerId) {
      return;
    }
    refs.graphBoard.classList.remove("panning");
    try {
      refs.graphBoard.releasePointerCapture(ev.pointerId);
    } catch (e) {}
    state.graph.pan = null;
  }

  function loadGraphLayout() {
    try {
      const raw = localStorage.getItem(GRAPH_LAYOUT_KEY);
      return raw ? (JSON.parse(raw) || {}) : {};
    } catch (e) {
      return {};
    }
  }

  function saveGraphLayout() {
    if (!state.graph.data || !Array.isArray(state.graph.data.nodes)) return;
    const compact = {};
    state.graph.data.nodes.forEach((n) => {
      const p = state.graph.pos[n.id];
      if (!p) return;
      compact[n.id] = { x: Math.round(Number(p.x) || 0), y: Math.round(Number(p.y) || 0) };
    });
    localStorage.setItem(GRAPH_LAYOUT_KEY, JSON.stringify(compact));
  }

  async function autoLayoutGraph() {
    if (!state.graph.data || !Array.isArray(state.graph.data.nodes)) {
      setStatus(refs.graphStatus, "No graph loaded");
      return;
    }
    state.graph.pos = buildGraphDefaultPos(state.graph.data.nodes);
    renderGraph(state.graph.data);
    setStatus(refs.graphStatus, "Applied auto layout");
  }

  function setSelectOptions(selectEl, options, placeholder) {
    if (!selectEl) {
      return;
    }
    selectEl.innerHTML = "";
    const first = document.createElement("option");
    first.value = "";
    first.textContent = placeholder || "-- select --";
    selectEl.appendChild(first);
    (options || []).forEach((item) => {
      const opt = document.createElement("option");
      opt.value = String(item.value || "");
      opt.textContent = String(item.label || item.value || "");
      selectEl.appendChild(opt);
    });
  }

  function safeJsonParse(text, fallback) {
    try {
      return JSON.parse(String(text || "").trim() || "{}");
    } catch (error) {
      return fallback;
    }
  }

  function parseJsonTextOrThrow(text, label, fallback) {
    const raw = String(text || "").trim();
    if (!raw) {
      return fallback;
    }
    try {
      return JSON.parse(raw);
    } catch (error) {
      throw new Error(`${label} must be valid JSON`);
    }
  }

  function pretty(value) {
    try {
      return JSON.stringify(value, null, 2);
    } catch (error) {
      return String(value);
    }
  }

  function loadShellHistory() {
    try {
      const raw = localStorage.getItem(SHELL_HISTORY_KEY);
      if (!raw) {
        state.ide.shellHistory = [];
        return;
      }
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) {
        state.ide.shellHistory = [];
        return;
      }
      state.ide.shellHistory = parsed
        .map((item) => ({
          command: String(item.command || ""),
          cwd: String(item.cwd || ""),
          timeout: Number(item.timeout || 25),
          at: String(item.at || ""),
          exit_code: Number(item.exit_code || 0),
          timed_out: !!item.timed_out,
        }))
        .filter((item) => item.command)
        .slice(0, SHELL_HISTORY_MAX);
    } catch (error) {
      state.ide.shellHistory = [];
    }
  }

  function saveShellHistory() {
    const compact = (state.ide.shellHistory || []).slice(0, SHELL_HISTORY_MAX);
    localStorage.setItem(SHELL_HISTORY_KEY, JSON.stringify(compact));
  }

  function pushShellHistory(entry) {
    const item = {
      command: String((entry && entry.command) || "").trim(),
      cwd: String((entry && entry.cwd) || "").trim(),
      timeout: Number((entry && entry.timeout) || 25),
      at: String((entry && entry.at) || new Date().toISOString()),
      exit_code: Number((entry && entry.exit_code) || 0),
      timed_out: !!(entry && entry.timed_out),
    };
    if (!item.command) {
      return;
    }
    const key = `${item.command}@@${item.cwd}`;
    const next = (state.ide.shellHistory || []).filter((row) => `${row.command}@@${row.cwd}` !== key);
    next.unshift(item);
    state.ide.shellHistory = next.slice(0, SHELL_HISTORY_MAX);
    saveShellHistory();
    renderShellHistory();
  }

  function renderShellHistory() {
    if (!refs.shellHistory) {
      return;
    }
    refs.shellHistory.innerHTML = "";
    const items = Array.isArray(state.ide.shellHistory) ? state.ide.shellHistory : [];
    if (!items.length) {
      refs.shellHistory.textContent = "No command history";
      return;
    }
    items.forEach((item) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "search-result-item";
      row.dataset.command = item.command;
      row.dataset.cwd = item.cwd;
      row.dataset.timeout = String(item.timeout || 25);
      row.innerHTML = `
        <div><strong>${esc(item.command)}</strong></div>
        <small>cwd=${esc(item.cwd || ".")} | timeout=${Number(item.timeout || 25)}s</small>
        <small>${esc(item.at || "-")} | exit=${Number(item.exit_code || 0)}${item.timed_out ? " | timeout" : ""}</small>
      `;
      refs.shellHistory.appendChild(row);
    });
  }

  function loadMonitorSettings() {
    const defaults = {
      interval: 10,
      traces: true,
      logSearch: true,
      runtimeLog: false,
      runtimeSummary: false,
      enabled: false,
    };
    try {
      const raw = localStorage.getItem(MONITOR_SETTINGS_KEY);
      if (!raw) {
        return defaults;
      }
      const parsed = JSON.parse(raw) || {};
      return {
        interval: Math.max(2, Math.min(120, Number(parsed.interval) || defaults.interval)),
        traces: parsed.traces !== false,
        logSearch: parsed.logSearch !== false,
        runtimeLog: !!parsed.runtimeLog,
        runtimeSummary: !!parsed.runtimeSummary,
        enabled: !!parsed.enabled,
      };
    } catch (error) {
      return defaults;
    }
  }

  function saveMonitorSettings(settings) {
    const payload = {
      interval: Math.max(2, Math.min(120, Number(settings.interval) || 10)),
      traces: !!settings.traces,
      logSearch: !!settings.logSearch,
      runtimeLog: !!settings.runtimeLog,
      runtimeSummary: !!settings.runtimeSummary,
      enabled: !!settings.enabled,
    };
    localStorage.setItem(MONITOR_SETTINGS_KEY, JSON.stringify(payload));
  }

  function monitorSettingsFromUI() {
    return {
      interval: Math.max(2, Math.min(120, Number((refs.monitorInterval && refs.monitorInterval.value) || 10) || 10)),
      traces: !!(refs.monitorAutoTraces && refs.monitorAutoTraces.checked),
      logSearch: !!(refs.monitorAutoLogSearch && refs.monitorAutoLogSearch.checked),
      runtimeLog: !!(refs.monitorAutoRuntimeLog && refs.monitorAutoRuntimeLog.checked),
      runtimeSummary: !!(refs.monitorAutoRuntimeSummary && refs.monitorAutoRuntimeSummary.checked),
      enabled: !!(state.observability.monitor && state.observability.monitor.timer),
    };
  }

  function applyMonitorSettingsToUI(settings) {
    if (refs.monitorInterval) refs.monitorInterval.value = String(settings.interval || 10);
    if (refs.monitorAutoTraces) refs.monitorAutoTraces.checked = !!settings.traces;
    if (refs.monitorAutoLogSearch) refs.monitorAutoLogSearch.checked = !!settings.logSearch;
    if (refs.monitorAutoRuntimeLog) refs.monitorAutoRuntimeLog.checked = !!settings.runtimeLog;
    if (refs.monitorAutoRuntimeSummary) refs.monitorAutoRuntimeSummary.checked = !!settings.runtimeSummary;
  }

  function stopAutoRefreshMonitor() {
    const monitor = state.observability.monitor;
    if (!monitor) {
      return;
    }
    if (monitor.timer) {
      clearInterval(monitor.timer);
      monitor.timer = null;
    }
    monitor.running = false;
    const saved = monitorSettingsFromUI();
    saved.enabled = false;
    saveMonitorSettings(saved);
    setStatus(refs.monitorStatus, "Auto refresh stopped");
  }

  async function runAutoRefreshTick() {
    const monitor = state.observability.monitor;
    if (!monitor || monitor.running) {
      return;
    }
    if (document.hidden) {
      return;
    }
    monitor.running = true;
    const started = Date.now();
    const tasks = [];
    if (refs.monitorAutoTraces && refs.monitorAutoTraces.checked) {
      tasks.push(loadTraces());
    }
    if (refs.monitorAutoLogSearch && refs.monitorAutoLogSearch.checked) {
      tasks.push(searchLogsAdvanced());
    }
    if (refs.monitorAutoRuntimeLog && refs.monitorAutoRuntimeLog.checked) {
      tasks.push(loadLogs());
    }
    if (refs.monitorAutoRuntimeSummary && refs.monitorAutoRuntimeSummary.checked) {
      tasks.push(loadRuntime());
    }
    await Promise.allSettled(tasks);
    monitor.running = false;
    const elapsed = Date.now() - started;
    setStatus(refs.monitorStatus, `Auto refresh tick | tasks=${tasks.length} | ${elapsed}ms | ${new Date().toLocaleTimeString()}`);
  }

  function startAutoRefreshMonitor() {
    if (!token()) {
      setStatus(refs.monitorStatus, "Enter Dev Token first");
      return;
    }
    stopAutoRefreshMonitor();
    const settings = monitorSettingsFromUI();
    const intervalMs = Math.max(2, Math.min(120, Number(settings.interval) || 10)) * 1000;
    state.observability.monitor.timer = setInterval(() => {
      runAutoRefreshTick().catch((error) => {
        setStatus(refs.monitorStatus, `Auto refresh failed: ${error.message}`);
      });
    }, intervalMs);
    settings.enabled = true;
    saveMonitorSettings(settings);
    setStatus(refs.monitorStatus, `Auto refresh started every ${Math.round(intervalMs / 1000)}s`);
    runAutoRefreshTick().catch((error) => {
      setStatus(refs.monitorStatus, `Auto refresh failed: ${error.message}`);
    });
  }

  async function loadFlowHistory() {
    const data = await api("/api/dev/flow/history?limit=80", { method: "GET" });
    const items = Array.isArray(data.items) ? data.items : [];
    state.history.flow = items.slice();
    setSelectOptions(
      refs.flowHistorySelect,
      items.map((item) => ({
        value: String(item.revision),
        label: `rev ${item.revision} | ${item.updated_at} | ${item.updated_by}`,
      })),
      "-- flow history --"
    );
    return items;
  }

  async function rollbackFlowFromHistory() {
    const revision = Number(refs.flowHistorySelect.value || 0);
    if (!revision) {
      setStatus(refs.flowStatus, "Select flow revision first");
      return;
    }
    await api("/api/dev/flow/rollback", {
      method: "POST",
      body: JSON.stringify({ revision, updated_by: "dev-ui-rollback" }),
    });
    await Promise.all([loadFlow(), loadFlowHistory(), graphModel() ? renderGraphFromModelDraft(false) : loadGraph(), loadRuntime()]);
    setStatus(refs.flowStatus, `Flow rolled back from revision ${revision}`);
  }

  async function loadFlowFromHistorySelection() {
    const revision = Number(refs.flowHistorySelect.value || 0);
    if (!revision) {
      await loadFlowHistory();
      setStatus(refs.flowStatus, "Flow history refreshed");
      return;
    }
    if (!state.history.flow.length) {
      await loadFlowHistory();
    }
    const item = state.history.flow.find((row) => Number(row.revision) === revision);
    if (!item || !item.config) {
      setStatus(refs.flowStatus, `Flow revision not found: ${revision}`);
      return;
    }
    applyConfig(item.config);
    setStatus(refs.flowStatus, `Loaded flow revision ${revision} into draft form (not applied yet)`);
  }

  async function loadGraphHistory() {
    const data = await api("/api/dev/graph/model/history?limit=80", { method: "GET" });
    const items = Array.isArray(data.items) ? data.items : [];
    state.history.graph = items.slice();
    setSelectOptions(
      refs.graphHistorySelect,
      items.map((item) => ({
        value: String(item.revision),
        label: `rev ${item.revision} | ${item.updated_at} | ${item.updated_by}`,
      })),
      "-- graph history --"
    );
    return items;
  }

  async function rollbackGraphFromHistory() {
    const revision = Number(refs.graphHistorySelect.value || 0);
    if (!revision) {
      setStatus(refs.graphStatus, "Select graph revision first");
      return;
    }
    await api("/api/dev/graph/model/rollback", {
      method: "POST",
      body: JSON.stringify({ revision, updated_by: "dev-ui-rollback" }),
    });
    await Promise.all([loadGraphModel(), loadGraphHistory()]);
    setStatus(refs.graphStatus, `Graph model rolled back from revision ${revision}`);
  }

  async function loadGraphFromHistorySelection() {
    const revision = Number(refs.graphHistorySelect.value || 0);
    if (!revision) {
      await loadGraphHistory();
      setStatus(refs.graphStatus, "Graph history refreshed");
      return;
    }
    if (!state.history.graph.length) {
      await loadGraphHistory();
    }
    const item = state.history.graph.find((row) => Number(row.revision) === revision);
    if (!item || !item.model) {
      setStatus(refs.graphStatus, `Graph revision not found: ${revision}`);
      return;
    }
    if (!state.graph.modelState) {
      state.graph.modelState = {
        revision: Number(item.revision),
        updated_at: item.updated_at,
        updated_by: item.updated_by,
        model: item.model,
      };
    } else {
      state.graph.modelState.model = item.model;
    }
    await renderGraphFromModelDraft(false);
    setStatus(refs.graphStatus, `Loaded graph revision ${revision} into draft model (not applied yet)`);
  }

  async function loadEnvHistory() {
    const data = await api("/api/dev/env/history?limit=80", { method: "GET" });
    const items = Array.isArray(data.items) ? data.items : [];
    state.history.env = items.slice();
    setSelectOptions(
      refs.envHistorySelect,
      items.map((item) => ({
        value: String(item.id || ""),
        label: `${item.id} | ${item.updated_at} | ${item.updated_by}`,
      })),
      "-- env history --"
    );
    return items;
  }

  async function loadEnvSnapshotPreview() {
    const snapshotId = (refs.envHistorySelect.value || "").trim();
    if (!snapshotId) {
      await loadEnvHistory();
      setStatus(refs.envStatus, "Env history refreshed");
      return;
    }
    const data = await api(`/api/dev/env/history/${encodeURIComponent(snapshotId)}`, { method: "GET" });
    fields.envRaw.value = data.content || "";
    setStatus(refs.envStatus, `Loaded snapshot ${snapshotId} into editor (not applied yet)`);
  }

  async function rollbackEnvFromHistory() {
    const snapshotId = (refs.envHistorySelect.value || "").trim();
    if (!snapshotId) {
      setStatus(refs.envStatus, "Select env history snapshot first");
      return;
    }
    const data = await api("/api/dev/env/rollback", {
      method: "POST",
      body: JSON.stringify({ snapshot_id: snapshotId, updated_by: "dev-ui-rollback" }),
    });
    await Promise.all([loadEnv(), loadEnvHistory(), loadRuntime()]);
    setStatus(refs.envStatus, `Rolled back env from ${snapshotId} | backup=${data.backup_path || "-"}`);
  }

  function renderTraceList() {
    if (!refs.traceList) {
      return;
    }
    refs.traceList.innerHTML = "";
    const traces = state.observability.traces || [];
    if (!traces.length) {
      refs.traceList.textContent = "No traces found.";
      return;
    }

    traces.forEach((trace) => {
      const row = document.createElement("div");
      row.className = "trace-item";
      if (trace.trace_id === state.observability.selectedTraceId) {
        row.classList.add("active");
      }
      row.dataset.traceId = trace.trace_id;
      const status = String(trace.status || "unknown");
      row.innerHTML = `
        <div>${esc(trace.trace_id || "")}</div>
        <small>${esc(trace.session_id || "-")} | ${esc(status)} | ${Number(trace.latency_ms || 0).toFixed(0)}ms</small>
        <small>${esc(trace.message_preview || "")}</small>
      `;
      row.addEventListener("click", () => {
        selectTrace(trace.trace_id).catch((error) => {
          setStatus(refs.traceMeta, `Trace load failed: ${error.message}`);
        });
      });
      refs.traceList.appendChild(row);
    });
  }

  async function loadTraces() {
    const sessionFilter = (refs.traceSessionFilter && refs.traceSessionFilter.value) || "";
    const statusFilter = (refs.traceStatusFilter && refs.traceStatusFilter.value) || "";
    const data = await api(query("/api/dev/traces", { limit: 120, session_id: sessionFilter, status: statusFilter }), {
      method: "GET",
    });
    state.observability.traces = Array.isArray(data.items) ? data.items : [];
    if (
      state.observability.selectedTraceId &&
      !state.observability.traces.some((item) => item.trace_id === state.observability.selectedTraceId)
    ) {
      state.observability.selectedTraceId = "";
    }
    if (!state.observability.selectedTraceId && state.observability.traces[0]) {
      state.observability.selectedTraceId = state.observability.traces[0].trace_id || "";
    }
    renderTraceList();
    if (state.observability.selectedTraceId) {
      await selectTrace(state.observability.selectedTraceId);
    } else {
      refs.traceSteps.textContent = "";
      refs.traceData.textContent = "";
      setStatus(refs.traceMeta, "No trace selected");
    }
  }

  async function selectTrace(traceId) {
    const id = String(traceId || "").trim();
    if (!id) {
      return;
    }
    const trace = await api(`/api/dev/traces/${encodeURIComponent(id)}`, { method: "GET" });
    state.observability.selectedTraceId = id;
    state.observability.selectedTrace = trace;
    if (refs.logSearchTrace) {
      refs.logSearchTrace.value = id;
    }
    renderTraceList();

    const steps = Array.isArray(trace.steps) ? trace.steps : [];
    refs.traceSteps.textContent = pretty(steps);
    refs.traceData.textContent = pretty(trace);
    setStatus(
      refs.traceMeta,
      `trace=${id} | status=${trace.status || "-"} | steps=${steps.length} | latency=${Number(trace.latency_ms || 0).toFixed(0)}ms`
    );
  }

  async function applyTraceGraphHighlight() {
    const traceId = state.observability.selectedTraceId || "";
    if (!traceId) {
      setStatus(refs.traceMeta, "Select trace first");
      return;
    }
    const data = await api(`/api/dev/traces/${encodeURIComponent(traceId)}/graph`, { method: "GET" });
    setGraphRuntimeHighlight(data);
    setActiveTab("flow-graph", true);
    if (graphModel()) {
      await renderGraphFromModelDraft(false);
    } else {
      await loadGraph();
    }
    setStatus(refs.graphStatus, `Applied trace highlight: ${traceId}`);
  }

  async function loadConnections() {
    const data = await api("/api/dev/connections", { method: "GET" });
    state.observability.connections = data;
    refs.connOutput.textContent = pretty(data);
  }

  function renderRouteMap() {
    const rawFilter = String((refs.routeFilter && refs.routeFilter.value) || "").trim().toLowerCase();
    const routes = Array.isArray(state.observability.routes) ? state.observability.routes : [];
    const filtered = !rawFilter
      ? routes
      : routes.filter((item) => {
          const methods = Array.isArray(item.methods) ? item.methods.join(",") : "";
          const tags = Array.isArray(item.tags) ? item.tags.join(",") : "";
          const haystack = `${item.path || ""} ${item.endpoint || ""} ${methods} ${tags}`.toLowerCase();
          return haystack.includes(rawFilter);
        });

    const lines = filtered.map((item) => {
      const methods = Array.isArray(item.methods) && item.methods.length ? item.methods.join(",") : "-";
      const tags = Array.isArray(item.tags) && item.tags.length ? ` [${item.tags.join(",")}]` : "";
      const endpoint = item.endpoint ? ` -> ${item.endpoint}` : "";
      return `${methods.padEnd(10, " ")} ${item.path || ""}${tags}${endpoint}`;
    });
    const head = `routes=${filtered.length}/${routes.length}`;
    refs.routeOutput.textContent = [head, ...lines].join("\n");
  }

  async function loadRoutes() {
    const data = await api("/api/dev/routes", { method: "GET" });
    state.observability.routes = Array.isArray(data.items) ? data.items : [];
    renderRouteMap();
  }

  async function runApiProbe() {
    const method = String((refs.probeMethod && refs.probeMethod.value) || "GET").trim().toUpperCase();
    const path = String((refs.probePath && refs.probePath.value) || "").trim() || "/";
    const queryRaw = String((refs.probeQuery && refs.probeQuery.value) || "").trim();
    const headersRaw = String((refs.probeHeaders && refs.probeHeaders.value) || "").trim();
    const bodyRaw = String((refs.probeBody && refs.probeBody.value) || "").trim();

    const query = parseJsonTextOrThrow(queryRaw, "Query", {});
    const headers = parseJsonTextOrThrow(headersRaw, "Headers", {});
    if (typeof query !== "object" || Array.isArray(query)) {
      throw new Error("Query must be a JSON object");
    }
    if (typeof headers !== "object" || Array.isArray(headers)) {
      throw new Error("Headers must be a JSON object");
    }

    let body = null;
    if (bodyRaw) {
      try {
        body = JSON.parse(bodyRaw);
      } catch (error) {
        body = bodyRaw;
      }
    }

    setStatus(refs.probeStatus, "Probing endpoint...");
    const data = await api("/api/dev/http/probe", {
      method: "POST",
      body: JSON.stringify({
        method,
        path,
        query,
        headers,
        body,
      }),
    });

    const bodyPreview = data.is_json && data.body_json !== null ? pretty(data.body_json) : String(data.body_text || "");
    const responseText = [
      `HTTP ${data.status_code} ${data.reason_phrase || ""}`.trim(),
      `latency_ms=${data.latency_ms} content_type=${data.content_type || "-"}`,
      "",
      "Headers:",
      pretty(data.headers || {}),
      "",
      "Body:",
      bodyPreview,
    ].join("\n");
    refs.probeOutput.textContent = responseText;
    setStatus(refs.probeStatus, `Probe done | status=${data.status_code} | latency=${data.latency_ms}ms`);
  }

  function renderWorkspaceSearchResults() {
    const root = refs.ideSearchResults;
    if (!root) {
      return;
    }
    root.innerHTML = "";
    const items = Array.isArray(state.ide.searchResults) ? state.ide.searchResults : [];
    if (!items.length) {
      root.textContent = "No results";
      return;
    }
    items.forEach((item) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "search-result-item";
      row.dataset.openPath = String(item.path || "");
      row.dataset.line = String(item.line || 1);
      row.dataset.col = String(item.column || 1);
      row.innerHTML = `
        <div><strong>${esc(item.path || "")}</strong></div>
        <small>Ln ${Number(item.line || 1)}, Col ${Number(item.column || 1)}</small>
        <div>${esc(item.preview || "")}</div>
      `;
      root.appendChild(row);
    });
  }

  async function searchWorkspace() {
    const queryText = String((refs.ideSearchQuery && refs.ideSearchQuery.value) || "").trim();
    if (!queryText) {
      setStatus(refs.ideSearchStatus, "Enter search text");
      return;
    }
    const scopePath = String((refs.ideSearchPath && refs.ideSearchPath.value) || "").trim();
    const caseSensitive = !!(refs.ideSearchCase && refs.ideSearchCase.checked);
    const regexMode = !!(refs.ideSearchRegex && refs.ideSearchRegex.checked);
    setStatus(refs.ideSearchStatus, "Searching workspace...");
    const data = await api(
      query("/api/dev/fs/search", {
        q: queryText,
        path: scopePath,
        case_sensitive: caseSensitive,
        regex: regexMode,
        max_results: 180,
      }),
      { method: "GET" }
    );
    state.ide.searchResults = Array.isArray(data.items) ? data.items : [];
    renderWorkspaceSearchResults();
    setStatus(
      refs.ideSearchStatus,
      `Search done | root=${data.root || "."} | files=${data.scanned_files || 0} | matched=${data.matched || 0}`
    );
  }

  function renderSymbolResults() {
    if (!refs.symbolResults) {
      return;
    }
    refs.symbolResults.innerHTML = "";
    const items = Array.isArray(state.ide.symbolResults) ? state.ide.symbolResults : [];
    if (!items.length) {
      refs.symbolResults.textContent = "No symbol matches";
      return;
    }
    items.forEach((item) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "search-result-item";
      row.dataset.openPath = String(item.path || "");
      row.dataset.line = String(item.line || 1);
      row.dataset.col = String(item.column || 1);
      row.innerHTML = `
        <div><strong>${esc(item.path || "")}</strong></div>
        <small>${esc(item.kind || "reference")} | Ln ${Number(item.line || 1)}, Col ${Number(item.column || 1)}</small>
        <div>${esc(item.preview || "")}</div>
      `;
      refs.symbolResults.appendChild(row);
    });
  }

  async function findSymbolInWorkspace() {
    const symbol = String((refs.symbolName && refs.symbolName.value) || "").trim();
    if (!symbol) {
      setStatus(refs.symbolStatus, "Enter symbol");
      return;
    }
    const path = String((refs.symbolPath && refs.symbolPath.value) || "").trim();
    const caseSensitive = !!(refs.symbolCase && refs.symbolCase.checked);
    setStatus(refs.symbolStatus, "Finding symbol...");
    const data = await api(
      query("/api/dev/fs/symbol", {
        symbol,
        path,
        case_sensitive: caseSensitive,
        max_results: 220,
      }),
      { method: "GET" }
    );
    state.ide.symbolResults = Array.isArray(data.items) ? data.items : [];
    renderSymbolResults();
    setStatus(
      refs.symbolStatus,
      `Symbol done | defs=${data.definitions || 0} refs=${data.references || 0} files=${data.scanned_files || 0}`
    );
  }

  async function runShellInWorkspace() {
    const command = String((refs.shellCommand && refs.shellCommand.value) || "").trim();
    if (!command) {
      setStatus(refs.shellStatus, "Enter command");
      return;
    }
    const cwd = String((refs.shellCwd && refs.shellCwd.value) || "").trim();
    const timeout = Math.max(1, Math.min(120, Number((refs.shellTimeout && refs.shellTimeout.value) || 25) || 25));
    setStatus(refs.shellStatus, "Running command...");
    const data = await api("/api/dev/shell/run", {
      method: "POST",
      body: JSON.stringify({
        command,
        cwd,
        timeout_seconds: timeout,
      }),
    });
    refs.shellOutput.textContent = [
      `$ ${data.command || ""}`,
      `cwd=${data.cwd || "."} | exit=${data.exit_code} | latency=${data.latency_ms}ms | timeout=${data.timed_out ? "yes" : "no"}`,
      "",
      "stdout:",
      String(data.stdout || ""),
      "",
      "stderr:",
      String(data.stderr || ""),
    ].join("\n");
    setStatus(
      refs.shellStatus,
      data.timed_out
        ? `Command timed out after ${data.timeout_seconds}s`
        : `Command finished | exit=${data.exit_code} | latency=${data.latency_ms}ms`
    );
    pushShellHistory({
      command,
      cwd,
      timeout,
      at: new Date().toISOString(),
      exit_code: data.exit_code,
      timed_out: data.timed_out,
    });
  }

  async function searchLogsAdvanced() {
    const payload = {
      path: refs.logSearchPath.value || "logs/user_audit.log",
      contains: refs.logSearchContains.value || "",
      platform: refs.logSearchPlatform.value || "",
      trace_id: refs.logSearchTrace.value || "",
      session_id: refs.logSearchSession.value || "",
      limit: 180,
      scan_lines: 3000,
    };
    setStatus(refs.logSearchStatus, "Searching logs...");
    const data = await api(query("/api/dev/logs/search", payload), { method: "GET" });
    refs.logSearchOutput.textContent = pretty(data.items || []);
    setStatus(refs.logSearchStatus, `Log search done | scanned=${data.scanned || 0} matched=${data.matched || 0}`);
  }

  function clearScenarioForm() {
    refs.scenarioId.value = "";
    refs.scenarioName.value = "";
    refs.scenarioDescription.value = "";
    refs.scenarioMessage.value = "";
    refs.scenarioConfig.value = "{}";
    refs.scenarioRunOutput.textContent = "";
    setStatus(refs.scenarioRunMeta, "");
  }

  function readScenarioForm() {
    const rawConfig = (refs.scenarioConfig.value || "").trim();
    const configOverride = safeJsonParse(rawConfig || "{}", null);
    if (configOverride === null || typeof configOverride !== "object" || Array.isArray(configOverride)) {
      throw new Error("config_override must be a valid JSON object");
    }
    return {
      id: (refs.scenarioId.value || "").trim() || null,
      name: (refs.scenarioName.value || "").trim(),
      description: (refs.scenarioDescription.value || "").trim(),
      message: (refs.scenarioMessage.value || "").trim(),
      config_override: configOverride,
      updated_by: "dev-ui",
    };
  }

  function fillScenarioForm(item) {
    const scenario = item || {};
    refs.scenarioId.value = scenario.id || "";
    refs.scenarioName.value = scenario.name || "";
    refs.scenarioDescription.value = scenario.description || "";
    refs.scenarioMessage.value = scenario.message || "";
    refs.scenarioConfig.value = pretty(scenario.config_override || {});
    refs.scenarioRunOutput.textContent = scenario.last_output_preview || "";
    setStatus(
      refs.scenarioRunMeta,
      scenario.last_run_at
        ? `Last run: ${scenario.last_run_at} | trace=${scenario.last_trace_id || "-"} | latency=${scenario.last_latency_ms || 0}ms`
        : "No previous run"
    );
  }

  async function loadScenarios() {
    const data = await api("/api/dev/scenarios?limit=200", { method: "GET" });
    const items = Array.isArray(data.items) ? data.items : [];
    state.scenarios.items = items;
    setSelectOptions(
      refs.scenarioSelect,
      items.map((item) => ({
        value: item.id,
        label: `${item.id} | ${item.name}`,
      })),
      "-- scenarios --"
    );

    if (!state.scenarios.selectedId && items[0]) {
      state.scenarios.selectedId = items[0].id;
    }
    if (state.scenarios.selectedId) {
      refs.scenarioSelect.value = state.scenarios.selectedId;
    }
    if (refs.scenarioSelect.value) {
      await loadScenarioFromSelect();
    } else {
      clearScenarioForm();
    }
  }

  async function loadScenarioFromSelect() {
    const scenarioId = (refs.scenarioSelect.value || "").trim();
    if (!scenarioId) {
      clearScenarioForm();
      return;
    }
    const data = await api(`/api/dev/scenarios/${encodeURIComponent(scenarioId)}`, { method: "GET" });
    state.scenarios.selectedId = scenarioId;
    fillScenarioForm(data);
    setStatus(refs.scenarioStatus, `Loaded scenario ${scenarioId}`);
  }

  async function saveScenarioFromForm() {
    const payload = readScenarioForm();
    if (!payload.name) {
      throw new Error("Scenario name is required");
    }
    if (!payload.message) {
      throw new Error("Scenario message is required");
    }
    const data = await api("/api/dev/scenarios", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    const saved = data.item || {};
    state.scenarios.selectedId = saved.id || "";
    await loadScenarios();
    if (saved.id) {
      refs.scenarioSelect.value = saved.id;
      await loadScenarioFromSelect();
    }
    setStatus(refs.scenarioStatus, `Saved scenario ${saved.id || "-"}`);
  }

  async function deleteScenarioSelected() {
    const scenarioId = (refs.scenarioSelect.value || refs.scenarioId.value || "").trim();
    if (!scenarioId) {
      throw new Error("Select scenario first");
    }
    await api(`/api/dev/scenarios/${encodeURIComponent(scenarioId)}`, { method: "DELETE" });
    state.scenarios.selectedId = "";
    await loadScenarios();
    clearScenarioForm();
    setStatus(refs.scenarioStatus, `Deleted scenario ${scenarioId}`);
  }

  async function runScenarioSelected() {
    const scenarioId = (refs.scenarioSelect.value || refs.scenarioId.value || "").trim();
    if (!scenarioId) {
      throw new Error("Select scenario first");
    }
    setStatus(refs.scenarioStatus, `Running scenario ${scenarioId}...`);
    const data = await api(`/api/dev/scenarios/${encodeURIComponent(scenarioId)}/run`, {
      method: "POST",
      body: JSON.stringify({ updated_by: "dev-ui", include_debug: true }),
    });
    const result = data.result || {};
    refs.scenarioRunOutput.textContent = result.text || "";
    setStatus(
      refs.scenarioRunMeta,
      `trace=${data.trace_id || "-"} | latency=${Number(data.latency_ms || 0).toFixed(0)}ms | tokens=${((result.tokens || {}).total_tokens) || 0}`
    );
    state.observability.selectedTraceId = data.trace_id || "";
    await Promise.all([loadScenarios(), loadTraces()]);
    if (state.observability.selectedTraceId) {
      await selectTrace(state.observability.selectedTraceId);
      setActiveTab("observability", true);
    }
    setStatus(refs.scenarioStatus, `Scenario ${scenarioId} completed`);
  }

  async function loadTree(path, force) {
    const p = normPath(path);
    if (!force && state.ide.tree.has(p)) {
      return state.ide.tree.get(p) || [];
    }
    const data = await api(query("/api/dev/fs/tree", { path: p, max_entries: 300 }), { method: "GET" });
    const items = Array.isArray(data.items) ? data.items : [];
    state.ide.tree.set(p, items);
    return items;
  }

  async function refreshExplorer(force) {
    if (force) {
      state.ide.tree.clear();
    }
    setStatus(refs.ideTreeStatus, "Loading explorer...");
    await loadTree("", !!force);
    const expanded = Array.from(state.ide.expanded).filter((p) => p);
    for (const p of expanded) {
      try { await loadTree(p, !!force); } catch (e) {}
    }
    renderExplorer();
    setStatus(refs.ideTreeStatus, `Explorer ready | expanded=${state.ide.expanded.size}`);
  }

  function renderExplorer() {
    refs.ideTree.innerHTML = "";
    if (!state.ide.tree.has("")) {
      refs.ideTree.textContent = "Connect and refresh explorer.";
      return;
    }
    const frag = document.createDocumentFragment();
    renderBranch("", 0, frag);
    refs.ideTree.appendChild(frag);
  }

  function renderBranch(dir, depth, parent) {
    const list = state.ide.tree.get(dir) || [];
    list.forEach((it) => {
      const isDir = it.type === "dir";
      const expanded = isDir && state.ide.expanded.has(it.path);
      const row = document.createElement("div");
      row.className = "tree-row";
      if (it.path === state.ide.selectedPath) row.classList.add("selected");
      row.style.setProperty("--indent-width", `${depth * 14}px`);
      row.innerHTML = `
        <span class="tree-indent"></span>
        <span class="tree-toggle">${isDir ? (expanded ? "v" : ">") : ""}</span>
        <span class="tree-icon">${isDir ? "d" : "f"}</span>
        <span class="tree-name">${esc(it.name)}</span>
      `;
      row.addEventListener("click", () => {
        state.ide.selectedPath = it.path;
        state.ide.selectedType = it.type;
        refs.ideOpenPath.value = it.path;
        if (isDir) state.ide.currentDir = it.path;
        renderExplorer();
      });
      row.addEventListener("dblclick", () => {
        if (isDir) {
          toggleDir(it.path).catch((e) => setStatus(refs.ideTreeStatus, `Toggle failed: ${e.message}`));
        } else {
          openFile(it.path).catch((e) => setStatus(refs.ideEditorStatus, `Open failed: ${e.message}`));
        }
      });
      parent.appendChild(row);

      if (isDir && expanded && state.ide.tree.has(it.path)) {
        renderBranch(it.path, depth + 1, parent);
      }
    });
  }

  async function toggleDir(path) {
    const p = normPath(path);
    if (state.ide.expanded.has(p)) {
      state.ide.expanded.delete(p);
      renderExplorer();
      return;
    }
    state.ide.expanded.add(p);
    await loadTree(p, false);
    renderExplorer();
  }

  async function expandToFile(path) {
    const p = normPath(path);
    await loadTree("", false);
    const parts = p.split("/").filter(Boolean);
    let cur = "";
    for (let i = 0; i < parts.length - 1; i += 1) {
      cur = cur ? `${cur}/${parts[i]}` : parts[i];
      state.ide.expanded.add(cur);
      await loadTree(cur, false);
    }
    state.ide.currentDir = parentPath(p);
  }

  function renderEditorMeta() {
    if (!state.ide.openPath) {
      refs.ideEditorMeta.textContent = "No file opened";
      updateEditorIndicators();
      return;
    }
    const m = state.ide.fileMeta || {};
    refs.ideEditorMeta.textContent = `${state.ide.openPath} | ${m.language || "plaintext"} | ${fmtBytes(m.size)} | ${m.modified_at || "-"}${state.ide.dirty ? " | UNSAVED" : ""}`;
    updateEditorIndicators();
  }

  function fmtBytes(size) {
    const n = Number(size || 0);
    if (!Number.isFinite(n)) return "-";
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / (1024 * 1024)).toFixed(2)} MB`;
  }

  async function openFile(rawPath) {
    const p = normPath(rawPath || refs.ideOpenPath.value || state.ide.selectedPath);
    if (!p) {
      setStatus(refs.ideEditorStatus, "Please provide file path");
      return;
    }
    if (state.ide.dirty && state.ide.openPath && state.ide.openPath !== p) {
      if (!window.confirm("Discard unsaved changes and open another file?")) return;
    }
    setStatus(refs.ideEditorStatus, `Opening ${p}...`);
    const data = await api(query("/api/dev/fs/read", { path: p }), { method: "GET" });
    state.ide.openPath = normPath(data.path || p);
    state.ide.fileMeta = data;
    state.ide.lastContent = data.content || "";
    state.ide.dirty = false;
    setEditorValue(state.ide.lastContent);
    setEditorLanguage(data.language || detectLanguage(state.ide.openPath));
    refs.ideOpenPath.value = state.ide.openPath;
    state.ide.selectedPath = state.ide.openPath;
    state.ide.selectedType = "file";
    await expandToFile(state.ide.openPath);
    renderExplorer();
    renderEditorMeta();
    setStatus(refs.ideEditorStatus, `Opened ${state.ide.openPath}`);
  }

  function focusEditorPosition(line, col) {
    const targetLine = Math.max(1, Number(line) || 1);
    const targetCol = Math.max(1, Number(col) || 1);
    if (usingMonaco()) {
      const editor = state.ide.editor.monacoEditor;
      editor.revealPositionInCenter({ lineNumber: targetLine, column: targetCol });
      editor.setPosition({ lineNumber: targetLine, column: targetCol });
      editor.focus();
      updateEditorIndicators();
      return;
    }

    const content = refs.ideEditor.value || "";
    const lines = content.split("\n");
    let idx = 0;
    for (let i = 0; i < targetLine - 1 && i < lines.length; i += 1) {
      idx += lines[i].length + 1;
    }
    const lineText = lines[Math.max(0, targetLine - 1)] || "";
    idx += Math.min(lineText.length, Math.max(0, targetCol - 1));
    refs.ideEditor.focus();
    refs.ideEditor.selectionStart = idx;
    refs.ideEditor.selectionEnd = idx;
    refs.ideEditor.scrollTop = Math.max(0, (targetLine - 5) * 18);
    updateEditorIndicators();
  }

  async function openFileAtPosition(path, line, col) {
    const p = normPath(path);
    if (!p) {
      return;
    }
    if (state.ide.openPath !== p) {
      await openFile(p);
    }
    focusEditorPosition(line, col);
  }

  async function reloadFile() {
    if (!state.ide.openPath) {
      setStatus(refs.ideEditorStatus, "No open file");
      return;
    }
    if (state.ide.dirty && !window.confirm("Discard unsaved changes and reload file?")) {
      return;
    }
    await openFile(state.ide.openPath);
  }

  async function saveFile() {
    const p = normPath(refs.ideOpenPath.value || state.ide.openPath);
    if (!p) {
      setStatus(refs.ideEditorStatus, "Please provide file path");
      return;
    }
    setStatus(refs.ideEditorStatus, `Saving ${p}...`);
    const data = await api("/api/dev/fs/write", {
      method: "PUT",
      body: JSON.stringify({ path: p, content: getEditorValue(), create_dirs: true }),
    });
    state.ide.openPath = normPath(data.path || p);
    state.ide.lastContent = getEditorValue();
    state.ide.dirty = false;
    state.ide.fileMeta = {
      ...(state.ide.fileMeta || {}),
      language: (state.ide.fileMeta && state.ide.fileMeta.language) || detectLanguage(state.ide.openPath),
      size: data.size,
      modified_at: data.modified_at,
    };
    refs.ideOpenPath.value = state.ide.openPath;
    state.ide.selectedPath = state.ide.openPath;
    state.ide.selectedType = "file";
    renderEditorMeta();
    setStatus(refs.ideEditorStatus, `Saved ${state.ide.openPath}${data.backup_path ? ` | backup=${data.backup_path}` : ""}`);
    await Promise.all([refreshExplorer(true), loadRuntime(), loadLogs()]);
    if (state.ide.openPath === "backend/dev/flow_config.json") {
      await Promise.all([loadFlow(), graphModel() ? renderGraphFromModelDraft(false) : loadGraph()]);
    }
    if (state.ide.openPath === "backend/dev/flow_graph_model.json") {
      await loadGraphModel();
    }
  }

  function detectLanguage(path) {
    const p = normPath(path).toLowerCase();
    if (p.endsWith(".py")) return "python";
    if (p.endsWith(".js")) return "javascript";
    if (p.endsWith(".ts")) return "typescript";
    if (p.endsWith(".html")) return "html";
    if (p.endsWith(".css")) return "css";
    if (p.endsWith(".json")) return "json";
    if (p.endsWith(".md")) return "markdown";
    if (p.endsWith(".env")) return "dotenv";
    if (p.endsWith(".yml") || p.endsWith(".yaml")) return "yaml";
    if (p.endsWith(".sql")) return "sql";
    if (p.endsWith(".txt")) return "text";
    return "plaintext";
  }

  function updateEditorIndicators() {
    if (!refs.ideLangBadge || !refs.ideCursorPos || !refs.ideDirtyBadge) {
      return;
    }

    const lang = ((state.ide.fileMeta && state.ide.fileMeta.language) || detectLanguage(state.ide.openPath) || "plaintext").toLowerCase();
    refs.ideLangBadge.textContent = `${lang}${usingMonaco() ? " · monaco" : " · basic"}`;
    const cur = editorCursor();
    refs.ideCursorPos.textContent = `Ln ${cur.line}, Col ${cur.col}`;
    refs.ideDirtyBadge.textContent = state.ide.dirty ? "Unsaved" : "Saved";
    refs.ideDirtyBadge.classList.toggle("unsaved", state.ide.dirty);
    refs.ideDirtyBadge.classList.toggle("saved", !state.ide.dirty);
  }

  async function goRoot() {
    state.ide.selectedPath = "";
    state.ide.selectedType = "dir";
    state.ide.currentDir = "";
    state.ide.expanded.add("");
    await refreshExplorer(false);
  }

  async function goUp() {
    const base = state.ide.currentDir || parentPath(state.ide.selectedPath) || "";
    const up = parentPath(base);
    state.ide.currentDir = up;
    state.ide.selectedPath = up;
    state.ide.selectedType = "dir";
    state.ide.expanded.add(up);
    await loadTree(up, false);
    renderExplorer();
  }

  async function loadRuntime() {
    setStatus(refs.ideRuntimeStatus, "Loading runtime summary...");
    const data = await api("/api/dev/runtime/summary", { method: "GET" });
    refs.ideRuntimeSummary.textContent = JSON.stringify(data, null, 2);
    setStatus(refs.ideRuntimeStatus, "Runtime summary loaded");
  }

  async function loadLogs() {
    const p = normPath(refs.ideLogPath.value || "logs/user_audit.log");
    setStatus(refs.ideRuntimeStatus, "Loading log tail...");
    const data = await api(query("/api/dev/logs/tail", { path: p, lines: 160 }), { method: "GET" });
    refs.ideRuntimeLog.textContent = data.exists ? (data.lines || []).join("\n") : `Log not found: ${data.path}`;
    setStatus(refs.ideRuntimeStatus, data.exists ? `Tail loaded: ${data.path} | lines=${data.line_count}` : `Log file not found: ${data.path}`);
  }

  async function connectAll() {
    if (!token()) {
      setStatus(refs.authStatus, "Please enter Dev Token");
      return;
    }
    localStorage.setItem(TOKEN_KEY, token());
    setStatus(refs.authStatus, "Connecting...");
    await Promise.all([
      loadFlow(),
      loadEnv(),
      loadGraphModel(),
      refreshExplorer(true),
      loadRuntime(),
      loadLogs(),
      loadTraces(),
      loadConnections(),
      loadRoutes(),
      loadScenarios(),
    ]);
    await ensureMonacoEditor();
    setStatus(refs.authStatus, "Connected");
  }

  function esc(v) {
    return String(v)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function escAttr(v) {
    return esc(v).replace(/`/g, "&#96;");
  }

  refs.connectBtn.addEventListener("click", () => connectAll().catch((e) => setStatus(refs.authStatus, `Connection failed: ${e.message}`)));
  refs.loadBtn.addEventListener("click", () => Promise.all([loadFlow(), loadGraphModel()]).catch((e) => setStatus(refs.flowStatus, `Reload failed: ${e.message}`)));
  refs.saveBtn.addEventListener("click", () => {
    saveFlow()
      .then(() => (graphModel() ? renderGraphFromModelDraft(false) : loadGraph()))
      .then(() => loadRuntime())
      .catch((e) => setStatus(refs.flowStatus, `Save failed: ${e.message}`));
  });
  refs.flowHistoryLoadBtn.addEventListener("click", () => loadFlowFromHistorySelection().catch((e) => setStatus(refs.flowStatus, `Flow history load failed: ${e.message}`)));
  refs.flowHistorySelect.addEventListener("change", () => {
    const revision = refs.flowHistorySelect.value || "";
    if (revision) {
      setStatus(refs.flowStatus, `Selected flow revision ${revision}. Click Load History to preview or Rollback to apply.`);
    }
  });
  refs.flowRollbackBtn.addEventListener("click", () => {
    if (!window.confirm("Rollback flow to selected revision?")) {
      return;
    }
    rollbackFlowFromHistory().catch((e) => setStatus(refs.flowStatus, `Flow rollback failed: ${e.message}`));
  });
  refs.testBtn.addEventListener("click", () => runTest().catch((e) => setStatus(refs.testMeta, `Test failed: ${e.message}`)));
  refs.clearBtn.addEventListener("click", () => { setStatus(refs.testMeta, ""); refs.testOutput.textContent = ""; });
  refs.envLoadBtn.addEventListener("click", () => loadEnv().catch((e) => setStatus(refs.envStatus, `Reload env failed: ${e.message}`)));
  refs.envSaveBtn.addEventListener("click", () => saveEnv().catch((e) => setStatus(refs.envStatus, `Save env failed: ${e.message}`)));
  refs.envHistoryLoadBtn.addEventListener("click", () => loadEnvSnapshotPreview().catch((e) => setStatus(refs.envStatus, `Env history load failed: ${e.message}`)));
  refs.envHistorySelect.addEventListener("change", () => {
    const snapshotId = (refs.envHistorySelect.value || "").trim();
    if (snapshotId) {
      setStatus(refs.envStatus, `Selected snapshot ${snapshotId}. Click Load History to preview or Rollback to apply.`);
    }
  });
  refs.envRollbackBtn.addEventListener("click", () => {
    if (!window.confirm("Rollback .env to selected snapshot?")) {
      return;
    }
    rollbackEnvFromHistory().catch((e) => setStatus(refs.envStatus, `Env rollback failed: ${e.message}`));
  });
  refs.graphLoadBtn.addEventListener("click", () => loadGraph().catch((e) => setStatus(refs.graphStatus, `Reload graph failed: ${e.message}`)));
  refs.graphPreviewBtn.addEventListener("click", () => previewGraph().catch((e) => setStatus(refs.graphStatus, `Preview graph failed: ${e.message}`)));
  refs.graphModelLoadBtn.addEventListener("click", () => loadGraphModel().catch((e) => setStatus(refs.graphStatus, `Load graph model failed: ${e.message}`)));
  refs.graphModelSaveBtn.addEventListener("click", () => saveGraphModel().catch((e) => setStatus(refs.graphStatus, `Save graph model failed: ${e.message}`)));
  refs.graphModelResetBtn.addEventListener("click", () => {
    if (!window.confirm("Reset graph model to default?")) {
      return;
    }
    resetGraphModel().catch((e) => setStatus(refs.graphStatus, `Reset graph model failed: ${e.message}`));
  });
  refs.graphLayoutBtn.addEventListener("click", () => autoLayoutGraph().catch((e) => setStatus(refs.graphStatus, `Layout failed: ${e.message}`)));
  refs.graphHistoryLoadBtn.addEventListener("click", () => loadGraphFromHistorySelection().catch((e) => setStatus(refs.graphStatus, `Graph history load failed: ${e.message}`)));
  refs.graphHistorySelect.addEventListener("change", () => {
    const revision = refs.graphHistorySelect.value || "";
    if (revision) {
      setStatus(refs.graphStatus, `Selected graph revision ${revision}. Click Load History to preview or Rollback to apply.`);
    }
  });
  refs.graphRollbackBtn.addEventListener("click", () => {
    if (!window.confirm("Rollback graph model to selected revision?")) {
      return;
    }
    rollbackGraphFromHistory().catch((e) => setStatus(refs.graphStatus, `Graph rollback failed: ${e.message}`));
  });
  refs.graphZoomOutBtn.addEventListener("click", () => changeGraphZoom(-1));
  refs.graphZoomResetBtn.addEventListener("click", () => resetGraphZoom());
  refs.graphZoomInBtn.addEventListener("click", () => changeGraphZoom(1));

  refs.graphNodeNewBtn.addEventListener("click", () => newGraphNode().catch((e) => setStatus(refs.graphStatus, `New node failed: ${e.message}`)));
  refs.graphNodeApplyBtn.addEventListener("click", () => applyGraphNode().catch((e) => setStatus(refs.graphStatus, `Apply node failed: ${e.message}`)));
  refs.graphNodeDeleteBtn.addEventListener("click", () => {
    if (!window.confirm("Delete this node and connected edges?")) {
      return;
    }
    deleteGraphNode().catch((e) => setStatus(refs.graphStatus, `Delete node failed: ${e.message}`));
  });
  refs.graphEdgeSelect.addEventListener("change", () => {
    state.graph.selectedEdge = refs.graphEdgeSelect.value || null;
    populateEdgeEditor(state.graph.selectedEdge || "");
  });
  refs.graphEdgeNewBtn.addEventListener("click", () => newGraphEdge().catch((e) => setStatus(refs.graphStatus, `New edge failed: ${e.message}`)));
  refs.graphEdgeApplyBtn.addEventListener("click", () => applyGraphEdge().catch((e) => setStatus(refs.graphStatus, `Apply edge failed: ${e.message}`)));
  refs.graphEdgeDeleteBtn.addEventListener("click", () => {
    if (!window.confirm("Delete this edge?")) {
      return;
    }
    deleteGraphEdge().catch((e) => setStatus(refs.graphStatus, `Delete edge failed: ${e.message}`));
  });

  refs.ideRootBtn.addEventListener("click", () => goRoot().catch((e) => setStatus(refs.ideTreeStatus, `Root failed: ${e.message}`)));
  refs.ideUpBtn.addEventListener("click", () => goUp().catch((e) => setStatus(refs.ideTreeStatus, `Up failed: ${e.message}`)));
  refs.ideRefreshTreeBtn.addEventListener("click", () => refreshExplorer(true).catch((e) => setStatus(refs.ideTreeStatus, `Refresh failed: ${e.message}`)));
  refs.ideOpenBtn.addEventListener("click", () => openFile().catch((e) => setStatus(refs.ideEditorStatus, `Open failed: ${e.message}`)));
  refs.ideReloadBtn.addEventListener("click", () => reloadFile().catch((e) => setStatus(refs.ideEditorStatus, `Reload failed: ${e.message}`)));
  refs.ideSaveBtn.addEventListener("click", () => saveFile().catch((e) => setStatus(refs.ideEditorStatus, `Save failed: ${e.message}`)));
  refs.ideRuntimeRefreshBtn.addEventListener("click", () => Promise.all([loadRuntime(), loadLogs()]).catch((e) => setStatus(refs.ideRuntimeStatus, `Runtime refresh failed: ${e.message}`)));
  refs.ideLogRefreshBtn.addEventListener("click", () => loadLogs().catch((e) => setStatus(refs.ideRuntimeStatus, `Log load failed: ${e.message}`)));
  refs.ideSearchBtn.addEventListener("click", () => searchWorkspace().catch((e) => setStatus(refs.ideSearchStatus, `Search failed: ${e.message}`)));
  refs.symbolFindBtn.addEventListener("click", () => findSymbolInWorkspace().catch((e) => setStatus(refs.symbolStatus, `Symbol search failed: ${e.message}`)));
  refs.shellRunBtn.addEventListener("click", () => runShellInWorkspace().catch((e) => setStatus(refs.shellStatus, `Run failed: ${e.message}`)));
  refs.shellPreset.addEventListener("change", () => {
    const value = String(refs.shellPreset.value || "").trim();
    if (value) {
      refs.shellCommand.value = value;
      setStatus(refs.shellStatus, "Preset applied");
    }
  });
  refs.shellHistoryClearBtn.addEventListener("click", () => {
    state.ide.shellHistory = [];
    saveShellHistory();
    renderShellHistory();
    setStatus(refs.shellStatus, "Command history cleared");
  });

  refs.traceRefreshBtn.addEventListener("click", () => loadTraces().catch((e) => setStatus(refs.traceMeta, `Trace refresh failed: ${e.message}`)));
  refs.traceSessionFilter.addEventListener("change", () => loadTraces().catch((e) => setStatus(refs.traceMeta, `Trace filter failed: ${e.message}`)));
  refs.traceStatusFilter.addEventListener("change", () => loadTraces().catch((e) => setStatus(refs.traceMeta, `Trace filter failed: ${e.message}`)));
  refs.traceApplyGraphBtn.addEventListener("click", () => applyTraceGraphHighlight().catch((e) => setStatus(refs.traceMeta, `Graph highlight failed: ${e.message}`)));
  refs.traceClearGraphBtn.addEventListener("click", () => {
    clearGraphRuntimeHighlight();
    setStatus(refs.traceMeta, "Graph highlight cleared");
  });
  refs.connRefreshBtn.addEventListener("click", () => loadConnections().catch((e) => {
    refs.connOutput.textContent = `Connection map load failed: ${e.message}`;
  }));
  refs.routeRefreshBtn.addEventListener("click", () => loadRoutes().catch((e) => {
    refs.routeOutput.textContent = `Route map load failed: ${e.message}`;
  }));
  refs.routeFilter.addEventListener("input", () => renderRouteMap());
  refs.probeSendBtn.addEventListener("click", () => runApiProbe().catch((e) => setStatus(refs.probeStatus, `Probe failed: ${e.message}`)));
  refs.logSearchBtn.addEventListener("click", () => searchLogsAdvanced().catch((e) => setStatus(refs.logSearchStatus, `Log search failed: ${e.message}`)));
  refs.monitorStartBtn.addEventListener("click", () => startAutoRefreshMonitor());
  refs.monitorStopBtn.addEventListener("click", () => stopAutoRefreshMonitor());
  refs.monitorInterval.addEventListener("change", () => saveMonitorSettings(monitorSettingsFromUI()));
  refs.monitorAutoTraces.addEventListener("change", () => saveMonitorSettings(monitorSettingsFromUI()));
  refs.monitorAutoLogSearch.addEventListener("change", () => saveMonitorSettings(monitorSettingsFromUI()));
  refs.monitorAutoRuntimeLog.addEventListener("change", () => saveMonitorSettings(monitorSettingsFromUI()));
  refs.monitorAutoRuntimeSummary.addEventListener("change", () => saveMonitorSettings(monitorSettingsFromUI()));

  refs.scenarioRefreshBtn.addEventListener("click", () => loadScenarios().catch((e) => setStatus(refs.scenarioStatus, `Scenario refresh failed: ${e.message}`)));
  refs.scenarioSelect.addEventListener("change", () => loadScenarioFromSelect().catch((e) => setStatus(refs.scenarioStatus, `Scenario load failed: ${e.message}`)));
  refs.scenarioNewBtn.addEventListener("click", () => {
    refs.scenarioSelect.value = "";
    state.scenarios.selectedId = "";
    clearScenarioForm();
    setStatus(refs.scenarioStatus, "Ready for new scenario");
  });
  refs.scenarioLoadBtn.addEventListener("click", () => loadScenarioFromSelect().catch((e) => setStatus(refs.scenarioStatus, `Scenario load failed: ${e.message}`)));
  refs.scenarioSaveBtn.addEventListener("click", () => saveScenarioFromForm().catch((e) => setStatus(refs.scenarioStatus, `Scenario save failed: ${e.message}`)));
  refs.scenarioDeleteBtn.addEventListener("click", () => {
    if (!window.confirm("Delete selected scenario?")) {
      return;
    }
    deleteScenarioSelected().catch((e) => setStatus(refs.scenarioStatus, `Scenario delete failed: ${e.message}`));
  });
  refs.scenarioRunBtn.addEventListener("click", () => runScenarioSelected().catch((e) => setStatus(refs.scenarioStatus, `Scenario run failed: ${e.message}`)));

  refs.ideEditor.addEventListener("input", () => {
    if (usingMonaco()) {
      return;
    }
    state.ide.dirty = getEditorValue() !== state.ide.lastContent;
    renderEditorMeta();
  });
  refs.ideEditor.addEventListener("click", () => {
    if (!usingMonaco()) updateEditorIndicators();
  });
  refs.ideEditor.addEventListener("keyup", () => {
    if (!usingMonaco()) updateEditorIndicators();
  });
  refs.ideEditor.addEventListener("select", () => {
    if (!usingMonaco()) updateEditorIndicators();
  });
  refs.ideEditor.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      saveFile().catch((err) => setStatus(refs.ideEditorStatus, `Save failed: ${err.message}`));
    }
  });

  refs.inspectorFiles.addEventListener("click", (e) => {
    const target = e.target;
    if (!(target instanceof HTMLElement)) return;
    const button = target.closest("button[data-open-file]");
    if (!(button instanceof HTMLButtonElement)) return;
    const file = button.getAttribute("data-open-file");
    if (!file) return;
    setActiveTab("workspace", true);
    openFile(file).catch((err) => setStatus(refs.ideEditorStatus, `Open from graph failed: ${err.message}`));
  });

  refs.ideSearchResults.addEventListener("click", (e) => {
    const target = e.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    const button = target.closest("button[data-open-path]");
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }
    const path = button.dataset.openPath || "";
    const line = Number(button.dataset.line || 1);
    const col = Number(button.dataset.col || 1);
    openFileAtPosition(path, line, col).catch((err) => setStatus(refs.ideEditorStatus, `Open result failed: ${err.message}`));
  });

  refs.symbolResults.addEventListener("click", (e) => {
    const target = e.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    const button = target.closest("button[data-open-path]");
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }
    const path = button.dataset.openPath || "";
    const line = Number(button.dataset.line || 1);
    const col = Number(button.dataset.col || 1);
    openFileAtPosition(path, line, col).catch((err) => setStatus(refs.ideEditorStatus, `Open symbol failed: ${err.message}`));
  });

  refs.shellHistory.addEventListener("click", (e) => {
    const target = e.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    const button = target.closest("button[data-command]");
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }
    refs.shellCommand.value = button.dataset.command || "";
    refs.shellCwd.value = button.dataset.cwd || "";
    refs.shellTimeout.value = String(button.dataset.timeout || "25");
    setStatus(refs.shellStatus, "Loaded command from history");
  });

  refs.graphBoard.addEventListener("wheel", onGraphWheel, { passive: false });
  refs.graphBoard.addEventListener("pointerdown", onGraphBoardPointerDown);

  window.addEventListener("pointermove", (ev) => {
    onGraphPanPointerMove(ev);
    onGraphPointerMove(ev);
  });
  window.addEventListener("pointerup", (ev) => {
    onGraphPanPointerEnd(ev);
    onGraphPointerEnd(ev);
  });
  window.addEventListener("pointercancel", (ev) => {
    onGraphPanPointerEnd(ev);
    onGraphPointerEnd(ev);
  });
  window.addEventListener("resize", () => {
    if (!state.graph.data || !Array.isArray(state.graph.data.nodes)) {
      return;
    }
    refreshGraphViewport();
  });

  const savedToken = localStorage.getItem(TOKEN_KEY);
  if (savedToken) refs.token.value = savedToken;
  loadShellHistory();
  renderShellHistory();
  const monitorSettings = loadMonitorSettings();
  applyMonitorSettingsToUI(monitorSettings);
  if (monitorSettings.enabled) {
    startAutoRefreshMonitor();
  }
  initTabs();
  setGraphZoomIndicator();
  renderEditorMeta();
  updateEditorIndicators();
})();
