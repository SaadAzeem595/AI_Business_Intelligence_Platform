"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { RAGService, ContextResponse } from "../services/rag.service";

export function useRAGDocuments(projectId: string) {
  return useQuery({
    queryKey: ["rag", "documents", projectId],
    queryFn: () => RAGService.listDocuments(projectId),
    enabled: !!projectId,
    staleTime: 10 * 1000,
  });
}

export function useRAGIngest(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ file, author, tags }: { file: File; author?: string; tags?: string }) =>
      RAGService.ingestDocument(file, projectId, author, tags),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rag", "documents", projectId] });
    },
  });
}

export function useRAGDelete(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (docId: string) => RAGService.deleteDocument(docId, projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rag", "documents", projectId] });
    },
  });
}

export function useRAGReindex(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (docId: string) => RAGService.reindexDocument(docId, projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rag", "documents", projectId] });
    },
  });
}

export function useRAGSearch(projectId: string) {
  return useMutation({
    mutationFn: ({ query, limit, hybridAlpha }: { query: string; limit?: number; hybridAlpha?: number }): Promise<ContextResponse> =>
      RAGService.retrieveContext(query, projectId, limit, hybridAlpha),
  });
}
