from typing import Optional
import logging
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import get_current_user, MockUser
from app.features.billing.schemas import (
    CheckoutRequest,
    CheckoutResponse,
    PortalRequest,
    PortalResponse,
    SubscriptionResponse,
    UsageResponse,
)
from app.features.billing.entitlements import EntitlementService
from app.features.billing.stripe_service import StripeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["Billing & Subscriptions"])


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SubscriptionResponse:
    """Returns active subscription state and metadata for the current user's workspace."""
    sub = await EntitlementService.get_or_create_workspace_subscription(
        db, current_user.workspace_id
    )
    effective_plan = await EntitlementService.get_workspace_plan(
        db, current_user.workspace_id
    )
    return SubscriptionResponse(
        plan=effective_plan,
        status=sub.status,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        cancel_at_period_end=sub.cancel_at_period_end,
        stripe_customer_id=sub.stripe_customer_id,
        stripe_subscription_id=sub.stripe_subscription_id,
    )


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> UsageResponse:
    """Returns dataset capacity usage and feature entitlements for the workspace."""
    usage_data = await EntitlementService.get_workspace_usage(
        db, current_user.workspace_id
    )
    return UsageResponse(**usage_data)


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    payload: CheckoutRequest,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> CheckoutResponse:
    """Generates a secure hosted Stripe Checkout session for upgrading to Growth."""
    try:
        url = await StripeService.create_checkout_session(
            db=db,
            workspace_id=current_user.workspace_id,
            user_id=current_user.id,
            email=current_user.email,
            name=current_user.name,
            return_url=payload.return_url,
        )
        return CheckoutResponse(checkout_url=url)
    except Exception as e:
        logger.error(f"Checkout creation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to initialize Stripe checkout session: {str(e)}",
        )


@router.post("/portal", response_model=PortalResponse)
async def create_portal(
    payload: PortalRequest,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> PortalResponse:
    """Generates a Stripe Customer Portal session link for subscription management."""
    try:
        url = await StripeService.create_portal_session(
            db=db,
            workspace_id=current_user.workspace_id,
            return_url=payload.return_url,
        )
        return PortalResponse(portal_url=url)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as e:
        logger.error(f"Portal session creation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to open Stripe customer portal: {str(e)}",
        )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="stripe-signature"),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Production-grade, idempotent Stripe webhook endpoint.
    Processes signature-verified lifecycle events from Stripe.
    """
    payload_bytes = await request.body()
    try:
        result = await StripeService.handle_webhook(
            db=db,
            payload_bytes=payload_bytes,
            sig_header=stripe_signature,
        )
        return result
    except ValueError as e:
        logger.warning(f"Stripe webhook validation failure: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Stripe webhook internal processing error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook handler failure",
        )
