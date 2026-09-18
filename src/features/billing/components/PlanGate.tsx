"use client";

import React from "react";
import Link from "next/link";
import { Lock, Sparkles, ArrowRight, Loader2 } from "lucide-react";
import { useSubscription } from "../hooks/useSubscription";
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";

interface PlanGateProps {
  feature: string;
  featureName?: string;
  description?: string;
  requiredPlan?: "growth" | "enterprise";
  children: React.ReactNode;
  fallback?: React.ReactNode;
  showOverlay?: boolean;
}

export function PlanGate({
  feature,
  featureName,
  description,
  requiredPlan = "growth",
  children,
  fallback,
  showOverlay = false,
}: PlanGateProps) {
  const { hasFeature, isGrowthOrHigher, createCheckout, isCheckingOut } =
    useSubscription();

  const isEntitled = hasFeature(feature);

  if (isEntitled) {
    return <>{children}</>;
  }

  if (fallback) {
    return <>{fallback}</>;
  }

  const title = featureName || feature.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  const planLabel = requiredPlan === "growth" ? "Growth Plan" : "Enterprise Plan";
  const planCost = requiredPlan === "growth" ? "$79/mo" : "Custom";

  const defaultDesc =
    description ||
    `Access to ${title} requires an active ${planLabel} subscription. Upgrade now to unlock advanced ML models, automated schedules, and unlimited workspace capacity.`;

  const lockContent = (
    <div className="relative rounded-2xl border border-border/80 bg-card/90 p-8 shadow-xl backdrop-blur-md text-center max-w-lg mx-auto">
      <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-tr from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 text-indigo-400">
        <Lock className="h-7 w-7" />
      </div>

      <div className="mb-2 flex items-center justify-center gap-2">
        <Badge variant="info" className="gap-1 font-semibold text-xs px-3 py-1">
          <Sparkles className="h-3 w-3 text-indigo-400" /> Available on {planLabel}
        </Badge>
      </div>

      <h3 className="text-xl font-bold tracking-tight text-foreground mb-2">
        Unlock {title}
      </h3>

      <p className="text-sm text-muted-foreground mb-6 leading-relaxed">
        {defaultDesc}
      </p>

      <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
        <Button
          onClick={() => createCheckout({ plan: requiredPlan })}
          disabled={isCheckingOut}
          className="w-full sm:w-auto bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-medium shadow-md shadow-indigo-500/20 transition-all hover:scale-[1.02]"
        >
          {isCheckingOut ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Initializing Stripe...
            </>
          ) : (
            <>
              Upgrade to {planLabel} ({planCost})
              <ArrowRight className="ml-2 h-4 w-4" />
            </>
          )}
        </Button>

        <Link href="/settings/billing" className="w-full sm:w-auto">
          <Button variant="outline" className="w-full">
            View All Features
          </Button>
        </Link>
      </div>
    </div>
  );

  if (showOverlay) {
    return (
      <div className="relative overflow-hidden rounded-xl">
        <div className="pointer-events-none select-none blur-sm opacity-40">
          {children}
        </div>
        <div className="absolute inset-0 z-10 flex items-center justify-center p-4 bg-background/50 backdrop-blur-[2px]">
          {lockContent}
        </div>
      </div>
    );
  }

  return <div className="py-12 px-4">{lockContent}</div>;
}
