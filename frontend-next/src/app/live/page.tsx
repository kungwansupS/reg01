"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Mic, MicOff } from "lucide-react";
import { useSocket } from "@/providers/socket-provider";
import { cn } from "@/lib/utils";

export default function LivePage() {
  const { socket, connected } = useSocket();
  const [micActive, setMicActive] = useState(false);
  const [aiSpeaking, setAiSpeaking] = useState(false);
  const [subtitle, setSubtitle] = useState("");
  const audioCtxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
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
      setSubtitle(data.text || "");
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

  const toggleMic = useCallback(async () => {
    if (!socket || !connected) return;

    if (micActive) {
      // Stop
      socket.emit("live_stop");
      if (processorRef.current) {
        processorRef.current.disconnect();
        processorRef.current = null;
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
      setMicActive(false);
      setSubtitle("");
      return;
    }

    // Start
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
    <div className="flex flex-col items-center justify-center min-h-screen bg-black text-white relative">
      {/* Status indicator */}
      <div className="absolute top-6 right-6">
        <div className={cn(
          "w-3 h-3 rounded-full",
          connected ? "bg-green-500" : "bg-red-500"
        )} />
      </div>

      {/* Subtitle */}
      {subtitle && (
        <div className="absolute top-1/4 px-8 text-center">
          <p className="text-lg text-zinc-300 max-w-lg leading-relaxed">{subtitle}</p>
        </div>
      )}

      {/* Mic toggle button */}
      <button
        onClick={toggleMic}
        disabled={!connected}
        className={cn(
          "w-24 h-24 rounded-full flex items-center justify-center transition-all duration-300 shadow-2xl",
          micActive && aiSpeaking
            ? "bg-cmu-purple scale-110 animate-pulse"
            : micActive
            ? "bg-green-500 scale-105"
            : "bg-zinc-800 hover:bg-zinc-700",
          !connected && "opacity-30 cursor-not-allowed"
        )}
      >
        {micActive ? (
          <MicOff className="w-10 h-10 text-white" />
        ) : (
          <Mic className="w-10 h-10 text-white" />
        )}
      </button>

      <p className="mt-6 text-sm text-zinc-500">
        {!connected
          ? "Connecting..."
          : micActive
          ? aiSpeaking
            ? "AI is speaking..."
            : "Listening..."
          : "Press to start (or M)"}
      </p>
    </div>
  );
}
