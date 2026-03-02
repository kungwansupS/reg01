"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Mic, MicOff, ArrowLeft, Wifi, WifiOff, MessageSquare } from "lucide-react";
import { useSocket } from "@/providers/socket-provider";
import { cn } from "@/lib/utils";
import Link from "next/link";
import dynamic from "next/dynamic";
import type { Live2DHandle } from "@/components/live2d/Live2DCanvas";

const Live2DCanvas = dynamic(() => import("@/components/live2d/Live2DCanvas"), { ssr: false });

const SPEAKING_MOTIONS = ["Tap", "Flick", "Tap@Body"];

export default function LivePage() {
  const { socket, connected } = useSocket();
  const [micActive, setMicActive] = useState(false);
  const [aiSpeaking, setAiSpeaking] = useState(false);
  const [subtitle, setSubtitle] = useState("");
  const audioCtxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const monitorCtxRef = useRef<AudioContext | null>(null);
  const animFrameRef = useRef<number>(0);
  const scheduledTimeRef = useRef(0);
  const live2dRef = useRef<Live2DHandle>(null);
  const mouthOpenRef = useRef(0);
  const currentTurnIdRef = useRef<string>("");
  const eosSentAtMsRef = useRef<number>(0);
  const firstAudioOutAtMsRef = useRef<number>(0);
  const interruptionSentAtMsRef = useRef<number>(0);

  // Socket.IO event handlers
  useEffect(() => {
    if (!socket) return;

    socket.on("live_audio_out", (data: { audio: string }) => {
      if (!firstAudioOutAtMsRef.current) {
        firstAudioOutAtMsRef.current = performance.now();
        if (eosSentAtMsRef.current > 0) {
          const latencyMs = firstAudioOutAtMsRef.current - eosSentAtMsRef.current;
          socket.emit("live_client_metric", {
            turn_id: currentTurnIdRef.current,
            metric: "eos_to_first_audio_ms",
            value: Math.round(latencyMs * 100) / 100,
            client_ts_ms: Date.now(),
          });
        }
      }
      playAudioChunk(data.audio);
    });
    socket.on("live_speaking", (data: { speaking: boolean }) => {
      setAiSpeaking(data.speaking);
      live2dRef.current?.setSpeaking(data.speaking);
    });
    socket.on("live_text", (data: { text: string }) => {
      setSubtitle(data.text || "");
    });
    socket.on("live_turn_complete", (data: { turn_id?: string }) => {
      setAiSpeaking(false);
      live2dRef.current?.setSpeaking(false);
      if (data?.turn_id) currentTurnIdRef.current = data.turn_id;
    });
    socket.on("live_interrupted", () => {
      flushPlayback();
      setAiSpeaking(false);
      live2dRef.current?.setSpeaking(false);
      if (interruptionSentAtMsRef.current > 0) {
        const reactionMs = performance.now() - interruptionSentAtMsRef.current;
        socket.emit("live_client_metric", {
          turn_id: currentTurnIdRef.current,
          metric: "interruption_reaction_ms",
          value: Math.round(reactionMs * 100) / 100,
          client_ts_ms: Date.now(),
        });
        interruptionSentAtMsRef.current = 0;
      }
    });
    socket.on("live_metrics", (data: { metric?: string; value?: number; source?: string }) => {
      console.debug("live_metrics", data);
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
      socket.off("live_metrics");
    };
  }, [socket]);

  function flushPlayback() {
    scheduledTimeRef.current = 0;
    mouthOpenRef.current = 0;
    live2dRef.current?.setLipSyncValue(0);
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

    // Compute volume from PCM for lip sync
    let sum = 0;
    for (let i = 0; i < float32.length; i++) sum += float32[i] * float32[i];
    const volume = Math.sqrt(sum / float32.length);
    const target = Math.min(volume * 5, 1);
    mouthOpenRef.current += (target - mouthOpenRef.current) * 0.4;
    live2dRef.current?.setLipSyncValue(mouthOpenRef.current);

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

  const toggleMic = useCallback(async () => {
    if (!socket || !connected) return;

    if (micActive) {
      eosSentAtMsRef.current = performance.now();
      firstAudioOutAtMsRef.current = 0;
      socket.emit("live_stop");
      if (processorRef.current) {
        processorRef.current.disconnect();
        processorRef.current = null;
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
      if (monitorCtxRef.current) {
        monitorCtxRef.current.close().catch(() => {});
        monitorCtxRef.current = null;
      }
      cancelAnimationFrame(animFrameRef.current);
      setMicActive(false);
      setSubtitle("");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { sampleRate: 16000, channelCount: 1 } });
      streamRef.current = stream;

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
        if (aiSpeaking && interruptionSentAtMsRef.current === 0) {
          interruptionSentAtMsRef.current = performance.now();
        }
        socket.emit("live_audio_in", { audio: base64 });
      };

      source.connect(processor);
      processor.connect(ctx.destination);

      socket.emit("live_start");
      setMicActive(true);
      scheduledTimeRef.current = 0;
      eosSentAtMsRef.current = 0;
      firstAudioOutAtMsRef.current = 0;
      interruptionSentAtMsRef.current = 0;
      currentTurnIdRef.current = "";
    } catch (err) {
      console.error("Mic access error:", err);
    }
  }, [socket, connected, micActive, aiSpeaking]);

  // Keyboard shortcut: M to toggle mic
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

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-black select-none">
      {/* Live2D Model (fullscreen background) */}
      <div className="absolute inset-0 z-0">
        <Live2DCanvas ref={live2dRef} className="w-full h-full" />
      </div>

      {/* Background glow effect */}
      <div
        className={cn(
          "absolute inset-0 z-[1] pointer-events-none transition-opacity duration-1000",
          micActive || aiSpeaking ? "opacity-100" : "opacity-0",
        )}
      >
        <div
          className={cn(
            "absolute bottom-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] rounded-full blur-[150px]",
            aiSpeaking ? "bg-cmu-purple/15" : "bg-accent/10",
          )}
        />
      </div>

      {/* Top Bar (overlay) */}
      <header className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between px-4 h-14">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="w-9 h-9 rounded-full bg-black/40 backdrop-blur-sm flex items-center justify-center hover:bg-black/60 transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-white" />
          </Link>
          <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-black/40 backdrop-blur-sm">
            <div className="w-2 h-2 rounded-full bg-danger animate-pulse" />
            <span className="text-sm font-semibold text-white">LIVE</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div
            className={cn(
              "flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium backdrop-blur-sm",
              connected ? "bg-success/20 text-success" : "bg-danger/20 text-danger",
            )}
          >
            {connected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
            {connected ? "Connected" : "Offline"}
          </div>
          <Link
            href="/"
            className="w-9 h-9 rounded-full bg-black/40 backdrop-blur-sm flex items-center justify-center hover:bg-black/60 transition-colors"
            title="Chat Mode"
          >
            <MessageSquare className="w-4 h-4 text-white" />
          </Link>
        </div>
      </header>

      {/* Subtitle + Status (bottom overlay) */}
      <div className="absolute bottom-28 left-0 right-0 z-10 flex flex-col items-center gap-3 px-4">
        {/* Status text */}
        <p
          className={cn(
            "text-sm font-medium transition-colors duration-300",
            aiSpeaking ? "text-cmu-purple-light" : micActive ? "text-accent" : "text-white/70",
          )}
        >
          {!connected
            ? "Connecting..."
            : aiSpeaking
              ? "AI กำลังพูด..."
              : micActive
                ? "กำลังฟัง..."
                : "กด M หรือปุ่มด้านล่างเพื่อเริ่ม"}
        </p>

        {/* Subtitle */}
        {subtitle && (
          <div className="max-w-lg px-5 py-2.5 rounded-xl bg-black/60 backdrop-blur-md border border-white/10">
            <p className="text-sm text-white leading-relaxed text-center">{subtitle}</p>
          </div>
        )}
      </div>

      {/* Bottom Controls */}
      <div className="absolute bottom-6 left-0 right-0 z-10 flex flex-col items-center gap-3">
        <button
          onClick={toggleMic}
          disabled={!connected}
          className={cn(
            "w-16 h-16 rounded-full flex items-center justify-center transition-all duration-300 shadow-2xl",
            micActive
              ? "bg-danger hover:bg-danger/90 ring-4 ring-danger/30"
              : "bg-white/10 backdrop-blur-sm hover:bg-white/20 ring-2 ring-white/20",
            !connected && "opacity-30 cursor-not-allowed",
          )}
        >
          {micActive ? <MicOff className="w-7 h-7 text-white" /> : <Mic className="w-7 h-7 text-white" />}
        </button>
        <p className="text-[11px] text-white/50">
          {micActive ? "กดเพื่อหยุด" : "กดเพื่อเริ่มสนทนา"}
          <span className="ml-2 opacity-50">[ M ]</span>
        </p>
      </div>
    </div>
  );
}
