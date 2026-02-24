import type { Metadata } from "next";
import { SocketProvider } from "@/providers/socket-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "REG CMU AI Assistant",
  description: "AI-powered registration assistant for Chiang Mai University",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="th">
      <body className="font-sans antialiased">
        <SocketProvider>{children}</SocketProvider>
      </body>
    </html>
  );
}
