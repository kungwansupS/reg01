const socket = window.socket || null;

let currentAIResponseAudio = null;
let currentMediaSource = null;
let stopped = false;
let lastAIKey = "";
let lastAIAt = 0;
let statusTimer = null;
let browserTtsVoice = null;

const skipBtn = document.getElementById("skip-ai-response");
const aiStatusBar = document.getElementById("ai-status-bar");

function setAIStatus(text, { timeoutMs = 12000 } = {}) {
  if (!aiStatusBar) return;
  const value = String(text || "").trim();
  if (!value) {
    aiStatusBar.textContent = "";
    aiStatusBar.classList.add("hidden");
    if (statusTimer) {
      clearTimeout(statusTimer);
      statusTimer = null;
    }
    return;
  }
  aiStatusBar.textContent = value;
  aiStatusBar.classList.remove("hidden");
  if (statusTimer) clearTimeout(statusTimer);
  statusTimer = setTimeout(() => {
    aiStatusBar.textContent = "";
    aiStatusBar.classList.add("hidden");
    statusTimer = null;
  }, Math.max(3000, timeoutMs));
}

window.setAIStatus = setAIStatus;
window.clearAIStatus = () => setAIStatus("");

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

  if (response.status === 204) return false;
  const contentType = String(response.headers.get("content-type") || "").toLowerCase();
  if (!response.ok || !response.body || !contentType.includes("audio/")) return false;

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
  return true;
}

function detectSpeechLang(text) {
  const value = String(text || "");
  if (/[ก-๙]/.test(value)) return "th-TH";
  if (/[\u3040-\u30ff\u31f0-\u31ff]/.test(value)) return "ja-JP";
  if (/[\u4e00-\u9fff]/.test(value)) return "zh-CN";
  return "en-US";
}

function getBrowserVoice(lang) {
  const synth = window.speechSynthesis;
  if (!synth) return null;
  const voices = synth.getVoices();
  if (!voices || voices.length === 0) return null;
  if (browserTtsVoice && browserTtsVoice.lang === lang) return browserTtsVoice;
  browserTtsVoice = voices.find((v) => String(v.lang || "").toLowerCase().startsWith(lang.toLowerCase().slice(0, 2))) || null;
  return browserTtsVoice;
}

async function browserSpeakFallback(text) {
  const synth = window.speechSynthesis;
  if (!synth || typeof SpeechSynthesisUtterance === "undefined") return false;
  const cleanText = String(text || "").replace(/^\[Bot[^\]]*\]\s*/i, "").replace(/\/\//g, " ").trim();
  if (!cleanText) return false;

  const lang = detectSpeechLang(cleanText);
  return new Promise((resolve) => {
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = lang;
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;
    const voice = getBrowserVoice(lang);
    if (voice) utterance.voice = voice;
    utterance.onend = () => resolve(true);
    utterance.onerror = () => resolve(false);
    try {
      synth.cancel();
      synth.speak(utterance);
    } catch (_) {
      resolve(false);
    }
  });
}

window.handleAIResponse = async function handleAIResponse(data) {
  if (!data || dedupeAIMessage(data)) return;

  const text = String(data.text || "").trim();
  const ttsText = String(data.tts_text || data.text || "").trim();
  if (!text) {
    setAIStatus("No response text.", { timeoutMs: 3500 });
    return;
  }
  setAIStatus("");

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
    const ok = await streamTtsAudio(ttsText);
    if (!ok) {
      const usedBrowserTts = await browserSpeakFallback(ttsText);
      if (usedBrowserTts) {
        setAIStatus("Using local browser voice.", { timeoutMs: 2500 });
      } else {
        setAIStatus("TTS unavailable.", { timeoutMs: 3500 });
      }
    }
  } catch (err) {
    console.error("TTS stream error:", err);
    const usedBrowserTts = await browserSpeakFallback(ttsText);
    if (usedBrowserTts) {
      setAIStatus("Using local browser voice.", { timeoutMs: 2500 });
    } else {
      setAIStatus("TTS stream unavailable.", { timeoutMs: 3500 });
    }
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
    setAIStatus(String(data?.status || ""));
  });

  socket.on("queue_position", (data) => {
    if (!data) return;
    const pos = parseInt(data.position, 10);
    const status = String(data.status || "").trim();

    if (status === "processing" || pos === 0) {
      setAIStatus("กำลังประมวลผล...", { timeoutMs: 30000 });
    } else if (pos > 0) {
      const wait = data.estimated_wait || pos * 5;
      setAIStatus(
        `กำลังรอคิว ลำดับที่ ${pos} (ประมาณ ${wait} วินาที)`,
        { timeoutMs: 120000 }
      );
    }
  });
}
