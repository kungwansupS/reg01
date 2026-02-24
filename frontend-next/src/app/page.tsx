"use client";

import { useState, useCallback, useRef } from "react";
import { Send, Mic, MicOff, SkipForward, MessageSquare } from "lucide-react";
import { useSocket } from "@/providers/socket-provider";
import { ConnectionStatus } from "@/components/chat/connection-status";
import { ChatMessages, type ChatMessage } from "@/components/chat/chat-messages";
import { useTts } from "@/hooks/use-tts";
import { useRecorder } from "@/hooks/use-recorder";
import { sendSpeech } from "@/lib/api";
import { getSessionId } from "@/lib/utils";
import Link from "next/link";

export default function ChatPage() {
  const { socket, connected } = useSocket();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [statusText, setStatusText] = useState("");
  const [isTextMode, setIsTextMode] = useState(false);
  const [isSending, setIsSending] = useState(false);
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

      const ttsText = data.tts_text || text;
      try {
        const ok = await speak(ttsText);
        if (!ok) {
          const used = await browserSpeak(ttsText);
          if (used) setStatusText("Using local browser voice.");
          else setStatusText("TTS unavailable.");
          setTimeout(() => setStatusText(""), 3000);
        }
      } catch {
        await browserSpeak(ttsText);
      }
    },
    [addMessage, speak, browserSpeak]
  );

  // Socket event listeners
  const registeredRef = useRef(false);
  if (socket && !registeredRef.current) {
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
        setStatusText(`กำลังรอคิว ลำดับที่ ${pos} (ประมาณ ${wait} วินาที)`);
      }
    });
    socket.on("subtitle", (data) => {
      if (data?.speaker === "user") addMessage("user", data.text || "");
    });
  }

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isSending) return;

    addMessage("user", text);
    setInput("");
    setIsSending(true);
    setStatusText("Sending request...");

    try {
      const payload = await sendSpeech(text);
      if (payload?.queue_error) {
        setStatusText("");
        addMessage("ai", payload.text || "ระบบมีผู้ใช้จำนวนมาก กรุณาลองใหม่");
        return;
      }
      if (payload?.text) {
        await handleAIResponse(payload);
      }
      setStatusText("");
    } catch (err) {
      setStatusText("");
      addMessage("ai", "Network error while sending message.");
    } finally {
      setIsSending(false);
    }
  }, [input, isSending, addMessage, handleAIResponse]);

  const handleRecordResult = useCallback(
    async (blob: Blob) => {
      setStatusText("Processing audio...");
      const form = new FormData();
      form.append("audio", blob, "recording.webm");
      form.append("session_id", getSessionId());

      try {
        const res = await fetch("/api/speech", { method: "POST", body: form });
        if (!res.ok) throw new Error(`${res.status}`);
        const payload = await res.json();
        if (payload?.text) await handleAIResponse(payload);
        setStatusText("");
      } catch {
        setStatusText("Audio processing failed.");
        setTimeout(() => setStatusText(""), 3000);
      }
    },
    [handleAIResponse]
  );

  const { recording, start: startRec, stop: stopRec } = useRecorder(handleRecordResult);

  return (
    <div className="flex flex-col h-screen bg-black text-white">
      <ConnectionStatus />

      {/* Header */}
      <header className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
        <h1 className="text-lg font-bold gradient-text-cmu">REG CMU AI</h1>
        <Link href="/admin" className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors">
          Admin
        </Link>
      </header>

      {/* Messages */}
      <ChatMessages messages={messages} statusText={statusText} />

      {/* Controls */}
      <div className="border-t border-zinc-800 p-4">
        <div className="flex items-center gap-2 max-w-2xl mx-auto">
          <button
            onClick={() => setIsTextMode(!isTextMode)}
            className="p-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 transition-colors"
            title="Toggle mode"
          >
            <MessageSquare className="w-5 h-5" />
          </button>

          {isTextMode ? (
            <>
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSend()}
                placeholder="พิมพ์ข้อความที่นี่..."
                className="flex-1 bg-zinc-800 rounded-xl px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-cmu-purple/50 placeholder:text-zinc-500"
                disabled={isSending}
              />
              <button
                onClick={handleSend}
                disabled={isSending || !input.trim()}
                className="p-2.5 rounded-xl gradient-cmu text-white disabled:opacity-50 transition-opacity"
              >
                <Send className="w-5 h-5" />
              </button>
            </>
          ) : (
            <button
              onClick={recording ? stopRec : startRec}
              className={`flex-1 py-3 rounded-xl font-semibold transition-all ${
                recording
                  ? "bg-red-500/20 text-red-400 border border-red-500/50 animate-pulse"
                  : "bg-zinc-800 hover:bg-zinc-700 text-white"
              }`}
            >
              <div className="flex items-center justify-center gap-2">
                {recording ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                {recording ? "หยุดบันทึก" : "กดเพื่อพูด"}
              </div>
            </button>
          )}

          <button
            onClick={stopTts}
            className="p-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 transition-colors"
            title="Skip/Stop TTS"
          >
            <SkipForward className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}
