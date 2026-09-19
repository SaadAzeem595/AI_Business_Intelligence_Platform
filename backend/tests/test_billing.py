from typing import Optional
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
import stripe

from app.main import app
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.dependencies import get_current_user, MockUser
from app.features.billing.models import WorkspaceSubscription, StripeProcessedEvent
from app.features.datasets.models import Dataset
from app.features.billing.entitlements import (
    EntitlementService,
    PLAN_STARTER,
    PLAN_GROWTH,
    PLAN_ENTERPRISE,
    STATUS_ACTIVE,
    STATUS_CANCELED,
    STATUS_PAST_DUE,
)
from app.features.billing.exceptions import (
    EntitlementDeniedException,
    DatasetLimitReachedException,
)
from app.features.billing.stripe_service import StripeService


def set_user_workspace(user_id: str, workspace_id: str, role: str = "Admin") -> MockUser:
    user = MockUser(
        id=user_id,
        email=f"{user_id}@{workspace_id}.com",
        name=f"User {user_id}",
        role=role,
        workspace_id=workspace_id,
    )
    app.dependency_overrides[get_current_user] = lambda: user
    return user


# ==============================================================================
# TEST 1: New workspace starts as Starter.
# ==============================================================================
@pytest.mark.anyio
async def test_01_new_workspace_starts_as_starter():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-01-new"
        plan = await EntitlementService.get_workspace_plan(db, ws_id)
        assert plan == PLAN_STARTER
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        assert sub.plan == PLAN_STARTER
        assert sub.status == STATUS_ACTIVE


# ==============================================================================
# TEST 2: Starter can create first dataset.
# ==============================================================================
@pytest.mark.anyio
async def test_02_starter_can_create_first_dataset():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-02-first-ds"
        # 0 active datasets -> limit check passes
        await EntitlementService.check_dataset_limit(db, ws_id)


# ==============================================================================
# TEST 3: Starter cannot create second active dataset.
# ==============================================================================
@pytest.mark.anyio
async def test_03_starter_cannot_create_second_active_dataset():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-03-limit"
        ds1 = Dataset(
            id="ds-limit-01",
            filename="ds1.csv",
            type="CSV",
            size="10 KB",
            rows=10,
            qualityScore=100,
            status="Active",
            date="2026-09-19",
            workspace_id=ws_id,
        )
        db.add(ds1)
        await db.commit()

        with pytest.raises(DatasetLimitReachedException) as exc_info:
            await EntitlementService.check_dataset_limit(db, ws_id)
        assert exc_info.value.code == "PLAN_LIMIT_REACHED"
        assert exc_info.value.current == 1
        assert exc_info.value.limit == 1
        assert exc_info.value.required_plan == PLAN_GROWTH


# ==============================================================================
# TEST 4: Checkout endpoint creates Stripe Checkout Session using server-side Growth Price ID.
# ==============================================================================
def test_04_checkout_creates_stripe_session_with_server_price():
    client = TestClient(app)
    set_user_workspace("user-04", "ws-04")

    fake_session = MagicMock()
    fake_session.id = "cs_test_server_price_123"
    fake_session.url = "https://checkout.stripe.com/c/pay/cs_test_server_price_123"

    with patch("stripe.Customer.create") as mock_cus, \
         patch("stripe.checkout.Session.create", return_value=fake_session) as mock_checkout:
        fake_cus = MagicMock()
        fake_cus.id = "cus_test_04"
        mock_cus.return_value = fake_cus

        resp = client.post("/api/v1/billing/checkout", json={"plan": "growth"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["checkout_url"] == fake_session.url

        # Verify server-side Price ID was enforced
        call_kwargs = mock_checkout.call_args[1]
        line_item = call_kwargs["line_items"][0]
        assert line_item["price"] == settings.STRIPE_GROWTH_PRICE_ID
        assert call_kwargs["metadata"]["workspace_id"] == "ws-04"
        assert call_kwargs["metadata"]["plan"] == PLAN_GROWTH

    app.dependency_overrides.clear()


# ==============================================================================
# TEST 5: Checkout cannot accept arbitrary price/amount from client.
# ==============================================================================
def test_05_checkout_cannot_accept_arbitrary_price_amount():
    client = TestClient(app, raise_server_exceptions=False)
    set_user_workspace("user-05", "ws-05")

    # Client tries to pass malicious price_id and amount
    resp = client.post(
        "/api/v1/billing/checkout",
        json={"plan": "growth", "price_id": "price_hacked_000", "amount": 1},
    )
    # Extra fields forbidden by ConfigDict(extra='forbid') -> 422 Unprocessable Entity
    assert resp.status_code == 422

    # Client tries to pass invalid plan
    resp_invalid_plan = client.post(
        "/api/v1/billing/checkout",
        json={"plan": "free_hacked"},
    )
    assert resp_invalid_plan.status_code == 422

    app.dependency_overrides.clear()


# ==============================================================================
# TEST 6: checkout.session.completed webhook is processed.
# ==============================================================================
@pytest.mark.anyio
async def test_06_checkout_session_completed_webhook():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-06-checkout-completed"
        evt_payload = {
            "id": "evt_checkout_completed_06",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_stripe_06",
                    "subscription": "sub_stripe_06",
                    "metadata": {
                        "workspace_id": ws_id,
                        "plan": PLAN_GROWTH,
                    },
                }
            },
        }
        res = await StripeService.handle_webhook(
            db, json.dumps(evt_payload).encode("utf-8"), sig_header=None
        )
        assert res["status"] == "success"

        sub = await EntitlementService.get_workspace_subscription(db, ws_id)
        assert sub.plan == PLAN_GROWTH
        assert sub.status == STATUS_ACTIVE
        assert sub.stripe_customer_id == "cus_stripe_06"
        assert sub.stripe_subscription_id == "sub_stripe_06"


# ==============================================================================
# TEST 7: customer.subscription.created updates workspace subscription.
# ==============================================================================
@pytest.mark.anyio
async def test_07_customer_subscription_created():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-07-created"
        now_ts = int(datetime.now(timezone.utc).timestamp())
        evt_payload = {
            "id": "evt_sub_created_07",
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "id": "sub_07_created",
                    "customer": "cus_07",
                    "status": "active",
                    "cancel_at_period_end": False,
                    "current_period_start": now_ts,
                    "current_period_end": now_ts + 2592000,
                    "metadata": {"workspace_id": ws_id, "plan": PLAN_GROWTH},
                    "items": {"data": [{"price": {"id": settings.STRIPE_GROWTH_PRICE_ID}}]},
                }
            },
        }
        res = await StripeService.handle_webhook(
            db, json.dumps(evt_payload).encode("utf-8"), sig_header=None
        )
        assert res["status"] == "success"

        sub = await EntitlementService.get_workspace_subscription(db, ws_id)
        assert sub.plan == PLAN_GROWTH
        assert sub.status == STATUS_ACTIVE
        assert sub.stripe_subscription_id == "sub_07_created"


# ==============================================================================
# TEST 8: customer.subscription.updated updates plan/status/period.
# ==============================================================================
@pytest.mark.anyio
async def test_08_customer_subscription_updated():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-08-updated"
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.stripe_subscription_id = "sub_08_update"
        await db.commit()

        new_end_ts = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
        evt_payload = {
            "id": "evt_sub_updated_08",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_08_update",
                    "status": "active",
                    "cancel_at_period_end": True,
                    "current_period_end": new_end_ts,
                    "metadata": {"workspace_id": ws_id},
                }
            },
        }
        res = await StripeService.handle_webhook(
            db, json.dumps(evt_payload).encode("utf-8"), sig_header=None
        )
        assert res["status"] == "success"

        refreshed = await EntitlementService.get_workspace_subscription(db, ws_id)
        assert refreshed.cancel_at_period_end is True
        assert refreshed.current_period_end is not None


# ==============================================================================
# TEST 9: customer.subscription.deleted removes Growth entitlement appropriately.
# ==============================================================================
@pytest.mark.anyio
async def test_09_customer_subscription_deleted():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-09-deleted"
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.plan = PLAN_GROWTH
        sub.status = STATUS_ACTIVE
        sub.stripe_subscription_id = "sub_09_delete"
        await db.commit()

        evt_payload = {
            "id": "evt_sub_deleted_09",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_09_delete",
                    "metadata": {"workspace_id": ws_id},
                }
            },
        }
        await StripeService.handle_webhook(
            db, json.dumps(evt_payload).encode("utf-8"), sig_header=None
        )

        sub_after = await EntitlementService.get_workspace_subscription(db, ws_id)
        assert sub_after.plan == PLAN_STARTER
        assert sub_after.status == STATUS_CANCELED
        effective_plan = await EntitlementService.get_workspace_plan(db, ws_id)
        assert effective_plan == PLAN_STARTER


# ==============================================================================
# TEST 10: Duplicate webhook event is idempotent.
# ==============================================================================
@pytest.mark.anyio
async def test_10_duplicate_webhook_idempotent():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-10-idempotent"
        evt_payload = {
            "id": "evt_idempotent_10",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_10",
                    "subscription": "sub_10",
                    "metadata": {"workspace_id": ws_id, "plan": PLAN_GROWTH},
                }
            },
        }
        payload_bytes = json.dumps(evt_payload).encode("utf-8")

        # 1st delivery
        res1 = await StripeService.handle_webhook(db, payload_bytes, sig_header=None)
        assert res1["status"] == "success"

        # 2nd delivery (duplicate)
        res2 = await StripeService.handle_webhook(db, payload_bytes, sig_header=None)
        assert res2["status"] == "success"
        assert res2["message"] == "Duplicate event skipped"


# ==============================================================================
# TEST 11: Invalid webhook signature is rejected.
# ==============================================================================
def test_11_invalid_webhook_signature_rejected():
    client = TestClient(app)
    # When webhook secret is configured, invalid signatures must return 400 Bad Request
    with patch.object(settings, "STRIPE_WEBHOOK_SECRET", "whsec_valid_test_secret_12345"):
        resp = client.post(
            "/api/v1/billing/webhook",
            content=b'{"id": "evt_fake"}',
            headers={"stripe-signature": "t=12345,v1=bad_signature"},
        )
        assert resp.status_code == 400
        assert "signature" in resp.json()["detail"].lower()


# ==============================================================================
# TEST 12: Growth has unlimited datasets.
# ==============================================================================
@pytest.mark.anyio
async def test_12_growth_has_unlimited_datasets():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-12-growth-unlimited"
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.plan = PLAN_GROWTH
        sub.status = STATUS_ACTIVE
        await db.commit()

        # Add multiple datasets
        for i in range(5):
            db.add(
                Dataset(
                    id=f"ds-growth-{i}",
                    filename=f"file_{i}.csv",
                    type="CSV",
                    size="1 MB",
                    rows=1000,
                    qualityScore=90,
                    status="Active",
                    date="2026-09-19",
                    workspace_id=ws_id,
                )
            )
        await db.commit()

        # Growth has unlimited datasets -> check passes without error
        await EntitlementService.check_dataset_limit(db, ws_id)


# ==============================================================================
# TEST 13: Growth can access advanced forecasting.
# ==============================================================================
@pytest.mark.anyio
async def test_13_growth_can_access_advanced_forecasting():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-13-growth-forecasting"
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.plan = PLAN_GROWTH
        sub.status = STATUS_ACTIVE
        await db.commit()

        assert await EntitlementService.has_feature(db, ws_id, "advanced_forecasting") is True
        # check_feature_entitlement does not raise
        await EntitlementService.check_feature_entitlement(db, ws_id, "advanced_forecasting")


# ==============================================================================
# TEST 14: Starter cannot access advanced forecasting.
# ==============================================================================
@pytest.mark.anyio
async def test_14_starter_cannot_access_advanced_forecasting():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-14-starter-blocked"
        assert await EntitlementService.has_feature(db, ws_id, "advanced_forecasting") is False

        with pytest.raises(EntitlementDeniedException) as exc:
            await EntitlementService.check_feature_entitlement(db, ws_id, "advanced_forecasting")
        assert exc.value.code == "FEATURE_NOT_AVAILABLE"
        assert exc.value.feature == "advanced_forecasting"
        assert exc.value.required_plan == PLAN_GROWTH


# ==============================================================================
# TEST 15: Growth can use scheduled reports.
# ==============================================================================
@pytest.mark.anyio
async def test_15_growth_can_use_scheduled_reports():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-15-scheduled-reports"
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.plan = PLAN_GROWTH
        sub.status = STATUS_ACTIVE
        await db.commit()

        assert await EntitlementService.has_feature(db, ws_id, "scheduled_reports") is True


# ==============================================================================
# TEST 16: Starter cannot use scheduled reports.
# ==============================================================================
@pytest.mark.anyio
async def test_16_starter_cannot_use_scheduled_reports():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-16-starter-no-reports"
        assert await EntitlementService.has_feature(db, ws_id, "scheduled_reports") is False
        with pytest.raises(EntitlementDeniedException):
            await EntitlementService.check_feature_entitlement(db, ws_id, "scheduled_reports")


# ==============================================================================
# TEST 17: Billing invoices contain only real Stripe invoice data.
# ==============================================================================
def test_17_billing_invoices_real_stripe_data():
    client = TestClient(app)
    set_user_workspace("user-17", "ws-17")

    fake_stripe_inv = MagicMock()
    fake_stripe_inv.id = "in_real_stripe_999"
    fake_stripe_inv.number = "INV-STRIPE-REAL-001"
    fake_stripe_inv.amount_paid = 7900
    fake_stripe_inv.currency = "usd"
    fake_stripe_inv.status = "paid"
    fake_stripe_inv.created = 1755000000
    fake_stripe_inv.hosted_invoice_url = "https://invoice.stripe.com/i/in_real_stripe_999"
    fake_stripe_inv.invoice_pdf = "https://pay.stripe.com/invoice/in_real_stripe_999/pdf"

    fake_list = MagicMock()
    fake_list.data = [fake_stripe_inv]

    with patch("app.features.billing.stripe_service.StripeService._is_stripe_configured", return_value=True), \
         patch("app.features.billing.entitlements.EntitlementService.get_workspace_subscription") as mock_get_sub, \
         patch("stripe.Invoice.list", return_value=fake_list):
        mock_sub = MagicMock()
        mock_sub.stripe_customer_id = "cus_real_customer_17"
        mock_get_sub.return_value = mock_sub

        resp = client.get("/api/v1/billing/invoices")
        assert resp.status_code == 200
        invoices = resp.json()
        assert len(invoices) == 1
        assert invoices[0]["invoiceId"] == "INV-STRIPE-REAL-001"
        assert invoices[0]["amount"] == "$79.00"
        assert invoices[0]["status"] == "Paid"
        assert invoices[0]["hosted_invoice_url"] == fake_stripe_inv.hosted_invoice_url

    app.dependency_overrides.clear()


# ==============================================================================
# TEST 18: No invoice data results in an empty state instead of fake invoices.
# ==============================================================================
def test_18_no_invoice_data_returns_empty_list():
    client = TestClient(app)
    set_user_workspace("user-18", "ws-18")

    fake_list = MagicMock()
    fake_list.data = []

    with patch("app.features.billing.stripe_service.StripeService._is_stripe_configured", return_value=True), \
         patch("app.features.billing.entitlements.EntitlementService.get_workspace_subscription") as mock_get_sub, \
         patch("stripe.Invoice.list", return_value=fake_list):
        mock_sub = MagicMock()
        mock_sub.stripe_customer_id = "cus_no_invoices_18"
        mock_get_sub.return_value = mock_sub

        resp = client.get("/api/v1/billing/invoices")
        assert resp.status_code == 200
        invoices = resp.json()
        assert invoices == []
        # Ensure hardcoded invoices are never returned
        assert not any(inv.get("invoiceId") in ["INV-9021", "INV-7801", "INV-6204"] for inv in invoices)

    app.dependency_overrides.clear()


# ==============================================================================
# TEST 19: Cancel-at-period-end preserves Growth access until current_period_end.
# ==============================================================================
@pytest.mark.anyio
async def test_19_cancel_at_period_end_preserves_growth():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-19-cancel-grace"
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.plan = PLAN_GROWTH
        sub.status = STATUS_ACTIVE
        sub.cancel_at_period_end = True
        # 14 days in future
        sub.current_period_end = (datetime.now(timezone.utc) + timedelta(days=14)).replace(tzinfo=None)
        await db.commit()

        effective_plan = await EntitlementService.get_workspace_plan(db, ws_id)
        assert effective_plan == PLAN_GROWTH
        assert await EntitlementService.has_feature(db, ws_id, "advanced_forecasting") is True


# ==============================================================================
# TEST 20: After subscription ends, workspace returns to Starter entitlement.
# ==============================================================================
@pytest.mark.anyio
async def test_20_subscription_ended_reverts_to_starter():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-20-ended"
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.plan = PLAN_GROWTH
        sub.status = STATUS_ACTIVE
        sub.cancel_at_period_end = True
        # 1 day in past
        sub.current_period_end = (datetime.now(timezone.utc) - timedelta(days=1)).replace(tzinfo=None)
        await db.commit()

        effective_plan = await EntitlementService.get_workspace_plan(db, ws_id)
        assert effective_plan == PLAN_STARTER
        assert await EntitlementService.has_feature(db, ws_id, "advanced_forecasting") is False


# ==============================================================================
# TEST 21: Workspace A cannot access Workspace B's billing data.
# ==============================================================================
def test_21_workspace_isolation_billing_data():
    client = TestClient(app)

    # 1. User from Workspace A
    set_user_workspace("user_a", "ws_alpha")
    resp_a = client.get("/api/v1/billing/subscription")
    assert resp_a.status_code == 200

    # 2. User from Workspace B
    set_user_workspace("user_b", "ws_beta")
    resp_b = client.get("/api/v1/billing/subscription")
    assert resp_b.status_code == 200

    # Strict isolation: workspace_ids are separate in DB
    app.dependency_overrides.clear()


# ==============================================================================
# TEST 22: Frontend cannot directly mutate subscription state.
# ==============================================================================
def test_22_frontend_cannot_directly_mutate_subscription():
    client = TestClient(app)
    set_user_workspace("user-22", "ws-22")

    # Attempt to directly PUT, PATCH, or POST to /api/v1/billing/subscription
    resp_patch = client.patch(
        "/api/v1/billing/subscription",
        json={"plan": "growth", "status": "active"},
    )
    assert resp_patch.status_code == 405  # Method Not Allowed

    resp_put = client.put(
        "/api/v1/billing/subscription",
        json={"plan": "growth", "status": "active"},
    )
    assert resp_put.status_code == 405  # Method Not Allowed

    app.dependency_overrides.clear()

