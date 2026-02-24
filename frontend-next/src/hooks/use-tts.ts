"use client";

import { useRef, useCallback } from "react";

export function useTts() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const mediaSourceRef = useRef<MediaSource | null>(null);
  const stoppedRef = useRef(false);

  const stop = useCallback(() => {
    stoppedRef.current = true;
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current.src = "";
      audioRef.current = null;
    }
    if (mediaSourceRef.current) {
      try {
        if (mediaSourceRef.current.readyState === "open") mediaSourceRef.current.endOfStream();
      } catch { /* ignore */ }
      mediaSourceRef.current = null;
    }
  }, []);

  const speak = useCallback(async (text: string): Promise<boolean> => {
    stop();
    stoppedRef.current = false;

    const form = new FormData();
    form.append("text", text);

    let response: Response;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 8000);
    try {
      response = await fetch("/api/speak", { method: "POST", body: form, signal: controller.signal });
    } finally {
      clearTimeout(timeoutId);
    }

    if (response.status === 204) return false;
    const ct = (response.headers.get("content-type") || "").toLowerCase();
    if (!response.ok || !response.body || !ct.includes("audio/")) return false;

    const mediaSource = new MediaSource();
    mediaSourceRef.current = mediaSource;

    const audio = new Audio();
    audio.src = URL.createObjectURL(mediaSource);
    audioRef.current = audio;

    await audio.play().catch(() => {});

    mediaSource.addEventListener("sourceopen", () => {
      const sb = mediaSource.addSourceBuffer("audio/mpeg");
      const reader = response.body!.getReader();
      const queue: ArrayBuffer[] = [];

      sb.addEventListener("updateend", () => {
        if (queue.length > 0 && !sb.updating) sb.appendBuffer(queue.shift()!);
      });

      (function pump() {
        if (stoppedRef.current) return;
        reader.read().then(({ done, value }) => {
          if (stoppedRef.current) return;
          if (done) {
            if (!sb.updating && queue.length === 0) {
              try { mediaSource.endOfStream(); } catch { /* ignore */ }
            }
            return;
          }
          if (!value) {
            pump();
            return;
          }

          const chunk = value.buffer.slice(
            value.byteOffset,
            value.byteOffset + value.byteLength
          );

          if (!sb.updating) {
            sb.appendBuffer(chunk);
          } else {
            queue.push(chunk);
          }
          pump();
        });
      })();
    });

    return true;
  }, [stop]);

  const browserSpeak = useCallback(async (text: string): Promise<boolean> => {
    const synth = window.speechSynthesis;
    if (!synth || typeof SpeechSynthesisUtterance === "undefined") return false;
    const clean = text.replace(/^\[Bot[^\]]*\]\s*/i, "").replace(/\/\//g, " ").trim();
    if (!clean) return false;

    const lang = /[ก-๙]/.test(clean) ? "th-TH" : /[\u3040-\u30ff]/.test(clean) ? "ja-JP" : "en-US";

    return new Promise((resolve) => {
      const utt = new SpeechSynthesisUtterance(clean);
      utt.lang = lang;
      utt.rate = 1.0;
      utt.onend = () => resolve(true);
      utt.onerror = () => resolve(false);
      try { synth.cancel(); synth.speak(utt); } catch { resolve(false); }
    });
  }, []);

  return { speak, browserSpeak, stop };
}
