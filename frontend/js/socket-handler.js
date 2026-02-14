const socket = window.socket;

// stop ai reponse
let currentAIResponseAudio = null; // เพิ่มตัวแปรนี้ไว้ด้านบน
let currentMediaSource = null; // เพิ่มตัวแปรนี้
let stopped = false; // ย้ายออกมาเป็น global ถ้าต้องการ

const skipBtn = document.getElementById("skip-ai-response");

if (skipBtn) {
  skipBtn.addEventListener("click", () => {
    console.log("[DEBUG] skip-ai-response CLICKED");
    stopped = true;
    if (currentAIResponseAudio) {
      console.log("[DEBUG] currentAIResponseAudio exists, pausing and clearing src");
      currentAIResponseAudio.pause();
      currentAIResponseAudio.currentTime = 0;
      currentAIResponseAudio.src = ""; // ล้างแหล่งที่มาของเสียง
      currentAIResponseAudio = null;
    } else {
      console.log("[DEBUG] currentAIResponseAudio is null");
    }
    if (currentMediaSource) {
      try {
        console.log("[DEBUG] currentMediaSource exists, readyState =", currentMediaSource.readyState);
        if (currentMediaSource.readyState === "open") {
          console.log("[DEBUG] currentMediaSource exists, calling endOfStream()");
          currentMediaSource.endOfStream();
        } else {
          console.log("[DEBUG] currentMediaSource is not open, readyState =", currentMediaSource.readyState);
        }
      } catch (e) {
        console.log("[DEBUG] Error in endOfStream:", e);
      }
      currentMediaSource = null;
    } else {
      console.log("[DEBUG] currentMediaSource is null");
    }
    skipBtn.classList.add("hidden");
  });
}

function registerSessionRoom() {
  const sid = (window.session_id || localStorage.getItem("session_id") || "").trim();
  if (!sid || !socket?.connected) return;
  socket.emit("client_register_session", { session_id: sid });
}

socket.on("connect", () => {
  console.log("✅ Socket.IO connected");
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
  console.log("❌ Socket.IO disconnected");
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

function showStatusTemporarily() {
  const connectionStatus = document.getElementById("connection-status");
  connectionStatus?.classList.add("show");
  setTimeout(() => {
    connectionStatus?.classList.remove("show");
  }, 3000);
}

socket.on("session_registered", (data) => {
  const sid = String(data?.session_id || "").trim();
  if (!sid) return;
  window.session_id = sid;
  localStorage.setItem("session_id", sid);
});

socket.on("subtitle", (data) => {
  if (data.speaker === "user") {
    const userMessage = document.createElement("div");
    userMessage.className = "user-message";
    userMessage.textContent = data.text;
    const subtitles = document.getElementById("subtitles");
    subtitles?.appendChild(userMessage);
    subtitles.scrollTop = subtitles?.scrollHeight || 0;
  }
});

socket.on("ai_response", async (data) => {
  console.log("🤖 AI ตอบกลับ:", data.text);

  if (!data.text || data.text.trim() === "") {
    const aiStatusBar = document.getElementById("ai-status-bar");
    if (aiStatusBar) aiStatusBar.textContent = "❌ ไม่สามารถตอบกลับได้";
    return;
  }

  const aiMessage = document.createElement("div");
  aiMessage.className = "ai-message";
  aiMessage.textContent = data.text;
  const subtitles = document.getElementById("subtitles");
  subtitles?.appendChild(aiMessage);
  subtitles.scrollTop = subtitles?.scrollHeight || 0;

  if (data.motion && typeof playMotion === "function") {
    playMotion(data.motion);
  }

  const form = new FormData();
  form.append("text", data.text);

  const response = await fetch("/api/speak", {
    method: "POST",
    body: form
  });

  const mediaSource = new MediaSource();
  currentMediaSource = mediaSource;
  stopped = false; // reset flag ทุกครั้งที่มีเสียงใหม่

  const audio = new Audio();
  audio.src = URL.createObjectURL(mediaSource);
  currentAIResponseAudio = audio; // เก็บไว้เพื่อให้สามารถหยุดได้
  audio.play();

  // แสดงปุ่ม skip
  if (skipBtn) skipBtn.classList.remove("hidden");
  audio.addEventListener("ended", () => {
    if (skipBtn) skipBtn.classList.add("hidden");
    currentAIResponseAudio = null;
    currentMediaSource = null;
  });
  mediaSource.addEventListener("sourceopen", () => {
    const sourceBuffer = mediaSource.addSourceBuffer("audio/mpeg");
    const reader = response.body.getReader();
    let queue = [];
    let updating = false;

    sourceBuffer.addEventListener("updateend", () => {
      updating = false;
      if (queue.length > 0 && !sourceBuffer.updating) {
        sourceBuffer.appendBuffer(queue.shift());
      }
    });

    function pump() {
      if (stopped) {
        console.log("[DEBUG] pump stopped by skip");
        return;
      }
      reader.read().then(({ done, value }) => {
        if (stopped) {
          console.log("[DEBUG] pump stopped by skip (after read)");
          return;
        }
        if (done) {
          if (!sourceBuffer.updating && queue.length === 0) {
            try { mediaSource.endOfStream(); } catch (e) {}
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
});

socket.on("ai_status", (data) => {
  const aiStatusBar = document.getElementById("ai-status-bar");
  const statusText = data.status || "";

  if (!aiStatusBar) return;

  if (statusText.includes("กำลัง")) {
    const cleanText = statusText.replace(/\.\.\.$/, "");
    aiStatusBar.innerHTML = cleanText +
      '<span class="dot-anim">.</span>' +
      '<span class="dot-anim">.</span>' +
      '<span class="dot-anim">.</span>';
  } else {
    aiStatusBar.innerHTML = statusText;
  }
});
