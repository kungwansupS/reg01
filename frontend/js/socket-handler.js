const socket = window.socket || null;

let currentAIResponseAudio = null;
let currentMediaSource = null;
let stopped = false;
let lastAIKey = "";
let lastAIAt = 0;

const skipBtn = document.getElementById("skip-ai-response");

function dedupeAIMessage(data) {
  const key = `${String(data?.motion || "")}|${String(data?.text || "")}`.trim();
  const now = Date.now();
  if (key && key === lastAIKey && now - lastAIAt < 2000) return true;
  lastAIKey = key;
  lastAIAt = now;
  return false;
}

function registerSessionRoom() {
  if (!socket || !socket.connected) return;
  const sid = (window.session_id || localStorage.getItem("session_id") || "").trim();
  if (!sid) return;
  socket.emit("client_register_session", { session_id: sid });
}

function showStatusTemporarily() {
  const connectionStatus = document.getElementById("connection-status");
  connectionStatus?.classList.add("show");
  setTimeout(() => {
    connectionStatus?.classList.remove("show");
  }, 3000);
}

function stopCurrentPlayback() {
  stopped = true;
  if (currentAIResponseAudio) {
    currentAIResponseAudio.pause();
    currentAIResponseAudio.currentTime = 0;
    currentAIResponseAudio.src = "";
    currentAIResponseAudio = null;
  }
  if (currentMediaSource) {
    try {
      if (currentMediaSource.readyState === "open") currentMediaSource.endOfStream();
    } catch (_) {
      // ignore
    }
    currentMediaSource = null;
  }
  skipBtn?.classList.add("hidden");
}

if (skipBtn) {
  skipBtn.addEventListener("click", stopCurrentPlayback);
}

async function streamTtsAudio(text) {
  const form = new FormData();
  form.append("text", text);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 8000);
  let response;
  try {
    response = await fetch("/api/speak", {
      method: "POST",
      body: form,
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeoutId);
  }

  if (response.status === 204) return;
  const contentType = String(response.headers.get("content-type") || "").toLowerCase();
  if (!response.ok || !response.body || !contentType.includes("audio/")) return;

  const mediaSource = new MediaSource();
  currentMediaSource = mediaSource;
  stopped = false;

  const audio = new Audio();
  audio.src = URL.createObjectURL(mediaSource);
  currentAIResponseAudio = audio;
  skipBtn?.classList.remove("hidden");

  audio.addEventListener("ended", () => {
    skipBtn?.classList.add("hidden");
    currentAIResponseAudio = null;
    currentMediaSource = null;
  });

  await audio.play().catch(() => {});

  mediaSource.addEventListener("sourceopen", () => {
    const sourceBuffer = mediaSource.addSourceBuffer("audio/mpeg");
    const reader = response.body.getReader();
    const queue = [];
    let updating = false;

    sourceBuffer.addEventListener("updateend", () => {
      updating = false;
      if (queue.length > 0 && !sourceBuffer.updating) {
        sourceBuffer.appendBuffer(queue.shift());
      }
    });

    function pump() {
      if (stopped) return;
      reader.read().then(({ done, value }) => {
        if (stopped) return;
        if (done) {
          if (!sourceBuffer.updating && queue.length === 0) {
            try {
              mediaSource.endOfStream();
            } catch (_) {
              // ignore
            }
          }
          return;
        }
        if (!sourceBuffer.updating && !updating) {
          sourceBuffer.appendBuffer(value);
          updating = true;
        } else {
          queue.push(value);
        }
        pump();
      });
    }

    pump();
  });

  if (typeof setupAudioAnalyzer === "function") {
    setupAudioAnalyzer(audio);
  }
}

window.handleAIResponse = async function handleAIResponse(data) {
  if (!data || dedupeAIMessage(data)) return;

  const text = String(data.text || "").trim();
  if (!text) {
    const aiStatusBar = document.getElementById("ai-status-bar");
    if (aiStatusBar) aiStatusBar.textContent = "No response text.";
    return;
  }

  const aiMessage = document.createElement("div");
  aiMessage.className = "ai-message";
  aiMessage.textContent = text;
  const subtitles = document.getElementById("subtitles");
  subtitles?.appendChild(aiMessage);
  subtitles.scrollTop = subtitles?.scrollHeight || 0;

  if (data.motion && typeof playMotion === "function") {
    playMotion(data.motion);
  }

  try {
    await streamTtsAudio(text);
  } catch (err) {
    console.error("TTS stream error:", err);
  }
};

if (!socket) {
  console.warn("Socket unavailable. HTTP fallback mode enabled.");
} else {
  socket.on("connect", () => {
    const statusText = document.getElementById("status-text");
    const connectionStatus = document.getElementById("connection-status");

    if (statusText) statusText.textContent = "Connected";
    if (connectionStatus) {
      connectionStatus.classList.remove("disconnected");
      connectionStatus.classList.add("connected");
      showStatusTemporarily();
    }
    registerSessionRoom();
  });

  socket.on("disconnect", () => {
    const statusText = document.getElementById("status-text");
    const connectionStatus = document.getElementById("connection-status");

    if (statusText) statusText.textContent = "Disconnected";
    if (connectionStatus) {
      connectionStatus.classList.remove("connected");
      connectionStatus.classList.add("disconnected");
      showStatusTemporarily();
    }

    const retryInterval = setInterval(() => {
      if (!socket.connected) {
        socket.connect();
      } else {
        clearInterval(retryInterval);
      }
    }, 3000);
  });

  socket.on("session_registered", (data) => {
    const sid = String(data?.session_id || "").trim();
    if (!sid) return;
    window.session_id = sid;
    localStorage.setItem("session_id", sid);
  });

  if (socket.connected) {
    registerSessionRoom();
  } else {
    setTimeout(registerSessionRoom, 500);
  }

  socket.on("subtitle", (data) => {
    if (data?.speaker !== "user") return;
    const userMessage = document.createElement("div");
    userMessage.className = "user-message";
    userMessage.textContent = String(data.text || "");
    const subtitles = document.getElementById("subtitles");
    subtitles?.appendChild(userMessage);
    subtitles.scrollTop = subtitles?.scrollHeight || 0;
  });

  socket.on("ai_response", async (data) => {
    await window.handleAIResponse(data);
  });

  socket.on("ai_status", (data) => {
    const aiStatusBar = document.getElementById("ai-status-bar");
    if (!aiStatusBar) return;
    aiStatusBar.textContent = String(data?.status || "");
  });
}
