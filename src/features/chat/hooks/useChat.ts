"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChatService, ChatMessagePayload } from "../services/chat.service";

export function useChat() {
  const queryClient = useQueryClient();

  const sessionsQuery = useQuery({
    queryKey: ["chat", "sessions"],
    queryFn: ChatService.getSessions,
    staleTime: 5 * 60 * 1000,
  });

  const sendMessageMutation = useMutation({
    mutationFn: (payload: ChatMessagePayload) => ChatService.sendMessage(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat", "sessions"] });
    },
  });

  return {
    sessions: sessionsQuery.data || [],
    isLoadingSessions: sessionsQuery.isLoading,
    sendMessage: sendMessageMutation.mutateAsync,
    isSending: sendMessageMutation.isPending,
    response: sendMessageMutation.data || null,
  };
}
