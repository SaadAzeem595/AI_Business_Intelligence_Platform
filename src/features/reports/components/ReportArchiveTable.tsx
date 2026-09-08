"use client";

import React, { useState } from "react";
import { Report, ReportFilterParams } from "@/shared/types/reports";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";
import {
  FileText,
  Clock,
  Download,
  Trash2,
  Eye,
  Mail,
  RefreshCw,
  Search,
  Filter,
  ChevronLeft,
  ChevronRight,
  Database,
  CheckCircle2,
  AlertCircle,
  Hourglass,
  Layers,
} from "lucide-react";
import { useProjects } from "@/features/projects/hooks/useProjects";

interface ReportArchiveTableProps {
  reports: Report[];
  isLoading: boolean;
  onView: (report: Report) => void;
  onDownload: (id: string, title: string, format?: string) => Promise<void>;
  onSendEmail: (id: string, recipient?: string) => Promise<void>;
  onRegenerate: (id: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  filters: ReportFilterParams;
  onFilterChange: (filters: ReportFilterParams) => void;
}

export function ReportArchiveTable({
  reports,
  isLoading,
  onView,
  onDownload,
  onSendEmail,
  onRegenerate,
  onDelete,
  filters,
  onFilterChange,
}: ReportArchiveTableProps) {
  const { projects } = useProjects();
  const [search, setSearch] = useState(filters.search || "");
  const [selectedFormat, setSelectedFormat] = useState(filters.format || "");
  const [selectedStatus, setSelectedStatus] = useState(filters.status || "");
  const [selectedProject, setSelectedProject] = useState(filters.project_id || "");
  const [selectedType, setSelectedType] = useState(filters.report_type || "");
  const [page, setPage] = useState(1);
  const pageSize = 8;

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onFilterChange({
      ...filters,
      search: search || undefined,
      format: selectedFormat || undefined,
      status: selectedStatus || undefined,
      project_id: selectedProject || undefined,
      report_type: selectedType || undefined,
    });
    setPage(1);
  };

  const handleClearFilters = () => {
    setSearch("");
    setSelectedFormat("");
    setSelectedStatus("");
    setSelectedProject("");
    setSelectedType("");
    onFilterChange({});
    setPage(1);
  };

  // Client-side filtering fallback
  const filteredReports = reports.filter((r) => {
    if (search && !r.title.toLowerCase().includes(search.toLowerCase())) return false;
    if (selectedFormat && r.type !== selectedFormat) return false;
    if (selectedStatus && r.delivery_status !== selectedStatus) return false;
    if (selectedProject && r.project_id !== selectedProject) return false;
    if (selectedType && r.template !== selectedType) return false;
    return true;
  });

  const totalPages = Math.ceil(filteredReports.length / pageSize) || 1;
  const paginatedReports = filteredReports.slice((page - 1) * pageSize, page * pageSize);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "Delivered":
        return (
          <Badge variant="outline" className="bg-emerald-500/10 text-emerald-400 border-emerald-500/30 text-[10px] flex items-center gap-1">
            <CheckCircle2 className="h-3 w-3" /> Delivered
          </Badge>
        );
      case "Failed":
        return (
          <Badge variant="outline" className="bg-rose-500/10 text-rose-400 border-rose-500/30 text-[10px] flex items-center gap-1">
            <AlertCircle className="h-3 w-3" /> Failed
          </Badge>
        );
      case "Delivery Pending":
      case "Pending":
      default:
        return (
          <Badge variant="outline" className="bg-amber-500/10 text-amber-400 border-amber-500/30 text-[10px] flex items-center gap-1">
            <Hourglass className="h-3 w-3" /> {status}
          </Badge>
        );
    }
  };

  const getFormatBadge = (type: string) => {
    switch (type) {
      case "PDF":
        return <Badge variant="outline" className="text-[10px] bg-rose-500/10 text-rose-300 border-rose-500/20">PDF</Badge>;
      case "PowerPoint":
      case "PPTX":
        return <Badge variant="outline" className="text-[10px] bg-amber-500/10 text-amber-300 border-amber-500/20">PPTX</Badge>;
      case "HTML":
        return <Badge variant="outline" className="text-[10px] bg-brand-indigo/10 text-brand-indigo border-brand-indigo/20">HTML</Badge>;
      default:
        return <Badge variant="outline" className="text-[10px]">{type}</Badge>;
    }
  };

  return (
    <Card className="border border-border/80 bg-card/60 backdrop-blur shadow-sm space-y-4">
      <CardHeader className="pb-2">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <CardTitle className="text-base font-bold flex items-center gap-2 text-foreground">
              <FileText className="h-4.5 w-4.5 text-brand-indigo" />
              Executive Reports Archive
            </CardTitle>
            <CardDescription className="text-xs text-muted-foreground">
              Traceable log of all synthesized briefings, verified analytical contexts, and delivery histories.
            </CardDescription>
          </div>

          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs font-mono">
              Total Reports: {filteredReports.length}
            </Badge>
          </div>
        </div>

        {/* Filter Controls Bar */}
        <form onSubmit={handleSearchSubmit} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-2 pt-3">
          {/* Search Input */}
          <div className="lg:col-span-2 relative">
            <Search className="h-3.5 w-3.5 absolute left-2.5 top-2.5 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search reports by title..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-xs rounded-md border border-border/80 bg-background text-foreground"
            />
          </div>

          {/* Project Filter */}
          <div>
            <select
              value={selectedProject}
              onChange={(e) => setSelectedProject(e.target.value)}
              className="w-full py-1.5 px-2 text-xs rounded-md border border-border/80 bg-background text-foreground cursor-pointer"
            >
              <option value="">All Projects</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {/* Format Filter */}
          <div>
            <select
              value={selectedFormat}
              onChange={(e) => setSelectedFormat(e.target.value)}
              className="w-full py-1.5 px-2 text-xs rounded-md border border-border/80 bg-background text-foreground cursor-pointer"
            >
              <option value="">All Formats</option>
              <option value="PDF">PDF</option>
              <option value="PowerPoint">PowerPoint</option>
              <option value="HTML">HTML</option>
            </select>
          </div>

          {/* Status Filter */}
          <div>
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="w-full py-1.5 px-2 text-xs rounded-md border border-border/80 bg-background text-foreground cursor-pointer"
            >
              <option value="">All Statuses</option>
              <option value="Delivered">Delivered</option>
              <option value="Pending">Pending</option>
              <option value="Failed">Failed</option>
            </select>
          </div>

          {/* Action Filter Button */}
          <div className="flex gap-1">
            <Button type="submit" size="sm" variant="outline" className="text-xs flex-1">
              Apply
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={handleClearFilters} className="text-xs px-2">
              Reset
            </Button>
          </div>
        </form>
      </CardHeader>

      <CardContent className="space-y-4">
        {isLoading ? (
          <div className="py-16 text-center text-xs text-muted-foreground flex flex-col items-center gap-2">
            <RefreshCw className="h-6 w-6 animate-spin text-brand-indigo" />
            <span>Loading executive reports archive...</span>
          </div>
        ) : paginatedReports.length === 0 ? (
          <div className="py-16 text-center text-xs text-muted-foreground border border-dashed border-border/70 rounded-lg space-y-2">
            <FileText className="h-8 w-8 mx-auto text-muted-foreground/50" />
            <p className="font-semibold text-foreground">No reports match your filters</p>
            <p className="text-muted-foreground text-[11px]">Compile a new report or adjust your search filter criteria.</p>
          </div>
        ) : (
          <div className="border border-border/80 rounded-lg overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/40 text-muted-foreground border-b border-border text-[11px]">
                <tr>
                  <th className="p-3">Report Title</th>
                  <th className="p-3">Project / Period</th>
                  <th className="p-3">Format</th>
                  <th className="p-3">Schedule</th>
                  <th className="p-3">Recipient</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Created</th>
                  <th className="p-3">Size</th>
                  <th className="p-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {paginatedReports.map((row) => (
                  <tr key={row.id} className="hover:bg-muted/10 transition-colors">
                    <td className="p-3">
                      <div className="flex items-center gap-2">
                        <FileText className="h-4 w-4 text-brand-indigo shrink-0" />
                        <div>
                          <div className="font-semibold text-foreground hover:text-brand-indigo cursor-pointer transition-colors" onClick={() => onView(row)}>
                            {row.title}
                          </div>
                          <div className="text-[10px] text-muted-foreground">{row.template || "Executive Summary"}</div>
                        </div>
                      </div>
                    </td>

                    <td className="p-3">
                      <div className="text-foreground font-medium">
                        {projects.find((p) => p.id === row.project_id)?.name || "Global Workspace"}
                      </div>
                      <div className="text-[10px] text-muted-foreground">{row.reporting_period || "Last 30 Days"}</div>
                    </td>

                    <td className="p-3">{getFormatBadge(row.type)}</td>

                    <td className="p-3">
                      <div className="flex items-center gap-1 text-[11px]">
                        <Clock className="h-3 w-3 text-muted-foreground" />
                        <span>{row.frequency}</span>
                      </div>
                    </td>

                    <td className="p-3 text-muted-foreground font-mono text-[11px] truncate max-w-[140px]">{row.recipient}</td>

                    <td className="p-3">{getStatusBadge(row.delivery_status)}</td>

                    <td className="p-3 text-muted-foreground text-[11px] whitespace-nowrap">
                      {row.created ? row.created.split("T")[0] : "—"}
                    </td>

                    <td className="p-3 text-muted-foreground font-mono text-[11px]">{row.size}</td>

                    <td className="p-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        {/* View Preview Button */}
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7 text-muted-foreground hover:text-brand-indigo"
                          title="View Interactive Preview"
                          onClick={() => onView(row)}
                        >
                          <Eye className="h-3.5 w-3.5" />
                        </Button>

                        {/* Download Menu / Direct Download */}
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7 text-muted-foreground hover:text-foreground"
                          title="Download Report File"
                          onClick={() => onDownload(row.id, row.title, row.type)}
                        >
                          <Download className="h-3.5 w-3.5" />
                        </Button>

                        {/* Email Dispatch */}
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7 text-muted-foreground hover:text-brand-indigo"
                          title="Email Report Deliverable"
                          onClick={() => onSendEmail(row.id, row.recipient)}
                        >
                          <Mail className="h-3.5 w-3.5" />
                        </Button>

                        {/* Delete Report */}
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7 text-muted-foreground hover:text-rose-400 hover:bg-rose-500/10"
                          title="Delete Report Record"
                          onClick={() => onDelete(row.id)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        <div className="flex items-center justify-between text-xs text-muted-foreground pt-1">
          <div>
            Page {page} of {totalPages} &bull; Showing {paginatedReports.length} items
          </div>
          <div className="flex items-center gap-1">
            <Button
              size="sm"
              variant="outline"
              className="h-7 px-2"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <ChevronLeft className="h-3.5 w-3.5 mr-0.5" /> Prev
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-7 px-2"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Next <ChevronRight className="h-3.5 w-3.5 ml-0.5" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
