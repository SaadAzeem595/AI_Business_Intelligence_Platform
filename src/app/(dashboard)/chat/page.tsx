"use client";

import React, { useState, useRef, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Card, CardContent } from "@/shared/components/ui/card";
import { BaseChart } from "@/shared/components/data-display/BaseChart";
import { BaseTable, type Column } from "@/shared/components/data-display/BaseTable";
import { Sparkles, Send, RefreshCw, Copy, FileOutput, MessageSquarePlus, Trash2 } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import { useChat } from "@/features/chat/hooks/useChat";
import { useUIStore } from "@/shared/services/uiStore";
import { useDatasets } from "@/features/datasets/hooks/useDatasets";

import { useProjects } from "@/features/projects/hooks/useProjects";
import { FolderGit2, CheckCircle2, AlertCircle, Compass, Database } from "lucide-react";

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

export default function AIChatPage() {
  const searchParams = useSearchParams();
  const initialPrompt = searchParams.get("prompt");
  const datasetIdParam = searchParams.get("datasetId") || searchParams.get("dataset");
  
  const { activeOrg, activeProject, setActiveProject } = useUIStore();
  const { projects } = useProjects();
  const { datasets } = useDatasets(undefined, activeProject || undefined);
  
  const [selectedDatasetId, setSelectedDatasetId] = useState("");
  const [selectedDataset, setSelectedDataset] = useState("");
  const [detectedDataset, setDetectedDataset] = useState<string | null>(null);
  const [detectedDatasetId, setDetectedDatasetId] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<{ id: string; name: string }[]>([]);
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);

  // Auto-select dataset based on query parameter from navigation
  useEffect(() => {
    if (datasetIdParam && datasets.length > 0) {
      const matched = datasets.find((d: any) => 
        d.id === datasetIdParam || 
        d.filename === datasetIdParam || 
        d.display_name === datasetIdParam ||
        d.duckdb_table === datasetIdParam
      );
      if (matched) {
        setSelectedDatasetId(matched.id);
        setSelectedDataset(matched.filename);
        if (matched.project_id && !activeProject) {
          setActiveProject(matched.project_id);
        }
      }
    }
  }, [datasetIdParam, datasets, activeProject, setActiveProject]);

  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "Hello! I am your AI Business Intelligence assistant. I can query active datasets, run forecasting models, and segment your cohorts. What are we analyzing today?",
    },
  ]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of conversation feed
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  // Handle initial prompt from router search query params
  useEffect(() => {
    if (initialPrompt && messages.length === 1) {
      handleSendMessage(initialPrompt);
    }
  }, [initialPrompt]);

  const { sendMessage } = useChat();

  const handleSendMessage = async (text: string, overrideDatasetId?: string, overrideDatasetName?: string) => {
    if (!text.trim()) return;
    
    const userMessage: Message = { role: "user", content: text };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsTyping(true);
    setCandidates([]);

    const activeDatasetId = overrideDatasetId !== undefined ? overrideDatasetId : selectedDatasetId;
    const activeDatasetName = overrideDatasetName !== undefined ? overrideDatasetName : selectedDataset;
    const matched = datasets.find((d: any) => d.id === activeDatasetId || d.filename === activeDatasetName);
    const effectiveProject = activeProject || matched?.project_id || undefined;

    try {
      const response = await sendMessage({
        message: text,
        sessionId: sessionId,
        workspace: activeOrg || "default",
        workspaceId: activeOrg || "default",
        dataset: activeDatasetName || undefined,
        datasetId: activeDatasetId || undefined,
        selectedDatasetIds: activeDatasetId ? [activeDatasetId] : [],
        activeProject: effectiveProject,
        projectId: effectiveProject,
        history: messages.map(m => ({ role: m.role as "user" | "assistant", content: m.content })),
      });
      
      if (response.sessionId) {
        setSessionId(response.sessionId);
      }

      if (response.datasetName) {
        setDetectedDataset(response.datasetName);
        if (response.datasetId) {
          setDetectedDatasetId(response.datasetId);
        }
      }

      if (response.status === "needs_clarification" && response.datasetNames && response.datasetNames.length > 0) {
        setCandidates(
          response.datasetNames.map((name: string, i: number) => ({
            id: response.datasetIds?.[i] || name,
            name: name,
          }))
        );
      }

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: response.content,
          chart: response.chart,
          table: response.table,
        },
      ]);
    } catch (err: any) {
      const errMsg = err?.response?.data?.error || err?.response?.data?.detail || err?.message || "Sorry, I encountered an error analyzing your request.";
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `❌ ${typeof errMsg === "string" ? errMsg : JSON.stringify(errMsg)}`,
        },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleSelectCandidate = (candidate: { id: string; name: string }) => {
    setSelectedDatasetId(candidate.id);
    setSelectedDataset(candidate.name);
    setDetectedDataset(candidate.name);
    setDetectedDatasetId(candidate.id);
    setCandidates([]);
    handleSendMessage(`Analyze ${candidate.name}`, candidate.id, candidate.name);
  };

  const handleClearChat = () => {
    setSessionId(undefined);
    setDetectedDataset(null);
    setDetectedDatasetId(null);
    setCandidates([]);
    setMessages([
      {
        role: "assistant",
        content: "Hello! I am your AI Business Intelligence assistant. I can query active datasets, run forecasting models, and segment your cohorts. What are we analyzing today?",
      },
    ]);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8.5rem)] relative border border-border bg-card rounded-xl overflow-hidden select-none">
      {/* Thread Controls Header */}
      <div className="flex flex-wrap gap-2 min-h-13 w-full items-center justify-between border-b border-border bg-card/85 px-4 py-2 shrink-0">
        <span className="text-xs font-semibold text-foreground/80 flex items-center gap-1.5">
          <Sparkles className="h-4 w-4 text-brand-indigo" /> AI Chat Session
        </span>
        <div className="flex items-center gap-2 flex-wrap">
          {/* Project Selector Dropdown */}
          <div className="flex items-center gap-1">
            <FolderGit2 className="h-3.5 w-3.5 text-muted-foreground" />
            <select
              value={activeProject || ""}
              onChange={(e) => {
                const val = e.target.value;
                setActiveProject(val || null);
                setSelectedDatasetId("");
                setSelectedDataset("");
                setDetectedDataset(null);
              }}
              className="text-xs border border-border rounded-lg bg-card text-foreground px-2.5 py-1.5 outline-none cursor-pointer hover:border-brand-indigo/60 transition-all shadow-sm font-medium focus:ring-1 focus:ring-brand-indigo"
            >
              <option value="">📁 All Projects (Global)</option>
              {projects.map((p: any) => (
                <option key={p.id} value={p.id}>
                  📁 {p.name}
                </option>
              ))}
            </select>
          </div>

          {/* Active Dataset Selector Dropdown */}
          <div className="flex items-center gap-1">
            <Database className="h-3.5 w-3.5 text-muted-foreground" />
            <select
              value={selectedDatasetId}
              onChange={(e) => {
                const val = e.target.value;
                setSelectedDatasetId(val);
                const matched = datasets.find((d: any) => d.id === val);
                setSelectedDataset(matched ? matched.filename : "");
                setDetectedDataset(matched ? matched.filename : null);
                setCandidates([]);
                if (matched?.project_id && matched.project_id !== activeProject) {
                  setActiveProject(matched.project_id);
                }
              }}
              className="text-xs border border-brand-indigo/35 rounded-lg bg-card text-foreground px-3 py-1.5 outline-none cursor-pointer hover:border-brand-indigo/70 transition-all shadow-sm font-medium focus:ring-1 focus:ring-brand-indigo"
            >
              <option value="">🔮 Auto-detect Dataset</option>
              {datasets.map((d: any) => (
                <option key={d.id} value={d.id}>
                  📊 {d.display_name || d.filename} {d.type ? `(${d.type})` : ""}
                </option>
              ))}
            </select>
          </div>

          <Button size="icon" variant="ghost" className="h-8 w-8 hover:bg-muted text-muted-foreground hover:text-foreground" onClick={handleClearChat} title="Clear conversation">
            <Trash2 className="h-4 w-4" />
          </Button>
          <Button size="icon" variant="ghost" className="h-8 w-8 hover:bg-muted text-muted-foreground hover:text-foreground" title="Export logs">
            <FileOutput className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Auto-detect Status Banner */}
      <div className="px-4 py-2 bg-muted/40 border-b border-border/60 text-xs flex items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-2 overflow-hidden text-ellipsis whitespace-nowrap">
          {!selectedDatasetId ? (
            detectedDataset ? (
              <span className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 font-medium">
                <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                <span>Auto-detected: <strong>{detectedDataset}</strong></span>
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-brand-indigo font-medium">
                <Compass className="h-3.5 w-3.5 shrink-0 animate-spin" style={{ animationDuration: '6s' }} />
                <span>Auto-detect ON — Datasets and columns will be resolved dynamically from your query.</span>
              </span>
            )
          ) : (
            <span className="flex items-center gap-1.5 text-foreground/80 font-medium">
              <Database className="h-3.5 w-3.5 text-brand-indigo shrink-0" />
              <span>Manually Scoped: <strong>{selectedDataset || "Selected Dataset"}</strong></span>
            </span>
          )}
        </div>
        
        {selectedDatasetId ? (
          <button
            onClick={() => {
              setSelectedDatasetId("");
              setSelectedDataset("");
              setDetectedDataset(null);
            }}
            className="text-[11px] text-brand-indigo hover:underline shrink-0 font-medium cursor-pointer"
          >
            Switch to Auto-detect
          </button>
        ) : null}
      </div>

      {/* Candidates Clarification Bar (appears if backend requests clarification) */}
      {candidates.length > 0 && (
        <div className="px-4 py-2.5 bg-amber-500/10 border-b border-amber-500/20 text-xs flex items-center gap-2 flex-wrap shrink-0">
          <AlertCircle className="h-4 w-4 text-amber-500 shrink-0" />
          <span className="font-semibold text-amber-600 dark:text-amber-400">Multiple datasets matched your query. Which one did you mean?</span>
          <div className="flex items-center gap-1.5 flex-wrap ml-2">
            {candidates.map((c) => (
              <button
                key={c.id}
                onClick={() => handleSelectCandidate(c)}
                className="px-2.5 py-1 rounded-md bg-amber-500/20 hover:bg-amber-500/30 text-amber-700 dark:text-amber-300 font-medium text-xs transition-colors cursor-pointer"
              >
                📊 {c.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Messages Feed View */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar bg-background/25">
        {messages.map((msg, index) => {
          const isAI = msg.role === "assistant";
          return (
            <div key={index} className={cn("flex gap-3 max-w-[85%] sm:max-w-[75%]", isAI ? "self-start" : "self-end ml-auto flex-row-reverse")}>
              <div
                className={cn(
                  "h-7 w-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0 shadow-sm select-none",
                  isAI ? "bg-brand-indigo text-brand-indigo-foreground" : "bg-primary text-primary-foreground"
                )}
              >
                {isAI ? "AI" : "US"}
              </div>
              <div className="space-y-3">
                <div
                  className={cn(
                    "text-xs p-3.5 rounded-2xl leading-relaxed whitespace-pre-wrap",
                    isAI
                      ? "bg-card border border-border text-foreground rounded-tl-xs"
                      : "bg-brand-indigo text-brand-indigo-foreground rounded-tr-xs"
                  )}
                >
                  {msg.content}
                </div>

                {/* Inline Recharts widget */}
                {isAI && msg.chart && (
                  <Card className="border-border/80 bg-card overflow-hidden">
                    <CardContent className="p-4">
                      <BaseChart type={msg.chart.type} data={msg.chart.data} xKey={msg.chart.xKey} yKeys={msg.chart.yKeys} height={200} />
                    </CardContent>
                  </Card>
                )}

                {/* Inline Tables widget */}
                {isAI && msg.table && (
                  <BaseTable columns={msg.table.columns} data={msg.table.data} className="border-border/80 bg-card" />
                )}
              </div>
            </div>
          );
        })}

        {isTyping && (
          <div className="flex gap-3 max-w-[75%] self-start">
            <div className="h-7 w-7 rounded-full bg-brand-indigo text-brand-indigo-foreground flex items-center justify-center text-xs font-bold shrink-0 animate-pulse">
              AI
            </div>
            <div className="bg-card border border-border text-foreground text-xs p-3.5 rounded-2xl rounded-tl-xs flex items-center gap-2">
              <RefreshCw className="h-3.5 w-3.5 animate-spin text-brand-indigo" />
              <span>Analyzing query and compiling insights...</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Suggested prompts list (displays if conversation is clean/empty) */}
      {messages.length === 1 && (
        <div className="px-4 py-3 bg-card border-t border-border/40 space-y-2">
          <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Suggested prompts</span>
          <div className="flex flex-wrap gap-1.5">
            {[
              "Show monthly sales trends as a bar chart",
              "Cluster customer cohorts details",
              "Scan duplicates inside q3_financials",
            ].map((p, idx) => (
              <button
                key={idx}
                onClick={() => handleSendMessage(p)}
                className="text-xs px-2.5 py-1.5 rounded-full border border-border/80 hover:border-brand-indigo/40 hover:bg-brand-indigo/5 text-muted-foreground hover:text-foreground transition-all cursor-pointer select-none"
              >
                {p}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Message Input Box at bottom */}
      <div className="p-3 border-t border-border bg-card shrink-0">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage(input);
          }}
          className="flex items-center gap-2"
        >
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask AI anything about your datasets (e.g. 'Show sales monthly trends as bar chart')..."
            className="flex-1 border-border/80 focus-visible:ring-brand-indigo"
          />
          <Button type="submit" size="icon" variant="brand" className="h-9 w-9 shrink-0">
            <Send className="h-4 w-4" />
          </Button>
        </form>
      </div>
    </div>
  );
}
