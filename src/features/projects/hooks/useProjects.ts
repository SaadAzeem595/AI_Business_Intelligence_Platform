"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ProjectService, Project } from "../services/project.service";

export function useProjects(id?: string) {
  const queryClient = useQueryClient();

  const listQuery = useQuery({
    queryKey: ["projects", "list"],
    queryFn: ProjectService.getList,
    enabled: !id,
    staleTime: 30 * 1000,
  });

  const detailQuery = useQuery({
    queryKey: ["projects", "detail", id],
    queryFn: () => ProjectService.get(id!),
    enabled: !!id,
    staleTime: 5 * 60 * 1000,
  });

  const createMutation = useMutation({
    mutationFn: ({ name, description }: { name: string; description?: string }) =>
      ProjectService.create(name, description),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects", "list"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (targetId: string) => ProjectService.delete(targetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects", "list"] });
    },
  });

  return {
    projects: listQuery.data || [],
    project: detailQuery.data || null,
    isLoading: id ? detailQuery.isLoading : listQuery.isLoading,
    isError: id ? detailQuery.isError : listQuery.isError,
    refetch: id ? detailQuery.refetch : listQuery.refetch,
    isCreating: createMutation.isPending,
    createProject: createMutation.mutateAsync,
    deleteProject: deleteMutation.mutateAsync,
  };
}
