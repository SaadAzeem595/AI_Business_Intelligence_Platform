"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DatasetService } from "../services/dataset.service";

export function useDatasets(id?: string, projectId?: string) {
  const queryClient = useQueryClient();

  const listQuery = useQuery({
    queryKey: projectId ? ["project-datasets", projectId] : ["datasets", "list"],
    queryFn: () => DatasetService.getList(projectId),
    enabled: !id,
    staleTime: 30 * 1000,
  });

  const detailQuery = useQuery({
    queryKey: ["datasets", "detail", id],
    queryFn: () => DatasetService.getDetails(id!),
    enabled: !!id,
    staleTime: 5 * 60 * 1000,
  });

  const cleanMutation = useMutation({
    mutationFn: ({ actions }: { actions: string[] }) => DatasetService.clean(id!, actions),
    onSuccess: (data) => {
      queryClient.setQueryData(["datasets", "detail", id], data);
      if (projectId) {
        queryClient.invalidateQueries({ queryKey: ["project-datasets", projectId] });
      } else {
        queryClient.invalidateQueries({ queryKey: ["datasets", "list"] });
      }
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (targetId: string) => DatasetService.delete(targetId),
    onMutate: async (deletedId) => {
      const queryKey = projectId ? ["project-datasets", projectId] : ["datasets", "list"];
      await queryClient.cancelQueries({ queryKey });
      const previousList = queryClient.getQueryData<any[]>(queryKey);
      if (previousList) {
        queryClient.setQueryData(
          queryKey,
          previousList.filter((d) => d.id !== deletedId)
        );
      }
      return { previousList };
    },
    onError: (err, deletedId, context) => {
      const queryKey = projectId ? ["project-datasets", projectId] : ["datasets", "list"];
      if (context?.previousList) {
        queryClient.setQueryData(queryKey, context.previousList);
      }
    },
    onSettled: () => {
      const queryKey = projectId ? ["project-datasets", projectId] : ["datasets", "list"];
      queryClient.invalidateQueries({ queryKey });
    },
  });

  return {
    datasets: listQuery.data || [],
    datasetDetails: detailQuery.data || null,
    isLoading: id ? detailQuery.isLoading : listQuery.isLoading,
    isCleaning: cleanMutation.isPending,
    clean: cleanMutation.mutateAsync,
    deleteDataset: deleteMutation.mutateAsync,
  };
}
