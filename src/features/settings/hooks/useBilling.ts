"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BillingService } from "../services/billing.service";
import { BillingInput, WorkspaceInput, ProfileInput } from "../schemas/settings.schema";

export function useBilling() {
  const queryClient = useQueryClient();

  const invoicesQuery = useQuery({
    queryKey: ["settings", "invoices"],
    queryFn: BillingService.getInvoices,
    staleTime: 10 * 60 * 1000,
  });

  const updateBillingMutation = useMutation({
    mutationFn: (data: BillingInput) => BillingService.updateBilling(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "invoices"] });
    },
  });

  return {
    invoices: invoicesQuery.data || [],
    isLoadingInvoices: invoicesQuery.isLoading,
    updateBilling: updateBillingMutation.mutateAsync,
    isUpdatingBilling: updateBillingMutation.isPending,
  };
}

export function useWorkspaceSettings() {
  const queryClient = useQueryClient();

  const teamQuery = useQuery({
    queryKey: ["settings", "team"],
    queryFn: BillingService.getTeam,
    staleTime: 5 * 60 * 1000,
  });

  const apiKeysQuery = useQuery({
    queryKey: ["settings", "apiKeys"],
    queryFn: BillingService.getApiKeys,
    staleTime: 5 * 60 * 1000,
  });

  const updateProfileMutation = useMutation({
    mutationFn: (data: ProfileInput) => BillingService.updateProfile(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
    },
  });

  const updateWorkspaceMutation = useMutation({
    mutationFn: (data: WorkspaceInput) => BillingService.updateWorkspace(data),
  });

  return {
    team: teamQuery.data || [],
    isLoadingTeam: teamQuery.isLoading,
    apiKeys: apiKeysQuery.data || [],
    isLoadingApiKeys: apiKeysQuery.isLoading,
    updateProfile: updateProfileMutation.mutateAsync,
    isUpdatingProfile: updateProfileMutation.isPending,
    updateWorkspace: updateWorkspaceMutation.mutateAsync,
    isUpdatingWorkspace: updateWorkspaceMutation.isPending,
  };
}
