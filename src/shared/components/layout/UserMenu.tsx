"use client";

import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { User, CreditCard, Settings, LogOut, ChevronDown } from "lucide-react";

export function UserMenu() {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 p-1.5 rounded-full hover:bg-muted text-muted-foreground transition-all cursor-pointer active:scale-95"
      >
        <div className="h-7 w-7 rounded-full bg-brand-indigo flex items-center justify-center text-brand-indigo-foreground text-xs font-semibold select-none shadow-sm">
          SA
        </div>
        <span className="hidden sm:inline text-xs font-medium text-foreground/80">Saad A.</span>
        <ChevronDown className="hidden sm:inline h-3 w-3 opacity-60" />
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-56 rounded-lg border border-border bg-popover p-1 shadow-md text-popover-foreground animate-fade-in z-50">
          <div className="px-3 py-2 border-b border-border/40 select-none">
            <p className="text-sm font-semibold truncate text-foreground">Saad Alvi</p>
            <p className="text-[11px] text-muted-foreground truncate">saad@example.com</p>
          </div>
          <div className="py-1">
            <Link
              href="/settings/profile"
              onClick={() => setIsOpen(false)}
              className="flex items-center gap-2 px-3 py-2 rounded-md text-xs hover:bg-muted/80 transition-colors text-foreground/80 hover:text-foreground"
            >
              <User className="h-3.5 w-3.5" />
              <span>My Profile</span>
            </Link>
            <Link
              href="/settings/profile"
              onClick={() => setIsOpen(false)}
              className="flex items-center gap-2 px-3 py-2 rounded-md text-xs hover:bg-muted/80 transition-colors text-foreground/80 hover:text-foreground"
            >
              <Settings className="h-3.5 w-3.5" />
              <span>Workspace Settings</span>
            </Link>
            <Link
              href="/settings/billing"
              onClick={() => setIsOpen(false)}
              className="flex items-center gap-2 px-3 py-2 rounded-md text-xs hover:bg-muted/80 transition-colors text-foreground/80 hover:text-foreground"
            >
              <CreditCard className="h-3.5 w-3.5" />
              <span>Billing & Plan</span>
            </Link>
          </div>
          <div className="border-t border-border/40 pt-1 mt-1">
            <Link
              href="/login"
              onClick={() => setIsOpen(false)}
              className="flex items-center gap-2 px-3 py-2 rounded-md text-xs hover:bg-rose-500/10 text-rose-500 hover:text-rose-600 transition-colors"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span>Log out</span>
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
