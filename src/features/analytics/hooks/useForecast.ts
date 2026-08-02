"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnalyticsService } from "../services/analytics.service";

export function useForecast(model?: string, confidence?: number, periods?: number) {
  const query = useQuery({
    queryKey: ["analytics", "forecast", model, confidence, periods],
    queryFn: () => AnalyticsService.getForecast(model!, confidence!, periods!),
    enabled: !!model && confidence !== undefined && periods !== undefined,
    staleTime: 5 * 60 * 1000,
  });

  return {
    forecastData: query.data?.data || [],
    metrics: query.data?.metrics || [],
    isLoading: query.isLoading,
    isError: query.isError,
    refetch: query.refetch,
  };
}

export function useSegmentation(clusters?: number, features?: string) {
  const query = useQuery({
    queryKey: ["analytics", "segmentation", clusters, features],
    queryFn: () => AnalyticsService.getSegmentation(clusters!, features!),
    enabled: clusters !== undefined && !!features,
    staleTime: 5 * 60 * 1000,
  });

  return {
    scatterData: query.data?.scatter || [],
    cohorts: query.data?.cohorts || [],
    isLoading: query.isLoading,
    refetch: query.refetch,
  };
}

export function useAnomalies(sensitivity?: number) {
  const query = useQuery({
    queryKey: ["analytics", "anomalies", sensitivity],
    queryFn: () => AnalyticsService.getAnomalies(sensitivity!),
    enabled: sensitivity !== undefined,
    staleTime: 2 * 60 * 1000,
  });

  return {
    timelineData: query.data?.timeline || [],
    anomalies: query.data?.logs || [],
    isLoading: query.isLoading,
    refetch: query.refetch,
  };
}

export function useSQL() {
  const queryClient = useQueryClient();

  const schemaQuery = useQuery({
    queryKey: ["sql", "schema"],
    queryFn: AnalyticsService.getSQLSchema,
    staleTime: 10 * 60 * 1000,
  });

  const executeMutation = useMutation({
    mutationFn: (queryText: string) => AnalyticsService.executeSQL(queryText),
  });

  return {
    schema: schemaQuery.data || [],
    isLoadingSchema: schemaQuery.isLoading,
    executeSQL: executeMutation.mutateAsync,
    isExecuting: executeMutation.isPending,
    results: executeMutation.data || null,
  };
}
