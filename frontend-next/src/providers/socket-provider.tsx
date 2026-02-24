"use client";

import { createContext, useContext, useEffect, useState, useRef, type ReactNode } from "react";
import { type Socket } from "socket.io-client";
import { getSocket } from "@/lib/socket";
import { getSessionId } from "@/lib/utils";

interface SocketContextValue {
  socket: Socket | null;
  connected: boolean;
}

const SocketContext = createContext<SocketContextValue>({ socket: null, connected: false });

export function useSocket() {
  return useContext(SocketContext);
}

export function SocketProvider({ children }: { children: ReactNode }) {
  const [connected, setConnected] = useState(false);
  const socketRef = useRef<Socket | null>(null);

  useEffect(() => {
    const socket = getSocket();
    socketRef.current = socket;

    socket.on("connect", () => {
      setConnected(true);
      socket.emit("client_register_session", { session_id: getSessionId() });
    });

    socket.on("disconnect", () => setConnected(false));

    socket.on("session_registered", (data: { session_id?: string }) => {
      const sid = data?.session_id?.trim();
      if (sid) {
        localStorage.setItem("session_id", sid);
      }
    });

    socket.connect();

    return () => {
      socket.off("connect");
      socket.off("disconnect");
      socket.off("session_registered");
      socket.disconnect();
    };
  }, []);

  return (
    <SocketContext value={{ socket: socketRef.current, connected }}>
      {children}
    </SocketContext>
  );
}
