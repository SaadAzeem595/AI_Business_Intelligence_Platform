from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # PDF, PowerPoint
    frequency: Mapped[str] = mapped_column(String, nullable=False)  # Daily, Weekly, Ad-hoc
    created: Mapped[str] = mapped_column(String, nullable=False)
    size: Mapped[str] = mapped_column(String, nullable=False)
    recipient: Mapped[str] = mapped_column(String, nullable=False)
    workspace: Mapped[str] = mapped_column(String, nullable=False, default="default")
    author: Mapped[str] = mapped_column(String, nullable=False, default="system")
    template: Mapped[str] = mapped_column(String, nullable=False, default="CEO")
    datasets_used: Mapped[str] = mapped_column(String, nullable=True)
    delivery_status: Mapped[str] = mapped_column(String, nullable=False, default="Pending")
    file_path: Mapped[str] = mapped_column(String, nullable=True)


class ReportSchedule(Base):
    __tablename__ = "report_schedules"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    workspace: Mapped[str] = mapped_column(String, nullable=False, default="default")
    report_type: Mapped[str] = mapped_column(String, nullable=False)  # PDF, PowerPoint
    frequency: Mapped[str] = mapped_column(String, nullable=False)  # Daily, Weekly, Monthly, Quarterly
    template: Mapped[str] = mapped_column(String, nullable=False, default="CEO")
    recipient: Mapped[str] = mapped_column(String, nullable=False)
    author: Mapped[str] = mapped_column(String, nullable=False, default="system")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
