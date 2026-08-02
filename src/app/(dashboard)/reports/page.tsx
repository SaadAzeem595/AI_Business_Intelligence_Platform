"use client";

import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";
import { BaseTable, type Column } from "@/shared/components/data-display/BaseTable";
import { FileText, Calendar, Mail, FilePlus, Sparkles, Download, Trash2, Clock } from "lucide-react";

interface Report {
  id: string;
  title: string;
  type: "PDF" | "PowerPoint" | "CSV";
  frequency: "Daily" | "Weekly" | "Ad-hoc";
  created: string;
  size: string;
  recipient: string;
}

import { useReports } from "@/features/reports/hooks/useReports";

export default function ReportsPage() {
  const { reports, isLoading, generateReport, isGenerating, deleteReport } = useReports();
  const [scheduleOpt, setScheduleOpt] = useState("Weekly");

  const columns: Column<Report>[] = [
    {
      header: "Report Title",
      accessorKey: "title",
      cell: (row) => (
        <div className="flex items-center gap-2 font-semibold text-foreground">
          <FileText className="h-4 w-4 text-brand-indigo shrink-0" />
          <span>{row.title}</span>
        </div>
      ),
    },
    {
      header: "Format",
      accessorKey: "type",
      cell: (row) => <Badge variant="outline">{row.type}</Badge>,
    },
    {
      header: "Schedule",
      accessorKey: "frequency",
      cell: (row) => (
        <div className="flex items-center gap-1 text-[11px] font-medium">
          <Clock className="h-3 w-3 text-muted-foreground" />
          <span>{row.frequency}</span>
        </div>
      ),
    },
    { header: "Recipient", accessorKey: "recipient" },
    { header: "Size", accessorKey: "size" },
    { header: "Compiled On", accessorKey: "created" },
    {
      header: "Actions",
      accessorKey: "actions",
      align: "right",
      cell: (row) => (
        <div className="flex items-center justify-end gap-1.5">
          <Button size="icon" variant="ghost" className="h-8 w-8 hover:bg-muted text-muted-foreground hover:text-foreground">
            <Download className="h-4 w-4" />
          </Button>
          <Button size="icon" variant="ghost" className="h-8 w-8 hover:bg-rose-500/10 text-muted-foreground hover:text-rose-500" onClick={() => deleteReport(row.id)}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ),
    },
  ];

  const handleCreateReport = async () => {
    const isWeekly = scheduleOpt.includes("Weekly");
    const isDaily = scheduleOpt.includes("Daily");
    const freq = isWeekly ? "Weekly" : isDaily ? "Daily" : "Ad-hoc";

    await generateReport({
      title: "Executive Summaries Analytics Compilation",
      type: "PDF",
      frequency: freq,
      recipient: "saad@example.com",
    });
  };

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Executive Summaries & Reports</h1>
        <p className="text-xs text-muted-foreground">Compile tabular graphs into PDF brochures or slides, and schedule regular dashboard emails.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Side: Report compiler wizard */}
        <div className="lg:col-span-1 space-y-6">
          <Card className="border-border/80">
            <CardHeader>
              <CardTitle className="text-sm font-bold flex items-center gap-1.5 text-foreground/80">
                <Sparkles className="h-4.5 w-4.5 text-brand-indigo animate-pulse" /> AI Report Compiler
              </CardTitle>
              <CardDescription className="text-[10px]">Stitch widgets layout into exports.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[11px] font-semibold text-muted-foreground">Target Recipient Email</label>
                <input
                  type="email"
                  defaultValue="board@acme.com"
                  className="text-xs p-2 rounded-md border border-border/80 bg-background w-full text-foreground/80"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[11px] font-semibold text-muted-foreground">Compilation Frequency</label>
                <select
                  value={scheduleOpt}
                  onChange={(e) => setScheduleOpt(e.target.value)}
                  className="text-xs p-2 rounded-md border border-border/80 bg-background w-full text-foreground/80 cursor-pointer"
                >
                  <option>Ad-hoc (Single compile)</option>
                  <option>Daily at 8:00 AM</option>
                  <option>Weekly (Mondays)</option>
                </select>
              </div>

              <Button onClick={handleCreateReport} disabled={isGenerating} className="w-full mt-4" variant="brand" size="sm">
                {isGenerating ? "Compiling report panels..." : "Compile & Email Report"}
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Right Side: Compiled archives table list */}
        <div className="lg:col-span-2 space-y-3">
          <h2 className="text-sm font-semibold tracking-tight flex items-center gap-1.5">
            <FileText className="h-4 w-4 text-brand-indigo" /> Reports Log Archive
          </h2>
          <BaseTable columns={columns as any} data={reports} isLoading={isLoading} />
        </div>
      </div>
    </div>
  );
}
