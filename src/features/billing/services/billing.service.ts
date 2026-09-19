import { apiClient } from "@/shared/api/client";
import { API_ENDPOINTS } from "@/shared/api/endpoints";
import {
  SubscriptionData,
  UsageData,
  CheckoutSessionRequest,
  CheckoutSessionResponse,
  PortalSessionRequest,
  PortalSessionResponse,
  Invoice,
} from "@/shared/types/billing";

export const BillingService = {
  /**
   * Retrieves current workspace subscription details, plan, and status.
   */
  async getSubscription(): Promise<SubscriptionData> {
    const response = await apiClient.get<SubscriptionData>(
      API_ENDPOINTS.BILLING.SUBSCRIPTION
    );
    return response.data;
  },

  /**
   * Triggers authoritative synchronization against Stripe to reconcile subscription status.
   */
  async syncSubscription(): Promise<SubscriptionData> {
    const response = await apiClient.post<SubscriptionData>(
      API_ENDPOINTS.BILLING.SYNC
    );
    return response.data;
  },

  /**
   * Retrieves real-time dataset usage, quota limits, and feature entitlements.
   */
  async getUsage(): Promise<UsageData> {
    const response = await apiClient.get<UsageData>(
      API_ENDPOINTS.BILLING.USAGE
    );
    return response.data;
  },

  /**
   * Retrieves authentic past billing history invoices from Stripe.
   * Returns empty array if no invoices exist; never returns fake data.
   */
  async getInvoices(): Promise<Invoice[]> {
    try {
      const response = await apiClient.get<Invoice[]>(
        API_ENDPOINTS.BILLING.INVOICES
      );
      return response.data || [];
    } catch {
      return [];
    }
  },

  /**
   * Generates a hosted Stripe Checkout session URL for upgrading to Growth.
   */
  async createCheckoutSession(
    payload?: CheckoutSessionRequest
  ): Promise<CheckoutSessionResponse> {
    const response = await apiClient.post<CheckoutSessionResponse>(
      API_ENDPOINTS.BILLING.CHECKOUT,
      payload || { plan: "growth" }
    );
    return response.data;
  },

  /**
   * Generates a Stripe Customer Portal link to manage cards, billing, and cancellations.
   */
  async createPortalSession(
    payload?: PortalSessionRequest
  ): Promise<PortalSessionResponse> {
    const response = await apiClient.post<PortalSessionResponse>(
      API_ENDPOINTS.BILLING.PORTAL,
      payload || {}
    );
    return response.data;
  },
};
