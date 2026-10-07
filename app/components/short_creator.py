import reflex as rx

from app.components.dashboard import dashboard_header
from app.states.short_state import ShortState


def creator_select(
    label: str, name: str, options: list[str], selected: rx.Var
) -> rx.Component:
    return rx.el.div(
        rx.el.label(
            label,
            html_for=name,
            class_name="mb-2 block text-xs font-medium text-white/70",
        ),
        rx.el.div(
            rx.el.select(
                rx.foreach(
                    options,
                    lambda option: rx.el.option(
                        option,
                        value=option,
                        class_name="bg-[#13131C] text-white",
                    ),
                ),
                id=name,
                name=name,
                default_value=selected,
                key=selected,
                class_name="w-full appearance-none rounded-xl border border-white/15 bg-[#0B0B10] px-4 py-3 pr-10 text-sm text-white focus:border-violet-400 focus:outline-hidden focus:ring-2 focus:ring-violet-400/20",
            ),
            rx.icon(
                "chevron-down",
                class_name="pointer-events-none absolute right-3 top-3.5 h-4 w-4 text-white/50",
            ),
            class_name="relative",
        ),
    )


def creator_form() -> rx.Component:
    return rx.el.form(
        rx.el.fieldset(
            rx.el.label(
                "What's your story?",
                html_for="short-idea",
                class_name="mb-3 block text-base font-semibold text-white",
            ),
            rx.el.textarea(
                id="short-idea",
                name="idea",
                required=True,
                min_length=1,
                max_length=2000,
                default_value=ShortState.idea,
                key=ShortState.idea,
                placeholder="For example: Why a ten-minute walk can change your day. Make it uplifting and practical.",
                class_name="min-h-40 w-full resize-y rounded-2xl border border-white/15 bg-[#0B0B10] px-4 py-4 text-sm leading-relaxed text-white placeholder:text-white/30 focus:border-violet-400 focus:outline-hidden focus:ring-2 focus:ring-violet-400/20",
            ),
            rx.el.p(
                "1–2000 characters · English narration · one idea works best",
                class_name="mt-2 text-xs text-white/40",
            ),
            rx.el.div(
                creator_select(
                    "Maximum duration (seconds)",
                    "duration",
                    ["15", "30", "45", "60"],
                    ShortState.duration,
                ),
                creator_select(
                    "Visual style",
                    "style",
                    [
                        "Cinematic",
                        "Illustrated",
                        "3D animation",
                        "Photorealistic",
                    ],
                    ShortState.style,
                ),
                creator_select(
                    "AI voice",
                    "voice",
                    ["alloy", "nova", "onyx"],
                    ShortState.voice,
                ),
                creator_select(
                    "Captions",
                    "captions",
                    ["Classic", "Bold", "None"],
                    ShortState.caption_style,
                ),
                class_name="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-2",
            ),
            rx.el.p(
                "Choose Classic for readable captions or Bold for larger type. Caption timing is estimated by AI and scaled to the narration, not word-level speech alignment.",
                class_name="mt-5 text-xs leading-relaxed text-white/40",
            ),
            disabled=ShortState.busy | ShortState.loading,
            class_name="min-w-0 disabled:opacity-60",
        ),
        rx.el.button(
            rx.cond(
                ShortState.busy,
                rx.icon("loader-circle", class_name="h-4 w-4 animate-spin"),
                rx.icon("sparkles", class_name="h-4 w-4"),
            ),
            rx.cond(
                ShortState.busy,
                "Creating your Short…",
                "Generate my Short · 1 video",
            ),
            type="submit",
            disabled=ShortState.busy
            | ShortState.loading
            | (~ShortState.ready)
            | (~ShortState.available)
            | (ShortState.remaining < 1),
            class_name="mt-7 flex w-full items-center justify-center gap-2 rounded-xl bg-[#8B5CF6] px-5 py-4 text-sm font-semibold text-white transition-colors hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-violet-400",
        ),
        rx.el.p(
            "One video is reserved before generation. Only a successfully verified MP4 is charged; failed work releases the reservation. Generation can take several minutes.",
            class_name="mt-3 text-center text-xs leading-relaxed text-white/45",
        ),
        on_submit=ShortState.submit,
        class_name="mt-6 rounded-3xl border border-white/8 bg-[#13131C] p-5 sm:p-7",
    )


def creator_feedback() -> rx.Component:
    return rx.el.div(
        rx.cond(
            ShortState.loading,
            rx.el.div(
                "Checking your plan and generation availability…",
                role="status",
                class_name="mt-6 animate-pulse rounded-2xl bg-white/5 p-5 text-sm text-white/60",
            ),
        ),
        rx.cond(
            ShortState.error != "",
            rx.el.div(
                rx.icon(
                    "circle-alert",
                    class_name="mt-0.5 h-5 w-5 shrink-0 text-red-400",
                ),
                rx.el.div(
                    rx.el.p(
                        ShortState.error,
                        class_name="text-sm leading-relaxed text-red-200",
                    ),
                    rx.el.button(
                        "Recheck allowance & setup",
                        on_click=ShortState.load_creator,
                        disabled=ShortState.busy,
                        class_name="mt-3 rounded-lg bg-white/5 px-3 py-2 text-xs text-white hover:bg-white/10 disabled:opacity-40",
                    ),
                ),
                role="alert",
                class_name="mt-6 flex gap-3 rounded-2xl border border-red-400/20 bg-red-500/10 p-5",
            ),
        ),
        rx.cond(
            ShortState.busy,
            rx.el.section(
                rx.el.div(
                    rx.icon(
                        "loader-circle",
                        class_name="h-5 w-5 shrink-0 animate-spin text-[#C4B5FD]",
                    ),
                    rx.el.p(
                        ShortState.stage, class_name="text-sm text-white/80"
                    ),
                    class_name="flex items-center gap-3",
                ),
                rx.el.progress(
                    value=ShortState.progress,
                    max=100,
                    aria_label="Short generation progress",
                    class_name="mt-4 h-2 w-full accent-[#8B5CF6]",
                ),
                rx.el.p(
                    f"{ShortState.progress}% · Keep this tab open. Your project is already saved in My Videos.",
                    class_name="mt-3 text-xs leading-relaxed text-white/45",
                ),
                role="status",
                aria_live="polite",
                class_name="mt-6 rounded-2xl border border-violet-400/20 bg-violet-500/5 p-5",
            ),
        ),
    )


def creator_result() -> rx.Component:
    return rx.cond(
        ShortState.output_file != "",
        rx.el.section(
            rx.el.div(
                rx.icon("circle-check", class_name="h-5 w-5 text-green-400"),
                rx.el.span(
                    "YOUR SHORT IS READY",
                    class_name="text-xs font-semibold tracking-wider text-green-400",
                ),
                class_name="flex items-center gap-2",
            ),
            rx.el.h2(
                ShortState.output_title,
                class_name="mt-3 text-xl font-semibold text-white",
            ),
            rx.el.p(
                f"{ShortState.output_seconds:.1f}s · 9:16 · 540 × 960 · MP4",
                class_name="mt-2 text-xs text-white/50",
            ),
            rx.el.video(
                src=rx.get_upload_url(ShortState.output_file),
                controls=True,
                plays_inline=True,
                preload="metadata",
                aria_label="Your generated Short",
                class_name="mx-auto mt-5 max-h-[560px] w-full max-w-[315px] rounded-2xl bg-black",
            ),
            rx.el.details(
                rx.el.summary(
                    "Read the narration",
                    class_name="mt-5 cursor-pointer text-sm text-[#C4B5FD]",
                ),
                rx.el.p(
                    ShortState.output_script,
                    class_name="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-white/60",
                ),
            ),
            rx.el.a(
                "Open My Videos to download",
                rx.icon("arrow-right", class_name="h-4 w-4"),
                href="/videos",
                class_name="mt-6 flex w-fit items-center gap-2 rounded-xl bg-[#8B5CF6] px-5 py-3 text-sm font-semibold text-white hover:bg-violet-500",
            ),
            class_name="mt-7 rounded-3xl border border-green-400/20 bg-[#13131C] p-5 sm:p-7",
        ),
    )


def short_creator() -> rx.Component:
    return rx.el.main(
        dashboard_header(),
        rx.el.div(
            rx.el.a(
                rx.icon("arrow-left", class_name="h-4 w-4"),
                "Dashboard",
                href="/",
                class_name="mb-7 flex w-fit items-center gap-2 text-xs text-white/50 hover:text-white",
            ),
            rx.el.p(
                "ONE IDEA. ONE VERTICAL STORY.",
                class_name="text-[10px] font-semibold tracking-[0.18em] text-[#A78BFA]",
            ),
            rx.el.h1(
                "Create a Short",
                class_name="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl",
            ),
            rx.el.p(
                "Start with your idea. We'll write the hook and story, generate scene images and AI narration, and bring it together with captions and an original instrumental.",
                class_name="mt-4 text-sm leading-relaxed text-white/55",
            ),
            rx.cond(
                ShortState.ready,
                rx.el.div(
                    rx.el.div(
                        rx.icon("film", class_name="h-4 w-4 text-[#A78BFA]"),
                        rx.el.p(
                            f"{ShortState.plan} · {ShortState.remaining} videos available",
                            class_name="text-sm font-medium text-white/75",
                        ),
                        class_name="flex items-center gap-2",
                    ),
                    rx.el.p(
                        ShortState.setup,
                        class_name="mt-3 text-xs leading-relaxed text-white/45",
                    ),
                    rx.cond(
                        ShortState.warning != "",
                        rx.el.p(
                            ShortState.warning,
                            class_name="mt-3 text-xs leading-relaxed text-[#448BFF]",
                        ),
                    ),
                    rx.cond(
                        ShortState.remaining == 0,
                        rx.el.div(
                            rx.el.p(
                                "No videos are available in your current allowance. Pending generations also reserve videos.",
                                class_name="text-sm text-white/65",
                            ),
                            rx.el.a(
                                "View plans",
                                href="/plans",
                                class_name="mt-2 block text-xs font-semibold text-[#C4B5FD] hover:text-white",
                            ),
                            class_name="mt-4 border-t border-white/8 pt-4",
                        ),
                    ),
                    class_name="mt-6 rounded-2xl border border-white/8 bg-[#13131C] p-5",
                ),
            ),
            creator_feedback(),
            creator_form(),
            creator_result(),
            rx.el.p(
                "Generated scene images, not live-action footage. AI voice is synthetic. Media links are shareable; avoid sensitive personal information in your idea.",
                class_name="mt-6 text-center text-xs leading-relaxed text-white/35",
            ),
            rx.el.a(
                "View saved projects in My Videos",
                href="/videos",
                class_name="mx-auto mt-4 block w-fit text-xs text-[#C4B5FD] hover:text-white",
            ),
            class_name="mx-auto w-full max-w-2xl flex-1 px-5 py-8 sm:py-10",
        ),
        class_name="flex min-h-dvh w-full flex-col bg-[#0B0B10] font-['Inter'] text-white",
    )
