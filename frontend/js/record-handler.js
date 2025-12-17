let isRecording = false;
let mediaRecorder;
let chunks = [];
let stopTimeout = null;

const recordButton = document.getElementById("record-button");
const startSound = document.getElementById("start-sound");
const stopSound = document.getElementById("stop-sound");
const waveform = document.getElementById("waveform");

startSound.volume = 0.5;
stopSound.volume = 1.0;

async function startRecording() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  mediaRecorder = new MediaRecorder(stream);
  chunks = [];

  mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
  mediaRecorder.onstop = async () => {
    const blob = new Blob(chunks, { type: "audio/webm" });
    const form = new FormData();
    form.append("audio", blob, "voice.webm");
    form.append("session_id", window.session_id);

    console.log("📤 ส่งเสียงไป /api/speech");

    await fetch(`/api/speech`, {
      method: "POST",
      body: form
    });
  };

  mediaRecorder.start();
  setupWaveformVisualizer(stream);
  waveform.classList.remove("hidden");
  recordButton.classList.add("recording");
  isRecording = true;
  startSound.play();
}

function stopRecording() {
  if (isRecording && mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
    recordButton.classList.remove("recording");
    isRecording = false;
    stopSound.play();

    if (typeof waveformCtx !== "undefined" && waveformCtx) {
      waveformCtx.close();
      waveformCtx = null;
      waveform.classList.add("hidden");
    }
  }
}

function delayedStop() {
  if (stopTimeout) clearTimeout(stopTimeout);
  stopTimeout = setTimeout(() => {
    stopRecording();
  }, 1000);
}

recordButton.addEventListener("mousedown", async () => {
  if (!isRecording) await startRecording();
  if (stopTimeout) clearTimeout(stopTimeout);
});

recordButton.addEventListener("mouseup", () => {
  delayedStop();
});

recordButton.addEventListener("mouseleave", () => {
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
