import React from "react";
import { Sidebar } from "@/shared/components/layout/Sidebar";
import { Navbar } from "@/shared/components/layout/Navbar";
import { OfflineBanner } from "@/shared/components/layout/OfflineBanner";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen w-full overflow-hidden bg-background text-foreground">
      {/* Responsive Collapsible Sidebar */}
      <Sidebar />
      
      {/* Main Workspace Frame */}
      <div className="flex flex-col flex-1 overflow-hidden relative">
        {/* Offline Network Status Alert Banner */}
        <OfflineBanner />

        {/* Top Sticky Dashboard Navigation */}
        <Navbar />
        
        {/* Scrollable page body content wrapper */}
        <main className="flex-1 overflow-y-auto bg-background/50 p-4 md:p-6 custom-scrollbar relative">
          <div className="max-w-[1400px] mx-auto w-full space-y-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
