"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { NotificationService } from "../services/notification.service";

export function useNotifications() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["settings", "notifications"],
    queryFn: NotificationService.getNotifications,
    staleTime: 30 * 1000,
  });

  const markReadMutation = useMutation({
    mutationFn: NotificationService.markAllRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "notifications"] });
    },
  });

  return {
    notifications: query.data || [],
    isLoading: query.isLoading,
    markAllRead: markReadMutation.mutateAsync,
    isMarkingRead: markReadMutation.isPending,
  };
}
