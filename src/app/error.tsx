"use client";

import React, { useEffect } from "react";
import { Button } from "@/shared/components/ui/button";
import { AlertOctagon } from "lucide-react";

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error("Layout crash caught:", error);
  }, [error]);

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col items-center justify-center p-6 text-center select-none">
      <div className="w-full max-w-sm space-y-6">
        <div className="flex flex-col items-center space-y-2">
          <div className="p-3 bg-rose-500/10 rounded-full text-rose-500 mb-2 animate-pulse">
            <AlertOctagon className="h-8 w-8" />
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight">System Error</h1>
          <p className="text-xs text-muted-foreground leading-relaxed">
            An unexpected error occurred in your current session context.
          </p>
        </div>
        <div className="flex flex-col gap-2">
          <Button onClick={reset} variant="brand" className="w-full">
            Reload Page Context
          </Button>
          <a href="/dashboard" className="w-full">
            <Button variant="outline" className="w-full">
              Return to Dashboard
            </Button>
          </a>
        </div>
      </div>
    </div>
  );
}
