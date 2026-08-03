"use client";

import React, { useState, useRef } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";
import { BaseTable, type Column } from "@/shared/components/data-display/BaseTable";
import { UploadCloud, File, Trash2, ArrowRight, Table } from "lucide-react";
import { cn } from "@/shared/lib/utils";

import { useDatasets } from "@/features/datasets/hooks/useDatasets";
import { useUpload } from "@/features/datasets/hooks/useUpload";
import { Dataset } from "@/shared/types/dataset";

export default function DatasetsPage() {
  const { datasets, isLoading, deleteDataset } = useDatasets();
  const { upload, isUploading, progress } = useUpload();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragActive, setIsDragActive] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const cleanTableName = file.name
        .replace(/\.[^/.]+$/, "")
        .replace(/[^a-zA-Z0-9]/g, "_")
        .toLowerCase();
      upload({ file, tableName: cleanTableName });
    }
  };

  const handleButtonClick = () => {
    fileInputRef.current?.click();
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragActive(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragActive(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragActive(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      const cleanTableName = file.name
        .replace(/\.[^/.]+$/, "")
        .replace(/[^a-zA-Z0-9]/g, "_")
        .toLowerCase();
      upload({ file, tableName: cleanTableName });
    }
  };

  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    deleteDataset(id);
  };

  const columns: Column<Dataset>[] = [
    {
      header: "File Name",
      accessorKey: "filename",
      cell: (row) => (
        <div className="flex items-center gap-2 font-semibold text-foreground">
          <File className="h-4 w-4 text-brand-indigo shrink-0" />
          <span>{row.filename}</span>
        </div>
      ),
    },
    {
      header: "Format",
      accessorKey: "type",
      cell: (row) => <Badge variant="outline">{row.type}</Badge>,
    },
    { header: "Size", accessorKey: "size" },
    {
      header: "Rows count",
      accessorKey: "rows",
      cell: (row) => (row.rows > 0 ? row.rows.toLocaleString() : "N/A"),
    },
    {
      header: "Health Score",
      accessorKey: "qualityScore",
      cell: (row) => {
        if (row.qualityScore === 0) return <span className="text-muted-foreground">-</span>;
        return (
          <span
            className={
              row.qualityScore >= 90
                ? "text-emerald-500 font-bold"
                : row.qualityScore >= 80
                ? "text-amber-500 font-bold"
                : "text-rose-500 font-bold"
            }
          >
            {row.qualityScore}%
          </span>
        );
      },
    },
    {
      header: "Status",
      accessorKey: "status",
      cell: (row) => {
        const variants: Record<Dataset["status"], "success" | "warning" | "destructive"> = {
          Active: "success",
          Processing: "warning",
          Failed: "destructive",
        };
        return <Badge variant={variants[row.status]}>{row.status}</Badge>;
      },
    },
    {
      header: "Actions",
      accessorKey: "actions",
      align: "right",
      cell: (row) => (
        <div className="flex items-center justify-end gap-1">
          <Link href={`/datasets/${row.id}`}>
            <Button size="icon" variant="ghost" className="h-8 w-8 hover:bg-muted text-muted-foreground hover:text-foreground">
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 hover:bg-rose-500/10 text-muted-foreground hover:text-rose-500"
            onClick={(e) => handleDelete(row.id, e)}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Data Sources</h1>
        <p className="text-xs text-muted-foreground">Upload and manage datasets. DuckDB analyzes and indexes uploaded sheets automatically.</p>
      </div>

      {/* Drag & Drop Upload Zone */}
      <Card 
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={cn(
          "border-dashed border-border/80 bg-card hover:bg-muted/10 transition-colors select-none",
          isDragActive && "border-brand-indigo bg-brand-indigo/5"
        )}
      >
        <CardContent className="flex flex-col items-center justify-center p-10 space-y-4 text-center">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept=".csv,.xlsx,.xls,.pdf,.json"
            className="hidden"
          />
          <div className="p-4 bg-brand-indigo/10 rounded-full text-brand-indigo">
            <UploadCloud className="h-8 w-8 animate-pulse" />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-semibold tracking-tight text-foreground">Upload CSV, Excel sheets, or PDFs</h3>
            <p className="text-xs text-muted-foreground max-w-sm leading-relaxed">
              Drag your document files here, or click to browse. Files up to 50MB are supported. Unstructured PDFs are transcribed via semantic parsers.
            </p>
          </div>
          <Button size="sm" onClick={handleButtonClick} disabled={isUploading}>
            {isUploading ? "Uploading & parsing..." : "Select File"}
          </Button>
        </CardContent>
      </Card>

      {/* Datasets Table */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold tracking-tight flex items-center gap-1.5">
          <Table className="h-4 w-4 text-brand-indigo" /> Uploaded Datasets ({datasets?.length || 0})
        </h2>
        <BaseTable columns={columns as any} data={datasets} isLoading={isLoading} />
      </div>
    </div>
  );
}
