document.addEventListener("DOMContentLoaded", () => {
  const socket = window.socket;
  const inputBox = document.getElementById("user-input");
  const sendBtn = document.getElementById("send-button");
  const recordBtn = document.getElementById("record-button");
  const toggleButton = document.getElementById("toggle-mode");

  if (!localStorage.getItem("auth_token")) {
    localStorage.setItem("auth_token", `dev-token-${Math.random().toString(36).slice(2, 11)}`);
  }

  window.isTextMode = false;

  function updateModeUI() {
    if (window.isTextMode) {
      inputBox.classList.remove("hidden");
      sendBtn.classList.remove("hidden");
      recordBtn.classList.add("hidden");
    } else {
      inputBox.classList.add("hidden");
      sendBtn.classList.add("hidden");
      recordBtn.classList.remove("hidden");
    }
  }

  toggleButton.addEventListener("click", () => {
    window.isTextMode = !window.isTextMode;
    updateModeUI();
  });

  updateModeUI();

  sendBtn.addEventListener("click", () => {
    sendText(inputBox, socket);
  });

  document.addEventListener("keydown", (event) => {
    if (window.isTextMode && event.code === "Enter") {
      event.preventDefault();
      sendText(inputBox, socket);
    }
  });
});

function syncSessionIdFromResponse(response, socket) {
  const serverSession = (response.headers.get("x-session-id") || "").trim();
  if (!serverSession) return;
  window.session_id = serverSession;
  localStorage.setItem("session_id", serverSession);
  if (socket?.connected) {
    socket.emit("client_register_session", { session_id: serverSession });
  }
}

async function sendText(inputBox, socket) {
  const text = inputBox.value.trim();
  if (!text) return;
  if (typeof window.setAIStatus === "function") {
    window.setAIStatus("Sending request...", { timeoutMs: 15000 });
  }

  if (!socket?.connected) {
    showPopup("Socket disconnected, using direct API mode.");
  }

  const userMessage = document.createElement("div");
  userMessage.className = "user-message";
  userMessage.textContent = text;
  const subtitles = document.getElementById("subtitles");
  subtitles?.appendChild(userMessage);
  subtitles.scrollTop = subtitles?.scrollHeight || 0;

  inputBox.value = "";

  const sessionId = window.session_id || localStorage.getItem("session_id") || crypto.randomUUID();
  window.session_id = sessionId;
  localStorage.setItem("session_id", sessionId);

  const form = new FormData();
  form.append("text", text);
  form.append("session_id", sessionId);

  const authToken = localStorage.getItem("auth_token") || "";

  try {
    const response = await fetch("/api/speech", {
      method: "POST",
      body: form,
      headers: {
        "X-API-Key": authToken,
      },
    });
    syncSessionIdFromResponse(response, socket);

    if (!response.ok) {
      if (typeof window.clearAIStatus === "function") window.clearAIStatus();
      showPopup(`Request failed (${response.status})`);
      return;
    }

    const payload = await response.json().catch(() => null);
    if (payload?.text) {
      if (typeof window.handleAIResponse === "function") {
        await window.handleAIResponse({
          text: payload.text,
          tts_text: payload.tts_text || payload.text,
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
    if (typeof window.clearAIStatus === "function") window.clearAIStatus();
  } catch (err) {
    console.error("Network Error:", err);
    if (typeof window.clearAIStatus === "function") window.clearAIStatus();
    showPopup("Network error while sending message.");
  }
}

function showPopup(message) {
  const popup = document.getElementById("popup-alert");
  if (!popup) return;
  popup.textContent = message;
  popup.classList.remove("hidden");
  popup.classList.add("show");
  setTimeout(() => {
    popup.classList.remove("show");
    popup.classList.add("hidden");
  }, 3000);
}
