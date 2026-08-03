"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FolderKanban,
  Database,
  MessageSquareCode,
  TrendingUp,
  Users2,
  AlertTriangle,
  Code2,
  Library,
  FileBarChart2,
  Settings,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Building2,
} from "lucide-react";
import { useUIStore } from "@/shared/services/uiStore";
import { cn } from "@/shared/lib/utils";

const navigationItems = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Projects", href: "/projects", icon: FolderKanban },
  { name: "Datasets", href: "/datasets", icon: Database },
  { name: "AI Chat", href: "/chat", icon: MessageSquareCode, badge: "AI" },
  { name: "Forecasting", href: "/forecasting", icon: TrendingUp },
  { name: "Segmentation", href: "/segmentation", icon: Users2 },
  { name: "Anomaly Detection", href: "/anomalies", icon: AlertTriangle },
  { name: "SQL Playground", href: "/sql", icon: Code2 },
  { name: "Knowledge Base", href: "/knowledge", icon: Library },
  { name: "Executive Reports", href: "/reports", icon: FileBarChart2 },
  { name: "Settings", href: "/settings/profile", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { isSidebarCollapsed, toggleSidebar, activeOrg, setActiveOrg } = useUIStore();

  const orgs = ["Acme Corp", "Stripe Inc.", "Vercel Ltd."];

  return (
    <aside
      className={cn(
        "hidden md:flex flex-col h-screen border-r border-border bg-card text-card-foreground transition-all duration-300 relative select-none z-30 shrink-0",
        isSidebarCollapsed ? "w-[72px]" : "w-64"
      )}
    >
      {/* Sidebar Header */}
      <div className="flex items-center justify-between p-4 h-16 border-b border-border/80">
        {!isSidebarCollapsed ? (
          <Link href="/" className="flex items-center gap-2 font-bold tracking-tight text-foreground select-none">
            <div className="p-1 bg-brand-indigo rounded text-brand-indigo-foreground shrink-0">
              <Sparkles className="h-5 w-5" />
            </div>
            <span className="text-base font-extrabold bg-gradient-to-r from-foreground to-foreground/80 bg-clip-text">DataPilot AI</span>
          </Link>
        ) : (
          <Link href="/" className="mx-auto p-1 bg-brand-indigo rounded text-brand-indigo-foreground shrink-0">
            <Sparkles className="h-5 w-5" />
          </Link>
        )}
        
        {!isSidebarCollapsed && (
          <button
            onClick={toggleSidebar}
            className="p-1.5 rounded-md hover:bg-muted text-muted-foreground border border-border/60 cursor-pointer active:scale-95 transition-all"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Org Selector Context */}
      <div className="p-3 border-b border-border/40">
        {!isSidebarCollapsed ? (
          <div className="flex items-center gap-2 p-2 rounded-lg border border-border/60 hover:bg-muted/40 transition-colors">
            <Building2 className="h-4 w-4 text-muted-foreground shrink-0" />
            <select
              value={activeOrg}
              onChange={(e) => setActiveOrg(e.target.value)}
              className="text-xs font-semibold bg-transparent border-none outline-none w-full text-foreground/80 cursor-pointer focus:ring-0"
            >
              {orgs.map((org) => (
                <option key={org} value={org} className="bg-card text-foreground">
                  {org}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div className="flex items-center justify-center p-2 rounded-lg border border-border/60 hover:bg-muted/40 transition-colors">
            <Building2 className="h-4 w-4 text-muted-foreground" />
          </div>
        )}
      </div>

      {/* Navigation list */}
      <nav className="flex-1 overflow-y-auto p-3 space-y-1.5 custom-scrollbar">
        {navigationItems.map((item) => {
          const isActive = pathname.startsWith(item.href) || pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all group relative select-none",
                isActive
                  ? "bg-secondary text-foreground border border-border/40"
                  : "text-muted-foreground hover:bg-muted/30 hover:text-foreground border border-transparent"
              )}
            >
              <Icon className={cn("h-4.5 w-4.5 shrink-0 transition-colors", isActive ? "text-brand-indigo" : "text-muted-foreground group-hover:text-foreground")} />
              {!isSidebarCollapsed && <span className="flex-1 truncate">{item.name}</span>}
              {!isSidebarCollapsed && item.badge && (
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-brand-indigo/10 text-brand-indigo border border-brand-indigo/20">
                  {item.badge}
                </span>
              )}
              {isSidebarCollapsed && (
                <div className="absolute left-full ml-4 px-2 py-1 bg-popover border border-border text-popover-foreground text-xs rounded opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto transition-opacity z-50 whitespace-nowrap shadow-md">
                  {item.name}
                </div>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Sidebar Footer */}
      {isSidebarCollapsed && (
        <div className="p-3 border-t border-border/40 flex items-center justify-center">
          <button
            onClick={toggleSidebar}
            className="p-1.5 rounded-md hover:bg-muted text-muted-foreground border border-border/60 cursor-pointer active:scale-95 transition-all"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </aside>
  );
}
