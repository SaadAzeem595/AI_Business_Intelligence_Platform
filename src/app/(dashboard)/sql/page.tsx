"use client";

import React, { useState, useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Badge } from "@/shared/components/ui/badge";
import { BaseTable, type Column } from "@/shared/components/data-display/BaseTable";
import { 
  Database, 
  Play, 
  Code2, 
  Download, 
  Table, 
  Sparkles, 
  FolderKanban, 
  ChevronRight, 
  ChevronDown, 
  History, 
  Eraser, 
  Wand2, 
  ShieldAlert, 
  Search, 
  FileText, 
  Layers, 
  AlertCircle, 
  CheckCircle2, 
  Info, 
  Clock, 
  ArrowRight,
  ShieldCheck
} from "lucide-react";
import { useUIStore } from "@/shared/services/uiStore";
import { useProjects } from "@/features/projects/hooks/useProjects";
import { useDatasets } from "@/features/datasets/hooks/useDatasets";
import { useSQL } from "@/features/analytics/hooks/useForecast";
import { cn } from "@/shared/lib/utils";

interface ColumnMeta {
  name: string;
  type: string;
}

interface TableSchema {
  id?: string;
  name: string;
  rowsCount: number;
  columns?: ColumnMeta[];
}

export default function SQLPlaygroundPage() {
  const { activeProject, setActiveProject } = useUIStore();
  const { projects, isLoading: isLoadingProjects } = useProjects();
  const { datasets, isLoading: isLoadingDatasets } = useDatasets(undefined, activeProject);
  
  // Active selected dataset in the project (or "all")
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>("all");

  // Dynamic SQL Schema & Query Hook
  const { 
    schema, 
    isLoadingSchema, 
    executeSQL, 
    isExecuting, 
    results, 
    isError, 
    error, 
    resetResults 
  } = useSQL(activeProject);

  // Editor & UX state
  const [query, setQuery] = useState<string>("");
  const [expandedTables, setExpandedTables] = useState<Record<string, boolean>>({});
  const [schemaSearch, setSchemaSearch] = useState<string>("");
  const [limitProtection, setLimitProtection] = useState<boolean>(true);
  const [queryHistory, setQueryHistory] = useState<string[]>([]);
  const [showHistoryDropdown, setShowHistoryDropdown] = useState<boolean>(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-select first project if none is active
  useEffect(() => {
    if (!activeProject && projects.length > 0) {
      setActiveProject(projects[0].id);
    }
  }, [activeProject, projects, setActiveProject]);

  // Load project query history from localStorage
  useEffect(() => {
    if (activeProject && typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem(`datapilot_sql_history_${activeProject}`);
        if (saved) {
          setQueryHistory(JSON.parse(saved));
        } else {
          setQueryHistory([]);
        }
      } catch {
        setQueryHistory([]);
      }
    }
  }, [activeProject]);

  // Set default initial query when schema loads or active project / dataset changes
  useEffect(() => {
    if (schema && schema.length > 0) {
      // Automatically expand first table by default
      setExpandedTables((prev) => ({ ...prev, [schema[0].name]: true }));

      // If dataset filter is selected, find target table
      let targetTable = schema[0].name;
      if (selectedDatasetId !== "all") {
        const found = schema.find((t: TableSchema) => t.id === selectedDatasetId || t.name === selectedDatasetId);
        if (found) {
          targetTable = found.name;
        }
      }
      setQuery(`SELECT * FROM ${targetTable} LIMIT 10;`);
    } else {
      setQuery("");
    }
    resetResults();
  }, [schema, selectedDatasetId, activeProject]);

  // Save successful query to history
  const saveToHistory = (executedQuery: string) => {
    const trimmed = executedQuery.trim();
    if (!trimmed || !activeProject) return;
    setQueryHistory((prev) => {
      const filtered = prev.filter((q) => q.trim() !== trimmed);
      const updated = [trimmed, ...filtered].slice(0, 10);
      try {
        localStorage.setItem(`datapilot_sql_history_${activeProject}`, JSON.stringify(updated));
      } catch {}
      return updated;
    });
  };

  // Run Query with LIMIT Protection
  const handleRunQuery = async () => {
    let finalQuery = query.trim();
    if (!finalQuery) return;

    // Apply LIMIT protection if enabled and no LIMIT clause is present
    if (limitProtection && !/\blimit\s+\d+/i.test(finalQuery)) {
      if (finalQuery.endsWith(";")) {
        finalQuery = finalQuery.slice(0, -1).trim() + " LIMIT 100;";
      } else {
        finalQuery = finalQuery + " LIMIT 100;";
      }
      setQuery(finalQuery);
    }

    try {
      await executeSQL(finalQuery);
      saveToHistory(finalQuery);
    } catch {
      // Error handled by Hook boundary
    }
  };

  // Click to insert text at textarea cursor position
  const insertAtCursor = (textToInsert: string) => {
    const textarea = textareaRef.current;
    if (!textarea) {
      setQuery((prev) => (prev ? `${prev} ${textToInsert}` : textToInsert));
      return;
    }

    const startPos = textarea.selectionStart;
    const endPos = textarea.selectionEnd;
    const currentVal = textarea.value;

    const newVal =
      currentVal.substring(0, startPos) +
      textToInsert +
      currentVal.substring(endPos, currentVal.length);

    setQuery(newVal);

    // Set cursor position after inserted text
    setTimeout(() => {
      textarea.focus();
      const newCursorPos = startPos + textToInsert.length;
      textarea.setSelectionRange(newCursorPos, newCursorPos);
    }, 50);
  };

  // Toggle table expansion in schema browser
  const toggleTableExpand = (tableName: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedTables((prev) => ({ ...prev, [tableName]: !prev[tableName] }));
  };

  // Format SQL Query
  const handleFormatSQL = () => {
    if (!query.trim()) return;

    let formatted = query;
    const keywords = [
      "SELECT", "FROM", "WHERE", "ORDER BY", "GROUP BY", "LIMIT", "JOIN",
      "LEFT JOIN", "RIGHT JOIN", "INNER JOIN", "ON", "AND", "OR", "ASC",
      "DESC", "HAVING", "AS", "COUNT", "SUM", "AVG", "MIN", "MAX", "DISTINCT"
    ];

    // Capitalize SQL keywords
    keywords.forEach((kw) => {
      const regex = new RegExp(`\\b${kw}\\b`, "gi");
      formatted = formatted.replace(regex, kw);
    });

    // Add clean line breaks before major clause keywords
    const majorClauses = ["FROM", "WHERE", "GROUP BY", "ORDER BY", "LIMIT", "JOIN", "LEFT JOIN", "RIGHT JOIN", "HAVING"];
    majorClauses.forEach((clause) => {
      const regex = new RegExp(`\\s+(${clause})\\b`, "g");
      formatted = formatted.replace(regex, `\n$1`);
    });

    setQuery(formatted.trim());
  };

  // Clear SQL Editor
  const handleClearSQL = () => {
    setQuery("");
    resetResults();
  };

  // Download Query Results as CSV
  const handleDownloadCSV = () => {
    if (!results || !results.rows || results.rows.length === 0) return;

    const cols = results.columns || Object.keys(results.rows[0]);
    const csvLines: string[] = [];

    // Header row
    csvLines.push(cols.map((c) => `"${c.replace(/"/g, '""')}"`).join(","));

    // Data rows
    results.rows.forEach((row: any) => {
      const line = cols.map((col) => {
        const val = row[col];
        if (val === null || val === undefined) return '""';
        const strVal = typeof val === "object" ? JSON.stringify(val) : String(val);
        return `"${strVal.replace(/"/g, '""')}"`;
      }).join(",");
      csvLines.push(line);
    });

    const csvBlob = new Blob([csvLines.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(csvBlob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `sql_results_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Filter Schema tables & columns by search term
  const filteredSchema: TableSchema[] = (schema || []).filter((table: TableSchema) => {
    if (!schemaSearch.trim()) return true;
    const term = schemaSearch.toLowerCase();
    const matchesTable = table.name.toLowerCase().includes(term);
    const matchesCol = table.columns?.some((c) => c.name.toLowerCase().includes(term));
    return matchesTable || matchesCol;
  });

  // Construct dynamic BaseTable columns from results
  const tableColumns: Column<any>[] = results?.columns
    ? results.columns.map((colName) => ({
        header: colName.toUpperCase().replace(/_/g, " "),
        accessorKey: colName,
        cell: (row: any) => {
          const val = row[colName];
          if (val === null || val === undefined) {
            return <span className="italic text-muted-foreground/40 font-mono text-[11px]">null</span>;
          }
          if (typeof val === "boolean") {
            return (
              <Badge variant={val ? "success" : "secondary"} className="text-[10px] px-1.5 py-0">
                {val ? "TRUE" : "FALSE"}
              </Badge>
            );
          }
          if (typeof val === "object") {
            return <span className="font-mono text-xs text-brand-indigo">{JSON.stringify(val)}</span>;
          }
          return <span className="font-mono text-xs">{String(val)}</span>;
        },
      }))
    : [];

  const activeProjectName = projects.find((p) => p.id === activeProject)?.name || "Select Project";

  return (
    <div className="space-y-6">
      {/* Title Header & Workspace Context Controls */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-border/60 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight">SQL Playground</h1>
            <Badge variant="outline" className="text-xs font-semibold gap-1">
              <FolderKanban className="h-3.5 w-3.5 text-brand-indigo" />
              <span>Project: {activeProjectName}</span>
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Execute direct SQL queries against DuckDB in-memory views mapped to your project datasets.
          </p>
        </div>

        {/* Dynamic Project & Dataset Selectors at TOP-LEFT consistent with Forecasting/Segmentation */}
        <div className="flex flex-wrap items-center gap-3 bg-muted/20 p-2 rounded-lg border border-border/60">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-muted-foreground flex items-center gap-1">
              <FolderKanban className="h-3.5 w-3.5 text-brand-indigo" /> Project:
            </span>
            <select
              value={activeProject || ""}
              onChange={(e) => {
                setActiveProject(e.target.value);
                setSelectedDatasetId("all");
              }}
              className="text-xs p-1.5 rounded-md border border-border/80 bg-background font-semibold text-foreground cursor-pointer outline-none focus:ring-1 focus:ring-brand-indigo min-w-[150px]"
            >
              {isLoadingProjects ? (
                <option>Loading projects...</option>
              ) : projects.length === 0 ? (
                <option value="">No projects available</option>
              ) : (
                projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))
              )}
            </select>
          </div>

          <div className="flex items-center gap-2 border-l border-border/60 pl-3">
            <span className="text-xs font-semibold text-muted-foreground flex items-center gap-1">
              <Layers className="h-3.5 w-3.5 text-brand-indigo" /> Dataset:
            </span>
            <select
              value={selectedDatasetId}
              onChange={(e) => setSelectedDatasetId(e.target.value)}
              className="text-xs p-1.5 rounded-md border border-border/80 bg-background font-semibold text-foreground cursor-pointer outline-none focus:ring-1 focus:ring-brand-indigo min-w-[160px]"
              disabled={!activeProject || isLoadingDatasets}
            >
              <option value="all">All Project Datasets ({datasets.length})</option>
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.display_name || d.filename}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Main SQL Workspace Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Left Panel: Schema Browser */}
        <Card className="border-border/80 lg:col-span-1 h-[calc(100vh-14rem)] flex flex-col overflow-hidden select-none">
          <CardHeader className="pb-3 border-b border-border/40 shrink-0 bg-muted/10">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-bold flex items-center gap-1.5 text-foreground/90">
                <Database className="h-4 w-4 text-brand-indigo" /> Schema Browser
              </CardTitle>
              <Badge variant="secondary" className="text-[10px] px-1.5">
                {filteredSchema.length} {filteredSchema.length === 1 ? "table" : "tables"}
              </Badge>
            </div>
            <CardDescription className="text-[10px] text-muted-foreground">
              DuckDB registered views & column types
            </CardDescription>

            {/* Schema Search Filter Input */}
            <div className="relative mt-2">
              <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Search tables & columns..."
                value={schemaSearch}
                onChange={(e) => setSchemaSearch(e.target.value)}
                className="pl-8 text-xs h-8 bg-background/60"
              />
            </div>
          </CardHeader>

          <CardContent className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar">
            {isLoadingSchema ? (
              <div className="py-8 text-center text-xs text-muted-foreground space-y-2">
                <div className="animate-spin h-5 w-5 border-2 border-brand-indigo border-t-transparent rounded-full mx-auto" />
                <p>Inspecting DuckDB schema...</p>
              </div>
            ) : filteredSchema.length === 0 ? (
              <div className="py-8 text-center text-xs text-muted-foreground space-y-2">
                <AlertCircle className="h-6 w-6 text-muted-foreground mx-auto opacity-50" />
                <p className="font-semibold text-foreground">No tables found</p>
                <p className="text-[11px] text-muted-foreground leading-relaxed px-2">
                  {activeProject
                    ? "Upload a dataset to this project to inspect DuckDB table schemas and execute SQL queries."
                    : "Select a project above to inspect available dataset schemas."}
                </p>
              </div>
            ) : (
              <div className="space-y-1.5">
                {filteredSchema.map((table: TableSchema) => {
                  const isExpanded = !!expandedTables[table.name];
                  return (
                    <div key={table.name} className="rounded-md border border-border/50 bg-background/40 overflow-hidden">
                      {/* Table Header Row */}
                      <div
                        onClick={() => insertAtCursor(`SELECT * FROM ${table.name} LIMIT 10;`)}
                        className="w-full text-left p-2 hover:bg-muted/40 transition-colors flex items-center justify-between cursor-pointer group"
                      >
                        <div className="flex items-center gap-1.5 truncate">
                          <button
                            onClick={(e) => toggleTableExpand(table.name, e)}
                            className="p-0.5 hover:bg-muted rounded text-muted-foreground hover:text-foreground"
                          >
                            {isExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                          </button>
                          <Table className="h-3.5 w-3.5 text-brand-indigo shrink-0" />
                          <span className="font-mono text-xs font-semibold text-foreground group-hover:text-brand-indigo truncate">
                            {table.name}
                          </span>
                        </div>

                        <Badge variant="secondary" className="text-[9px] px-1 py-0 select-none shrink-0">
                          {table.rowsCount.toLocaleString()} r
                        </Badge>
                      </div>

                      {/* Expandable Column List */}
                      {isExpanded && (
                        <div className="border-t border-border/40 bg-muted/20 p-2 space-y-1">
                          {table.columns && table.columns.length > 0 ? (
                            table.columns.map((col) => (
                              <button
                                key={col.name}
                                onClick={() => insertAtCursor(`"${col.name}"`)}
                                className="w-full text-left px-2 py-1 hover:bg-muted/50 rounded flex items-center justify-between text-[11px] text-muted-foreground hover:text-foreground transition-colors group cursor-pointer"
                                title="Click to insert column into SQL editor"
                              >
                                <span className="font-mono truncate group-hover:text-brand-indigo">
                                  {col.name}
                                </span>
                                <span className="font-mono text-[9px] text-muted-foreground/70 uppercase">
                                  {col.type}
                                </span>
                              </button>
                            ))
                          ) : (
                            <p className="text-[10px] text-muted-foreground italic px-2 py-0.5">No columns available</p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Right Panel: SQL Editor & Output Preview */}
        <div className="lg:col-span-3 flex flex-col space-y-4">
          <Card className="border-border/80 flex flex-col overflow-hidden">
            <CardHeader className="flex flex-row items-center justify-between py-2.5 px-4 border-b border-border/40 bg-muted/10 shrink-0">
              <span className="text-xs font-bold text-muted-foreground flex items-center gap-1.5">
                <Code2 className="h-4 w-4 text-brand-indigo" /> SQL Editor Window
              </span>

              {/* Editor Toolbar UX Controls */}
              <div className="flex items-center gap-2 flex-wrap">
                {/* LIMIT Protection Toggle */}
                <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground cursor-pointer select-none border-r border-border/60 pr-2">
                  <input
                    type="checkbox"
                    checked={limitProtection}
                    onChange={(e) => setLimitProtection(e.target.checked)}
                    className="rounded border-border/80 text-brand-indigo focus:ring-0 h-3.5 w-3.5 cursor-pointer"
                  />
                  <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
                  <span>Limit Protection</span>
                </label>

                {/* Format SQL Button */}
                <Button size="sm" variant="outline" className="h-7 text-xs gap-1 px-2" onClick={handleFormatSQL} title="Format SQL keywords & indentation">
                  <Wand2 className="h-3 w-3 text-brand-indigo" /> Format
                </Button>

                {/* Clear Button */}
                <Button size="sm" variant="outline" className="h-7 text-xs gap-1 px-2" onClick={handleClearSQL} title="Clear SQL editor">
                  <Eraser className="h-3 w-3 text-muted-foreground" /> Clear
                </Button>

                {/* Query History Dropdown */}
                {queryHistory.length > 0 && (
                  <div className="relative">
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs gap-1 px-2"
                      onClick={() => setShowHistoryDropdown((prev) => !prev)}
                      title="View session query history"
                    >
                      <History className="h-3 w-3 text-amber-500" /> History ({queryHistory.length})
                    </Button>

                    {showHistoryDropdown && (
                      <div className="absolute right-0 top-8 w-72 bg-popover border border-border/80 rounded-md shadow-xl z-50 p-2 space-y-1">
                        <div className="flex items-center justify-between pb-1 border-b border-border/40 text-[11px] font-bold text-muted-foreground px-1">
                          <span>Recent Queries</span>
                          <button onClick={() => setShowHistoryDropdown(false)} className="text-muted-foreground hover:text-foreground">✕</button>
                        </div>
                        <div className="max-h-48 overflow-y-auto space-y-1 custom-scrollbar">
                          {queryHistory.map((hQuery, idx) => (
                            <button
                              key={idx}
                              onClick={() => {
                                setQuery(hQuery);
                                setShowHistoryDropdown(false);
                              }}
                              className="w-full text-left p-1.5 text-[10px] font-mono hover:bg-muted/50 rounded border border-border/30 truncate text-muted-foreground hover:text-foreground transition-all block"
                            >
                              {hQuery}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Run Query Main Action Button */}
                <Button size="sm" variant="brand" className="h-8 text-xs gap-1.5 px-4 font-semibold" onClick={handleRunQuery} disabled={isExecuting}>
                  <Play className="h-3.5 w-3.5 fill-current" /> {isExecuting ? "Executing..." : "Run Query"}
                </Button>
              </div>
            </CardHeader>

            <CardContent className="p-0">
              <textarea
                ref={textareaRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full h-44 p-4 font-mono text-xs bg-background/60 outline-none text-foreground border-none resize-y focus:ring-0 custom-scrollbar leading-relaxed"
                placeholder="SELECT * FROM table_name LIMIT 10;"
              />
            </CardContent>
          </Card>

          {/* Results Area */}
          <div className="space-y-3 flex-1 flex flex-col min-h-0">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold tracking-tight flex items-center gap-1.5">
                <Table className="h-4 w-4 text-brand-indigo" /> Query Results
              </h2>

              {results && !isError && (
                <div className="flex items-center gap-4 text-[11px] text-muted-foreground">
                  <span>
                    Returned <strong className="text-foreground">{results.rows?.length || 0}</strong> rows in{" "}
                    <span className="font-bold text-foreground">{results.elapsedMs}ms</span>
                  </span>
                  {results.rows && results.rows.length > 0 && (
                    <button
                      onClick={handleDownloadCSV}
                      className="text-brand-indigo font-semibold hover:underline flex items-center gap-1 cursor-pointer"
                    >
                      <Download className="h-3.5 w-3.5" /> Export CSV
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* SQL Execution Error Banner State */}
            {isError && error && (
              <Card className="border-red-500/40 bg-red-500/10 p-4 text-red-600 dark:text-red-400">
                <div className="flex items-start gap-3">
                  <ShieldAlert className="h-5 w-5 shrink-0 text-red-500 mt-0.5" />
                  <div className="space-y-1">
                    <h4 className="text-xs font-bold text-foreground">SQL Execution Error</h4>
                    <p className="font-mono text-[11px] leading-relaxed break-all bg-background/40 p-2.5 rounded border border-red-500/30 text-red-400">
                      {error}
                    </p>
                  </div>
                </div>
              </Card>
            )}

            {/* Main Data Table Result Render */}
            <div className="flex-1 min-h-[240px]">
              {!activeProject ? (
                <Card className="p-12 text-center text-muted-foreground space-y-3">
                  <FolderKanban className="h-8 w-8 text-brand-indigo mx-auto opacity-60" />
                  <h3 className="text-sm font-bold text-foreground">No active project selected</h3>
                  <p className="text-xs max-w-sm mx-auto">
                    Please select a project from the top-left dropdown to inspect its DuckDB tables and execute SQL queries.
                  </p>
                </Card>
              ) : schema && schema.length === 0 ? (
                <Card className="p-12 text-center text-muted-foreground space-y-3">
                  <Layers className="h-8 w-8 text-amber-500 mx-auto opacity-60" />
                  <h3 className="text-sm font-bold text-foreground">No datasets available in this project</h3>
                  <p className="text-xs max-w-sm mx-auto">
                    Active project &quot;{activeProjectName}&quot; currently has no datasets registered in DuckDB. Upload a dataset to begin querying.
                  </p>
                </Card>
              ) : (
                <BaseTable
                  columns={tableColumns}
                  data={results?.rows || []}
                  isLoading={isExecuting}
                  emptyState={
                    !isExecuting && (
                      <div className="flex flex-col items-center justify-center space-y-2 py-8 text-center">
                        <CheckCircle2 className="h-8 w-8 text-muted-foreground/40" />
                        <p className="text-sm font-medium text-foreground">
                          {results ? "Query executed successfully, but returned 0 rows" : "No query executed yet"}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {results
                            ? "Try adjusting your WHERE filters or SELECT statement."
                            : "Click 'Run Query' above or select a table from the Schema Browser to inspect data."}
                        </p>
                      </div>
                    )
                  }
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
