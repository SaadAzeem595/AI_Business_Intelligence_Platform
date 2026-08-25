"use client";

import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";
import { BaseChart } from "@/shared/components/data-display/BaseChart";
import { BaseTable, type Column } from "@/shared/components/data-display/BaseTable";
import { Sliders, Sparkles, AlertCircle, CheckCircle2, Info, Target } from "lucide-react";
import { useSegmentation } from "@/features/analytics/hooks/useForecast";
import { CohortSegment, SegmentProfile } from "@/shared/types/analytics";

export default function SegmentationPage() {
  const [clustersCount, setClustersCount] = useState(3);
  const [modeOption, setModeOption] = useState("auto");

  const {
    scatterData,
    cohorts,
    evaluation,
    profiles,
    featuresUsed,
    datasetType,
    entityKey,
    isLoading,
    isError,
    error,
    refetch,
  } = useSegmentation(clustersCount, undefined, undefined, undefined, modeOption);

  const columns: Column<CohortSegment>[] = [
    {
      header: "Generated Segment Name",
      accessorKey: "name",
      cell: (row) => <span className="font-semibold text-foreground">{row.name}</span>,
    },
    { header: "Entity Count", accessorKey: "count", cell: (row) => row.count.toLocaleString() },
    { header: "Average Spend / Metric", accessorKey: "avgSpent" },
    { header: "Frequency Metric", accessorKey: "freqScore" },
    {
      header: "Risk Rating",
      accessorKey: "riskRating",
      cell: (row) => {
        const variants: Record<CohortSegment["riskRating"], "success" | "warning" | "destructive"> = {
          Low: "success",
          Medium: "warning",
          High: "destructive",
        };
        return <Badge variant={variants[row.riskRating] || "warning"}>{row.riskRating}</Badge>;
      },
    },
  ];

  const handleRunCluster = () => {
    refetch();
  };

  // Sort scatter data by X coordinate for line/point plotting
  const sortedScatter = React.useMemo(() => {
    return [...scatterData].sort((a, b) => a.x - b.x);
  }, [scatterData]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Customer & Tabular Segmentation</h1>
          <p className="text-xs text-muted-foreground">
            Data-driven cohort clustering using RFM analytics or generic numerical feature modeling with automated K evaluation.
          </p>
        </div>
        {datasetType && (
          <Badge variant="outline" className="w-fit text-xs border-brand-indigo/30 bg-brand-indigo/5 text-brand-indigo px-3 py-1">
            Mode: {datasetType} {entityKey ? `(Key: ${entityKey})` : ""}
          </Badge>
        )}
      </div>

      {/* Error state alert */}
      {isError && (
        <Card className="border-destructive/50 bg-destructive/5">
          <CardContent className="pt-6 flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h4 className="text-sm font-semibold text-destructive">Segmentation Execution Error</h4>
              <p className="text-xs text-muted-foreground">
                {error?.response?.data?.detail || error?.message || "Failed to execute clustering on active dataset. Please verify an active dataset is uploaded."}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Left Tuning Panel */}
        <Card className="border-border/80 lg:col-span-1 h-fit">
          <CardHeader>
            <CardTitle className="text-base font-bold flex items-center gap-1.5">
              <Sliders className="h-4.5 w-4.5 text-brand-indigo" /> Segment Parameters
            </CardTitle>
            <CardDescription className="text-[11px]">Tune clustering model parameters and feature modes.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {/* Clusters count */}
            <div className="space-y-2">
              <div className="flex justify-between text-xs font-semibold">
                <span className="text-muted-foreground">Number of clusters (k)</span>
                <span className="text-brand-indigo font-bold">{clustersCount}</span>
              </div>
              <input
                type="range"
                min="2"
                max="8"
                value={clustersCount}
                onChange={(e) => setClustersCount(Number(e.target.value))}
                className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-brand-indigo"
              />
              {evaluation?.optimal_k && (
                <div className="flex items-center gap-1.5 text-[11px] text-emerald-600 dark:text-emerald-400 mt-1">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  <span>Optimal K recommended: <strong>{evaluation.optimal_k}</strong></span>
                </div>
              )}
            </div>

            {/* Feature mode selection */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-muted-foreground">Feature Engineering Mode</label>
              <select
                value={modeOption}
                onChange={(e) => setModeOption(e.target.value)}
                className="text-xs p-2 rounded-md border border-border/80 bg-background w-full text-foreground/80 cursor-pointer"
              >
                <option value="auto">Auto-Detect (RFM / Numerical)</option>
                <option value="rfm">RFM Transactional (Recency, Frequency, Spend)</option>
                <option value="numerical">Generic Numerical Clustering</option>
              </select>
            </div>

            {/* Features Used List */}
            {featuresUsed && featuresUsed.length > 0 && (
              <div className="space-y-1.5">
                <span className="text-[11px] font-semibold text-muted-foreground">Features Engaged</span>
                <div className="flex flex-wrap gap-1">
                  {featuresUsed.map((feat) => (
                    <Badge key={feat} variant="secondary" className="text-[10px] py-0 px-1.5 font-mono">
                      {feat}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            <Button onClick={handleRunCluster} disabled={isLoading} className="w-full mt-4" variant="brand" size="sm">
              {isLoading ? "Computing clusters..." : "Run Clustering Model"}
            </Button>
          </CardContent>
        </Card>

        {/* Right Visuals & Cohorts Section */}
        <div className="lg:col-span-3 space-y-6">
          {/* Evaluation Metrics Cards */}
          {evaluation && (
            <div className="grid grid-cols-3 gap-3">
              <div className="p-3 rounded-lg border border-border/80 bg-card">
                <span className="text-[10px] text-muted-foreground uppercase font-semibold">Silhouette Score</span>
                <div className="text-lg font-bold text-foreground mt-0.5">{evaluation.silhouette_score}</div>
                <span className="text-[10px] text-muted-foreground">Cluster separation metric (-1 to +1)</span>
              </div>
              <div className="p-3 rounded-lg border border-border/80 bg-card">
                <span className="text-[10px] text-muted-foreground uppercase font-semibold">Davies-Bouldin</span>
                <div className="text-lg font-bold text-foreground mt-0.5">{evaluation.davies_bouldin_index}</div>
                <span className="text-[10px] text-muted-foreground">Cluster similarity index (lower is better)</span>
              </div>
              <div className="p-3 rounded-lg border border-border/80 bg-card">
                <span className="text-[10px] text-muted-foreground uppercase font-semibold">Calinski-Harabasz</span>
                <div className="text-lg font-bold text-foreground mt-0.5">{evaluation.calinski_harabasz_index}</div>
                <span className="text-[10px] text-muted-foreground">Variance ratio criterion</span>
              </div>
            </div>
          )}

          {/* Scatter Plot */}
          <Card className="border-border/80">
            <CardHeader className="pb-2">
              <CardTitle className="text-base font-bold flex items-center justify-between">
                <span>Cohorts Scatter Plot</span>
                {scatterData.length > 0 && (
                  <span className="text-xs text-muted-foreground font-normal">
                    {scatterData.length} Sample Points Plotted
                  </span>
                )}
              </CardTitle>
              <CardDescription className="text-[11px]">
                Calculated 2D projection coordinates derived from scaling and dimensional reduction of features.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {sortedScatter.length > 0 ? (
                <BaseChart
                  type="line"
                  data={sortedScatter}
                  xKey="x"
                  yKeys={["y"]}
                  colors={["var(--color-brand-indigo)"]}
                  height={280}
                />
              ) : (
                <div className="h-[280px] flex items-center justify-center text-xs text-muted-foreground">
                  {isLoading ? "Calculating cluster coordinates..." : "No scatter data available."}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Details Cohorts Table */}
          <div className="space-y-3">
            <h2 className="text-sm font-semibold tracking-tight flex items-center gap-1.5">
              <Sparkles className="h-4 w-4 text-brand-indigo" /> Cluster Cohorts Summary
            </h2>
            <BaseTable columns={columns as any} data={cohorts} isLoading={isLoading} />
          </div>

          {/* Business Profiles & Recommendations Section */}
          {profiles && profiles.length > 0 && (
            <div className="space-y-3">
              <h2 className="text-sm font-semibold tracking-tight flex items-center gap-1.5">
                <Target className="h-4 w-4 text-brand-indigo" /> Data-Driven Business Profiles & Actionable Recommendations
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {profiles.map((prof: SegmentProfile) => (
                  <Card key={prof.cluster_id} className="border-border/80">
                    <CardHeader className="pb-2">
                      <div className="flex items-start justify-between gap-2">
                        <CardTitle className="text-sm font-bold text-foreground">
                          {prof.name}
                        </CardTitle>
                        <Badge
                          variant={
                            prof.risk_rating === "Low"
                              ? "success"
                              : prof.risk_rating === "High"
                              ? "destructive"
                              : "warning"
                          }
                          className="text-[10px]"
                        >
                          {prof.risk_rating} Risk
                        </Badge>
                      </div>
                      <CardDescription className="text-xs">
                        Size: {prof.size.toLocaleString()} entities ({prof.percentage}%)
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-2 text-xs">
                      <div>
                        <span className="font-semibold text-muted-foreground">Characteristics: </span>
                        <span>{prof.characteristics}</span>
                      </div>
                      <div className="p-2.5 rounded-md bg-muted/30 border border-border/50 text-foreground/90">
                        <span className="font-semibold text-brand-indigo flex items-center gap-1 mb-0.5">
                          <Info className="h-3.5 w-3.5" /> Actionable Strategy:
                        </span>
                        <span>{prof.recommendation}</span>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
