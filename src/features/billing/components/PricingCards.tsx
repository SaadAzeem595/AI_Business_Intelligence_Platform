"use client";

import React from "react";
import Link from "next/link";
import { CheckCircle2, Sparkles, ArrowRight, Loader2, CreditCard } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import { Card, CardContent } from "@/shared/components/ui/card";
import { Badge } from "@/shared/components/ui/badge";
import { useSubscription } from "../hooks/useSubscription";

export function PricingCards() {
  const {
    plan,
    isGrowthOrHigher,
    createCheckout,
    isCheckingOut,
    openPortal,
    isOpeningPortal,
  } = useSubscription();

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
      {/* Starter Tier */}
      <Card className="border-border/80 flex flex-col justify-between hover:border-border transition-colors">
        <CardContent className="p-6 space-y-6 flex-1">
          <div className="flex justify-between items-start">
            <div>
              <h3 className="text-base font-bold text-foreground">Starter</h3>
              <p className="text-xs text-muted-foreground mt-1">
                For individual analysts testing the engine.
              </p>
            </div>
            {plan === "starter" && (
              <Badge variant="secondary" className="text-[10px]">Current Plan</Badge>
            )}
          </div>
          <div className="flex items-baseline">
            <span className="text-3xl font-extrabold">$0</span>
            <span className="text-xs text-muted-foreground ml-1">/ month</span>
          </div>
          <ul className="space-y-2 text-xs text-muted-foreground">
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" /> 1 active dataset file
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" /> Basic SQL Playground
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" /> Standard AI Chat queries
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" /> Ad-hoc Report Generation
            </li>
          </ul>
        </CardContent>
        <div className="p-6 pt-0 border-t border-border/40 mt-4">
          <Link href="/dashboard" className="w-full">
            <Button variant="outline" className="w-full mt-4">
              {plan === "starter" ? "Go to Dashboard" : "Switch to Starter"}
            </Button>
          </Link>
        </div>
      </Card>

      {/* Growth Tier */}
      <Card className="border-brand-indigo/50 border-2 bg-brand-indigo/5 flex flex-col justify-between relative shadow-lg shadow-indigo-500/5">
        <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 px-2.5 py-0.5 rounded-full bg-brand-indigo text-[10px] font-bold text-brand-indigo-foreground uppercase tracking-wider flex items-center gap-1">
          <Sparkles className="h-3 w-3" /> Most Popular
        </div>
        <CardContent className="p-6 space-y-6 flex-1 pt-8">
          <div className="flex justify-between items-start">
            <div>
              <h3 className="text-base font-bold text-foreground">Growth</h3>
              <p className="text-xs text-muted-foreground mt-1">
                For scaling businesses and data departments.
              </p>
            </div>
            {plan === "growth" && (
              <Badge variant="info" className="text-[10px]">Current Plan</Badge>
            )}
          </div>
          <div className="flex items-baseline">
            <span className="text-3xl font-extrabold text-foreground">$79</span>
            <span className="text-xs text-muted-foreground ml-1">/ month</span>
          </div>
          <ul className="space-y-2 text-xs text-muted-foreground">
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" /> Unlimited datasets uploading
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" /> Advanced Forecasting & Outliers
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" /> Scheduled Executive PDF reports
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" /> Shared team collaboration spaces
            </li>
          </ul>
        </CardContent>
        <div className="p-6 pt-0 border-t border-border/40 mt-4">
          {plan === "growth" ? (
            <Button
              variant="outline"
              onClick={() => openPortal()}
              disabled={isOpeningPortal}
              className="w-full mt-4"
            >
              {isOpeningPortal ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Manage in Stripe Portal"
              )}
            </Button>
          ) : (
            <Button
              variant="brand"
              onClick={() => createCheckout({ plan: "growth" })}
              disabled={isCheckingOut}
              className="w-full mt-4 shadow-md shadow-indigo-500/20"
            >
              {isCheckingOut ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Redirecting to Stripe...
                </>
              ) : (
                <>
                  Upgrade Now
                  <ArrowRight className="ml-2 h-4 w-4" />
                </>
              )}
            </Button>
          )}
        </div>
      </Card>

      {/* Enterprise Tier */}
      <Card className="border-border/80 flex flex-col justify-between hover:border-border transition-colors">
        <CardContent className="p-6 space-y-6 flex-1">
          <div className="flex justify-between items-start">
            <div>
              <h3 className="text-base font-bold text-foreground">Enterprise</h3>
              <p className="text-xs text-muted-foreground mt-1">
                For multi-tenant compliance and custom setups.
              </p>
            </div>
            {plan === "enterprise" && (
              <Badge variant="info" className="text-[10px]">Current Plan</Badge>
            )}
          </div>
          <div className="flex items-baseline">
            <span className="text-3xl font-extrabold text-foreground">Custom</span>
          </div>
          <ul className="space-y-2 text-xs text-muted-foreground">
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" /> Custom integrations
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" /> SSO, SAML, & Auditing keys
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" /> Dedicated DuckDB cloud scaling
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" /> SLA support guarantees
            </li>
          </ul>
        </CardContent>
        <div className="p-6 pt-0 border-t border-border/40 mt-4">
          <Link href="mailto:sales@datapilot.ai?subject=Enterprise%20Inquiry" className="w-full">
            <Button variant="outline" className="w-full mt-4">
              Contact Sales
            </Button>
          </Link>
        </div>
      </Card>
    </div>
  );
}
