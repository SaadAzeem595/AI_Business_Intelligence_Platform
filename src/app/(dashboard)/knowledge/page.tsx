"use client";

import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Badge } from "@/shared/components/ui/badge";
import { Library, Search, FileText, UploadCloud, FolderClosed, ArrowRight } from "lucide-react";

interface SearchMatch {
  title: string;
  excerpt: string;
  score: number;
  date: string;
}

export default function KnowledgeBasePage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [matches, setMatches] = useState<SearchMatch[]>([]);

  const mockDocs = [
    { name: "invoice_2026_acme.pdf", size: "1.2 MB", added: "2026-08-01" },
    { name: "sales_growth_strategies.docx", size: "840 KB", added: "2026-07-30" },
    { name: "competitor_analysis_report.pdf", size: "4.8 MB", added: "2026-07-25" },
    { name: "customer_support_guide.txt", size: "140 KB", added: "2026-07-18" },
  ];

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    
    setIsSearching(true);
    setTimeout(() => {
      setMatches([
        {
          title: "invoice_2026_acme.pdf",
          excerpt: "...outstanding invoice balance for Acme Corp totals $8,900, due in August 2026. Payment terms are net-30 days...",
          score: 0.94,
          date: "2026-08-01",
        },
        {
          title: "sales_growth_strategies.docx",
          excerpt: "...our customer segmentation indicates that Champions cohort generates 40%+ revenue, whereas At-Risk counts 280 users...",
          score: 0.81,
          date: "2026-07-30",
        },
      ]);
      setIsSearching(false);
    }, 500);
  };

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Knowledge Base</h1>
        <p className="text-xs text-muted-foreground">Upload corporate booklets and search pages using semantic vectors (RAG). Ask questions about unstructured text.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Side: Document Uploader & Folder list */}
        <div className="lg:col-span-1 space-y-6">
          <Card className="border-border/80">
            <CardHeader>
              <CardTitle className="text-sm font-bold flex items-center gap-1.5">
                <UploadCloud className="h-4.5 w-4.5 text-brand-indigo" /> Upload Documents
              </CardTitle>
              <CardDescription className="text-[10px]">Add text documents to vector index.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="border border-dashed border-border/80 hover:bg-muted/10 transition-colors p-6 rounded-lg text-center cursor-pointer select-none">
                <FileText className="h-6 w-6 text-muted-foreground mx-auto mb-2" />
                <span className="text-xs font-semibold text-foreground/80 block">Select PDF or Word File</span>
                <span className="text-[10px] text-muted-foreground/60 block mt-0.5">Maximum size: 20MB</span>
              </div>
            </CardContent>
          </Card>

          {/* Library Folders */}
          <Card className="border-border/80">
            <CardHeader className="pb-3 border-b border-border/40">
              <CardTitle className="text-sm font-bold flex items-center gap-1.5 text-foreground/80">
                <Library className="h-4 w-4 text-brand-indigo" /> Document Directories
              </CardTitle>
            </CardHeader>
            <CardContent className="p-3 space-y-1">
              {mockDocs.map((doc, idx) => (
                <div key={idx} className="flex items-center justify-between p-2 hover:bg-muted/40 rounded-md border border-border/40 text-xs transition-colors">
                  <div className="flex items-center gap-2 truncate">
                    <FileText className="h-3.5 w-3.5 text-brand-indigo shrink-0" />
                    <span className="font-medium text-foreground/80 truncate">{doc.name}</span>
                  </div>
                  <span className="text-[10px] text-muted-foreground shrink-0">{doc.size}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        {/* Right Side: Document Search Interface */}
        <div className="lg:col-span-2 space-y-6">
          <Card className="border-border/80 bg-card">
            <CardContent className="p-6">
              <form onSubmit={handleSearch} className="space-y-4">
                <span className="text-xs font-bold text-foreground/80 block">Semantic Vector Search</span>
                <div className="flex items-center gap-2">
                  <Input
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Enter query (e.g. 'Show outstanding Acme balances')..."
                    className="border-border/80 focus-visible:ring-brand-indigo"
                  />
                  <Button type="submit" size="sm" variant="brand" className="h-9 shrink-0 gap-1.5" disabled={isSearching}>
                    <Search className="h-4 w-4" /> {isSearching ? "Searching..." : "Search"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          {/* Search results */}
          {searchQuery && (
            <div className="space-y-3">
              <h2 className="text-sm font-semibold tracking-tight">Search Results Match ({matches.length})</h2>
              {isSearching ? (
                <div className="space-y-4">
                  {Array.from({ length: 2 }).map((_, i) => (
                    <Card key={i} className="border-border/80 animate-pulse">
                      <CardContent className="p-4 space-y-2">
                        <div className="h-4 w-1/4 bg-muted rounded" />
                        <div className="h-3 w-3/4 bg-muted rounded" />
                        <div className="h-3 w-1/2 bg-muted rounded" />
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ) : matches.length === 0 ? (
                <div className="p-8 text-center text-xs text-muted-foreground border border-dashed border-border/80 rounded-lg">
                  No direct semantic hits found. Try re-phrasing your search query.
                </div>
              ) : (
                <div className="space-y-3">
                  {matches.map((match, idx) => (
                    <Card key={idx} className="border-border/80 hover:border-brand-indigo/35 transition-all">
                      <CardHeader className="p-4 pb-1.5 flex flex-row items-center justify-between">
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-brand-indigo" />
                          <CardTitle className="text-xs font-bold text-foreground">{match.title}</CardTitle>
                        </div>
                        <Badge variant="outline" className="text-[10px] text-emerald-500 border-emerald-500/30 bg-emerald-500/5">
                          Match: {Math.round(match.score * 100)}%
                        </Badge>
                      </CardHeader>
                      <CardContent className="p-4 pt-1.5 text-xs text-muted-foreground space-y-2">
                        <p className="leading-relaxed whitespace-pre-wrap">{match.excerpt}</p>
                        <div className="text-[10px] text-muted-foreground/60 pt-2 border-t border-border/40">
                          Indexed on: {match.date}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
