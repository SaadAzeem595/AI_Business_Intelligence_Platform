"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { BillingService } from "../services/billing.service";
import { CheckoutSessionRequest, PortalSessionRequest, PlanType } from "@/shared/types/billing";

export const BILLING_QUERY_KEYS = {
  SUBSCRIPTION: ["billing", "subscription"],
  USAGE: ["billing", "usage"],
};

export function useSubscription() {
  const queryClient = useQueryClient();

  const subscriptionQuery = useQuery({
    queryKey: BILLING_QUERY_KEYS.SUBSCRIPTION,
    queryFn: () => BillingService.getSubscription(),
    staleTime: 10 * 1000,
    retry: 1,
  });

  const usageQuery = useQuery({
    queryKey: BILLING_QUERY_KEYS.USAGE,
    queryFn: () => BillingService.getUsage(),
    staleTime: 10 * 1000,
    retry: 1,
  });

  const checkoutMutation = useMutation({
    mutationFn: (payload?: CheckoutSessionRequest) =>
      BillingService.createCheckoutSession(payload),
    onSuccess: (data) => {
      if (data?.checkout_url && typeof window !== "undefined") {
        window.location.href = data.checkout_url;
      }
    },
  });

  const portalMutation = useMutation({
    mutationFn: (payload?: PortalSessionRequest) =>
      BillingService.createPortalSession(payload),
    onSuccess: (data) => {
      if (data?.portal_url && typeof window !== "undefined") {
        window.location.href = data.portal_url;
      }
    },
  });

  const plan: PlanType = usageQuery.data?.plan || subscriptionQuery.data?.plan || "starter";
  const status = usageQuery.data?.status || subscriptionQuery.data?.status || "active";
  const isGrowthOrHigher = plan === "growth" || plan === "enterprise";
  const isGracePeriod = Boolean(subscriptionQuery.data?.cancel_at_period_end);

  const hasFeature = (featureName: string): boolean => {
    if (!usageQuery.data?.features) {
      // Fallback default for Starter plan while loading
      return ["basic_sql", "standard_ai_chat"].includes(featureName);
    }
    return Boolean(usageQuery.data.features[featureName]);
  };

  const datasetUsage = usageQuery.data?.datasets || {
    current: 0,
    limit: plan === "starter" ? 1 : null,
  };

  const isAtDatasetLimit =
    datasetUsage.limit !== null && datasetUsage.current >= datasetUsage.limit;

  const refetchAll = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: BILLING_QUERY_KEYS.SUBSCRIPTION }),
      queryClient.invalidateQueries({ queryKey: BILLING_QUERY_KEYS.USAGE }),
      queryClient.invalidateQueries({ queryKey: ["settings", "invoices"] }),
    ]);
    await Promise.all([
      subscriptionQuery.refetch(),
      usageQuery.refetch(),
    ]);
  };

  return {
    subscription: subscriptionQuery.data,
    usage: usageQuery.data,
    isLoading: subscriptionQuery.isLoading || usageQuery.isLoading,
    isError: subscriptionQuery.isError || usageQuery.isError,
    plan,
    status,
    isGrowthOrHigher,
    isGracePeriod,
    currentPeriodEnd: subscriptionQuery.data?.current_period_end,
    datasetUsage,
    isAtDatasetLimit,
    hasFeature,
    createCheckout: (req?: CheckoutSessionRequest) => checkoutMutation.mutateAsync(req),
    isCheckingOut: checkoutMutation.isPending,
    checkoutError: checkoutMutation.error,
    openPortal: (req?: PortalSessionRequest) => portalMutation.mutateAsync(req),
    isOpeningPortal: portalMutation.isPending,
    portalError: portalMutation.error,
    refetch: refetchAll,
  };
}
