"use client";

import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";
import {
  Sparkles,
  Calendar,
  Layers,
  FileCheck,
  Mail,
  Clock,
  CheckSquare,
  Square,
  Eye,
  Send,
  Loader2,
  Database,
  Lock,
} from "lucide-react";
import { useProjects } from "@/features/projects/hooks/useProjects";
import { useSubscription } from "@/features/billing/hooks/useSubscription";
import { GenerateReportPayload } from "@/shared/types/reports";

interface ReportConfigPanelProps {
  onGenerate: (payload: GenerateReportPayload) => Promise<void>;
  isGenerating: boolean;
}

const REPORTING_PERIODS = [
  "Full Dataset Period",
  "Last 7 Days",
  "Last 30 Days",
  "Last 90 Days",
  "Last 12 Months",
  "Current Quarter",
  "Previous Quarter",
  "Custom Range",
];

const REPORT_TYPES = [
  "Executive Summary",
  "Sales Performance",
  "Customer Analytics",
  "Financial Performance",
  "Operations",
  "Risk & Anomaly",
  "Custom",
];

const DATA_SOURCES = [
  { id: "dashboard", label: "Dashboard KPIs" },
  { id: "sql", label: "SQL Analytics (DuckDB)" },
  { id: "forecasting", label: "Time-Series Forecasting" },
  { id: "segmentation", label: "Customer Segmentation" },
  { id: "anomaly", label: "Anomaly Detection" },
  { id: "rag", label: "Knowledge Base / RAG" },
];

const SECTION_OPTIONS = [
  { id: "kpis", label: "KPIs" },
  { id: "charts", label: "Charts" },
  { id: "summary", label: "AI Summary" },
  { id: "insights", label: "Key Insights" },
  { id: "impact", label: "Business Impact" },
  { id: "recommendations", label: "Recommendations" },
  { id: "evidence", label: "Source Evidence" },
];

export function ReportConfigPanel({ onGenerate, isGenerating }: ReportConfigPanelProps) {
  const { projects } = useProjects();

  const [title, setTitle] = useState("Executive Intelligence & Performance Report");
  const [projectId, setProjectId] = useState<string>("");
  const [period, setPeriod] = useState("Full Dataset Period");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const [reportType, setReportType] = useState("Executive Summary");
  const [selectedSources, setSelectedSources] = useState<string[]>([
    "dashboard",
    "sql",
    "forecasting",
    "segmentation",
    "anomaly",
    "rag",
  ]);
  const [outputFormat, setOutputFormat] = useState<"PDF" | "PowerPoint" | "HTML">("PDF");
  const [selectedOptions, setSelectedOptions] = useState<string[]>([
    "kpis",
    "charts",
    "summary",
    "insights",
    "impact",
    "recommendations",
    "evidence",
  ]);
  const [recipient, setRecipient] = useState("board@company.com");
  const [schedule, setSchedule] = useState<"Ad-hoc" | "Daily" | "Weekly" | "Monthly">("Ad-hoc");

  const { hasFeature, createCheckout, isCheckingOut } = useSubscription();
  const isScheduleEntitled = hasFeature("scheduled_reports");

  // Preselect Olist project if available
  React.useEffect(() => {
    if (!projectId && projects && projects.length > 0) {
      const olistProj = projects.find((p) => p.name.toLowerCase().includes("olist"));
      if (olistProj) {
        setProjectId(olistProj.id);
      }
    }
  }, [projects, projectId]);

  const selectedProject = projects.find((p) => p.id === projectId);
  const isOlist = selectedProject?.name?.toLowerCase().includes("olist") || false;

  const toggleSource = (sourceId: string) => {
    setSelectedSources((prev) =>
      prev.includes(sourceId) ? prev.filter((id) => id !== sourceId) : [...prev, sourceId]
    );
  };

  const toggleOption = (optionId: string) => {
    setSelectedOptions((prev) =>
      prev.includes(optionId) ? prev.filter((id) => id !== optionId) : [...prev, optionId]
    );
  };

  const handleSubmit = async (previewOnly: boolean = false) => {
    if (schedule !== "Ad-hoc" && !isScheduleEntitled) {
      createCheckout({ plan: "growth" });
      return;
    }
    const payload: GenerateReportPayload = {
      title,
      project_id: projectId || undefined,
      reporting_period: period,
      custom_date_range:
        period === "Custom Range" && customStart && customEnd
          ? { startDate: customStart, endDate: customEnd }
          : undefined,
      template: reportType,
      data_sources: selectedSources,
      type: outputFormat,
      options: selectedOptions,
      recipient,
      frequency: schedule,
      preview_only: previewOnly,
    };
    await onGenerate(payload);
  };

  return (
    <Card className="border border-border/80 bg-card/60 backdrop-blur shadow-sm">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-bold flex items-center gap-2 text-foreground">
            <Sparkles className="h-5 w-5 text-brand-indigo animate-pulse" />
            AI Executive Report Compiler
          </CardTitle>
          <Badge variant="outline" className="bg-brand-indigo/10 text-brand-indigo border-brand-indigo/20 text-[11px]">
            Grounding Active
          </Badge>
        </div>
        <CardDescription className="text-xs text-muted-foreground">
          Aggregate trusted outputs across analytical engines into a verified executive brief.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4 text-xs">
        {/* Report Name & Project Scope */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="space-y-1">
            <label className="font-semibold text-muted-foreground">Report Name</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full p-2 text-xs rounded-md border border-border/80 bg-background text-foreground"
              placeholder="e.g. Q3 Sales & Performance Audit"
            />
          </div>

          <div className="space-y-1">
            <label className="font-semibold text-muted-foreground flex items-center gap-1">
              <Database className="h-3.5 w-3.5" /> Project Scope
            </label>
            <select
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              className="w-full p-2 text-xs rounded-md border border-border/80 bg-background text-foreground cursor-pointer"
            >
              <option value="">Global Workspace (All Datasets)</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Reporting Period & Report Type */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="space-y-1">
            <label className="font-semibold text-muted-foreground flex items-center gap-1">
              <Calendar className="h-3.5 w-3.5" /> Reporting Period
            </label>
            <select
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              className="w-full p-2 text-xs rounded-md border border-border/80 bg-background text-foreground cursor-pointer"
            >
              {REPORTING_PERIODS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
            {isOlist && (
              <p className="text-[10px] text-brand-indigo/90 font-medium pt-0.5">
                Historical dataset: rolling periods anchor to latest dataset transactions (2016-2018).
              </p>
            )}
          </div>

          <div className="space-y-1">
            <label className="font-semibold text-muted-foreground flex items-center gap-1">
              <Layers className="h-3.5 w-3.5" /> Report Type
            </label>
            <select
              value={reportType}
              onChange={(e) => setReportType(e.target.value)}
              className="w-full p-2 text-xs rounded-md border border-border/80 bg-background text-foreground cursor-pointer"
            >
              {REPORT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Custom Range pickers if selected */}
        {period === "Custom Range" && (
          <div className="grid grid-cols-2 gap-3 p-2 rounded-md bg-muted/20 border border-border/60">
            <div className="space-y-1">
              <label className="text-[10px] text-muted-foreground font-medium">Start Date</label>
              <input
                type="date"
                value={customStart}
                onChange={(e) => setCustomStart(e.target.value)}
                className="w-full p-1.5 text-xs rounded border border-border bg-background"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] text-muted-foreground font-medium">End Date</label>
              <input
                type="date"
                value={customEnd}
                onChange={(e) => setCustomEnd(e.target.value)}
                className="w-full p-1.5 text-xs rounded border border-border bg-background"
              />
            </div>
          </div>
        )}

        {/* Data Sources selection checkboxes */}
        <div className="space-y-1.5">
          <label className="font-semibold text-muted-foreground block">
            Data Sources to Aggregate (Trusted Modules)
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {DATA_SOURCES.map((source) => {
              const isChecked = selectedSources.includes(source.id);
              return (
                <button
                  key={source.id}
                  type="button"
                  onClick={() => toggleSource(source.id)}
                  className={`flex items-center gap-2 p-2 rounded-md border text-left transition-colors ${
                    isChecked
                      ? "border-brand-indigo/60 bg-brand-indigo/10 text-foreground font-medium"
                      : "border-border/60 bg-background/50 text-muted-foreground hover:border-border"
                  }`}
                >
                  {isChecked ? (
                    <CheckSquare className="h-4 w-4 text-brand-indigo shrink-0" />
                  ) : (
                    <Square className="h-4 w-4 shrink-0 text-muted-foreground" />
                  )}
                  <span className="truncate">{source.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Output Format & Section Options */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="font-semibold text-muted-foreground flex items-center gap-1">
              <FileCheck className="h-3.5 w-3.5" /> Output Format
            </label>
            <div className="flex gap-1">
              {(["PDF", "PowerPoint", "HTML"] as const).map((fmt) => (
                <button
                  key={fmt}
                  type="button"
                  onClick={() => setOutputFormat(fmt)}
                  className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-colors ${
                    outputFormat === fmt
                      ? "bg-brand-indigo text-white shadow-sm"
                      : "bg-muted/40 text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {fmt}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="font-semibold text-muted-foreground block">Report Sections & Modules</label>
            <div className="flex flex-wrap gap-1.5">
              {SECTION_OPTIONS.map((opt) => {
                const isSelected = selectedOptions.includes(opt.id);
                return (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => toggleOption(opt.id)}
                    className={`px-2 py-1 rounded-md text-[11px] border transition-all ${
                      isSelected
                        ? "bg-muted border-border font-medium text-foreground"
                        : "bg-transparent border-border/40 text-muted-foreground hover:border-border"
                    }`}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Recipient Email & Recurring Schedule */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
          <div className="space-y-1">
            <label className="font-semibold text-muted-foreground flex items-center gap-1">
              <Mail className="h-3.5 w-3.5" /> Recipient Email
            </label>
            <input
              type="email"
              value={recipient}
              onChange={(e) => setRecipient(e.target.value)}
              className="w-full p-2 text-xs rounded-md border border-border/80 bg-background text-foreground"
              placeholder="executive@acme.com"
            />
          </div>

          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <label className="font-semibold text-muted-foreground flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" /> Scheduling Routine
              </label>
              {!isScheduleEntitled && (
                <Badge variant="info" className="text-[10px] px-1.5 py-0 h-4">
                  Growth Tier
                </Badge>
              )}
            </div>
            <select
              value={schedule}
              onChange={(e) => setSchedule(e.target.value as any)}
              className="w-full p-2 text-xs rounded-md border border-border/80 bg-background text-foreground cursor-pointer"
            >
              <option value="Ad-hoc">Ad-hoc (Immediate Compilation)</option>
              <option value="Daily">Daily at 8:00 AM {!isScheduleEntitled ? "🔒 (Growth)" : ""}</option>
              <option value="Weekly">Weekly (Every Monday) {!isScheduleEntitled ? "🔒 (Growth)" : ""}</option>
              <option value="Monthly">Monthly (1st of each month) {!isScheduleEntitled ? "🔒 (Growth)" : ""}</option>
            </select>
            {schedule !== "Ad-hoc" && !isScheduleEntitled && (
              <div className="rounded-md border border-indigo-500/30 bg-indigo-500/10 p-2 text-indigo-400 text-[11px] flex items-center justify-between gap-2 mt-1">
                <span className="flex items-center gap-1.5">
                  <Lock className="h-3.5 w-3.5 shrink-0" />
                  Recurring delivery requires Growth
                </span>
                <Button
                  size="sm"
                  type="button"
                  variant="brand"
                  className="h-6 text-[10px] px-2"
                  onClick={() => createCheckout({ plan: "growth" })}
                  disabled={isCheckingOut}
                >
                  {isCheckingOut ? "Loading..." : "Upgrade $79/mo"}
                </Button>
              </div>
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="grid grid-cols-2 gap-3 pt-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => handleSubmit(true)}
            disabled={isGenerating}
            className="w-full flex items-center gap-1.5"
          >
            {isGenerating ? (
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            ) : (
              <Eye className="h-4 w-4 text-brand-indigo" />
            )}
            Preview Brief
          </Button>

          <Button
            type="button"
            variant="brand"
            size="sm"
            onClick={() => handleSubmit(false)}
            disabled={isGenerating}
            className="w-full flex items-center gap-1.5 shadow-sm"
          >
            {isGenerating ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Aggregating & Compiling...</span>
              </>
            ) : (
              <>
                <Send className="h-4 w-4" />
                <span>Compile & Deliver</span>
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
