import reflex as rx

from reflex_enterprise.auth import User
from app.components.dashboard import status_badge
from app.components.onboarding import brand
from app.states.videos_state import LibraryProject, VideosState


def library_header() -> rx.Component:
    return rx.el.header(
        brand(),
        rx.el.nav(
            rx.el.a(
                rx.icon("arrow-left", class_name="h-4 w-4"),
                "Dashboard",
                href="/",
                class_name="flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-white/60 hover:bg-white/5 hover:text-white focus-visible:outline-2 focus-visible:outline-violet-400",
            ),
            rx.el.a(
                "Plans",
                href="/plans",
                class_name="rounded-lg px-3 py-2 text-xs text-white/60 hover:bg-white/5 hover:text-white",
            ),
            rx.el.a(
                "Settings",
                href="/settings",
                class_name="rounded-lg px-3 py-2 text-xs text-white/60 hover:bg-white/5 hover:text-white",
            ),
            rx.el.button(
                "Sign out",
                on_click=User.logout,
                class_name="rounded-lg px-3 py-2 text-xs text-white/50 hover:bg-white/5 hover:text-white focus-visible:outline-2 focus-visible:outline-violet-400",
            ),
            aria_label="Main navigation",
            class_name="flex items-center gap-1",
        ),
        class_name="flex w-full flex-wrap items-center justify-between gap-3 border-b border-white/8 px-5 py-5 sm:px-8",
    )


def type_label(kind: rx.Var) -> rx.Component:
    return rx.el.span(
        rx.match(
            kind,
            ("short", "Short"),
            ("product_ad", "Product Ad"),
            ("ugc_ad", "UGC Ad"),
            "Video",
        ),
        class_name="text-xs font-medium text-[#A78BFA]",
    )


def library_tab(label: str, kind: str) -> rx.Component:
    return rx.el.button(
        label,
        on_click=lambda: VideosState.change_tab(kind),
        disabled=VideosState.loading | VideosState.busy,
        aria_pressed=VideosState.tab == kind,
        class_name=rx.cond(
            VideosState.tab == kind,
            "shrink-0 rounded-xl bg-violet-500/15 px-4 py-2.5 text-xs font-semibold text-[#C4B5FD] focus-visible:outline-2 focus-visible:outline-violet-400 disabled:opacity-50",
            "shrink-0 rounded-xl bg-transparent px-4 py-2.5 text-xs font-medium text-white/50 hover:bg-white/5 hover:text-white focus-visible:outline-2 focus-visible:outline-violet-400 disabled:opacity-50",
        ),
    )


def thumbnail(project: LibraryProject) -> rx.Component:
    return rx.el.div(
        rx.icon("film", class_name="h-9 w-9 text-[#A78BFA]/60"),
        rx.cond(
            (project["thumbnail_file"] != "")
            | (project["thumbnail_url"] != ""),
            rx.el.img(
                src=rx.cond(
                    project["thumbnail_file"] != "",
                    rx.get_upload_url(project["thumbnail_file"]),
                    project["thumbnail_url"],
                ),
                alt=f"Thumbnail for {project['title']}",
                loading="lazy",
                referrer_policy="no-referrer",
                class_name="absolute inset-0 h-full w-full object-cover text-xs text-white/50",
            ),
        ),
        class_name="relative flex aspect-video w-full items-center justify-center overflow-hidden rounded-xl border border-white/5 bg-[#0B0B10]",
    )


def library_card(project: LibraryProject) -> rx.Component:
    return rx.el.article(
        thumbnail(project),
        rx.el.div(
            type_label(project["project_type"]),
            status_badge(project["status"]),
            class_name="mt-4 flex flex-wrap items-center justify-between gap-2",
        ),
        rx.el.h2(
            project["title"],
            class_name="mt-3 break-words text-base font-semibold text-white",
        ),
        rx.el.p(project["created"], class_name="mt-1 text-xs text-white/40"),
        rx.cond(
            (project["video_url"] != "") | (project["video_file"] != ""),
            rx.el.details(
                rx.el.summary(
                    "Preview video",
                    class_name="cursor-pointer rounded-lg py-3 text-xs font-medium text-[#C4B5FD] focus-visible:outline-2 focus-visible:outline-violet-400",
                ),
                rx.el.video(
                    src=rx.cond(
                        project["video_file"] != "",
                        rx.get_upload_url(project["video_file"]),
                        project["video_url"],
                    ),
                    controls=True,
                    preload="none",
                    aria_label=f"Preview of {project['title']}",
                    class_name="max-h-96 w-full rounded-xl bg-black",
                ),
            ),
            rx.el.p(
                project["media_note"],
                class_name="mt-4 text-xs leading-relaxed text-white/45",
            ),
        ),
        rx.cond(
            (project["project_type"] == "product_ad")
            | (project["project_type"] == "ugc_ad"),
            rx.el.a(
                rx.icon("notebook-text", class_name="h-4 w-4"),
                "View script, storyboard & brief",
                href=f"/ads/{project['id']}",
                class_name="mt-4 flex items-center gap-2 rounded-xl bg-violet-500/10 px-3 py-3 text-xs text-[#C4B5FD] hover:bg-violet-500/20 focus-visible:outline-2 focus-visible:outline-violet-400",
            ),
        ),
        rx.el.div(
            rx.el.button(
                rx.icon("pencil", class_name="h-3.5 w-3.5"),
                "Edit text",
                on_click=lambda: VideosState.open_project(
                    project["id"], "edit"
                ),
                disabled=VideosState.busy,
                class_name="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/75 hover:bg-white/10 disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-violet-400",
            ),
            rx.el.button(
                rx.icon("download", class_name="h-3.5 w-3.5"),
                "MP4",
                on_click=lambda: VideosState.download_mp4(project["id"]),
                disabled=VideosState.busy
                | (
                    (project["video_url"] == "") & (project["video_file"] == "")
                ),
                title="Download verified MP4; unavailable when no accessible MP4 is attached",
                class_name="flex items-center gap-1.5 rounded-lg border border-white/10 bg-transparent px-3 py-2 text-xs text-white/60 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-30 focus-visible:outline-2 focus-visible:outline-violet-400",
            ),
            rx.el.button(
                rx.icon("rotate-cw", class_name="h-3.5 w-3.5"),
                "Regenerate?",
                on_click=lambda: VideosState.open_project(
                    project["id"], "regenerate"
                ),
                disabled=VideosState.busy,
                title="View why regeneration is currently unavailable",
                class_name="flex items-center gap-1.5 rounded-lg bg-transparent px-2 py-2 text-xs text-white/45 hover:bg-white/5 hover:text-white disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-violet-400",
            ),
            rx.el.button(
                rx.icon("trash-2", class_name="h-4 w-4"),
                on_click=lambda: VideosState.open_project(
                    project["id"], "delete"
                ),
                disabled=VideosState.busy,
                aria_label=f"Delete {project['title']}",
                class_name="ml-auto rounded-lg bg-transparent p-2 text-white/40 hover:bg-red-500/10 hover:text-red-400 disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-red-400",
            ),
            class_name="mt-4 flex flex-wrap items-center gap-2 border-t border-white/8 pt-4",
        ),
        key=project["id"],
        class_name="min-w-0 rounded-2xl border border-white/8 bg-[#13131C] p-4 sm:p-5",
    )


def edit_form() -> rx.Component:
    return rx.el.form(
        rx.el.p(
            "Manual text editing only. Saving will not re-render your video or change existing visuals, audio, scenes or captions. Use Create a Short for a new video; a full re-rendering editor is not available yet.",
            class_name="mb-5 rounded-xl border border-blue-400/15 bg-[#448BFF]/5 p-4 text-xs leading-relaxed text-white/60",
        ),
        rx.el.label(
            "Title",
            html_for="library-title",
            class_name="mb-2 block text-xs font-medium text-white/70",
        ),
        rx.el.input(
            id="library-title",
            name="title",
            required=True,
            max_length=200,
            default_value=VideosState.selected_title,
            key=VideosState.selected_title,
            auto_focus=True,
            class_name="w-full rounded-xl border border-white/15 bg-[#0B0B10] px-4 py-3 text-sm text-white focus:border-violet-400 focus:outline-hidden focus:ring-2 focus:ring-violet-400/20",
        ),
        rx.el.label(
            "Script",
            html_for="library-script",
            class_name="mb-2 mt-5 block text-xs font-medium text-white/70",
        ),
        rx.el.textarea(
            id="library-script",
            name="script",
            max_length=50000,
            default_value=VideosState.selected_script,
            key=VideosState.selected_script,
            placeholder="No script yet. Add your text here…",
            class_name="min-h-48 w-full resize-y rounded-xl border border-white/15 bg-[#0B0B10] px-4 py-3 text-sm leading-relaxed text-white placeholder:text-white/30 focus:border-violet-400 focus:outline-hidden focus:ring-2 focus:ring-violet-400/20",
        ),
        rx.el.div(
            rx.el.button(
                "Cancel",
                type="button",
                on_click=VideosState.close_modal,
                disabled=VideosState.busy,
                class_name="rounded-xl bg-white/5 px-4 py-3 text-xs text-white/70 hover:bg-white/10 disabled:opacity-40",
            ),
            rx.el.button(
                rx.cond(VideosState.busy, "Saving…", "Save text changes"),
                type="submit",
                disabled=VideosState.busy,
                class_name="rounded-xl bg-[#8B5CF6] px-5 py-3 text-xs font-semibold text-white hover:bg-violet-500 disabled:opacity-40",
            ),
            class_name="mt-5 flex justify-end gap-3",
        ),
        on_submit=VideosState.save_edits,
    )


def delete_confirmation() -> rx.Component:
    return rx.el.div(
        rx.el.p(
            f"Delete “{VideosState.selected_title}”? This permanently removes the saved project and its asset records from your library. This cannot be undone.",
            class_name="text-sm leading-relaxed text-white/65",
        ),
        rx.el.p(
            "Completed video usage is not refunded. Active generation must be cancelled before deletion. Files stored by external media providers are not removed.",
            class_name="mt-3 text-xs leading-relaxed text-white/40",
        ),
        rx.el.div(
            rx.el.button(
                "Keep project",
                auto_focus=True,
                on_click=VideosState.close_modal,
                disabled=VideosState.busy,
                class_name="rounded-xl bg-white/5 px-4 py-3 text-xs text-white/70 hover:bg-white/10 disabled:opacity-40",
            ),
            rx.el.button(
                rx.cond(VideosState.busy, "Deleting…", "Delete permanently"),
                on_click=VideosState.confirm_delete,
                disabled=VideosState.busy,
                class_name="rounded-xl bg-red-500/15 px-5 py-3 text-xs font-semibold text-red-300 hover:bg-red-500/25 disabled:opacity-40",
            ),
            class_name="mt-6 flex flex-wrap justify-end gap-3",
        ),
    )


def library_modal() -> rx.Component:
    return rx.cond(
        VideosState.modal != "",
        rx.el.div(
            rx.el.section(
                rx.el.div(
                    rx.el.h2(
                        rx.match(
                            VideosState.modal,
                            ("edit", "Edit title & script"),
                            ("delete", "Delete project?"),
                            "Regeneration unavailable",
                        ),
                        id="library-modal-title",
                        class_name="text-xl font-semibold text-white",
                    ),
                    rx.el.button(
                        rx.icon("x", class_name="h-5 w-5"),
                        on_click=VideosState.close_modal,
                        aria_label="Close dialog",
                        disabled=VideosState.busy,
                        class_name="rounded-lg bg-transparent p-2 text-white/50 hover:bg-white/5 disabled:opacity-40",
                    ),
                    class_name="mb-5 flex items-center justify-between gap-3",
                ),
                rx.cond(
                    VideosState.modal_error != "",
                    rx.el.p(
                        VideosState.modal_error,
                        role="alert",
                        class_name="mb-4 rounded-xl bg-red-500/10 p-3 text-sm text-red-200",
                    ),
                ),
                rx.match(
                    VideosState.modal,
                    ("edit", edit_form()),
                    ("delete", delete_confirmation()),
                    rx.el.div(
                        rx.icon(
                            "info", class_name="mb-4 h-6 w-6 text-[#448BFF]"
                        ),
                        rx.el.p(
                            "In-place regeneration is not available yet. Use Create a Short to make a new normal Short from your idea. This action has not generated anything or deducted credits.",
                            class_name="text-sm leading-relaxed text-white/65",
                        ),
                        rx.el.p(
                            "You can manually edit the saved title and script. Those edits do not change an existing rendered video.",
                            class_name="mt-3 text-xs leading-relaxed text-white/45",
                        ),
                        rx.el.button(
                            "Got it",
                            auto_focus=True,
                            on_click=VideosState.close_modal,
                            class_name="mt-6 rounded-xl bg-[#8B5CF6] px-5 py-3 text-xs font-semibold text-white hover:bg-violet-500",
                        ),
                    ),
                ),
                role="dialog",
                aria_modal=True,
                aria_labelledby="library-modal-title",
                class_name="my-auto w-full max-w-xl rounded-3xl border border-white/15 bg-[#13131C] p-5 sm:p-7",
            ),
            class_name="fixed inset-0 z-50 flex overflow-y-auto bg-black/80 p-4 sm:p-8",
        ),
    )


def library_results() -> rx.Component:
    return rx.el.div(
        rx.cond(
            VideosState.projects.length() > 0,
            rx.el.div(
                rx.foreach(VideosState.projects, library_card),
                class_name="grid w-full grid-cols-1 items-start gap-4 sm:grid-cols-2 xl:grid-cols-3",
            ),
            rx.el.div(
                rx.icon(
                    "clapperboard", class_name="mx-auto h-9 w-9 text-[#A78BFA]"
                ),
                rx.el.h2(
                    rx.cond(
                        VideosState.page > 0,
                        "No more projects on this page",
                        "No videos here yet",
                    ),
                    class_name="mt-5 text-lg font-semibold text-white",
                ),
                rx.el.p(
                    "Saved projects matching this tab will appear here. Try another tab or return to your dashboard.",
                    class_name="mx-auto mt-2 max-w-md text-sm leading-relaxed text-white/50",
                ),
                class_name="rounded-3xl border border-dashed border-white/15 bg-[#13131C] px-5 py-12 text-center",
            ),
        ),
        rx.el.div(
            rx.el.button(
                rx.icon("chevron-left", class_name="h-4 w-4"),
                "Previous",
                on_click=VideosState.previous_page,
                disabled=(VideosState.page == 0)
                | VideosState.loading
                | VideosState.busy,
                class_name="flex items-center gap-2 rounded-xl border border-white/10 bg-[#13131C] px-4 py-3 text-xs text-white/70 hover:bg-white/5 disabled:opacity-30",
            ),
            rx.el.span(
                f"Page {VideosState.page + 1} · Up to 12 projects",
                class_name="text-center text-xs text-white/40",
            ),
            rx.el.button(
                "Next",
                rx.icon("chevron-right", class_name="h-4 w-4"),
                on_click=VideosState.next_page,
                disabled=(~VideosState.has_next)
                | VideosState.loading
                | VideosState.busy,
                class_name="flex items-center gap-2 rounded-xl border border-white/10 bg-[#13131C] px-4 py-3 text-xs text-white/70 hover:bg-white/5 disabled:opacity-30",
            ),
            class_name="mt-6 flex items-center justify-between gap-3",
        ),
    )


def videos_library() -> rx.Component:
    return rx.el.main(
        library_header(),
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    rx.el.p(
                        "YOUR VIDEO COLLECTION",
                        class_name="text-[10px] font-semibold tracking-[0.18em] text-[#A78BFA]",
                    ),
                    rx.el.h1(
                        "My Videos",
                        class_name="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl",
                    ),
                    rx.el.p(
                        "Your saved projects. Preview, manage and make your next move.",
                        class_name="mt-3 text-sm text-white/50",
                    ),
                ),
                rx.el.button(
                    rx.icon("refresh-cw", class_name="h-4 w-4"),
                    "Refresh",
                    on_click=VideosState.refresh,
                    disabled=VideosState.loading | VideosState.busy,
                    class_name="flex w-fit items-center gap-2 rounded-xl border border-white/10 bg-[#13131C] px-4 py-3 text-xs text-white/70 hover:border-white/25 disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-violet-400",
                ),
                class_name="flex flex-col justify-between gap-5 sm:flex-row sm:items-center",
            ),
            rx.el.nav(
                library_tab("All", "all"),
                library_tab("Shorts", "short"),
                library_tab("Product Ads", "product_ad"),
                library_tab("UGC Ads", "ugc_ad"),
                aria_label="Filter videos by type",
                class_name="my-7 flex gap-1 overflow-x-auto rounded-2xl border border-white/8 bg-[#13131C] p-1.5",
            ),
            rx.cond(
                VideosState.notice != "",
                rx.el.p(
                    VideosState.notice,
                    role="status",
                    class_name="mb-5 rounded-2xl border border-blue-400/20 bg-[#448BFF]/5 p-4 text-sm text-white/65",
                ),
            ),
            rx.cond(
                VideosState.error != "",
                rx.el.div(
                    rx.el.p(
                        VideosState.error, class_name="text-sm text-red-200"
                    ),
                    rx.el.button(
                        "Try again",
                        on_click=VideosState.refresh,
                        disabled=VideosState.loading,
                        class_name="mt-3 rounded-lg bg-white/5 px-4 py-2 text-xs text-white hover:bg-white/10",
                    ),
                    role="alert",
                    class_name="mb-5 rounded-2xl border border-red-400/20 bg-red-500/10 p-5",
                ),
            ),
            rx.cond(
                VideosState.loading,
                rx.el.div(
                    rx.el.p(
                        "Loading your library and checking attached videos…",
                        role="status",
                        class_name="mb-4 text-sm text-white/50",
                    ),
                    rx.el.div(
                        rx.foreach(
                            rx.Var.range(6),
                            lambda i: rx.el.div(
                                key=i,
                                class_name="h-72 animate-pulse rounded-2xl bg-white/5",
                            ),
                        ),
                        class_name="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3",
                    ),
                ),
            ),
            rx.cond(VideosState.ready, library_results()),
            class_name="mx-auto w-full max-w-7xl flex-1 px-5 py-8 sm:px-8 sm:py-10",
        ),
        library_modal(),
        class_name="flex min-h-dvh w-full flex-col bg-[#0B0B10] font-['Inter'] text-white",
    )
