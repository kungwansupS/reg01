"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Mic, MicOff, ArrowLeft, Wifi, WifiOff, Bot, MessageSquare } from "lucide-react";
import { useSocket } from "@/providers/socket-provider";
import { cn } from "@/lib/utils";
import Link from "next/link";

export default function LivePage() {
  const { socket, connected } = useSocket();
  const [micActive, setMicActive] = useState(false);
  const [aiSpeaking, setAiSpeaking] = useState(false);
  const [subtitle, setSubtitle] = useState("");
  const [subtitleHistory, setSubtitleHistory] = useState<string[]>([]);
  const [audioLevel, setAudioLevel] = useState(0);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number>(0);
  const scheduledTimeRef = useRef(0);

  useEffect(() => {
    if (!socket) return;

    socket.on("live_audio_out", (data: { audio: string }) => {
      playAudioChunk(data.audio);
    });
    socket.on("live_speaking", (data: { speaking: boolean }) => {
      setAiSpeaking(data.speaking);
    });
    socket.on("live_text", (data: { text: string }) => {
      const t = data.text || "";
      setSubtitle(t);
      if (t) setSubtitleHistory((prev) => [...prev.slice(-20), t]);
    });
    socket.on("live_turn_complete", () => {
      setAiSpeaking(false);
    });
    socket.on("live_interrupted", () => {
      flushPlayback();
      setAiSpeaking(false);
    });
    socket.on("live_error", (data: { message?: string }) => {
      console.error("Live error:", data.message);
    });

    return () => {
      socket.off("live_audio_out");
      socket.off("live_speaking");
      socket.off("live_text");
      socket.off("live_turn_complete");
      socket.off("live_interrupted");
      socket.off("live_error");
    };
  }, [socket]);

  function flushPlayback() {
    scheduledTimeRef.current = 0;
  }

  function playAudioChunk(base64: string) {
    if (!audioCtxRef.current) {
      audioCtxRef.current = new AudioContext({ sampleRate: 24000 });
    }
    const ctx = audioCtxRef.current;
    const raw = atob(base64);
    const buf = new ArrayBuffer(raw.length);
    const view = new Uint8Array(buf);
    for (let i = 0; i < raw.length; i++) view[i] = raw.charCodeAt(i);

    const int16 = new Int16Array(buf);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 32768;

    const audioBuffer = ctx.createBuffer(1, float32.length, 24000);
    audioBuffer.getChannelData(0).set(float32);

    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(ctx.destination);

    const now = ctx.currentTime;
    const startAt = Math.max(now, scheduledTimeRef.current);
    source.start(startAt);
    scheduledTimeRef.current = startAt + audioBuffer.duration;
  }

  function startAudioLevelMonitor(stream: MediaStream) {
    const ctx = new AudioContext();
    const src = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    src.connect(analyser);
    analyserRef.current = analyser;

    const dataArr = new Uint8Array(analyser.frequencyBinCount);
    function tick() {
      analyser.getByteFrequencyData(dataArr);
      let sum = 0;
      for (let i = 0; i < dataArr.length; i++) sum += dataArr[i];
      const avg = sum / dataArr.length / 255;
      setAudioLevel(avg);
      animFrameRef.current = requestAnimationFrame(tick);
    }
    tick();
  }

  const toggleMic = useCallback(async () => {
    if (!socket || !connected) return;

    if (micActive) {
      socket.emit("live_stop");
      if (processorRef.current) {
        processorRef.current.disconnect();
        processorRef.current = null;
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
      cancelAnimationFrame(animFrameRef.current);
      setMicActive(false);
      setSubtitle("");
      setAudioLevel(0);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { sampleRate: 16000, channelCount: 1 } });
      streamRef.current = stream;
      startAudioLevelMonitor(stream);

      const ctx = new AudioContext({ sampleRate: 16000 });
      const source = ctx.createMediaStreamSource(stream);
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        const input = e.inputBuffer.getChannelData(0);
        const int16 = new Int16Array(input.length);
        for (let i = 0; i < input.length; i++) {
          int16[i] = Math.max(-32768, Math.min(32767, Math.round(input[i] * 32768)));
        }
        const base64 = btoa(String.fromCharCode(...new Uint8Array(int16.buffer)));
        socket.emit("live_audio_in", { audio: base64 });
      };

      source.connect(processor);
      processor.connect(ctx.destination);

      socket.emit("live_start");
      setMicActive(true);
      scheduledTimeRef.current = 0;
    } catch (err) {
      console.error("Mic access error:", err);
    }
  }, [socket, connected, micActive]);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "m" || e.key === "M") {
        if (document.activeElement?.tagName !== "INPUT" && document.activeElement?.tagName !== "TEXTAREA") {
          toggleMic();
        }
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [toggleMic]);

  const bars = 5;
  const barHeights = Array.from({ length: bars }, (_, i) => {
    const base = micActive ? audioLevel : aiSpeaking ? 0.3 + Math.random() * 0.3 : 0;
    const variation = Math.sin(Date.now() / 200 + i * 1.5) * 0.2;
    return Math.max(4, Math.min(40, (base + variation) * 50));
  });

  return (
    <div className="flex flex-col h-screen bg-yt-bg text-yt-text select-none">
      {/* ─── Top Bar ─── */}
      <header className="flex items-center justify-between px-4 h-14 border-b border-yt-border shrink-0 z-10">
        <div className="flex items-center gap-3">
          <Link href="/" className="yt-btn-icon">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-danger animate-pulse" />
            <span className="text-sm font-semibold">LIVE</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className={cn(
            "flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium",
            connected ? "bg-success/10 text-success" : "bg-danger/10 text-danger"
          )}>
            {connected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
            {connected ? "Connected" : "Offline"}
          </div>
          <Link href="/" className="yt-btn-icon" title="Chat Mode">
            <MessageSquare className="w-5 h-5" />
          </Link>
        </div>
      </header>

      {/* ─── Main Content ─── */}
      <div className="flex-1 flex flex-col items-center justify-center relative overflow-hidden">
        {/* Background glow */}
        <div className={cn(
          "absolute inset-0 transition-opacity duration-1000",
          (micActive || aiSpeaking) ? "opacity-100" : "opacity-0"
        )}>
          <div className={cn(
            "absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full blur-[120px]",
            aiSpeaking ? "bg-cmu-purple/20" : "bg-accent/10"
          )} />
        </div>

        {/* Avatar Area */}
        <div className="relative z-10 flex flex-col items-center">
          {/* Avatar Circle with Audio Visualizer */}
          <div className="relative">
            <div className={cn(
              "w-48 h-48 sm:w-56 sm:h-56 rounded-full flex items-center justify-center transition-all duration-500",
              aiSpeaking
                ? "bg-gradient-to-br from-cmu-purple/30 to-cmu-purple-light/20 scale-105"
                : micActive
                ? "bg-gradient-to-br from-accent/20 to-accent/5 scale-100"
                : "bg-yt-surface"
            )}>
              {/* Pulse rings */}
              {(micActive || aiSpeaking) && (
                <>
                  <div className={cn(
                    "absolute inset-0 rounded-full border-2 animate-pulse-ring",
                    aiSpeaking ? "border-cmu-purple-light" : "border-accent"
                  )} />
                  <div className={cn(
                    "absolute inset-[-8px] rounded-full border animate-pulse-ring",
                    aiSpeaking ? "border-cmu-purple/50" : "border-accent/30"
                  )} style={{ animationDelay: "0.5s" }} />
                </>
              )}

              <Bot className={cn(
                "w-20 h-20 sm:w-24 sm:h-24 transition-colors duration-300",
                aiSpeaking ? "text-cmu-purple-light" : micActive ? "text-accent" : "text-yt-text-muted"
              )} />
            </div>

            {/* Audio Level Bars */}
            {(micActive || aiSpeaking) && (
              <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 flex items-end gap-1 h-10">
                {barHeights.map((h, i) => (
                  <div
                    key={i}
                    className={cn("audio-bar transition-all duration-100", aiSpeaking ? "bg-cmu-purple-light" : "bg-accent")}
                    style={{ height: `${h}px` }}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Status Text */}
          <div className="mt-12 text-center">
            <p className={cn(
              "text-lg font-semibold transition-colors duration-300",
              aiSpeaking ? "text-cmu-purple-light" : micActive ? "text-accent" : "text-yt-text"
            )}>
              {!connected
                ? "Connecting..."
                : aiSpeaking
                ? "AI กำลังพูด..."
                : micActive
                ? "กำลังฟัง..."
                : "REG CMU AI Live"
              }
            </p>
            <p className="text-xs text-yt-text-muted mt-1">
              {!connected ? "" : micActive ? "พูดได้เลย — AI จะตอบทันที" : "กด M หรือปุ่มด้านล่างเพื่อเริ่ม"}
            </p>
          </div>

          {/* Subtitle */}
          {subtitle && (
            <div className="mt-6 max-w-lg px-6 py-3 rounded-xl bg-yt-surface/80 border border-yt-border backdrop-blur-sm">
              <p className="text-sm text-yt-text leading-relaxed text-center">{subtitle}</p>
            </div>
          )}
        </div>
      </div>

      {/* ─── Bottom Controls ─── */}
      <div className="shrink-0 pb-8 pt-4 flex flex-col items-center gap-4 z-10">
        <button
          onClick={toggleMic}
          disabled={!connected}
          className={cn(
            "w-16 h-16 rounded-full flex items-center justify-center transition-all duration-300 shadow-xl",
            micActive
              ? "bg-danger hover:bg-danger/90 scale-100"
              : "bg-yt-surface-hover hover:bg-yt-surface-active scale-100",
            !connected && "opacity-30 cursor-not-allowed"
          )}
        >
          {micActive
            ? <MicOff className="w-7 h-7 text-white" />
            : <Mic className="w-7 h-7 text-yt-text" />
          }
        </button>
        <p className="text-[11px] text-yt-text-muted">
          {micActive ? "กดเพื่อหยุด" : "กดเพื่อเริ่มสนทนา"}
          <span className="ml-2 opacity-50">[ M ]</span>
        </p>
      </div>
    </div>
  );
}
