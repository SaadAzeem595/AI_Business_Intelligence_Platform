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
  
  const { activeOrg, activeProject } = useUIStore();
  const { datasets } = useDatasets();
  const [selectedDatasetId, setSelectedDatasetId] = useState("");
  const [selectedDataset, setSelectedDataset] = useState("");
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);

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

  const handleSendMessage = async (text: string) => {
    if (!text.trim()) return;
    
    const userMessage: Message = { role: "user", content: text };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsTyping(true);

    try {
      const response = await sendMessage({
        message: text,
        sessionId: sessionId,
        workspace: activeOrg,
        dataset: selectedDataset || undefined,
        activeProject: activeProject,
        history: messages.map(m => ({ role: m.role as "user" | "assistant", content: m.content })),
      });
      
      if (response.sessionId) {
        setSessionId(response.sessionId);
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
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, I encountered an error analyzing your request. Check your connections.",
        },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleClearChat = () => {
    setSessionId(undefined);
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
      <div className="flex h-13 w-full items-center justify-between border-b border-border bg-card/85 px-4 shrink-0">
        <span className="text-xs font-semibold text-foreground/80 flex items-center gap-1.5">
          <Sparkles className="h-4 w-4 text-brand-indigo" /> AI Chat Session
        </span>
        <div className="flex items-center gap-1.5">
          {/* Active Dataset Selector Dropdown */}
          <select
            value={selectedDatasetId}
            onChange={(e) => {
              const val = e.target.value;
              setSelectedDatasetId(val);
              const matched = datasets.find((d: any) => d.id === val);
              setSelectedDataset(matched ? matched.filename : "");
            }}
            className="text-xs border border-border/80 rounded bg-card text-foreground px-2 py-1 outline-none cursor-pointer hover:border-brand-indigo/40 mr-2"
          >
            <option value="">Auto-detect Dataset</option>
            {datasets.map((d: any) => (
              <option key={d.id} value={d.id}>
                {d.filename}
              </option>
            ))}
          </select>

          <Button size="icon" variant="ghost" className="h-8 w-8 hover:bg-muted text-muted-foreground hover:text-foreground" onClick={handleClearChat} title="Clear conversation">
            <Trash2 className="h-4 w-4" />
          </Button>
          <Button size="icon" variant="ghost" className="h-8 w-8 hover:bg-muted text-muted-foreground hover:text-foreground" title="Export logs">
            <FileOutput className="h-4 w-4" />
          </Button>
        </div>
      </div>

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
