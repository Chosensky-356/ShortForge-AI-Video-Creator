import reflex as rx

import asyncio
import calendar
import json
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

from reflex_enterprise.auth import User
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JSONValue
from app.services.analytics import append_event, subscription_transition
from app.services.billing import product_ids, safe_https_url

FREE_VIDEO_LIMIT = 3
STARTER_VIDEO_LIMIT = 25
GROWTH_VIDEO_LIMIT = 80
YEARLY_VIDEO_LIMIT = 360
MAX_DURATION = 60
MONTHLY_EXHAUSTED_MESSAGE = "You've reached your monthly video limit. Upgrade to ShortForge Pro to keep creating."
VERIFICATION_UNAVAILABLE = "Billing verification is unavailable. Only Free access is enabled; no paid subscription has been verified."
_ACTIVE = ("queued", "generating", "rendering")


class UsageError(ValueError):
    """A safe, user-facing usage or lifecycle rejection."""


@dataclass(frozen=True)
class Access:
    subject: str
    tier: str
    limit: int
    months: int
    start: datetime
    end: datetime
    verified: bool
    warning: str = ""
    management_url: str = ""
    subscription_status: str = "Paid status not verified"
    renewal_cancelled: bool = False

    @property
    def period_label(self) -> str:
        return {1: "month", 3: "three-month period", 12: "year"}[self.months]

    @property
    def exhausted_message(self) -> str:
        if self.months == 1:
            return MONTHLY_EXHAUSTED_MESSAGE
        period = "three-month" if self.months == 3 else "yearly"
        return f"You've reached your {period} video limit. Your allowance renews at the start of your next billing period."


@dataclass(frozen=True)
class UsageSnapshot:
    access: Access
    used: int
    reserved: int
    reset_at: datetime

    @property
    def remaining(self) -> int:
        return max(0, self.access.limit - self.used - self.reserved)


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("A UTC billing timestamp is required")
    return parsed.astimezone(timezone.utc)


def _add_months(value: datetime, months: int) -> datetime:
    offset = value.year * 12 + value.month - 1 + months
    year, month = divmod(offset, 12)
    month += 1
    return value.replace(
        year=year,
        month=month,
        day=min(value.day, calendar.monthrange(year, month)[1]),
    )


def _free(
    subject: str, now: datetime, warning: str = "", verified: bool = False
) -> Access:
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return Access(
        subject,
        "free",
        FREE_VIDEO_LIMIT,
        1,
        start,
        _add_months(start, 1),
        verified,
        warning,
        subscription_status="No active paid subscription"
        if verified
        else "Paid status not verified",
    )


async def authenticated_subject() -> str:
    claims = await User.current() or {}
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise UsageError(
            "Your sign-in could not be confirmed. Please sign in again."
        )
    return subject


def _fetch_subscriber(subject: str, key: str) -> dict:
    request = Request(
        f"https://api.revenuecat.com/v1/subscribers/{quote(subject, safe='')}",
        headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
        },
        method="GET",
    )
    with urlopen(request, timeout=10) as response:
        payload = response.read(1_048_577)
        if len(payload) > 1_048_576:
            raise ValueError("Billing response is too large")
        result = json.loads(payload)
        if not isinstance(result, dict):
            raise ValueError("Invalid billing response")
        return result


def _parse_access(
    subject: str,
    payload: dict,
    products: dict[str, tuple[str, int, int]],
    now: datetime,
) -> Access:
    subscriber = payload.get("subscriber")
    if not isinstance(subscriber, dict) or not isinstance(
        subscriber.get("entitlements"), dict
    ):
        raise ValueError("Invalid subscriber response")
    entitlement = os.getenv("VITE_REVENUECAT_ENTITLEMENT", "").strip() or "pro"
    pro = subscriber["entitlements"].get(entitlement)
    if pro is None:
        return _free(subject, now, verified=True)
    if not isinstance(pro, dict):
        raise ValueError("Invalid entitlement response")
    expiry = pro.get("expires_date")
    if not isinstance(expiry, str):
        return _free(
            subject,
            now,
            "Paid access could not be verified for a finite billing term. Only Free access is enabled.",
        )
    end = _utc(expiry)
    if end <= now:
        from dataclasses import replace

        return replace(
            _free(subject, now, verified=True),
            subscription_status="Expired · Free access",
            management_url=safe_https_url(subscriber.get("management_url", "")),
        )
    product = pro.get("product_identifier")
    if not isinstance(product, str) or product not in products:
        return _free(
            subject,
            now,
            "This subscription product is not recognized. Only Free access is enabled; paid access has not been verified.",
        )
    subscriptions = subscriber.get("subscriptions", {})
    subscription = (
        subscriptions.get(product, {})
        if isinstance(subscriptions, dict)
        else {}
    )
    anchor = (
        subscription.get("purchase_date")
        if isinstance(subscription, dict)
        else None
    )
    anchor = anchor or pro.get("purchase_date")
    if not isinstance(anchor, str):
        raise ValueError("Missing verified billing anchor")
    start = _utc(anchor)
    if start > now or start >= end:
        raise ValueError("Invalid verified billing term")
    tier, limit, months = products[product]
    # Long or extended terms still have finite, anchored quota windows.
    elapsed = max(0, (now.year - start.year) * 12 + now.month - start.month)
    index = elapsed // months
    candidate = _add_months(start, index * months)
    if candidate > now:
        index = max(0, index - 1)
    period_start = _add_months(start, index * months)
    period_end = min(end, _add_months(start, (index + 1) * months))
    cancelled = isinstance(subscription, dict) and bool(
        subscription.get("unsubscribe_detected_at")
    )
    billing_issue = isinstance(subscription, dict) and bool(
        subscription.get("billing_issues_detected_at")
    )
    status = (
        "Active · renewal cancelled; access until expiry"
        if cancelled
        else "Active · subscription verified"
    )
    if billing_issue:
        status = "Active · billing issue detected; access until expiry"
    return Access(
        subject,
        tier,
        limit,
        months,
        period_start,
        period_end,
        True,
        management_url=safe_https_url(subscriber.get("management_url", "")),
        subscription_status=status,
        renewal_cancelled=cancelled,
    )


async def verify_access() -> Access:
    """Derive identity and privileges on the server; never accept a client plan."""
    subject = await authenticated_subject()
    now = datetime.now(timezone.utc)
    key = os.environ.get("REVENUECAT_SECRET_API_KEY", "").strip()
    products: dict[str, tuple[str, int, int]] = {}
    configured = (
        ("starter", STARTER_VIDEO_LIMIT, 1),
        ("growth", GROWTH_VIDEO_LIMIT, 3),
        ("yearly", YEARLY_VIDEO_LIMIT, 12),
    )
    ids = product_ids()
    for tier, limit, months in configured:
        product = ids[tier]
        if product:
            if product in products:
                return _free(subject, now, VERIFICATION_UNAVAILABLE)
            products[product] = (tier, limit, months)
    if not key or not products:
        return _free(subject, now, VERIFICATION_UNAVAILABLE)
    try:
        payload = await asyncio.wait_for(
            asyncio.to_thread(_fetch_subscriber, subject, key), timeout=12
        )
        return _parse_access(
            subject, payload, products, datetime.now(timezone.utc)
        )
    except Exception as e:
        # Do not log provider payloads, request headers, subjects or credentials.
        logging.exception(
            f"Error: billing verification failed ({type(e).__name__})"
        )
        return _free(
            subject, datetime.now(timezone.utc), VERIFICATION_UNAVAILABLE
        )


@dataclass
class _Profile:
    identity_subject: str
    onboarding_completed: bool
    onboarding_answers: dict[str, JSONValue]
    monthly_video_allowance: int
    monthly_videos_used: int
    monthly_videos_reserved: int
    usage_period_start: date
    usage_period_end: date | None


@dataclass
class _Project:
    id: str
    status: str
    target_duration_seconds: int
    generation_settings: dict[str, JSONValue]
    usage_charged_at: datetime | None


_PROJECT_LOCK_SQL = """
    SELECT id, status, target_duration_seconds, generation_settings,
           usage_charged_at
    FROM video_projects
    WHERE id = :project_id AND owner_subject = :subject
    FOR UPDATE
"""


async def _lock_profile(session: AsyncSession, subject: str) -> _Profile:
    row = (
        (
            await session.execute(
                text("""
                SELECT identity_subject, onboarding_completed, onboarding_answers,
                       COALESCE(monthly_video_allowance, 0) AS monthly_video_allowance,
                       COALESCE(monthly_videos_used, 0) AS monthly_videos_used,
                       COALESCE(monthly_videos_reserved, 0) AS monthly_videos_reserved,
                       usage_period_start, usage_period_end
                FROM creator_profiles
                WHERE identity_subject = :subject
                FOR UPDATE
            """),
                {"subject": subject},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None or not row["onboarding_completed"]:
        raise UsageError(
            "Complete your creator onboarding before creating videos."
        )
    return _Profile(**row)


async def _lock_project(
    session: AsyncSession, subject: str, project_id: str
) -> _Project:
    row = (
        (
            await session.execute(
                text(_PROJECT_LOCK_SQL),
                {"project_id": project_id, "subject": subject},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise UsageError("This project is no longer available.")
    return _Project(**row)


async def _save_profile(session: AsyncSession, profile: _Profile) -> None:
    (
        await session.execute(
            text("""
                UPDATE creator_profiles
                SET onboarding_answers = :answers,
                    monthly_video_allowance = :allowance,
                    monthly_videos_used = :used,
                    monthly_videos_reserved = :reserved,
                    usage_period_start = :period_start,
                    usage_period_end = :period_end,
                    updated_at = CURRENT_TIMESTAMP
                WHERE identity_subject = :subject
                RETURNING identity_subject
            """).bindparams(bindparam("answers", type_=JSONB)),
            {
                "subject": profile.identity_subject,
                "answers": profile.onboarding_answers,
                "allowance": profile.monthly_video_allowance,
                "used": profile.monthly_videos_used,
                "reserved": profile.monthly_videos_reserved,
                "period_start": profile.usage_period_start,
                "period_end": profile.usage_period_end,
            },
        )
    ).one()


def _sync_period(profile: _Profile, access: Access) -> datetime:
    now = datetime.now(timezone.utc)
    metadata = dict(profile.onboarding_answers or {})
    ledger = metadata.get("_usage_period")
    old_end = None
    if isinstance(ledger, dict) and isinstance(ledger.get("end"), str):
        old_end = _utc(ledger["end"])
    elif profile.usage_period_end:
        old_end = datetime.combine(
            profile.usage_period_end, datetime.min.time(), timezone.utc
        )
    reset = old_end is not None and now >= old_end and access.start >= old_end
    adopt_paid_term = (
        access.verified
        and access.tier != "free"
        and (
            not isinstance(ledger, dict)
            or ledger.get("tier") != access.tier
            or ledger.get("start") != access.start.isoformat()
        )
    )
    if old_end is None or reset or adopt_paid_term:
        if reset:
            profile.monthly_videos_used = 0
        metadata["_usage_period"] = {
            "start": access.start.isoformat(),
            "end": access.end.isoformat(),
            "tier": access.tier,
        }
        profile.onboarding_answers = metadata
        profile.usage_period_start = access.start.date()
        profile.usage_period_end = access.end.date()
        old_end = access.end
    # A downgrade, outage or tier switch never erases already spent credits.
    # Pending reservations survive rollover and consume the new allowance.
    profile.monthly_videos_used = max(0, profile.monthly_videos_used or 0)
    profile.monthly_videos_reserved = max(
        0, profile.monthly_videos_reserved or 0
    )
    profile.monthly_video_allowance = access.limit
    # Do not persist a paid tier as an authorization source.
    return old_end


async def sync_usage(session: AsyncSession, access: Access) -> UsageSnapshot:
    profile = await _lock_profile(session, access.subject)
    end = _sync_period(profile, access)
    if access.verified:
        metadata = dict(profile.onboarding_answers or {})
        prior = metadata.get("_verified_subscription", {})
        previous_active = (
            isinstance(prior, dict) and prior.get("active") is True
        )
        previous_cancelled = (
            isinstance(prior, dict) and prior.get("renewal_cancelled") is True
        )
        active = access.tier != "free"
        cancelled = active and access.renewal_cancelled
        event_name = subscription_transition(
            previous_active, active, previous_cancelled, cancelled
        )
        metadata["_verified_subscription"] = {
            "active": active,
            "renewal_cancelled": cancelled,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        profile.onboarding_answers = metadata
        if event_name:
            await append_event(session, event_name)
    await _save_profile(session, profile)
    return UsageSnapshot(
        access,
        profile.monthly_videos_used,
        profile.monthly_videos_reserved,
        end,
    )


def _duration(value: int) -> None:
    if type(value) is not int or not 1 <= value <= MAX_DURATION:
        raise UsageError(
            f"Videos must be between 1 and {MAX_DURATION} seconds."
        )


async def reserve_project(project_id: str) -> str:
    """Reserve ONE existing draft before any costly work; return an attempt token.

    Repeated calls for an active attempt return the same token, not another credit.
    Workers must keep the token and pass it to every lifecycle operation.
    """
    access = await verify_access()
    async with rx.asession() as session, session.begin():
        profile = await _lock_profile(session, access.subject)
        _sync_period(profile, access)
        await _save_profile(session, profile)
        project = await _lock_project(session, access.subject, project_id)
        _duration(project.target_duration_seconds)
        settings = dict(project.generation_settings or {})
        usage = settings.get("_usage", {})
        batch_id = settings.get("batch_id")
        if isinstance(batch_id, str) and batch_id:
            conflict = (
                await session.execute(
                    text("""
                SELECT EXISTS (
                    SELECT 1 FROM video_projects AS other
                    WHERE other.owner_subject = :subject
                      AND other.id <> :project_id
                      AND other.project_type = 'short'
                      AND other.generation_settings->>'batch_id' = :batch_id
                      AND other.status IN ('queued', 'generating', 'rendering')
                ) AND EXISTS (
                    SELECT 1 FROM video_projects
                    WHERE id = :project_id AND owner_subject = :subject
                      AND project_type = 'short'
                )
            """),
                    {
                        "subject": access.subject,
                        "project_id": project_id,
                        "batch_id": batch_id,
                    },
                )
            ).scalar()
            if conflict:
                raise UsageError(
                    "Another concept in this batch is already rendering. Wait for it to finish or refresh to recover interrupted work; only one concept can render at a time."
                )
        if project.usage_charged_at or project.status == "completed":
            raise UsageError(
                "This project has already been charged. Create a new project for another render."
            )
        if project.status in _ACTIVE:
            if (
                isinstance(usage, dict)
                and usage.get("held") is True
                and isinstance(usage.get("token"), str)
            ):
                return usage["token"]
            raise UsageError(
                "This project is already running without a recognized reservation."
            )
        if project.status not in ("draft", "failed", "cancelled"):
            raise UsageError("This project cannot be reserved.")
        if (
            profile.monthly_videos_used + profile.monthly_videos_reserved
            >= access.limit
        ):
            raise UsageError(access.exhausted_message)
        token = str(uuid4())
        settings["_usage"] = {"held": True, "token": token}
        profile.monthly_videos_reserved += 1
        await _save_profile(session, profile)
        (
            await session.execute(
                text("""
                    UPDATE video_projects
                    SET generation_settings = :settings,
                        status = 'queued', generation_stage = 'queued',
                        status_message = 'Video reserved for generation.',
                        generation_attempts = COALESCE(generation_attempts, 0) + 1,
                        progress_percent = 0, error_code = '', error_message = '',
                        queued_at = :now, status_changed_at = :now,
                        failed_at = NULL, cancelled_at = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :project_id AND owner_subject = :subject
                    RETURNING id
                """).bindparams(bindparam("settings", type_=JSONB)),
                {
                    "project_id": project_id,
                    "subject": access.subject,
                    "settings": settings,
                    "now": datetime.now(timezone.utc),
                },
            )
        ).one()
        return token


def _attempt(project: _Project, token: str) -> dict:
    usage = (project.generation_settings or {}).get("_usage", {})
    if not isinstance(usage, dict) or not token or usage.get("token") != token:
        raise UsageError("This generation attempt is no longer active.")
    return usage


async def mark_stage(project_id: str, token: str, stage: str) -> bool:
    """Claim a stage once. Only the worker receiving True may perform its work."""
    if stage not in ("generating", "rendering"):
        raise UsageError("Invalid generation stage.")
    subject = await authenticated_subject()
    async with rx.asession() as session, session.begin():
        await _lock_profile(session, subject)
        project = await _lock_project(session, subject, project_id)
        usage = _attempt(project, token)
        if project.status == stage:
            return False
        allowed = ("queued",) if stage == "generating" else ("generating",)
        if project.status not in allowed or usage.get("held") is not True:
            raise UsageError("Invalid generation transition.")
        (
            await session.execute(
                text("""
                    UPDATE video_projects
                    SET status = :stage, generation_stage = :stage,
                        status_changed_at = :now,
                        started_at = CASE WHEN :stage = 'generating'
                                          THEN :now ELSE started_at END,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :project_id AND owner_subject = :subject
                    RETURNING id
                """),
                {
                    "project_id": project_id,
                    "subject": subject,
                    "stage": stage,
                    "now": datetime.now(timezone.utc),
                },
            )
        ).one()
        return True


def _release(profile: _Profile, project: _Project, usage: dict) -> None:
    if usage.get("held") is True:
        if profile.monthly_videos_reserved < 1:
            raise UsageError(
                "Usage records need reconciliation. No changes were made."
            )
        profile.monthly_videos_reserved -= 1
        settings = dict(project.generation_settings or {})
        settings["_usage"] = {**usage, "held": False}
        project.generation_settings = settings


async def complete_render(project_id: str, token: str, asset_id: str) -> None:
    """Charge once, only for a persisted ready MP4 from a trusted render worker.

    This is a backend service, not a frontend event. Render workers must validate
    the actual output before marking the GeneratedAsset ready.
    """
    access = await verify_access()
    async with rx.asession() as session, session.begin():
        profile = await _lock_profile(session, access.subject)
        _sync_period(profile, access)
        project = await _lock_project(session, access.subject, project_id)
        usage = _attempt(project, token)
        if (
            project.status == "completed"
            and project.usage_charged_at is not None
        ):
            return
        if (
            project.status != "rendering"
            or usage.get("held") is not True
            or project.usage_charged_at is not None
        ):
            raise UsageError("Only an active reserved render can complete.")
        _duration(project.target_duration_seconds)
        asset = (
            (
                await session.execute(
                    text("""
                    SELECT a.asset_type, a.status, a.mime_type, a.byte_size,
                           a.duration_seconds, a.url
                    FROM generated_assets AS a
                    JOIN video_projects AS p ON p.id = a.project_id
                    WHERE a.id = :asset_id AND a.project_id = :project_id
                      AND p.owner_subject = :subject
                    FOR UPDATE OF a
                """),
                    {
                        "asset_id": asset_id,
                        "project_id": project.id,
                        "subject": access.subject,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        if (
            asset is None
            or asset["asset_type"] != "video"
            or asset["status"] != "ready"
            or asset["mime_type"] != "video/mp4"
            or not asset["byte_size"]
            or asset["byte_size"] <= 0
            or asset["duration_seconds"] is None
            or not 0 < asset["duration_seconds"] <= MAX_DURATION
        ):
            raise UsageError(
                "A successfully rendered MP4 of at most 60 seconds is required."
            )
        location = urlsplit(asset["url"])
        if not asset["url"] or not (
            location.scheme == "https"
            and location.netloc
            or asset["url"].startswith("/uploaded_files/")
            and not location.netloc
        ):
            raise UsageError("Rendered video location is unavailable.")
        _release(profile, project, usage)
        profile.monthly_videos_used += 1
        await _save_profile(session, profile)
        (
            await session.execute(
                text("""
                    UPDATE video_projects
                    SET generation_settings = :settings,
                        status = 'completed', generation_stage = 'completed',
                        progress_percent = 100, output_video_url = :url,
                        usage_charged_at = :now, completed_at = :now,
                        status_changed_at = :now,
                        status_message = 'Video completed.',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :project_id AND owner_subject = :subject
                    RETURNING id
                """).bindparams(bindparam("settings", type_=JSONB)),
                {
                    "project_id": project_id,
                    "subject": access.subject,
                    "settings": project.generation_settings,
                    "url": asset["url"],
                    "now": datetime.now(timezone.utc),
                },
            )
        ).one()
        await append_event(session, "generated", project_id)
        summary = (
            await session.execute(
                text("""
            SELECT (SELECT COUNT(*) FROM video_projects WHERE owner_subject = :subject AND usage_charged_at IS NOT NULL),
                   project_type FROM video_projects WHERE id = :id AND owner_subject = :subject LIMIT 1
        """),
                {"subject": access.subject, "id": project_id},
            )
        ).one()
        if summary[0] == 1:
            await append_event(session, "first_video", project_id)
        if summary[1] in ("product_ad", "ugc_ad"):
            await append_event(session, summary[1], project_id)


async def _end_attempt(project_id: str, token: str, status: str) -> None:
    subject = await authenticated_subject()
    async with rx.asession() as session, session.begin():
        profile = await _lock_profile(session, subject)
        project = await _lock_project(session, subject, project_id)
        usage = _attempt(project, token)
        if project.status == status and usage.get("held") is False:
            return
        if (
            project.status not in _ACTIVE
            or project.usage_charged_at is not None
        ):
            raise UsageError("This attempt is no longer active.")
        _release(profile, project, usage)
        await _save_profile(session, profile)
        message = (
            "Generation failed. Your reservation was released."
            if status == "failed"
            else "Generation cancelled. Your reservation was released."
        )
        (
            await session.execute(
                text("""
                    UPDATE video_projects
                    SET generation_settings = :settings,
                        status = :status, generation_stage = :status,
                        status_changed_at = :now, status_message = :message,
                        failed_at = CASE WHEN :status = 'failed'
                                         THEN :now ELSE failed_at END,
                        cancelled_at = CASE WHEN :status = 'cancelled'
                                            THEN :now ELSE cancelled_at END,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :project_id AND owner_subject = :subject
                    RETURNING id
                """).bindparams(bindparam("settings", type_=JSONB)),
                {
                    "project_id": project_id,
                    "subject": subject,
                    "settings": project.generation_settings,
                    "status": status,
                    "now": datetime.now(timezone.utc),
                    "message": message,
                },
            )
        ).one()
        if status == "failed":
            await append_event(session, "generation_failed", project_id)


async def fail_project(project_id: str, token: str) -> None:
    await _end_attempt(project_id, token, "failed")


async def cancel_project(project_id: str, token: str) -> None:
    await _end_attempt(project_id, token, "cancelled")


async def delete_project(project_id: str) -> bool:
    """Deletion cannot refund completed usage or strand a reservation."""
    subject = await authenticated_subject()
    async with rx.asession() as session, session.begin():
        profile = await _lock_profile(session, subject)
        row = (
            (
                await session.execute(
                    text(_PROJECT_LOCK_SQL),
                    {"project_id": project_id, "subject": subject},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return False
        project = _Project(**row)
        if project.status in _ACTIVE:
            raise UsageError(
                "Cancel the active generation before deleting this project."
            )
        usage = (project.generation_settings or {}).get("_usage", {})
        if isinstance(usage, dict):
            _release(profile, project, usage)
        await _save_profile(session, profile)
        (
            await session.execute(
                text("""
                    DELETE FROM video_projects
                    WHERE id = :project_id AND owner_subject = :subject
                    RETURNING id
                """),
                {"project_id": project_id, "subject": subject},
            )
        ).one()
        return True
