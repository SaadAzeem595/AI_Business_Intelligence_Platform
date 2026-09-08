"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ReportService } from "../services/report.service";
import { Report, GenerateReportPayload, ReportFilterParams } from "@/shared/types/reports";

export function useReports(initialFilters?: ReportFilterParams) {
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState<ReportFilterParams>(initialFilters || {});
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [previewReport, setPreviewReport] = useState<Report | null>(null);

  const reportsQuery = useQuery({
    queryKey: ["reports", "list", filters],
    queryFn: () => ReportService.getList(filters),
    staleTime: 60 * 1000,
  });

  const reportDetailQuery = useQuery({
    queryKey: ["reports", "detail", selectedReportId],
    queryFn: () => (selectedReportId ? ReportService.getById(selectedReportId) : null),
    enabled: !!selectedReportId,
    staleTime: 60 * 1000,
  });

  const schedulesQuery = useQuery({
    queryKey: ["reports", "schedules"],
    queryFn: ReportService.listSchedules,
    staleTime: 60 * 1000,
  });

  const generateMutation = useMutation({
    mutationFn: (payload: GenerateReportPayload) => ReportService.generate(payload),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["reports", "list"] });
      if (data) {
        setPreviewReport(data);
      }
    },
  });

  const regenerateMutation = useMutation({
    mutationFn: ({ id, customFocus }: { id: string; customFocus?: string }) =>
      ReportService.regenerateNarrative(id, customFocus),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["reports", "list"] });
      if (selectedReportId) {
        queryClient.invalidateQueries({ queryKey: ["reports", "detail", selectedReportId] });
      }
      setPreviewReport(data);
    },
  });

  const emailMutation = useMutation({
    mutationFn: ({ id, recipient }: { id: string; recipient?: string }) =>
      ReportService.sendEmail(id, recipient),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reports", "list"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => ReportService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reports", "list"] });
    },
  });

  const createScheduleMutation = useMutation({
    mutationFn: (payload: any) => ReportService.createSchedule(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reports", "schedules"] });
    },
  });

  const cancelScheduleMutation = useMutation({
    mutationFn: (id: string) => ReportService.cancelSchedule(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reports", "schedules"] });
    },
  });

  const downloadReport = async (id: string, title: string, format?: string) => {
    await ReportService.download(id, title, format);
  };

  return {
    reports: reportsQuery.data || [],
    isLoading: reportsQuery.isLoading,
    isRefetching: reportsQuery.isRefetching,
    refetchReports: reportsQuery.refetch,
    filters,
    setFilters,

    selectedReportId,
    setSelectedReportId,
    previewReport: previewReport || reportDetailQuery.data || null,
    setPreviewReport,

    generateReport: generateMutation.mutateAsync,
    isGenerating: generateMutation.isPending,

    regenerateNarrative: regenerateMutation.mutateAsync,
    isRegenerating: regenerateMutation.isPending,

    sendEmail: emailMutation.mutateAsync,
    isSendingEmail: emailMutation.isPending,

    deleteReport: deleteMutation.mutateAsync,
    downloadReport,

    schedules: schedulesQuery.data || [],
    isLoadingSchedules: schedulesQuery.isLoading,
    createSchedule: createScheduleMutation.mutateAsync,
    cancelSchedule: cancelScheduleMutation.mutateAsync,
  };
}
