import reflex as rx
import reflex_enterprise as rxe

import asyncio
import json
import logging
from typing import Any, TypedDict
from uuid import UUID, uuid4

from sqlalchemy import text
from app.services.ad_generation import (
    AdError,
    validate_brief,
    save_photo,
    read_photo,
    generate_ad,
    safe_ad_error,
)
from app.services.usage import authenticated_subject


class StoryboardScene(TypedDict):
    purpose: str
    visual: str
    narration: str
    start: float
    end: float


class AdState(rx.State):
    kind: str = "product_ad"
    loading: bool = True
    busy: bool = False
    uploading: bool = False
    error: str = ""
    notice: str = ""
    stage: str = ""
    progress: int = 0
    photo_file: str = ""
    _photo_file: str = ""
    _photo_persisted: bool = False
    _photo_width: int = 0
    _photo_height: int = 0
    _photo_size: int = 0
    brief: dict[str, str] = {
        "product_name": "",
        "description": "",
        "audience": "",
        "problem": "",
        "benefit": "",
        "tone": "",
        "cta": "",
        "claims": "",
        "persona": "",
        "situation": "",
        "demonstration": "",
        "objection": "",
        "offer": "",
        "url": "",
        "duration": "30",
        "platform": "TikTok",
        "style": "Studio",
    }
    project_id: str = ""
    _attempt: str = ""
    _running: bool = False
    title: str = ""
    script: str = ""
    hook: str = ""
    cta: str = ""
    observations: str = ""
    claim_notes: str = ""
    scenes: list[StoryboardScene] = []
    brief_display: list[dict[str, str]] = []
    captions_display: str = ""
    detail_status: str = ""

    @rxe.event
    async def load_creator(self):
        if self.busy:
            return
        self.kind = (
            "ugc_ad"
            if self.router.page.path.rstrip("/").endswith("ugc")
            else "product_ad"
        )
        self.brief = {key: "" for key in self.brief}
        self.brief.update(
            duration="30",
            platform="TikTok",
            style="Casual" if self.kind == "ugc_ad" else "Studio",
        )
        self.title = self.script = self.project_id = self.photo_file = (
            self._photo_file
        ) = ""
        self.scenes = []
        self.notice = self.error = ""
        self.loading = True
        try:
            subject = await authenticated_subject()
            async with rx.asession() as session:
                profile = (
                    await session.execute(
                        text(
                            "SELECT onboarding_completed FROM creator_profiles WHERE identity_subject = :subject LIMIT 1"
                        ),
                        {"subject": subject},
                    )
                ).scalar_one_or_none()
                if not profile:
                    yield rx.redirect("/onboarding")
                    return
                await self._recover(session, subject)
                await session.commit()
        except Exception as e:
            logging.exception(f"Error: ad creator loading ({type(e).__name__})")
            self.error = "Could not load the creator. Please refresh."
        finally:
            self.loading = False

    async def _recover(self, session, subject: str):
        await session.execute(
            text("""
            UPDATE video_projects SET generation_stage = 'ad_interrupted',
                status_message = 'Draft writing was interrupted. Brief and uploaded photo are saved; no video credits used.',
                error_code = 'ad_interrupted', progress_percent = 0, updated_at = CURRENT_TIMESTAMP
            WHERE owner_subject = :subject AND project_type IN ('product_ad', 'ugc_ad')
                AND status = 'draft' AND generation_stage = 'ad_writing'
                AND updated_at < CURRENT_TIMESTAMP - INTERVAL '5 minutes'
        """),
            {"subject": subject},
        )

    @rxe.event
    async def upload_photo(self, files: list[rx.UploadFile]):
        if self.busy or self.loading or self.uploading:
            return
        self.error = ""
        self.uploading = True
        self.stage = "Validating and decoding your product photo…"
        yield
        try:
            await authenticated_subject()
            if len(files) != 1:
                raise AdError("Select exactly one product photo.")
            data = await files[0].read(8 * 1024 * 1024 + 1)
            filename, width, height, size = await asyncio.to_thread(
                save_photo, data
            )
            old = self._photo_file
            old_persisted = self._photo_persisted
            self._photo_file = self.photo_file = filename
            self._photo_width, self._photo_height, self._photo_size = (
                width,
                height,
                size,
            )
            self._photo_persisted = False
            self.notice = f"Photo ready · {width} × {height} · metadata removed. It is saved to a project only when you submit a valid brief."
            if old and not old_persisted:
                await asyncio.to_thread(
                    (rx.get_upload_dir() / old).unlink, missing_ok=True
                )
            yield rx.clear_selected_files("ad-photo")
        except Exception as e:
            logging.exception(f"Error: photo validation ({type(e).__name__})")
            self.error = safe_ad_error(e)
        finally:
            self.uploading = False
            self.stage = ""

    @rxe.event
    async def submit(self, form_data: dict[str, Any]):
        if self.busy or self.loading or self.uploading:
            return
        self.error = self.notice = ""
        try:
            brief = validate_brief(form_data, self.kind)
            if not self._photo_file:
                raise AdError("Upload a product photo before saving the brief.")
            await asyncio.to_thread(read_photo, self._photo_file)
            subject = await authenticated_subject()
            project_id, token = str(uuid4()), uuid4().hex
            settings = {
                "workflow": "ad_draft_v1",
                "brief": brief,
                "attempt": token,
                "image_source": "user_upload",
                "rendered": False,
            }
            async with rx.asession() as session, session.begin():
                profile = (
                    await session.execute(
                        text(
                            "SELECT onboarding_completed FROM creator_profiles WHERE identity_subject = :subject FOR UPDATE"
                        ),
                        {"subject": subject},
                    )
                ).scalar_one_or_none()
                if not profile:
                    raise AdError(
                        "Complete onboarding before saving an ad draft."
                    )
                await session.execute(
                    text("""
                    INSERT INTO video_projects (id, owner_subject, project_type, title, idea, style,
                        target_duration_seconds, status, generation_stage, status_message,
                        generation_settings, scenes, captions, music, thumbnail_url)
                    VALUES (:id, :subject, :kind, :title, :idea, :style, :duration, 'draft',
                        'ad_writing', 'Brief saved. Writing an image-grounded ad draft; no video credits used.',
                        CAST(:settings AS JSONB), '[]'::jsonb, '[]'::jsonb, '{}'::jsonb, :thumbnail)
                """),
                    {
                        "id": project_id,
                        "subject": subject,
                        "kind": self.kind,
                        "title": brief["product_name"],
                        "idea": brief["description"],
                        "style": brief["style"],
                        "duration": int(brief["duration"]),
                        "settings": json.dumps(settings),
                        "thumbnail": f"/uploaded_files/{self._photo_file}",
                    },
                )
                await session.execute(
                    text("""
                    INSERT INTO generated_assets (id, project_id, asset_type, status, url, mime_type,
                        byte_size, provider, metadata)
                    VALUES (:id, :project, 'image', 'ready', :url, 'image/png', :size,
                        'user_upload', CAST(:metadata AS JSONB))
                """),
                    {
                        "id": str(uuid4()),
                        "project": project_id,
                        "url": f"/uploaded_files/{self._photo_file}",
                        "size": self._photo_size,
                        "metadata": json.dumps(
                            {
                                "source": "user_upload",
                                "filename": self._photo_file,
                                "width": self._photo_width,
                                "height": self._photo_height,
                                "byte_size": self._photo_size,
                                "metadata_removed": True,
                            }
                        ),
                    },
                )
            self.brief = {**self.brief, **brief}
            self.project_id, self._attempt = project_id, token
            self._photo_persisted = True
            self.title = self.script = ""
            self.scenes = []
            self.busy = True
            self.progress = 20
            self.stage = (
                "Brief saved. Reading the photo and writing your script…"
            )
            yield AdState.write_draft
        except Exception as e:
            logging.exception(f"Error: ad brief save ({type(e).__name__})")
            self.error = safe_ad_error(e)

    @rxe.event(background=True)
    async def write_draft(self):
        async with self:
            if not self.busy or self._running:
                return
            self._running = True
            brief, kind, filename = (
                dict(self.brief),
                self.kind,
                self._photo_file,
            )
            project_id, token = self.project_id, self._attempt
        try:
            subject = await authenticated_subject()
            spec = await asyncio.wait_for(
                asyncio.to_thread(generate_ad, brief, kind, filename),
                timeout=65,
            )
            async with self:
                self.progress = 85
                self.stage = "Validating the storyboard and saving your draft…"
            settings = {
                "workflow": "ad_draft_v1",
                "brief": validate_brief(brief, kind),
                "attempt": token,
                "image_source": "user_upload",
                "rendered": False,
                "image_observations": spec.image_observations,
                "claim_notes": spec.claim_notes,
                "timing": "estimated; no footage or audio rendered",
            }
            async with rx.asession() as session, session.begin():
                row = (
                    await session.execute(
                        text("""
                    UPDATE video_projects SET title = :title, hook = :hook, script = :script,
                        voiceover_text = :voiceover, cta = :cta, scenes = CAST(:scenes AS JSONB),
                        captions = CAST(:captions AS JSONB), generation_settings = CAST(:settings AS JSONB),
                        generation_stage = 'ad_draft_ready', progress_percent = 100,
                        status_message = 'Script and storyboard ready. No MP4 or avatar rendered; no video credits used.',
                        error_code = '', error_message = '', updated_at = CURRENT_TIMESTAMP
                    WHERE id = :id AND owner_subject = :subject AND status = 'draft'
                        AND generation_stage = 'ad_writing' AND generation_settings->>'attempt' = :token
                    RETURNING id
                """),
                        {
                            "id": project_id,
                            "subject": subject,
                            "token": token,
                            "title": spec.title,
                            "hook": spec.hook,
                            "script": spec.script,
                            "voiceover": spec.voiceover_text,
                            "cta": spec.cta,
                            "scenes": json.dumps(
                                [s.model_dump() for s in spec.scenes]
                            ),
                            "captions": json.dumps(
                                [c.model_dump() for c in spec.captions]
                            ),
                            "settings": json.dumps(settings),
                        },
                    )
                ).scalar_one_or_none()
                if row is None:
                    raise AdError(
                        "This draft changed or was deleted. Open My Videos to check its saved state."
                    )
            async with self:
                self.title, self.script, self.hook, self.cta = (
                    spec.title,
                    spec.script,
                    spec.hook,
                    spec.cta,
                )
                self.scenes = [s.model_dump() for s in spec.scenes]
                self.observations, self.claim_notes = (
                    spec.image_observations,
                    spec.claim_notes,
                )
                self.captions_display = "\n".join(
                    f"{c.start:.1f}–{c.end:.1f}s · {c.text}"
                    for c in spec.captions
                )
                self.progress = 100
                self.stage = "Draft ready and saved in My Videos."
                self.notice = self.stage
        except BaseException as e:
            logging.exception(f"Error: ad draft writing ({type(e).__name__})")
            message = safe_ad_error(e)
            try:
                subject = await authenticated_subject()
                async with rx.asession() as session, session.begin():
                    await session.execute(
                        text("""
                        UPDATE video_projects SET generation_stage = 'ad_stopped', status_message = :message,
                            error_code = 'ad_draft_stopped', error_message = :message, progress_percent = 0,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = :id AND owner_subject = :subject AND status = 'draft'
                            AND generation_stage = 'ad_writing' AND generation_settings->>'attempt' = :token
                    """),
                        {
                            "id": project_id,
                            "subject": subject,
                            "token": token,
                            "message": message,
                        },
                    )
            except Exception as failure:
                logging.exception(
                    f"Error: ad failure persistence ({type(failure).__name__})"
                )
                message = "Draft writing stopped; saved status could not be confirmed. Refresh My Videos before retrying. No video credit used."
            async with self:
                self.error = message
                self.stage = "Draft writing stopped."
            if isinstance(e, asyncio.CancelledError):
                raise
        finally:
            async with self:
                self.busy = self._running = False

    @rxe.event
    async def load_detail(self):
        if self.busy:
            return
        self.loading = True
        self.title = self.script = self.photo_file = self.error = (
            self.notice
        ) = ""
        self.scenes = []
        self.brief_display = []
        try:
            subject = await authenticated_subject()
            project_id = str(
                UUID(str(self.router.page.params.get("ad_id", "")))
            )
            async with rx.asession() as session:
                await self._recover(session, subject)
                row = (
                    await session.execute(
                        text("""
                    SELECT title, script, hook, cta, scenes, captions, generation_settings, status_message, project_type
                    FROM video_projects WHERE id = :id AND owner_subject = :subject
                        AND project_type IN ('product_ad', 'ugc_ad') LIMIT 1
                """),
                        {"id": project_id, "subject": subject},
                    )
                ).one_or_none()
                asset = (
                    await session.execute(
                        text("""
                    SELECT a.metadata FROM generated_assets a JOIN video_projects p ON p.id = a.project_id
                    WHERE p.id = :id AND p.owner_subject = :subject AND a.asset_type = 'image'
                        AND a.provider = 'user_upload' ORDER BY a.created_at DESC LIMIT 1
                """),
                        {"id": project_id, "subject": subject},
                    )
                ).scalar_one_or_none()
                await session.commit()
            if row is None:
                raise AdError(
                    "This ad draft is unavailable or does not belong to your account."
                )
            self.project_id = project_id
            self.title, self.script, self.hook, self.cta = (
                str(v or "") for v in row[:4]
            )
            self.scenes = [
                {
                    "purpose": str(s.get("purpose", "")),
                    "visual": str(s.get("visual", "")),
                    "narration": str(s.get("narration", "")),
                    "start": float(s.get("start", 0)),
                    "end": float(s.get("end", 0)),
                }
                for s in (row[4] or [])[:4]
            ]
            settings = row[6] or {}
            self.brief_display = [
                {"label": key.replace("_", " ").title(), "value": str(value)}
                for key, value in settings.get("brief", {}).items()
            ]
            self.observations = str(settings.get("image_observations", ""))
            self.claim_notes = str(settings.get("claim_notes", ""))
            self.captions_display = "\n".join(
                f"{float(c.get('start', 0)):.1f}–{float(c.get('end', 0)):.1f}s · {c.get('text', '')}"
                for c in (row[5] or [])[:30]
            )
            self.detail_status, self.kind = str(row[7] or "Draft"), str(row[8])
            if asset and isinstance(asset.get("filename"), str):
                filename = asset["filename"]
                try:
                    await asyncio.to_thread(read_photo, filename)
                    self.photo_file = filename
                except Exception as e:
                    logging.exception(
                        f"Error: draft photo unavailable ({type(e).__name__})"
                    )
                    self.notice = "The uploaded photo is no longer available on this server. The saved script and brief remain available."
        except Exception as e:
            logging.exception(f"Error: ad detail ({type(e).__name__})")
            self.error = safe_ad_error(e)
        finally:
            self.loading = False
