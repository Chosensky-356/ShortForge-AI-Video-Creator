import reflex as rx
import reflex_enterprise as rxe

import asyncio
import logging
from typing import Any

from app.services.short_generation import (
    ShortBrief,
    create_draft,
    generate_short,
    provider_status,
    recover_interrupted,
)
from app.services.usage import UsageError, sync_usage, verify_access


class ShortState(rx.State):
    loading: bool = True
    ready: bool = False
    busy: bool = False
    error: str = ""
    warning: str = ""
    setup: str = ""
    available: bool = False
    remaining: int = 0
    plan: str = "Free"
    progress: int = 0
    stage: str = ""
    idea: str = ""
    duration: str = "30"
    style: str = "Cinematic"
    voice: str = "alloy"
    caption_style: str = "Classic"
    project_id: str = ""
    output_file: str = ""
    output_title: str = ""
    output_script: str = ""
    output_seconds: float = 0.0

    @rxe.event
    async def load_creator(self):
        if self.busy:
            return
        self.loading = True
        self.ready = False
        self.error = ""
        yield
        try:
            access = await verify_access()
            await recover_interrupted()
            async with rx.asession() as session:
                snapshot = await sync_usage(session, access)
                await session.commit()
            self.plan = access.tier.title()
            self.remaining = snapshot.remaining
            self.warning = access.warning
            self.available, self.setup = await asyncio.to_thread(
                provider_status
            )
            self.ready = True
        except UsageError as e:
            logging.exception(f"Error: {e}")
            self.error = str(e)
            yield rx.redirect("/onboarding")
        except Exception as e:
            logging.exception(
                f"Error: creator loading failed ({type(e).__name__})"
            )
            self.error = (
                "We couldn't check your allowance. Please reload the creator."
            )
        finally:
            self.loading = False

    @rxe.event
    async def submit(self, form_data: dict[str, Any]):
        if self.busy or self.loading:
            return
        self.error = ""
        self.idea = str(form_data.get("idea", "")).strip()
        self.duration = str(form_data.get("duration", "30"))
        self.style = str(form_data.get("style", "Cinematic"))
        self.voice = str(form_data.get("voice", "alloy"))
        self.caption_style = str(form_data.get("captions", "Classic"))
        try:
            ShortBrief.validate_inputs(
                self.idea,
                self.duration,
                self.style,
                self.voice,
                self.caption_style,
            )
        except ValueError as e:
            logging.exception(f"Error: {e}")
            self.error = str(e)
            return
        self.busy = True
        self.progress = 0
        self.stage = "Saving your idea and reserving one video…"
        self.output_file = ""
        self.output_title = ""
        self.output_script = ""
        self.output_seconds = 0.0
        self.project_id = ""
        yield ShortState.run_generation

    @rxe.event(background=True)
    async def run_generation(self):
        async with self:
            if not self.busy:
                return
            brief = ShortBrief(
                self.idea,
                int(self.duration),
                self.style,
                self.voice,
                self.caption_style,
            )

        async def update(progress: int, stage: str):
            async with self:
                self.progress = progress
                self.stage = stage

        try:
            project_id = await create_draft(brief)
            async with self:
                self.project_id = project_id
            result = await generate_short(project_id, brief, update)
            async with self:
                self.output_file = result.filename
                self.output_title = result.title
                self.output_script = result.script
                self.output_seconds = result.duration
                self.progress = 100
                self.stage = "Ready! Your Short is saved in My Videos."
        except Exception as e:
            logging.exception(
                f"Error: short generation failed ({type(e).__name__})"
            )
            from app.services.short_generation import safe_error

            async with self:
                self.error = safe_error(e)
                self.stage = "Generation stopped."
        finally:
            try:
                access = await verify_access()
                async with rx.asession() as session:
                    snapshot = await sync_usage(session, access)
                    await session.commit()
                async with self:
                    self.remaining = snapshot.remaining
                    self.warning = access.warning
            except Exception as e:
                logging.exception(
                    f"Error: allowance refresh failed ({type(e).__name__})"
                )
                async with self:
                    self.warning = "Allowance could not be refreshed. Reload before creating another Short."
            async with self:
                self.busy = False
