"use client";

import React, { useState, useEffect, useRef } from "react";
import { useUIStore } from "@/shared/services/uiStore";
import { useProjects } from "@/features/projects/hooks/useProjects";
import {
  useRAGDocuments,
  useRAGIngest,
  useRAGDelete,
  useRAGReindex,
  useRAGSearch,
} from "@/features/rag/hooks/useRAG";
import { RAGDocument, ContextResponse } from "@/features/rag/services/rag.service";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Badge } from "@/shared/components/ui/badge";
import {
  Library,
  Search,
  FileText,
  UploadCloud,
  FolderClosed,
  ArrowRight,
  Trash2,
  X,
  RefreshCw,
  Eye,
  SlidersHorizontal,
  Layers,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  FileCode,
  FileSpreadsheet,
  FileIcon,
  ChevronLeft,
  ChevronRight,
  Filter,
  Info,
  Database,
  Tag,
  Calculator,
  Table,
} from "lucide-react";

const ALLOWED_EXTENSIONS = [
  "pdf",
  "docx",
  "doc",
  "txt",
  "csv",
  "xlsx",
  "xls",
  "pptx",
  "html",
  "htm",
  "json",
  "md",
  "markdown",
];

const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024; // 50MB

const formatFileSize = (bytes: number): string => {
  if (!bytes || bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
};

const getFormatBadge = (docType: string) => {
  const t = (docType || "TXT").toUpperCase();
  switch (t) {
    case "PDF":
      return { label: "PDF", bg: "bg-rose-500/10 text-rose-400 border-rose-500/20" };
    case "DOCX":
    case "DOC":
      return { label: "Word", bg: "bg-blue-500/10 text-blue-400 border-blue-500/20" };
    case "CSV":
    case "XLSX":
    case "XLS":
      return { label: "Excel/CSV", bg: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" };
    case "PPTX":
      return { label: "PPTX", bg: "bg-amber-500/10 text-amber-400 border-amber-500/20" };
    case "HTML":
    case "HTM":
      return { label: "HTML", bg: "bg-orange-500/10 text-orange-400 border-orange-500/20" };
    case "JSON":
      return { label: "JSON", bg: "bg-purple-500/10 text-purple-400 border-purple-500/20" };
    case "MD":
    case "MARKDOWN":
      return { label: "Markdown", bg: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20" };
    default:
      return { label: t, bg: "bg-muted text-muted-foreground border-border/40" };
  }
};

const getFormatIcon = (docType: string) => {
  const t = (docType || "").toUpperCase();
  if (t === "PDF" || t === "DOCX" || t === "DOC") return <FileText className="h-4 w-4 text-brand-indigo" />;
  if (t === "CSV" || t === "XLSX" || t === "XLS") return <FileSpreadsheet className="h-4 w-4 text-emerald-400" />;
  if (t === "JSON" || t === "HTML" || t === "MD") return <FileCode className="h-4 w-4 text-cyan-400" />;
  return <FileIcon className="h-4 w-4 text-brand-indigo" />;
};

export default function KnowledgeBasePage() {
  const { activeProject, setActiveProject } = useUIStore();
  const { projects, isLoading: isLoadingProjects } = useProjects();

  // Auto-select first project if none is selected
  useEffect(() => {
    if (!activeProject && projects.length > 0) {
      setActiveProject(projects[0].id);
    }
  }, [activeProject, projects, setActiveProject]);

  // Project RAG Queries & Mutations
  const {
    data: rawDocuments = [],
    isLoading: isLoadingDocs,
    isError: isDocsError,
    refetch: refetchDocs,
  } = useRAGDocuments(activeProject);

  const ingestMutation = useRAGIngest(activeProject);
  const deleteMutation = useRAGDelete(activeProject);
  const reindexMutation = useRAGReindex(activeProject);
  const searchMutation = useRAGSearch(activeProject);

  // Local UI States
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<ContextResponse | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [hybridAlpha, setHybridAlpha] = useState<number>(0.5);
  const [searchLimit, setSearchLimit] = useState<number>(5);

  const [docFilter, setDocFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("ALL");
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 6;

  const [selectedDocMetadata, setSelectedDocMetadata] = useState<RAGDocument | null>(null);
  const [deleteConfirmDoc, setDeleteConfirmDoc] = useState<RAGDocument | null>(null);
  const [reindexingDocId, setReindexingDocId] = useState<string | null>(null);

  // Upload States & Drag and Drop
  const [isDragging, setIsDragging] = useState(false);
  const [uploadStep, setUploadStep] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Clear search results and page state when switching projects
  useEffect(() => {
    setSearchResults(null);
    setHasSearched(false);
    setSearchQuery("");
    setCurrentPage(1);
    setSelectedDocMetadata(null);
    setUploadError(null);
    setUploadSuccess(null);
  }, [activeProject]);

  const activeProjectObj = projects.find((p) => p.id === activeProject);

  // File Ingestion Logic
  const handleProcessFile = async (file: File) => {
    setUploadError(null);
    setUploadSuccess(null);

    const ext = file.name.split(".").pop()?.toLowerCase() || "";
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setUploadError(
        `Unsupported file type ".${ext}". Supported types: PDF, DOCX, TXT, CSV, XLSX, PPTX, HTML, JSON, MD.`
      );
      return;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      setUploadError(`File size exceeds 50MB maximum limit (${formatFileSize(file.size)}).`);
      return;
    }

    try {
      setUploadStep("1/4 Uploading document payload...");
      await new Promise((res) => setTimeout(res, 200));

      setUploadStep("2/4 Extracting text & parsing headings...");
      await new Promise((res) => setTimeout(res, 300));

      setUploadStep("3/4 Generating semantic embeddings...");
      const res = await ingestMutation.mutateAsync({
        file,
        author: "Analyst",
      });

      setUploadStep("4/4 Indexing in DuckDB Vector Store...");
      await new Promise((res) => setTimeout(res, 200));

      setUploadStep(null);
      setUploadSuccess(`Successfully indexed "${file.name}" into RAG workspace (${res.chunks_count} chunks).`);
    } catch (err: any) {
      setUploadStep(null);
      setUploadError(err.message || "Failed to ingest document into RAG index.");
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleProcessFile(file);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleProcessFile(file);
  };

  // Search Logic
  const handleSearchSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim() || !activeProject) return;

    try {
      setHasSearched(true);
      const result = await searchMutation.mutateAsync({
        query: searchQuery.trim(),
        limit: searchLimit,
        hybridAlpha: hybridAlpha,
      });
      setSearchResults(result);
    } catch (err: any) {
      console.error("Vector search failed:", err);
    }
  };

  // Document Re-indexing
  const handleReindex = async (doc: RAGDocument) => {
    try {
      setReindexingDocId(doc.doc_id);
      await reindexMutation.mutateAsync(doc.doc_id);
      setUploadSuccess(`Successfully re-indexed document "${doc.filename}".`);
    } catch (err: any) {
      setUploadError(`Failed to re-index document: ${err.message}`);
    } finally {
      setReindexingDocId(null);
    }
  };

  // Document Deletion
  const handleDeleteConfirm = async () => {
    if (!deleteConfirmDoc) return;
    try {
      await deleteMutation.mutateAsync(deleteConfirmDoc.doc_id);
      setUploadSuccess(`Deleted document "${deleteConfirmDoc.filename}" from project RAG index.`);
      setDeleteConfirmDoc(null);
    } catch (err: any) {
      setUploadError(`Failed to delete document: ${err.message}`);
    }
  };

  // Filtered & Paginated Documents
  const filteredDocs = rawDocuments.filter((doc) => {
    const matchesName = doc.filename.toLowerCase().includes(docFilter.toLowerCase());
    const matchesType = typeFilter === "ALL" || (doc.document_type || "").toUpperCase() === typeFilter;
    return matchesName && matchesType;
  });

  const totalPages = Math.ceil(filteredDocs.length / itemsPerPage) || 1;
  const paginatedDocs = filteredDocs.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);

  const documentTypesList = Array.from(
    new Set(rawDocuments.map((d) => (d.document_type || "TXT").toUpperCase()))
  );

  return (
    <div className="space-y-6 pb-12">
      {/* Header & Project Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border/40 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-brand-indigo/10 text-brand-indigo border border-brand-indigo/20">
              <Library className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">RAG Knowledge Workspace</h1>
              <p className="text-xs text-muted-foreground">
                Enterprise document ingestion, vector index management, and hybrid semantic search.
              </p>
            </div>
          </div>
        </div>

        {/* Project Selector Control */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-card border border-border/80 rounded-lg px-3 py-1.5 shadow-xs">
            <FolderClosed className="h-4 w-4 text-brand-indigo shrink-0" />
            <div className="flex flex-col">
              <span className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">
                Active Project Scope
              </span>
              {isLoadingProjects ? (
                <span className="text-xs text-muted-foreground animate-pulse">Loading projects...</span>
              ) : (
                <select
                  value={activeProject}
                  onChange={(e) => setActiveProject(e.target.value)}
                  className="bg-transparent text-xs font-semibold text-foreground focus:outline-hidden cursor-pointer"
                >
                  {projects.length === 0 ? (
                    <option value="">No projects available</option>
                  ) : (
                    projects.map((p) => (
                      <option key={p.id} value={p.id} className="bg-card text-foreground">
                        {p.name}
                      </option>
                    ))
                  )}
                </select>
              )}
            </div>
          </div>

          <Badge variant="outline" className="text-xs py-1.5 px-3 border-brand-indigo/30 bg-brand-indigo/5 text-brand-indigo hidden md:inline-flex items-center gap-1.5">
            <Database className="h-3.5 w-3.5" />
            <span>{rawDocuments.length} Indexed Docs</span>
          </Badge>
        </div>
      </div>

      {/* Global Status Banners */}
      {uploadError && (
        <div className="p-3.5 rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-400 text-xs flex items-center justify-between animate-in fade-in">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{uploadError}</span>
          </div>
          <button onClick={() => setUploadError(null)} className="hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {uploadSuccess && (
        <div className="p-3.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 text-xs flex items-center justify-between animate-in fade-in">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            <span>{uploadSuccess}</span>
          </div>
          <button onClick={() => setUploadSuccess(null)} className="hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {!activeProject ? (
        <Card className="border-border/80 p-12 text-center">
          <FolderClosed className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <h3 className="text-base font-bold">No Active Project Selected</h3>
          <p className="text-xs text-muted-foreground mt-1">
            Please select a project from the top-left dropdown to access its isolated RAG workspace.
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Drag & Drop Ingestion + Document Management Table (7 cols) */}
          <div className="lg:col-span-7 space-y-6">
            {/* Drag & Drop Ingestion Zone */}
            <Card className="border-border/80 bg-card/60 backdrop-blur-xs">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-bold flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <UploadCloud className="h-4 w-4 text-brand-indigo" />
                    Document Ingestion Pipeline
                  </span>
                  <span className="text-[10px] text-muted-foreground font-normal">
                    Project: <span className="text-foreground font-medium">{activeProjectObj?.name || activeProject}</span>
                  </span>
                </CardTitle>
                <CardDescription className="text-xs">
                  Upload PDF, Word, Excel, CSV, PPTX, HTML, JSON, or Markdown documents to build the project vector index.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() => !uploadStep && fileInputRef.current?.click()}
                  className={`border-2 border-dashed rounded-xl p-6 text-center transition-all select-none ${
                    uploadStep
                      ? "border-brand-indigo/60 bg-brand-indigo/5 cursor-wait"
                      : isDragging
                      ? "border-brand-indigo bg-brand-indigo/10 scale-[0.99]"
                      : "border-border/80 hover:border-brand-indigo/50 hover:bg-muted/10 cursor-pointer"
                  }`}
                >
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileChange}
                    accept=".pdf,.docx,.doc,.txt,.csv,.xlsx,.xls,.pptx,.html,.htm,.json,.md,.markdown"
                    className="hidden"
                  />

                  {uploadStep ? (
                    <div className="space-y-3 py-2">
                      <RefreshCw className="h-8 w-8 text-brand-indigo animate-spin mx-auto" />
                      <div>
                        <span className="text-xs font-semibold text-foreground block">{uploadStep}</span>
                        <span className="text-[10px] text-muted-foreground block mt-1">
                          Processing, chunking, and embedding vectors into DuckDB
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <div className="p-3 rounded-full bg-brand-indigo/10 text-brand-indigo w-fit mx-auto">
                        <UploadCloud className="h-6 w-6" />
                      </div>
                      <div>
                        <span className="text-xs font-semibold text-foreground block">
                          Drag & drop document here, or click to browse
                        </span>
                        <span className="text-[10px] text-muted-foreground block mt-0.5">
                          Supported formats: PDF, DOCX, TXT, CSV, XLSX, PPTX, HTML, JSON, MD (Max 50MB)
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Document Management Table */}
            <Card className="border-border/80 bg-card">
              <CardHeader className="pb-3 border-b border-border/40">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <CardTitle className="text-sm font-bold flex items-center gap-2">
                      <FolderClosed className="h-4 w-4 text-brand-indigo" />
                      Indexed Project Documents ({filteredDocs.length})
                    </CardTitle>
                    <CardDescription className="text-[11px]">
                      Manage active vector embeddings and metadata records for this project workspace.
                    </CardDescription>
                  </div>

                  {/* Filter Controls */}
                  <div className="flex items-center gap-2">
                    <Input
                      value={docFilter}
                      onChange={(e) => {
                        setDocFilter(e.target.value);
                        setCurrentPage(1);
                      }}
                      placeholder="Search docs..."
                      className="h-8 w-36 text-xs border-border/80"
                    />
                    {documentTypesList.length > 0 && (
                      <select
                        value={typeFilter}
                        onChange={(e) => {
                          setTypeFilter(e.target.value);
                          setCurrentPage(1);
                        }}
                        className="h-8 text-xs bg-card border border-border/80 rounded-md px-2 text-foreground"
                      >
                        <option value="ALL">All Types</option>
                        {documentTypesList.map((t) => (
                          <option key={t} value={t}>
                            {t}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                </div>
              </CardHeader>

              <CardContent className="p-0">
                {isLoadingDocs ? (
                  <div className="p-8 space-y-3">
                    {Array.from({ length: 3 }).map((_, i) => (
                      <div key={i} className="h-12 bg-muted/20 animate-pulse rounded-lg" />
                    ))}
                  </div>
                ) : isDocsError ? (
                  <div className="p-8 text-center text-xs text-rose-400">
                    Failed to fetch documents for project scope.
                    <Button variant="ghost" size="sm" onClick={() => refetchDocs()} className="ml-2">
                      Retry
                    </Button>
                  </div>
                ) : paginatedDocs.length === 0 ? (
                  <div className="p-12 text-center text-xs text-muted-foreground space-y-2">
                    <FileText className="h-8 w-8 mx-auto text-muted-foreground/50 mb-2" />
                    <p className="font-medium text-foreground/80">No documents indexed in this project yet.</p>
                    <p className="text-[11px]">
                      {docFilter || typeFilter !== "ALL"
                        ? "No documents match the current filter criteria."
                        : "Upload a document above to begin building the project RAG vector store."}
                    </p>
                  </div>
                ) : (
                  <div className="divide-y divide-border/40">
                    {paginatedDocs.map((doc) => {
                      const badgeInfo = getFormatBadge(doc.document_type);
                      const isReindexing = reindexingDocId === doc.doc_id;

                      return (
                        <div
                          key={doc.doc_id}
                          className="p-3.5 hover:bg-muted/20 transition-colors flex items-center justify-between gap-3 text-xs"
                        >
                          <div className="flex items-center gap-3 min-w-0">
                            <div className="p-2 rounded-lg bg-muted/40 shrink-0">
                              {getFormatIcon(doc.document_type)}
                            </div>
                            <div className="min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="font-semibold text-foreground truncate">{doc.filename}</span>
                                <Badge variant="outline" className={`text-[9px] px-1.5 py-0 ${badgeInfo.bg}`}>
                                  {badgeInfo.label}
                                </Badge>
                              </div>
                              <div className="flex items-center gap-3 text-[10px] text-muted-foreground mt-0.5">
                                <span>{formatFileSize(doc.file_size)}</span>
                                <span>•</span>
                                <span>{doc.chunks_count} chunks</span>
                                <span>•</span>
                                <span>{doc.upload_date}</span>
                              </div>
                            </div>
                          </div>

                          <div className="flex items-center gap-2 shrink-0">
                            <Badge
                              variant="outline"
                              className="text-[9px] px-1.5 py-0.5 text-emerald-400 border-emerald-500/30 bg-emerald-500/10 flex items-center gap-1"
                            >
                              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                              Indexed
                            </Badge>

                            {/* Actions */}
                            <div className="flex items-center gap-1">
                              <Button
                                size="icon"
                                variant="ghost"
                                className="h-7 w-7 text-muted-foreground hover:text-foreground"
                                title="View document metadata & details"
                                onClick={() => setSelectedDocMetadata(doc)}
                              >
                                <Eye className="h-3.5 w-3.5" />
                              </Button>

                              <Button
                                size="icon"
                                variant="ghost"
                                className="h-7 w-7 text-muted-foreground hover:text-brand-indigo"
                                title="Re-index document vectors"
                                disabled={isReindexing}
                                onClick={() => handleReindex(doc)}
                              >
                                <RefreshCw className={`h-3.5 w-3.5 ${isReindexing ? "animate-spin text-brand-indigo" : ""}`} />
                              </Button>

                              <Button
                                size="icon"
                                variant="ghost"
                                className="h-7 w-7 text-muted-foreground hover:text-rose-400"
                                title="Delete document"
                                onClick={() => setDeleteConfirmDoc(doc)}
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </Button>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Pagination Footer */}
                {totalPages > 1 && (
                  <div className="p-3 border-t border-border/40 flex items-center justify-between text-xs text-muted-foreground">
                    <span>
                      Page {currentPage} of {totalPages} ({filteredDocs.length} total docs)
                    </span>
                    <div className="flex items-center gap-1">
                      <Button
                        size="icon"
                        variant="outline"
                        className="h-7 w-7"
                        disabled={currentPage === 1}
                        onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                      >
                        <ChevronLeft className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        size="icon"
                        variant="outline"
                        className="h-7 w-7"
                        disabled={currentPage === totalPages}
                        onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                      >
                        <ChevronRight className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Right Column: Semantic Vector Search Workspace (5 cols) */}
          <div className="lg:col-span-5 space-y-6">
            <Card className="border-border/80 bg-card">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-bold flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-brand-indigo" />
                  Semantic Search & Retrieval Engine
                </CardTitle>
                <CardDescription className="text-[11px]">
                  Query vector embeddings using hybrid RRF search across indexed project documents.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <form onSubmit={handleSearchSubmit} className="space-y-3">
                  <div className="relative">
                    <Input
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Ask a question or enter query..."
                      className="pr-10 border-border/80 focus-visible:ring-brand-indigo text-xs"
                    />
                    <Button
                      type="submit"
                      size="icon"
                      variant="brand"
                      className="absolute right-1 top-1 h-7 w-7"
                      disabled={searchMutation.isPending || !searchQuery.trim()}
                    >
                      {searchMutation.isPending ? (
                        <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Search className="h-3.5 w-3.5" />
                      )}
                    </Button>
                  </div>

                  {/* Search Options (Hybrid Alpha & Limit) */}
                  <div className="p-3 rounded-lg bg-muted/20 border border-border/40 space-y-2.5 text-xs">
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="font-semibold text-foreground/80 flex items-center gap-1.5">
                        <SlidersHorizontal className="h-3 w-3 text-brand-indigo" /> Search Mode:
                      </span>
                      <span className="text-brand-indigo font-medium">
                        {hybridAlpha === 0 ? "Keyword Only" : hybridAlpha === 1 ? "Dense Vector Only" : `Hybrid (Alpha: ${hybridAlpha})`}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-muted-foreground">BM25 Keyword</span>
                      <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.25"
                        value={hybridAlpha}
                        onChange={(e) => setHybridAlpha(parseFloat(e.target.value))}
                        className="flex-1 accent-brand-indigo cursor-pointer h-1.5 bg-muted rounded-lg"
                      />
                      <span className="text-[10px] text-muted-foreground">Vector Dense</span>
                    </div>

                    <div className="flex items-center justify-between text-[10px] text-muted-foreground pt-1 border-t border-border/30">
                      <span>Max Results Limit:</span>
                      <div className="flex items-center gap-1">
                        {[3, 5, 10].map((lim) => (
                          <button
                            key={lim}
                            type="button"
                            onClick={() => setSearchLimit(lim)}
                            className={`px-2 py-0.5 rounded text-[10px] transition-colors ${
                              searchLimit === lim
                                ? "bg-brand-indigo text-white font-bold"
                                : "bg-muted/40 hover:bg-muted text-muted-foreground"
                            }`}
                          >
                            Top {lim}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                </form>

                {/* Search Results Display */}
                {searchMutation.isPending ? (
                  <div className="space-y-3 pt-2">
                    {Array.from({ length: 2 }).map((_, i) => (
                      <Card key={i} className="border-border/60 bg-muted/10 animate-pulse">
                        <CardContent className="p-3.5 space-y-2">
                          <div className="h-3.5 w-1/3 bg-muted rounded" />
                          <div className="h-3 w-5/6 bg-muted rounded" />
                          <div className="h-3 w-2/3 bg-muted rounded" />
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                ) : hasSearched && searchResults ? (
                  <div className="space-y-3 pt-2">
                    {/* Source-Grounded Answer Card */}
                    {searchResults.grounded_answer && (
                      <Card className={`border shadow-xs animate-in fade-in ${
                        searchResults.grounded_answer.evidence_status === "insufficient"
                          ? "border-amber-500/40 bg-amber-500/5"
                          : searchResults.grounded_answer.evidence_status === "analytical"
                          ? "border-brand-indigo/50 bg-brand-indigo/5"
                          : "border-emerald-500/40 bg-emerald-500/5"
                      }`}>
                        <CardHeader className="p-3.5 pb-2 border-b border-border/30 flex flex-row items-center justify-between">
                          <div className="flex items-center gap-2">
                            <div className={`p-1.5 rounded ${
                              searchResults.grounded_answer.evidence_status === "insufficient"
                                ? "bg-amber-500/20 text-amber-400"
                                : searchResults.grounded_answer.evidence_status === "analytical"
                                ? "bg-brand-indigo/20 text-brand-indigo"
                                : "bg-emerald-500/20 text-emerald-400"
                            }`}>
                              {searchResults.grounded_answer.evidence_status === "insufficient" ? (
                                <AlertCircle className="h-4 w-4" />
                              ) : searchResults.grounded_answer.evidence_status === "analytical" ? (
                                <Calculator className="h-4 w-4" />
                              ) : (
                                <CheckCircle2 className="h-4 w-4" />
                              )}
                            </div>
                            <div>
                              <CardTitle className="text-xs font-bold text-foreground flex items-center gap-2">
                                {searchResults.grounded_answer.evidence_status === "insufficient"
                                  ? "Insufficient Evidence"
                                  : searchResults.grounded_answer.evidence_status === "analytical"
                                  ? "Exact Analytical Answer (DuckDB SQL Engine)"
                                  : "Source-Grounded Answer"}
                              </CardTitle>
                              <CardDescription className="text-[10px] text-muted-foreground">
                                {searchResults.grounded_answer.evidence_status === "insufficient"
                                  ? "Strict hallucination prevention: not enough evidence in indexed files"
                                  : searchResults.grounded_answer.evidence_status === "analytical"
                                  ? "Calculated dynamically via DuckDB SQL analytics"
                                  : "Synthesized strictly from verified retrieved document context"}
                              </CardDescription>
                            </div>
                          </div>
                          <Badge variant="outline" className={`text-[9px] ${
                            searchResults.grounded_answer.evidence_status === "insufficient"
                              ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
                              : searchResults.grounded_answer.evidence_status === "analytical"
                              ? "bg-brand-indigo/10 text-brand-indigo border-brand-indigo/30"
                              : "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                          }`}>
                            {searchResults.grounded_answer.evidence_status === "insufficient"
                              ? "No Unsupported Facts"
                              : searchResults.grounded_answer.evidence_status === "analytical"
                              ? "SQL Verified"
                              : "Source Grounded"}
                          </Badge>
                        </CardHeader>
                        <CardContent className="p-3.5 space-y-2.5 text-xs">
                          {searchResults.analytical_answer && searchResults.grounded_answer.evidence_status === "analytical" ? (
                            <div className="space-y-2">
                              <div className="text-lg font-extrabold text-foreground tracking-tight">
                                {searchResults.analytical_answer.calculated_value}
                              </div>
                              <p className="text-[11px] text-muted-foreground leading-relaxed">
                                {searchResults.analytical_answer.explanation}
                              </p>
                              {searchResults.analytical_answer.sql_query && (
                                <div className="p-2 rounded bg-black/40 border border-border/40 font-mono text-[10px] text-cyan-300 overflow-x-auto select-all">
                                  {searchResults.analytical_answer.sql_query}
                                </div>
                              )}
                            </div>
                          ) : (
                            <p className="text-foreground/90 leading-relaxed font-sans text-xs">
                              {searchResults.grounded_answer.answer}
                            </p>
                          )}

                          {/* Direct Facts vs Inference */}
                          {searchResults.grounded_answer.direct_facts.length > 0 && searchResults.grounded_answer.evidence_status !== "insufficient" && (
                            <div className="p-2 rounded bg-muted/20 border border-border/30 space-y-1 text-[11px]">
                              <span className="font-semibold text-foreground/90 block text-[10px] uppercase tracking-wider">
                                Direct Facts from Sources:
                              </span>
                              {searchResults.grounded_answer.direct_facts.map((df, dfIdx) => (
                                <div key={dfIdx} className="flex items-start gap-1.5 text-muted-foreground">
                                  <span className="text-emerald-400 font-bold">•</span>
                                  <span>{df}</span>
                                </div>
                              ))}
                            </div>
                          )}

                          {searchResults.grounded_answer.inferences.length > 0 && (
                            <div className="p-2 rounded bg-muted/20 border border-border/30 space-y-1 text-[11px]">
                              <span className="font-semibold text-foreground/90 block text-[10px] uppercase tracking-wider">
                                Inferred Context / Analysis:
                              </span>
                              {searchResults.grounded_answer.inferences.map((inf, infIdx) => (
                                <div key={infIdx} className="flex items-start gap-1.5 text-muted-foreground">
                                  <span className="text-brand-indigo font-bold">•</span>
                                  <span>{inf}</span>
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Sources Cited */}
                          {searchResults.grounded_answer.sources && searchResults.grounded_answer.sources.length > 0 && (
                            <div className="pt-1.5 border-t border-border/20 text-[10px] text-muted-foreground flex flex-wrap items-center gap-1.5">
                              <span className="font-semibold text-foreground/80">Cited Sources:</span>
                              {searchResults.grounded_answer.sources.map((s, sIdx) => (
                                <Badge key={sIdx} variant="secondary" className="text-[9px] px-1.5 py-0 font-normal">
                                  {s.source_label || s.filename}
                                </Badge>
                              ))}
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    )}

                    <div className="flex items-center justify-between text-xs text-muted-foreground pt-1">
                      <span className="font-semibold text-foreground flex items-center gap-1.5">
                        <Database className="h-3.5 w-3.5 text-brand-indigo" />
                        Retrieval Evidence ({searchResults.results.length} Matched Chunks)
                      </span>
                      <span className="text-[10px]">Token Context: {searchResults.token_count}</span>
                    </div>

                    {searchResults.results.length === 0 ? (
                      <div className="p-6 text-center text-xs text-muted-foreground border border-dashed border-border/80 rounded-lg space-y-1">
                        <AlertCircle className="h-5 w-5 mx-auto text-muted-foreground/60 mb-1" />
                        <p className="font-semibold text-foreground/80">No semantic matches found</p>
                        <p className="text-[11px]">
                          Try adjusting your search terms or increasing the BM25 keyword weighting.
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
                        {searchResults.results.map((res, idx) => {
                          const relLabel = res.relevance_label || (res.score >= 0.75 ? "Highly Relevant" : res.score >= 0.50 ? "Relevant" : res.score >= 0.30 ? "Moderately Relevant" : "Low Relevance");
                          const scoreColor =
                            res.score >= 0.75
                              ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10"
                              : res.score >= 0.50
                              ? "text-blue-400 border-blue-500/30 bg-blue-500/10"
                              : res.score >= 0.30
                              ? "text-amber-400 border-amber-500/30 bg-amber-500/10"
                              : "text-slate-400 border-slate-500/30 bg-slate-500/10";

                          const chunkType = res.chunk_type || res.citation.chunk_type || "text";
                          let chunkBadge = { label: "Passage", bg: "bg-muted text-muted-foreground border-border/40" };
                          if (chunkType === "dataset_schema") {
                            chunkBadge = { label: "Dataset Schema", bg: "bg-purple-500/10 text-purple-400 border-purple-500/20" };
                          } else if (chunkType === "dataset_summary") {
                            chunkBadge = { label: "Dataset Summary", bg: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20" };
                          } else if (chunkType === "table_rows") {
                            const rRange = res.row_range || (res.citation.row_start ? `Rows ${res.citation.row_start}–${res.citation.row_end}` : "Table Rows");
                            chunkBadge = { label: rRange, bg: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" };
                          }

                          return (
                            <Card
                              key={idx}
                              className="border-border/80 hover:border-brand-indigo/40 transition-all bg-card/80 space-y-0"
                            >
                              <CardHeader className="p-3 pb-1 flex flex-row items-center justify-between gap-2">
                                <div className="flex items-center gap-2 min-w-0">
                                  {getFormatIcon(res.citation.document_type)}
                                  <CardTitle className="text-xs font-bold text-foreground truncate">
                                    {res.citation.filename}
                                  </CardTitle>
                                  <Badge variant="outline" className={`text-[9px] px-1.5 py-0 shrink-0 ${chunkBadge.bg}`}>
                                    {chunkBadge.label}
                                  </Badge>
                                </div>
                                <div className="flex items-center gap-1.5 shrink-0">
                                  <Badge variant="outline" className={`text-[10px] ${scoreColor}`} title={`Calibrated relevance score: ${res.score.toFixed(2)}/1.00`}>
                                    {relLabel} • Score: {res.score.toFixed(2)}
                                  </Badge>
                                </div>
                              </CardHeader>
                              <CardContent className="p-3 pt-1.5 space-y-2 text-xs">
                                {res.explanation && (
                                  <div className="text-[10px] text-muted-foreground bg-muted/20 px-2 py-1 rounded border border-border/30 flex items-center gap-1.5">
                                    <Info className="h-3 w-3 text-brand-indigo shrink-0" />
                                    <span className="truncate">{res.explanation}</span>
                                  </div>
                                )}

                                <div className="text-foreground/90 leading-relaxed text-[11px] font-sans bg-muted/20 p-2.5 rounded-md border border-border/30 max-h-48 overflow-y-auto whitespace-pre-wrap">
                                  {res.text}
                                </div>

                                <div className="flex items-center justify-between text-[10px] text-muted-foreground pt-1 border-t border-border/20">
                                  <div className="flex items-center gap-2 truncate">
                                    {res.citation.heading && (
                                      <span className="truncate max-w-[140px] text-brand-indigo font-medium">
                                        #{res.citation.heading}
                                      </span>
                                    )}
                                    {res.citation.page && <span>Chunk #{res.citation.page}</span>}
                                  </div>

                                  <button
                                    onClick={() => {
                                      const foundDoc = rawDocuments.find((d) => d.doc_id === res.doc_id);
                                      if (foundDoc) setSelectedDocMetadata(foundDoc);
                                    }}
                                    className="text-brand-indigo hover:underline flex items-center gap-1 font-medium shrink-0"
                                  >
                                    View Metadata <ArrowRight className="h-3 w-3" />
                                  </button>
                                </div>
                              </CardContent>
                            </Card>
                          );
                        })}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="p-8 text-center text-xs text-muted-foreground border border-dashed border-border/80 rounded-lg space-y-2">
                    <Search className="h-6 w-6 mx-auto text-muted-foreground/40 mb-1" />
                    <p className="font-semibold text-foreground/80">Vector Search Ready</p>
                    <p className="text-[11px]">
                      Enter any natural language question to perform semantic vector retrieval against project documents.
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* Metadata Inspector Modal */}
      {selectedDocMetadata && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs transition-all animate-in fade-in">
          <div className="relative w-full max-w-2xl bg-card border border-border/80 rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
            <div className="flex items-center justify-between p-4 border-b border-border/40 bg-muted/20">
              <div className="flex items-center gap-2.5">
                {getFormatIcon(selectedDocMetadata.document_type)}
                <div>
                  <h3 className="text-sm font-bold text-foreground">{selectedDocMetadata.filename}</h3>
                  <p className="text-[10px] text-muted-foreground">Document Metadata Inspector</p>
                </div>
              </div>
              <Button
                size="icon"
                variant="ghost"
                className="h-8 w-8"
                onClick={() => setSelectedDocMetadata(null)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="p-5 space-y-4 overflow-y-auto">
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="p-3 rounded-lg bg-muted/20 border border-border/40 space-y-1">
                  <span className="text-[10px] text-muted-foreground uppercase block font-semibold">Document ID</span>
                  <span className="font-mono text-foreground text-[11px] select-all">{selectedDocMetadata.doc_id}</span>
                </div>
                <div className="p-3 rounded-lg bg-muted/20 border border-border/40 space-y-1">
                  <span className="text-[10px] text-muted-foreground uppercase block font-semibold">File Format & Size</span>
                  <span className="font-medium text-foreground">
                    {selectedDocMetadata.document_type.toUpperCase()} • {formatFileSize(selectedDocMetadata.file_size)}
                  </span>
                </div>
                <div className="p-3 rounded-lg bg-muted/20 border border-border/40 space-y-1">
                  <span className="text-[10px] text-muted-foreground uppercase block font-semibold">Vector Chunks Count</span>
                  <span className="font-medium text-foreground">{selectedDocMetadata.chunks_count} indexed chunks</span>
                </div>
                <div className="p-3 rounded-lg bg-muted/20 border border-border/40 space-y-1">
                  <span className="text-[10px] text-muted-foreground uppercase block font-semibold">Upload Date</span>
                  <span className="font-medium text-foreground">{selectedDocMetadata.upload_date}</span>
                </div>
                <div className="p-3 rounded-lg bg-muted/20 border border-border/40 space-y-1">
                  <span className="text-[10px] text-muted-foreground uppercase block font-semibold">Project Workspace</span>
                  <span className="font-medium text-foreground">{selectedDocMetadata.workspace}</span>
                </div>
                <div className="p-3 rounded-lg bg-muted/20 border border-border/40 space-y-1">
                  <span className="text-[10px] text-muted-foreground uppercase block font-semibold">Author</span>
                  <span className="font-medium text-foreground">{selectedDocMetadata.author}</span>
                </div>
              </div>
            </div>

            <div className="p-4 border-t border-border/40 bg-muted/10 flex justify-end gap-2">
              <Button size="sm" variant="outline" onClick={() => setSelectedDocMetadata(null)}>
                Close Inspector
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirmDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs transition-all animate-in fade-in">
          <div className="relative w-full max-w-md bg-card border border-border/80 rounded-xl shadow-2xl p-6 space-y-4">
            <div className="flex items-center gap-3 text-rose-400">
              <AlertCircle className="h-6 w-6 shrink-0" />
              <h3 className="text-base font-bold text-foreground">Confirm Document Deletion</h3>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Are you sure you want to delete <strong className="text-foreground">{deleteConfirmDoc.filename}</strong>?
              This will permanently purge all <strong className="text-foreground">{deleteConfirmDoc.chunks_count} chunks</strong> from the project vector store.
            </p>
            <div className="flex items-center justify-end gap-2 pt-2">
              <Button size="sm" variant="outline" onClick={() => setDeleteConfirmDoc(null)}>
                Cancel
              </Button>
              <Button
                size="sm"
                variant="destructive"
                disabled={deleteMutation.isPending}
                onClick={handleDeleteConfirm}
              >
                {deleteMutation.isPending ? "Deleting..." : "Delete Document"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
