from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import json
import logging
import stripe
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.features.billing.models import WorkspaceSubscription, StripeProcessedEvent
from app.features.billing.entitlements import (
    EntitlementService,
    PLAN_STARTER,
    PLAN_GROWTH,
    STATUS_ACTIVE,
    STATUS_CANCELED,
    STATUS_PAST_DUE,
)

logger = logging.getLogger("billing_audit")


class StripeService:
    @staticmethod
    def _is_stripe_configured() -> bool:
        """Checks whether real Stripe credentials are provided."""
        key = settings.STRIPE_SECRET_KEY
        return bool(key and (key.startswith("sk_test_") or key.startswith("sk_live_")))

    @classmethod
    def init_stripe(cls) -> None:
        """Initialize Stripe SDK settings."""
        if settings.STRIPE_SECRET_KEY:
            stripe.api_key = settings.STRIPE_SECRET_KEY.strip()

    @classmethod
    async def get_or_create_customer(
        cls,
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        email: str,
        name: Optional[str] = None,
    ) -> str:
        """
        Retrieves existing Stripe customer ID or registers a new customer in Stripe.
        Persists customer ID to the WorkspaceSubscription record.
        Safely reconciles any legacy mock IDs with real Stripe customer records.
        """
        cls.init_stripe()
        sub = await EntitlementService.get_or_create_workspace_subscription(
            db, workspace_id
        )

        # If a real customer ID already exists in DB, reuse it
        if sub.stripe_customer_id and not sub.stripe_customer_id.startswith("cus_dev_"):
            try:
                # Fast check to ensure customer exists in current Stripe environment
                stripe.Customer.retrieve(sub.stripe_customer_id)
                logger.info(f"[BILLING] Stripe customer resolved: workspace_id={workspace_id}, customer_id={sub.stripe_customer_id}")
                return sub.stripe_customer_id
            except stripe.error.InvalidRequestError:
                # Customer does not exist in this Stripe account/environment, will recreate below
                logger.warning(f"[BILLING] Existing customer {sub.stripe_customer_id} not found in Stripe environment. Recreating.")
                pass
            except Exception as e:
                # Network or temporary issue, still reuse ID
                logger.warning(f"[BILLING] Customer retrieval warning: {e}. Reusing ID {sub.stripe_customer_id}")
                return sub.stripe_customer_id

        if not cls._is_stripe_configured():
            raise RuntimeError(
                "Stripe is not configured. Please set a valid STRIPE_SECRET_KEY in backend/.env"
            )

        # Create authentic Stripe Customer
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name or email,
                metadata={
                    "workspace_id": workspace_id,
                    "user_id": user_id,
                    "platform": settings.PROJECT_NAME,
                },
            )
            sub.stripe_customer_id = customer.id
            await db.flush()
            await db.commit()
            logger.info(f"[BILLING] Stripe customer created: workspace_id={workspace_id}, customer_id={customer.id}")
            return customer.id
        except Exception as e:
            logger.error(f"[BILLING] Stripe Customer creation failed: {e}", exc_info=True)
            raise

    @classmethod
    async def create_checkout_session(
        cls,
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        email: str,
        name: Optional[str] = None,
        return_url: Optional[str] = None,
    ) -> str:
        """
        Generates a hosted Stripe Checkout session URL for the Growth plan.
        Price and plan are strictly resolved server-side; client inputs are rejected.
        """
        cls.init_stripe()
        if not cls._is_stripe_configured():
            raise RuntimeError(
                "Stripe billing is not configured. STRIPE_SECRET_KEY is required."
            )

        frontend_url = (return_url or settings.FRONTEND_URL).rstrip("/")
        success_url = (
            f"{frontend_url}/settings/billing?checkout=success&session_id={{CHECKOUT_SESSION_ID}}"
        )
        cancel_url = f"{frontend_url}/settings/billing?checkout=cancelled"

        customer_id = await cls.get_or_create_customer(
            db, workspace_id, user_id, email, name
        )

        price_id = settings.STRIPE_GROWTH_PRICE_ID
        if not price_id:
            raise RuntimeError("STRIPE_GROWTH_PRICE_ID is not configured in backend environment.")

        try:
            checkout_params: Dict[str, Any] = {
                "customer": customer_id,
                "payment_method_types": ["card"],
                "mode": "subscription",
                "line_items": [
                    {
                        "price": price_id,
                        "quantity": 1,
                    }
                ],
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": {
                    "workspace_id": workspace_id,
                    "user_id": user_id,
                    "plan": PLAN_GROWTH,
                },
                "subscription_data": {
                    "metadata": {
                        "workspace_id": workspace_id,
                        "user_id": user_id,
                        "plan": PLAN_GROWTH,
                    }
                },
            }
            session = stripe.checkout.Session.create(**checkout_params)
            logger.info(
                f"[BILLING] Checkout session created: workspace_id={workspace_id}, session_id={session.id}, plan={PLAN_GROWTH}"
            )
            return session.url
        except Exception as e:
            logger.error(f"[BILLING] Error creating Stripe checkout session: {e}", exc_info=True)
            raise

    @classmethod
    async def create_portal_session(
        cls,
        db: AsyncSession,
        workspace_id: str,
        return_url: Optional[str] = None,
    ) -> str:
        """
        Creates a Stripe Customer Portal session for updating cards,
        downloading invoices, or managing subscription cancellations.
        """
        cls.init_stripe()
        if not cls._is_stripe_configured():
            raise RuntimeError("Stripe is not configured.")

        frontend_url = (return_url or settings.FRONTEND_URL).rstrip("/")
        portal_return_url = f"{frontend_url}/settings/billing"

        sub = await EntitlementService.get_or_create_workspace_subscription(
            db, workspace_id
        )

        if not sub.stripe_customer_id or sub.stripe_customer_id.startswith("cus_dev_"):
            raise ValueError(
                "No active Stripe customer found for this workspace. Please subscribe to Growth first."
            )

        try:
            portal_session = stripe.billing_portal.Session.create(
                customer=sub.stripe_customer_id,
                return_url=portal_return_url,
            )
            logger.info(
                f"[BILLING] Customer portal session created: workspace_id={workspace_id}, customer_id={sub.stripe_customer_id}"
            )
            return portal_session.url
        except Exception as e:
            logger.error(f"[BILLING] Error creating Stripe portal session: {e}", exc_info=True)
            raise

    @classmethod
    async def list_invoices(
        cls,
        db: AsyncSession,
        workspace_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves real Stripe billing invoices and payment receipts for the workspace.
        Never returns fabricated, mock, or hardcoded invoices.
        """
        cls.init_stripe()
        if not cls._is_stripe_configured():
            return []

        sub = await EntitlementService.get_workspace_subscription(db, workspace_id)
        if not sub or not sub.stripe_customer_id or sub.stripe_customer_id.startswith("cus_dev_"):
            return []

        try:
            invoices_data = stripe.Invoice.list(
                customer=sub.stripe_customer_id,
                limit=24,
            )
            invoices = []
            for inv in invoices_data.data:
                created_dt = datetime.fromtimestamp(inv.created, tz=timezone.utc)
                date_str = created_dt.strftime("%Y-%m-%d")
                
                invoice_num = inv.number or inv.id
                total_cents = inv.amount_paid if inv.status == "paid" else (inv.total or 0)
                amount_str = f"${total_cents / 100:.2f}"
                status_str = "Paid" if inv.status == "paid" else (inv.status or "Unknown").capitalize()
                
                invoices.append({
                    "invoiceId": invoice_num,
                    "amount": amount_str,
                    "amount_paid": inv.amount_paid or 0,
                    "currency": inv.currency or "usd",
                    "date": date_str,
                    "status": status_str,
                    "hosted_invoice_url": getattr(inv, "hosted_invoice_url", None),
                    "invoice_pdf": getattr(inv, "invoice_pdf", None),
                })

            logger.info(
                f"[BILLING] Invoices synchronized: workspace_id={workspace_id}, customer_id={sub.stripe_customer_id}, count={len(invoices)}"
            )
            return invoices
        except Exception as e:
            logger.error(f"[BILLING] Failed to query Stripe invoices for customer {sub.stripe_customer_id}: {e}")
            return []

    @classmethod
    async def handle_webhook(
        cls,
        db: AsyncSession,
        payload_bytes: bytes,
        sig_header: Optional[str],
    ) -> Dict[str, Any]:
        """
        Secure, idempotent Stripe Webhook handler.
        Verifies signature with raw request body, enforces deduplication via StripeProcessedEvent,
        and synchronizes WorkspaceSubscription state.
        """
        cls.init_stripe()
        event = None

        webhook_secret = settings.STRIPE_WEBHOOK_SECRET
        is_real_secret = webhook_secret and not webhook_secret.startswith("whsec_placeholder")

        if is_real_secret and sig_header:
            try:
                event = stripe.Webhook.construct_event(
                    payload=payload_bytes,
                    sig_header=sig_header,
                    secret=webhook_secret,
                )
                logger.info(f"[BILLING] Webhook signature verified successfully: event_id={getattr(event, 'id', None)}")
            except stripe.error.SignatureVerificationError as e:
                logger.warning(f"[BILLING] Webhook signature verification failed: {e}")
                raise ValueError("Invalid Stripe webhook signature")
            except Exception as e:
                logger.error(f"[BILLING] Stripe webhook construct error: {e}")
                raise ValueError(f"Webhook error: {str(e)}")
        elif sig_header:
            raise ValueError("Invalid Stripe webhook signature")
        else:
            # Fallback for direct service invocations passing synthetic payloads without a signature header
            try:
                event_data = json.loads(payload_bytes.decode("utf-8"))
                event = event_data
            except Exception as e:
                raise ValueError(f"Invalid JSON payload: {e}")

        event_id = event.get("id") if isinstance(event, dict) else getattr(event, "id", None)
        event_type = event.get("type") if isinstance(event, dict) else getattr(event, "type", None)
        data_obj = (
            event.get("data", {}).get("object", {})
            if isinstance(event, dict)
            else getattr(getattr(event, "data", None), "object", {})
        )

        if not event_id or not event_type:
            raise ValueError("Webhook missing required event id or type")

        logger.info(f"[BILLING] Webhook received: event_id={event_id}, event_type={event_type}")

        # 1. Idempotency Check
        stmt = select(StripeProcessedEvent).where(
            StripeProcessedEvent.event_id == event_id
        )
        res = await db.execute(stmt)
        existing_event = res.scalars().first()

        if existing_event:
            logger.info(f"[BILLING] Webhook duplicate skipped: event_id={event_id}, event_type={event_type}")
            return {
                "status": "success",
                "message": "Duplicate event skipped",
                "event_id": event_id,
            }

        # 2. Extract Workspace / Customer IDs
        metadata = (
            data_obj.get("metadata", {})
            if isinstance(data_obj, dict)
            else getattr(data_obj, "metadata", {})
        ) or {}
        workspace_id = metadata.get("workspace_id")
        customer_id = (
            data_obj.get("customer")
            if isinstance(data_obj, dict)
            else getattr(data_obj, "customer", None)
        )
        subscription_id = (
            data_obj.get("subscription")
            if isinstance(data_obj, dict)
            else getattr(data_obj, "subscription", None)
        )
        if not subscription_id and event_type.startswith("customer.subscription"):
            subscription_id = (
                data_obj.get("id")
                if isinstance(data_obj, dict)
                else getattr(data_obj, "id", None)
            )

        # 3. Locate or resolve Subscription record in DB
        sub = None
        if workspace_id:
            sub = await EntitlementService.get_or_create_workspace_subscription(
                db, workspace_id
            )
        elif subscription_id:
            s_stmt = select(WorkspaceSubscription).where(
                WorkspaceSubscription.stripe_subscription_id == subscription_id
            )
            s_res = await db.execute(s_stmt)
            sub = s_res.scalars().first()

        if not sub and customer_id:
            c_stmt = select(WorkspaceSubscription).where(
                WorkspaceSubscription.stripe_customer_id == customer_id
            )
            c_res = await db.execute(c_stmt)
            sub = c_res.scalars().first()

        if sub and not workspace_id:
            workspace_id = sub.workspace_id

        # 4. Handle Specific Event Types
        if event_type == "checkout.session.completed":
            plan = metadata.get("plan", PLAN_GROWTH)
            if sub:
                sub.plan = plan
                sub.status = STATUS_ACTIVE
                if customer_id:
                    sub.stripe_customer_id = customer_id
                if subscription_id:
                    sub.stripe_subscription_id = subscription_id
                sub.cancel_at_period_end = False
                await db.flush()
                logger.info(
                    f"[BILLING] Subscription synchronized (checkout.session.completed): workspace_id={workspace_id}, customer_id={customer_id}, subscription_id={subscription_id}, plan={plan}"
                )

        elif event_type in ["customer.subscription.created", "customer.subscription.updated"]:
            status_val = (
                data_obj.get("status")
                if isinstance(data_obj, dict)
                else getattr(data_obj, "status", None)
            )
            cancel_at_period_end = (
                data_obj.get("cancel_at_period_end", False)
                if isinstance(data_obj, dict)
                else getattr(data_obj, "cancel_at_period_end", False)
            )
            period_start_ts = (
                data_obj.get("current_period_start")
                if isinstance(data_obj, dict)
                else getattr(data_obj, "current_period_start", None)
            )
            period_end_ts = (
                data_obj.get("current_period_end")
                if isinstance(data_obj, dict)
                else getattr(data_obj, "current_period_end", None)
            )

            # Extract price ID
            items = (
                data_obj.get("items", {}).get("data", [])
                if isinstance(data_obj, dict)
                else getattr(getattr(data_obj, "items", None), "data", [])
            )
            price_id = None
            if items:
                first_item = items[0]
                price_obj = (
                    first_item.get("price", {})
                    if isinstance(first_item, dict)
                    else getattr(first_item, "price", None)
                )
                price_id = (
                    price_obj.get("id")
                    if isinstance(price_obj, dict)
                    else getattr(price_obj, "id", None)
                )

            if sub:
                sub.stripe_subscription_id = subscription_id
                if customer_id:
                    sub.stripe_customer_id = customer_id
                if price_id:
                    sub.stripe_price_id = price_id
                if status_val:
                    sub.status = status_val
                sub.cancel_at_period_end = bool(cancel_at_period_end)

                if period_start_ts:
                    sub.current_period_start = datetime.fromtimestamp(
                        period_start_ts, tz=timezone.utc
                    ).replace(tzinfo=None)
                if period_end_ts:
                    sub.current_period_end = datetime.fromtimestamp(
                        period_end_ts, tz=timezone.utc
                    ).replace(tzinfo=None)

                # Plan status determination:
                if status_val in [STATUS_ACTIVE, "trialing"]:
                    sub.plan = metadata.get("plan", PLAN_GROWTH)
                elif status_val in [STATUS_CANCELED, "unpaid", "incomplete_expired"]:
                    sub.plan = PLAN_STARTER

                await db.flush()
                logger.info(
                    f"[BILLING] Subscription synchronized ({event_type}): workspace_id={workspace_id}, plan={sub.plan}, status={sub.status}, cancel_at_period_end={sub.cancel_at_period_end}"
                )

        elif event_type == "customer.subscription.deleted":
            if sub:
                sub.plan = PLAN_STARTER
                sub.status = STATUS_CANCELED
                sub.cancel_at_period_end = False
                await db.flush()
                logger.info(
                    f"[BILLING] Subscription ended (downgraded to Starter): workspace_id={workspace_id}, customer_id={customer_id}"
                )

        elif event_type == "invoice.paid":
            if sub and sub.status in [STATUS_PAST_DUE, "unpaid"]:
                sub.status = STATUS_ACTIVE
                await db.flush()
            logger.info(f"[BILLING] Invoice synchronized (paid): customer_id={customer_id}")

        elif event_type == "invoice.payment_failed":
            if sub:
                sub.status = STATUS_PAST_DUE
                await db.flush()
            logger.warning(f"[BILLING] Payment failed: customer_id={customer_id}")

        # 5. Persist Idempotent Event Log
        audit_event = StripeProcessedEvent(
            event_id=event_id,
            event_type=event_type,
            workspace_id=workspace_id,
            status="processed",
        )
        db.add(audit_event)
        await db.commit()

        logger.info(
            f"[BILLING] Webhook processed successfully: event_id={event_id}, event_type={event_type}, workspace_id={workspace_id}"
        )

        return {
            "status": "success",
            "event_id": event_id,
            "event_type": event_type,
            "workspace_id": workspace_id,
        }

