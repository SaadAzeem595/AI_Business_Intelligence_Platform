from typing import Optional, Dict, Any
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
        return bool(key and not key.startswith("sk_test_placeholder"))

    @classmethod
    def init_stripe(cls) -> None:
        """Initialize Stripe SDK settings."""
        if settings.STRIPE_SECRET_KEY:
            stripe.api_key = settings.STRIPE_SECRET_KEY

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
        """
        cls.init_stripe()
        sub = await EntitlementService.get_or_create_workspace_subscription(
            db, workspace_id
        )

        if sub.stripe_customer_id:
            return sub.stripe_customer_id

        if not cls._is_stripe_configured():
            # Mock / sandbox fallback for development without live keys
            mock_id = f"cus_dev_{workspace_id}_{user_id[:8] if user_id else '001'}"
            sub.stripe_customer_id = mock_id
            await db.flush()
            return mock_id

        # Live Stripe Customer Creation
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
            logger.info(
                json.dumps({
                    "event": "stripe_customer_created",
                    "workspace_id": workspace_id,
                    "stripe_customer_id": customer.id,
                })
            )
            return customer.id
        except Exception as e:
            logger.error(f"Stripe Customer creation error: {e}")
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
        """
        cls.init_stripe()
        frontend_url = (return_url or settings.FRONTEND_URL).rstrip("/")
        success_url = (
            f"{frontend_url}/settings/billing?checkout=success&session_id={{CHECKOUT_SESSION_ID}}"
        )
        cancel_url = f"{frontend_url}/settings/billing?checkout=cancelled"

        customer_id = await cls.get_or_create_customer(
            db, workspace_id, user_id, email, name
        )

        if not cls._is_stripe_configured():
            # Dev mock session checkout link
            mock_session_id = f"cs_dev_mock_{workspace_id}"
            return f"{frontend_url}/settings/billing?checkout=success&session_id={mock_session_id}&mock=true"

        price_id = settings.STRIPE_GROWTH_PRICE_ID
        if not price_id or price_id.startswith("price_growth_monthly"):
            # If a specific price ID is not created in Stripe dashboard yet, search or create
            try:
                prices = stripe.Price.list(active=True, limit=10)
                if prices.data:
                    price_id = prices.data[0].id
                else:
                    # Create placeholder product & price
                    prod = stripe.Product.create(name="DataPilot AI Growth Plan")
                    new_price = stripe.Price.create(
                        unit_amount=7900,
                        currency="usd",
                        recurring={"interval": "month"},
                        product=prod.id,
                    )
                    price_id = new_price.id
            except Exception as e:
                logger.warning(f"Unable to query/create stripe price automatically: {e}")

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
                json.dumps({
                    "event": "stripe_checkout_session_created",
                    "workspace_id": workspace_id,
                    "session_id": session.id,
                    "plan": PLAN_GROWTH,
                })
            )
            return session.url
        except Exception as e:
            logger.error(f"Error creating Stripe checkout session: {e}")
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
        frontend_url = (return_url or settings.FRONTEND_URL).rstrip("/")
        portal_return_url = f"{frontend_url}/settings/billing"

        sub = await EntitlementService.get_or_create_workspace_subscription(
            db, workspace_id
        )

        if not cls._is_stripe_configured():
            return f"{frontend_url}/settings/billing?portal=active_mock"

        if not sub.stripe_customer_id:
            raise ValueError(
                "No active Stripe customer found for this workspace. Please subscribe first."
            )

        try:
            portal_session = stripe.billing_portal.Session.create(
                customer=sub.stripe_customer_id,
                return_url=portal_return_url,
            )
            logger.info(
                json.dumps({
                    "event": "stripe_portal_session_created",
                    "workspace_id": workspace_id,
                    "customer_id": sub.stripe_customer_id,
                })
            )
            return portal_session.url
        except Exception as e:
            logger.error(f"Error creating Stripe portal session: {e}")
            raise

    @classmethod
    async def handle_webhook(
        cls,
        db: AsyncSession,
        payload_bytes: bytes,
        sig_header: Optional[str],
    ) -> Dict[str, Any]:
        """
        Secure, idempotent Stripe Webhook handler.
        Verifies signature, enforces deduplication via StripeProcessedEvent,
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
            except stripe.error.SignatureVerificationError as e:
                logger.warning(f"Stripe webhook signature verification failed: {e}")
                raise ValueError("Invalid Stripe webhook signature")
            except Exception as e:
                logger.error(f"Stripe webhook construct error: {e}")
                raise ValueError(f"Webhook error: {str(e)}")
        else:
            # Fallback for dev / mock testing
            try:
                event_data = json.loads(payload_bytes.decode("utf-8"))
                event = event_data
            except Exception as e:
                raise ValueError(f"Invalid JSON payload: {e}")

        event_id = event.get("id") if isinstance(event, dict) else event.id
        event_type = event.get("type") if isinstance(event, dict) else event.type
        data_obj = (
            event.get("data", {}).get("object", {})
            if isinstance(event, dict)
            else event.data.object
        )

        if not event_id:
            raise ValueError("Webhook missing event id")

        # 1. Idempotency Check
        stmt = select(StripeProcessedEvent).where(
            StripeProcessedEvent.event_id == event_id
        )
        res = await db.execute(stmt)
        existing_event = res.scalars().first()

        if existing_event:
            logger.info(
                json.dumps({
                    "event": "stripe_webhook_duplicate_skipped",
                    "event_id": event_id,
                    "event_type": event_type,
                })
            )
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

                # If subscription is active, ensure plan is set to Growth
                if status_val in [STATUS_ACTIVE, "trialing"]:
                    sub.plan = metadata.get("plan", sub.plan or PLAN_GROWTH)
                elif status_val in [STATUS_CANCELED, "unpaid", "incomplete_expired"]:
                    sub.plan = PLAN_STARTER

                await db.flush()

        elif event_type == "customer.subscription.deleted":
            if sub:
                sub.plan = PLAN_STARTER
                sub.status = STATUS_CANCELED
                sub.cancel_at_period_end = False
                await db.flush()

        elif event_type == "invoice.paid":
            if sub and sub.status in [STATUS_PAST_DUE, "unpaid"]:
                sub.status = STATUS_ACTIVE
                await db.flush()

        elif event_type == "invoice.payment_failed":
            if sub:
                sub.status = STATUS_PAST_DUE
                await db.flush()

        # 5. Persist Idempotent Event Log
        audit_event = StripeProcessedEvent(
            event_id=event_id,
            event_type=event_type,
            workspace_id=workspace_id,
        )
        db.add(audit_event)
        await db.commit()

        logger.info(
            json.dumps({
                "event": "stripe_webhook_processed",
                "event_id": event_id,
                "event_type": event_type,
                "workspace_id": workspace_id,
                "sub_plan": sub.plan if sub else None,
                "sub_status": sub.status if sub else None,
            })
        )

        return {
            "status": "success",
            "event_id": event_id,
            "event_type": event_type,
            "workspace_id": workspace_id,
        }
