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
  useProjectAnomalySchemaInfo, 
  useProjectAnomalies 
} from "@/features/analytics/hooks/useForecast";
import { 
  ProjectAnomalyRequest, 
  AnomalyLogDetailed 
} from "@/shared/types/analytics";
import { 
  AlertTriangle, 
  Settings2, 
  CheckCircle2, 
  AlertCircle, 
  Calendar, 
  BarChart3, 
  FolderKanban, 
  Layers, 
  ShieldCheck, 
  Info, 
  Activity, 
  Zap
} from "lucide-react";

export default function AnomaliesPage() {
  const { activeProject, setActiveProject } = useUIStore();
  const { projects } = useProjects();

  // Pick first available project if none active in store
  useEffect(() => {
    if (!activeProject && projects.length > 0) {
      setActiveProject(projects[0].id);
    }
  }, [activeProject, projects, setActiveProject]);

  // Schema Discovery Hook
  const { 
    candidates, 
    message: schemaMessage, 
    isLoading: isLoadingSchema 
  } = useProjectAnomalySchemaInfo(activeProject);

  // Form selections state
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>("");
  const [timestampColumn, setTimestampColumn] = useState<string>("");
  const [metricColumn, setMetricColumn] = useState<string>("");
  const [detectionMethod, setDetectionMethod] = useState<"zscore" | "iqr" | "iforest">("zscore");
  const [sensitivity, setSensitivity] = useState<number>(0.05);

  // Active query configuration state
  const [activeConfig, setActiveConfig] = useState<ProjectAnomalyRequest | undefined>(undefined);

  // Sync schema candidates into form state
  useEffect(() => {
    if (candidates && candidates.length > 0) {
      const activeCand = candidates.find(c => c.dataset_id === selectedDatasetId) || candidates.find(c => c.is_time_series_capable) || candidates[0];
      setSelectedDatasetId(activeCand.dataset_id);
      const tsCol = activeCand.suggested_date || activeCand.date_columns[0] || "";
      const mCol = activeCand.suggested_metric || activeCand.metric_columns[0] || "";
      setTimestampColumn(tsCol);
      setMetricColumn(mCol);

      if (tsCol && mCol) {
        setActiveConfig({
          dataset_id: activeCand.dataset_id,
          timestamp_column: tsCol,
          metric_column: mCol,
          detection_method: "zscore",
          sensitivity: 0.05
        });
      }
    } else {
      setSelectedDatasetId("");
      setTimestampColumn("");
      setMetricColumn("");
    }
  }, [candidates, activeProject]);

  const handleDatasetChange = (datasetId: string) => {
    setSelectedDatasetId(datasetId);
    const cand = candidates.find(c => c.dataset_id === datasetId);
    if (cand) {
      setTimestampColumn(cand.suggested_date || cand.date_columns[0] || "");
      setMetricColumn(cand.suggested_metric || cand.metric_columns[0] || "");
    }
  };

  // Anomaly Query Hook
  const { 
    anomalyResult, 
    isLoading: isExecuting, 
    isError, 
    error 
  } = useProjectAnomalies(activeProject, activeConfig);

  // Local state for anomaly logs resolution toggle
  const [localLogs, setLocalLogs] = useState<AnomalyLogDetailed[]>([]);

  useEffect(() => {
    if (anomalyResult?.logs) {
      setLocalLogs(anomalyResult.logs);
    } else {
      setLocalLogs([]);
    }
  }, [anomalyResult]);

  const handleResolve = (logId: string) => {
    setLocalLogs(prev => prev.map(l => l.id === logId ? { ...l, status: l.status === "Resolved" ? "Unresolved" : "Resolved" } : l));
  };

  const handleRunDetection = () => {
    if (!selectedDatasetId || !timestampColumn || !metricColumn) return;
    setActiveConfig({
      dataset_id: selectedDatasetId,
      timestamp_column: timestampColumn,
      metric_column: metricColumn,
      detection_method: detectionMethod,
      sensitivity: sensitivity
    });
  };

  const selectedCandidate = candidates.find(c => c.dataset_id === selectedDatasetId);
  const activeProjectObj = projects.find(p => p.id === activeProject);

  // Anomaly Logs Table Columns
  const logColumns: Column<AnomalyLogDetailed>[] = [
    {
      header: "Anomaly ID",
      accessorKey: "id",
      cell: (row) => <span className="font-mono font-bold text-foreground">{row.id}</span>,
    },
    {
      header: "Timestamp",
      accessorKey: "timestamp",
      cell: (row) => <span className="font-mono text-xs text-muted-foreground">{row.timestamp}</span>,
    },
    {
      header: "Metric",
      accessorKey: "metric",
      cell: (row) => <span className="font-semibold text-foreground">{row.metric}</span>,
    },
    {
      header: "Observed",
      accessorKey: "value_formatted",
      cell: (row) => <span className="font-mono font-bold text-foreground">{row.value_formatted}</span>,
    },
    {
      header: "Expected Mean",
      accessorKey: "expected_value_formatted",
      cell: (row) => <span className="font-mono text-xs text-muted-foreground">{row.expected_value_formatted || "-"}</span>,
    },
    {
      header: "Threshold",
      accessorKey: "threshold_formatted",
      cell: (row) => <span className="font-mono text-xs text-amber-500 font-semibold">{row.threshold_formatted || "-"}</span>,
    },
    {
      header: "Deviation",
      accessorKey: "deviation",
      cell: (row) => <span className="font-mono font-bold text-rose-500 text-xs">{row.deviation}</span>,
    },
    {
      header: "Severity",
      accessorKey: "severity",
      cell: (row) => {
        const variants: Record<string, "destructive" | "warning" | "outline" | "secondary"> = {
          High: "destructive",
          Medium: "warning",
          Low: "outline",
          None: "secondary"
        };
        return <Badge variant={variants[row.severity] || "outline"} className="text-[10px] uppercase font-bold">{row.severity}</Badge>;
      },
    },
    {
      header: "Business Explanation",
      accessorKey: "explanation",
      cell: (row) => (
        <span className="text-xs text-muted-foreground leading-snug line-clamp-2 max-w-xs" title={row.explanation}>
          {row.explanation}
        </span>
      ),
    },
    {
      header: "Action",
      accessorKey: "actions",
      align: "right",
      cell: (row) => (
        <Button
          size="sm"
          variant={row.status === "Resolved" ? "ghost" : "outline"}
          className={`h-7 text-xs cursor-pointer transition-all ${
            row.status === "Resolved"
              ? "text-emerald-500 hover:text-emerald-600 bg-emerald-500/10"
              : "border-border/80 hover:bg-emerald-500/10 hover:text-emerald-500"
          }`}
          onClick={() => handleResolve(row.id)}
        >
          <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
          {row.status === "Resolved" ? "Resolved" : "Resolve"}
        </Button>
      ),
    },
  ];

  // Chart data formatting: actual metric vs upper/lower threshold boundaries
  const chartData = anomalyResult?.timeline
    ? anomalyResult.timeline.map((pt) => ({
        timestamp: pt.timestamp,
        [metricColumn || "Value"]: pt.value,
        UpperThreshold: pt.upper_limit,
        LowerThreshold: pt.lower_limit,
        AnomalyValue: pt.is_anomaly ? pt.value : undefined,
      }))
    : [];

  return (
    <div className="space-y-6">
      {/* Workspace & Header Context Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border/60 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight">Anomaly & Outlier Detection</h1>
            <Badge variant="outline" className="text-xs font-semibold gap-1">
              <FolderKanban className="h-3.5 w-3.5 text-brand-indigo" />
              <span>Project: {activeProjectObj?.name || activeProject || "None"}</span>
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Production BI anomaly monitoring evaluating dataset distributions, threshold boundaries, and ML statistical outliers.
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
              {projects.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* No Suitable Datasets Banner */}
      {!isLoadingSchema && candidates.length === 0 && (
        <Card className="border-amber-500/40 bg-amber-500/5 text-amber-600 dark:text-amber-400 p-6">
          <div className="flex items-start gap-4">
            <AlertCircle className="h-6 w-6 shrink-0 text-amber-500 mt-0.5" />
            <div className="space-y-2">
              <h3 className="text-sm font-bold text-foreground">No anomaly detection datasets available in active project</h3>
              <p className="text-xs leading-relaxed max-w-2xl">
                {schemaMessage || "To run anomaly detection, your active project requires datasets containing date/timestamp columns and numeric metrics."}
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Error Banner */}
      {(isError || (anomalyResult && anomalyResult.status === "error")) && (
        <Card className="border-rose-500/40 bg-rose-500/10 p-4 text-rose-500 text-xs font-medium flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4.5 w-4.5 shrink-0" />
            <span>{anomalyResult?.message || error?.message || "Failed to execute anomaly detection pipeline."}</span>
          </div>
        </Card>
      )}

      {/* Main Grid Layout */}
      {candidates.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Left Side: Tuning & Selector Controls Panel */}
          <Card className="border-border/80 lg:col-span-1 h-fit select-none">
            <CardHeader className="pb-3 border-b border-border/40">
              <CardTitle className="text-base font-bold flex items-center gap-1.5">
                <Settings2 className="h-4.5 w-4.5 text-brand-indigo" /> Detection Configuration
              </CardTitle>
              <CardDescription className="text-[11px]">Inspect project dataset & set algorithm bounds.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 pt-4">
              {/* Dataset Candidate Selector */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground flex items-center gap-1">
                  <Layers className="h-3.5 w-3.5 text-brand-indigo" /> Dataset Target
                </label>
                <select
                  value={selectedDatasetId}
                  onChange={(e) => handleDatasetChange(e.target.value)}
                  className="text-xs p-2 rounded-md border border-border/80 bg-background w-full text-foreground cursor-pointer font-medium"
                >
                  {candidates.map((c) => (
                    <option key={c.dataset_id} value={c.dataset_id}>
                      {c.is_derived_olist ? "✨ " + c.dataset_name : c.dataset_name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Timestamp / Date Column Picker */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground flex items-center gap-1">
                  <Calendar className="h-3.5 w-3.5 text-brand-indigo" /> Timestamp / Date Column
                </label>
                <select
                  value={timestampColumn}
                  onChange={(e) => setTimestampColumn(e.target.value)}
                  disabled={!selectedCandidate?.date_columns.length}
                  className="text-xs p-2 rounded-md border border-border/80 bg-background w-full text-foreground cursor-pointer disabled:opacity-50"
                >
                  {selectedCandidate?.date_columns.length ? (
                    selectedCandidate.date_columns.map((col) => (
                      <option key={col} value={col}>{col}</option>
                    ))
                  ) : (
                    <option value="">No date column found</option>
                  )}
                </select>
              </div>

              {/* Metric Column Picker */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground flex items-center gap-1">
                  <BarChart3 className="h-3.5 w-3.5 text-brand-indigo" /> Numeric Target Metric
                </label>
                <select
                  value={metricColumn}
                  onChange={(e) => setMetricColumn(e.target.value)}
                  disabled={!selectedCandidate?.metric_columns.length}
                  className="text-xs p-2 rounded-md border border-border/80 bg-background w-full text-foreground cursor-pointer disabled:opacity-50"
                >
                  {selectedCandidate?.metric_columns.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>

              {/* Detection Algorithm Method */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground">Detection Algorithm</label>
                <select
                  value={detectionMethod}
                  onChange={(e) => setDetectionMethod(e.target.value as any)}
                  className="text-xs p-2 rounded-md border border-border/80 bg-background w-full text-foreground cursor-pointer font-medium"
                >
                  <option value="zscore">Z-Score (Normal Distribution Quantiles)</option>
                  <option value="iqr">IQR (Tukey Boxplot Fences)</option>
                  <option value="iforest">Isolation Forest (ML Outlier Tree)</option>
                </select>
              </div>

              {/* Sensitivity Slider */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs font-semibold">
                  <span className="text-muted-foreground">Sensitivity Factor (α)</span>
                  <span className="text-rose-500 font-mono font-bold">{(sensitivity * 100).toFixed(1)}%</span>
                </div>
                <input
                  type="range"
                  min="0.01"
                  max="0.20"
                  step="0.01"
                  value={sensitivity}
                  onChange={(e) => setSensitivity(Number(e.target.value))}
                  className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-rose-500"
                />
                <p className="text-[10px] text-muted-foreground leading-relaxed mt-1 bg-muted/30 p-2 rounded border border-border/40">
                  {detectionMethod === "zscore" && `α = ${(sensitivity * 100).toFixed(1)}% sets critical Z-score quantile. Lower % strictly demands extreme standard deviation spikes.`}
                  {detectionMethod === "iqr" && `α = ${(sensitivity * 100).toFixed(1)}% calculates Tukey multiplier k. Lower % expands Q1/Q3 outer fences.`}
                  {detectionMethod === "iforest" && `α = ${(sensitivity * 100).toFixed(1)}% sets Isolation Forest expected tree contamination rate.`}
                </p>
              </div>

              {/* Run Action Button */}
              <Button
                onClick={handleRunDetection}
                disabled={isExecuting || !selectedDatasetId || !timestampColumn || !metricColumn}
                className="w-full mt-2 font-semibold cursor-pointer"
                variant="brand"
                size="sm"
              >
                {isExecuting ? "Executing Algorithm..." : "Run Anomaly Detection"}
              </Button>
            </CardContent>
          </Card>

          {/* Right Side: KPI Cards, Chart, Logs Table, Business Impact */}
          <div className="lg:col-span-3 space-y-6">
            {/* KPI Cards Row */}
            {anomalyResult && anomalyResult.status === "success" && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 rounded-xl border border-border/80 bg-card">
                  <div className="flex items-center justify-between text-muted-foreground mb-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider">Total Observations</span>
                    <Activity className="h-4 w-4 text-brand-indigo" />
                  </div>
                  <div className="text-2xl font-bold text-foreground">
                    {anomalyResult.total_observations.toLocaleString()}
                  </div>
                  <span className="text-[10px] text-muted-foreground">Scanned time-series points</span>
                </div>

                <div className="p-4 rounded-xl border border-border/80 bg-card">
                  <div className="flex items-center justify-between text-muted-foreground mb-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider">Anomalies Detected</span>
                    <AlertTriangle className="h-4 w-4 text-rose-500" />
                  </div>
                  <div className="text-2xl font-bold text-rose-500">
                    {anomalyResult.anomalies_detected}
                  </div>
                  <span className="text-[10px] text-muted-foreground">Outlier spikes & dips</span>
                </div>

                <div className="p-4 rounded-xl border border-border/80 bg-card">
                  <div className="flex items-center justify-between text-muted-foreground mb-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider">Anomaly Rate</span>
                    <Zap className="h-4 w-4 text-amber-500" />
                  </div>
                  <div className="text-2xl font-bold text-foreground">
                    {anomalyResult.anomaly_rate}%
                  </div>
                  <span className="text-[10px] text-muted-foreground">% of total series data</span>
                </div>

                <div className="p-4 rounded-xl border border-border/80 bg-card">
                  <div className="flex items-center justify-between text-muted-foreground mb-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider">Highest Severity</span>
                    <ShieldCheck className="h-4 w-4 text-emerald-500" />
                  </div>
                  <div className="text-lg font-bold text-foreground mt-1">
                    <Badge
                      variant={
                        anomalyResult.highest_severity === "High"
                          ? "destructive"
                          : anomalyResult.highest_severity === "Medium"
                          ? "warning"
                          : anomalyResult.highest_severity === "Low"
                          ? "outline"
                          : "secondary"
                      }
                      className="text-xs px-2.5 py-0.5 uppercase font-bold"
                    >
                      {anomalyResult.highest_severity}
                    </Badge>
                  </div>
                  <span className="text-[10px] text-muted-foreground mt-1 block">Maximum flagged level</span>
                </div>
              </div>
            )}

            {/* Zero Anomalies Status Banner */}
            {anomalyResult && anomalyResult.status === "success" && anomalyResult.anomalies_detected === 0 && (
              <Card className="border-emerald-500/40 bg-emerald-500/5 dark:bg-emerald-500/10 p-5">
                <div className="flex items-start gap-4">
                  <CheckCircle2 className="h-6 w-6 shrink-0 text-emerald-500 mt-0.5" />
                  <div className="space-y-2 w-full">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-bold text-foreground">
                        Zero Anomalies Detected — All Observations Within Calculated Boundaries
                      </h3>
                      <Badge variant="outline" className="text-[10px] border-emerald-500/40 text-emerald-600 dark:text-emerald-400 font-mono">
                        0.00% Anomaly Rate
                      </Badge>
                    </div>
                    <p className="text-xs leading-relaxed text-muted-foreground">
                      All <span className="font-bold text-foreground">{anomalyResult.total_observations}</span> observations for metric <span className="font-bold text-foreground">'{anomalyResult.metric_column}'</span> fell strictly within calculated statistical bounds [<span className="font-mono text-emerald-600 dark:text-emerald-400 font-bold">{anomalyResult.lower_threshold}</span>, <span className="font-mono text-emerald-600 dark:text-emerald-400 font-bold">{anomalyResult.upper_threshold}</span>].
                    </p>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2 text-xs border-t border-emerald-500/20">
                      <div>
                        <span className="text-[10px] text-muted-foreground block">Observation Count:</span>
                        <span className="font-bold text-foreground font-mono">{anomalyResult.total_observations}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-muted-foreground block">Observed Range:</span>
                        <span className="font-bold text-foreground font-mono">{anomalyResult.min_observed} to {anomalyResult.max_observed}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-muted-foreground block">Baseline Mean:</span>
                        <span className="font-bold text-foreground font-mono">{anomalyResult.mean_observed}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-muted-foreground block">Calculated Bounds:</span>
                        <span className="font-bold text-emerald-600 dark:text-emerald-400 font-mono">{anomalyResult.lower_threshold} ~ {anomalyResult.upper_threshold}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </Card>
            )}

            {/* Anomaly Detection Chart */}
            <Card className="border-border/80">
              <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-border/40 bg-muted/10">
                <div>
                  <CardTitle className="text-base font-bold flex items-center gap-2">
                    <Activity className="h-4.5 w-4.5 text-brand-indigo" />
                    <span>Time Series Outlier Boundaries</span>
                  </CardTitle>
                  <CardDescription className="text-[11px]">
                    Solid line plots metric observations ({metricColumn || "Metric"}); dashed lines mark upper/lower statistical limits.
                  </CardDescription>
                </div>
                <div className="flex items-center gap-3 text-xs text-muted-foreground font-medium mt-2 sm:mt-0">
                  <div className="flex items-center gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-full bg-brand-indigo" />
                    <span>{metricColumn || "Observed"}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-full bg-rose-500" />
                    <span>Upper Threshold</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
                    <span>Lower Threshold</span>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-4">
                {chartData.length > 0 ? (
                  <BaseChart
                    type="line"
                    data={chartData}
                    xKey="timestamp"
                    yKeys={[metricColumn || "Value", "UpperThreshold", "LowerThreshold"]}
                    colors={["var(--color-brand-indigo)", "#ef4444", "#f59e0b"]}
                  />
                ) : (
                  <div className="h-[280px] flex items-center justify-center text-xs text-muted-foreground">
                    {isExecuting ? "Executing anomaly detection algorithm..." : "No timeline data to display."}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Business Impact & Recommended Actions */}
            {anomalyResult && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Business Impact */}
                <Card className="border-border/80 p-4 space-y-3">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <Info className="h-4 w-4 text-brand-indigo" /> Business Impact & Insights
                  </h3>
                  <ul className="space-y-2 text-xs leading-relaxed text-foreground">
                    {anomalyResult.business_impact.map((ins, idx) => (
                      <li key={idx} className="flex items-start gap-2 bg-muted/20 p-2.5 rounded-md border border-border/40">
                        <span className="h-1.5 w-1.5 rounded-full bg-brand-indigo mt-1.5 shrink-0" />
                        <span>{ins}</span>
                      </li>
                    ))}
                  </ul>
                </Card>

                {/* Recommended Actions */}
                <Card className="border-border/80 p-4 space-y-3">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <ShieldCheck className="h-4 w-4 text-emerald-500" /> Actionable Recommendations
                  </h3>
                  <ul className="space-y-2 text-xs leading-relaxed text-foreground">
                    {anomalyResult.recommended_actions.map((rec, idx) => (
                      <li key={idx} className="flex items-start gap-2 bg-emerald-500/5 p-2.5 rounded-md border border-emerald-500/20 text-foreground font-medium">
                        <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                        <span>{rec}</span>
                      </li>
                    ))}
                  </ul>
                </Card>
              </div>
            )}

            {/* Anomalies Log Feed Table */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold tracking-tight flex items-center gap-1.5">
                  <AlertTriangle className="h-4 w-4 text-rose-500" /> Flagged Outliers & Anomalies Log Feed
                </h2>
                <span className="text-xs text-muted-foreground font-mono">
                  {localLogs.length} total anomalies logged
                </span>
              </div>
              <BaseTable columns={logColumns as any} data={localLogs} isLoading={isExecuting} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
