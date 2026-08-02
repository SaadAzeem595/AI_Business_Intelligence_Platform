"use client";

import React, { useState, useRef, useEffect } from "react";
import { Bell, Search, Sun, Moon, Menu } from "lucide-react";
import { Breadcrumbs } from "./Breadcrumbs";
import { UserMenu } from "./UserMenu";
import { useTheme } from "@/shared/providers/ThemeProvider";
import { useUIStore } from "@/shared/services/uiStore";

export function Navbar() {
  const { theme, setTheme } = useTheme();
  const { toggleSidebar } = useUIStore();
  const [showNotifications, setShowNotifications] = useState(false);
  const notificationRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (notificationRef.current && !notificationRef.current.contains(event.target as Node)) {
        setShowNotifications(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <header className="flex h-16 w-full items-center justify-between border-b border-border bg-card px-4 md:px-6 shrink-0 z-20 sticky top-0 select-none">
      <div className="flex items-center gap-4">
        {/* Mobile Hamburger toggle */}
        <button
          onClick={toggleSidebar}
          className="p-1.5 rounded-md hover:bg-muted text-muted-foreground md:hidden cursor-pointer active:scale-95 transition-all"
        >
          <Menu className="h-4.5 w-4.5" />
        </button>

        {/* Dynamic Breadcrumbs */}
        <Breadcrumbs />
      </div>

      <div className="flex items-center gap-4">
        {/* Fake Search bar (launches Command palette) */}
        <button className="hidden sm:flex items-center gap-2 text-xs text-muted-foreground px-3 py-1.5 border border-border/80 rounded-md hover:bg-muted/40 transition-colors w-48 text-left cursor-pointer select-none">
          <Search className="h-3.5 w-3.5" />
          <span>Search workspace...</span>
          <kbd className="ml-auto pointer-events-none select-none font-mono text-[10px] text-muted-foreground/60">⌘K</kbd>
        </button>

        {/* Notification Button */}
        <div className="relative" ref={notificationRef}>
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className="p-2 rounded-full hover:bg-muted text-muted-foreground relative cursor-pointer active:scale-95 transition-all"
          >
            <Bell className="h-4.5 w-4.5" />
            <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-brand-indigo ring-2 ring-card" />
          </button>

          {showNotifications && (
            <div className="absolute right-0 mt-2 w-80 rounded-lg border border-border bg-popover p-1 shadow-md text-popover-foreground animate-fade-in z-50">
              <div className="px-3 py-2 border-b border-border/40 font-semibold text-xs flex justify-between select-none">
                <span>Notifications</span>
                <span className="text-[10px] font-bold text-brand-indigo cursor-pointer hover:underline">Mark all read</span>
              </div>
              <div className="max-h-60 overflow-y-auto py-1 divide-y divide-border/20 text-xs">
                <div className="px-3 py-2 hover:bg-muted/40 transition-colors">
                  <p className="font-semibold text-foreground">Dataset uploaded successfully</p>
                  <p className="text-[10px] text-muted-foreground mt-0.5">Your file `q3_sales.csv` was processed.</p>
                  <span className="text-[9px] text-muted-foreground/80 mt-1 block">5m ago</span>
                </div>
                <div className="px-3 py-2 hover:bg-muted/40 transition-colors">
                  <p className="font-semibold text-foreground">AI Analysis Complete</p>
                  <p className="text-[10px] text-muted-foreground mt-0.5">Anomaly checks flagged 4 outliers.</p>
                  <span className="text-[9px] text-muted-foreground/80 mt-1 block">1h ago</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Theme Toggle Button */}
        <button
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="p-2 rounded-full hover:bg-muted text-muted-foreground cursor-pointer active:scale-95 transition-all"
          title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
        >
          {theme === "dark" ? <Sun className="h-4.5 w-4.5" /> : <Moon className="h-4.5 w-4.5" />}
        </button>

        {/* User Profile Menu */}
        <UserMenu />
      </div>
    </header>
  );
}
