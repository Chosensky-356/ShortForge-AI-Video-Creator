import reflex as rx
import reflex_enterprise as rxe

import asyncio
import logging
from typing import Any

from app.services.ten_generation import (
    BatchCard,
    BatchHistory,
    create_batch,
    load_batch,
    load_history,
    owned_render_brief,
    concept_provider_status,
)
from app.services.short_generation import (
    ShortBrief,
    generate_short,
    provider_status,
    recover_interrupted,
    safe_error,
)
from app.services.usage import UsageError, sync_usage, verify_access


class TenState(rx.State):
    loading: bool = True
    ready: bool = False
    busy: bool = False
    _running: bool = False
    error: str = ""
    notice: str = ""
    warning: str = ""
    setup: str = ""
    concepts_available: bool = False
    render_available: bool = False
    remaining: int = 0
    plan: str = "Free"
    batch_id: str = ""
    selected_id: str = ""
    cards: list[BatchCard] = []
    history: list[BatchHistory] = []
    history_page: int = 0
    has_next: bool = False
    batch_active: bool = False
    idea: str = ""
    duration: str = "30"
    style: str = "Cinematic"
    voice: str = "alloy"
    caption_style: str = "Classic"
    progress: int = 0
    stage: str = ""
    task: str = ""

    @rxe.event
    def load_creator(self):
        self.batch_id = self.router.url.query_parameters.get("batch", "")
        self.history_page = 0
        self.error = ""
        self.loading = True
        return TenState.refresh

    @rxe.event
    def open_batch(self, batch_id: str):
        if not self.busy:
            return rx.redirect(f"/create/ten?batch={batch_id}")

    @rxe.event
    def history_next(self):
        if self.has_next and not self.loading:
            self.history_page += 1
            return TenState.refresh

    @rxe.event
    def history_previous(self):
        if self.history_page > 0 and not self.loading:
            self.history_page -= 1
            return TenState.refresh

    @rxe.event(background=True)
    async def refresh(self):
        async with self:
            self.loading = True
            batch_id, page = self.batch_id, self.history_page
        try:
            access = await verify_access()
            await recover_interrupted()
            async with rx.asession() as session, session.begin():
                snapshot = await sync_usage(session, access)
            history, has_next = await load_history(page)
            if not batch_id and history:
                batch_id = history[0]["id"]
            cards = await load_batch(batch_id) if batch_id else []
            concepts_available, concept_message = concept_provider_status()
            render_available, render_message = await asyncio.to_thread(
                provider_status
            )
            async with self:
                self.plan = access.tier.title()
                self.remaining = snapshot.remaining
                self.warning = access.warning
                self.concepts_available = concepts_available
                self.render_available = render_available
                self.setup = (
                    concept_message
                    if not concepts_available
                    else render_message
                )
                self.history, self.has_next = history, has_next
                self.batch_id, self.cards = batch_id, cards
                self.batch_active = any(
                    card["status"] in ("queued", "generating", "rendering")
                    for card in cards
                )
                self.ready = True
        except Exception as e:
            logging.exception(
                f"Error: batch refresh failed ({type(e).__name__})"
            )
            async with self:
                self.error = (
                    str(e)
                    if isinstance(e, UsageError)
                    else "We couldn't refresh your saved concepts or allowance. Please try again."
                )
                self.ready = False
        finally:
            async with self:
                self.loading = False

    @rxe.event
    def submit(self, form_data: dict[str, Any]):
        if self.busy or self.loading or not self.ready:
            return
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
        self.error = self.notice = ""
        self.busy = True
        self.task = "concepts"
        self.progress = 0
        self.stage = "Writing ten distinct editorial concepts. No video credit is reserved…"
        return TenState.run_task

    @rxe.event
    def select_one(self, project_id: str):
        if self.busy or self.loading or not self.ready:
            return
        self.selected_id = project_id
        self.task = "render"
        self.error = self.notice = ""
        self.busy = True
        self.progress = 0
        self.stage = "Checking this saved draft and reserving one video…"
        return TenState.run_task

    @rxe.event(background=True)
    async def run_task(self):
        async with self:
            if self._running or not self.busy:
                return
            self._running = True
            task, batch_id, project_id = (
                self.task,
                self.batch_id,
                self.selected_id,
            )
            idea, duration, style, voice, captions = (
                self.idea,
                self.duration,
                self.style,
                self.voice,
                self.caption_style,
            )

        async def update(percent: int, stage: str):
            async with self:
                self.progress, self.stage = percent, stage
                self.cards = [
                    {
                        **card,
                        "progress": percent,
                        "message": stage,
                        "status": "rendering"
                        if percent >= 82
                        else "generating",
                    }
                    if card["id"] == project_id
                    else card
                    for card in self.cards
                ]
                self.batch_active = True

        try:
            if task == "concepts":
                ShortBrief.validate_inputs(
                    idea, duration, style, voice, captions
                )
                brief = ShortBrief(idea, int(duration), style, voice, captions)
                batch_id = await create_batch(brief)
                async with self:
                    self.batch_id = batch_id
                    self.history_page = 0
                    self.notice = "All ten concepts are saved as drafts. Choose just one to render; no credits were used to save them."
                    self.progress = 100
                    self.stage = "Ten concepts saved."
                yield rx.redirect(f"/create/ten?batch={batch_id}")
            elif task == "render":
                brief = await owned_render_brief(project_id, batch_id)
                available, message = await asyncio.to_thread(provider_status)
                if not available:
                    raise UsageError(message)
                await generate_short(project_id, brief, update)
                async with self:
                    self.notice = "Your verified MP4 is saved. One video credit was charged; the other concepts remain unchanged."
                    self.progress = 100
                    self.stage = "Selected Short completed."
            else:
                raise UsageError("Choose a saved concept before rendering.")
        except Exception as e:
            logging.exception(f"Error: batch task failed ({type(e).__name__})")
            async with self:
                self.error = safe_error(e)
                self.stage = "Stopped. Refresh for saved status and allowance."
        finally:
            async with self:
                self.busy = False
                self._running = False
        yield TenState.refresh
