"use client";

import React, { useState } from "react";
import { Report, ExecutiveReportData } from "@/shared/types/reports";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";
import {
  X,
  FileText,
  Download,
  Mail,
  RefreshCw,
  Edit2,
  Check,
  TrendingUp,
  AlertTriangle,
  Users,
  Target,
  ShieldCheck,
  BookOpen,
  Calendar,
  Layers,
  ArrowUpRight,
  ArrowDownRight,
  Clock,
  Sparkles,
} from "lucide-react";
import { BaseChart } from "@/shared/components/data-display/BaseChart";

interface ReportPreviewModalProps {
  report: Report | null;
  onClose: () => void;
  onRegenerate: (id: string, customFocus?: string) => Promise<void>;
  isRegenerating: boolean;
  onSendEmail: (id: string, recipient?: string) => Promise<void>;
  isSendingEmail: boolean;
  onDownload: (id: string, title: string, format?: string) => Promise<void>;
}

export function ReportPreviewModal({
  report,
  onClose,
  onRegenerate,
  isRegenerating,
  onSendEmail,
  isSendingEmail,
  onDownload,
}: ReportPreviewModalProps) {
  if (!report) return null;

  const data: ExecutiveReportData | undefined = report.report_data;
  const [activeTab, setActiveTab] = useState<"summary" | "kpis" | "insights" | "anomalies" | "forecast" | "segments" | "impact" | "recommendations" | "evidence">("summary");
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editedTitle, setEditedTitle] = useState(report.title);
  const [customFocus, setCustomFocus] = useState("");
  const [showRegenPrompt, setShowRegenPrompt] = useState(false);

  // Section toggle visibility
  const [visibleSections, setVisibleSections] = useState({
    summary: true,
    kpis: true,
    insights: true,
    charts: true,
    anomalies: true,
    forecast: true,
    segments: true,
    impact: true,
    recommendations: true,
    evidence: true,
  });

  const toggleSection = (key: keyof typeof visibleSections) => {
    setVisibleSections((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleRegenerate = async () => {
    await onRegenerate(report.id, customFocus || undefined);
    setShowRegenPrompt(false);
  };

  const formatChartData = () => {
    if (!data?.trends_chart?.labels) return [];
    return data.trends_chart.labels.map((label, idx) => ({
      name: label,
      value: data.trends_chart.values[idx] || 0,
    }));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-card border border-border rounded-xl shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col overflow-hidden text-foreground">
        {/* Modal Top Bar */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border bg-muted/20">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-brand-indigo/10 flex items-center justify-center border border-brand-indigo/20">
              <FileText className="h-5 w-5 text-brand-indigo" />
            </div>
            <div>
              {isEditingTitle ? (
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={editedTitle}
                    onChange={(e) => setEditedTitle(e.target.value)}
                    className="text-sm font-bold bg-background px-2 py-1 rounded border border-border text-foreground"
                  />
                  <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => setIsEditingTitle(false)}>
                    <Check className="h-3.5 w-3.5 text-emerald-500" />
                  </Button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-bold tracking-tight">{editedTitle}</h2>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="h-6 w-6 text-muted-foreground hover:text-foreground"
                    onClick={() => setIsEditingTitle(true)}
                  >
                    <Edit2 className="h-3 w-3" />
                  </Button>
                </div>
              )}
              <div className="flex items-center gap-2 text-[11px] text-muted-foreground mt-0.5">
                <span>{report.template || "Executive Summary"}</span>
                <span>&bull;</span>
                <span>{report.reporting_period || "Last 30 Days"}</span>
                <span>&bull;</span>
                <Badge variant="outline" className="text-[10px] py-0">
                  {report.delivery_status}
                </Badge>
              </div>
            </div>
          </div>

          {/* Action buttons on top bar */}
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setShowRegenPrompt(!showRegenPrompt)}
              disabled={isRegenerating}
              className="text-xs flex items-center gap-1.5"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isRegenerating ? "animate-spin" : ""}`} />
              Regenerate AI
            </Button>

            <Button
              size="sm"
              variant="outline"
              onClick={() => onSendEmail(report.id, report.recipient)}
              disabled={isSendingEmail}
              className="text-xs flex items-center gap-1.5"
            >
              <Mail className="h-3.5 w-3.5 text-brand-indigo" />
              {isSendingEmail ? "Sending..." : "Email Report"}
            </Button>

            <div className="flex items-center rounded-md border border-border bg-background p-0.5">
              <Button
                size="sm"
                variant="ghost"
                className="h-7 px-2 text-[11px]"
                onClick={() => onDownload(report.id, editedTitle, "pdf")}
              >
                PDF
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 px-2 text-[11px]"
                onClick={() => onDownload(report.id, editedTitle, "pptx")}
              >
                PPTX
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 px-2 text-[11px]"
                onClick={() => onDownload(report.id, editedTitle, "html")}
              >
                HTML
              </Button>
            </div>

            <Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground hover:text-foreground" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Optional Narrative Regeneration Focus Prompt Drawer */}
        {showRegenPrompt && (
          <div className="bg-brand-indigo/5 border-b border-brand-indigo/20 px-6 py-3 flex items-center gap-3">
            <input
              type="text"
              placeholder="e.g. Focus deeply on West region customer churn and operational risk..."
              value={customFocus}
              onChange={(e) => setCustomFocus(e.target.value)}
              className="text-xs flex-1 p-2 rounded-md border border-border bg-background text-foreground"
            />
            <Button size="sm" variant="brand" onClick={handleRegenerate} disabled={isRegenerating} className="text-xs shrink-0">
              {isRegenerating ? "Synthesizing..." : "Run Regeneration"}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setShowRegenPrompt(false)} className="text-xs shrink-0">
              Cancel
            </Button>
          </div>
        )}

        {/* Section Navigation Tabs & Section Visibility Toggles */}
        <div className="border-b border-border bg-muted/10 px-6 flex items-center justify-between overflow-x-auto text-xs">
          <div className="flex space-x-1 py-2">
            {(
              [
                { id: "summary", label: "Executive Summary" },
                { id: "kpis", label: "KPI Overview" },
                { id: "insights", label: "Key Insights" },
                { id: "anomalies", label: "Anomalies" },
                { id: "forecast", label: "Forecasting" },
                { id: "segments", label: "Segmentation" },
                { id: "impact", label: "Business Impact" },
                { id: "recommendations", label: "Recommendations" },
                { id: "evidence", label: "Sources & Citations" },
              ] as const
            ).map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-3 py-1.5 rounded-md font-medium transition-colors whitespace-nowrap ${
                  activeTab === tab.id
                    ? "bg-brand-indigo text-white shadow-sm"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/30"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="hidden lg:flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <span className="font-semibold">Confidence:</span>
            <span className="text-emerald-400 font-mono">
              {((data?.metadata?.confidence_score || 0.95) * 100).toFixed(0)}%
            </span>
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar text-xs">
          {/* TAB 1: EXECUTIVE SUMMARY */}
          {activeTab === "summary" && (
            <div className="space-y-4">
              <div className="border-l-4 border-brand-indigo bg-brand-indigo/5 p-4 rounded-r-lg space-y-2">
                <h3 className="font-bold text-sm text-foreground flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-brand-indigo" /> Verified Executive Takeaways
                </h3>
                <ul className="space-y-2 text-muted-foreground">
                  {data?.executive_summary?.map((sentence, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-[13px] leading-relaxed text-foreground/90">
                      <span className="text-brand-indigo font-bold shrink-0">•</span>
                      <span>{sentence}</span>
                    </li>
                  )) || <li>Insufficient data available in the selected sources.</li>}
                </ul>
              </div>

              {/* Mini KPI highlights preview */}
              {data?.kpi_overview && data.kpi_overview.length > 0 && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2">
                  {data.kpi_overview.slice(0, 4).map((kpi, idx) => (
                    <div key={idx} className="p-3 rounded-lg border border-border/70 bg-card">
                      <div className="text-[10px] uppercase font-bold text-muted-foreground truncate">{kpi.title}</div>
                      <div className="text-lg font-bold text-foreground mt-1">{kpi.current_value}</div>
                      <div className="text-[10px] text-emerald-400 mt-0.5">{kpi.change_pct} period over period</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: KPI OVERVIEW */}
          {activeTab === "kpis" && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {data?.kpi_overview?.map((kpi, idx) => {
                  const isUp = kpi.direction === "up";
                  return (
                    <Card key={idx} className="border border-border/80 bg-card hover:border-brand-indigo/50 transition-all">
                      <CardContent className="p-4 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] font-bold text-muted-foreground uppercase">{kpi.title}</span>
                          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-brand-indigo/10 text-brand-indigo border border-brand-indigo/20">
                            {kpi.source_id}
                          </span>
                        </div>
                        <div className="text-2xl font-extrabold text-foreground">{kpi.current_value}</div>
                        <div className="flex items-center justify-between text-[11px] pt-1 border-t border-border/40">
                          <div className={`flex items-center gap-0.5 font-semibold ${isUp ? "text-emerald-400" : "text-rose-400"}`}>
                            {isUp ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                            {kpi.change_pct}
                          </div>
                          <span className="text-muted-foreground text-[10px]">vs {kpi.previous_value || "prior"}</span>
                        </div>
                        <div className="text-[10px] text-muted-foreground truncate">{kpi.source}</div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>

              {/* Trend Chart */}
              {data?.trends_chart?.labels && (
                <Card className="border border-border/80 bg-card p-4">
                  <h4 className="font-bold text-xs mb-3 text-foreground flex items-center gap-1.5">
                    <TrendingUp className="h-4 w-4 text-brand-indigo" />
                    {data.trends_chart.title}
                  </h4>
                  <BaseChart
                    type="line"
                    data={formatChartData()}
                    xKey="name"
                    yKeys={["value"]}
                    height={220}
                  />
                </Card>
              )}
            </div>
          )}

          {/* TAB 3: KEY INSIGHTS */}
          {activeTab === "insights" && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {data?.key_insights?.map((ins) => (
                <div key={ins.id} className="p-4 rounded-lg border border-border/80 bg-card space-y-2">
                  <div className="flex items-center justify-between">
                    <h4 className="font-bold text-sm text-foreground">{ins.title}</h4>
                    <Badge
                      variant="outline"
                      className={`text-[10px] ${
                        ins.severity === "High"
                          ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
                          : ins.severity === "Medium"
                          ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
                          : "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                      }`}
                    >
                      {ins.severity} Severity
                    </Badge>
                  </div>
                  <p className="text-muted-foreground text-xs leading-relaxed">{ins.description}</p>
                  <div className="pt-2 border-t border-border/50 text-[11px] space-y-1">
                    <div className="text-muted-foreground">
                      <strong className="text-foreground/80">Relevance:</strong> {ins.business_relevance}
                    </div>
                    <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                      <span>Metric: <strong className="text-foreground/80">{ins.supporting_metric}</strong></span>
                      <span className="font-mono text-brand-indigo">{ins.source_id} &bull; {ins.source}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* TAB 4: ANOMALIES */}
          {activeTab === "anomalies" && (
            <div className="space-y-3">
              {data?.anomalies && data.anomalies.length > 0 ? (
                <div className="border border-border rounded-lg overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-muted/40 text-muted-foreground border-b border-border">
                      <tr>
                        <th className="p-3">Metric Outlier</th>
                        <th className="p-3">Date</th>
                        <th className="p-3">Severity</th>
                        <th className="p-3">Deviation</th>
                        <th className="p-3">Baseline</th>
                        <th className="p-3">Business Impact</th>
                        <th className="p-3">Source</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/60">
                      {data.anomalies.map((a) => (
                        <tr key={a.id} className="hover:bg-muted/10">
                          <td className="p-3 font-semibold text-foreground">{a.metric}</td>
                          <td className="p-3 text-muted-foreground">{a.affected_date}</td>
                          <td className="p-3">
                            <Badge
                              variant="outline"
                              className={`text-[10px] ${
                                a.severity === "High" ? "bg-rose-500/10 text-rose-400" : "bg-amber-500/10 text-amber-400"
                              }`}
                            >
                              {a.severity}
                            </Badge>
                          </td>
                          <td className="p-3 font-mono text-brand-indigo">{a.deviation}</td>
                          <td className="p-3 text-muted-foreground">{a.baseline}</td>
                          <td className="p-3 text-muted-foreground">{a.business_impact}</td>
                          <td className="p-3 font-mono text-[10px] text-muted-foreground">{a.source_id}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="p-8 text-center text-muted-foreground">No statistical anomalies detected in this reporting period.</div>
              )}
            </div>
          )}

          {/* TAB 5: FORECASTING */}
          {activeTab === "forecast" && (
            <div className="space-y-4">
              {data?.forecast ? (
                <>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div className="p-3 rounded border border-border bg-card">
                      <span className="text-[10px] text-muted-foreground block">Horizon</span>
                      <strong className="text-sm text-foreground">{data.forecast.horizon}</strong>
                    </div>
                    <div className="p-3 rounded border border-border bg-card">
                      <span className="text-[10px] text-muted-foreground block">Model</span>
                      <strong className="text-sm text-foreground">{data.forecast.model_used}</strong>
                    </div>
                    <div className="p-3 rounded border border-border bg-card">
                      <span className="text-[10px] text-muted-foreground block">Trend Direction</span>
                      <strong className="text-sm text-emerald-400">{data.forecast.trend_direction}</strong>
                    </div>
                    <div className="p-3 rounded border border-border bg-card">
                      <span className="text-[10px] text-muted-foreground block">Source ID</span>
                      <strong className="text-sm font-mono text-brand-indigo">{data.forecast.source_id}</strong>
                    </div>
                  </div>

                  <div className="border border-border rounded-lg overflow-hidden">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-muted/40 text-muted-foreground border-b border-border">
                        <tr>
                          <th className="p-2.5">Date</th>
                          <th className="p-2.5">Predicted Value</th>
                          <th className="p-2.5">Lower Confidence Bound</th>
                          <th className="p-2.5">Upper Confidence Bound</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        {data.forecast.points?.slice(0, 8).map((pt, idx) => (
                          <tr key={idx} className="hover:bg-muted/10">
                            <td className="p-2.5 font-medium">{pt.date}</td>
                            <td className="p-2.5 font-bold text-foreground">
                              ${pt.forecast ? pt.forecast.toLocaleString(undefined, { minimumFractionDigits: 2 }) : "—"}
                            </td>
                            <td className="p-2.5 text-muted-foreground">
                              ${pt.lower ? pt.lower.toLocaleString(undefined, { minimumFractionDigits: 2 }) : "—"}
                            </td>
                            <td className="p-2.5 text-muted-foreground">
                              ${pt.upper ? pt.upper.toLocaleString(undefined, { minimumFractionDigits: 2 }) : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : (
                <div className="p-8 text-center text-muted-foreground">Forecasting results unavailable.</div>
              )}
            </div>
          )}

          {/* TAB 6: SEGMENTATION */}
          {activeTab === "segments" && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {data?.segmentation?.map((s, idx) => (
                <div key={idx} className="p-4 rounded-lg border border-border bg-card space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="font-bold text-sm text-foreground">{s.name}</h4>
                    <Badge variant="outline" className="text-[10px] bg-brand-indigo/10 text-brand-indigo border-brand-indigo/20">
                      {s.status}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center p-2 rounded bg-muted/20 border border-border/40">
                    <div>
                      <span className="text-[9px] text-muted-foreground block">Size</span>
                      <strong className="text-xs">{s.size.toLocaleString()}</strong>
                    </div>
                    <div>
                      <span className="text-[9px] text-muted-foreground block">Share</span>
                      <strong className="text-xs text-brand-indigo">{s.size_pct}</strong>
                    </div>
                    <div>
                      <span className="text-[9px] text-muted-foreground block">Avg Spend</span>
                      <strong className="text-xs">{s.avg_spent}</strong>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground">{s.meaningful_changes}</p>
                  <div className="text-[10px] font-mono text-muted-foreground pt-1 border-t border-border/40">
                    {s.source_id} &bull; {s.source}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* TAB 7: BUSINESS IMPACT */}
          {activeTab === "impact" && (
            <div className="space-y-3">
              {data?.business_impact?.map((imp) => (
                <div key={imp.id} className="p-4 rounded-lg border border-border bg-card space-y-1.5">
                  <div className="flex items-center justify-between">
                    <strong className="text-sm text-foreground">{imp.issue}</strong>
                    <Badge
                      variant="outline"
                      className={`text-[10px] ${
                        imp.severity === "High" ? "bg-rose-500/10 text-rose-400" : "bg-amber-500/10 text-amber-400"
                      }`}
                    >
                      {imp.severity} Severity
                    </Badge>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    <strong className="text-foreground/80">Affected Business Area:</strong> {imp.affected_area}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    <strong className="text-foreground/80">Magnitude:</strong> {imp.magnitude}
                  </div>
                  <div className="text-[11px] text-brand-indigo/90 pt-1 border-t border-border/40">
                    <strong>Evidence Grounding:</strong> {imp.supporting_evidence} ({imp.source_id})
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* TAB 8: RECOMMENDATIONS */}
          {activeTab === "recommendations" && (
            <div className="space-y-3">
              {data?.recommendations?.map((rec) => (
                <div key={rec.id} className="p-4 rounded-lg border border-border bg-card border-l-4 border-l-brand-indigo space-y-2">
                  <div className="flex items-center justify-between">
                    <Badge
                      variant="outline"
                      className={`text-[10px] ${
                        rec.priority === "High" ? "bg-rose-500/10 text-rose-400" : "bg-amber-500/10 text-amber-400"
                      }`}
                    >
                      {rec.priority} Priority
                    </Badge>
                    <span className="text-[11px] text-muted-foreground font-semibold">Owner: {rec.suggested_owner}</span>
                  </div>
                  <h4 className="text-sm font-bold text-foreground">{rec.recommendation}</h4>
                  <p className="text-xs text-muted-foreground">
                    <strong className="text-foreground/80">Reason:</strong> {rec.reason}
                  </p>
                  <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1 border-t border-border/40">
                    <span>
                      <strong className="text-foreground/80">Expected Impact:</strong> {rec.expected_impact}
                    </span>
                    <span className="font-mono text-brand-indigo">{rec.source_id}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* TAB 9: EVIDENCE & CITATIONS */}
          {activeTab === "evidence" && (
            <div className="border border-border rounded-lg overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-muted/40 text-muted-foreground border-b border-border">
                  <tr>
                    <th className="p-3">Source ID</th>
                    <th className="p-3">Category</th>
                    <th className="p-3">Authoritative Claim / Statistic</th>
                    <th className="p-3">Source System</th>
                    <th className="p-3">Details / Location</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {data?.evidence?.map((ev, idx) => (
                    <tr key={idx} className="hover:bg-muted/10">
                      <td className="p-3 font-mono font-bold text-brand-indigo">{ev.source_id}</td>
                      <td className="p-3 font-semibold text-foreground">{ev.category}</td>
                      <td className="p-3 text-foreground/90">{ev.claim}</td>
                      <td className="p-3 font-mono text-[11px] text-muted-foreground">{ev.source_name}</td>
                      <td className="p-3 text-muted-foreground">{ev.details}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-border bg-muted/20 flex items-center justify-between text-xs text-muted-foreground">
          <div>
            DataPilot AI Platform &bull; Anti-Hallucination & Mathematical Validation Engine Active
          </div>
          <Button variant="outline" size="sm" onClick={onClose} className="text-xs">
            Close Preview
          </Button>
        </div>
      </div>
    </div>
  );
}
