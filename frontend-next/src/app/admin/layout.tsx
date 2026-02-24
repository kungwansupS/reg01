"use client";

import { useState, useCallback, type ReactNode } from "react";
import {
  LayoutDashboard, MessageSquare, FolderOpen, FileText,
  Database, BrainCircuit, Activity, ShieldCheck, LogOut,
} from "lucide-react";
import { cn, getAdminToken, setAdminToken, clearAdminToken } from "@/lib/utils";

const NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "chat", label: "Unified Chat", icon: MessageSquare },
  { id: "files", label: "File Explorer", icon: FolderOpen },
  { id: "logs", label: "Audit Logs", icon: FileText },
  { id: "database", label: "Database", icon: Database },
  { id: "faq", label: "FAQ Manager", icon: BrainCircuit },
  { id: "monitor", label: "Live Monitor", icon: Activity },
] as const;

export type AdminTab = (typeof NAV_ITEMS)[number]["id"];

interface AdminContextValue {
  activeTab: AdminTab;
  setActiveTab: (tab: AdminTab) => void;
  isLoggedIn: boolean;
}

import { createContext, useContext } from "react";
const AdminContext = createContext<AdminContextValue>({
  activeTab: "dashboard",
  setActiveTab: () => {},
  isLoggedIn: false,
});
export const useAdmin = () => useContext(AdminContext);

export default function AdminLayout({ children }: { children: ReactNode }) {
  const [isLoggedIn, setIsLoggedIn] = useState(() => !!getAdminToken());
  const [activeTab, setActiveTab] = useState<AdminTab>("dashboard");
  const [tokenInput, setTokenInput] = useState("");
  const [loginError, setLoginError] = useState("");

  const handleLogin = useCallback(async () => {
    if (!tokenInput.trim()) return;
    const token = tokenInput.trim();
    try {
      const res = await fetch("/api/admin/stats", {
        headers: {
          "X-Admin-Token": token,
          Authorization: `Bearer ${token}`,
        },
      });
      if (res.ok) {
        setAdminToken(token);
        setIsLoggedIn(true);
        setLoginError("");
      } else {
        setLoginError("Invalid token");
      }
    } catch {
      setLoginError("Connection error");
    }
  }, [tokenInput]);

  const handleLogout = useCallback(() => {
    clearAdminToken();
    setIsLoggedIn(false);
    setTokenInput("");
  }, []);

  if (!isLoggedIn) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-8 w-full max-w-md shadow-2xl">
          <div className="text-center mb-8">
            <div className="gradient-cmu w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <ShieldCheck className="text-white w-8 h-8" />
            </div>
            <h2 className="text-2xl font-black gradient-text-cmu">Enterprise Portal</h2>
            <p className="text-sm text-zinc-500 mt-1">REG CMU Platform</p>
          </div>
          <div className="space-y-4">
            <input
              type="password"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleLogin()}
              placeholder="Security Token"
              className="w-full px-4 py-3 bg-zinc-800 border border-zinc-700 rounded-xl text-center font-mono tracking-widest text-white outline-none focus:ring-2 focus:ring-cmu-purple/50"
            />
            {loginError && <p className="text-red-400 text-sm text-center">{loginError}</p>}
            <button
              onClick={handleLogin}
              className="w-full gradient-cmu text-white font-bold py-3 rounded-xl hover:opacity-90 transition-opacity"
            >
              Authenticate
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <AdminContext value={{ activeTab, setActiveTab, isLoggedIn }}>
      <div className="flex h-screen bg-zinc-950 text-white overflow-hidden">
        {/* Sidebar */}
        <aside className="w-64 bg-zinc-900 border-r border-zinc-800 flex flex-col">
          <div className="p-5 border-b border-zinc-800">
            <div className="flex items-center gap-3">
              <div className="gradient-cmu p-2 rounded-xl">
                <BrainCircuit className="text-white w-5 h-5" />
              </div>
              <div>
                <span className="font-black text-lg gradient-text-cmu block leading-tight">REG CMU</span>
                <p className="text-[10px] text-zinc-500">Admin Console</p>
              </div>
            </div>
          </div>

          <nav className="flex-1 p-3 space-y-1 overflow-y-auto custom-scrollbar">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const active = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={cn(
                    "w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all",
                    active
                      ? "bg-cmu-purple/15 text-cmu-purple-light"
                      : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
                  )}
                >
                  <Icon className="w-4.5 h-4.5" />
                  {item.label}
                </button>
              );
            })}
          </nav>

          <div className="p-3 border-t border-zinc-800">
            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-zinc-400 hover:bg-zinc-800 hover:text-red-400 transition-all"
            >
              <LogOut className="w-4.5 h-4.5" />
              Logout
            </button>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto custom-scrollbar">{children}</main>
      </div>
    </AdminContext>
  );
}
