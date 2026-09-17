from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # PDF, PowerPoint, HTML
    frequency: Mapped[str] = mapped_column(String, nullable=False)  # Daily, Weekly, Ad-hoc, Monthly
    created: Mapped[str] = mapped_column(String, nullable=False)
    size: Mapped[str] = mapped_column(String, nullable=False)
    recipient: Mapped[str] = mapped_column(String, nullable=False)
    workspace: Mapped[str] = mapped_column(String, nullable=False, default="default")
    project_id: Mapped[str] = mapped_column(String, nullable=True)
    author: Mapped[str] = mapped_column(String, nullable=False, default="system")
    template: Mapped[str] = mapped_column(String, nullable=False, default="Executive Summary")
    reporting_period: Mapped[str] = mapped_column(String, nullable=True, default="Last 30 Days")
    data_sources: Mapped[str] = mapped_column(String, nullable=True)  # JSON or comma-separated
    options: Mapped[str] = mapped_column(String, nullable=True)  # JSON list of included options
    datasets_used: Mapped[str] = mapped_column(String, nullable=True)
    delivery_status: Mapped[str] = mapped_column(String, nullable=False, default="Pending")
    delivery_error: Mapped[str] = mapped_column(String, nullable=True)
    file_path: Mapped[str] = mapped_column(String, nullable=True)
    report_data: Mapped[str] = mapped_column(String, nullable=True)  # JSON-encoded normalized report context

    @property
    def status(self) -> str:
        return "Active"


class ReportSchedule(Base):
    __tablename__ = "report_schedules"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    workspace: Mapped[str] = mapped_column(String, nullable=False, default="default")
    project_id: Mapped[str] = mapped_column(String, nullable=True)
    report_type: Mapped[str] = mapped_column(String, nullable=False)  # PDF, PowerPoint, HTML
    frequency: Mapped[str] = mapped_column(String, nullable=False)  # Daily, Weekly, Monthly, Quarterly
    template: Mapped[str] = mapped_column(String, nullable=False, default="Executive Summary")
    reporting_period: Mapped[str] = mapped_column(String, nullable=True, default="Last 30 Days")
    data_sources: Mapped[str] = mapped_column(String, nullable=True)
    options: Mapped[str] = mapped_column(String, nullable=True)
    recipient: Mapped[str] = mapped_column(String, nullable=False)
    author: Mapped[str] = mapped_column(String, nullable=False, default="system")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
