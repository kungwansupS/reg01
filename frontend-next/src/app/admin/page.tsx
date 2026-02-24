"use client";

import { useAdmin } from "./layout";
import { DashboardTab } from "@/components/admin/dashboard-tab";
import { ChatTab } from "@/components/admin/chat-tab";
import { FilesTab } from "@/components/admin/files-tab";
import { LogsTab } from "@/components/admin/logs-tab";
import { DatabaseTab } from "@/components/admin/database-tab";
import { FaqTab } from "@/components/admin/faq-tab";
import { MonitorTab } from "@/components/admin/monitor-tab";

export default function AdminPage() {
  const { activeTab } = useAdmin();

  return (
    <>
      {activeTab === "dashboard" && <DashboardTab />}
      {activeTab === "chat" && <ChatTab />}
      {activeTab === "files" && <FilesTab />}
      {activeTab === "logs" && <LogsTab />}
      {activeTab === "database" && <DatabaseTab />}
      {activeTab === "faq" && <FaqTab />}
      {activeTab === "monitor" && <MonitorTab />}
    </>
  );
}
