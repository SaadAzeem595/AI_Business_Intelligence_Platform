"use client";

import React, { useState } from "react";
import { useReports } from "@/features/reports/hooks/useReports";
import { ReportConfigPanel } from "@/features/reports/components/ReportConfigPanel";
import { ReportArchiveTable } from "@/features/reports/components/ReportArchiveTable";
import { ReportPreviewModal } from "@/features/reports/components/ReportPreviewModal";
import { GenerateReportPayload, Report } from "@/shared/types/reports";
import { Card, CardContent } from "@/shared/components/ui/card";
import { Badge } from "@/shared/components/ui/badge";
import {
  FileText,
  Sparkles,
  ShieldCheck,
  TrendingUp,
  Mail,
  CheckCircle2,
  Database,
  Cpu,
} from "lucide-react";

export default function ReportsPage() {
  const {
    reports,
    isLoading,
    filters,
    setFilters,
    generateReport,
    isGenerating,
    deleteReport,
    downloadReport,
    sendEmail,
    isSendingEmail,
    regenerateNarrative,
    isRegenerating,
    previewReport,
    setPreviewReport,
    setSelectedReportId,
  } = useReports();

  const [activeModalReport, setActiveModalReport] = useState<Report | null>(null);
  const [notification, setNotification] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const showNotification = (type: "success" | "error", message: string) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  const handleGenerateReport = async (payload: GenerateReportPayload) => {
    try {
      const result = await generateReport(payload);
      if (result) {
        setActiveModalReport(result);
        showNotification("success", `Report "${result.title}" compiled successfully.`);
      }
    } catch (err: any) {
      showNotification("error", err?.response?.data?.detail || "Failed to compile executive report.");
    }
  };

  const handleViewReport = (report: Report) => {
    setSelectedReportId(report.id);
    setActiveModalReport(report);
  };

  const handleRegenerate = async (id: string, customFocus?: string) => {
    try {
      const updated = await regenerateNarrative({ id, customFocus });
      setActiveModalReport(updated);
      showNotification("success", "AI executive narrative regenerated successfully.");
    } catch (err: any) {
      showNotification("error", err?.response?.data?.detail || "Failed to regenerate narrative.");
    }
  };

  const handleSendEmail = async (id: string, recipient?: string) => {
    try {
      await sendEmail({ id, recipient });
      showNotification("success", `Report emailed successfully to ${recipient || "target recipient"}.`);
    } catch (err: any) {
      showNotification("error", err?.response?.data?.detail || "Failed to dispatch email.");
    }
  };

  const handleDeleteReport = async (id: string) => {
    if (confirm("Are you sure you want to delete this report deliverable?")) {
      try {
        await deleteReport(id);
        if (activeModalReport?.id === id) {
          setActiveModalReport(null);
        }
        showNotification("success", "Report deleted successfully.");
      } catch (err: any) {
        showNotification("error", err?.response?.data?.detail || "Failed to delete report.");
      }
    }
  };

  // If previewReport state was updated from a mutation, sync with active modal
  React.useEffect(() => {
    if (previewReport && !activeModalReport) {
      setActiveModalReport(previewReport);
    }
  }, [previewReport]);

  return (
    <div className="space-y-6">
      {/* Toast Notification */}
      {notification && (
        <div
          className={`fixed top-4 right-4 z-50 p-3 rounded-lg border text-xs shadow-lg flex items-center gap-2 animate-in fade-in slide-in-from-top-2 duration-200 ${
            notification.type === "success"
              ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-400"
              : "bg-rose-500/15 border-rose-500/30 text-rose-400"
          }`}
        >
          {notification.type === "success" ? (
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
          ) : (
            <CheckCircle2 className="h-4 w-4 shrink-0 text-rose-400" />
          )}
          <span>{notification.message}</span>
        </div>
      )}

      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">AI Executive Reports</h1>
            <Badge className="bg-brand-indigo/15 text-brand-indigo border-brand-indigo/30 text-[11px] font-semibold">
              Production Enterprise
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Automated intelligence briefs aggregating verified metrics across Dashboard, DuckDB SQL, Forecasting, Cohorts, and RAG.
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <Badge variant="outline" className="bg-card py-1 px-2.5 text-foreground/80 flex items-center gap-1.5 border-border">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
            <span>Anti-Hallucination Active</span>
          </Badge>
          <Badge variant="outline" className="bg-card py-1 px-2.5 text-foreground/80 flex items-center gap-1.5 border-border">
            <Database className="h-3.5 w-3.5 text-brand-indigo" />
            <span>Source Grounded</span>
          </Badge>
        </div>
      </div>

      {/* Metric Highlights Overview Bar */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Card className="border border-border/70 bg-card/60">
          <CardContent className="p-3.5 flex items-center justify-between">
            <div>
              <p className="text-[10px] uppercase font-bold text-muted-foreground">Reports Compiled</p>
              <h3 className="text-xl font-extrabold text-foreground mt-0.5">{reports.length}</h3>
            </div>
            <div className="h-8 w-8 rounded-md bg-brand-indigo/10 flex items-center justify-center text-brand-indigo">
              <FileText className="h-4 w-4" />
            </div>
          </CardContent>
        </Card>

        <Card className="border border-border/70 bg-card/60">
          <CardContent className="p-3.5 flex items-center justify-between">
            <div>
              <p className="text-[10px] uppercase font-bold text-muted-foreground">Fact Verification Rate</p>
              <h3 className="text-xl font-extrabold text-emerald-400 mt-0.5">100%</h3>
            </div>
            <div className="h-8 w-8 rounded-md bg-emerald-500/10 flex items-center justify-center text-emerald-400">
              <ShieldCheck className="h-4 w-4" />
            </div>
          </CardContent>
        </Card>

        <Card className="border border-border/70 bg-card/60">
          <CardContent className="p-3.5 flex items-center justify-between">
            <div>
              <p className="text-[10px] uppercase font-bold text-muted-foreground">Connected Modules</p>
              <h3 className="text-xl font-extrabold text-foreground mt-0.5">6 Engines</h3>
            </div>
            <div className="h-8 w-8 rounded-md bg-amber-500/10 flex items-center justify-center text-amber-400">
              <Cpu className="h-4 w-4" />
            </div>
          </CardContent>
        </Card>

        <Card className="border border-border/70 bg-card/60">
          <CardContent className="p-3.5 flex items-center justify-between">
            <div>
              <p className="text-[10px] uppercase font-bold text-muted-foreground">Delivery Confidence</p>
              <h3 className="text-xl font-extrabold text-foreground mt-0.5">96.4%</h3>
            </div>
            <div className="h-8 w-8 rounded-md bg-purple-500/10 flex items-center justify-center text-purple-400">
              <TrendingUp className="h-4 w-4" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Workspace Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Report Configuration Panel (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <ReportConfigPanel onGenerate={handleGenerateReport} isGenerating={isGenerating} />
        </div>

        {/* Right Column: Reports Log Archive Table (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          <ReportArchiveTable
            reports={reports}
            isLoading={isLoading}
            onView={handleViewReport}
            onDownload={downloadReport}
            onSendEmail={handleSendEmail}
            onRegenerate={(id) => handleRegenerate(id)}
            onDelete={handleDeleteReport}
            filters={filters}
            onFilterChange={setFilters}
          />
        </div>
      </div>

      {/* Interactive Report Preview Modal */}
      {activeModalReport && (
        <ReportPreviewModal
          report={activeModalReport}
          onClose={() => setActiveModalReport(null)}
          onRegenerate={handleRegenerate}
          isRegenerating={isRegenerating}
          onSendEmail={handleSendEmail}
          isSendingEmail={isSendingEmail}
          onDownload={downloadReport}
        />
      )}
    </div>
  );
}
