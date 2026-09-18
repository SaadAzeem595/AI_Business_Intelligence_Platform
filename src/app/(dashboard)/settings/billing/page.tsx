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
} from "lucide-react";
import { useSubscription } from "@/features/billing/hooks/useSubscription";
import { useBilling } from "@/features/settings/hooks/useBilling";

interface Invoice {
  invoiceId: string;
  amount: string;
  date: string;
  status: "Paid" | "Pending";
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
  } = useSubscription();

  const { invoices, isLoadingInvoices } = useBilling();

  // Polling state when returning from successful checkout
  const [pollingAttempts, setPollingAttempts] = useState(0);
  const [pollSuccess, setPollSuccess] = useState(false);

  useEffect(() => {
    if (checkoutStatus === "success" && plan !== "growth") {
      const interval = setInterval(() => {
        setPollingAttempts((prev) => {
          if (prev < 15) {
            refetch();
            return prev + 1;
          } else {
            clearInterval(interval);
            return prev;
          }
        });
      }, 2000);

      return () => clearInterval(interval);
    } else if (checkoutStatus === "success" && plan === "growth") {
      setPollSuccess(true);
    }
  }, [checkoutStatus, plan, refetch]);

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
      cell: () => (
        <Button
          size="icon"
          variant="ghost"
          className="h-8 w-8 hover:bg-muted text-muted-foreground hover:text-foreground"
          onClick={() => openPortal()}
          title="Download Receipt via Stripe Portal"
        >
          <Download className="h-4 w-4" />
        </Button>
      ),
    },
  ];

  // Helper for status badge variant
  const getStatusBadge = () => {
    if (isGracePeriod) {
      return (
        <Badge variant="warning" className="gap-1">
          <Clock className="h-3 w-3" /> Canceling at period end
        </Badge>
      );
    }
    switch (status) {
      case "active":
        return (
          <Badge variant="success" className="gap-1">
            <CheckCircle2 className="h-3 w-3" /> Active
          </Badge>
        );
      case "past_due":
        return (
          <Badge variant="destructive" className="gap-1">
            <AlertTriangle className="h-3 w-3" /> Past Due
          </Badge>
        );
      case "canceled":
        return (
          <Badge variant="destructive" className="gap-1">
            <XCircle className="h-3 w-3" /> Canceled
          </Badge>
        );
      case "trialing":
        return (
          <Badge variant="info" className="gap-1">
            <Sparkles className="h-3 w-3" /> Trialing
          </Badge>
        );
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

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
      : 15;

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Billing & Subscriptions
          </h1>
          <p className="text-xs text-muted-foreground">
            Manage workspace payment methods, monitor Stripe subscriptions, and inspect usage limits.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            className="text-xs gap-1.5"
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
            >
              {isOpeningPortal ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <ExternalLink className="h-3.5 w-3.5" />
              )}
              Stripe Customer Portal
            </Button>
          )}
        </div>
      </div>

      {/* Checkout Return Banners */}
      {checkoutStatus === "success" && (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-emerald-400 flex items-start gap-3">
          <CheckCircle2 className="h-5 w-5 mt-0.5 shrink-0" />
          <div className="text-xs space-y-1">
            <div className="font-semibold text-sm">
              Payment Completed Successfully!
            </div>
            {plan === "growth" || pollSuccess ? (
              <p>
                Your workspace has been elevated to <strong>Growth Plan</strong>. You now have unlimited datasets and all advanced forecasting, anomalies, and reporting features.
              </p>
            ) : (
              <p className="flex items-center gap-2">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Synchronizing subscription webhook with Stripe (Attempt {pollingAttempts}/15)...
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
              Your checkout session was canceled. Your workspace plan and current quota have not been changed.
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Side: Current Plan & Quota Card */}
        <div className="lg:col-span-1 space-y-6">
          <Card className="border-border/80 shadow-sm relative overflow-hidden">
            {isGrowthOrHigher && (
              <div className="absolute top-0 right-0 left-0 h-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500" />
            )}
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base font-bold flex items-center gap-1.5">
                  <CreditCard className="h-4.5 w-4.5 text-indigo-500" />
                  Current Plan
                </CardTitle>
                {getStatusBadge()}
              </div>
              <CardDescription className="text-xs">
                {plan === "growth"
                  ? "Growth Tier (Full Analytics & Automated Delivery)"
                  : plan === "enterprise"
                  ? "Enterprise Custom Scaled Platform"
                  : "Starter Tier (Core SQL & Single Dataset Sandbox)"}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="flex items-baseline justify-between border-b border-border/40 pb-4">
                <div>
                  <h3 className="text-3xl font-black text-foreground capitalize">
                    {plan === "growth"
                      ? "$79.00"
                      : plan === "enterprise"
                      ? "Custom"
                      : "$0.00"}
                    <span className="text-xs font-normal text-muted-foreground ml-1">
                      {plan === "enterprise" ? "Annual" : "/ month"}
                    </span>
                  </h3>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    Workspace plan: <strong className="text-foreground capitalize">{plan}</strong>
                  </p>
                </div>

                {plan === "starter" ? (
                  <Button
                    size="sm"
                    onClick={() => createCheckout({ plan: "growth" })}
                    disabled={isCheckingOut}
                    className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs font-medium shadow-sm"
                  >
                    {isCheckingOut ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <>
                        Upgrade Now
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
                    className="text-xs"
                  >
                    {isOpeningPortal ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      "Manage Subscription"
                    )}
                  </Button>
                )}
              </div>

              {/* Renewal or Period End Info */}
              {formattedPeriodEnd && (
                <div className="text-xs flex items-center justify-between text-muted-foreground bg-muted/40 p-2.5 rounded-lg border border-border/40">
                  <span className="flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5 text-indigo-400" />
                    {isGracePeriod ? "Access expires on" : "Renews automatically on"}
                  </span>
                  <span className="font-semibold text-foreground">
                    {formattedPeriodEnd}
                  </span>
                </div>
              )}

              {/* Real Dataset Usage Limits */}
              <div className="space-y-3 pt-1 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                    <Database className="h-3 w-3" /> Dataset Quota
                  </span>
                  <span className="font-medium">
                    {datasetUsage.current} /{" "}
                    {datasetUsage.limit === null ? "Unlimited" : datasetUsage.limit}
                  </span>
                </div>

                <div className="h-2 w-full bg-muted/70 rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all duration-500 rounded-full ${
                      isAtDatasetLimit
                        ? "bg-amber-500"
                        : "bg-indigo-500"
                    }`}
                    style={{ width: `${datasetPct}%` }}
                  />
                </div>

                {isAtDatasetLimit && plan === "starter" && (
                  <div className="text-[11px] text-amber-500 bg-amber-500/10 p-2 rounded border border-amber-500/20">
                    Dataset capacity limit reached (1/1). Upgrade to Growth to upload unlimited datasets.
                  </div>
                )}
              </div>

              {/* Entitlement Checklist */}
              <div className="space-y-2 pt-3 border-t border-border/40 text-xs">
                <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                  Workspace Capabilities
                </span>
                <ul className="space-y-1.5">
                  <li className="flex items-center gap-2 text-muted-foreground">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                    <span>DuckDB & SQL Playground Engine</span>
                  </li>
                  <li className="flex items-center gap-2 text-muted-foreground">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                    <span>Standard AI Chat Assistant</span>
                  </li>
                  <li className={`flex items-center gap-2 ${isGrowthOrHigher ? "text-muted-foreground" : "text-muted-foreground/50"}`}>
                    <CheckCircle2 className={`h-3.5 w-3.5 shrink-0 ${isGrowthOrHigher ? "text-emerald-500" : "text-muted-foreground/30"}`} />
                    <span>Advanced Trend Forecasting (ARIMA & Prophet)</span>
                  </li>
                  <li className={`flex items-center gap-2 ${isGrowthOrHigher ? "text-muted-foreground" : "text-muted-foreground/50"}`}>
                    <CheckCircle2 className={`h-3.5 w-3.5 shrink-0 ${isGrowthOrHigher ? "text-emerald-500" : "text-muted-foreground/30"}`} />
                    <span>Multi-variate Anomaly Detection</span>
                  </li>
                  <li className={`flex items-center gap-2 ${isGrowthOrHigher ? "text-muted-foreground" : "text-muted-foreground/50"}`}>
                    <CheckCircle2 className={`h-3.5 w-3.5 shrink-0 ${isGrowthOrHigher ? "text-emerald-500" : "text-muted-foreground/30"}`} />
                    <span>Scheduled Automated Reports (PDF & PPTX)</span>
                  </li>
                  <li className={`flex items-center gap-2 ${isGrowthOrHigher ? "text-muted-foreground" : "text-muted-foreground/50"}`}>
                    <CheckCircle2 className={`h-3.5 w-3.5 shrink-0 ${isGrowthOrHigher ? "text-emerald-500" : "text-muted-foreground/30"}`} />
                    <span>Workspace Team Collaboration</span>
                  </li>
                </ul>
              </div>

              <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground/80 pt-2 border-t border-border/40">
                <ShieldCheck className="h-4 w-4 text-emerald-500 shrink-0" />
                <span>Encrypted & handled via Stripe PCI-compliant servers</span>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Side: Available Plans Matrix & Invoices */}
        <div className="lg:col-span-2 space-y-6">
          {/* Plan Comparison Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Starter Plan Card */}
            <Card className={`border-border/80 ${plan === "starter" ? "ring-2 ring-indigo-500/40 bg-card/60" : ""}`}>
              <CardHeader className="pb-2">
                <div className="flex justify-between items-start">
                  <div>
                    <CardTitle className="text-base font-bold">Starter</CardTitle>
                    <CardDescription className="text-xs">For individuals & exploratory testing</CardDescription>
                  </div>
                  {plan === "starter" && <Badge variant="secondary">Current Plan</Badge>}
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="text-2xl font-bold">
                  $0 <span className="text-xs font-normal text-muted-foreground">/ month</span>
                </div>
                <ul className="text-xs space-y-1.5 text-muted-foreground">
                  <li className="flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" /> 1 Active Dataset
                  </li>
                  <li className="flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" /> DuckDB SQL Querying
                  </li>
                  <li className="flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" /> Standard AI Chat
                  </li>
                  <li className="flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" /> Ad-hoc Report Generation
                  </li>
                </ul>
                <Button
                  variant="outline"
                  className="w-full text-xs"
                  disabled={plan === "starter"}
                >
                  {plan === "starter" ? "Active" : "Included"}
                </Button>
              </CardContent>
            </Card>

            {/* Growth Plan Card */}
            <Card className={`border-indigo-500/40 relative overflow-hidden bg-gradient-to-b from-indigo-500/5 to-transparent ${plan === "growth" ? "ring-2 ring-indigo-500" : ""}`}>
              <div className="absolute top-3 right-3">
                <Badge variant="info" className="gap-1 font-semibold text-[10px]">
                  <Sparkles className="h-3 w-3" /> Popular
                </Badge>
              </div>
              <CardHeader className="pb-2">
                <div className="flex justify-between items-start">
                  <div>
                    <CardTitle className="text-base font-bold">Growth</CardTitle>
                    <CardDescription className="text-xs">For growing analytics teams & companies</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="text-2xl font-bold text-indigo-400">
                  $79 <span className="text-xs font-normal text-muted-foreground">/ month</span>
                </div>
                <ul className="text-xs space-y-1.5 text-muted-foreground">
                  <li className="flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-indigo-400 shrink-0" /> Unlimited Datasets
                  </li>
                  <li className="flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-indigo-400 shrink-0" /> ARIMA & Prophet Forecasting
                  </li>
                  <li className="flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-indigo-400 shrink-0" /> Multi-variate Anomaly Detection
                  </li>
                  <li className="flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-indigo-400 shrink-0" /> Automated Schedule Reports
                  </li>
                  <li className="flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-indigo-400 shrink-0" /> Shared Workspace Collaboration
                  </li>
                </ul>

                {plan === "growth" ? (
                  <Button
                    variant="outline"
                    className="w-full text-xs"
                    onClick={() => openPortal()}
                    disabled={isOpeningPortal}
                  >
                    Manage in Stripe Portal
                  </Button>
                ) : (
                  <Button
                    onClick={() => createCheckout({ plan: "growth" })}
                    disabled={isCheckingOut}
                    className="w-full text-xs bg-indigo-600 hover:bg-indigo-500 text-white font-medium"
                  >
                    {isCheckingOut ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      "Upgrade to Growth"
                    )}
                  </Button>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Invoices History Table */}
          <div className="space-y-3 pt-2">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold tracking-tight text-foreground">
                Invoices & Payment Receipts
              </h2>
              {subscription?.stripe_customer_id && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => openPortal()}
                  className="text-xs text-indigo-400 hover:text-indigo-300"
                >
                  View All in Stripe Portal <ArrowRight className="ml-1 h-3 w-3" />
                </Button>
              )}
            </div>
            <BaseTable
              columns={columns as any}
              data={invoices}
              isLoading={isLoadingInvoices}
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
