export type PlanType = 'starter' | 'growth' | 'enterprise';

export type SubscriptionStatus =
  | 'trialing'
  | 'active'
  | 'past_due'
  | 'canceled'
  | 'incomplete'
  | 'incomplete_expired'
  | 'unpaid';

export interface SubscriptionData {
  plan: PlanType;
  status: SubscriptionStatus;
  current_period_start?: string | null;
  current_period_end?: string | null;
  cancel_at_period_end: boolean;
  stripe_customer_id?: string | null;
  stripe_subscription_id?: string | null;
}

export interface DatasetCapacity {
  current: number;
  limit: number | null; // null indicates unlimited
}

export interface UsageData {
  plan: PlanType;
  status: SubscriptionStatus;
  cancel_at_period_end: boolean;
  current_period_end?: string | null;
  datasets: DatasetCapacity;
  features: {
    basic_sql: boolean;
    standard_ai_chat: boolean;
    advanced_forecasting: boolean;
    advanced_anomaly_detection: boolean;
    scheduled_reports: boolean;
    shared_collaboration: boolean;
    custom_integrations: boolean;
    sso: boolean;
    audit_logging: boolean;
    dedicated_scaling: boolean;
    [key: string]: boolean;
  };
}

export interface CheckoutSessionRequest {
  plan?: PlanType;
  return_url?: string;
}

export interface CheckoutSessionResponse {
  checkout_url: string;
}

export interface PortalSessionRequest {
  return_url?: string;
}

export interface PortalSessionResponse {
  portal_url: string;
}

export interface BillingErrorResponse {
  error?: {
    code: string;
    message: string;
    module?: string;
    details?: Record<string, unknown>;
  };
  code?: string;
  detail?: string;
  feature?: string;
  current_plan?: string;
  required_plan?: string;
  current?: number;
  limit?: number;
}

export interface Invoice {
  invoiceId: string;
  amount: string;
  amount_paid?: number;
  currency?: string;
  date: string;
  status: string;
  hosted_invoice_url?: string | null;
  invoice_pdf?: string | null;
}
