import { io, Socket } from "socket.io-client";

let socket: Socket | null = null;

export function getSocket(): Socket {
  if (!socket) {
    // Connect directly to backend (same hostname, port 5000).
    // Works in dev (localhost:5000) and Docker (port mapped to host 5000).
    // Next.js rewrites can't reliably proxy WebSocket upgrades.
    const backendUrl =
      typeof window !== "undefined"
        ? `${window.location.protocol}//${window.location.hostname}:5000`
        : "http://localhost:5000";

    socket = io(backendUrl, {
      transports: ["websocket", "polling"],
      autoConnect: false,
    });
  }
  return socket;
}
