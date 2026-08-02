"use client";

import { useQuery } from "@tanstack/react-query";
import { DashboardService } from "../services/dashboard.service";

export function useDashboard() {
  const metricsQuery = useQuery({
    queryKey: ["dashboard", "metrics"],
    queryFn: DashboardService.getMetrics,
    staleTime: 30 * 1000,
  });

  const trendsQuery = useQuery({
    queryKey: ["dashboard", "trends"],
    queryFn: DashboardService.getTrends,
    staleTime: 60 * 1000,
  });

  return {
    metrics: metricsQuery.data || null,
    trends: trendsQuery.data || [],
    isLoading: metricsQuery.isLoading || trendsQuery.isLoading,
    isError: metricsQuery.isError || trendsQuery.isError,
    refetch: async () => {
      await Promise.all([metricsQuery.refetch(), trendsQuery.refetch()]);
    },
  };
}
