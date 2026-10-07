import reflex as rx

from datetime import date, datetime, timezone
from typing import TypeAlias
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


JSONValue: TypeAlias = (
    str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]
)


class Base(DeclarativeBase):
    pass


class CreatorProfile(Base):
    __tablename__ = "creator_profiles"
    __table_args__ = (
        CheckConstraint(
            "identity_subject <> ''", name="ck_creator_identity_required"
        ),
        CheckConstraint(
            "onboarding_step BETWEEN 0 AND 4", name="ck_creator_onboarding_step"
        ),
        CheckConstraint(
            "monthly_video_allowance >= 0",
            name="ck_creator_allowance_nonnegative",
        ),
        CheckConstraint(
            "monthly_videos_used >= 0", name="ck_creator_usage_nonnegative"
        ),
        CheckConstraint(
            "monthly_videos_reserved >= 0",
            name="ck_creator_reservations_nonnegative",
        ),
        CheckConstraint(
            "usage_period_end IS NULL OR usage_period_end > usage_period_start",
            name="ck_creator_usage_period",
        ),
    )

    identity_subject: Mapped[str] = mapped_column(
        String(512), primary_key=True, default="", server_default=""
    )
    display_name: Mapped[str] = mapped_column(
        String(200), default="", server_default=""
    )
    onboarding_completed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    onboarding_step: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    # Replace nested JSON values when editing; mutable tracking covers top-level edits.
    onboarding_answers: Mapped[dict[str, JSONValue]] = mapped_column(
        MutableDict.as_mutable(JSONB), default=dict
    )
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    plan: Mapped[str] = mapped_column(
        String(64), default="free", server_default="free"
    )
    monthly_video_allowance: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    monthly_videos_used: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    monthly_videos_reserved: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    usage_period_start: Mapped[date] = mapped_column(
        Date,
        default=lambda: datetime.now(timezone.utc).date().replace(day=1),
        server_default=text(
            "date_trunc('month', timezone('UTC', CURRENT_TIMESTAMP))::date"
        ),
    )
    usage_period_end: Mapped[date | None] = mapped_column(
        Date, nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    projects: Mapped[list["VideoProject"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )


class VideoProject(Base):
    __tablename__ = "video_projects"
    __table_args__ = (
        CheckConstraint(
            "owner_subject <> ''", name="ck_project_owner_required"
        ),
        CheckConstraint(
            "target_duration_seconds > 0", name="ck_project_duration_positive"
        ),
        CheckConstraint(
            "progress_percent BETWEEN 0 AND 100",
            name="ck_project_progress_range",
        ),
        CheckConstraint(
            "generation_attempts >= 0", name="ck_project_attempts_nonnegative"
        ),
        CheckConstraint(
            "status IN ('draft', 'queued', 'generating', 'rendering', 'completed', 'failed', 'cancelled')",
            name="ck_project_status",
        ),
        CheckConstraint(
            "project_type IN ('short', 'product_ad', 'ugc_ad')",
            name="ck_project_type",
        ),
        Index("ix_projects_owner_created", "owner_subject", "created_at"),
        Index("ix_projects_status_updated", "status", "updated_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    # Empty ownership defaults fail validation/FK checks; an authenticated owner is required.
    owner_subject: Mapped[str] = mapped_column(
        String(512),
        ForeignKey("creator_profiles.identity_subject", ondelete="CASCADE"),
        default="",
        server_default="",
    )
    project_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="short", server_default="short"
    )
    title: Mapped[str] = mapped_column(
        String(200), default="Untitled short", server_default="Untitled short"
    )
    idea: Mapped[str] = mapped_column(Text, default="", server_default="")
    style: Mapped[str] = mapped_column(
        String(64), default="", server_default=""
    )
    target_duration_seconds: Mapped[int] = mapped_column(
        Integer, default=30, server_default=text("30")
    )
    language: Mapped[str] = mapped_column(
        String(32), default="en", server_default="en"
    )
    aspect_ratio: Mapped[str] = mapped_column(
        String(16), default="9:16", server_default="9:16"
    )
    status: Mapped[str] = mapped_column(
        String(32), default="draft", server_default="draft"
    )
    status_message: Mapped[str] = mapped_column(
        Text, default="", server_default=""
    )
    generation_stage: Mapped[str] = mapped_column(
        String(64), default="", server_default=""
    )
    progress_percent: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    generation_attempts: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )

    hook: Mapped[str] = mapped_column(Text, default="", server_default="")
    script: Mapped[str] = mapped_column(Text, default="", server_default="")
    scenes: Mapped[list[dict[str, JSONValue]]] = mapped_column(
        MutableList.as_mutable(JSONB), default=list
    )
    captions: Mapped[list[dict[str, JSONValue]]] = mapped_column(
        MutableList.as_mutable(JSONB), default=list
    )
    music: Mapped[dict[str, JSONValue]] = mapped_column(
        MutableDict.as_mutable(JSONB), default=dict
    )
    cta: Mapped[str] = mapped_column(Text, default="", server_default="")
    voiceover_text: Mapped[str] = mapped_column(
        Text, default="", server_default=""
    )
    generation_settings: Mapped[dict[str, JSONValue]] = mapped_column(
        MutableDict.as_mutable(JSONB), default=dict
    )
    output_video_url: Mapped[str] = mapped_column(
        Text, default="", server_default=""
    )
    thumbnail_url: Mapped[str] = mapped_column(
        Text, default="", server_default=""
    )
    error_code: Mapped[str] = mapped_column(
        String(100), default="", server_default=""
    )
    error_message: Mapped[str] = mapped_column(
        Text, default="", server_default=""
    )
    usage_charged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # Generation handlers will set status_changed_at alongside status transitions.
    status_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    queued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    owner: Mapped[CreatorProfile] = relationship(
        back_populates="projects", lazy="raise"
    )
    assets: Mapped[list["GeneratedAsset"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )


class GeneratedAsset(Base):
    __tablename__ = "generated_assets"
    __table_args__ = (
        CheckConstraint("project_id <> ''", name="ck_asset_project_required"),
        CheckConstraint(
            "asset_type IN ('image', 'video', 'voiceover', 'music', 'captions', 'thumbnail', 'other')",
            name="ck_asset_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'generating', 'ready', 'failed')",
            name="ck_asset_status",
        ),
        CheckConstraint(
            "sequence_index >= 0", name="ck_asset_sequence_nonnegative"
        ),
        CheckConstraint(
            "byte_size IS NULL OR byte_size >= 0",
            name="ck_asset_size_nonnegative",
        ),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_asset_duration_nonnegative",
        ),
        Index(
            "ix_assets_project_type_sequence",
            "project_id",
            "asset_type",
            "sequence_index",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("video_projects.id", ondelete="CASCADE"),
        default="",
        server_default="",
    )
    asset_type: Mapped[str] = mapped_column(
        String(32), default="other", server_default="other"
    )
    status: Mapped[str] = mapped_column(
        String(32), default="pending", server_default="pending"
    )
    url: Mapped[str] = mapped_column(Text, default="", server_default="")
    mime_type: Mapped[str] = mapped_column(
        String(128), default="", server_default=""
    )
    sequence_index: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    scene_index: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None
    )
    byte_size: Mapped[int | None] = mapped_column(nullable=True, default=None)
    duration_seconds: Mapped[float | None] = mapped_column(
        nullable=True, default=None
    )
    provider: Mapped[str] = mapped_column(
        String(100), default="", server_default=""
    )
    provider_asset_id: Mapped[str] = mapped_column(
        String(512), default="", server_default=""
    )
    prompt: Mapped[str] = mapped_column(Text, default="", server_default="")
    # DeclarativeBase reserves `metadata`; retain that DB column name via asset_metadata.
    asset_metadata: Mapped[dict[str, JSONValue]] = mapped_column(
        "metadata",
        MutableDict.as_mutable(JSONB),
        default=dict,
    )
    error_message: Mapped[str] = mapped_column(
        Text, default="", server_default=""
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    project: Mapped[VideoProject] = relationship(
        back_populates="assets", lazy="raise"
    )


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    __table_args__ = (
        CheckConstraint(
            "event_name IN ('signup', 'first_video', 'generated', 'downloaded', 'product_ad', 'ugc_ad', 'paywall_viewed', 'subscription_started', 'subscription_cancelled', 'restore', 'generation_failed')",
            name="ck_analytics_event_name",
        ),
        Index("ix_analytics_owner_time", "owner_subject", "timestamp"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    owner_subject: Mapped[str] = mapped_column(
        String(512),
        ForeignKey("creator_profiles.identity_subject", ondelete="CASCADE"),
        nullable=False,
        default="",
        server_default="",
    )
    event_name: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", server_default=""
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, default=None
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
