"use client";

import React, { useState } from "react";
import Link from "next/link";
import { KPICard } from "@/shared/components/data-display/KPICard";
import { BaseChart } from "@/shared/components/data-display/BaseChart";
import { BaseTable, type Column } from "@/shared/components/data-display/BaseTable";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/shared/components/ui/card";
import { DollarSign, Users, Target, AlertCircle, FilePlus, Sparkles, Send } from "lucide-react";
import { useDashboard } from "@/features/dashboard/hooks/useDashboard";
import { useDatasets } from "@/features/datasets/hooks/useDatasets";

interface UploadLog {
  filename: string;
  size: string;
  rows: number;
  status: "Active" | "Processing" | "Failed";
  date: string;
}

export default function DashboardPage() {
  const [chartType, setChartType] = useState<"area" | "line" | "bar">("area");
  
  const { metrics, trends, isLoading } = useDashboard();
  const { datasets } = useDatasets();

  const columns: Column<UploadLog>[] = [
    {
      header: "Dataset File",
      accessorKey: "filename",
      cell: (row) => <span className="font-semibold text-foreground">{row.filename}</span>,
    },
    { header: "Size", accessorKey: "size" },
    {
      header: "Rows count",
      accessorKey: "rows",
      cell: (row) => row.rows.toLocaleString(),
    },
    {
      header: "Status",
      accessorKey: "status",
      cell: (row) => {
        const variants: Record<UploadLog["status"], "success" | "warning" | "destructive"> = {
          Active: "success",
          Processing: "warning",
          Failed: "destructive",
        };
        return <Badge variant={variants[row.status]}>{row.status}</Badge>;
      },
    },
    { header: "Uploaded At", accessorKey: "date" },
  ];

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Workspace Overview</h1>
          <p className="text-xs text-muted-foreground">Monitor real-time company revenue, run machine learning predictions, and compile summaries.</p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/datasets">
            <Button size="sm" className="gap-1">
              <FilePlus className="h-4 w-4" /> Upload Dataset
            </Button>
          </Link>
          <Link href="/chat">
            <Button size="sm" variant="outline" className="gap-1 border-brand-indigo/35 text-brand-indigo hover:bg-brand-indigo/5">
              <Sparkles className="h-4 w-4" /> Ask AI Assistant
            </Button>
          </Link>
        </div>
      </div>

      {/* KPI Cards section */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          title="Total gross revenue"
          value={metrics?.grossRevenue || "$1,248,390"}
          change={{ value: metrics?.grossRevenueChange ?? 14.2, type: "up", label: "vs. previous month" }}
          icon={<DollarSign className="h-4 w-4 text-brand-indigo" />}
        />
        <KPICard
          title="Active cohort users"
          value={metrics?.activeUsers || "14,204"}
          change={{ value: metrics?.activeUsersChange ?? 8.7, type: "up", label: "vs. previous month" }}
          icon={<Users className="h-4 w-4 text-emerald-500" />}
        />
        <KPICard
          title="Prediction confidence"
          value={metrics?.predictionAccuracy || "94.6%"}
          change={{ value: metrics?.predictionAccuracyChange ?? 1.2, type: "up", label: "Model precision accuracy" }}
          icon={<Target className="h-4 w-4 text-amber-500" />}
        />
        <KPICard
          title="Anomalies checked"
          value={`${metrics?.anomaliesCount ?? 2} Flags`}
          change={{ value: 50.0, type: "down", label: "Action recommended" }}
          icon={<AlertCircle className="h-4 w-4 text-rose-500" />}
        />
      </div>

      {/* Core split layout: 70% Chart, 30% Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Sales Chart Container */}
        <Card className="lg:col-span-2 border-border/80">
          <CardHeader className="flex flex-row items-center justify-between pb-4">
            <div>
              <CardTitle className="text-base font-bold">Revenue Projections</CardTitle>
              <CardDescription className="text-[11px]">Compare current sales performance relative to monthly targets.</CardDescription>
            </div>
            <div className="flex border border-border/80 rounded-md overflow-hidden p-0.5 bg-muted/20">
              {(["area", "line", "bar"] as const).map((type) => (
                <button
                  key={type}
                  onClick={() => setChartType(type)}
                  className={`text-[10px] font-bold px-2 py-1 capitalize rounded-md transition-all cursor-pointer ${
                    chartType === type
                      ? "bg-card text-foreground shadow-xs"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {type}
                </button>
              ))}
            </div>
          </CardHeader>
          <CardContent>
            <BaseChart type={chartType} data={trends} xKey="month" yKeys={["revenue", "target"]} />
          </CardContent>
        </Card>

        {/* AI Assistant Quick Actions panel */}
        <Card className="border-border/80 flex flex-col justify-between">
          <CardHeader>
            <CardTitle className="text-base font-bold flex items-center gap-1.5 text-brand-indigo">
              <Sparkles className="h-4 w-4" /> AI Analytics Panel
            </CardTitle>
            <CardDescription className="text-[11px]">Generate quick forecasts or queries instantly from active tables.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 flex-1">
            <div className="space-y-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Suggested prompts</span>
              <div className="space-y-1.5">
                {[
                  "Forecast next quarter sales",
                  "Identify clusters in active customers",
                  "Flag anomalies in raw transactions log",
                ].map((prompt, idx) => (
                  <Link
                    key={idx}
                    href={`/chat?prompt=${encodeURIComponent(prompt)}`}
                    className="flex items-center justify-between p-2 rounded-md border border-border/60 hover:border-brand-indigo/40 hover:bg-brand-indigo/5 text-xs text-muted-foreground hover:text-foreground transition-all select-none group"
                  >
                    <span className="truncate">{prompt}</span>
                    <Send className="h-3 w-3 text-muted-foreground group-hover:text-brand-indigo opacity-0 group-hover:opacity-100 transition-all shrink-0" />
                  </Link>
                ))}
              </div>
            </div>
            <div className="space-y-2 mt-4 pt-4 border-t border-border/40">
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">DuckDB Health status</span>
              <div className="flex items-center gap-2 text-xs">
                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-muted-foreground">In-Memory Engine: Active ({datasets?.length || 0} datasets loaded)</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent uploads list */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold tracking-tight">Recent Datasets Uploaded</h2>
          <Link href="/datasets">
            <Button size="sm" variant="ghost" className="text-xs text-brand-indigo hover:text-brand-indigo/80">
              View all datasets
            </Button>
          </Link>
        </div>
        <BaseTable columns={columns as any} data={datasets} isLoading={isLoading} />
      </div>
    </div>
  );
}
