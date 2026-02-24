import { io, Socket } from "socket.io-client";

let socket: Socket | null = null;

export function getSocket(): Socket {
  if (!socket) {
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "";
    socket = io(backendUrl || undefined, {
      transports: ["websocket", "polling"],
      autoConnect: false,
    });
  }
  return socket;
}
