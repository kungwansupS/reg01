let isRecording = false;
let mediaRecorder;
let chunks = [];
let stopTimeout = null;

const recordButton = document.getElementById("record-button");
const startSound = document.getElementById("start-sound");
const stopSound = document.getElementById("stop-sound");
const waveform = document.getElementById("waveform");

if (startSound) startSound.volume = 0.5;
if (stopSound) stopSound.volume = 1.0;

function syncSessionIdFromSpeechResponse(response) {
  const serverSession = (response.headers.get("x-session-id") || "").trim();
  if (!serverSession) return;
  window.session_id = serverSession;
  localStorage.setItem("session_id", serverSession);
  if (window.socket?.connected) {
    window.socket.emit("client_register_session", { session_id: serverSession });
  }
}

async function submitAudio(blob) {
  const form = new FormData();
  const sessionId = window.session_id || localStorage.getItem("session_id") || crypto.randomUUID();
  window.session_id = sessionId;
  localStorage.setItem("session_id", sessionId);

  form.append("audio", blob, "voice.webm");
  form.append("session_id", sessionId);

  const authToken = localStorage.getItem("auth_token") || "";
  const response = await fetch("/api/speech", {
    method: "POST",
    body: form,
    headers: {
      "X-API-Key": authToken,
    },
  });

  syncSessionIdFromSpeechResponse(response);
  if (!response.ok) {
    throw new Error(`Speech request failed (${response.status})`);
  }

  const payload = await response.json().catch(() => null);
  if (payload?.text) {
    if (typeof window.handleAIResponse === "function") {
      await window.handleAIResponse({
        text: payload.text,
        motion: payload.motion || "Idle",
      });
    } else {
      const aiMessage = document.createElement("div");
      aiMessage.className = "ai-message";
      aiMessage.textContent = payload.text;
      const subtitles = document.getElementById("subtitles");
      subtitles?.appendChild(aiMessage);
      subtitles.scrollTop = subtitles?.scrollHeight || 0;
    }
  }
}

async function startRecording() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  mediaRecorder = new MediaRecorder(stream);
  chunks = [];

  mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
  mediaRecorder.onstop = async () => {
    const blob = new Blob(chunks, { type: "audio/webm" });
    try {
      await submitAudio(blob);
    } catch (err) {
      console.error("Failed to send speech:", err);
    }
  };

  mediaRecorder.start();
  setupWaveformVisualizer(stream);
  waveform?.classList.remove("hidden");
  recordButton?.classList.add("recording");
  isRecording = true;
  startSound?.play();
}

function stopRecording() {
  if (!isRecording || !mediaRecorder || mediaRecorder.state !== "recording") return;

  mediaRecorder.stop();
  recordButton?.classList.remove("recording");
  isRecording = false;
  stopSound?.play();

  if (typeof waveformCtx !== "undefined" && waveformCtx) {
    waveformCtx.close();
    waveformCtx = null;
    waveform?.classList.add("hidden");
  }
}

function delayedStop() {
  if (stopTimeout) clearTimeout(stopTimeout);
  stopTimeout = setTimeout(() => {
    stopRecording();
  }, 1000);
}

recordButton?.addEventListener("mousedown", async () => {
  if (!isRecording) await startRecording();
  if (stopTimeout) clearTimeout(stopTimeout);
});

recordButton?.addEventListener("mouseup", () => {
  delayedStop();
});

recordButton?.addEventListener("mouseleave", () => {
  delayedStop();
});

document.addEventListener("keydown", async (event) => {
  if (window.isTextMode) return;
  if ((event.code === "Space" || event.code === "Enter") && !isRecording) {
    event.preventDefault();
    await startRecording();
  }
  if (stopTimeout) clearTimeout(stopTimeout);
});

document.addEventListener("keyup", (event) => {
  if ((event.code === "Space" || event.code === "Enter") && isRecording) {
    event.preventDefault();
    delayedStop();
  }
});
