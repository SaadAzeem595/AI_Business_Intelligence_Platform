"use client";

import React from "react";
import Link from "next/link";
import { Sparkles } from "lucide-react";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background text-foreground flex items-center justify-center p-6 relative select-none">
      <div className="w-full max-w-md space-y-6">
        <div className="flex flex-col items-center text-center space-y-2">
          <Link href="/" className="flex items-center gap-2 font-bold tracking-tight mb-2">
            <div className="p-1 bg-brand-indigo rounded text-brand-indigo-foreground shrink-0">
              <Sparkles className="h-5 w-5" />
            </div>
            <span className="text-base font-extrabold">DataPilot AI</span>
          </Link>
        </div>
        {children}
      </div>
    </div>
  );
}
