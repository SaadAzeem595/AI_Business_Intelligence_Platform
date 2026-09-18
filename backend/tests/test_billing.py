import json
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.core.database import AsyncSessionLocal
from app.features.billing.models import WorkspaceSubscription, StripeProcessedEvent
from app.features.billing.entitlements import (
    EntitlementService,
    PLAN_STARTER,
    PLAN_GROWTH,
    STATUS_ACTIVE,
    STATUS_CANCELED,
)
from app.features.billing.exceptions import (
    EntitlementDeniedException,
    DatasetLimitReachedException,
)
from app.features.billing.stripe_service import StripeService


@pytest.mark.anyio
async def test_billing_entitlements_defaults():
    """Verify default workspace subscription and feature gating."""
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-entitlements-default"
        plan = await EntitlementService.get_workspace_plan(db, ws_id)
        assert plan == PLAN_STARTER

        # Basic features enabled
        assert await EntitlementService.has_feature(db, ws_id, "basic_sql") is True
        assert await EntitlementService.has_feature(db, ws_id, "standard_ai_chat") is True

        # Growth tier features disabled on Starter
        assert await EntitlementService.has_feature(db, ws_id, "advanced_forecasting") is False
        assert await EntitlementService.has_feature(db, ws_id, "advanced_anomaly_detection") is False
        assert await EntitlementService.has_feature(db, ws_id, "scheduled_reports") is False
        assert await EntitlementService.has_feature(db, ws_id, "shared_collaboration") is False

        # Entitlement denial raises structured exception
        with pytest.raises(EntitlementDeniedException) as exc_info:
            await EntitlementService.check_feature_entitlement(
                db, ws_id, "advanced_forecasting"
            )
        assert exc_info.value.code == "FEATURE_NOT_AVAILABLE"
        assert exc_info.value.feature == "advanced_forecasting"
        assert exc_info.value.current_plan == PLAN_STARTER
        assert exc_info.value.required_plan == PLAN_GROWTH


@pytest.mark.anyio
async def test_billing_cancellation_grace_period():
    """Verify grace period when cancel_at_period_end is set."""
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-grace-period"
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.plan = PLAN_GROWTH
        sub.status = STATUS_ACTIVE
        sub.cancel_at_period_end = True
        # Period end in the future -> retain Growth access
        sub.current_period_end = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=7)
        await db.commit()

        effective_plan = await EntitlementService.get_workspace_plan(db, ws_id)
        assert effective_plan == PLAN_GROWTH
        assert await EntitlementService.has_feature(db, ws_id, "advanced_forecasting") is True

        # Period end in the past -> falls back to Starter
        sub.current_period_end = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
        await db.commit()

        effective_plan_expired = await EntitlementService.get_workspace_plan(db, ws_id)
        assert effective_plan_expired == PLAN_STARTER


@pytest.mark.anyio
async def test_webhook_checkout_and_idempotency():
    """Verify Stripe webhook elevates subscription to Growth and enforces idempotency."""
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-webhook-idempotent"
        evt_id = "evt_test_checkout_001"

        payload = {
            "id": evt_id,
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_test_12345",
                    "subscription": "sub_test_67890",
                    "metadata": {
                        "workspace_id": ws_id,
                        "plan": PLAN_GROWTH,
                    },
                }
            },
        }
        payload_bytes = json.dumps(payload).encode("utf-8")

        # 1. First event delivery
        res1 = await StripeService.handle_webhook(db, payload_bytes, sig_header=None)
        assert res1["status"] == "success"

        # Subscription should now be active Growth
        sub = await EntitlementService.get_workspace_subscription(db, ws_id)
        assert sub.plan == PLAN_GROWTH
        assert sub.status == STATUS_ACTIVE
        assert sub.stripe_customer_id == "cus_test_12345"
        assert sub.stripe_subscription_id == "sub_test_67890"

        # 2. Second event delivery (same event_id) -> Idempotency skips duplicate
        res2 = await StripeService.handle_webhook(db, payload_bytes, sig_header=None)
        assert res2["status"] == "success"
        assert res2["message"] == "Duplicate event skipped"


@pytest.mark.anyio
async def test_webhook_subscription_deleted():
    """Verify customer.subscription.deleted event drops plan back to Starter."""
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-deletion"
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.plan = PLAN_GROWTH
        sub.status = STATUS_ACTIVE
        sub.stripe_subscription_id = "sub_to_delete_999"
        await db.commit()

        del_payload = {
            "id": "evt_test_del_002",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_to_delete_999",
                    "metadata": {"workspace_id": ws_id},
                }
            },
        }
        await StripeService.handle_webhook(
            db, json.dumps(del_payload).encode("utf-8"), sig_header=None
        )

        sub_refreshed = await EntitlementService.get_workspace_subscription(db, ws_id)
        assert sub_refreshed.plan == PLAN_STARTER
        assert sub_refreshed.status == STATUS_CANCELED


def test_billing_api_endpoints():
    """Test /api/v1/billing API endpoints via TestClient."""
    client = TestClient(app)

    # 1. GET /api/v1/billing/subscription
    resp = client.get("/api/v1/billing/subscription")
    assert resp.status_code == 200
    data = resp.json()
    assert "plan" in data
    assert "status" in data

    # 2. GET /api/v1/billing/usage
    resp_usage = client.get("/api/v1/billing/usage")
    assert resp_usage.status_code == 200
    usage_data = resp_usage.json()
    assert "datasets" in usage_data
    assert "features" in usage_data
    assert "basic_sql" in usage_data["features"]

    # 3. POST /api/v1/billing/checkout
    resp_checkout = client.post(
        "/api/v1/billing/checkout",
        json={"plan": "growth"},
    )
    assert resp_checkout.status_code == 200
    checkout_data = resp_checkout.json()
    assert "checkout_url" in checkout_data


@pytest.mark.anyio
async def test_entitlement_gating_on_scheduled_reports():
    """Verify that scheduled report creation is blocked for Starter and allowed for Growth."""
    client = TestClient(app)

    async with AsyncSessionLocal() as db:
        # 1. On Starter: verify that check_feature_entitlement blocks scheduled_reports
        with pytest.raises(EntitlementDeniedException) as exc:
            await EntitlementService.check_feature_entitlement(
                db, "test-ws-gating", "scheduled_reports"
            )
        assert exc.value.code == "FEATURE_NOT_AVAILABLE"

        # 2. Upgrade to Growth
        sub = await EntitlementService.get_or_create_workspace_subscription(
            db, "test-ws-gating"
        )
        sub.plan = PLAN_GROWTH
        sub.status = STATUS_ACTIVE
        await db.commit()

        # Growth is now permitted
        assert (
            await EntitlementService.has_feature(
                db, "test-ws-gating", "scheduled_reports"
            )
            is True
        )


@pytest.mark.anyio
async def test_dataset_limit_enforcement():
    """Verify that Starter plan blocks dataset upload once limit of 1 is reached, and Growth allows unlimited."""
    from app.features.datasets.models import Dataset

    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-dataset-limits"
        # 1. On Starter with 0 datasets -> check passes
        await EntitlementService.check_dataset_limit(db, ws_id)

        # 2. Add 1 dataset
        ds1 = Dataset(
            id="test-ds-limit-01",
            filename="test1.csv",
            type="CSV",
            size="10 KB",
            rows=100,
            qualityScore=90,
            status="Active",
            date="2026-09-18",
            workspace_id=ws_id,
        )
        db.add(ds1)
        await db.commit()

        # 3. On Starter with 1 dataset -> check raises DatasetLimitReachedException
        with pytest.raises(DatasetLimitReachedException) as exc:
            await EntitlementService.check_dataset_limit(db, ws_id)
        assert exc.value.code == "PLAN_LIMIT_REACHED"
        assert exc.value.current == 1
        assert exc.value.limit == 1
        assert exc.value.required_plan == PLAN_GROWTH

        # 4. Upgrade workspace to Growth
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.plan = PLAN_GROWTH
        sub.status = STATUS_ACTIVE
        await db.commit()

        # 5. On Growth with 1 dataset -> check passes
        await EntitlementService.check_dataset_limit(db, ws_id)

        # 6. Add 2nd dataset -> check still passes (unlimited)
        ds2 = Dataset(
            id="test-ds-limit-02",
            filename="test2.csv",
            type="CSV",
            size="20 KB",
            rows=200,
            qualityScore=95,
            status="Active",
            date="2026-09-18",
            workspace_id=ws_id,
        )
        db.add(ds2)
        await db.commit()

        await EntitlementService.check_dataset_limit(db, ws_id)

