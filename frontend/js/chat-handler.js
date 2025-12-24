document.addEventListener("DOMContentLoaded", () => {
  const socket = window.socket;
  const inputBox = document.getElementById("user-input");
  const sendBtn = document.getElementById("send-button");
  const recordBtn = document.getElementById("record-button");
  const toggleButton = document.getElementById("toggle-mode");

  console.log("💡 session_id =", window.session_id);

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

  document.addEventListener("keydown", async (event) => {
    if (window.isTextMode && event.code === "Enter") {
      event.preventDefault();
      sendText(inputBox, socket);
    }
  });
});

async function sendText(inputBox, socket) {
  const text = inputBox.value.trim();
  if (!text) return;

  if (!socket.connected) {
    showPopup("ไม่สามารถส่งข้อความได้: ไม่ได้เชื่อมต่อเซิร์ฟเวอร์");
    return;
  }

  const userMessage = document.createElement("div");
  userMessage.className = "user-message";
  userMessage.textContent = text;
  const subtitles = document.getElementById("subtitles");
  subtitles?.appendChild(userMessage);
  subtitles.scrollTop = subtitles?.scrollHeight || 0;

  inputBox.value = "";

  const form = new FormData();
  const sessionId = window.session_id || localStorage.getItem("session_id") || crypto.randomUUID();
  form.append("text", text);
  form.append("session_id", sessionId);

  // เตรียม Token (จำลองว่าได้มาจากระบบ Login)
  const authToken = localStorage.getItem("auth_token") || "mock-student-id-12345";

  try {
    await fetch(`/api/speech`, {
      method: "POST",
      body: form,
      headers: {
        "X-API-Key": authToken // ส่งกุญแจยืนยันตัวตน
      }
    });
    console.log("📨 ส่งข้อความสำเร็จ");
  } catch (err) {
    console.error("❌ ไม่สามารถส่งข้อความ:", err);
    showPopup("เกิดข้อผิดพลาดขณะส่งข้อความ");
  }
}

function showPopup(message) {
  const popup = document.getElementById("popup-alert");
  if (!popup) return;
  popup.textContent = message;
  popup.classList.add("show");
  setTimeout(() => {
    popup.classList.remove("show");
  }, 3000);
}