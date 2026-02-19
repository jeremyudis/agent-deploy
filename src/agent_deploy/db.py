"""SQLAlchemy models and engine helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    String,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)


class Base(DeclarativeBase):
    pass


class DeployRun(Base):
    __tablename__ = "deploy_runs"

    deploy_id: Mapped[str] = mapped_column(String, primary_key=True)
    service: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[str] = mapped_column(String, nullable=False)
    regions: Mapped[dict] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    deploy_id: Mapped[str] = mapped_column(
        String, ForeignKey("deploy_runs.deploy_id"), nullable=False
    )
    region: Mapped[str] = mapped_column(String, nullable=False)
    decision: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reasoning: Mapped[str] = mapped_column(String, default="")
    evidence: Mapped[dict] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    deploy_id: Mapped[str] = mapped_column(
        String, ForeignKey("deploy_runs.deploy_id"), nullable=False
    )
    region: Mapped[str] = mapped_column(String, nullable=False)
    decision: Mapped[str] = mapped_column(String, nullable=False)
    approver: Mapped[str] = mapped_column(String, default="")
    reason: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


def get_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy engine for the given database URL."""
    return create_engine(database_url)


def get_session(engine: Engine) -> Session:
    """Create a new session bound to *engine*."""
    factory = sessionmaker(bind=engine)
    return factory()
