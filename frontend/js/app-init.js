let session_id = localStorage.getItem("session_id");
if (!session_id) {
  session_id = crypto.randomUUID();
  localStorage.setItem("session_id", session_id);
}
window.session_id = session_id;

window.socket = io();

socket.on("connect", () => console.log("✅ Socket connected"));
socket.on("disconnect", () => console.log("❌ Socket disconnected"));

document.addEventListener("DOMContentLoaded", () => {
  const startSound = document.getElementById("start-sound");
  const stopSound = document.getElementById("stop-sound");
  if (startSound) startSound.volume = 0.5;
  if (stopSound) stopSound.volume = 1.0;
});
