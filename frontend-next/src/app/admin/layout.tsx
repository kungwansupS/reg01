"use client";

import { useState, useCallback, type ReactNode, createContext, useContext } from "react";
import {
  LayoutDashboard, MessageSquare, FolderOpen, FileText,
  Database, BrainCircuit, Activity, ShieldCheck, LogOut,
  PanelLeftClose, PanelLeft, ArrowLeft, Bot,
} from "lucide-react";
import { cn, getAdminToken, setAdminToken, clearAdminToken } from "@/lib/utils";
import Link from "next/link";

const NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "chat", label: "Chat", icon: MessageSquare },
  { id: "files", label: "Files", icon: FolderOpen },
  { id: "logs", label: "Audit Logs", icon: FileText },
  { id: "database", label: "Database", icon: Database },
  { id: "faq", label: "FAQ", icon: BrainCircuit },
  { id: "monitor", label: "Monitor", icon: Activity },
] as const;

export type AdminTab = (typeof NAV_ITEMS)[number]["id"];

interface AdminContextValue {
  activeTab: AdminTab;
  setActiveTab: (tab: AdminTab) => void;
  isLoggedIn: boolean;
}

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
  const [collapsed, setCollapsed] = useState(false);
  const [loggingIn, setLoggingIn] = useState(false);

  const handleLogin = useCallback(async () => {
    if (!tokenInput.trim() || loggingIn) return;
    const token = tokenInput.trim();
    setLoggingIn(true);
    setLoginError("");
    try {
      const res = await fetch("/api/admin/stats", {
        headers: { "X-Admin-Token": token, Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setAdminToken(token);
        setIsLoggedIn(true);
      } else {
        setLoginError("Invalid token");
      }
    } catch {
      setLoginError("Connection error");
    }
    setLoggingIn(false);
  }, [tokenInput, loggingIn]);

  const handleLogout = useCallback(() => {
    clearAdminToken();
    setIsLoggedIn(false);
    setTokenInput("");
  }, []);

  if (!isLoggedIn) {
    return (
      <div className="login-container">
        <div className="yt-card p-8 w-full max-w-md">
          <div className="text-center mb-8">
            <div className="w-16 h-16 rounded-2xl gradient-cmu flex items-center justify-center mx-auto mb-4">
              <ShieldCheck className="text-white w-8 h-8" />
            </div>
            <h2 className="text-2xl font-bold gradient-text-cmu">Admin Console</h2>
            <p className="text-sm text-yt-text-muted mt-1">REG CMU Platform</p>
          </div>
          <div className="space-y-4">
            <input
              type="password"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleLogin()}
              placeholder="Admin Token"
              className="w-full yt-input text-center font-mono tracking-widest py-3"
            />
            {loginError && <p className="text-danger text-sm text-center">{loginError}</p>}
            <button
              onClick={handleLogin}
              disabled={loggingIn}
              className="w-full yt-btn yt-btn-primary py-3 rounded-xl font-semibold disabled:opacity-50"
            >
              {loggingIn ? "Authenticating..." : "Sign In"}
            </button>
            <Link href="/" className="block text-center text-sm text-yt-text-muted hover:text-yt-text transition-colors">
              ← Back to Chat
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <AdminContext value={{ activeTab, setActiveTab, isLoggedIn }}>
      <div className="flex h-screen bg-yt-bg text-yt-text overflow-hidden">
        {/* ─── YouTube-style Sidebar ─── */}
        <aside className={cn(
          "flex flex-col border-r border-yt-border shrink-0 transition-all duration-200",
          collapsed ? "w-[72px]" : "w-[240px]"
        )}>
          {/* Logo */}
          <div className={cn("flex items-center h-14 border-b border-yt-border shrink-0", collapsed ? "px-3 justify-center" : "px-4 gap-3")}>
            {!collapsed && (
              <Link href="/" className="yt-btn-icon shrink-0" title="Back to Chat">
                <ArrowLeft className="w-5 h-5" />
              </Link>
            )}
            <div className={cn("flex items-center gap-2", collapsed && "justify-center")}>
              <div className="w-8 h-8 rounded-lg gradient-cmu flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4 text-white" />
              </div>
              {!collapsed && (
                <div className="min-w-0">
                  <p className="text-sm font-bold gradient-text-cmu leading-tight truncate">REG CMU</p>
                  <p className="text-[10px] text-yt-text-muted">Admin</p>
                </div>
              )}
            </div>
            {!collapsed && (
              <button onClick={() => setCollapsed(true)} className="yt-btn-icon ml-auto shrink-0">
                <PanelLeftClose className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Nav */}
          <nav className="flex-1 p-2 space-y-0.5 overflow-y-auto custom-scrollbar">
            {collapsed && (
              <button onClick={() => setCollapsed(false)} className="yt-sidebar-item justify-center mb-2" title="Expand">
                <PanelLeft className="w-5 h-5" />
              </button>
            )}
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const active = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={cn(
                    "yt-sidebar-item",
                    active && "yt-sidebar-item-active",
                    collapsed && "justify-center px-0"
                  )}
                  title={collapsed ? item.label : undefined}
                >
                  <Icon className="w-5 h-5 shrink-0" />
                  {!collapsed && <span>{item.label}</span>}
                </button>
              );
            })}
          </nav>

          {/* Footer */}
          <div className="p-2 border-t border-yt-border">
            <button
              onClick={handleLogout}
              className={cn(
                "yt-sidebar-item text-yt-text-secondary hover:text-danger",
                collapsed && "justify-center px-0"
              )}
              title={collapsed ? "Logout" : undefined}
            >
              <LogOut className="w-5 h-5 shrink-0" />
              {!collapsed && <span>Logout</span>}
            </button>
          </div>
        </aside>

        {/* ─── Main Content ─── */}
        <main className="flex-1 overflow-y-auto custom-scrollbar">{children}</main>
      </div>
    </AdminContext>
  );
}
