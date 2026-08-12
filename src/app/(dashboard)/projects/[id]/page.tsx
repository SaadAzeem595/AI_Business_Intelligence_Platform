"use client";

import React, { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useProjects } from "@/features/projects/hooks/useProjects";
import { useDatasets } from "@/features/datasets/hooks/useDatasets";
import { useUpload } from "@/features/datasets/hooks/useUpload";
import { useUIStore } from "@/shared/services/uiStore";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";
import { BaseTable, type Column } from "@/shared/components/data-display/BaseTable";
import { cn } from "@/shared/lib/utils";
import { 
  Database, 
  MessageSquareCode, 
  Code2, 
  TrendingUp, 
  ArrowLeft, 
  UploadCloud, 
  File, 
  Trash2, 
  ArrowRight, 
  Table, 
  Sparkles, 
  Send,
  Play,
  Download,
  Folder
} from "lucide-react";
import { Dataset } from "@/shared/types/dataset";
import { useSQL } from "@/features/analytics/hooks/useForecast";
import { useChat } from "@/features/chat/hooks/useChat";

interface Message {
  role: "user" | "assistant";
  content: string;
  chart?: {
    type: "bar" | "line" | "area";
    data: any[];
    xKey: string;
    yKeys: string[];
  };
  table?: {
    columns: Column<any>[];
    data: any[];
  };
}

export default function ProjectWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const [activeTab, setActiveTab] = useState<"database" | "chat" | "sql" | "analytics">("database");

  const { project, isLoading: isLoadingProject } = useProjects(projectId);
  const { datasets, isLoading: isLoadingDatasets, deleteDataset } = useDatasets(undefined, projectId);
  const { upload, isUploading, progress } = useUpload(projectId);
  const { activeProject, setActiveProject, activeOrg } = useUIStore();

  // Set active project context in Zustand store for sub-components/AI Chat compatibility
  useEffect(() => {
    if (projectId) {
      setActiveProject(projectId);
    }
  }, [projectId, setActiveProject]);

  // File Upload Logic
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

  const handleDelete = (dsId: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    deleteDataset(dsId);
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

  // SQL Playground Logic
  const [sqlQuery, setSqlQuery] = useState("");
  const { schema, isLoadingSchema, executeSQL, isExecuting, results } = useSQL();
  const [runStats, setRunStats] = useState<{ elapsed: number; rows: number } | null>(null);

  useEffect(() => {
    if (schema && schema.length > 0 && !sqlQuery) {
      setSqlQuery(`SELECT * FROM ${schema[0].name} LIMIT 5;`);
    }
  }, [schema, sqlQuery]);

  const handleRunSQL = async () => {
    try {
      // Modify execution payload to pass active project_id from context
      const res = await executeSQL(sqlQuery);
      if (res) {
        setRunStats({ elapsed: res.elapsedMs, rows: res.rows.length });
      }
    } catch (err: any) {
      console.error(err);
    }
  };

  // AI Chat Logic
  const { sendMessage } = useChat();
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "Hello! I am your project-scoped AI assistant. I can query datasets associated with this project, generate charts, and run analytics. Ask me anything about your project data!",
    },
  ]);
  const [chatInput, setChatInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const handleSendChatMessage = async () => {
    if (!chatInput.trim()) return;
    const userMsg: Message = { role: "user", content: chatInput };
    setMessages((prev) => [...prev, userMsg]);
    setChatInput("");
    setIsTyping(true);

    try {
      const res = await sendMessage({
        message: chatInput,
        workspace: activeOrg,
        workspaceId: activeOrg,
        activeProject: projectId,
        history: messages.map(m => ({ role: m.role, content: m.content })),
        selectedDatasetIds: datasets.map(d => d.id),
      });

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.content,
          chart: res.chart,
          table: res.table
        }
      ]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Error: ${err.message || "Failed to process chat request."}`
        }
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  if (isLoadingProject) {
    return <div className="text-center py-20 text-xs text-muted-foreground">Loading project workspace...</div>;
  }

  if (!project) {
    return (
      <div className="space-y-4 py-10 max-w-md mx-auto text-center">
        <h2 className="text-lg font-bold">Project Not Found</h2>
        <p className="text-xs text-muted-foreground">This project doesn't exist or you don't have access permissions.</p>
        <Button onClick={() => router.push("/projects")} size="sm">
          <ArrowLeft className="h-4 w-4 mr-1.5" /> Back to Projects
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Workspace Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border/60 pb-5">
        <div className="flex items-center gap-3">
          <Button
            size="icon"
            variant="outline"
            className="h-8 w-8 hover:bg-muted cursor-pointer shrink-0"
            onClick={() => router.push("/projects")}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight">{project.name}</h1>
              <Badge variant="success">Workspace Active</Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">{project.description || "Project-scoped data analysis workspace."}</p>
          </div>
        </div>

        {/* Dynamic Workspace Tabs */}
        <div className="flex border border-border/80 rounded-md overflow-hidden p-0.5 bg-muted/20 w-fit shrink-0">
          {[
            { id: "database", label: "Database/Datasets", icon: Database },
            { id: "chat", label: "AI Chat", icon: MessageSquareCode },
            { id: "sql", label: "SQL Playground", icon: Code2 },
            { id: "analytics", label: "Analytics Dashboard", icon: TrendingUp },
          ].map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={cn(
                  "text-[10px] font-bold px-3 py-1.5 capitalize rounded-md transition-all cursor-pointer flex items-center gap-1.5",
                  activeTab === tab.id
                    ? "bg-card text-foreground shadow-xs"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Tabs Contents */}
      {activeTab === "database" && (
        <div className="space-y-6">
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
                  Drag files here or click to browse. Files up to 50MB will be parsed and registered as isolated DuckDB tables for this project.
                </p>
              </div>
              <div className="w-full max-w-xs space-y-2">
                <Button size="sm" onClick={() => fileInputRef.current?.click()} disabled={isUploading} className="w-full">
                  {isUploading ? `Uploading & parsing (${progress}%)...` : "Select File"}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Scoped Datasets Table */}
          <div className="space-y-3">
            <h2 className="text-sm font-semibold tracking-tight flex items-center gap-1.5">
              <Table className="h-4 w-4 text-brand-indigo" /> Project Connected Datasets ({datasets.length})
            </h2>
            <BaseTable columns={columns as any} data={datasets} isLoading={isLoadingDatasets} />
          </div>
        </div>
      )}

      {activeTab === "chat" && (
        <Card className="border-border/80 h-[calc(100vh-16rem)] flex flex-col justify-between overflow-hidden">
          <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
            {messages.map((msg, index) => (
              <div key={index} className={cn("flex flex-col max-w-[80%] rounded-lg p-3 text-xs leading-relaxed", 
                msg.role === "user" ? "bg-brand-indigo text-brand-indigo-foreground ml-auto" : "bg-muted text-foreground mr-auto"
              )}>
                <span className="font-bold opacity-80 uppercase text-[9px] mb-1">{msg.role}</span>
                <div>{msg.content}</div>
                {msg.table && (
                  <div className="mt-3 overflow-x-auto border border-border/40 rounded-md bg-background/50">
                    <BaseTable columns={msg.table.columns} data={msg.table.data} />
                  </div>
                )}
              </div>
            ))}
            {isTyping && (
              <div className="bg-muted text-foreground mr-auto max-w-[80%] rounded-lg p-3 text-xs flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-foreground/60 animate-bounce" />
                <span className="h-1.5 w-1.5 rounded-full bg-foreground/60 animate-bounce delay-75" />
                <span className="h-1.5 w-1.5 rounded-full bg-foreground/60 animate-bounce delay-150" />
              </div>
            )}
            <div ref={chatBottomRef} />
          </div>
          
          <div className="p-3 border-t border-border/60 bg-muted/10 flex gap-2 shrink-0">
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSendChatMessage()}
              placeholder="Ask questions about this project's datasets..."
              className="flex-1 bg-background text-xs outline-none border border-border/80 rounded-md px-3 py-2 text-foreground focus:border-brand-indigo/60 focus:ring-1 focus:ring-brand-indigo/30 transition-all"
            />
            <Button size="sm" onClick={handleSendChatMessage} disabled={!chatInput.trim()}>
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </Card>
      )}

      {activeTab === "sql" && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Schema Browser */}
          <Card className="border-border/80 lg:col-span-1 h-[calc(100vh-16rem)] flex flex-col overflow-hidden">
            <CardHeader className="pb-3 border-b border-border/40 shrink-0">
              <CardTitle className="text-sm font-bold flex items-center gap-1.5 text-foreground/80">
                <Database className="h-4 w-4 text-brand-indigo" /> Schema Browser
              </CardTitle>
              <CardDescription className="text-[10px]">Project tables in DuckDB.</CardDescription>
            </CardHeader>
            <CardContent className="flex-1 overflow-y-auto p-3 space-y-3 custom-scrollbar">
              <div className="space-y-1.5">
                <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                  <Folder className="h-3.5 w-3.5" /> Project Tables ({schema?.length || 0})
                </span>
                <div className="space-y-1">
                  {schema?.map((table) => (
                    <button
                      key={table.name}
                      onClick={() => setSqlQuery(`SELECT * FROM ${table.name} LIMIT 10;`)}
                      className="w-full text-left p-2 hover:bg-muted/40 rounded-md border border-border/40 hover:border-brand-indigo/35 text-xs text-muted-foreground hover:text-foreground transition-all cursor-pointer truncate flex items-center justify-between"
                    >
                      <span className="font-mono truncate text-[11px]">{table.name}</span>
                      <Badge variant="secondary" className="text-[8px] px-1 py-0 select-none">
                        {table.rowsCount.toLocaleString()} r
                      </Badge>
                    </button>
                  ))}
                  {(!schema || schema.length === 0) && (
                    <div className="text-[10px] text-muted-foreground py-4 text-center">No tables loaded. Upload a CSV.</div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* SQL Editor */}
          <div className="lg:col-span-3 flex flex-col space-y-4">
            <Card className="border-border/80 flex flex-col">
              <CardHeader className="flex flex-row items-center justify-between pb-3 border-b border-border/40 bg-muted/10 shrink-0">
                <span className="text-xs font-bold text-muted-foreground flex items-center gap-1.5">
                  <Code2 className="h-4 w-4 text-brand-indigo" /> SQL Editor Window
                </span>
                <div className="flex items-center gap-2">
                  <Button size="sm" variant="brand" className="h-8 text-xs gap-1.5" onClick={handleRunSQL} disabled={isExecuting}>
                    <Play className="h-3.5 w-3.5 fill-current" /> {isExecuting ? "Executing..." : "Run Query"}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <textarea
                  value={sqlQuery}
                  onChange={(e) => setSqlQuery(e.target.value)}
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
                  </div>
                )}
              </div>

              <div className="flex-1 min-h-[200px] border border-border/40 rounded-lg overflow-hidden bg-card">
                <BaseTable 
                  columns={results?.columns ? results.columns.map(c => ({ header: c.toUpperCase(), accessorKey: c })) : []} 
                  data={results?.rows || []} 
                  isLoading={isExecuting} 
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === "analytics" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card className="p-4 border-border/80">
              <CardHeader className="p-0 pb-2">
                <CardTitle className="text-xs text-muted-foreground font-semibold">Project Datasets</CardTitle>
              </CardHeader>
              <div className="text-2xl font-bold">{datasets.length}</div>
              <p className="text-[10px] text-muted-foreground mt-1">Available in SQL and Chat</p>
            </Card>
            <Card className="p-4 border-border/80">
              <CardHeader className="p-0 pb-2">
                <CardTitle className="text-xs text-muted-foreground font-semibold">Total Records Index</CardTitle>
              </CardHeader>
              <div className="text-2xl font-bold">
                {datasets.reduce((acc, d) => acc + d.rows, 0).toLocaleString()}
              </div>
              <p className="text-[10px] text-emerald-500 font-medium mt-1">✓ DuckDB synchronized</p>
            </Card>
            <Card className="p-4 border-border/80">
              <CardHeader className="p-0 pb-2">
                <CardTitle className="text-xs text-muted-foreground font-semibold">Health Index Mean</CardTitle>
              </CardHeader>
              <div className="text-2xl font-bold">
                {datasets.length > 0 
                  ? `${Math.round(datasets.reduce((acc, d) => acc + d.qualityScore, 0) / datasets.length)}%` 
                  : "N/A"}
              </div>
              <p className="text-[10px] text-muted-foreground mt-1">Dataset quality score</p>
            </Card>
          </div>

          <Card className="border-border/80 p-6">
            <CardHeader className="px-0 pt-0 pb-4">
              <CardTitle className="text-sm font-bold flex items-center gap-1.5 text-brand-indigo">
                <Sparkles className="h-4.5 w-4.5" /> Project Analytics Dashboard
              </CardTitle>
              <CardDescription className="text-xs">Select columns on the datasets tab or ask the AI chat questions to configure predictive models (ARIMA/Prophet).</CardDescription>
            </CardHeader>
            <CardContent className="h-64 flex items-center justify-center border border-dashed border-border rounded-lg bg-muted/5 select-none">
              <div className="text-center space-y-2">
                <Sparkles className="h-8 w-8 text-brand-indigo animate-bounce mx-auto" />
                <p className="text-xs font-semibold">Interactive Forecasting & Segmentations Scoped</p>
                <p className="text-[10px] text-muted-foreground max-w-sm leading-relaxed">Connect datasets in the Database tab, then head over to SQL Playground or AI Chat to trigger automated machine learning modeling.</p>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
