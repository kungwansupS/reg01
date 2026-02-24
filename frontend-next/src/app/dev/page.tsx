"use client";

import { useState, useCallback } from "react";
import {
  Settings, BookOpen, GitBranch, Eye, FileCode, Code2, Server, Play,
  ShieldCheck, ArrowLeft, PanelLeftClose, PanelLeft, LogOut, AlertTriangle,
} from "lucide-react";
import { cn, getDevToken, setDevToken as saveDevToken, clearDevToken } from "@/lib/utils";
import Link from "next/link";
import { FlowConfigTab } from "@/components/dev/flow-config-tab";
import { FaqCacheTab } from "@/components/dev/faq-cache-tab";
import { FlowGraphTab } from "@/components/dev/flow-graph-tab";
import { ObservabilityTab } from "@/components/dev/observability-tab";
import { ScenariosTab } from "@/components/dev/scenarios-tab";
import { WorkspaceTab } from "@/components/dev/workspace-tab";
import { EnvironmentTab } from "@/components/dev/environment-tab";
import { TestRunTab } from "@/components/dev/test-run-tab";

const DEV_TABS = [
  { id: "flow-config", label: "Flow Config", icon: Settings },
  { id: "faq-cache", label: "FAQ Cache", icon: BookOpen },
  { id: "flow-graph", label: "Flow Graph", icon: GitBranch },
  { id: "observability", label: "Observability", icon: Eye },
  { id: "scenarios", label: "Scenarios", icon: Play },
  { id: "workspace", label: "Dev Workspace", icon: FileCode },
  { id: "environment", label: "Environment", icon: Server },
  { id: "test-run", label: "Test Run", icon: Code2 },
] as const;

type DevTab = (typeof DEV_TABS)[number]["id"];

export default function DevPage() {
  const [activeTab, setActiveTab] = useState<DevTab>("flow-config");
  const [devToken, setDevToken] = useState(() => getDevToken());
  const [isLoggedIn, setIsLoggedIn] = useState(() => !!devToken);
  const [tokenInput, setTokenInput] = useState("");
  const [collapsed, setCollapsed] = useState(false);
  const [loggingIn, setLoggingIn] = useState(false);
  const [loginError, setLoginError] = useState("");

  const handleLogin = useCallback(async () => {
    if (!tokenInput.trim() || loggingIn) return;
    const token = tokenInput.trim();
    setLoggingIn(true);
    setLoginError("");
    try {
      const res = await fetch("/api/dev/traces?limit=1", {
        headers: { "X-Dev-Token": token, Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        saveDevToken(token);
        setDevToken(token);
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
    clearDevToken();
    setDevToken("");
    setIsLoggedIn(false);
    setTokenInput("");
  }, []);

  if (!isLoggedIn) {
    return (
      <div className="dev-page login-container">
        <div className="dev-card p-8 w-full max-w-md">
          <div className="text-center mb-8">
            <div className="w-16 h-16 rounded-2xl bg-[var(--accent)] flex items-center justify-center mx-auto mb-4">
              <ShieldCheck className="text-white w-8 h-8" />
            </div>
            <h2 className="text-2xl font-bold text-[var(--accent)]">REG-01 Developer Console</h2>
            <p className="text-sm text-[var(--muted)] mt-1">เครื่องมือ dev-only สำหรับปรับ flow และแก้ค่า environment โดยไม่กระทบหน้า admin</p>
            <div className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-[var(--warn)]/50 text-[var(--warn)] text-xs">
              <AlertTriangle className="w-3 h-3" /> LOCAL ONLY: หน้าและ API ของ dev จะเข้าได้เฉพาะ localhost
            </div>
          </div>
          <div className="space-y-4">
            <div>
              <label className="block text-xs text-[var(--muted)] mb-2 font-semibold">X-Dev-Token</label>
              <input
                type="password"
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleLogin()}
                placeholder="ใส่ DEV_TOKEN"
                className="dev-input w-full text-center font-mono tracking-widest py-3"
              />
            </div>
            {loginError && <p className="text-[var(--danger)] text-sm text-center">{loginError}</p>}
            <button
              onClick={handleLogin}
              disabled={loggingIn}
              className="w-full dev-btn-primary py-3 text-base"
            >
              {loggingIn ? "Connecting..." : "Connect"}
            </button>
            <Link href="/" className="block text-center text-sm text-[var(--muted)] hover:text-[var(--ink)] transition-colors">
              ← Back to Chat
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="dev-page flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className={cn(
        "flex flex-col border-r border-[var(--border)] shrink-0 transition-all duration-200",
        collapsed ? "w-[64px]" : "w-[220px]"
      )} style={{ background: "linear-gradient(180deg, var(--panel) 0%, var(--panel-2) 100%)" }}>
        <div className={cn("flex items-center h-14 border-b border-[var(--border)] shrink-0", collapsed ? "px-2 justify-center" : "px-3 gap-2")}>
          {!collapsed && (
            <Link href="/" className="p-1.5 rounded-lg hover:bg-[var(--bg-2)] transition shrink-0" title="Back">
              <ArrowLeft className="w-4 h-4 text-[var(--muted)]" />
            </Link>
          )}
          <div className={cn("flex items-center gap-2", collapsed && "justify-center")}>
            <div className="w-7 h-7 rounded-lg bg-[var(--accent)] flex items-center justify-center shrink-0">
              <Code2 className="w-3.5 h-3.5 text-[#071b16]" />
            </div>
            {!collapsed && (
              <div className="min-w-0">
                <p className="text-xs font-bold text-[var(--accent)] leading-tight truncate">REG-01</p>
                <p className="text-[9px] text-[var(--muted)]">Developer Console</p>
              </div>
            )}
          </div>
          {!collapsed && (
            <button onClick={() => setCollapsed(true)} className="p-1.5 rounded-lg hover:bg-[var(--bg-2)] ml-auto shrink-0">
              <PanelLeftClose className="w-3.5 h-3.5 text-[var(--muted)]" />
            </button>
          )}
        </div>

        <nav className="flex-1 p-1.5 space-y-0.5 overflow-y-auto custom-scrollbar">
          {collapsed && (
            <button onClick={() => setCollapsed(false)} className="w-full flex justify-center p-2 rounded-lg hover:bg-[var(--bg-2)] mb-1" title="Expand">
              <PanelLeft className="w-4 h-4 text-[var(--muted)]" />
            </button>
          )}
          {DEV_TABS.map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-semibold transition-all",
                  active
                    ? "bg-[var(--accent)]/20 text-[var(--accent)] border border-[var(--accent)]/60 shadow-[0_0_0_2px_rgba(35,197,143,0.2)]"
                    : "text-[#c7d6ec] hover:bg-[var(--bg-2)] border border-transparent",
                  collapsed && "justify-center px-0"
                )}
                title={collapsed ? tab.label : undefined}
              >
                <Icon className="w-4 h-4 shrink-0" />
                {!collapsed && <span>{tab.label}</span>}
              </button>
            );
          })}
        </nav>

        <div className="p-1.5 border-t border-[var(--border)]">
          <button
            onClick={handleLogout}
            className={cn(
              "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-semibold text-[var(--muted)] hover:text-[var(--danger)] transition",
              collapsed && "justify-center px-0"
            )}
            title={collapsed ? "Logout" : undefined}
          >
            <LogOut className="w-4 h-4 shrink-0" />
            {!collapsed && <span>Disconnect</span>}
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto custom-scrollbar p-5">
        {activeTab === "flow-config" && <FlowConfigTab />}
        {activeTab === "faq-cache" && <FaqCacheTab />}
        {activeTab === "flow-graph" && <FlowGraphTab />}
        {activeTab === "observability" && <ObservabilityTab />}
        {activeTab === "scenarios" && <ScenariosTab />}
        {activeTab === "workspace" && <WorkspaceTab />}
        {activeTab === "environment" && <EnvironmentTab />}
        {activeTab === "test-run" && <TestRunTab />}
      </main>
    </div>
  );
}
