"use client";

import React, { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";
import { BaseTable, type Column } from "@/shared/components/data-display/BaseTable";
import {
  CreditCard,
  CheckCircle2,
  ShieldCheck,
  Download,
  Sparkles,
  ArrowRight,
  ExternalLink,
  AlertTriangle,
  RefreshCw,
  Loader2,
  XCircle,
  Database,
  Layers,
  Clock,
  Receipt,
  Calendar,
  Lock,
} from "lucide-react";
import { useSubscription } from "@/features/billing/hooks/useSubscription";
import { useBilling } from "@/features/settings/hooks/useBilling";

interface Invoice {
  invoiceId: string;
  amount: string;
  date: string;
  status: string;
  hosted_invoice_url?: string | null;
  invoice_pdf?: string | null;
}

function BillingContent() {
  const searchParams = useSearchParams();
  const checkoutStatus = searchParams.get("checkout");
  const sessionId = searchParams.get("session_id");

  const {
    subscription,
    usage,
    isLoading,
    isError,
    plan,
    status,
    isGrowthOrHigher,
    isGracePeriod,
    currentPeriodEnd,
    datasetUsage,
    isAtDatasetLimit,
    createCheckout,
    isCheckingOut,
    openPortal,
    isOpeningPortal,
    refetch,
    syncSubscription,
  } = useSubscription();

  const { invoices, isLoadingInvoices } = useBilling();

  // Polling state when returning from checkout
  const [pollingAttempts, setPollingAttempts] = useState(0);
  const [syncTimeout, setSyncTimeout] = useState(false);

  useEffect(() => {
    if (checkoutStatus === "success" && plan !== "growth") {
      let currentAttempt = 0;
      const maxAttempts = 10;
      let timer: NodeJS.Timeout;

      const runPoll = async () => {
        currentAttempt += 1;
        setPollingAttempts(currentAttempt);
        try {
          await syncSubscription();
        } catch {
          // ignore error while polling
        }

        if (currentAttempt < maxAttempts) {
          const delay = Math.min(1500 + currentAttempt * 500, 4000);
          timer = setTimeout(runPoll, delay);
        } else {
          setSyncTimeout(true);
        }
      };

      timer = setTimeout(runPoll, 1000);
      return () => clearTimeout(timer);
    }
  }, [checkoutStatus, plan, syncSubscription]);

  // Requirement 37: Loading state must show skeleton and NOT temporarily show Starter
  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse" aria-label="Loading billing information">
        <div className="flex flex-col sm:flex-row justify-between gap-4">
          <div className="space-y-2">
            <div className="h-7 w-64 bg-muted/60 rounded" />
            <div className="h-4 w-96 bg-muted/40 rounded" />
          </div>
          <div className="flex items-center gap-2">
            <div className="h-8 w-24 bg-muted/50 rounded" />
            <div className="h-8 w-36 bg-muted/50 rounded" />
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1 space-y-6">
            <Card className="border-border/60 bg-card/40 p-6 h-[460px] flex flex-col justify-between">
              <div className="space-y-4">
                <div className="h-5 w-32 bg-muted/60 rounded" />
                <div className="h-10 w-44 bg-muted/60 rounded" />
                <div className="h-4 w-28 bg-muted/40 rounded" />
                <div className="space-y-2 pt-6">
                  <div className="h-4 w-full bg-muted/40 rounded" />
                  <div className="h-4 w-5/6 bg-muted/40 rounded" />
                  <div className="h-4 w-4/6 bg-muted/40 rounded" />
                </div>
              </div>
              <div className="h-10 w-full bg-muted/50 rounded" />
            </Card>
          </div>
          <div className="lg:col-span-2 space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card className="border-border/60 bg-card/40 p-6 h-[280px]" />
              <Card className="border-border/60 bg-card/40 p-6 h-[280px]" />
            </div>
            <Card className="border-border/60 bg-card/40 p-6 h-[220px]" />
          </div>
        </div>
      </div>
    );
  }

  const columns: Column<Invoice>[] = [
    {
      header: "Invoice Number",
      accessorKey: "invoiceId",
      cell: (row) => (
        <span className="font-semibold text-foreground">{row.invoiceId}</span>
      ),
    },
    { header: "Billing Date", accessorKey: "date" },
    { header: "Amount Paid", accessorKey: "amount" },
    {
      header: "Status",
      accessorKey: "status",
      cell: (row) => (
        <Badge variant={row.status === "Paid" ? "success" : "warning"}>
          {row.status}
        </Badge>
      ),
    },
    {
      header: "Receipt",
      accessorKey: "receipt",
      align: "right",
      cell: (row) => {
        if (row.hosted_invoice_url || row.invoice_pdf) {
          return (
            <a
              href={row.hosted_invoice_url || row.invoice_pdf || "#"}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center h-8 w-8 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
              title="View Invoice Receipt on Stripe"
            >
              <ExternalLink className="h-4 w-4" />
            </a>
          );
        }
        return (
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 hover:bg-muted text-muted-foreground hover:text-foreground"
            onClick={() => openPortal()}
            title="Manage in Stripe Portal"
          >
            <Download className="h-4 w-4" />
          </Button>
        );
      },
    },
  ];

  // Helper for status badge variant
  const getStatusBadge = () => {
    if (isGracePeriod) {
      return (
        <Badge variant="warning" className="gap-1 font-semibold text-[11px]">
          <Clock className="h-3 w-3" /> Active — Cancels at end of period
        </Badge>
      );
    }
    switch (status) {
      case "active":
        return (
          <Badge variant="success" className="gap-1 font-semibold text-[11px]">
            <CheckCircle2 className="h-3 w-3" /> Active
          </Badge>
        );
      case "past_due":
        return (
          <Badge variant="destructive" className="gap-1 font-semibold text-[11px]">
            <AlertTriangle className="h-3 w-3" /> Payment Issue
          </Badge>
        );
      case "canceled":
        return (
          <Badge variant="destructive" className="gap-1 font-semibold text-[11px]">
            <XCircle className="h-3 w-3" /> Canceled
          </Badge>
        );
      case "trialing":
        return (
          <Badge variant="info" className="gap-1 font-semibold text-[11px]">
            <Sparkles className="h-3 w-3" /> Trialing
          </Badge>
        );
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  const formattedPeriodStart = subscription?.current_period_start
    ? new Date(subscription.current_period_start).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : null;

  const formattedPeriodEnd = currentPeriodEnd
    ? new Date(currentPeriodEnd).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : null;

  const datasetPct =
    datasetUsage.limit !== null
      ? Math.min(100, Math.round((datasetUsage.current / datasetUsage.limit) * 100))
      : 20;

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Billing & Subscriptions
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Manage workspace payment methods, monitor Stripe subscriptions, and inspect real dataset usage.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            className="text-xs gap-1.5"
            aria-label="Refresh Subscription State"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </Button>
          {subscription?.stripe_customer_id && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => openPortal()}
              disabled={isOpeningPortal}
              className="text-xs gap-1.5"
              aria-label="Open Stripe Customer Portal"
            >
              {isOpeningPortal ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <ExternalLink className="h-3.5 w-3.5" />
              )}
              Manage Billing
            </Button>
          )}
        </div>
      </div>

      {/* Checkout Return Banners (Requirement 20) */}
      {checkoutStatus === "success" && (
        <div
          className={`rounded-xl border p-4 flex items-start gap-3 transition-colors ${
            plan === "growth"
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
              : syncTimeout
              ? "border-amber-500/30 bg-amber-500/10 text-amber-400"
              : "border-indigo-500/30 bg-indigo-500/10 text-indigo-400"
          }`}
          role="status"
        >
          {plan === "growth" ? (
            <CheckCircle2 className="h-5 w-5 mt-0.5 shrink-0 text-emerald-400" />
          ) : syncTimeout ? (
            <AlertTriangle className="h-5 w-5 mt-0.5 shrink-0 text-amber-400" />
          ) : (
            <Loader2 className="h-5 w-5 mt-0.5 shrink-0 animate-spin text-indigo-400" />
          )}
          <div className="text-xs space-y-1">
            <div className="font-semibold text-sm">
              {plan === "growth"
                ? "Your Growth plan is now active."
                : syncTimeout
                ? "Payment was received, but your subscription is still being synchronized."
                : "Payment received. Confirming your subscription..."}
            </div>
            {plan === "growth" ? (
              <p>
                Your workspace has been elevated to the <strong>Growth Plan</strong>. You now have unlimited datasets and immediate access to Advanced Forecasting, Anomaly Detection, and Scheduled Executive Reports.
              </p>
            ) : syncTimeout ? (
              <div className="space-y-1.5">
                <p>
                  Your plan will update automatically once Stripe webhook confirmation completes. You can also re-check status right now.
                </p>
                <div className="pt-1 flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setSyncTimeout(false);
                      refetch();
                    }}
                    className="text-xs h-7 gap-1"
                  >
                    <RefreshCw className="h-3 w-3" /> Re-check Status
                  </Button>
                  {subscription?.stripe_customer_id && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => openPortal()}
                      className="text-xs h-7 gap-1"
                    >
                      <ExternalLink className="h-3 w-3" /> Open Stripe Portal
                    </Button>
                  )}
                </div>
              </div>
            ) : (
              <p className="flex items-center gap-2">
                Synchronizing with Stripe (Attempt {pollingAttempts}/10)...
              </p>
            )}
          </div>
        </div>
      )}

      {checkoutStatus === "cancelled" && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-amber-400 flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 mt-0.5 shrink-0" />
          <div className="text-xs space-y-1">
            <div className="font-semibold text-sm">Checkout Cancelled</div>
            <p>
              Your checkout session was canceled. Your workspace plan and quota remain unchanged.
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Side: CURRENT SUBSCRIPTION & YOUR PLAN Card (Requirement 16 & 23) */}
        <div className="lg:col-span-1 space-y-6">
          <Card className="border-border/80 shadow-md relative overflow-hidden bg-card/90">
            {isGrowthOrHigher && (
              <div className="absolute top-0 right-0 left-0 h-1.5 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500" />
            )}
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                  <CreditCard className="h-4 w-4 text-indigo-400" />
                  Current Subscription
                </CardTitle>
                {getStatusBadge()}
              </div>
              <CardDescription className="text-xs">
                {isGracePeriod
                  ? "Growth — Cancels at end of billing period"
                  : plan === "growth"
                  ? "Growth Plan (Full analytics, forecasting & unlimited capacity)"
                  : plan === "enterprise"
                  ? "Enterprise Custom Platform"
                  : "Starter Plan (Exploratory analytics & single dataset sandbox)"}
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-5">
              {/* Plan Name & Pricing */}
              <div className="flex items-baseline justify-between border-b border-border/40 pb-4">
                <div>
                  <h3 className="text-3xl font-black text-foreground capitalize">
                    {plan === "growth" || isGracePeriod
                      ? "$79"
                      : plan === "enterprise"
                      ? "Custom"
                      : "$0"}
                    <span className="text-xs font-normal text-muted-foreground ml-1">
                      {plan === "enterprise" ? "pricing" : "/ month"}
                    </span>
                  </h3>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    Plan: <strong className="text-foreground capitalize">{isGracePeriod ? "Growth (Canceling)" : plan}</strong>
                  </p>
                </div>

                {plan === "starter" ? (
                  <Button
                    size="sm"
                    onClick={() => createCheckout({ plan: "growth" })}
                    disabled={isCheckingOut}
                    className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs font-semibold shadow-md shadow-indigo-500/20"
                    aria-label="Upgrade to Growth — $79/month"
                  >
                    {isCheckingOut ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <>
                        Upgrade to Growth
                        <ArrowRight className="ml-1 h-3.5 w-3.5" />
                      </>
                    )}
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => openPortal()}
                    disabled={isOpeningPortal}
                    className="text-xs gap-1"
                    aria-label="Manage Billing in Stripe Portal"
                  >
                    {isOpeningPortal ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <>
                        Manage Billing <ExternalLink className="h-3 w-3 ml-0.5" />
                      </>
                    )}
                  </Button>
                )}
              </div>

              {/* Requirement 16: Billing Period & Renewal Date */}
              {(formattedPeriodStart || formattedPeriodEnd) && (
                <div className="space-y-2 bg-muted/30 p-3 rounded-lg border border-border/40 text-xs">
                  {formattedPeriodStart && formattedPeriodEnd && (
                    <div className="flex items-center justify-between text-muted-foreground">
                      <span>Billing period:</span>
                      <span className="font-medium text-foreground">
                        {formattedPeriodStart} – {formattedPeriodEnd}
                      </span>
                    </div>
                  )}

                  {formattedPeriodEnd && (
                    <div className="flex items-center justify-between text-muted-foreground">
                      <span>{isGracePeriod ? "Access until:" : "Next billing date:"}</span>
                      <span className="font-semibold text-foreground">
                        {formattedPeriodEnd}
                      </span>
                    </div>
                  )}
                </div>
              )}

              {/* Requirement 22: Real Dataset Usage Section */}
              <div className="space-y-3 pt-1 text-xs" role="region" aria-label="Usage Metrics">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                    <Database className="h-3 w-3 text-indigo-400" /> Datasets
                  </span>
                  <span className="font-semibold text-foreground">
                    {datasetUsage.current} /{" "}
                    {datasetUsage.limit === null ? "Unlimited" : datasetUsage.limit}
                  </span>
                </div>

                <div className="h-2 w-full bg-muted/60 rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all duration-500 rounded-full ${
                      isAtDatasetLimit && plan === "starter"
                        ? "bg-amber-500"
                        : "bg-indigo-500"
                    }`}
                    style={{ width: `${plan === "starter" ? datasetPct : 15}%` }}
                  />
                </div>

                {isAtDatasetLimit && plan === "starter" && (
                  <div className="text-[11px] text-amber-400 bg-amber-500/10 p-2.5 rounded-lg border border-amber-500/20 flex items-start gap-2">
                    <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                    <span>
                      Dataset quota reached (1/1). Upgrade to Growth for unlimited datasets.
                    </span>
                  </div>
                )}
              </div>

              {/* Requirement 23: YOUR PLAN Entitlements Checklist */}
              <div className="space-y-2 pt-3 border-t border-border/40 text-xs">
                <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                  Your Plan Capabilities
                </span>
                <ul className="space-y-2">
                  <li className="flex items-center gap-2 text-muted-foreground">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                    <span>DuckDB & SQL Playground Engine</span>
                  </li>
                  <li className="flex items-center gap-2 text-muted-foreground">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                    <span>Standard AI Chat Assistant</span>
                  </li>
                  <li className={`flex items-center gap-2 ${isGrowthOrHigher ? "text-foreground font-medium" : "text-muted-foreground/40"}`}>
                    <CheckCircle2 className={`h-3.5 w-3.5 shrink-0 ${isGrowthOrHigher ? "text-emerald-500" : "text-muted-foreground/30"}`} />
                    <span>Advanced Forecasting (ARIMA & Prophet)</span>
                  </li>
                  <li className={`flex items-center gap-2 ${isGrowthOrHigher ? "text-foreground font-medium" : "text-muted-foreground/40"}`}>
                    <CheckCircle2 className={`h-3.5 w-3.5 shrink-0 ${isGrowthOrHigher ? "text-emerald-500" : "text-muted-foreground/30"}`} />
                    <span>Advanced Anomaly Detection / Outliers</span>
                  </li>
                  <li className={`flex items-center gap-2 ${isGrowthOrHigher ? "text-foreground font-medium" : "text-muted-foreground/40"}`}>
                    <CheckCircle2 className={`h-3.5 w-3.5 shrink-0 ${isGrowthOrHigher ? "text-emerald-500" : "text-muted-foreground/30"}`} />
                    <span>Scheduled Executive Reports (PDF & PPTX)</span>
                  </li>
                  <li className={`flex items-center gap-2 ${isGrowthOrHigher ? "text-foreground font-medium" : "text-muted-foreground/40"}`}>
                    <CheckCircle2 className={`h-3.5 w-3.5 shrink-0 ${isGrowthOrHigher ? "text-emerald-500" : "text-muted-foreground/30"}`} />
                    <span>Team Collaboration Spaces</span>
                  </li>
                </ul>
              </div>

              <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground/80 pt-2 border-t border-border/40">
                <ShieldCheck className="h-4 w-4 text-emerald-500 shrink-0" />
                <span>PCI-DSS compliant via Stripe encrypted processing</span>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Side: Available Plans Matrix & Real Invoice History */}
        <div className="lg:col-span-2 space-y-6">
          {/* Plan Comparison Cards (Requirement 18 & 36) */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Starter Plan Card */}
            <Card className={`border-border/80 ${plan === "starter" ? "ring-2 ring-indigo-500/40 bg-card/80" : ""}`}>
              <CardHeader className="pb-2">
                <div className="flex justify-between items-start">
                  <div>
                    <CardTitle className="text-base font-bold">Starter</CardTitle>
                    <CardDescription className="text-xs">For individual analysts testing the engine</CardDescription>
                  </div>
                  {plan === "starter" && (
                    <Badge variant="secondary" className="text-[10px] uppercase font-semibold">Current Plan</Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="text-2xl font-bold">
                  $0 <span className="text-xs font-normal text-muted-foreground">/ month</span>
                </div>
                <ul className="text-xs space-y-2 text-muted-foreground">
                  <li className="flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" /> 1 Active Dataset
                  </li>
                  <li className="flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" /> Basic SQL Playground
                  </li>
                  <li className="flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" /> Standard AI Chat
                  </li>
                </ul>
                <Button
                  variant="outline"
                  className="w-full text-xs"
                  disabled={plan === "starter"}
                  aria-label={plan === "starter" ? "Current Plan" : "Included"}
                >
                  {plan === "starter" ? "Current Plan" : "Included"}
                </Button>
              </CardContent>
            </Card>

            {/* Growth Plan Card */}
            <Card
              className={`border-indigo-500/40 relative overflow-hidden bg-gradient-to-b from-indigo-500/10 to-transparent ${
                plan === "growth" ? "ring-2 ring-indigo-500" : ""
              }`}
            >
              <div className="absolute top-3 right-3">
                <Badge variant="info" className="gap-1 font-semibold text-[10px]">
                  <Sparkles className="h-3 w-3" /> Most Popular
                </Badge>
              </div>
              <CardHeader className="pb-2">
                <div className="flex justify-between items-start">
                  <div>
                    <CardTitle className="text-base font-bold">Growth</CardTitle>
                    <CardDescription className="text-xs">For scaling businesses and data departments</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="text-2xl font-bold text-indigo-400">
                  $79 <span className="text-xs font-normal text-muted-foreground">/ month</span>
                </div>
                <ul className="text-xs space-y-2 text-muted-foreground">
                  <li className="flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-indigo-400 shrink-0" /> Unlimited Datasets
                  </li>
                  <li className="flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-indigo-400 shrink-0" /> Advanced Forecasting (ARIMA/Prophet)
                  </li>
                  <li className="flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-indigo-400 shrink-0" /> Advanced Anomaly Detection
                  </li>
                  <li className="flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-indigo-400 shrink-0" /> Scheduled Executive Reports
                  </li>
                  <li className="flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-indigo-400 shrink-0" /> Team Collaboration
                  </li>
                </ul>

                {plan === "growth" ? (
                  <Button
                    variant="outline"
                    className="w-full text-xs font-semibold gap-1"
                    onClick={() => openPortal()}
                    disabled={isOpeningPortal}
                    aria-label="Manage Billing in Stripe Portal"
                  >
                    {isOpeningPortal ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <>
                        Manage Billing <ExternalLink className="h-3 w-3 ml-0.5" />
                      </>
                    )}
                  </Button>
                ) : (
                  <Button
                    onClick={() => createCheckout({ plan: "growth" })}
                    disabled={isCheckingOut}
                    className="w-full text-xs bg-indigo-600 hover:bg-indigo-500 text-white font-semibold shadow-md shadow-indigo-500/20"
                    aria-label="Upgrade to Growth — $79/month"
                  >
                    {isCheckingOut ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      "Upgrade to Growth — $79/mo"
                    )}
                  </Button>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Real Invoice History Table (Requirement 29) */}
          <div className="space-y-3 pt-2">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold tracking-tight text-foreground flex items-center gap-1.5">
                <Receipt className="h-4 w-4 text-indigo-400" />
                Invoices & Payment Receipts
              </h2>
              {subscription?.stripe_customer_id && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => openPortal()}
                  className="text-xs text-indigo-400 hover:text-indigo-300 gap-1"
                  aria-label="Open Stripe Customer Portal for all past receipts"
                >
                  Stripe Portal <ExternalLink className="h-3 w-3" />
                </Button>
              )}
            </div>

            <BaseTable
              columns={columns as any}
              data={invoices}
              isLoading={isLoadingInvoices}
              emptyState={
                <div className="flex flex-col items-center justify-center space-y-2 py-8 text-center">
                  <Receipt className="h-8 w-8 text-muted-foreground/30" />
                  <p className="text-sm font-medium text-foreground">No invoices yet.</p>
                  <p className="text-xs text-muted-foreground">
                    Real Stripe payment receipts will appear here automatically upon completed billing cycles.
                  </p>
                </div>
              }
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default function BillingSettingsPage() {
  return (
    <Suspense
      fallback={
        <div className="p-8 flex items-center justify-center text-muted-foreground text-sm">
          <Loader2 className="h-5 w-5 animate-spin mr-2" />
          Loading billing workspace...
        </div>
      }
    >
      <BillingContent />
    </Suspense>
  );
}
