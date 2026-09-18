from fastapi import status
from app.core.exceptions import ServiceException


class EntitlementDeniedException(ServiceException):
    """Raised when a workspace attempts to use a feature not entitled by its plan."""

    def __init__(
        self,
        feature: str,
        current_plan: str,
        required_plan: str = "growth",
        message: str = None,
    ):
        feature_labels = {
            "advanced_forecasting": "Advanced Trend Forecasting",
            "advanced_anomaly_detection": "Advanced Anomaly Detection",
            "scheduled_reports": "Scheduled Executive Reports",
            "shared_collaboration": "Team Collaboration & User Management",
            "custom_integrations": "Custom Integrations",
            "sso": "Single Sign-On (SSO)",
            "audit_logging": "Advanced Audit Logging",
            "dedicated_scaling": "Dedicated Scaling & Infrastructure",
        }
        label = feature_labels.get(feature, feature.replace("_", " ").title())
        default_message = (
            f"{label} requires the {required_plan.title()} plan. "
            f"Please upgrade from {current_plan.title()} to access this feature."
        )

        details = {
            "code": "FEATURE_NOT_AVAILABLE",
            "feature": feature,
            "current_plan": current_plan,
            "required_plan": required_plan,
        }
        super().__init__(
            message=message or default_message,
            status_code=status.HTTP_403_FORBIDDEN,
            code="FEATURE_NOT_AVAILABLE",
            module="billing",
            details=details,
        )
        self.feature = feature
        self.current_plan = current_plan
        self.required_plan = required_plan


class DatasetLimitReachedException(ServiceException):
    """Raised when a workspace attempts to upload datasets beyond its plan allowance."""

    def __init__(
        self,
        current: int,
        limit: int = 1,
        current_plan: str = "starter",
        required_plan: str = "growth",
        message: str = None,
    ):
        default_message = (
            f"The {current_plan.title()} plan allows a maximum of {limit} active dataset. "
            f"You currently have {current}. Upgrade to {required_plan.title()} for unlimited datasets."
        )

        details = {
            "code": "PLAN_LIMIT_REACHED",
            "feature": "active_datasets",
            "current": current,
            "limit": limit,
            "current_plan": current_plan,
            "required_plan": required_plan,
        }
        super().__init__(
            message=message or default_message,
            status_code=status.HTTP_403_FORBIDDEN,
            code="PLAN_LIMIT_REACHED",
            module="billing",
            details=details,
        )
        self.current = current
        self.limit = limit
        self.current_plan = current_plan
        self.required_plan = required_plan
