import type { Metadata } from "next";
import { SocketProvider } from "@/providers/socket-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "REG CMU AI",
  description: "AI-powered registration assistant for Chiang Mai University",
  icons: { icon: "/favicon.ico" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="th">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet" />
      </head>
      <body className="font-sans antialiased">
        <SocketProvider>{children}</SocketProvider>
      </body>
    </html>
  );
}
