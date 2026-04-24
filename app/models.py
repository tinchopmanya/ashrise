from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


TASK_STATUSES = ("backlog", "ready", "progress", "blocked", "done")


class Base(DeclarativeBase):
    pass


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "(idea_id IS NOT NULL) OR (project_id IS NOT NULL) OR (candidate_id IS NOT NULL)",
            name="tasks_requires_owner",
        ),
        CheckConstraint(
            "status IN ('backlog', 'ready', 'progress', 'blocked', 'done')",
            name="tasks_status_check",
        ),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=func.uuid_generate_v4())
    idea_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("ideas.id", ondelete="CASCADE"),
        nullable=True,
    )
    project_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
    )
    candidate_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("vertical_candidates.id", ondelete="CASCADE"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'backlog'"))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default="{}")
    promoted_to: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    closed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationEvent(Base):
    __tablename__ = "notification_events"
    __table_args__ = (
        CheckConstraint(
            "channel IN ('telegram', 'whatsapp', 'email', 'system')",
            name="notification_events_channel_check",
        ),
        CheckConstraint(
            "direction IN ('inbound', 'outbound', 'system')",
            name="notification_events_direction_check",
        ),
        CheckConstraint(
            "delivery_status IN ('pending', 'delivered', 'failed', 'read', 'received')",
            name="notification_events_delivery_status_check",
        ),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=func.uuid_generate_v4())
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(32), nullable=False)
    project_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    candidate_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("vertical_candidates.id", ondelete="SET NULL"),
        nullable=True,
    )
    run_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    idea_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("ideas.id", ondelete="SET NULL"),
        nullable=True,
    )
    task_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    message_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'pending'"))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    delivered_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
