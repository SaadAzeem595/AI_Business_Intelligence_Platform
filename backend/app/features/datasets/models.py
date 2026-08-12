from typing import Optional
from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # CSV, Excel, JSON, PDF
    size: Mapped[str] = mapped_column(String, nullable=False)
    rows: Mapped[int] = mapped_column(Integer, default=0)
    qualityScore: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="Active")  # Active, Processing, Failed
    date: Mapped[str] = mapped_column(String, nullable=False)
    
    # Persistent dataset and workspace metadata fields
    workspace_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    storage_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    duckdb_table: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    columns_json: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    schema_json: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Scoped project fields
    project_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    owner_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    original_filename: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    project = relationship("Project")
    owner = relationship("User")


