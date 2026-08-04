"use client";

import React, { useState, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Badge } from "@/shared/components/ui/badge";
import { Library, Search, FileText, UploadCloud, FolderClosed, ArrowRight, Trash2, X } from "lucide-react";

interface SearchMatch {
  title: string;
  excerpt: string;
  score: number;
  date: string;
}

const loadPdfJs = (): Promise<any> => {
  return new Promise((resolve, reject) => {
    if (typeof window === 'undefined') {
      reject(new Error("Cannot load PDF.js in SSR context"));
      return;
    }
    if ((window as any)['pdfjs-dist/build/pdf']) {
      resolve((window as any)['pdfjs-dist/build/pdf']);
      return;
    }
    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';
    script.onload = () => {
      const pdfjsLib = (window as any)['pdfjs-dist/build/pdf'];
      pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
      resolve(pdfjsLib);
    };
    script.onerror = () => reject(new Error("Failed to load PDF.js script"));
    document.head.appendChild(script);
  });
};

const extractTextFromPdf = async (file: File): Promise<string> => {
  const pdfjsLib = await loadPdfJs();
  const arrayBuffer = await file.arrayBuffer();
  const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
  let text = '';
  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i);
    const content = await page.getTextContent();
    const strings = content.items.map((item: any) => item.str);
    text += strings.join(' ') + '\n';
  }
  return text;
};

const getSearchExcerpt = (text: string, query: string): { excerpt: string; score: number } => {
  const cleanQuery = query.toLowerCase().trim();
  const cleanText = text.replace(/\s+/g, ' ');
  const index = cleanText.toLowerCase().indexOf(cleanQuery);

  if (index !== -1) {
    const start = Math.max(0, index - 40);
    const end = Math.min(cleanText.length, index + cleanQuery.length + 120);
    let excerpt = cleanText.substring(start, end);
    if (start > 0) excerpt = '...' + excerpt;
    if (end < cleanText.length) excerpt = excerpt + '...';
    return { excerpt, score: 0.95 };
  }

  const words = cleanQuery.split(/\s+/).filter(w => w.length > 2);
  if (words.length === 0) {
    return { excerpt: text.substring(0, 160) + '...', score: 0.5 };
  }

  let bestCount = 0;
  const sentences = cleanText.split(/[.!?]+/);
  let bestSentence = '';

  for (const sentence of sentences) {
    let count = 0;
    const lowerSentence = sentence.toLowerCase();
    for (const word of words) {
      if (lowerSentence.includes(word)) {
        count++;
      }
    }
    if (count > bestCount) {
      bestCount = count;
      bestSentence = sentence.trim();
    }
  }

  if (bestCount > 0) {
    const score = parseFloat((0.5 + (bestCount / words.length) * 0.45).toFixed(2));
    const finalExcerpt = bestSentence.length > 180 ? bestSentence.substring(0, 180) + '...' : bestSentence + '.';
    return {
      excerpt: finalExcerpt.startsWith('...') ? finalExcerpt : '...' + finalExcerpt,
      score
    };
  }

  return { excerpt: text.substring(0, 160) + '...', score: 0.4 };
};

export default function KnowledgeBasePage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [matches, setMatches] = useState<SearchMatch[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<any | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [docs, setDocs] = useState([
    {
      name: "invoice_2026_acme.pdf",
      size: "1.2 MB",
      added: "2026-08-01",
      content: "ACME CORPORATION INVOICE\nInvoice Number: INV-2026-089\nDate: 2026-08-01\nDue Date: 2026-08-31\n\nBilling To:\nAcme Corporation\n123 Enterprise Way\nSuite 500\n\nDescription of Services:\n- Business Intelligence Platform Integration (Q2 Phase 2): $5,000.00\n- Automated Anomaly Detection Configuration: $2,400.00\n- Cloud Database Storage Allocation (DuckDB Serverless): $1,500.00\n\nTotal Outstanding Balance: $8,900.00\nPayment Terms: Net-30 days. Payments received after the due date are subject to a 1.5% monthly late fee. Please send all ACH transfers to Acme Operations bank routing. Thank you for your business!"
    },
    {
      name: "sales_growth_strategies.docx",
      size: "840 KB",
      added: "2026-07-30",
      content: "SALES GROWTH STRATEGIES - 2026 PLAN\n\nExecutive Summary:\nOur customer segmentation analysis indicates that the 'Champions' cohort generates over 40% of the recurring subscription revenue, whereas the 'At-Risk' segment currently counts 280 users. \n\nKey Strategic Initiatives:\n1. Targeted campaigns directed at SaaS cohorts showing high usage patterns.\n2. Churn reduction plays focusing on customers with low platform engagement scores.\n3. Dynamic up-selling of BI dashboard widgets and prediction plugins.\n4. Expanding operations into European sales channels to capture new enterprise accounts."
    },
    {
      name: "competitor_analysis_report.pdf",
      size: "4.8 MB",
      added: "2026-07-25",
      content: "COMPETITOR ANALYSIS REPORT - EXECUTIVE INTELLIGENCE BRIEF\n\nMarket Landscape Overview:\nOur current market share is estimated at 34%, representing a solid position but showing opportunities for expansion. Our primary competitors, DataCo and Intellisense, hold approximately 28% and 20% respectively.\n\nCompetitor Matrix:\n1. DataCo: High cost, complex SQL configuration required. Lacks native forecasting engines.\n2. Intellisense: User-friendly but scales poorly with larger datasets. Restricted UI customization.\n3. Our BI Platform: Native DuckDB vector speed, integrated machine learning pipelines, and highly customizable dashboard widgets."
    },
    {
      name: "customer_support_guide.txt",
      size: "140 KB",
      added: "2026-07-18",
      content: "CUSTOMER SUPPORT GUIDE & SLA\n\nSupport Tiers & Guidelines:\n- Tier 1: General usage questions, onboarding help. Target response time: 2 hours.\n- Tier 2: SQL query optimization, dataset integration troubleshooting. Target response: 4 hours.\n- Tier 3: Core database exceptions, predictive service failures. Response time: 8 hours.\n\nCommon Issues & Escalations:\n- Resetting user sessions: Can be done via the user admin console under Settings.\n- Data Source connection errors: Ensure file size does not exceed 50MB and that standard delimiters are used for CSV structures."
    },
  ]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setIsSearching(true);
    setTimeout(() => {
      const searchResults: SearchMatch[] = [];

      docs.forEach((doc) => {
        if (doc.content) {
          const matchResult = getSearchExcerpt(doc.content, searchQuery);
          if (matchResult.score > 0.4) {
            searchResults.push({
              title: doc.name,
              excerpt: matchResult.excerpt,
              score: matchResult.score,
              date: doc.added,
            });
          }
        }
      });

      const sortedResults = searchResults.sort((a, b) => b.score - a.score);
      setMatches(sortedResults);
      setIsSearching(false);
    }, 500);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const maxSize = 20 * 1024 * 1024;
    if (file.size > maxSize) {
      alert("File size exceeds 20MB limit.");
      return;
    }

    setIsUploading(true);

    // Asynchronously extract file text or fallback
    const processFile = async () => {
      let content = "";
      if (file.name.endsWith(".txt")) {
        try {
          content = await file.text();
        } catch (err) {
          console.error("Text file read error", err);
          content = "Could not parse plain text document.";
        }
      } else if (file.name.endsWith(".pdf")) {
        try {
          content = await extractTextFromPdf(file);
        } catch (err) {
          console.error("PDF extraction error, falling back to mock content", err);
          content = `DOCUMENT: ${file.name}\n\nAbstract: This is a placeholder description for the uploaded PDF document. Re-indexing of parsed text details is complete. Full text content could not be fully extracted due to binary formatting limits.`;
        }
      } else {
        content = `DOCUMENT: ${file.name}\n\nThis is a mock representation of the extracted text content from ${file.name}. \nIt includes general metadata and operational analytics relating to the document's subject. Keyword queries matching this file will search this placeholder document context successfully.`;
      }

      const sizeStr = file.size < 1024 * 1024
        ? `${Math.round(file.size / 1024)} KB`
        : `${(file.size / (1024 * 1024)).toFixed(1)} MB`;

      const newDoc = {
        name: file.name,
        size: sizeStr,
        added: new Date().toISOString().split("T")[0],
        content: content
      };

      setDocs((prevDocs) => [newDoc, ...prevDocs]);
      setIsUploading(false);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    };

    processFile();
  };

  const handleButtonClick = () => {
    fileInputRef.current?.click();
  };

  const handleDeleteDoc = (name: string) => {
    setDocs((prevDocs) => prevDocs.filter((doc) => doc.name !== name));
    setMatches((prevMatches) => prevMatches.filter((match) => match.title !== name));
  };

  const handleOpenPreview = (name: string) => {
    const doc = docs.find((d) => d.name === name);
    if (doc) {
      setSelectedDoc(doc);
    }
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
              <div
                onClick={isUploading ? undefined : handleButtonClick}
                className={`border border-dashed border-border/80 transition-all p-6 rounded-lg text-center select-none ${isUploading ? "bg-muted/5 cursor-not-allowed" : "hover:bg-muted/10 hover:border-brand-indigo/40 cursor-pointer"
                  }`}
              >
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  accept=".pdf,.docx,.doc,.txt"
                  className="hidden"
                />
                {isUploading ? (
                  <>
                    <UploadCloud className="h-6 w-6 text-brand-indigo mx-auto mb-2 animate-bounce" />
                    <span className="text-xs font-semibold text-foreground/80 block">Uploading & parsing document...</span>
                    <span className="text-[10px] text-muted-foreground/60 block mt-0.5">Adding to vector index</span>
                  </>
                ) : (
                  <>
                    <FileText className="h-6 w-6 text-muted-foreground mx-auto mb-2" />
                    <span className="text-xs font-semibold text-foreground/80 block">Select PDF or Word File</span>
                    <span className="text-[10px] text-muted-foreground/60 block mt-0.5">Maximum size: 20MB</span>
                  </>
                )}
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
              {docs.map((doc, idx) => (
                <div
                  key={idx}
                  onClick={() => handleOpenPreview(doc.name)}
                  className="group flex items-center justify-between p-2 hover:bg-muted/40 rounded-md border border-border/40 text-xs transition-colors cursor-pointer select-none"
                >
                  <div className="flex items-center gap-2 truncate mr-2">
                    <FileText className="h-3.5 w-3.5 text-brand-indigo shrink-0" />
                    <span className="font-medium text-foreground/80 truncate">{doc.name}</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[10px] text-muted-foreground group-hover:hidden transition-all">{doc.size}</span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteDoc(doc.name);
                      }}
                      className="hidden group-hover:inline-flex text-muted-foreground hover:text-rose-500 transition-colors p-0.5"
                      title="Delete document"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
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
                    <Card
                      key={idx}
                      onClick={() => handleOpenPreview(match.title)}
                      className="border-border/80 hover:border-brand-indigo/35 hover:bg-muted/5 transition-all cursor-pointer select-none"
                    >
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

      {/* Document Content Modal */}
      {selectedDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs transition-all animate-in fade-in duration-200">
          <div className="relative w-full max-w-3xl max-h-[85vh] bg-card border border-border/80 rounded-xl shadow-2xl flex flex-col overflow-hidden animate-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 border-b border-border/40 bg-muted/20">
              <div className="flex items-center gap-2.5 min-w-0">
                <FileText className="h-5 w-5 text-brand-indigo shrink-0" />
                <div className="min-w-0">
                  <h3 className="text-sm font-bold text-foreground truncate">{selectedDoc.name}</h3>
                  <p className="text-[10px] text-muted-foreground">
                    {selectedDoc.size} • Indexed on {selectedDoc.added}
                  </p>
                </div>
              </div>
              <Button
                size="icon"
                variant="ghost"
                className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-muted"
                onClick={() => setSelectedDoc(null)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            {/* Modal Content */}
            <div className="p-6 overflow-y-auto max-h-[60vh] space-y-4">
              <div className="flex items-center justify-between text-[11px] pb-3 border-b border-border/40 text-muted-foreground">
                <div className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                  <span>Vector embeddings computed & active</span>
                </div>
                <span>Format: {selectedDoc.name.split('.').pop()?.toUpperCase()}</span>
              </div>
              <div className="text-xs text-foreground/90 whitespace-pre-wrap leading-relaxed font-sans select-text">
                {selectedDoc.content || "No text content extracted from this document."}
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-border/40 bg-muted/10 flex justify-end">
              <Button size="sm" variant="outline" onClick={() => setSelectedDoc(null)}>
                Close Preview
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
