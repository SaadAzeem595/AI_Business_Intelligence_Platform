from typing import Optional, Dict, Any
from datetime import datetime, timezone
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.features.billing.models import WorkspaceSubscription
from app.features.billing.exceptions import (
    EntitlementDeniedException,
    DatasetLimitReachedException,
)
from app.features.datasets.models import Dataset

logger = logging.getLogger(__name__)

# Plan Constants
PLAN_STARTER = "starter"
PLAN_GROWTH = "growth"
PLAN_ENTERPRISE = "enterprise"

# Status Constants
STATUS_TRIALING = "trialing"
STATUS_ACTIVE = "active"
STATUS_PAST_DUE = "past_due"
STATUS_CANCELED = "canceled"
STATUS_INCOMPLETE = "incomplete"
STATUS_INCOMPLETE_EXPIRED = "incomplete_expired"
STATUS_UNPAID = "unpaid"

# Feature Matrix: feature -> list of entitled plans
PLAN_FEATURES = {
    # Core Analytics
    "basic_sql": [PLAN_STARTER, PLAN_GROWTH, PLAN_ENTERPRISE],
    "standard_ai_chat": [PLAN_STARTER, PLAN_GROWTH, PLAN_ENTERPRISE],
    # Growth Tier Features
    "advanced_forecasting": [PLAN_GROWTH, PLAN_ENTERPRISE],
    "advanced_anomaly_detection": [PLAN_GROWTH, PLAN_ENTERPRISE],
    "scheduled_reports": [PLAN_GROWTH, PLAN_ENTERPRISE],
    "shared_collaboration": [PLAN_GROWTH, PLAN_ENTERPRISE],
    # Enterprise Tier Features
    "custom_integrations": [PLAN_ENTERPRISE],
    "sso": [PLAN_ENTERPRISE],
    "audit_logging": [PLAN_ENTERPRISE],
    "dedicated_scaling": [PLAN_ENTERPRISE],
}

# Limits Matrix: plan -> dataset count limit (None means unlimited)
DATASET_LIMITS = {
    PLAN_STARTER: 1,
    PLAN_GROWTH: None,
    PLAN_ENTERPRISE: None,
}


class EntitlementService:
    @staticmethod
    async def get_workspace_subscription(
        db: AsyncSession, workspace_id: str
    ) -> Optional[WorkspaceSubscription]:
        """Fetch subscription record for a workspace."""
        if not workspace_id:
            workspace_id = "default"
        stmt = select(WorkspaceSubscription).where(
            WorkspaceSubscription.workspace_id == workspace_id
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @classmethod
    async def get_or_create_workspace_subscription(
        cls, db: AsyncSession, workspace_id: str
    ) -> WorkspaceSubscription:
        """Fetch or initialize default Starter subscription for a workspace."""
        if not workspace_id:
            workspace_id = "default"
        sub = await cls.get_workspace_subscription(db, workspace_id)
        if not sub:
            sub = WorkspaceSubscription(
                workspace_id=workspace_id,
                plan=PLAN_STARTER,
                status=STATUS_ACTIVE,
                cancel_at_period_end=False,
            )
            db.add(sub)
            await db.flush()
        return sub

    @classmethod
    async def get_workspace_plan(
        cls, db: AsyncSession, workspace_id: str
    ) -> str:
        """
        Determines the effective active plan for a workspace, taking into account
        cancellation grace periods and subscription status.
        """
        sub = await cls.get_workspace_subscription(db, workspace_id)
        if not sub:
            return PLAN_STARTER

        # Check if subscription has been canceled or expired
        if sub.status in [STATUS_CANCELED, STATUS_UNPAID, STATUS_INCOMPLETE_EXPIRED]:
            return PLAN_STARTER

        # Check cancellation at period end grace window
        if sub.cancel_at_period_end and sub.current_period_end:
            now = datetime.now(timezone.utc)
            period_end = sub.current_period_end
            if period_end.tzinfo is None:
                period_end = period_end.replace(tzinfo=timezone.utc)
            if now > period_end:
                return PLAN_STARTER

        # If status is past_due, we can allow grace access or fallback.
        # Standard SaaS practice: allow grace access unless canceled.
        if sub.status in [STATUS_ACTIVE, STATUS_TRIALING, STATUS_PAST_DUE]:
            return (sub.plan or PLAN_STARTER).lower()

        return PLAN_STARTER

    @classmethod
    async def has_feature(
        cls, db: AsyncSession, workspace_id: str, feature: str
    ) -> bool:
        """Check if the given workspace is entitled to use a specific feature."""
        plan = await cls.get_workspace_plan(db, workspace_id)
        allowed_plans = PLAN_FEATURES.get(feature, [])
        return plan in allowed_plans

    @classmethod
    async def check_feature_entitlement(
        cls, db: AsyncSession, workspace_id: str, feature: str
    ) -> None:
        """
        Validates entitlement to a feature, raising EntitlementDeniedException if unauthorized.
        """
        plan = await cls.get_workspace_plan(db, workspace_id)
        allowed_plans = PLAN_FEATURES.get(feature, [])
        if plan not in allowed_plans:
            required = PLAN_GROWTH if PLAN_GROWTH in allowed_plans else PLAN_ENTERPRISE
            raise EntitlementDeniedException(
                feature=feature,
                current_plan=plan,
                required_plan=required,
            )

    @classmethod
    async def get_active_dataset_count(
        cls, db: AsyncSession, workspace_id: str
    ) -> int:
        """Count custom active datasets uploaded to the workspace."""
        stmt = (
            select(func.count(Dataset.id))
            .where(
                Dataset.workspace_id == workspace_id,
                Dataset.status != "Deleted",
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none() or 0

    @classmethod
    async def check_dataset_limit(
        cls, db: AsyncSession, workspace_id: str
    ) -> None:
        """
        Validates dataset upload limits for the workspace's plan.
        Raises DatasetLimitReachedException if limit is reached.
        """
        plan = await cls.get_workspace_plan(db, workspace_id)
        limit = DATASET_LIMITS.get(plan)

        if limit is not None:
            current_count = await cls.get_active_dataset_count(db, workspace_id)
            if current_count >= limit:
                raise DatasetLimitReachedException(
                    current=current_count,
                    limit=limit,
                    current_plan=plan,
                    required_plan=PLAN_GROWTH,
                )

    @classmethod
    def get_plan_entitlements(cls, plan: str) -> Dict[str, bool]:
        """Returns map of all feature entitlements for a given plan."""
        norm_plan = (plan or PLAN_STARTER).lower()
        return {
            feat: norm_plan in allowed
            for feat, allowed in PLAN_FEATURES.items()
        }

    @classmethod
    async def get_workspace_usage(
        cls, db: AsyncSession, workspace_id: str
    ) -> Dict[str, Any]:
        """Returns comprehensive usage and entitlement breakdown for workspace."""
        sub = await cls.get_or_create_workspace_subscription(db, workspace_id)
        effective_plan = await cls.get_workspace_plan(db, workspace_id)
        current_count = await cls.get_active_dataset_count(db, workspace_id)
        limit = DATASET_LIMITS.get(effective_plan)

        return {
            "plan": effective_plan,
            "status": sub.status,
            "cancel_at_period_end": sub.cancel_at_period_end,
            "current_period_end": sub.current_period_end,
            "datasets": {
                "current": current_count,
                "limit": limit,
            },
            "features": cls.get_plan_entitlements(effective_plan),
        }
