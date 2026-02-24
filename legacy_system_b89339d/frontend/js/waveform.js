let waveformCtx;
let waveformAnalyser;
let waveformCanvasCtx;

function setupWaveformVisualizer(stream) {
  waveformCtx = new (window.AudioContext || window.webkitAudioContext)();
  waveformAnalyser = waveformCtx.createAnalyser();
  const source = waveformCtx.createMediaStreamSource(stream);
  source.connect(waveformAnalyser);
  waveformAnalyser.fftSize = 256;

  const waveform = document.getElementById("waveform");
  if (!waveform) return;
  waveformCanvasCtx = waveform.getContext("2d");

  drawWaveform();
}

function drawWaveform() {
  if (!waveformCanvasCtx) return;
  requestAnimationFrame(drawWaveform);

  const bufferLength = waveformAnalyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);
  waveformAnalyser.getByteFrequencyData(dataArray);

  const waveform = document.getElementById("waveform");
  const width = waveform.width;
  const height = waveform.height;

  waveformCanvasCtx.clearRect(0, 0, width, height);
  waveformCanvasCtx.fillStyle = "#2a2a2a";
  waveformCanvasCtx.fillRect(0, 0, width, height);

  const barWidth = width / bufferLength;
  let x = 0;

  for (let i = 0; i < bufferLength; i++) {
    const barHeight = (dataArray[i] / 255) * height;
    waveformCanvasCtx.fillStyle = "#ff80ab";
    waveformCanvasCtx.fillRect(x, height - barHeight, barWidth, barHeight);
    x += barWidth + 1;
  }
}
