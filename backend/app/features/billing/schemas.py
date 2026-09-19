from typing import Optional, Dict, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: str = Field(default="growth", description="Target subscription plan (e.g. growth)")
    return_url: Optional[str] = Field(default=None, description="Optional custom return base URL")

    @field_validator("plan")
    @classmethod
    def validate_plan(cls, v: str) -> str:
        allowed = ["growth"]
        if v.lower() not in allowed:
            raise ValueError(f"Invalid plan requested: '{v}'. Only {allowed} are available for checkout.")
        return v.lower()


class CheckoutResponse(BaseModel):
    checkout_url: str = Field(..., description="Stripe hosted checkout session redirect URL")


class PortalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    return_url: Optional[str] = Field(default=None, description="Optional custom return base URL")


class PortalResponse(BaseModel):
    portal_url: str = Field(..., description="Stripe Customer Portal redirect URL")


class SubscriptionResponse(BaseModel):
    plan: str
    status: str
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    entitlements: Optional[Dict[str, bool]] = None


class UsageDatasets(BaseModel):
    current: int
    limit: Optional[int] = None


class UsageResponse(BaseModel):
    plan: str
    status: str
    cancel_at_period_end: bool = False
    current_period_end: Optional[datetime] = None
    datasets: UsageDatasets
    features: Dict[str, bool]


class InvoiceResponse(BaseModel):
    invoiceId: str = Field(..., description="Display invoice identifier (e.g. Stripe invoice number or ID)")
    amount: str = Field(..., description="Formatted payment amount (e.g. $79.00)")
    amount_paid: int = Field(default=0, description="Amount paid in smallest currency unit (cents)")
    currency: str = Field(default="usd", description="Currency ISO code")
    date: str = Field(..., description="Billing invoice date (YYYY-MM-DD)")
    status: str = Field(..., description="Payment status: Paid, Open, Draft, etc.")
    hosted_invoice_url: Optional[str] = Field(default=None, description="Direct link to Stripe-hosted invoice receipt")
    invoice_pdf: Optional[str] = Field(default=None, description="Direct download link to Stripe invoice PDF")
