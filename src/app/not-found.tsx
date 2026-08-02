"use client";

import React from "react";
import Link from "next/link";
import { Button } from "@/shared/components/ui/button";
import { HelpCircle } from "lucide-react";

export default function NotFoundPage() {
  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col items-center justify-center p-6 text-center select-none">
      <div className="w-full max-w-sm space-y-6">
        <div className="flex flex-col items-center space-y-2">
          <div className="p-3 bg-brand-indigo/10 rounded-full text-brand-indigo mb-2">
            <HelpCircle className="h-8 w-8" />
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight">404 - Page Not Found</h1>
          <p className="text-xs text-muted-foreground leading-relaxed">
            The page you are looking for doesn't exist or has been relocated to another workspace directory folder.
          </p>
        </div>
        <Link href="/dashboard">
          <Button variant="brand" className="w-full mt-2">
            Return to Dashboard
          </Button>
        </Link>
      </div>
    </div>
  );
}
