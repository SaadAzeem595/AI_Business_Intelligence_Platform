"use client";

import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";
import { BaseChart } from "@/shared/components/data-display/BaseChart";
import { BaseTable, type Column } from "@/shared/components/data-display/BaseTable";
import { Users2, Sliders, Play, Sparkles } from "lucide-react";

interface CohortSegment {
  name: string;
  count: number;
  avgSpent: string;
  freqScore: string;
  riskRating: "Low" | "Medium" | "High";
}

import { useSegmentation } from "@/features/analytics/hooks/useForecast";

export default function SegmentationPage() {
  const [clustersCount, setClustersCount] = useState(3);
  const [metricOption, setMetricOption] = useState("LTV vs Recency");

  const { scatterData, cohorts, isLoading, refetch } = useSegmentation(clustersCount, metricOption);

  const columns: Column<CohortSegment>[] = [
    {
      header: "Generated Segment Name",
      accessorKey: "name",
      cell: (row) => <span className="font-semibold text-foreground">{row.name}</span>,
    },
    { header: "User count", accessorKey: "count", cell: (row) => row.count.toLocaleString() },
    { header: "Average Spend", accessorKey: "avgSpent" },
    { header: "Frequency metric", accessorKey: "freqScore" },
    {
      header: "Churn Risk",
      accessorKey: "riskRating",
      cell: (row) => {
        const variants: Record<CohortSegment["riskRating"], "success" | "warning" | "destructive"> = {
          Low: "success",
          Medium: "warning",
          High: "destructive",
        };
        return <Badge variant={variants[row.riskRating]}>{row.riskRating}</Badge>;
      },
    },
  ];

  const handleRunCluster = () => {
    refetch();
  };

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Customer Segmentation</h1>
        <p className="text-xs text-muted-foreground">Cluster customer columns automatically using K-Means modeling to evaluate cohorts churn risks.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Left Tuning Panel */}
        <Card className="border-border/80 lg:col-span-1 h-fit">
          <CardHeader>
            <CardTitle className="text-base font-bold flex items-center gap-1.5">
              <Sliders className="h-4.5 w-4.5 text-brand-indigo" /> Segment Parameters
            </CardTitle>
            <CardDescription className="text-[11px]">Adjust clustering models keys.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <div className="flex justify-between text-xs font-semibold">
                <span className="text-muted-foreground">Number of clusters (k)</span>
                <span className="text-brand-indigo">{clustersCount}</span>
              </div>
              <input
                type="range"
                min="2"
                max="6"
                value={clustersCount}
                onChange={(e) => setClustersCount(Number(e.target.value))}
                className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-brand-indigo"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-semibold text-muted-foreground">Primary Features Map</label>
              <select
                value={metricOption}
                onChange={(e) => setMetricOption(e.target.value)}
                className="text-xs p-2 rounded-md border border-border/80 bg-background w-full text-foreground/80 cursor-pointer"
              >
                <option>LTV vs Recency</option>
                <option>Spend vs Frequency</option>
                <option>Tenure vs Support Tickets</option>
              </select>
            </div>

            <Button onClick={handleRunCluster} disabled={isLoading} className="w-full mt-4" variant="brand" size="sm">
              {isLoading ? "Computing clusters..." : "Run Clustering Model"}
            </Button>
          </CardContent>
        </Card>

        {/* Right Scatter Visuals Map */}
        <div className="lg:col-span-3 space-y-6">
          <Card className="border-border/80">
            <CardHeader>
              <CardTitle className="text-base font-bold">Cohorts Scatter Plot</CardTitle>
              <CardDescription className="text-[11px]">Users clustered on {metricOption} axes. Select clusters below to review segments.</CardDescription>
            </CardHeader>
            <CardContent>
              {/* Uses Area chart styled as scatter or similar block mock visualization */}
              <BaseChart
                type="line"
                data={scatterData}
                xKey="x"
                yKeys={["y"]}
                colors={["var(--color-brand-indigo)"]}
                height={280}
              />
            </CardContent>
          </Card>

          {/* Details cohorts tables */}
          <div className="space-y-3">
            <h2 className="text-sm font-semibold tracking-tight flex items-center gap-1.5">
              <Sparkles className="h-4 w-4 text-brand-indigo" /> Cluster Cohorts Summary
            </h2>
            <BaseTable columns={columns as any} data={cohorts} isLoading={isLoading} />
          </div>
        </div>
      </div>
    </div>
  );
}
