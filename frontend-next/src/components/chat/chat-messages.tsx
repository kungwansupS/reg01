"use client";

import { useRef, useEffect } from "react";
import { Bot, User } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ChatMessage {
  id: string;
  role: "user" | "ai";
  text: string;
  timestamp?: number;
}

interface ChatMessagesProps {
  messages: ChatMessage[];
  statusText?: string;
}

export function ChatMessages({ messages, statusText }: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, statusText]);

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 custom-scrollbar">
      {messages.length === 0 && !statusText && (
        <div className="flex flex-col items-center justify-center h-full text-center opacity-60">
          <Bot className="w-16 h-16 text-yt-text-muted mb-4" />
          <p className="text-yt-text-secondary text-sm">สวัสดี! ถามอะไรก็ได้เกี่ยวกับการลงทะเบียน</p>
          <p className="text-yt-text-muted text-xs mt-1">พิมพ์ข้อความหรือกดปุ่มไมค์เพื่อเริ่มต้น</p>
        </div>
      )}

      {messages.map((msg) => (
        <div
          key={msg.id}
          className={cn("flex gap-3 max-w-[85%]", msg.role === "user" ? "ml-auto flex-row-reverse" : "mr-auto")}
        >
          {/* Avatar */}
          <div className={cn(
            "w-8 h-8 rounded-full shrink-0 flex items-center justify-center",
            msg.role === "user" ? "bg-accent/20" : "bg-yt-surface-hover"
          )}>
            {msg.role === "user"
              ? <User className="w-4 h-4 text-accent" />
              : <Bot className="w-4 h-4 text-cmu-purple-light" />
            }
          </div>

          {/* Bubble */}
          <div className={cn(
            "px-4 py-2.5 rounded-2xl text-sm leading-relaxed",
            msg.role === "user"
              ? "bg-accent/15 text-yt-text rounded-tr-sm"
              : "bg-yt-surface text-yt-text border border-yt-border rounded-tl-sm"
          )}>
            <p className="whitespace-pre-wrap">{msg.text}</p>
            {msg.timestamp && (
              <p className="text-[10px] text-yt-text-muted mt-1.5">
                {new Date(msg.timestamp).toLocaleTimeString("th-TH", { hour: "2-digit", minute: "2-digit" })}
              </p>
            )}
          </div>
        </div>
      ))}

      {/* Status text (shown on mobile, hidden on lg where avatar panel shows it) */}
      {statusText && (
        <div className="text-center text-xs text-accent animate-pulse lg:hidden">{statusText}</div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
