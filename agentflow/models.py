from datetime import datetime
from typing import Any
from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from agentflow.db import Base

class Workflow(Base):
    __tablename__ = "workflows"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    runs: Mapped[list["Run"]] = relationship(back_populates="workflow")

class Run(Base):
    __tablename__ = "runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    current_node: Mapped[str | None] = mapped_column(String(100))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    workflow: Mapped[Workflow] = relationship(back_populates="runs")
    events: Mapped[list["RunEvent"]] = relationship(back_populates="run", cascade="all, delete-orphan", order_by="RunEvent.id")

class RunEvent(Base):
    __tablename__ = "run_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    node_id: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    run: Mapped[Run] = relationship(back_populates="events")
