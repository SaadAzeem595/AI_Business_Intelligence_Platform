"use client";

import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Badge } from "@/shared/components/ui/badge";
import { BaseTable, type Column } from "@/shared/components/data-display/BaseTable";
import { Database, Play, Code2, Download, Table, Sparkles, Folder } from "lucide-react";
import { useSQL } from "@/features/analytics/hooks/useForecast";

interface DatabaseTableSchema {
  name: string;
  rowsCount: number;
}

export default function SQLPlaygroundPage() {
  const [query, setQuery] = useState(
    "SELECT * FROM customer_churn WHERE region = 'North' ORDER BY amount DESC LIMIT 5;"
  );

  const { schema, isLoadingSchema, executeSQL, isExecuting, results } = useSQL();

  const handleRunQuery = async () => {
    try {
      await executeSQL(query);
    } catch {
      // Error is caught by mutation boundary
    }
  };

  const columns: Column<any>[] = results?.columns
    ? results.columns.map((colName) => ({
        header: colName.toUpperCase().replace(/_/g, " "),
        accessorKey: colName,
      }))
    : [
        { header: "ID", accessorKey: "id" },
        { header: "Customer Name", accessorKey: "customer_name" },
        { header: "Region", accessorKey: "region" },
        { header: "Amount", accessorKey: "amount" },
        { header: "Status", accessorKey: "status" },
      ];

  const resultsData = results?.rows || [];
  const runStats = results
    ? { elapsed: results.elapsedMs, rows: results.rows.length }
    : null;

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">SQL Playground</h1>
        <p className="text-xs text-muted-foreground">Run direct SQL queries using the DuckDB in-memory engine. Query uploaded datasets directly.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Left Side: Schema Browser */}
        <Card className="border-border/80 lg:col-span-1 h-[calc(100vh-14rem)] flex flex-col overflow-hidden">
          <CardHeader className="pb-3 border-b border-border/40 shrink-0">
            <CardTitle className="text-sm font-bold flex items-center gap-1.5 text-foreground/80">
              <Database className="h-4 w-4 text-brand-indigo" /> Schema Browser
            </CardTitle>
            <CardDescription className="text-[10px]">Tables inside DuckDB.</CardDescription>
          </CardHeader>
          <CardContent className="flex-1 overflow-y-auto p-3 space-y-3 custom-scrollbar">
            <div className="space-y-1.5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                <Folder className="h-3.5 w-3.5" /> Tables ({schema?.length || 0})
              </span>
              <div className="space-y-1">
                {schema?.map((table) => (
                  <button
                    key={table.name}
                    onClick={() => setQuery(`SELECT * FROM ${table.name} LIMIT 10;`)}
                    className="w-full text-left p-2 hover:bg-muted/40 rounded-md border border-border/40 hover:border-brand-indigo/35 text-xs text-muted-foreground hover:text-foreground transition-all cursor-pointer truncate flex items-center justify-between"
                  >
                    <span className="font-mono truncate">{table.name}</span>
                    <Badge variant="secondary" className="text-[9px] px-1 py-0 select-none">
                      {table.rowsCount.toLocaleString()} r
                    </Badge>
                  </button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Right Side: SQL Editor & Output Preview */}
        <div className="lg:col-span-3 flex flex-col space-y-4">
          <Card className="border-border/80 flex flex-col">
            <CardHeader className="flex flex-row items-center justify-between pb-3 border-b border-border/40 bg-muted/10 shrink-0">
              <span className="text-xs font-bold text-muted-foreground flex items-center gap-1.5">
                <Code2 className="h-4 w-4 text-brand-indigo" /> SQL Editor Window
              </span>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="brand" className="h-8 text-xs gap-1.5" onClick={handleRunQuery} disabled={isExecuting}>
                  <Play className="h-3.5 w-3.5 fill-current" /> {isExecuting ? "Executing..." : "Run Query"}
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full h-48 p-4 font-mono text-xs bg-background/50 outline-none text-foreground border-none resize-none focus:ring-0 custom-scrollbar leading-relaxed"
                placeholder="SELECT * FROM table LIMIT 10;"
              />
            </CardContent>
          </Card>

          {/* Results Area */}
          <div className="space-y-3 flex-1 flex flex-col min-h-0">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold tracking-tight flex items-center gap-1.5">
                <Table className="h-4 w-4 text-brand-indigo" /> Query Results
              </h2>
              {runStats && (
                <div className="flex items-center gap-4 text-[11px] text-muted-foreground">
                  <span>Returned {runStats.rows} rows in <span className="font-bold text-foreground">{runStats.elapsed}ms</span></span>
                  <button className="text-brand-indigo font-semibold hover:underline flex items-center gap-1 cursor-pointer">
                    <Download className="h-3.5 w-3.5" /> CSV
                  </button>
                </div>
              )}
            </div>

            <div className="flex-1 min-h-[200px]">
              <BaseTable columns={columns} data={resultsData} isLoading={isExecuting} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
