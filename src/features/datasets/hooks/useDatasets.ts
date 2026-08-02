"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DatasetService } from "../services/dataset.service";

export function useDatasets(id?: string) {
  const queryClient = useQueryClient();

  const listQuery = useQuery({
    queryKey: ["datasets", "list"],
    queryFn: DatasetService.getList,
    enabled: !id,
    staleTime: 60 * 1000,
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
      queryClient.invalidateQueries({ queryKey: ["datasets", "list"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (targetId: string) => DatasetService.delete(targetId),
    onMutate: async (deletedId) => {
      await queryClient.cancelQueries({ queryKey: ["datasets", "list"] });
      const previousList = queryClient.getQueryData<any[]>(["datasets", "list"]);
      if (previousList) {
        queryClient.setQueryData(
          ["datasets", "list"],
          previousList.filter((d) => d.id !== deletedId)
        );
      }
      return { previousList };
    },
    onError: (err, deletedId, context) => {
      if (context?.previousList) {
        queryClient.setQueryData(["datasets", "list"], context.previousList);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["datasets", "list"] });
    },
  });

  return {
    datasets: listQuery.data || [],
    datasetDetails: detailQuery.data || null,
    isLoading: listQuery.isLoading || detailQuery.isLoading,
    isCleaning: cleanMutation.isPending,
    clean: cleanMutation.mutateAsync,
    deleteDataset: deleteMutation.mutateAsync,
  };
}
