"use client";

import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";
import { BaseChart } from "@/shared/components/data-display/BaseChart";
import { BaseTable, type Column } from "@/shared/components/data-display/BaseTable";
import { useUIStore } from "@/shared/services/uiStore";
import { useProjects } from "@/features/projects/hooks/useProjects";
import { 
  useForecastSchemaInfo, 
  useProjectForecast 
} from "@/features/analytics/hooks/useForecast";
import { 
  ProjectForecastRequest, 
  TimeSeriesCandidate, 
  ForecastModelMetrics 
} from "@/shared/types/analytics";
import { 
  TrendingUp, 
  Settings2, 
  Sparkles, 
  AlertCircle, 
  Calendar, 
  BarChart3, 
  CheckCircle2, 
  Info, 
  FolderKanban,
  Layers,
  ArrowUpRight,
  ArrowDownRight,
  ShieldCheck,
  Zap
} from "lucide-react";
import { cn } from "@/shared/lib/utils";

export default function ForecastingPage() {
  const { activeProject, setActiveProject } = useUIStore();
  const { projects } = useProjects();

  // If no active project selected in store, pick first available project
  useEffect(() => {
    if (!activeProject && projects.length > 0) {
      setActiveProject(projects[0].id);
    }
  }, [activeProject, projects, setActiveProject]);

  // Schema Discovery Hook
  const { 
    hasTimeSeries, 
    candidates, 
    message: discoveryMessage, 
    isLoading: isLoadingSchema 
  } = useForecastSchemaInfo(activeProject);

  // Active form selection state
  const [selectedCandidateId, setSelectedCandidateId] = useState<string>("");
  const [dateColumn, setDateColumn] = useState<string>("");
  const [targetMetric, setTargetMetric] = useState<string>("");
  const [aggregation, setAggregation] = useState<"daily" | "weekly" | "monthly">("monthly");
  const [horizon, setHorizon] = useState<number>(6);
  const [groupBy, setGroupBy] = useState<string>("");
  const [modelChoice, setModelChoice] = useState<string>("auto");
  const [confidence, setConfidence] = useState<number>(95);

  // Active forecast query configuration
  const [activeConfig, setActiveConfig] = useState<ProjectForecastRequest | undefined>(undefined);

  // Sync auto-detected candidates into form state
  useEffect(() => {
    if (candidates && candidates.length > 0) {
      const activeCandidate = candidates.find(c => c.dataset_id === selectedCandidateId) || candidates[0];
      setSelectedCandidateId(activeCandidate.dataset_id);
      setDateColumn(activeCandidate.suggested_date || activeCandidate.date_columns[0] || "");
      setTargetMetric(activeCandidate.suggested_metric || activeCandidate.metric_columns[0] || "");
      if (activeCandidate.categorical_columns.length > 0) {
        setGroupBy(activeCandidate.categorical_columns[0]);
      } else {
        setGroupBy("");
      }

      // Automatically trigger initial forecast
      setActiveConfig({
        dataset_id: activeCandidate.dataset_id,
        date_column: activeCandidate.suggested_date || activeCandidate.date_columns[0] || "",
        target_column: activeCandidate.suggested_metric || activeCandidate.metric_columns[0] || "",
        aggregation: "monthly",
        horizon: 6,
        group_by: undefined,
        model: "auto",
        confidence: 0.95
      });
    }
  }, [candidates]);

  // Update dropdown fields when user selects a different dataset candidate
  const handleCandidateChange = (candId: string) => {
    setSelectedCandidateId(candId);
    const cand = candidates.find(c => c.dataset_id === candId);
    if (cand) {
      setDateColumn(cand.suggested_date || cand.date_columns[0] || "");
      setTargetMetric(cand.suggested_metric || cand.metric_columns[0] || "");
    }
  };

  // Forecast Query Execution Hook
  const { 
    forecastResult, 
    isLoading: isExecutingForecast, 
    error: forecastError, 
    refetch 
  } = useProjectForecast(activeProject, activeConfig);

  const handleRunForecast = () => {
    setActiveConfig({
      dataset_id: selectedCandidateId,
      date_column: dateColumn,
      target_column: targetMetric,
      aggregation: aggregation,
      horizon: horizon,
      group_by: groupBy || undefined,
      model: modelChoice,
      confidence: confidence / 100.0
    });
  };

  const selectedCandidate = candidates.find(c => c.dataset_id === selectedCandidateId);

  // Model Evaluation Columns for Diagnostics Table
  const metricColumns: Column<ForecastModelMetrics>[] = [
    {
      header: "Algorithm",
      accessorKey: "model_name",
      cell: (row) => (
        <div className="flex items-center gap-2 font-semibold text-foreground">
          <span>{row.model_name}</span>
          {row.is_best && (
            <Badge variant="success" className="text-[9px] py-0 px-1.5 gap-1">
              <Sparkles className="h-3 w-3" /> Recommended Best
            </Badge>
          )}
        </div>
      ),
    },
    {
      header: "Mean Absolute Error (MAE)",
      accessorKey: "mae",
      cell: (row) => <span className="font-mono">{row.mae.toLocaleString()}</span>,
    },
    {
      header: "Root Mean Square Error (RMSE)",
      accessorKey: "rmse",
      cell: (row) => <span className="font-mono">{row.rmse.toLocaleString()}</span>,
    },
    {
      header: "Mean Absolute % Error (MAPE)",
      accessorKey: "mape",
      cell: (row) => <span className="font-mono font-bold text-brand-indigo">{row.mape}%</span>,
    },
  ];

  // Chart data formatting
  const chartData = forecastResult?.timeline.map(pt => ({
    date: pt.date,
    Actual: pt.actual,
    Forecast: pt.forecast,
    LowerBound: pt.lower,
    UpperBound: pt.upper
  })) || [];

  return (
    <div className="space-y-6">
      {/* Title Header & Workspace Context Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border/60 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight">Time Series Forecasting</h1>
            <Badge variant="outline" className="text-xs font-semibold gap-1">
              <FolderKanban className="h-3.5 w-3.5 text-brand-indigo" />
              <span>Project: {projects.find(p => p.id === activeProject)?.name || activeProject || "None"}</span>
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Production-grade predictive analytics inspecting project datasets and DuckDB relational views.
          </p>
        </div>

        {/* Project Switcher */}
        {projects.length > 1 && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground font-semibold">Active Project:</span>
            <select
              value={activeProject}
              onChange={(e) => setActiveProject(e.target.value)}
              className="text-xs p-1.5 rounded-md border border-border/80 bg-background font-semibold text-foreground cursor-pointer"
            >
              {projects.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* No Time-Series Data Banner */}
      {!isLoadingSchema && !hasTimeSeries && (
        <Card className="border-amber-500/40 bg-amber-500/5 text-amber-600 dark:text-amber-400 p-6">
          <div className="flex items-start gap-4">
            <AlertCircle className="h-6 w-6 shrink-0 text-amber-500 mt-0.5" />
            <div className="space-y-2">
              <h3 className="text-sm font-bold text-foreground">No suitable time-series data found in this project</h3>
              <p className="text-xs leading-relaxed max-w-2xl">
                {discoveryMessage || "To run forecasting, your active project requires datasets containing timestamp or date columns, numeric metrics, and historical observations."}
              </p>
              <div className="pt-2 text-xs font-semibold space-y-1">
                <p className="text-foreground">Required Dataset Requirements:</p>
                <ul className="list-disc list-inside space-y-0.5 text-muted-foreground font-normal">
                  <li>At least one date/time column (e.g. <code className="text-amber-500 font-mono">created_at</code>, <code className="text-amber-500 font-mono">order_purchase_timestamp</code>, <code className="text-amber-500 font-mono">date</code>).</li>
                  <li>A numeric target metric (e.g. <code className="text-amber-500 font-mono">price</code>, <code className="text-amber-500 font-mono">revenue</code>, <code className="text-amber-500 font-mono">sales</code>, <code className="text-amber-500 font-mono">quantity</code>).</li>
                  <li>Sufficient historical observations (at least 4 observations for daily/weekly, or 3 for monthly forecasting).</li>
                </ul>
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Main Layout Grid */}
      {hasTimeSeries && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Left Controls: Forecast Config Panel */}
          <Card className="border-border/80 lg:col-span-1 h-fit select-none">
            <CardHeader className="pb-3 border-b border-border/40">
              <CardTitle className="text-base font-bold flex items-center gap-1.5">
                <Settings2 className="h-4.5 w-4.5 text-brand-indigo" /> Forecast Controls
              </CardTitle>
              <CardDescription className="text-[11px]">Inspect project datasets & tune metrics.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 pt-4">
              {/* Dataset Candidate Picker */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground flex items-center gap-1">
                  <Layers className="h-3.5 w-3.5 text-brand-indigo" /> Dataset Target
                </label>
                <select
                  value={selectedCandidateId}
                  onChange={(e) => handleCandidateChange(e.target.value)}
                  className="text-xs p-2 rounded-md border border-border/80 bg-background w-full text-foreground cursor-pointer font-medium"
                >
                  {candidates.map(c => (
                    <option key={c.dataset_id} value={c.dataset_id}>
                      {c.is_derived_olist ? "✨ " + c.dataset_name : c.dataset_name}
                    </option>
                  ))}
                </select>
                {selectedCandidate?.is_derived_olist && (
                  <p className="text-[10px] text-emerald-500 font-medium">
                    ⚡ Auto-joined DuckDB relational schema (Orders + Items)
                  </p>
                )}
              </div>

              {/* Date Column */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground flex items-center gap-1">
                  <Calendar className="h-3.5 w-3.5 text-brand-indigo" /> Date / Timestamp Column
                </label>
                <select
                  value={dateColumn}
                  onChange={(e) => setDateColumn(e.target.value)}
                  className="text-xs p-2 rounded-md border border-border/80 bg-background w-full text-foreground cursor-pointer"
                >
                  {selectedCandidate?.date_columns.map(col => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>
              </div>

              {/* Metric Column */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground flex items-center gap-1">
                  <BarChart3 className="h-3.5 w-3.5 text-brand-indigo" /> Forecast Metric
                </label>
                <select
                  value={targetMetric}
                  onChange={(e) => setTargetMetric(e.target.value)}
                  className="text-xs p-2 rounded-md border border-border/80 bg-background w-full text-foreground cursor-pointer"
                >
                  {selectedCandidate?.metric_columns.map(m => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>

              {/* Aggregation Bucket */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground">Aggregation Frequency</label>
                <div className="grid grid-cols-3 border border-border/80 rounded-md overflow-hidden p-0.5 bg-muted/20">
                  {(["daily", "weekly", "monthly"] as const).map((agg) => (
                    <button
                      key={agg}
                      onClick={() => setAggregation(agg)}
                      className={cn(
                        "text-[10px] font-bold py-1.5 capitalize rounded-md transition-all cursor-pointer",
                        aggregation === agg ? "bg-card text-foreground shadow-xs" : "text-muted-foreground hover:text-foreground"
                      )}
                    >
                      {agg}
                    </button>
                  ))}
                </div>
              </div>

              {/* Horizon Steps */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground">Forecast Horizon</label>
                <select
                  value={horizon}
                  onChange={(e) => setHorizon(Number(e.target.value))}
                  className="text-xs p-2 rounded-md border border-border/80 bg-background w-full text-foreground cursor-pointer"
                >
                  <option value={7}>7 Days / Steps Ahead</option>
                  <option value={30}>30 Days / Steps Ahead</option>
                  <option value={3}>3 Months Ahead</option>
                  <option value={6}>6 Months Ahead</option>
                  <option value={12}>12 Months Ahead</option>
                </select>
              </div>

              {/* Model Choice */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground">Forecasting Algorithm</label>
                <select
                  value={modelChoice}
                  onChange={(e) => setModelChoice(e.target.value)}
                  className="text-xs p-2 rounded-md border border-border/80 bg-background w-full text-foreground cursor-pointer font-medium"
                >
                  <option value="auto">Auto-Select (Best CV Score)</option>
                  <option value="arima">ARIMA (Statsmodels)</option>
                  <option value="prophet">Prophet (Additive Model)</option>
                  <option value="naive">Naive Baseline</option>
                </select>
              </div>

              {/* Confidence Level Slider */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs font-semibold">
                  <span className="text-muted-foreground">Confidence interval</span>
                  <span className="text-brand-indigo">{confidence}%</span>
                </div>
                <input
                  type="range"
                  min="80"
                  max="99"
                  value={confidence}
                  onChange={(e) => setConfidence(Number(e.target.value))}
                  className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-brand-indigo"
                />
              </div>

              {/* Action Button */}
              <Button 
                onClick={handleRunForecast} 
                disabled={isExecutingForecast} 
                className="w-full mt-2 cursor-pointer font-semibold" 
                variant="brand" 
                size="sm"
              >
                {isExecutingForecast ? "Computing Time-Series..." : "Run Forecast Pipeline"}
              </Button>
            </CardContent>
          </Card>

          {/* Right Area: Results, Insights, Chart, Diagnostics */}
          <div className="lg:col-span-3 space-y-6">
            {/* Error / Warning Alert */}
            {(forecastResult?.status === "error" || forecastError) && (
              <Card className="border-rose-500/40 bg-rose-500/10 p-4 text-rose-500 text-xs font-medium flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <AlertCircle className="h-4.5 w-4.5 shrink-0" />
                  <span>{forecastResult?.message || forecastError?.message || "Failed to execute forecast model pipeline."}</span>
                </div>
              </Card>
            )}

            {/* Business Summary Header Banner */}
            {forecastResult?.business_summary && (
              <Card className="border-border/80 bg-card p-5 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/40 pb-3">
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-brand-indigo">
                      Executive Forecast Summary
                    </span>
                    <h2 className="text-base font-bold text-foreground mt-0.5">
                      {forecastResult.business_summary.headline}
                    </h2>
                  </div>
                  <Badge 
                    variant={forecastResult.business_summary.current_trend === "Upward" ? "success" : "warning"}
                    className="self-start sm:self-auto text-xs px-3 py-1 font-bold gap-1"
                  >
                    {forecastResult.business_summary.current_trend === "Upward" ? (
                      <ArrowUpRight className="h-4 w-4" />
                    ) : (
                      <ArrowDownRight className="h-4 w-4" />
                    )}
                    <span>{forecastResult.business_summary.current_trend} Trend ({forecastResult.business_summary.growth_percentage}%)</span>
                  </Badge>
                </div>

                {/* Key Metrics Grid */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="p-3 bg-muted/20 rounded-lg border border-border/40">
                    <span className="text-[10px] font-semibold text-muted-foreground">Forecasted Total</span>
                    <p className="text-lg font-bold text-foreground mt-0.5">
                      ${forecastResult.business_summary.forecasted_total.toLocaleString()}
                    </p>
                    <span className="text-[9px] text-muted-foreground">Target: {forecastResult.business_summary.horizon_label}</span>
                  </div>

                  <div className="p-3 bg-muted/20 rounded-lg border border-border/40">
                    <span className="text-[10px] font-semibold text-muted-foreground">Historical Total</span>
                    <p className="text-lg font-bold text-foreground mt-0.5">
                      ${forecastResult.business_summary.historical_total.toLocaleString()}
                    </p>
                    <span className="text-[9px] text-muted-foreground">Recorded observations</span>
                  </div>

                  <div className="p-3 bg-muted/20 rounded-lg border border-border/40">
                    <span className="text-[10px] font-semibold text-muted-foreground">Peak Forecast Period</span>
                    <p className="text-sm font-bold text-emerald-500 mt-1 line-clamp-1">
                      {forecastResult.business_summary.best_period}
                    </p>
                    <span className="text-[9px] text-muted-foreground">Highest demand peak</span>
                  </div>

                  <div className="p-3 bg-muted/20 rounded-lg border border-border/40">
                    <span className="text-[10px] font-semibold text-muted-foreground">Selected Algorithm</span>
                    <p className="text-sm font-bold text-brand-indigo mt-1 line-clamp-1">
                      {forecastResult.selected_model}
                    </p>
                    <span className="text-[9px] text-muted-foreground">{forecastResult.business_summary.confidence_level * 100}% confidence</span>
                  </div>
                </div>
              </Card>
            )}

            {/* Projections Line Chart */}
            <Card className="border-border/80">
              <CardHeader className="flex flex-row items-center justify-between pb-3 border-b border-border/40 bg-muted/10">
                <div>
                  <CardTitle className="text-base font-bold flex items-center gap-2">
                    <TrendingUp className="h-4.5 w-4.5 text-brand-indigo" /> 
                    <span>Time Series Projection Curve</span>
                  </CardTitle>
                  <CardDescription className="text-[11px]">
                    Solid line indicates historical actuals; dashed predictions show expected trajectory with shaded confidence bounds.
                  </CardDescription>
                </div>
                <div className="flex items-center gap-3 text-xs text-muted-foreground font-medium">
                  <div className="flex items-center gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-full bg-brand-indigo" />
                    <span>Actuals</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                    <span>Forecast</span>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-4">
                <BaseChart
                  type="line"
                  data={chartData}
                  xKey="date"
                  yKeys={["Actual", "Forecast"]}
                  colors={["var(--color-brand-indigo)", "#10b981"]}
                />
              </CardContent>
            </Card>

            {/* Insights & Recommendations Panels */}
            {forecastResult && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Data Insights */}
                <Card className="border-border/80 p-4 space-y-3">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <Info className="h-4 w-4 text-brand-indigo" /> Data-Grounded Insights
                  </h3>
                  <ul className="space-y-2 text-xs leading-relaxed text-foreground">
                    {forecastResult.insights.map((ins, idx) => (
                      <li key={idx} className="flex items-start gap-2 bg-muted/20 p-2.5 rounded-md border border-border/40">
                        <span className="h-1.5 w-1.5 rounded-full bg-brand-indigo mt-1.5 shrink-0" />
                        <span>{ins}</span>
                      </li>
                    ))}
                  </ul>
                </Card>

                {/* Practical Recommendations */}
                <Card className="border-border/80 p-4 space-y-3">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <ShieldCheck className="h-4 w-4 text-emerald-500" /> Practical Business Recommendations
                  </h3>
                  <ul className="space-y-2 text-xs leading-relaxed text-foreground">
                    {forecastResult.recommendations.map((rec, idx) => (
                      <li key={idx} className="flex items-start gap-2 bg-emerald-500/5 p-2.5 rounded-md border border-emerald-500/20 text-foreground font-medium">
                        <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                        <span>{rec}</span>
                      </li>
                    ))}
                  </ul>
                </Card>
              </div>
            )}

            {/* Model Diagnostics Accordion / Metrics Table */}
            {forecastResult?.metrics && forecastResult.metrics.length > 0 && (
              <div className="space-y-3 pt-2">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-semibold tracking-tight flex items-center gap-1.5">
                    <Zap className="h-4 w-4 text-brand-indigo" /> Model Diagnostics & Cross-Validation
                  </h2>
                  <span className="text-xs text-muted-foreground">
                    Evaluated {forecastResult.metrics.length} candidate model backends
                  </span>
                </div>
                <BaseTable 
                  columns={metricColumns as any} 
                  data={forecastResult.metrics} 
                  isLoading={isExecutingForecast} 
                />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
