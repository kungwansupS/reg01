"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import {
  Send, Mic, MicOff, SkipForward, Keyboard, Radio,
  Bot, Settings, Wifi, WifiOff, Volume2, VolumeX,
} from "lucide-react";
import { useSocket } from "@/providers/socket-provider";
import { ChatMessages, type ChatMessage } from "@/components/chat/chat-messages";
import { useTts } from "@/hooks/use-tts";
import { useRecorder } from "@/hooks/use-recorder";
import { sendSpeech, sendSpeechAudio } from "@/lib/api";
import { cn } from "@/lib/utils";
import Link from "next/link";
import dynamic from "next/dynamic";
import type { Live2DHandle } from "@/components/live2d/Live2DCanvas";

const Live2DCanvas = dynamic(() => import("@/components/live2d/Live2DCanvas"), { ssr: false });

export default function ChatPage() {
  const { socket, connected } = useSocket();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [statusText, setStatusText] = useState("");
  const [inputMode, setInputMode] = useState<"text" | "voice">("text");
  const [isSending, setIsSending] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);
  const { speak, browserSpeak, stop: stopTts } = useTts();

  const addMessage = useCallback((role: "user" | "ai", text: string) => {
    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role, text, timestamp: Date.now() }]);
  }, []);

  const handleAIResponse = useCallback(
    async (data: { text?: string; tts_text?: string; motion?: string }) => {
      const text = (data.text || "").trim();
      if (!text) return;
      setStatusText("");
      addMessage("ai", text);

      if (!ttsEnabled) return;
      const ttsText = data.tts_text || text;
      try {
        const ok = await speak(ttsText);
        if (!ok) {
          const used = await browserSpeak(ttsText);
          if (!used) {
            setStatusText("TTS unavailable");
            setTimeout(() => setStatusText(""), 3000);
          }
        }
      } catch {
        await browserSpeak(ttsText);
      }
    },
    [addMessage, speak, browserSpeak, ttsEnabled]
  );

  const registeredRef = useRef(false);
  useEffect(() => {
    if (!socket || registeredRef.current) return;
    registeredRef.current = true;

    socket.on("ai_response", (data) => handleAIResponse(data));
    socket.on("ai_status", (data) => setStatusText(data?.status || ""));
    socket.on("queue_position", (data) => {
      if (!data) return;
      const pos = parseInt(data.position, 10);
      const status = (data.status || "").trim();
      if (status === "processing" || pos === 0) {
        setStatusText("กำลังประมวลผล...");
      } else if (pos > 0) {
        const wait = data.estimated_wait || pos * 5;
        setStatusText(`คิวที่ ${pos} (≈${wait}s)`);
      }
    });
    socket.on("subtitle", (data) => {
      if (data?.speaker === "user") addMessage("user", data.text || "");
    });

    return () => {
      socket.off("ai_response");
      socket.off("ai_status");
      socket.off("queue_position");
      socket.off("subtitle");
      registeredRef.current = false;
    };
  }, [socket, handleAIResponse, addMessage]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isSending) return;
    addMessage("user", text);
    setInput("");
    setIsSending(true);
    setStatusText("กำลังส่ง...");
    try {
      const payload = await sendSpeech(text);
      if (payload?.queue_error) {
        setStatusText("");
        addMessage("ai", payload.text || "ระบบมีผู้ใช้จำนวนมาก กรุณาลองใหม่");
        return;
      }
      // Don't call handleAIResponse here — the backend emits ai_response via socket
      // which is handled by the socket listener. Processing both causes duplicate messages.
      setStatusText("");
    } catch {
      setStatusText("");
      addMessage("ai", "เกิดข้อผิดพลาดในการเชื่อมต่อ");
    } finally {
      setIsSending(false);
    }
  }, [input, isSending, addMessage]);

  const handleRecordResult = useCallback(
    async (blob: Blob) => {
      setStatusText("กำลังประมวลผลเสียง...");
      try {
        await sendSpeechAudio(blob);
        // Socket ai_response event will deliver the reply
        setStatusText("");
      } catch {
        setStatusText("ไม่สามารถประมวลผลเสียงได้");
        setTimeout(() => setStatusText(""), 3000);
      }
    },
    []
  );

  const { recording, start: startRec, stop: stopRec } = useRecorder(handleRecordResult);

  return (
    <div className="flex flex-col h-screen bg-yt-bg text-yt-text">
      {/* ─── Top Bar ─── */}
      <header className="flex items-center justify-between px-4 h-14 border-b border-yt-border shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full gradient-cmu flex items-center justify-center">
            <Bot className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold gradient-text-cmu leading-tight">REG CMU AI</h1>
            <p className="text-[10px] text-yt-text-muted">Assistant</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className={cn(
            "flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium",
            connected ? "bg-success/10 text-success" : "bg-danger/10 text-danger"
          )}>
            {connected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
            {connected ? "Online" : "Offline"}
          </div>
          <Link href="/live" className="yt-btn-icon" title="Live Mode">
            <Radio className="w-5 h-5" />
          </Link>
          <Link href="/admin" className="yt-btn-icon" title="Admin">
            <Settings className="w-5 h-5" />
          </Link>
        </div>
      </header>

      {/* ─── Main Content: Avatar Area + Chat ─── */}
      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
        {/* Avatar / Visual Area (left on desktop, top on mobile) */}
        <div className="hidden lg:flex lg:w-[420px] lg:shrink-0 flex-col items-center justify-end border-r border-yt-border bg-black relative overflow-hidden">
          {/* Live2D Model */}
          <div className="absolute inset-0">
            <Live2DCanvas className="w-full h-full" />
          </div>

          {/* Overlay info at bottom */}
          <div className="relative z-10 text-center pb-6">
            <h2 className="text-lg font-semibold text-white drop-shadow-lg">REG CMU AI</h2>
            <p className="text-sm text-white/60 mt-1">ผู้ช่วยระบบลงทะเบียน</p>

            {statusText && (
              <div className="mt-3 px-4 py-2 rounded-lg bg-accent/20 backdrop-blur-sm text-accent text-xs animate-pulse">
                {statusText}
              </div>
            )}
          </div>
        </div>

        {/* Chat Area (right on desktop, full on mobile) */}
        <div className="flex-1 flex flex-col min-w-0">
          <ChatMessages messages={messages} statusText={statusText} />

          {/* ─── Input Area ─── */}
          <div className="border-t border-yt-border p-3 shrink-0">
            <div className="flex items-center gap-2 max-w-3xl mx-auto">
              {/* Mode toggle */}
              <button
                onClick={() => setInputMode(inputMode === "text" ? "voice" : "text")}
                className={cn("yt-btn-icon shrink-0", inputMode === "voice" && "text-accent")}
                title={inputMode === "text" ? "สลับเป็นโหมดเสียง" : "สลับเป็นโหมดพิมพ์"}
              >
                {inputMode === "text" ? <Mic className="w-5 h-5" /> : <Keyboard className="w-5 h-5" />}
              </button>

              {inputMode === "text" ? (
                <>
                  <input
                    ref={inputRef}
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSend()}
                    placeholder="พิมพ์ข้อความ..."
                    className="flex-1 yt-input rounded-full px-4 py-2.5 text-sm"
                    disabled={isSending}
                  />
                  <button
                    onClick={handleSend}
                    disabled={isSending || !input.trim()}
                    className={cn(
                      "yt-btn yt-btn-primary rounded-full px-4",
                      (isSending || !input.trim()) && "opacity-40 cursor-not-allowed"
                    )}
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </>
              ) : (
                <button
                  onClick={recording ? stopRec : startRec}
                  className={cn(
                    "flex-1 py-3 rounded-full font-medium text-sm transition-all flex items-center justify-center gap-2",
                    recording
                      ? "bg-danger/15 text-danger border border-danger/30 animate-pulse"
                      : "bg-yt-surface-hover hover:bg-yt-surface-active text-yt-text"
                  )}
                >
                  {recording ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                  {recording ? "หยุดบันทึกเสียง" : "กดเพื่อพูด"}
                </button>
              )}

              {/* TTS toggle */}
              <button
                onClick={() => { setTtsEnabled(!ttsEnabled); if (ttsEnabled) stopTts(); }}
                className={cn("yt-btn-icon shrink-0", !ttsEnabled && "text-yt-text-muted")}
                title={ttsEnabled ? "ปิดเสียงตอบ" : "เปิดเสียงตอบ"}
              >
                {ttsEnabled ? <Volume2 className="w-5 h-5" /> : <VolumeX className="w-5 h-5" />}
              </button>

              {/* Skip TTS */}
              <button onClick={stopTts} className="yt-btn-icon shrink-0" title="ข้ามเสียง">
                <SkipForward className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
