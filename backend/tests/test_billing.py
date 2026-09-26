import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from unittest.mock import patch, MagicMock

import pytest
import httpx
from httpx import ASGITransport, AsyncClient

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
# TEST 1: Starter Entitlement
# ==============================================================================
@pytest.mark.anyio
async def test_01_starter_entitlement():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-01-starter-ent"
        plan = await EntitlementService.get_workspace_plan(db, ws_id)
        assert plan == PLAN_STARTER

        entitlements = await EntitlementService.get_workspace_entitlements(db, ws_id)
        assert entitlements["active_datasets"] == 1
        assert entitlements["basic_sql"] is True
        assert entitlements["standard_ai_chat"] is True
        assert entitlements["advanced_forecasting"] is False
        assert entitlements["advanced_anomaly_detection"] is False
        assert entitlements["scheduled_reports"] is False
        assert entitlements["team_collaboration"] is False


# ==============================================================================
# TEST 2: Growth Entitlement
# ==============================================================================
@pytest.mark.anyio
async def test_02_growth_entitlement():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-02-growth-ent"
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.plan = PLAN_GROWTH
        sub.status = STATUS_ACTIVE
        await db.commit()

        plan = await EntitlementService.get_workspace_plan(db, ws_id)
        assert plan == PLAN_GROWTH

        entitlements = await EntitlementService.get_workspace_entitlements(db, ws_id)
        assert entitlements["active_datasets"] == "unlimited"
        assert entitlements["basic_sql"] is True
        assert entitlements["standard_ai_chat"] is True
        assert entitlements["advanced_forecasting"] is True
        assert entitlements["advanced_anomaly_detection"] is True
        assert entitlements["scheduled_reports"] is True
        assert entitlements["team_collaboration"] is True


# ==============================================================================
# TEST 3: Enterprise Entitlement
# ==============================================================================
@pytest.mark.anyio
async def test_03_enterprise_entitlement():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-03-enterprise-ent"
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.plan = PLAN_ENTERPRISE
        sub.status = STATUS_ACTIVE
        await db.commit()

        plan = await EntitlementService.get_workspace_plan(db, ws_id)
        assert plan == PLAN_ENTERPRISE

        entitlements = await EntitlementService.get_workspace_entitlements(db, ws_id)
        assert entitlements["active_datasets"] == "unlimited"
        assert entitlements["advanced_forecasting"] is True
        assert entitlements["enterprise_integrations"] is True
        assert entitlements["sso_saml"] is True
        assert entitlements["advanced_auditing"] is True
        assert entitlements["dedicated_scaling"] is True


# ==============================================================================
# TEST 4: Subscription Lookup Endpoint
# ==============================================================================
@pytest.mark.anyio
async def test_04_subscription_lookup_endpoint():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-04-lookup"
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.plan = PLAN_GROWTH
        sub.status = STATUS_ACTIVE
        sub.stripe_subscription_id = "sub_stripe_lookup_04"
        sub.cancel_at_period_end = False
        await db.commit()

    set_user_workspace("user-04", ws_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/billing/subscription")
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == PLAN_GROWTH
        assert data["status"] == STATUS_ACTIVE
        assert data["stripe_subscription_id"] == "sub_stripe_lookup_04"
        assert data["cancel_at_period_end"] is False
        assert "entitlements" in data
        assert data["entitlements"]["advanced_forecasting"] is True
        assert data["entitlements"]["active_datasets"] == "unlimited"

    app.dependency_overrides.clear()


# ==============================================================================
# TEST 5: Workspace Subscription Isolation
# ==============================================================================
@pytest.mark.anyio
async def test_05_workspace_subscription_isolation():
    async with AsyncSessionLocal() as db:
        ws_a = "ws-isolation-a"
        ws_b = "ws-isolation-b"

        # Workspace A upgraded to Growth
        sub_a = await EntitlementService.get_or_create_workspace_subscription(db, ws_a)
        sub_a.plan = PLAN_GROWTH
        sub_a.status = STATUS_ACTIVE
        await db.commit()

        # Workspace B remains Starter
        sub_b = await EntitlementService.get_or_create_workspace_subscription(db, ws_b)
        assert sub_b.plan == PLAN_STARTER

        plan_a = await EntitlementService.get_workspace_plan(db, ws_a)
        plan_b = await EntitlementService.get_workspace_plan(db, ws_b)
        assert plan_a == PLAN_GROWTH
        assert plan_b == PLAN_STARTER

    # Verify through API context
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # User A
        set_user_workspace("user-iso-a", ws_a)
        resp_a = await ac.get("/api/v1/billing/subscription")
        assert resp_a.json()["plan"] == PLAN_GROWTH

        # User B
        set_user_workspace("user-iso-b", ws_b)
        resp_b = await ac.get("/api/v1/billing/subscription")
        assert resp_b.json()["plan"] == PLAN_STARTER

    app.dependency_overrides.clear()


# ==============================================================================
# TEST 6: Checkout Session Creation (Server-side price enforcement)
# ==============================================================================
@pytest.mark.anyio
async def test_06_checkout_session_creation():
    set_user_workspace("user-06", "ws-06")

    fake_session = MagicMock()
    fake_session.id = "cs_test_server_price_06"
    fake_session.url = "https://checkout.stripe.com/c/pay/cs_test_server_price_06"

    with patch("stripe.Customer.create") as mock_cus, \
         patch("stripe.checkout.Session.create", return_value=fake_session) as mock_checkout:
        fake_cus = MagicMock()
        fake_cus.id = "cus_test_06"
        mock_cus.return_value = fake_cus

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/api/v1/billing/checkout", json={"plan": "growth"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["checkout_url"] == fake_session.url

            call_kwargs = mock_checkout.call_args[1]
            line_item = call_kwargs["line_items"][0]
            # Server-side price ID must be enforced
            assert line_item["price"] == settings.STRIPE_GROWTH_PRICE_ID
            assert call_kwargs["metadata"]["workspace_id"] == "ws-06"
            assert call_kwargs["metadata"]["plan"] == PLAN_GROWTH

            # Malicious client tries arbitrary price_id and amount -> 422
            resp_bad = await ac.post(
                "/api/v1/billing/checkout",
                json={"plan": "growth", "price_id": "price_hacked_000", "amount": 1},
            )
            assert resp_bad.status_code == 422

    app.dependency_overrides.clear()


# ==============================================================================
# TEST 7: Webhook Signature Verification
# ==============================================================================
@pytest.mark.anyio
async def test_07_webhook_signature_verification():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch.object(settings, "STRIPE_WEBHOOK_SECRET", "whsec_valid_test_secret_12345"):
            resp = await ac.post(
                "/api/v1/billing/webhook",
                content=b'{"id": "evt_fake"}',
                headers={"stripe-signature": "t=12345,v1=bad_signature"},
            )
            assert resp.status_code == 400
            assert "signature" in resp.json()["detail"].lower()


# ==============================================================================
# TEST 8: Duplicate Webhook Handling (Idempotency)
# ==============================================================================
@pytest.mark.anyio
async def test_08_duplicate_webhook_handling():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-08-idempotent"
        evt_payload = {
            "id": "evt_idempotent_08",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_08",
                    "subscription": "sub_08",
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
# TEST 9: checkout.session.completed Webhook
# ==============================================================================
@pytest.mark.anyio
async def test_09_webhook_checkout_session_completed():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-09-checkout-completed"
        evt_payload = {
            "id": "evt_checkout_completed_09",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_stripe_09",
                    "subscription": "sub_stripe_09",
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
        assert sub.stripe_customer_id == "cus_stripe_09"
        assert sub.stripe_subscription_id == "sub_stripe_09"


# ==============================================================================
# TEST 10: customer.subscription.created Webhook
# ==============================================================================
@pytest.mark.anyio
async def test_10_webhook_subscription_created():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-10-created"
        now_ts = int(datetime.now(timezone.utc).timestamp())
        evt_payload = {
            "id": "evt_sub_created_10",
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "id": "sub_10_created",
                    "customer": "cus_10",
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
        assert sub.stripe_subscription_id == "sub_10_created"


# ==============================================================================
# TEST 11: customer.subscription.updated Webhook
# ==============================================================================
@pytest.mark.anyio
async def test_11_webhook_subscription_updated():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-11-updated"
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.stripe_subscription_id = "sub_11_update"
        await db.commit()

        new_end_ts = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
        evt_payload = {
            "id": "evt_sub_updated_11",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_11_update",
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
# TEST 12: customer.subscription.deleted Webhook
# ==============================================================================
@pytest.mark.anyio
async def test_12_webhook_subscription_deleted():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-12-deleted"
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.plan = PLAN_GROWTH
        sub.status = STATUS_ACTIVE
        sub.stripe_subscription_id = "sub_12_delete"
        await db.commit()

        evt_payload = {
            "id": "evt_sub_deleted_12",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_12_delete",
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
# TEST 13: invoice.paid Webhook
# ==============================================================================
@pytest.mark.anyio
async def test_13_webhook_invoice_paid():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-13-inv-paid"
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.stripe_subscription_id = "sub_13_inv"
        sub.plan = PLAN_GROWTH
        sub.status = STATUS_ACTIVE
        await db.commit()

        evt_payload = {
            "id": "evt_inv_paid_13",
            "type": "invoice.paid",
            "data": {
                "object": {
                    "id": "in_13_paid",
                    "subscription": "sub_13_inv",
                    "customer": "cus_13",
                    "amount_paid": 7900,
                    "currency": "usd",
                    "status": "paid",
                    "lines": {
                        "data": [{
                            "period": {
                                "start": int(datetime.now(timezone.utc).timestamp()),
                                "end": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
                            }
                        }]
                    },
                }
            },
        }
        res = await StripeService.handle_webhook(
            db, json.dumps(evt_payload).encode("utf-8"), sig_header=None
        )
        assert res["status"] == "success"

        sub_refreshed = await EntitlementService.get_workspace_subscription(db, ws_id)
        assert sub_refreshed.status == STATUS_ACTIVE
        assert sub_refreshed.plan == PLAN_GROWTH


# ==============================================================================
# TEST 14: invoice.payment_failed Webhook
# ==============================================================================
@pytest.mark.anyio
async def test_14_webhook_invoice_payment_failed():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-14-inv-failed"
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.stripe_subscription_id = "sub_14_inv_failed"
        sub.plan = PLAN_GROWTH
        sub.status = STATUS_ACTIVE
        await db.commit()

        evt_payload = {
            "id": "evt_inv_fail_14",
            "type": "invoice.payment_failed",
            "data": {
                "object": {
                    "id": "in_14_fail",
                    "subscription": "sub_14_inv_failed",
                    "customer": "cus_14",
                    "amount_due": 7900,
                    "status": "open",
                }
            },
        }
        res = await StripeService.handle_webhook(
            db, json.dumps(evt_payload).encode("utf-8"), sig_header=None
        )
        assert res["status"] == "success"

        sub_refreshed = await EntitlementService.get_workspace_subscription(db, ws_id)
        assert sub_refreshed.status == STATUS_PAST_DUE


# ==============================================================================
# TEST 15: Cancellation at Period End
# ==============================================================================
@pytest.mark.anyio
async def test_15_cancellation_at_period_end():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-15-grace-period"
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.plan = PLAN_GROWTH
        sub.status = STATUS_ACTIVE
        sub.cancel_at_period_end = True
        # Grace period active: 10 days in the future
        sub.current_period_end = (datetime.now(timezone.utc) + timedelta(days=10)).replace(tzinfo=None)
        await db.commit()

        # Growth remains active during grace period
        plan_grace = await EntitlementService.get_workspace_plan(db, ws_id)
        assert plan_grace == PLAN_GROWTH
        assert await EntitlementService.has_feature(db, ws_id, "advanced_forecasting") is True

        # Now simulate period has elapsed (1 day in past)
        sub.current_period_end = (datetime.now(timezone.utc) - timedelta(days=1)).replace(tzinfo=None)
        await db.commit()

        # Workspace now correctly reverts to Starter
        plan_expired = await EntitlementService.get_workspace_plan(db, ws_id)
        assert plan_expired == PLAN_STARTER
        assert await EntitlementService.has_feature(db, ws_id, "advanced_forecasting") is False


# ==============================================================================
# TEST 16: Dataset Limit Gate
# ==============================================================================
@pytest.mark.anyio
async def test_16_dataset_limit():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-16-ds-limit"
        # Starter: 0 datasets -> ok
        await EntitlementService.check_dataset_limit(db, ws_id)

        # Add 1 dataset (the limit for Starter)
        db.add(
            Dataset(
                id="ds-limit-01",
                filename="first.csv",
                type="CSV",
                size="10 KB",
                rows=10,
                qualityScore=100,
                status="Active",
                date="2026-09-19",
                workspace_id=ws_id,
            )
        )
        await db.commit()

        # Adding 2nd dataset must raise DatasetLimitReachedException
        with pytest.raises(DatasetLimitReachedException) as exc:
            await EntitlementService.check_dataset_limit(db, ws_id)
        assert exc.value.code == "PLAN_LIMIT_REACHED"
        assert exc.value.current == 1
        assert exc.value.limit == 1
        assert exc.value.required_plan == PLAN_GROWTH

        # Upgrade workspace to Growth
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.plan = PLAN_GROWTH
        sub.status = STATUS_ACTIVE
        await db.commit()

        # Now unlimited datasets are permitted
        await EntitlementService.check_dataset_limit(db, ws_id)


# ==============================================================================
# TEST 17: Advanced Forecasting Gate
# ==============================================================================
@pytest.mark.anyio
async def test_17_advanced_forecasting_gate():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-17-forecasting-gate"
        # Starter blocked
        assert await EntitlementService.has_feature(db, ws_id, "advanced_forecasting") is False
        with pytest.raises(EntitlementDeniedException) as exc:
            await EntitlementService.check_feature_entitlement(db, ws_id, "advanced_forecasting")
        assert exc.value.code == "FEATURE_NOT_AVAILABLE"
        assert exc.value.feature == "advanced_forecasting"

        # Upgrade to Growth
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.plan = PLAN_GROWTH
        sub.status = STATUS_ACTIVE
        await db.commit()

        # Growth allowed
        assert await EntitlementService.has_feature(db, ws_id, "advanced_forecasting") is True
        await EntitlementService.check_feature_entitlement(db, ws_id, "advanced_forecasting")


# ==============================================================================
# TEST 18: Anomaly Detection Gate
# ==============================================================================
@pytest.mark.anyio
async def test_18_anomaly_detection_gate():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-18-anomaly-gate"
        assert await EntitlementService.has_feature(db, ws_id, "advanced_anomaly_detection") is False
        with pytest.raises(EntitlementDeniedException) as exc:
            await EntitlementService.check_feature_entitlement(db, ws_id, "advanced_anomaly_detection")
        assert exc.value.code == "FEATURE_NOT_AVAILABLE"
        assert exc.value.feature == "advanced_anomaly_detection"

        # Upgrade to Growth
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.plan = PLAN_GROWTH
        sub.status = STATUS_ACTIVE
        await db.commit()

        assert await EntitlementService.has_feature(db, ws_id, "advanced_anomaly_detection") is True
        await EntitlementService.check_feature_entitlement(db, ws_id, "advanced_anomaly_detection")


# ==============================================================================
# TEST 19: Scheduled Report Gate
# ==============================================================================
@pytest.mark.anyio
async def test_19_scheduled_report_gate():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-19-report-gate"
        assert await EntitlementService.has_feature(db, ws_id, "scheduled_reports") is False
        with pytest.raises(EntitlementDeniedException) as exc:
            await EntitlementService.check_feature_entitlement(db, ws_id, "scheduled_reports")
        assert exc.value.code == "FEATURE_NOT_AVAILABLE"
        assert exc.value.feature == "scheduled_reports"

        # Upgrade to Growth
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.plan = PLAN_GROWTH
        sub.status = STATUS_ACTIVE
        await db.commit()

        assert await EntitlementService.has_feature(db, ws_id, "scheduled_reports") is True
        await EntitlementService.check_feature_entitlement(db, ws_id, "scheduled_reports")


# ==============================================================================
# TEST 20: Billing API Authorization
# ==============================================================================
@pytest.mark.anyio
async def test_20_billing_api_authorization():
    # Direct client mutation endpoints (PUT/PATCH) are rejected with 405 Method Not Allowed
    set_user_workspace("user-20", "ws-20")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp_patch = await ac.patch(
            "/api/v1/billing/subscription",
            json={"plan": "growth", "status": "active"},
        )
        assert resp_patch.status_code == 405

        resp_put = await ac.put(
            "/api/v1/billing/subscription",
            json={"plan": "growth", "status": "active"},
        )
        assert resp_put.status_code == 405

    app.dependency_overrides.clear()


# ==============================================================================
# TEST 21: Customer Portal Creation
# ==============================================================================
@pytest.mark.anyio
async def test_21_customer_portal_creation():
    async with AsyncSessionLocal() as db:
        ws_id = "test-ws-21-portal"
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.stripe_customer_id = "cus_portal_test_21"
        sub.plan = PLAN_GROWTH
        sub.status = STATUS_ACTIVE
        await db.commit()

    set_user_workspace("user-21", ws_id)

    fake_portal_session = MagicMock()
    fake_portal_session.url = "https://billing.stripe.com/p/session/portal_test_session_21"

    with patch("stripe.billing_portal.Session.create", return_value=fake_portal_session) as mock_portal:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/api/v1/billing/portal")
            assert resp.status_code == 200
            data = resp.json()
            assert data["portal_url"] == fake_portal_session.url
            assert mock_portal.call_args[1]["customer"] == "cus_portal_test_21"

    app.dependency_overrides.clear()


# ==============================================================================
# TEST 22: Subscription Persistence
# ==============================================================================
@pytest.mark.anyio
async def test_22_subscription_persistence():
    ws_id = "test-ws-22-persistence"

    # Step 1: Write Growth subscription to database
    async with AsyncSessionLocal() as db:
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.plan = PLAN_GROWTH
        sub.status = STATUS_ACTIVE
        sub.stripe_customer_id = "cus_persistent_22"
        sub.stripe_subscription_id = "sub_persistent_22"
        sub.current_period_start = datetime.now(timezone.utc).replace(tzinfo=None)
        sub.current_period_end = (datetime.now(timezone.utc) + timedelta(days=30)).replace(tzinfo=None)
        await db.commit()

    # Step 2: Open completely new DB session (simulating restart / fresh connection)
    async with AsyncSessionLocal() as db2:
        reloaded_sub = await EntitlementService.get_workspace_subscription(db2, ws_id)
        assert reloaded_sub is not None
        assert reloaded_sub.plan == PLAN_GROWTH
        assert reloaded_sub.status == STATUS_ACTIVE
        assert reloaded_sub.stripe_customer_id == "cus_persistent_22"
        assert reloaded_sub.stripe_subscription_id == "sub_persistent_22"
        assert reloaded_sub.current_period_end is not None

        # Effective plan is Growth
        effective_plan = await EntitlementService.get_workspace_plan(db2, ws_id)
        assert effective_plan == PLAN_GROWTH


# ==============================================================================
# TEST 23: Refresh / Re-login Subscription Recovery
# ==============================================================================
@pytest.mark.anyio
async def test_23_refresh_relogin_subscription_recovery():
    ws_id = "test-ws-23-recovery"

    # Seed upgraded subscription in DB
    async with AsyncSessionLocal() as db:
        sub = await EntitlementService.get_or_create_workspace_subscription(db, ws_id)
        sub.plan = PLAN_GROWTH
        sub.status = STATUS_ACTIVE
        sub.stripe_customer_id = "cus_recovery_23"
        sub.stripe_subscription_id = "sub_recovery_23"
        await db.commit()

    # Simulate User session 1 (before logout)
    set_user_workspace("user-session-1", ws_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp1 = await ac.get("/api/v1/billing/subscription")
        assert resp1.status_code == 200
        assert resp1.json()["plan"] == PLAN_GROWTH

    # Simulate Logout: Clear dependency overrides and user context
    app.dependency_overrides.clear()

    # Simulate Re-login: User logs back in from another device/session
    set_user_workspace("user-session-2-new-device", ws_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp2 = await ac.get("/api/v1/billing/subscription")
        assert resp2.status_code == 200
        # Recovered purely from the database!
        data = resp2.json()
        assert data["plan"] == PLAN_GROWTH
        assert data["status"] == STATUS_ACTIVE
        assert data["stripe_subscription_id"] == "sub_recovery_23"
        assert data["entitlements"]["advanced_forecasting"] is True
        assert data["entitlements"]["active_datasets"] == "unlimited"

    app.dependency_overrides.clear()
