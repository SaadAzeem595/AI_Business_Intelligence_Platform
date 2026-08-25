"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnalyticsService } from "../services/analytics.service";
import { ProjectForecastRequest } from "@/shared/types/analytics";

export function useForecastingHealth(projectId?: string) {
  const query = useQuery({
    queryKey: ["analytics", "forecasting-health", projectId],
    queryFn: () => AnalyticsService.checkForecastingHealth(projectId),
    staleTime: 60 * 1000,
    retry: 1,
  });

  return {
    isHealthy: query.isSuccess && query.data?.api === "ok",
    healthData: query.data || null,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error as any,
  };
}

export function useForecastSchemaInfo(projectId?: string) {
  const query = useQuery({
    queryKey: ["analytics", "forecast-schema-info", projectId],
    queryFn: () => AnalyticsService.getProjectForecastSchemaInfo(projectId!),
    enabled: !!projectId,
    staleTime: 30 * 1000,
  });

  return {
    hasTimeSeries: query.data?.has_time_series || false,
    candidates: query.data?.candidates || [],
    message: query.data?.message || null,
    isLoading: query.isLoading,
    isError: query.isError,
    refetch: query.refetch,
  };
}

export function useProjectForecast(projectId?: string, config?: ProjectForecastRequest) {
  const query = useQuery({
    queryKey: ["analytics", "project-forecast", projectId, config],
    queryFn: () => AnalyticsService.runProjectForecast(projectId!, config || {}),
    enabled: !!projectId && !!config && !!config.dataset_id && !!config.date_column && !!config.target_column,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  return {
    forecastResult: query.data || null,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error as any,
    refetch: query.refetch,
  };
}

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

export function useSegmentSchemaInfo(projectId?: string) {
  const query = useQuery({
    queryKey: ["analytics", "segment-schema-info", projectId],
    queryFn: () => AnalyticsService.getProjectSegmentSchemaInfo(projectId!),
    enabled: !!projectId,
    staleTime: 30 * 1000,
  });

  return {
    candidates: query.data?.candidates || [],
    datasetCount: query.data?.dataset_count || 0,
    message: query.data?.message || null,
    isLoading: query.isLoading,
    isError: query.isError,
    refetch: query.refetch,
  };
}

export function useSegmentation(
  clusters?: number,
  features?: string,
  datasetId?: string,
  projectId?: string,
  mode?: string,
  entityKey?: string
) {
  const query = useQuery({
    queryKey: ["analytics", "segmentation", clusters, features, datasetId, projectId, mode, entityKey],
    queryFn: () => AnalyticsService.getSegmentation(clusters, features, datasetId, projectId, mode, entityKey),
    enabled: clusters !== undefined && (projectId ? !!datasetId : true),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });


  return {
    segmentResult: query.data || null,
    scatterData: query.data?.scatter || [],
    cohorts: query.data?.cohorts || [],
    evaluation: query.data?.evaluation || null,
    profiles: query.data?.profiles || [],
    featuresUsed: query.data?.features_used || [],
    datasetType: query.data?.dataset_type || null,
    entityKey: query.data?.entity_key || null,
    message: query.data?.message || null,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error as any,
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

export function useSQL(projectId?: string) {
  const queryClient = useQueryClient();

  const schemaQuery = useQuery({
    queryKey: projectId ? ["sql", "schema", projectId] : ["sql", "schema"],
    queryFn: () => AnalyticsService.getSQLSchema(projectId),
    staleTime: 30 * 1000,
  });

  const executeMutation = useMutation({
    mutationFn: (queryText: string) => AnalyticsService.executeSQL(queryText, projectId),
  });

  return {
    schema: schemaQuery.data || [],
    isLoadingSchema: schemaQuery.isLoading,
    executeSQL: executeMutation.mutateAsync,
    isExecuting: executeMutation.isPending,
    results: executeMutation.data || null,
  };
}
