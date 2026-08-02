"use client";

import React from "react";
import { WifiOff } from "lucide-react";
import { useOffline } from "@/shared/hooks/useOffline";

export function OfflineBanner() {
  const isOffline = useOffline();

  if (!isOffline) return null;

  return (
    <div className="bg-rose-500 text-white text-xs font-bold py-2 px-4 flex items-center justify-center gap-2 select-none animate-fade-in shrink-0 z-50">
      <WifiOff className="h-4 w-4 shrink-0" />
      <span>You are currently offline. Active database query links and forecasting updates may be delayed.</span>
    </div>
  );
}
