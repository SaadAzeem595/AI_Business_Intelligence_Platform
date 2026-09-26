"use client";

import React from "react";
import Link from "next/link";
import { CheckCircle2, Sparkles, ArrowRight, Loader2, ExternalLink, AlertTriangle, ShieldCheck } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import { Card, CardContent } from "@/shared/components/ui/card";
import { Badge } from "@/shared/components/ui/badge";
import { useSubscription } from "../hooks/useSubscription";

export function PricingCards() {
  const {
    plan,
    status,
    isLoading,
    isGrowthOrHigher,
    isGracePeriod,
    currentPeriodEnd,
    createCheckout,
    isCheckingOut,
    openPortal,
    isOpeningPortal,
  } = useSubscription();

  const formattedPeriodEnd = currentPeriodEnd
    ? new Date(currentPeriodEnd).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : null;

  // Requirement 37: Loading state must show skeleton and NOT temporarily show Starter
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto animate-pulse" aria-label="Loading plans">
        {[1, 2, 3].map((idx) => (
          <Card key={idx} className="border-border/60 bg-card/40 flex flex-col justify-between h-[480px]">
            <CardContent className="p-6 space-y-6 flex-1">
              <div className="flex justify-between items-start">
                <div className="space-y-2">
                  <div className="h-6 w-24 bg-muted/60 rounded" />
                  <div className="h-4 w-40 bg-muted/40 rounded" />
                </div>
              </div>
              <div className="h-10 w-28 bg-muted/60 rounded mt-4" />
              <div className="space-y-3 pt-4">
                <div className="h-4 w-full bg-muted/40 rounded" />
                <div className="h-4 w-5/6 bg-muted/40 rounded" />
                <div className="h-4 w-4/6 bg-muted/40 rounded" />
                <div className="h-4 w-3/4 bg-muted/40 rounded" />
              </div>
            </CardContent>
            <div className="p-6 pt-0 border-t border-border/30">
              <div className="h-10 w-full bg-muted/60 rounded" />
            </div>
          </Card>
        ))}
      </div>
    );
  }

  const isPastDue = status === "past_due";

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto" role="region" aria-label="Pricing Plans">
      {/* 1. STARTER PLAN */}
      <Card className={`border-border/80 flex flex-col justify-between hover:border-border transition-all ${plan === "starter" ? "ring-2 ring-indigo-500/30 bg-card/80" : ""}`}>
        <CardContent className="p-6 space-y-6 flex-1">
          <div className="flex justify-between items-start">
            <div>
              <h3 className="text-lg font-bold text-foreground">Starter</h3>
              <p className="text-xs text-muted-foreground mt-1">
                For individual analysts testing the engine.
              </p>
            </div>
            {plan === "starter" && (
              <Badge variant="secondary" className="text-[10px] font-semibold tracking-wider uppercase">
                Current Plan
              </Badge>
            )}
          </div>
          <div className="flex items-baseline">
            <span className="text-4xl font-extrabold text-foreground">$0</span>
            <span className="text-xs text-muted-foreground ml-1.5 font-medium">/ month</span>
          </div>
          <ul className="space-y-2.5 text-xs text-muted-foreground" aria-label="Starter Plan Features">
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
              <span><strong>1 active dataset</strong></span>
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
              <span>Basic SQL Playground</span>
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
              <span>Standard AI Chat queries</span>
            </li>
          </ul>
        </CardContent>
        <div className="p-6 pt-0 border-t border-border/40 mt-4">
          <Link href="/dashboard" className="w-full">
            <Button
              variant="outline"
              className="w-full mt-4 text-xs font-semibold"
              disabled={plan === "starter"}
              aria-label={plan === "starter" ? "Starter is your Current Plan" : "Included in your current plan"}
            >
              {plan === "starter" ? "Current Plan" : "Included"}
            </Button>
          </Link>
        </div>
      </Card>

      {/* 2. GROWTH PLAN */}
      <Card
        className={`border-indigo-500/50 border-2 bg-gradient-to-b from-indigo-500/10 via-card/90 to-card flex flex-col justify-between relative shadow-xl shadow-indigo-500/10 ${
          plan === "growth" ? "ring-2 ring-indigo-500" : ""
        }`}
      >
        <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full bg-indigo-600 text-[10px] font-bold text-white uppercase tracking-wider flex items-center gap-1 shadow-md">
          <Sparkles className="h-3 w-3" /> Most Popular
        </div>
        <CardContent className="p-6 space-y-6 flex-1 pt-8">
          <div className="flex justify-between items-start">
            <div>
              <h3 className="text-lg font-bold text-foreground">Growth</h3>
              <p className="text-xs text-muted-foreground mt-1">
                For scaling businesses and data departments.
              </p>
            </div>
            {plan === "growth" && (
              <Badge
                variant={isPastDue ? "destructive" : isGracePeriod ? "warning" : "info"}
                className="text-[10px] font-semibold tracking-wider uppercase"
              >
                {isPastDue ? "Payment Issue" : isGracePeriod ? "Canceling" : "Current Plan"}
              </Badge>
            )}
          </div>
          <div className="flex items-baseline">
            <span className="text-4xl font-extrabold text-foreground">$79</span>
            <span className="text-xs text-muted-foreground ml-1.5 font-medium">/ month</span>
          </div>

          {isGracePeriod && formattedPeriodEnd && (
            <p className="text-[11px] text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2.5 py-1.5 rounded-md">
              Active until {formattedPeriodEnd} (Canceling at period end)
            </p>
          )}

          {isPastDue && (
            <p className="text-[11px] text-rose-400 bg-rose-500/10 border border-rose-500/20 px-2.5 py-1.5 rounded-md flex items-center gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
              Subscription requires payment attention.
            </p>
          )}

          <ul className="space-y-2.5 text-xs text-muted-foreground" aria-label="Growth Plan Features">
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-indigo-400 shrink-0" />
              <span><strong>Unlimited datasets</strong></span>
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-indigo-400 shrink-0" />
              <span>Advanced Forecasting (ARIMA & Prophet)</span>
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-indigo-400 shrink-0" />
              <span>Advanced Anomaly Detection / Outliers</span>
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-indigo-400 shrink-0" />
              <span>Scheduled Executive Reports (PDF & PPTX)</span>
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-indigo-400 shrink-0" />
              <span>Shared team collaboration spaces</span>
            </li>
          </ul>
        </CardContent>

        <div className="p-6 pt-0 border-t border-border/40 mt-4">
          {plan === "growth" ? (
            <Button
              variant="outline"
              onClick={() => openPortal()}
              disabled={isOpeningPortal}
              className="w-full mt-4 text-xs font-semibold gap-1.5"
              aria-label="Manage Growth Subscription in Stripe Portal"
            >
              {isOpeningPortal ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : isPastDue ? (
                "Payment Required — Manage Billing"
              ) : (
                <>
                  Manage Billing <ExternalLink className="h-3.5 w-3.5 ml-1" />
                </>
              )}
            </Button>
          ) : (
            <Button
              onClick={() => createCheckout({ plan: "growth" })}
              disabled={isCheckingOut}
              className="w-full mt-4 text-xs font-semibold bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white shadow-lg shadow-indigo-500/25 transition-all"
              aria-label="Upgrade to Growth — $79/month"
            >
              {isCheckingOut ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Redirecting to Stripe...
                </>
              ) : (
                <>
                  Upgrade to Growth — $79/mo
                  <ArrowRight className="ml-2 h-4 w-4" />
                </>
              )}
            </Button>
          )}
        </div>
      </Card>

      {/* 3. ENTERPRISE PLAN */}
      <Card className={`border-border/80 flex flex-col justify-between hover:border-border transition-all ${plan === "enterprise" ? "ring-2 ring-indigo-500/30 bg-card/80" : ""}`}>
        <CardContent className="p-6 space-y-6 flex-1">
          <div className="flex justify-between items-start">
            <div>
              <h3 className="text-lg font-bold text-foreground">Enterprise</h3>
              <p className="text-xs text-muted-foreground mt-1">
                For custom enterprise deployments & scale.
              </p>
            </div>
            {plan === "enterprise" && (
              <Badge variant="info" className="text-[10px] font-semibold tracking-wider uppercase">
                Current Plan
              </Badge>
            )}
          </div>
          <div className="flex items-baseline">
            <span className="text-4xl font-extrabold text-foreground">Custom</span>
            <span className="text-xs text-muted-foreground ml-1.5 font-medium">pricing</span>
          </div>
          <ul className="space-y-2.5 text-xs text-muted-foreground" aria-label="Enterprise Plan Features">
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
              <span>Custom integrations</span>
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
              <span>SSO / SAML authentication</span>
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
              <span>Advanced auditing & compliance logs</span>
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
              <span>Dedicated DuckDB / cloud scaling</span>
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
              <span>SLA support & Enterprise manager</span>
            </li>
          </ul>
        </CardContent>
        <div className="p-6 pt-0 border-t border-border/40 mt-4">
          <Link href="mailto:sales@datapilot.ai?subject=Enterprise%20Plan%20Inquiry" className="w-full">
            <Button
              variant="outline"
              className="w-full mt-4 text-xs font-semibold"
              aria-label="Contact Sales for Enterprise Plan"
            >
              Contact Sales
            </Button>
          </Link>
        </div>
      </Card>
    </div>
  );
}
