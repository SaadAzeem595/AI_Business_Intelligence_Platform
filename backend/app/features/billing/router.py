from typing import Optional, List
import logging
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db_session
from app.core.dependencies import get_current_user, MockUser
from app.features.billing.schemas import (
    CheckoutRequest,
    CheckoutResponse,
    PortalRequest,
    PortalResponse,
    SubscriptionResponse,
    UsageResponse,
    InvoiceResponse,
)
from app.features.billing.entitlements import EntitlementService
from app.features.billing.stripe_service import StripeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["Billing & Subscriptions"])


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    sync: bool = False,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SubscriptionResponse:
    """Returns active subscription state and metadata for the current user's workspace."""
    sub = await EntitlementService.get_or_create_workspace_subscription(
        db, current_user.workspace_id
    )

    # Reconcile if sync requested or if customer exists but subscription is unlinked or still starter
    if sub.stripe_customer_id and not sub.stripe_customer_id.startswith("cus_dev_"):
        if sync or sub.stripe_subscription_id is None or sub.plan == "starter":
            updated_sub = await StripeService.sync_subscription_from_stripe(
                db, current_user.workspace_id
            )
            if updated_sub:
                sub = updated_sub

    effective_plan = await EntitlementService.get_workspace_plan(
        db, current_user.workspace_id
    )
    entitlements = await EntitlementService.get_workspace_entitlements(
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
        entitlements=entitlements,
    )


@router.post("/sync", response_model=SubscriptionResponse)
async def sync_subscription(
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SubscriptionResponse:
    """Explicitly triggers synchronization against Stripe to reconcile subscription status."""
    await StripeService.sync_subscription_from_stripe(db, current_user.workspace_id)
    return await get_subscription(sync=False, current_user=current_user, db=db)


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


@router.get("/invoices", response_model=List[InvoiceResponse])
async def get_invoices(
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> List[InvoiceResponse]:
    """
    Returns authentic past billing history invoices from Stripe.
    Workspace isolation strictly enforced; never returns mock invoices.
    """
    invoices = await StripeService.list_invoices(db, current_user.workspace_id)
    return [InvoiceResponse(**inv) for inv in invoices]


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
    payload: Optional[PortalRequest] = None,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> PortalResponse:
    """Generates a Stripe Customer Portal session link for subscription management."""
    return_url = payload.return_url if payload else None
    try:
        url = await StripeService.create_portal_session(
            db=db,
            workspace_id=current_user.workspace_id,
            return_url=return_url,
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
    if not stripe_signature and settings.STRIPE_WEBHOOK_SECRET and not settings.STRIPE_WEBHOOK_SECRET.startswith("whsec_placeholder"):
        logger.warning("[BILLING] Webhook HTTP request received without stripe-signature header")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing stripe-signature header",
        )

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

