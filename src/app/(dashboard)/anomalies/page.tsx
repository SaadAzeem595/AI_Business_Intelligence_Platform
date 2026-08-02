"use client";

import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";
import { BaseChart } from "@/shared/components/data-display/BaseChart";
import { BaseTable, type Column } from "@/shared/components/data-display/BaseTable";
import { AlertTriangle, Settings, CheckCircle2, Play } from "lucide-react";

interface AnomalyLog {
  id: string;
  metric: string;
  value: string;
  deviation: string;
  date: string;
  status: "Unresolved" | "Resolved";
}

import { useAnomalies } from "@/features/analytics/hooks/useForecast";

export default function AnomaliesPage() {
  const [sensitivity, setSensitivity] = useState(2.5);

  const { timelineData, anomalies: queriedAnomalies, isLoading, refetch } = useAnomalies(sensitivity);
  const [anomalies, setAnomalies] = useState<any[]>([]);

  React.useEffect(() => {
    if (queriedAnomalies) {
      setAnomalies(queriedAnomalies);
    }
  }, [queriedAnomalies]);

  const columns: Column<AnomalyLog>[] = [
    {
      header: "Anomaly ID",
      accessorKey: "id",
      cell: (row) => <span className="font-semibold text-foreground">{row.id}</span>,
    },
    { header: "Metric Trigger", accessorKey: "metric" },
    { header: "Trigger Value", accessorKey: "value" },
    {
      header: "Z-Score Deviation",
      accessorKey: "deviation",
      cell: (row) => <span className="font-bold text-rose-500">{row.deviation}</span>,
    },
    { header: "Detected At", accessorKey: "date" },
    {
      header: "Status",
      accessorKey: "status",
      cell: (row) => {
        const variants: Record<AnomalyLog["status"], "warning" | "success"> = {
          Unresolved: "warning",
          Resolved: "success",
        };
        return <Badge variant={variants[row.status]}>{row.status}</Badge>;
      },
    },
    {
      header: "Action",
      accessorKey: "actions",
      align: "right",
      cell: (row) => (
        <Button
          size="sm"
          variant="outline"
          className="h-7 text-xs border-border/80 hover:bg-emerald-500/10 hover:text-emerald-500"
          onClick={() => handleResolve(row.id)}
          disabled={row.status === "Resolved"}
        >
          <CheckCircle2 className="h-3.5 w-3.5 mr-1" /> Resolve
        </Button>
      ),
    },
  ];

  const handleResolve = (id: string) => {
    setAnomalies(anomalies.map((a) => (a.id === id ? { ...a, status: "Resolved" } : a)));
  };

  const handleScan = () => {
    refetch();
  };

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Anomaly Detection</h1>
        <p className="text-xs text-muted-foreground">Scans system timeseries indicators and flags spikes or dips exceeding standard statistical ranges.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Left Side: Sensitivity Tuning */}
        <Card className="border-border/80 lg:col-span-1 h-fit">
          <CardHeader>
            <CardTitle className="text-base font-bold flex items-center gap-1.5">
              <Settings className="h-4.5 w-4.5 text-brand-indigo" /> Detection Sensitivity
            </CardTitle>
            <CardDescription className="text-[11px]">Define anomaly flagging limits.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <div className="flex justify-between text-xs font-semibold">
                <span className="text-muted-foreground">Threshold Multiplier</span>
                <span className="text-rose-500">{sensitivity} σ</span>
              </div>
              <input
                type="range"
                min="1.5"
                max="4.0"
                step="0.1"
                value={sensitivity}
                onChange={(e) => setSensitivity(Number(e.target.value))}
                className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-rose-500"
              />
            </div>
            <p className="text-[10px] text-muted-foreground leading-relaxed">
              Adjusting limits controls False Positive rates. Standard deviation boundary sets outlier thresholds (σ).
            </p>
            <Button onClick={handleScan} disabled={isLoading} className="w-full mt-4" variant="brand" size="sm">
              {isLoading ? "Scanning timeline..." : "Re-Scan Indicators"}
            </Button>
          </CardContent>
        </Card>

        {/* Right Side: Anomalies Graph */}
        <div className="lg:col-span-3 space-y-6">
          <Card className="border-border/80">
            <CardHeader className="flex flex-row items-center justify-between pb-4">
              <div>
                <CardTitle className="text-base font-bold">Timeseries Outliers Scan</CardTitle>
                <CardDescription className="text-[11px]">Shaded points indicate transactions values violating thresholds.</CardDescription>
              </div>
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span className="h-2 w-2 rounded-full bg-brand-indigo" /> Indicators Values
                <span className="h-2 w-2 rounded-full bg-rose-500" /> Threshold Bound ({sensitivity}σ)
              </div>
            </CardHeader>
            <CardContent>
              <BaseChart
                type="area"
                data={timelineData}
                xKey="date"
                yKeys={["value", "limit"]}
                colors={["var(--color-brand-indigo)", "#ef4444"]}
              />
            </CardContent>
          </Card>

          {/* Anomaly Log list */}
          <div className="space-y-3">
            <h2 className="text-sm font-semibold tracking-tight flex items-center gap-1.5">
              <AlertTriangle className="h-4 w-4 text-rose-500" /> Anomalies Log Feed
            </h2>
            <BaseTable columns={columns as any} data={anomalies} isLoading={isLoading} />
          </div>
        </div>
      </div>
    </div>
  );
}
