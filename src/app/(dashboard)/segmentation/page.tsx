"use client";

import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";
import { BaseChart } from "@/shared/components/data-display/BaseChart";
import { BaseTable, type Column } from "@/shared/components/data-display/BaseTable";
import { 
  Sliders, 
  Sparkles, 
  AlertCircle, 
  CheckCircle2, 
  Info, 
  Target, 
  FolderKanban, 
  Layers, 
  Key, 
  BarChart2, 
  Check 
} from "lucide-react";
import { useUIStore } from "@/shared/services/uiStore";
import { useProjects } from "@/features/projects/hooks/useProjects";
import { useSegmentation, useSegmentSchemaInfo } from "@/features/analytics/hooks/useForecast";
import { CohortSegment, SegmentProfile } from "@/shared/types/analytics";

export default function SegmentationPage() {
  const { activeProject, setActiveProject } = useUIStore();
  const { projects } = useProjects();

  // If no active project selected in store, pick first available project
  useEffect(() => {
    if (!activeProject && projects.length > 0) {
      setActiveProject(projects[0].id);
    }
  }, [activeProject, projects, setActiveProject]);

  // Project Segmentation Schema Candidates Hook
  const { 
    candidates, 
    message: schemaMessage, 
    isLoading: isLoadingSchema 
  } = useSegmentSchemaInfo(activeProject);

  // Form selection states
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>("");
  const [entityKey, setEntityKey] = useState<string>("");
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([]);
  const [clustersCount, setClustersCount] = useState<number>(3);
  const [modeOption, setModeOption] = useState<string>("auto");

  // Sync schema candidates into form state when activeProject or candidates change
  useEffect(() => {
    if (candidates && candidates.length > 0) {
      const activeCand = candidates.find((c: any) => c.dataset_id === selectedDatasetId) || candidates[0];
      setSelectedDatasetId(activeCand.dataset_id);
      setEntityKey(activeCand.entity_key || activeCand.available_entity_keys?.[0] || "");
      setSelectedFeatures(activeCand.suggested_features || activeCand.numerical_features || []);
      setModeOption(activeCand.suggested_mode || "auto");
    } else {
      setSelectedDatasetId("");
      setEntityKey("");
      setSelectedFeatures([]);
    }
  }, [candidates, activeProject]);

  const handleDatasetChange = (candId: string) => {
    setSelectedDatasetId(candId);
    const cand = candidates.find((c: any) => c.dataset_id === candId);
    if (cand) {
      setEntityKey(cand.entity_key || cand.available_entity_keys?.[0] || "");
      setSelectedFeatures(cand.suggested_features || cand.numerical_features || []);
      setModeOption(cand.suggested_mode || "auto");
    }
  };

  const toggleFeature = (feat: string) => {
    setSelectedFeatures((prev) =>
      prev.includes(feat) ? prev.filter((f) => f !== feat) : [...prev, feat]
    );
  };

  const selectedCandidate = candidates.find((c: any) => c.dataset_id === selectedDatasetId);
  const featuresParam = selectedFeatures.join(",");

  const {
    scatterData,
    cohorts,
    evaluation,
    profiles,
    featuresUsed,
    datasetType,
    entityKey: resolvedEntityKey,
    isLoading,
    isError,
    error,
    refetch,
  } = useSegmentation(
    clustersCount,
    featuresParam || undefined,
    selectedDatasetId || undefined,
    activeProject || undefined,
    modeOption,
    entityKey || undefined
  );

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
        const variants: Record<string, "success" | "warning" | "destructive" | "secondary" | "outline"> = {
          Low: "success",
          Medium: "warning",
          High: "destructive",
          Neutral: "secondary",
          "N/A": "outline",
        };
        return <Badge variant={variants[row.riskRating] || "outline"}>{row.riskRating}</Badge>;
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

  const activeProjectObj = projects.find((p) => p.id === activeProject);

  return (
    <div className="space-y-6">
      {/* Title Header & Workspace Context Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border/60 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight">Customer & Tabular Segmentation</h1>
            <Badge variant="outline" className="text-xs font-semibold gap-1">
              <FolderKanban className="h-3.5 w-3.5 text-brand-indigo" />
              <span>Project: {activeProjectObj?.name || activeProject || "None"}</span>
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Data-driven cohort clustering analyzing project datasets with automated K evaluation and business-readable persona mapping.
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

      {/* No Datasets Banner */}
      {!isLoadingSchema && candidates.length === 0 && (
        <Card className="border-amber-500/40 bg-amber-500/5 text-amber-600 dark:text-amber-400 p-6">
          <div className="flex items-start gap-4">
            <AlertCircle className="h-6 w-6 shrink-0 text-amber-500 mt-0.5" />
            <div className="space-y-2">
              <h3 className="text-sm font-bold text-foreground">No datasets available in active project</h3>
              <p className="text-xs leading-relaxed max-w-2xl">
                {schemaMessage || "To run cohort segmentation, please upload a dataset CSV/Excel file or assign an active dataset to this project."}
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Error State Alert */}
      {isError && (
        <Card className="border-destructive/50 bg-destructive/5">
          <CardContent className="pt-6 flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h4 className="text-sm font-semibold text-destructive">Segmentation Execution Error</h4>
              <p className="text-xs text-muted-foreground">
                {error?.response?.data?.detail || error?.message || "Failed to execute clustering on active dataset. Please verify dataset selection."}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main Layout Grid */}
      {candidates.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Left Tuning Panel */}
          <Card className="border-border/80 lg:col-span-1 h-fit select-none">
            <CardHeader className="pb-3 border-b border-border/40">
              <CardTitle className="text-base font-bold flex items-center gap-1.5">
                <Sliders className="h-4.5 w-4.5 text-brand-indigo" /> Segment Parameters
              </CardTitle>
              <CardDescription className="text-[11px]">Select dataset & tune clustering features.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 pt-4">
              {/* Dataset Target Selector */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground flex items-center gap-1">
                  <Layers className="h-3.5 w-3.5 text-brand-indigo" /> Dataset Target
                </label>
                <select
                  value={selectedDatasetId}
                  onChange={(e) => handleDatasetChange(e.target.value)}
                  className="text-xs p-2 rounded-md border border-border/80 bg-background w-full text-foreground cursor-pointer font-medium"
                >
                  {candidates.map((c: any) => (
                    <option key={c.dataset_id} value={c.dataset_id}>
                      {c.dataset_name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Entity Key Column Picker */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground flex items-center gap-1">
                  <Key className="h-3.5 w-3.5 text-brand-indigo" /> Entity / Key Column
                </label>
                <select
                  value={entityKey}
                  onChange={(e) => setEntityKey(e.target.value)}
                  className="text-xs p-2 rounded-md border border-border/80 bg-background w-full text-foreground cursor-pointer font-medium"
                >
                  {selectedCandidate?.available_entity_keys?.length ? (
                    selectedCandidate.available_entity_keys.map((k: string) => (
                      <option key={k} value={k}>{k}</option>
                    ))
                  ) : (
                    <option value={entityKey || ""}>{entityKey || "Auto-detect Key"}</option>
                  )}
                </select>
              </div>

              {/* Feature Engineering Mode */}
              <div className="space-y-1.5">
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

              {/* Cluster Count Slider */}
              <div className="space-y-1.5">
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
                  <div className="space-y-1 mt-1.5 p-2 rounded-md bg-brand-indigo/5 border border-brand-indigo/20 text-[11px]">
                    <div className="flex justify-between items-center text-foreground font-semibold">
                      <span>Recommended K:</span>
                      <span className="font-bold text-brand-indigo">{evaluation.optimal_k}</span>
                    </div>
                    <div className="flex justify-between items-center text-muted-foreground">
                      <span>Currently Selected K:</span>
                      <span className="font-bold">{clustersCount}</span>
                    </div>
                    {clustersCount === evaluation.optimal_k ? (
                      <div className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-medium text-[10px] mt-0.5">
                        <CheckCircle2 className="h-3 w-3 shrink-0" />
                        <span>Selected K matches Optimal K</span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1 text-amber-600 dark:text-amber-400 font-medium text-[10px] mt-0.5">
                        <Info className="h-3 w-3 shrink-0" />
                        <span>Custom Selected K (Optimal: {evaluation.optimal_k})</span>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Available Features Checklist */}
              {selectedCandidate?.numerical_features && selectedCandidate.numerical_features.length > 0 && (
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-muted-foreground flex items-center justify-between">
                    <span>Select Clustering Features</span>
                    <span className="text-[10px] text-brand-indigo font-normal">
                      {selectedFeatures.length}/{selectedCandidate.numerical_features.length} selected
                    </span>
                  </label>
                  <div className="flex flex-wrap gap-1 max-h-36 overflow-y-auto p-1.5 border border-border/60 rounded-md bg-muted/10">
                    {selectedCandidate.numerical_features.map((feat: string) => {
                      const isSelected = selectedFeatures.includes(feat);
                      return (
                        <button
                          key={feat}
                          type="button"
                          onClick={() => toggleFeature(feat)}
                          className={`text-[10px] px-2 py-0.5 rounded-md font-mono flex items-center gap-1 cursor-pointer transition-all ${
                            isSelected
                              ? "bg-brand-indigo text-white shadow-xs font-semibold"
                              : "bg-muted text-muted-foreground hover:bg-muted/80"
                          }`}
                        >
                          {isSelected && <Check className="h-3 w-3" />}
                          <span>{feat}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              <Button onClick={handleRunCluster} disabled={isLoading} className="w-full mt-4 cursor-pointer font-semibold" variant="brand" size="sm">
                {isLoading ? "Computing clusters..." : "Run Clustering Model"}
              </Button>
            </CardContent>
          </Card>

          {/* Right Visuals & Cohorts Section */}
          <div className="lg:col-span-3 space-y-6">
            {/* Context Summary Metadata Card */}
            <Card className="border-border/80 bg-card p-4 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/40 pb-2">
                <div className="flex items-center gap-2">
                  <BarChart2 className="h-4 w-4 text-brand-indigo" />
                  <span className="text-xs font-bold text-foreground">
                    Active Segmentation Target: {selectedCandidate?.dataset_name || "Dataset"}
                  </span>
                </div>
                <Badge variant="outline" className="text-[11px] border-brand-indigo/30 bg-brand-indigo/5 text-brand-indigo">
                  Mode: {datasetType || modeOption} {resolvedEntityKey ? `(Key: ${resolvedEntityKey})` : ""}
                </Badge>
              </div>
              <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                <div>
                  <span className="font-semibold text-foreground">Project: </span>
                  <span>{activeProjectObj?.name || activeProject}</span>
                </div>
                <div>
                  <span className="font-semibold text-foreground">Dataset ID: </span>
                  <span className="font-mono text-[11px]">{selectedDatasetId}</span>
                </div>
                <div>
                  <span className="font-semibold text-foreground">Entity Key: </span>
                  <span className="font-mono text-[11px]">{resolvedEntityKey || entityKey || "Auto"}</span>
                </div>
                <div>
                  <span className="font-semibold text-foreground">Features Engaged: </span>
                  <span>{(featuresUsed && featuresUsed.length > 0 ? featuresUsed : selectedFeatures).join(", ")}</span>
                </div>
              </div>
            </Card>

            {/* Evaluation Metrics Cards */}
            {evaluation && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="p-3 rounded-lg border border-border/80 bg-card">
                  <span className="text-[10px] text-muted-foreground uppercase font-semibold">Recommended vs Selected K</span>
                  <div className="text-sm font-bold text-foreground mt-0.5 flex items-baseline gap-1">
                    <span className="text-lg text-brand-indigo">{evaluation.selected_k ?? clustersCount}</span>
                    <span className="text-xs text-muted-foreground font-normal">(Rec: {evaluation.optimal_k})</span>
                  </div>
                  <span className="text-[10px] text-muted-foreground">Currently Selected vs Optimal K</span>
                </div>
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
                                : prof.risk_rating === "Medium"
                                ? "warning"
                                : prof.risk_rating === "Neutral"
                                ? "secondary"
                                : "outline"
                            }
                            className="text-[10px]"
                          >
                            {prof.risk_rating === "Neutral" || prof.risk_rating === "N/A"
                              ? `Risk Rating: ${prof.risk_rating}`
                              : `${prof.risk_rating} Risk`}
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
      )}
    </div>
  );
}

