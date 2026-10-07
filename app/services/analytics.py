import reflex as rx

from uuid import uuid4
from reflex_enterprise.auth import User
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

EVENT_NAMES = frozenset(
    (
        "signup",
        "first_video",
        "generated",
        "downloaded",
        "product_ad",
        "ugc_ad",
        "paywall_viewed",
        "subscription_started",
        "subscription_cancelled",
        "restore",
        "generation_failed",
    )
)


async def append_event(
    session: AsyncSession, event_name: str, project_id: str | None = None
) -> None:
    if event_name not in EVENT_NAMES:
        raise ValueError("Unsupported analytics event")
    user = await User.current() or {}
    subject = user.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise ValueError("Authenticated analytics owner required")
    await session.execute(
        text("""
        INSERT INTO analytics_events (id, owner_subject, event_name, project_id)
        SELECT CAST(:id AS UUID), CAST(:subject AS VARCHAR(512)),
               CAST(:event AS VARCHAR(32)), CAST(:project AS VARCHAR(36))
        WHERE EXISTS (
            SELECT 1 FROM creator_profiles
            WHERE identity_subject = CAST(:subject AS VARCHAR(512)))
          AND (CAST(:project AS VARCHAR(36)) IS NULL OR EXISTS (
              SELECT 1 FROM video_projects
              WHERE id = CAST(:project AS VARCHAR(36))
                AND owner_subject = CAST(:subject AS VARCHAR(512))))
    """),
        {
            "id": uuid4(),
            "subject": subject,
            "event": event_name,
            "project": project_id,
        },
    )


async def record_event(event_name: str, project_id: str | None = None) -> None:
    async with rx.asession() as session:
        await append_event(session, event_name, project_id)
        await session.commit()


def subscription_transition(
    previous_active: bool,
    active: bool,
    previous_cancelled: bool = False,
    cancelled: bool = False,
) -> str:
    if active and not previous_active:
        return "subscription_started"
    if previous_active and not previous_cancelled and (not active or cancelled):
        return "subscription_cancelled"
    return ""
