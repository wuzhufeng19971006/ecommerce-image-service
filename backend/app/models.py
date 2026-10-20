from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    thumb_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    parent_job_id: Mapped[str | None] = mapped_column(
        String(32), nullable=True, index=True
    )
    workflow: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    instruction: Mapped[str] = mapped_column(Text, nullable=False, default="")
    final_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    options_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    inputs_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    usage_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shots_total: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    shots_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    outputs: Mapped[list[JobOutput]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobOutput.position",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_jobs_created_at", "created_at"),
        Index("ix_jobs_workflow", "workflow"),
        Index("ix_jobs_status_created", "status", "created_at"),
    )


class JobOutput(Base):
    __tablename__ = "job_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    job: Mapped[Job] = relationship(back_populates="outputs")
    asset: Mapped[Asset] = relationship(lazy="selectin")

    __table_args__ = (
        UniqueConstraint("job_id", "position", name="uq_job_output_position"),
        Index("ix_job_outputs_job", "job_id"),
        Index("ix_job_outputs_asset", "asset_id"),
    )
