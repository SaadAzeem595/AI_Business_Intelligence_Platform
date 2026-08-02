"use client";

import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";
import { BaseTable, type Column } from "@/shared/components/data-display/BaseTable";
import { CreditCard, CheckCircle2, ShieldCheck, Download } from "lucide-react";

interface Invoice {
  invoiceId: string;
  amount: string;
  date: string;
  status: "Paid" | "Pending";
}

import { useBilling } from "@/features/settings/hooks/useBilling";

export default function BillingSettingsPage() {
  const [activePlan, setActivePlan] = useState<"Free" | "Growth" | "Enterprise">("Growth");

  const { invoices, isLoadingInvoices, updateBilling, isUpdatingBilling } = useBilling();

  const columns: Column<Invoice>[] = [
    { header: "Invoice Number", accessorKey: "invoiceId", cell: (row) => <span className="font-semibold text-foreground">{row.invoiceId}</span> },
    { header: "Billing Date", accessorKey: "date" },
    { header: "Amount Paid", accessorKey: "amount" },
    {
      header: "Status",
      accessorKey: "status",
      cell: (row) => <Badge variant={row.status === "Paid" ? "success" : "warning"}>{row.status}</Badge>,
    },
    {
      header: "Receipt",
      accessorKey: "receipt",
      align: "right",
      cell: (row) => (
        <Button size="icon" variant="ghost" className="h-8 w-8 hover:bg-muted text-muted-foreground hover:text-foreground">
          <Download className="h-4 w-4" />
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Billing & Plans</h1>
        <p className="text-xs text-muted-foreground">Manage payment methods, monitor Stripe subscriptions, and inspect usage limits.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Side: Current Plan Info & Pricing mock update */}
        <div className="lg:col-span-1 space-y-6">
          <Card className="border-border/80">
            <CardHeader>
              <CardTitle className="text-base font-bold flex items-center gap-1.5">
                <CreditCard className="h-4.5 w-4.5 text-brand-indigo" /> Current Subscription
              </CardTitle>
              <CardDescription className="text-[11px]">Your workspace is on the Growth tier plan.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-baseline justify-between">
                <h3 className="text-2xl font-black text-foreground">$79.00 <span className="text-xs font-normal text-muted-foreground">/ month</span></h3>
                <Badge variant="info">Active</Badge>
              </div>

              {/* Usage Indicators limits */}
              <div className="space-y-3 pt-4 border-t border-border/40 text-xs">
                <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Quota usage limits</span>
                <div className="space-y-2">
                  <div className="space-y-1">
                    <div className="flex justify-between font-medium">
                      <span className="text-muted-foreground">Datasets Uploaded</span>
                      <span>4 / Unlimited</span>
                    </div>
                    <div className="h-1.5 w-full bg-muted/65 rounded-full overflow-hidden">
                      <div className="h-full w-[25%] bg-brand-indigo rounded-full" />
                    </div>
                  </div>
                  <div className="space-y-1">
                    <div className="flex justify-between font-medium">
                      <span className="text-muted-foreground">PDF Summaries Generated</span>
                      <span>3 / 100 month</span>
                    </div>
                    <div className="h-1.5 w-full bg-muted/65 rounded-full overflow-hidden">
                      <div className="h-full w-[3%] bg-brand-indigo rounded-full" />
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground/80 mt-2">
                <ShieldCheck className="h-4 w-4 text-emerald-500" /> Stripe billing protection secured
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Side: Invoices history log */}
        <div className="lg:col-span-2 space-y-3">
          <h2 className="text-sm font-semibold tracking-tight">Invoice History</h2>
          <BaseTable columns={columns as any} data={invoices} isLoading={isLoadingInvoices} />
        </div>
      </div>
    </div>
  );
}
