let session_id = localStorage.getItem("session_id");
if (!session_id) {
  session_id = crypto.randomUUID();
  localStorage.setItem("session_id", session_id);
}
window.session_id = session_id;

const host = String(window.location.hostname || "").toLowerCase();
const port = String(window.location.port || "");
const preferLocalBackend = (host === "localhost" || host === "127.0.0.1") && port !== "5000";
const socketOptions = { transports: ["websocket", "polling"] };

// Keep backward compatibility with backup behavior when frontend is not served from :5000.
window.socket = preferLocalBackend ? io("http://localhost:5000", socketOptions) : io(socketOptions);

if (window.socket) {
  socket.on("connect", () => console.log("✅ Socket connected"));
  socket.on("disconnect", () => console.log("❌ Socket disconnected"));
}

document.addEventListener("DOMContentLoaded", () => {
  const startSound = document.getElementById("start-sound");
  const stopSound = document.getElementById("stop-sound");
  if (startSound) startSound.volume = 0.5;
  if (stopSound) stopSound.volume = 1.0;
});
