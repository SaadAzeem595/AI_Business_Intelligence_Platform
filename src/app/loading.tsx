"use client";

import React from "react";
import { Loader2 } from "lucide-react";

export default function LoadingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground flex items-center justify-center p-6 text-center select-none">
      <div className="space-y-4">
        <Loader2 className="h-8 w-8 animate-spin text-brand-indigo mx-auto" />
        <p className="text-xs font-semibold text-muted-foreground tracking-wider uppercase">Loading BI platform workspace...</p>
      </div>
    </div>
  );
}
