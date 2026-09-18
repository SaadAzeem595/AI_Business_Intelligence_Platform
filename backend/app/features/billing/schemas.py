from typing import Optional, Dict
from datetime import datetime
from pydantic import BaseModel, Field


class CheckoutRequest(BaseModel):
    plan: str = Field(default="growth", description="Target subscription plan (e.g. growth)")
    return_url: Optional[str] = Field(default=None, description="Optional custom return base URL")


class CheckoutResponse(BaseModel):
    checkout_url: str = Field(..., description="Stripe hosted checkout session redirect URL")


class PortalRequest(BaseModel):
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
