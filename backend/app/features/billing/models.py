from typing import Optional
from datetime import datetime
import uuid
from sqlalchemy import Boolean, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class WorkspaceSubscription(Base):
    __tablename__ = "workspace_subscriptions"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    workspace_id: Mapped[str] = mapped_column(
        String, unique=True, index=True, nullable=False
    )
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, index=True
    )
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, index=True
    )
    stripe_price_id: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    plan: Mapped[str] = mapped_column(
        String, default="starter", nullable=False
    )  # starter, growth, enterprise
    status: Mapped[str] = mapped_column(
        String, default="active", nullable=False
    )  # trialing, active, past_due, canceled, incomplete, incomplete_expired, unpaid
    current_period_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    current_period_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )


class StripeProcessedEvent(Base):
    __tablename__ = "stripe_processed_events"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    event_id: Mapped[str] = mapped_column(
        String, unique=True, index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(
        String, nullable=False
    )
    workspace_id: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
