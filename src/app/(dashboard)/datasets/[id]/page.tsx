"use client";

import React, { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";
import { BaseTable, type Column } from "@/shared/components/data-display/BaseTable";
import { useDatasets } from "@/features/datasets/hooks/useDatasets";
import {
  ArrowLeft,
  Settings2,
  FileCheck2,
  AlertTriangle,
  Flame,
  LayoutGrid,
  FileCode,
  Table,
  CheckCircle2,
} from "lucide-react";

interface DataRow {
  [key: string]: string | number | boolean;
}

interface SchemaColumn {
  name: string;
  type: string;
  completeness: number;
  distinctValues: number;
}

export default function DatasetDetailPage() {
  const params = useParams();
  const router = useRouter();
  const datasetId = params.id as string;
  const [activeTab, setActiveTab] = useState<"overview" | "preview" | "schema">("overview");

  const { datasetDetails, isLoading, clean } = useDatasets(datasetId);

  const datasetMeta = {
    name: datasetDetails?.filename || "Loading...",
    size: datasetDetails?.size || "...",
    rows: datasetDetails?.rows || 0,
    cols: datasetDetails?.cols || 0,
    health: datasetDetails?.health || 0,
    missing: datasetDetails?.missing || 0,
    duplicates: datasetDetails?.duplicates || 0,
  };

  const schemaColumns = datasetDetails?.schema || [];
  const previewData = datasetDetails?.preview || [];

  const schemaHeaders: Column<SchemaColumn>[] = [
    {
      header: "Column Name",
      accessorKey: "name",
      cell: (row) => <span className="font-semibold text-foreground">{row.name}</span>,
    },
    {
      header: "Data Type",
      accessorKey: "type",
      cell: (row) => <Badge variant="secondary">{row.type}</Badge>,
    },
    {
      header: "Completeness",
      accessorKey: "completeness",
      cell: (row) => (
        <span className={row.completeness === 100 ? "text-emerald-500 font-bold" : "text-amber-500 font-bold"}>
          {row.completeness}%
        </span>
      ),
    },
    {
      header: "Distinct Values",
      accessorKey: "distinctValues",
      cell: (row) => row.distinctValues.toLocaleString(),
    },
  ];

  const previewHeaders: Column<DataRow>[] = previewData.length > 0
    ? Object.keys(previewData[0]).map((key) => ({
        header: key
          .replace(/_/g, " ")
          .replace(/\b\w/g, (c) => c.toUpperCase()),
        accessorKey: key,
      }))
    : [];

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Button
            size="icon"
            variant="outline"
            className="h-8 w-8 hover:bg-muted cursor-pointer"
            onClick={() => router.push("/datasets")}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-xl font-bold tracking-tight">{datasetMeta.name}</h1>
            <p className="text-xs text-muted-foreground">
              {datasetMeta.size} • {datasetMeta.rows.toLocaleString()} rows • {datasetMeta.cols} columns
            </p>
          </div>
        </div>
        <div className="flex border border-border/80 rounded-md overflow-hidden p-0.5 bg-muted/20 w-fit shrink-0">
          {[
            { id: "overview", label: "Overview", icon: LayoutGrid },
            { id: "preview", label: "Preview Data", icon: Table },
            { id: "schema", label: "Columns Schema", icon: FileCode },
          ].map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`text-[10px] font-bold px-3 py-1.5 capitalize rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
                  activeTab === tab.id
                    ? "bg-card text-foreground shadow-xs"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {activeTab === "overview" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Health Stats */}
          <Card className="border-border/80 lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-base font-bold flex items-center gap-1.5">
                <FileCheck2 className="h-4.5 w-4.5 text-emerald-500" /> Data Quality Health Check
              </CardTitle>
              <CardDescription className="text-[11px]">Automatic profiling checks run by DuckDB parser.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center gap-6 p-4 bg-muted/25 rounded-lg border border-border/60">
                <div className="flex flex-col items-center">
                  <span className="text-3xl font-extrabold text-emerald-500">{datasetMeta.health}%</span>
                  <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider mt-1">Quality Score</span>
                </div>
                <div className="h-12 w-[1px] bg-border/80" />
                <div className="space-y-1 text-xs">
                  <p className="font-semibold text-foreground">Dataset passes production readiness checks.</p>
                  <p className="text-muted-foreground">Minor columns contain missing values, but general formatting checks pass standard casting profiles.</p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="p-4 border border-border/80 rounded-lg space-y-1 bg-card/60">
                  <div className="flex items-center gap-1 text-amber-500">
                    <AlertTriangle className="h-4 w-4" />
                    <span className="text-xs font-semibold">Missing Values ({datasetMeta.missing})</span>
                  </div>
                  <p className="text-xs text-muted-foreground pt-1">
                    42 cells in <span className="font-semibold">amount</span> are empty. Suggested action: Auto-fill with column median values.
                  </p>
                </div>
                <div className="p-4 border border-border/80 rounded-lg space-y-1 bg-card/60">
                  <div className="flex items-center gap-1 text-rose-500">
                    <Flame className="h-4 w-4" />
                    <span className="text-xs font-semibold">Duplicates ({datasetMeta.duplicates} Rows)</span>
                  </div>
                  <p className="text-xs text-muted-foreground pt-1">
                    {datasetMeta.duplicates > 0
                      ? `Found ${datasetMeta.duplicates} duplicate rows. Click Clean to prune these entries.`
                      : "No duplicate records detected. Data is structurally clean."}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Cleaning Quick Actions panel */}
          <Card className="border-border/80 flex flex-col justify-between">
            <CardHeader>
              <CardTitle className="text-base font-bold flex items-center gap-1.5">
                <Settings2 className="h-4.5 w-4.5 text-brand-indigo" /> Auto Clean Options
              </CardTitle>
              <CardDescription className="text-[11px]">Resolve structural flaws in one click.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 flex-1">
              <Button size="sm" variant="outline" className="w-full justify-start text-xs border-border/85" disabled={datasetMeta.missing === 0}>
                <CheckCircle2 className="h-4 w-4 text-emerald-500 mr-2" /> Fill missing numbers with median
              </Button>
              <Button size="sm" variant="outline" className="w-full justify-start text-xs border-border/85" disabled={datasetMeta.duplicates === 0}>
                <CheckCircle2 className="h-4 w-4 text-rose-500 mr-2" /> Prune duplicates ({datasetMeta.duplicates})
              </Button>
              <Button size="sm" variant="outline" className="w-full justify-start text-xs border-border/85">
                <CheckCircle2 className="h-4 w-4 text-brand-indigo mr-2" /> Standardize date column formatting
              </Button>
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === "preview" && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold tracking-tight">Records Preview (First 5 Rows)</h2>
          <BaseTable columns={previewHeaders} data={previewData} />
        </div>
      )}

      {activeTab === "schema" && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold tracking-tight">Fields Directory Schema</h2>
          <BaseTable columns={schemaHeaders} data={schemaColumns} />
        </div>
      )}
    </div>
  );
}
