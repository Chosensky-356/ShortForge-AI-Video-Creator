import reflex as rx
import reflex_enterprise as rxe
import asyncio
import http.client
import ipaddress
import logging
import socket
import ssl

from pathlib import Path
from typing import Any, TypedDict
from urllib.parse import unquote, urlsplit
from uuid import UUID
from reflex_enterprise.auth import User
from sqlalchemy import text
from app.services.usage import UsageError, delete_project
from app.services.analytics import record_event


class LibraryProject(TypedDict):
    id: str
    title: str
    project_type: str
    created: str
    status: str
    thumbnail_url: str
    thumbnail_file: str
    video_url: str
    video_file: str
    media_note: str


class VideosState(rx.State):
    projects: list[LibraryProject] = []
    loading: bool = True
    ready: bool = False
    busy: bool = False
    error: str = ""
    notice: str = ""
    tab: str = "all"
    page: int = 0
    has_next: bool = False
    modal: str = ""
    selected_id: str = ""
    selected_title: str = ""
    selected_script: str = ""
    selected_updated: str = ""
    modal_error: str = ""

    async def _subject(self) -> str:
        user = await User.current() or {}
        subject = user.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            raise ValueError("Sign-in could not be confirmed")
        return subject

    def _project_id(self, value: str) -> str:
        if not isinstance(value, str) or len(value) != 36:
            raise ValueError("Invalid project ID")
        parsed = str(UUID(value))
        if parsed != value.lower():
            raise ValueError("Invalid project ID")
        return parsed

    def _media_location(self, value: str, mp4: bool = False) -> tuple[str, str]:
        if not value or len(value) > 8192:
            return "", ""
        decoded = unquote(value)
        if (
            any(ord(c) < 32 or ord(c) == 127 for c in decoded)
            or "\\" in decoded
        ):
            return "", ""
        try:
            parsed = urlsplit(value)
            if parsed.fragment or parsed.username or parsed.password:
                return "", ""
            if mp4 and not unquote(parsed.path).lower().endswith(".mp4"):
                return "", ""
            if (
                parsed.path.startswith("/uploaded_files/")
                and not parsed.scheme
                and not parsed.netloc
            ):
                name = unquote(parsed.path.removeprefix("/uploaded_files/"))
                if (
                    parsed.query
                    or not name
                    or any(p in ("", ".", "..") for p in name.split("/"))
                ):
                    return "", ""
                root = rx.get_upload_dir().resolve()
                path = (root / name).resolve()
                if (
                    not path.is_relative_to(root)
                    or not path.is_file()
                    or path.stat().st_size == 0
                ):
                    return "", ""
                return "", name
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.port not in (None, 443)
            ):
                return "", ""
            host = parsed.hostname.lower()
            if (
                host == "localhost"
                or host.endswith((".localhost", ".local", ".internal"))
                or "." not in host
            ):
                return "", ""
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                address = None
            if address is not None and not address.is_global:
                return "", ""
            return value, ""
        except (ValueError, OSError):
            logging.exception("Unexpected error")
            return "", ""

    def _remote_mp4_exists(self, url: str) -> bool:
        parsed = urlsplit(url)
        host = parsed.hostname
        if not host:
            return False
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        if not addresses or any(
            not ipaddress.ip_address(a[4][0]).is_global for a in addresses
        ):
            return False
        connection = http.client.HTTPSConnection(host, timeout=6)
        raw = socket.create_connection((addresses[0][4][0], 443), timeout=6)
        try:
            connection.sock = ssl.create_default_context().wrap_socket(
                raw, server_hostname=host
            )
            target = parsed.path or "/"
            if parsed.query:
                target = f"{target}?{parsed.query}"
            connection.request("HEAD", target, headers={"Accept": "video/mp4"})
            response = connection.getresponse()
            mime = (
                response.getheader("Content-Type", "")
                .split(";")[0]
                .strip()
                .lower()
            )
            size = response.getheader("Content-Length", "")
            return (
                response.status == 200 and mime == "video/mp4" and size != "0"
            )
        finally:
            connection.close()
            raw.close()

    async def _checked_media(self, value: str) -> tuple[str, str]:
        url, filename = await asyncio.to_thread(
            self._media_location, value, True
        )
        if url:
            try:
                exists = await asyncio.wait_for(
                    asyncio.to_thread(self._remote_mp4_exists, url), timeout=9
                )
                if not exists:
                    return "", ""
            except Exception as e:
                logging.exception(f"Error: {e}")
                return "", ""
        return url, filename

    @rxe.event
    def change_tab(self, tab: str):
        if (
            tab in ("all", "short", "product_ad", "ugc_ad")
            and not self.loading
            and not self.busy
        ):
            self.tab = tab
            self.page = 0
            self.notice = ""
            return VideosState.refresh

    @rxe.event
    def next_page(self):
        if self.has_next and not self.loading:
            self.page += 1
            return VideosState.refresh

    @rxe.event
    def previous_page(self):
        if self.page > 0 and not self.loading:
            self.page -= 1
            return VideosState.refresh

    @rxe.event
    def load_library(self):
        self.page = 0
        self.tab = "all"
        self.notice = ""
        self.modal = ""
        self.selected_id = ""
        return VideosState.refresh

    @rxe.event
    async def refresh(self):
        self.loading = True
        self.ready = False
        self.error = ""
        self.projects = []
        self.has_next = False
        yield
        try:
            subject = await self._subject()
            async with rx.asession() as session:
                profile = (
                    await session.execute(
                        text(
                            "SELECT onboarding_completed FROM creator_profiles WHERE identity_subject = :subject LIMIT 1"
                        ),
                        {"subject": subject},
                    )
                ).one_or_none()
                if profile is None or not profile[0]:
                    yield rx.redirect("/onboarding")
                    return
                rows = (
                    await session.execute(
                        text("""
                    SELECT id, title, project_type, created_at, status,
                           thumbnail_url, output_video_url
                    FROM video_projects
                    WHERE owner_subject = :subject
                      AND (:kind = 'all' OR project_type = :kind)
                    ORDER BY created_at DESC, id DESC LIMIT 13 OFFSET :offset
                """),
                        {
                            "subject": subject,
                            "kind": self.tab,
                            "offset": self.page * 12,
                        },
                    )
                ).all()
            self.has_next = len(rows) > 12
            rows = rows[:12]
            media = await asyncio.gather(
                *(self._checked_media(str(row[6] or "")) for row in rows)
            )
            projects: list[LibraryProject] = []
            for row, (video_url, video_file) in zip(rows, media):
                thumbnail_url, thumbnail_file = await asyncio.to_thread(
                    self._media_location, str(row[5] or "")
                )
                projects.append(
                    {
                        "id": str(row[0]),
                        "title": str(row[1] or "Untitled video"),
                        "project_type": str(row[2] or "short"),
                        "created": row[3].strftime("%b %d, %Y")
                        if row[3]
                        else "Date unavailable",
                        "status": str(row[4] or "draft"),
                        "thumbnail_url": thumbnail_url,
                        "thumbnail_file": thumbnail_file,
                        "video_url": video_url,
                        "video_file": video_file,
                        "media_note": ""
                        if video_url or video_file
                        else (
                            "Attached output could not be verified as an accessible, safe MP4. Preview and download are unavailable."
                            if row[6]
                            else "No rendered MP4 is attached to this project yet."
                        ),
                    }
                )
            self.projects = projects
            self.ready = True
        except Exception as e:
            logging.exception(f"Error: {e}")
            self.error = "We couldn't load your videos. Please try again."
        finally:
            self.loading = False

    @rxe.event
    async def open_project(self, project_id: str, action: str):
        if self.busy or action not in ("edit", "delete", "regenerate"):
            return
        self.busy = True
        self.modal_error = ""
        self.notice = ""
        yield
        try:
            subject = await self._subject()
            project_id = self._project_id(project_id)
            async with rx.asession() as session:
                row = (
                    await session.execute(
                        text("""
                    SELECT title, script, updated_at FROM video_projects
                    WHERE id = :id AND owner_subject = :subject LIMIT 1
                """),
                        {"id": project_id, "subject": subject},
                    )
                ).one_or_none()
            if row is None:
                self.error = (
                    "This project is no longer available. Refresh your library."
                )
                return
            self.selected_id = project_id
            self.selected_title = str(row[0] or "Untitled video")
            self.selected_script = str(row[1] or "")
            self.selected_updated = row[2].isoformat() if row[2] else ""
            self.modal = action
        except Exception as e:
            logging.exception(f"Error: {e}")
            self.error = "We couldn't open this project. Refresh and try again."
        finally:
            self.busy = False

    @rxe.event
    def close_modal(self):
        if not self.busy:
            self.modal = ""
            self.selected_id = ""
            self.selected_title = ""
            self.selected_script = ""
            self.selected_updated = ""
            self.modal_error = ""

    @rxe.event
    async def save_edits(self, form_data: dict[str, Any]):
        if self.busy or self.modal != "edit":
            return
        title = str(form_data.get("title", "")).strip()
        script = str(form_data.get("script", ""))
        self.selected_title = title
        self.selected_script = script
        if (
            not title
            or len(title) > 200
            or len(script) > 50000
            or "\x00" in title
            or "\x00" in script
        ):
            self.modal_error = "Enter a title of 1–200 characters and a script of at most 50,000 characters."
            return
        self.busy = True
        self.modal_error = ""
        yield
        try:
            subject = await self._subject()
            project_id = self._project_id(self.selected_id)
            async with rx.asession() as session:
                result = await session.execute(
                    text("""
                    UPDATE video_projects SET title = :title, script = :script,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :id AND owner_subject = :subject
                      AND updated_at = CAST(:updated AS TIMESTAMP WITH TIME ZONE)
                """),
                    {
                        "id": project_id,
                        "subject": subject,
                        "title": title,
                        "script": script,
                        "updated": self.selected_updated,
                    },
                )
                if result.rowcount != 1:
                    await session.rollback()
                    self.modal_error = "The project changed or is no longer available. Close and reopen it before saving."
                    return
                await session.commit()
            self.modal = ""
            self.selected_id = ""
            self.notice = "Title and script saved. Existing video, captions and audio were not changed."
            yield VideosState.refresh
        except Exception as e:
            logging.exception(f"Error: {e}")
            self.modal_error = (
                "Your changes could not be saved. Please try again."
            )
        finally:
            self.busy = False

    @rxe.event
    async def confirm_delete(self):
        if self.busy or self.modal != "delete":
            return
        self.busy = True
        self.modal_error = ""
        yield
        try:
            project_id = self._project_id(self.selected_id)
            if not await delete_project(project_id):
                self.modal_error = "This project is no longer available. Close and refresh the library."
                return
            self.modal = ""
            self.selected_id = ""
            self.notice = "Project deleted from your library."
            if len(self.projects) == 1 and self.page > 0:
                self.page -= 1
            yield VideosState.refresh
        except UsageError as e:
            logging.exception("Unexpected error")
            self.modal_error = str(e)
        except Exception as e:
            logging.exception(f"Error: {e}")
            self.modal_error = (
                "The project could not be deleted. Please try again."
            )
        finally:
            self.busy = False

    @rxe.event
    async def download_mp4(self, project_id: str):
        if self.busy:
            return
        self.busy = True
        self.notice = "Checking your MP4…"
        yield
        try:
            subject = await self._subject()
            project_id = self._project_id(project_id)
            async with rx.asession() as session:
                row = (
                    await session.execute(
                        text(
                            "SELECT output_video_url FROM video_projects WHERE id = :id AND owner_subject = :subject LIMIT 1"
                        ),
                        {"id": project_id, "subject": subject},
                    )
                ).one_or_none()
            if row is None:
                self.notice = "This project is no longer available."
                return
            url, filename = await self._checked_media(str(row[0] or ""))
            if filename:
                path = (rx.get_upload_dir() / filename).resolve()
                if path.stat().st_size > 64 * 1024 * 1024:
                    self.notice = (
                        "This local video exceeds the 64 MB download limit."
                    )
                    return
                data = await asyncio.to_thread(Path.read_bytes, path)
                self.notice = "MP4 download requested."
                yield rx.download(
                    data=data, filename=f"shortforge-{project_id}.mp4"
                )
                await record_event("downloaded", project_id)
            elif url:
                self.notice = "MP4 download requested. If your browser blocks the remote download, use the video's download control."
                yield rx.download(
                    url=url, filename=f"shortforge-{project_id}.mp4"
                )
                await record_event("downloaded", project_id)
            else:
                self.notice = (
                    "No accessible, verified MP4 is available for download."
                )
        except Exception as e:
            logging.exception(f"Error: {e}")
            self.notice = "The download could not be started. Please try again."
        finally:
            self.busy = False
