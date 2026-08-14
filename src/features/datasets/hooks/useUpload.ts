"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DatasetService } from "../services/dataset.service";

export function useUpload(projectId?: string) {
  const queryClient = useQueryClient();
  const [progress, setProgress] = useState(0);

  const uploadMutation = useMutation({
    mutationFn: ({ file, tableName }: { file: File; tableName: string }) =>
      DatasetService.upload(file, tableName, projectId, (progressEvent) => {
        const percentCompleted = Math.round((progressEvent.loaded * 100) / (progressEvent.total || 1));
        setProgress(percentCompleted);
      }),
    onSuccess: () => {
      if (projectId) {
        queryClient.invalidateQueries({ queryKey: ["project-datasets", projectId] });
        queryClient.invalidateQueries({ queryKey: ["sql", "schema", projectId] });
      }
      queryClient.invalidateQueries({ queryKey: ["datasets", "list"] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      queryClient.invalidateQueries({ queryKey: ["sql", "schema"] });
      setProgress(0);
    },
    onError: () => {
      setProgress(0);
    },
  });

  return {
    upload: uploadMutation.mutateAsync,
    isUploading: uploadMutation.isPending,
    progress,
    error: uploadMutation.error,
  };
}
