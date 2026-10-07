import reflex as rx

from app.components.dashboard import dashboard_header, status_badge
from app.components.short_creator import creator_select
from app.services.short_generation import STYLES, VOICES, CAPTIONS
from app.services.ten_generation import BatchCard, BatchHistory
from app.states.ten_state import TenState


def ten_form() -> rx.Component:
    return rx.el.form(
        rx.el.fieldset(
            rx.el.label(
                "What's your idea?",
                html_for="ten-idea",
                class_name="mb-3 block text-base font-semibold text-white",
            ),
            rx.el.textarea(
                id="ten-idea",
                name="idea",
                required=True,
                min_length=1,
                max_length=2000,
                default_value=TenState.idea,
                key=TenState.idea,
                placeholder="A simple topic, a useful tip, or a story you want to explore from ten angles…",
                class_name="min-h-36 w-full resize-y rounded-2xl border border-white/15 bg-[#0B0B10] p-4 text-sm leading-relaxed text-white placeholder:text-white/30 focus:border-violet-400 focus:outline-hidden focus:ring-2 focus:ring-violet-400/20",
            ),
            rx.el.p(
                "1–2000 characters · English · one topic, ten editorial structures",
                class_name="mt-2 text-xs text-white/40",
            ),
            rx.el.div(
                creator_select(
                    "Maximum seconds",
                    "duration",
                    ["15", "30", "45", "60"],
                    TenState.duration,
                ),
                creator_select(
                    "Visual style", "style", list(STYLES), TenState.style
                ),
                creator_select(
                    "AI voice", "voice", list(VOICES), TenState.voice
                ),
                creator_select(
                    "Captions",
                    "captions",
                    list(CAPTIONS),
                    TenState.caption_style,
                ),
                class_name="mt-5 grid grid-cols-1 gap-5 sm:grid-cols-2",
            ),
            disabled=TenState.busy | TenState.loading,
            class_name="min-w-0 disabled:opacity-60",
        ),
        rx.el.button(
            rx.icon("sparkles", class_name="h-4 w-4"),
            rx.cond(
                TenState.busy & (TenState.task == "concepts"),
                "Writing ten concepts…",
                "Create ten concepts · no video credits",
            ),
            type="submit",
            disabled=TenState.busy
            | TenState.loading
            | (~TenState.ready)
            | (~TenState.concepts_available),
            class_name="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-[#8B5CF6] px-5 py-4 text-sm font-semibold text-white hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-violet-400",
        ),
        rx.el.p(
            "All ten are saved as drafts. Nothing is rendered automatically. Your selected settings are saved with every concept.",
            class_name="mt-3 text-xs leading-relaxed text-white/45",
        ),
        on_submit=TenState.submit,
        class_name="rounded-3xl border border-white/8 bg-[#13131C] p-5 sm:p-7",
    )


def concept_card(card: BatchCard) -> rx.Component:
    return rx.el.article(
        rx.el.div(
            rx.el.span(
                f"{card['order']} / 10 · {card['angle']}",
                class_name="text-xs font-semibold uppercase tracking-wide text-[#448BFF]",
            ),
            status_badge(card["status"]),
            class_name="flex flex-wrap items-center justify-between gap-3",
        ),
        rx.el.h3(
            card["title"],
            class_name="mt-4 break-words text-lg font-semibold text-white",
        ),
        rx.el.p(
            card["hook"],
            class_name="mt-3 break-words text-sm font-medium leading-relaxed text-[#C4B5FD]",
        ),
        rx.el.h4(
            "Short outline",
            class_name="mt-5 text-xs font-semibold text-white/75",
        ),
        rx.el.p(
            card["outline"],
            class_name="mt-2 whitespace-pre-wrap break-words text-sm leading-relaxed text-white/60",
        ),
        rx.el.h4(
            "Visual direction",
            class_name="mt-4 text-xs font-semibold text-white/75",
        ),
        rx.el.p(
            card["visual_direction"],
            class_name="mt-2 break-words text-sm leading-relaxed text-white/60",
        ),
        rx.el.p(
            f"CTA · {card['cta']}",
            class_name="mt-4 break-words text-xs leading-relaxed text-white/55",
        ),
        rx.el.p(
            f"≤ {card['duration']}s · {card['style']} · {card['voice']} · {card['captions']} captions",
            class_name="mt-4 text-xs leading-relaxed text-white/35",
        ),
        rx.el.p(
            card["message"],
            role="status",
            class_name="mt-4 break-words text-xs leading-relaxed text-[#448BFF]",
        ),
        rx.cond(
            (card["status"] == "queued")
            | (card["status"] == "generating")
            | (card["status"] == "rendering"),
            rx.el.div(
                rx.el.progress(
                    value=card["progress"],
                    max=100,
                    class_name="h-2 w-full accent-[#8B5CF6]",
                ),
                rx.el.p(
                    f"{card['progress']}% · Refresh for cross-session updates",
                    class_name="mt-2 text-xs text-white/45",
                ),
                class_name="mt-4",
            ),
        ),
        rx.cond(
            (card["status"] == "draft")
            | (card["status"] == "failed")
            | (card["status"] == "cancelled"),
            rx.el.button(
                rx.icon("clapperboard", class_name="h-4 w-4"),
                rx.cond(
                    card["status"] == "failed",
                    "Retry this concept · 1 video",
                    "Select & render this one · 1 video",
                ),
                on_click=lambda: TenState.select_one(card["id"]),
                disabled=TenState.busy
                | TenState.loading
                | TenState.batch_active
                | (~TenState.render_available)
                | (~TenState.ready)
                | (TenState.remaining < 1),
                class_name="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-[#8B5CF6] px-4 py-3 text-xs font-semibold text-white hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-violet-400",
            ),
        ),
        rx.cond(
            (card["status"] == "completed") & (card["filename"] != ""),
            rx.el.div(
                rx.el.video(
                    src=rx.get_upload_url(card["filename"]),
                    controls=True,
                    plays_inline=True,
                    preload="metadata",
                    class_name="mx-auto max-h-[480px] w-full max-w-[270px] rounded-2xl bg-black",
                ),
                rx.el.a(
                    "Download MP4",
                    rx.icon("download", class_name="h-4 w-4"),
                    href=rx.get_upload_url(card["filename"]),
                    download=True,
                    class_name="mt-4 flex w-fit items-center gap-2 rounded-xl border border-white/15 px-4 py-3 text-xs font-semibold text-[#C4B5FD] hover:bg-white/5",
                ),
                class_name="mt-5",
            ),
        ),
        rx.cond(
            (card["status"] == "completed") & (card["filename"] == ""),
            rx.el.p(
                card["media_note"], class_name="mt-4 text-xs text-white/45"
            ),
        ),
        key=card["id"],
        class_name="min-w-0 rounded-3xl border border-white/8 bg-[#13131C] p-5 sm:p-6",
    )


def history_item(batch: BatchHistory) -> rx.Component:
    return rx.el.button(
        rx.el.span(
            batch["label"], class_name="text-xs font-semibold text-white/80"
        ),
        rx.el.span(
            f"{batch['count']} saved · {batch['completed']} completed · {batch['active']} active",
            class_name="mt-2 block text-xs text-white/45",
        ),
        on_click=lambda: TenState.open_batch(batch["id"]),
        disabled=TenState.busy,
        key=batch["id"],
        class_name=rx.cond(
            TenState.batch_id == batch["id"],
            "w-full rounded-xl border border-violet-400/40 bg-violet-500/10 p-4 text-left disabled:opacity-40",
            "w-full rounded-xl border border-white/8 bg-[#13131C] p-4 text-left hover:border-violet-400/40 disabled:opacity-40",
        ),
    )


def ten_feedback() -> rx.Component:
    return rx.el.div(
        rx.cond(
            TenState.loading,
            rx.el.p(
                "Refreshing your saved drafts and allowance…",
                role="status",
                class_name="mb-5 animate-pulse rounded-2xl bg-white/5 p-4 text-sm text-white/60",
            ),
        ),
        rx.cond(
            TenState.error != "",
            rx.el.p(
                TenState.error,
                role="alert",
                class_name="mb-5 rounded-2xl border border-red-400/20 bg-red-500/10 p-4 text-sm leading-relaxed text-red-200",
            ),
        ),
        rx.cond(
            TenState.notice != "",
            rx.el.p(
                TenState.notice,
                role="status",
                class_name="mb-5 rounded-2xl border border-blue-400/20 bg-[#448BFF]/5 p-4 text-sm leading-relaxed text-[#448BFF]",
            ),
        ),
        rx.cond(
            TenState.busy,
            rx.el.div(
                rx.el.p(
                    TenState.stage,
                    class_name="text-sm leading-relaxed text-[#C4B5FD]",
                ),
                rx.el.progress(
                    value=TenState.progress,
                    max=100,
                    class_name="mt-3 h-2 w-full accent-[#8B5CF6]",
                ),
                rx.el.p(
                    "Keep this tab open. Saved render progress survives refresh; stale interrupted attempts are released after 30 minutes without updates.",
                    class_name="mt-3 text-xs leading-relaxed text-white/45",
                ),
                role="status",
                aria_live="polite",
                class_name="mb-5 rounded-2xl border border-violet-400/20 bg-violet-500/5 p-5",
            ),
        ),
    )


def ten_creator() -> rx.Component:
    return rx.el.main(
        dashboard_header(),
        rx.el.div(
            rx.el.a(
                "← Dashboard",
                href="/",
                class_name="text-xs text-white/50 hover:text-white",
            ),
            rx.el.div(
                rx.el.div(
                    rx.el.p(
                        "ONE IDEA. TEN CREATIVE DIRECTIONS.",
                        class_name="mt-7 text-[10px] font-semibold tracking-[0.18em] text-[#A78BFA]",
                    ),
                    rx.el.h1(
                        "Create 10 Videos",
                        class_name="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl",
                    ),
                    rx.el.p(
                        "Explore ten distinct concepts, then choose one to bring to life. You're in control of every render.",
                        class_name="mt-4 text-sm leading-relaxed text-white/55",
                    ),
                ),
                rx.el.button(
                    rx.icon("refresh-cw", class_name="h-4 w-4"),
                    "Refresh status & allowance",
                    on_click=TenState.refresh,
                    disabled=TenState.loading,
                    class_name="flex w-fit shrink-0 items-center gap-2 rounded-xl border border-white/10 bg-[#13131C] px-4 py-3 text-xs text-white/70 hover:text-white disabled:opacity-40",
                ),
                class_name="flex flex-col items-start justify-between gap-5 sm:flex-row sm:items-end",
            ),
            rx.el.div(
                rx.el.p(
                    f"{TenState.plan} · {TenState.remaining} videos available",
                    class_name="text-sm font-medium text-white/80",
                ),
                rx.el.p(
                    "One credit reserved per selected render. Charged only after a verified MP4; failed attempts release the reservation. Only one concept in a batch can render at a time, even in another tab.",
                    class_name="mt-3 text-xs leading-relaxed text-white/60",
                ),
                rx.el.p(
                    TenState.setup,
                    class_name="mt-3 text-xs leading-relaxed text-white/45",
                ),
                rx.cond(
                    TenState.warning != "",
                    rx.el.p(
                        TenState.warning,
                        class_name="mt-3 text-xs text-[#448BFF]",
                    ),
                ),
                rx.cond(
                    TenState.ready & (TenState.remaining == 0),
                    rx.el.div(
                        rx.el.p(
                            "Your video allowance is exhausted or reserved. You can still create and save ten concepts without video credits.",
                            class_name="text-sm text-white/65",
                        ),
                        rx.el.a(
                            "View plans",
                            href="/plans",
                            class_name="mt-2 block text-xs font-semibold text-[#C4B5FD]",
                        ),
                        class_name="mt-4 border-t border-white/8 pt-4",
                    ),
                ),
                rx.cond(
                    TenState.batch_active,
                    rx.el.p(
                        "A concept in this batch is running. Other renders are paused until it finishes. Refresh to see progress.",
                        class_name="mt-3 text-xs text-[#448BFF]",
                    ),
                ),
                class_name="my-6 rounded-2xl border border-white/8 bg-[#13131C] p-5",
            ),
            ten_feedback(),
            ten_form(),
            rx.el.section(
                rx.el.div(
                    rx.el.h2(
                        "Saved batch history",
                        class_name="text-xl font-semibold text-white",
                    ),
                    rx.el.a(
                        "My Videos ↗",
                        href="/videos",
                        class_name="text-xs text-[#C4B5FD] hover:text-white",
                    ),
                    class_name="mb-4 flex items-center justify-between gap-4",
                ),
                rx.cond(
                    TenState.history.length() > 0,
                    rx.el.div(
                        rx.foreach(TenState.history, history_item),
                        class_name="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3",
                    ),
                    rx.el.p(
                        "No saved batches yet. Start with one idea above; all ten drafts will appear here and in My Videos.",
                        class_name="rounded-2xl border border-dashed border-white/15 p-6 text-sm text-white/50",
                    ),
                ),
                rx.el.div(
                    rx.el.button(
                        "Previous",
                        on_click=TenState.history_previous,
                        disabled=(TenState.history_page == 0)
                        | TenState.loading
                        | TenState.busy,
                        class_name="rounded-lg bg-white/5 px-3 py-2 text-xs text-white/70 disabled:opacity-30",
                    ),
                    rx.el.button(
                        "Next",
                        on_click=TenState.history_next,
                        disabled=(~TenState.has_next)
                        | TenState.loading
                        | TenState.busy,
                        class_name="rounded-lg bg-white/5 px-3 py-2 text-xs text-white/70 disabled:opacity-30",
                    ),
                    class_name="mt-4 flex gap-3",
                ),
                class_name="mt-9",
            ),
            rx.cond(
                TenState.cards.length() > 0,
                rx.el.section(
                    rx.el.h2(
                        "Choose your next Short",
                        class_name="text-xl font-semibold text-white",
                    ),
                    rx.el.p(
                        "Question · myth · how-to · micro-story · POV · list · comparison · demonstration · mistake · challenge",
                        class_name="mt-2 text-xs leading-relaxed text-white/45",
                    ),
                    rx.el.div(
                        rx.foreach(TenState.cards, concept_card),
                        class_name="mt-5 grid w-full grid-cols-1 items-start gap-4 md:grid-cols-2 xl:grid-cols-3",
                    ),
                    class_name="mt-9",
                ),
            ),
            rx.el.p(
                "AI-generated concepts, still scene images and synthetic voice, not live-action footage or verified evidence. Caption timing is estimated. Media links are shareable; avoid sensitive information.",
                class_name="mt-8 text-center text-xs leading-relaxed text-white/35",
            ),
            class_name="mx-auto w-full max-w-7xl flex-1 px-5 py-8 sm:px-8 sm:py-10",
        ),
        class_name="flex min-h-dvh w-full flex-col bg-[#0B0B10] font-['Inter'] text-white",
    )
