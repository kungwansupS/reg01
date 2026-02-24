"use client";

import { useRef, useEffect } from "react";
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
    <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={cn(
            "max-w-[80%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed",
            msg.role === "user"
              ? "ml-auto bg-cmu-purple text-white rounded-br-md"
              : "mr-auto bg-zinc-800 text-zinc-100 rounded-bl-md"
          )}
        >
          {msg.text}
        </div>
      ))}
      {statusText && (
        <div className="text-center text-xs text-zinc-500 animate-pulse">{statusText}</div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
