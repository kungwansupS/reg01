import { getSessionId, getAuthToken, getAdminToken, getDevToken } from "./utils";

const BASE = "";

export async function sendSpeech(text: string): Promise<{
  text?: string;
  tts_text?: string;
  motion?: string;
  queue_error?: boolean;
  session_id?: string;
}> {
  const form = new FormData();
  form.append("text", text);
  form.append("session_id", getSessionId());

  const res = await fetch(`${BASE}/api/speech`, {
    method: "POST",
    body: form,
    headers: { "X-API-Key": getAuthToken() },
  });

  if (!res.ok) throw new Error(`Request failed (${res.status})`);
  return res.json();
}

export async function sendSpeechAudio(blob: Blob): Promise<{
  text?: string;
  tts_text?: string;
  motion?: string;
  queue_error?: boolean;
  session_id?: string;
}> {
  const form = new FormData();
  form.append("audio", blob, "recording.webm");
  form.append("session_id", getSessionId());

  const res = await fetch(`${BASE}/api/speech`, {
    method: "POST",
    body: form,
    headers: { "X-API-Key": getAuthToken() },
  });

  if (!res.ok) throw new Error(`Request failed (${res.status})`);
  return res.json();
}

export async function streamTts(text: string): Promise<Response> {
  const form = new FormData();
  form.append("text", text);
  return fetch(`${BASE}/api/speak`, { method: "POST", body: form });
}

export async function adminFetch(
  path: string,
  init?: RequestInit
): Promise<Response> {
  const token = getAdminToken();
  const headers = new Headers(init?.headers);
  headers.set("X-Admin-Token", token);
  headers.set("Authorization", `Bearer ${token}`);

  if (init?.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  return fetch(`${BASE}${path}`, { ...init, headers });
}

export async function adminFormPost(
  path: string,
  form: FormData
): Promise<Response> {
  const token = getAdminToken();
  return fetch(`${BASE}${path}`, {
    method: "POST",
    body: form,
    headers: {
      "X-Admin-Token": token,
      Authorization: `Bearer ${token}`,
    },
  });
}

export async function devFetch(
  path: string,
  init?: RequestInit
): Promise<Response> {
  const token = getDevToken();
  const headers = new Headers(init?.headers);
  headers.set("X-Dev-Token", token);
  headers.set("Authorization", `Bearer ${token}`);

  if (init?.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  return fetch(`${BASE}${path}`, { ...init, headers });
}
