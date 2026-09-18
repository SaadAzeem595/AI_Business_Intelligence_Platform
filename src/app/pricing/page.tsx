"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, ShieldCheck, Sparkles } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import { PricingCards } from "@/features/billing/components/PricingCards";

export default function PricingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col selection:bg-brand-indigo/30">
      {/* Top Navigation */}
      <header className="border-b border-border/80 sticky top-0 bg-background/80 backdrop-blur-md z-50 px-6 md:px-12 py-4 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <Link
            href="/"
            className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-4 w-4" /> Back to Home
          </Link>
          <div className="h-4 w-px bg-border/80 hidden sm:block" />
          <span className="font-bold text-base tracking-tight hidden sm:block">
            DataPilot AI
          </span>
        </div>

        <div className="flex items-center gap-3">
          <Link href="/sign-in">
            <Button variant="ghost" size="sm" className="text-xs">
              Sign In
            </Button>
          </Link>
          <Link href="/dashboard">
            <Button variant="brand" size="sm" className="text-xs">
              Open Dashboard
            </Button>
          </Link>
        </div>
      </header>

      {/* Hero Section */}
      <main className="flex-1 py-16 px-6 md:px-12 max-w-6xl mx-auto w-full space-y-16">
        <div className="text-center space-y-4 max-w-2xl mx-auto">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-brand-indigo/10 border border-brand-indigo/20 text-brand-indigo text-xs font-semibold">
            <Sparkles className="h-3.5 w-3.5" /> Flexible SaaS Subscription Plans
          </div>
          <h1 className="text-3xl md:text-5xl font-extrabold tracking-tight">
            Transparent Pricing for Modern Analytics
          </h1>
          <p className="text-sm text-muted-foreground">
            Scale seamlessly from single-analyst exploratory tests to full executive forecasting and enterprise data governance. Cancel or upgrade anytime with Stripe.
          </p>
        </div>

        {/* Pricing Cards Grid */}
        <PricingCards />

        {/* FAQ Section */}
        <div className="max-w-3xl mx-auto space-y-8 pt-12 border-t border-border/60">
          <h2 className="text-xl font-bold tracking-tight text-center">
            Frequently Asked Questions
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
            <div className="space-y-1.5 p-4 rounded-xl border border-border/60 bg-card/50">
              <h3 className="font-semibold text-foreground text-sm">
                Can I cancel my subscription anytime?
              </h3>
              <p className="text-muted-foreground leading-relaxed">
                Yes. You can cancel at any time from your Billing Settings via the Stripe Customer Portal. Your Growth tier features will remain active until the end of your paid billing period.
              </p>
            </div>
            <div className="space-y-1.5 p-4 rounded-xl border border-border/60 bg-card/50">
              <h3 className="font-semibold text-foreground text-sm">
                How does dataset quota work?
              </h3>
              <p className="text-muted-foreground leading-relaxed">
                The Starter plan allows 1 active uploaded dataset for exploratory queries. The Growth plan provides unlimited active dataset uploads, persistent tables, and multi-sheet joins.
              </p>
            </div>
            <div className="space-y-1.5 p-4 rounded-xl border border-border/60 bg-card/50">
              <h3 className="font-semibold text-foreground text-sm">
                Is my payment data secure?
              </h3>
              <p className="text-muted-foreground leading-relaxed">
                Absolutely. All credit card processing and billing transactions are securely handled directly by Stripe. DataPilot AI never stores or touches sensitive credit card numbers.
              </p>
            </div>
            <div className="space-y-1.5 p-4 rounded-xl border border-border/60 bg-card/50">
              <h3 className="font-semibold text-foreground text-sm">
                Do team members share the workspace plan?
              </h3>
              <p className="text-muted-foreground leading-relaxed">
                Yes. Subscriptions are workspace-scoped. When a workspace is on Growth, all analysts and members within that workspace receive full Growth capabilities.
              </p>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border/80 bg-card py-8 px-6 text-center text-xs text-muted-foreground">
        <p>© {new Date().getFullYear()} DataPilot AI Inc. Production-grade Stripe billing architecture.</p>
      </footer>
    </div>
  );
}
