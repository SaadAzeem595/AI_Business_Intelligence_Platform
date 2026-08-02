"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ReportService, GenerateReportPayload } from "../services/report.service";

export function useReports() {
  const queryClient = useQueryClient();

  const reportsQuery = useQuery({
    queryKey: ["reports", "list"],
    queryFn: ReportService.getList,
    staleTime: 2 * 60 * 1000,
  });

  const generateMutation = useMutation({
    mutationFn: (payload: GenerateReportPayload) => ReportService.generate(payload),
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

  return {
    reports: reportsQuery.data || [],
    isLoading: reportsQuery.isLoading,
    generateReport: generateMutation.mutateAsync,
    isGenerating: generateMutation.isPending,
    deleteReport: deleteMutation.mutateAsync,
  };
}
