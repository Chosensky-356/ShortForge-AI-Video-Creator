import reflex as rx
import reflex_enterprise as rxe
import logging

from datetime import datetime, timezone
from typing import TypedDict
from urllib.parse import urlsplit
from reflex_enterprise.auth import User
from sqlalchemy import text
from app.services.usage import sync_usage, verify_access


class RecentProject(TypedDict):
    id: str
    title: str
    status: str
    message: str
    progress: int
    duration: int
    created: str
    video_url: str


class DashboardState(rx.State):
    loading: bool = True
    ready: bool = False
    error: str = ""
    display_name: str = ""
    plan: str = ""
    allowance: int = 0
    used: int = 0
    reserved: int = 0
    remaining: int = 0
    reset_date: str = ""
    period_label: str = "month"
    billing_warning: str = ""
    verification_label: str = "Free access only"
    exhausted_message: str = ""
    refreshed_at: str = ""
    projects: list[RecentProject] = []
    panel: str = ""

    @rxe.event
    def open_panel(self, panel: str):
        if panel == "plans":
            self.panel = panel

    @rxe.event
    def close_panel(self):
        self.panel = ""

    @rxe.event
    async def load_dashboard(self):
        self.loading = True
        self.ready = False
        self.error = ""
        self.projects = []
        self.plan = ""
        self.display_name = ""
        self.allowance = self.used = self.reserved = self.remaining = 0
        self.reset_date = ""
        self.billing_warning = ""
        self.verification_label = "Free access only"
        self.period_label = "month"
        self.exhausted_message = ""
        self.refreshed_at = ""
        self.panel = ""
        yield
        try:
            user = await User.current() or {}
            subject = user.get("sub")
            if not isinstance(subject, str) or not subject.strip():
                self.error = "Your sign-in could not be confirmed. Please sign out and sign in again."
                return
            access = await verify_access()
            async with rx.asession() as session:
                profile = (
                    await session.execute(
                        text("""
                    SELECT onboarding_completed FROM creator_profiles
                    WHERE identity_subject = :subject FOR UPDATE
                """),
                        {"subject": subject},
                    )
                ).first()
                if profile is None or not profile[0]:
                    yield rx.redirect("/onboarding")
                    return
                now = datetime.now(timezone.utc)
                snapshot = await sync_usage(session, access)
                row = (
                    await session.execute(
                        text(
                            "SELECT display_name FROM creator_profiles WHERE identity_subject = :subject"
                        ),
                        {"subject": subject},
                    )
                ).one()
                rows = (
                    await session.execute(
                        text("""
                    SELECT id, title, status, status_message, COALESCE(progress_percent, 0),
                        COALESCE(target_duration_seconds, 30), created_at, output_video_url
                    FROM video_projects WHERE owner_subject = :subject
                    ORDER BY created_at DESC, id DESC LIMIT 8
                """),
                        {"subject": subject},
                    )
                ).all()
                await session.commit()
            self.display_name = str(row[0] or "Creator")
            self.plan = access.tier.title()
            self.allowance = access.limit
            self.used = snapshot.used
            self.reserved = snapshot.reserved
            self.remaining = snapshot.remaining
            self.reset_date = snapshot.reset_at.strftime("%b %d, %Y at %H:%M")
            self.period_label = access.period_label
            self.billing_warning = access.warning
            self.verification_label = (
                "Subscription verified with RevenueCat"
                if access.verified and access.tier != "free"
                else "Free access · subscription checked"
                if access.verified
                else "Free access only · paid status unverified"
            )
            self.exhausted_message = access.exhausted_message
            projects: list[RecentProject] = []
            for project in rows:
                url = str(project[7] or "")
                parsed = urlsplit(url)
                safe_url = (
                    url
                    if (parsed.scheme in ("https", "http") and parsed.netloc)
                    or (
                        url.startswith("/uploaded_files/") and not parsed.netloc
                    )
                    else ""
                )
                projects.append(
                    {
                        "id": str(project[0]),
                        "title": str(project[1] or "Untitled short"),
                        "status": str(project[2] or "draft"),
                        "message": str(project[3] or ""),
                        "progress": int(project[4]),
                        "duration": int(project[5]),
                        "created": project[6].strftime("%b %d, %Y")
                        if project[6]
                        else "",
                        "video_url": safe_url,
                    }
                )
            self.projects = projects
            self.refreshed_at = now.strftime("%H:%M UTC")
            self.ready = True
        except Exception as e:
            logging.exception(f"Error: {e}")
            self.error = "We couldn't load your dashboard. Your saved projects are safe. Please try again."
        finally:
            self.loading = False
