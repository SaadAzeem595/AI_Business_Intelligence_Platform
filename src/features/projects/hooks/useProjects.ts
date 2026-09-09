"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useUser } from "@clerk/nextjs";
import { useUIStore } from "@/shared/services/uiStore";
import { ProjectService, Project } from "../services/project.service";

export function useProjects(id?: string) {
  const queryClient = useQueryClient();
  const { isLoaded, user } = useUser();
  const { activeOrg } = useUIStore();

  const isDevAuthBypass =
    process.env.NEXT_PUBLIC_DEV_AUTH_BYPASS === "true" &&
    process.env.NODE_ENV !== "production";

  // Auth readiness
  const isAuthReady = isDevAuthBypass ? true : isLoaded;
  const userId = user?.id || (isDevAuthBypass ? "dev-user-001" : null);
  const workspaceId = activeOrg || "default";
  const isAuthLoading = !isAuthReady;
  const authError = isAuthReady && !userId ? "Authentication required." : null;

  const listQueryKey = ["projects", workspaceId, userId || "unauth", "list"];
  const detailQueryKey = ["projects", workspaceId, userId || "unauth", "detail", id];

  const listQuery = useQuery({
    queryKey: listQueryKey,
    queryFn: ProjectService.getList,
    enabled: Boolean(isAuthReady && userId && workspaceId && !id),
    staleTime: 30 * 1000,
    retry: 2,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 3000),
  });

  const detailQuery = useQuery({
    queryKey: detailQueryKey,
    queryFn: () => ProjectService.get(id!),
    enabled: Boolean(isAuthReady && userId && workspaceId && !!id),
    staleTime: 5 * 60 * 1000,
    retry: 2,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 3000),
  });

  const createMutation = useMutation({
    mutationFn: ({ name, description }: { name: string; description?: string }) =>
      ProjectService.create(name, description),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["projects", workspaceId, userId || "unauth"],
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (targetId: string) => ProjectService.delete(targetId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["projects", workspaceId, userId || "unauth"],
      });
    },
  });

  const isQueryLoading = id ? detailQuery.isLoading : listQuery.isLoading;
  const isQueryError = id ? detailQuery.isError : listQuery.isError;
  const queryError = id ? detailQuery.error : listQuery.error;

  return {
    projects: listQuery.data || [],
    project: detailQuery.data || null,
    isAuthLoading,
    authError,
    isLoading: isAuthLoading || isQueryLoading,
    isError: Boolean(authError || isQueryError),
    error: authError || (queryError instanceof Error ? queryError.message : (queryError ? String(queryError) : null)),
    refetch: id ? detailQuery.refetch : listQuery.refetch,
    isCreating: createMutation.isPending,
    createProject: createMutation.mutateAsync,
    deleteProject: deleteMutation.mutateAsync,
    workspaceId,
    userId,
  };
}
export type { Project };
