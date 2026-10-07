import reflex as rx

from reflex_enterprise.auth import User
from app.states.onboarding_state import OnboardingState


def brand() -> rx.Component:
    return rx.el.a(
        rx.el.div(
            rx.icon("clapperboard", class_name="h-5 w-5 text-white"),
            class_name="flex h-10 w-10 items-center justify-center rounded-xl bg-[#8B5CF6]",
        ),
        rx.el.span(
            "ShortForge",
            rx.el.span(" AI", class_name="text-[#A78BFA]"),
            class_name="text-lg font-semibold tracking-tight text-white",
        ),
        href="/",
        class_name="flex items-center gap-3 w-fit",
    )


def illustration(icon: str, label: str, detail: str) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.icon(icon, class_name="h-12 w-12 text-[#C4B5FD]"),
                class_name="flex h-24 w-24 items-center justify-center rounded-3xl border border-violet-400/25 bg-violet-500/15",
            ),
            rx.el.div(
                rx.icon("sparkles", class_name="h-4 w-4 text-[#448BFF]"),
                rx.el.span(label, class_name="text-sm font-medium text-white"),
                class_name="mt-7 flex items-center justify-center gap-2",
            ),
            rx.el.p(
                detail, class_name="mt-2 text-center text-xs text-white/45"
            ),
            class_name="flex flex-col items-center rounded-[32px] border border-white/10 bg-linear-to-br from-violet-500/10 to-blue-500/5 px-8 py-10 sm:py-12",
        ),
        class_name="mx-auto mb-8 w-full max-w-sm",
        aria_hidden=True,
    )


def screen(
    icon: str, label: str, detail: str, title: str, subtitle: str
) -> rx.Component:
    return rx.el.div(
        illustration(icon, label, detail),
        rx.el.h1(
            title,
            class_name="mx-auto max-w-sm text-center text-3xl font-semibold tracking-tight text-white sm:text-4xl",
        ),
        rx.el.p(
            subtitle,
            class_name="mx-auto mt-4 max-w-xs text-center text-base leading-relaxed text-white/60",
        ),
    )


def feedback() -> rx.Component:
    return rx.cond(
        OnboardingState.error != "",
        rx.el.div(
            rx.icon("circle-alert", class_name="h-5 w-5 shrink-0 text-red-400"),
            rx.el.div(
                rx.el.p(
                    OnboardingState.error, class_name="text-sm text-red-200"
                ),
                rx.el.button(
                    "Reload progress",
                    on_click=OnboardingState.retry,
                    disabled=OnboardingState.loading | OnboardingState.saving,
                    class_name="mt-2 text-sm font-medium text-white underline underline-offset-4 disabled:opacity-40",
                ),
            ),
            role="alert",
            class_name="mb-6 flex gap-3 rounded-2xl border border-red-400/20 bg-red-500/10 p-4",
        ),
    )


def loading_card() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            class_name="mx-auto h-48 w-full rounded-3xl bg-white/5 animate-pulse"
        ),
        rx.el.p(
            "Loading your progress…",
            role="status",
            class_name="mt-6 text-center text-sm text-white/60",
        ),
        class_name="w-full",
    )


def wizard() -> rx.Component:
    return rx.el.main(
        rx.el.header(
            brand(),
            rx.el.button(
                "Sign out",
                on_click=User.logout,
                class_name="rounded-lg px-3 py-2 text-xs text-white/50 hover:bg-white/5 hover:text-white",
            ),
            class_name="mx-auto flex w-full max-w-5xl items-center justify-between px-5 py-6 sm:px-8",
        ),
        rx.el.section(
            rx.el.div(
                rx.el.div(
                    rx.el.span(
                        f"GETTING STARTED · {OnboardingState.step + 1} OF 4",
                        class_name="text-[10px] font-semibold tracking-[0.18em] text-white/45",
                    ),
                    class_name="mb-7 text-center",
                ),
                feedback(),
                rx.cond(
                    OnboardingState.loading,
                    loading_card(),
                    rx.cond(
                        OnboardingState.ready,
                        rx.el.div(
                            rx.match(
                                OnboardingState.step,
                                (
                                    0,
                                    screen(
                                        "clapperboard",
                                        "An idea. A little AI. A great short.",
                                        "Made for your next big idea",
                                        "Welcome to ShortForge AI",
                                        "Turn your ideas into short videos",
                                    ),
                                ),
                                (
                                    1,
                                    screen(
                                        "wand-sparkles",
                                        "Your creative workflow, simplified",
                                        "Script • Voiceover • Visuals • Captions",
                                        "Create content faster",
                                        "Generate scripts, voiceovers, visuals and captions",
                                    ),
                                ),
                                (
                                    2,
                                    screen(
                                        "shopping-bag",
                                        "Put your product in the spotlight",
                                        "From product to story",
                                        "Create ads that sell",
                                        "Turn products into short advertisements",
                                    ),
                                ),
                                screen(
                                    "rocket",
                                    "Your next chapter starts here",
                                    "You bring the idea",
                                    "Let's create your first video",
                                    "",
                                ),
                            ),
                            rx.el.div(
                                rx.foreach(
                                    rx.Var.range(4),
                                    lambda i: rx.el.span(
                                        class_name=rx.cond(
                                            i == OnboardingState.step,
                                            "h-1.5 w-8 rounded-full bg-[#8B5CF6]",
                                            "h-1.5 w-1.5 rounded-full bg-white/20",
                                        )
                                    ),
                                ),
                                class_name="my-8 flex items-center justify-center gap-2",
                                aria_label="Onboarding progress",
                            ),
                            rx.el.button(
                                rx.cond(
                                    OnboardingState.saving,
                                    "Saving…",
                                    rx.cond(
                                        OnboardingState.step == 3,
                                        "Create My First Short",
                                        "Next",
                                    ),
                                ),
                                rx.icon("arrow-right", class_name="h-4 w-4"),
                                on_click=lambda: OnboardingState.move(1),
                                disabled=OnboardingState.saving,
                                class_name="flex min-h-14 w-full items-center justify-center gap-3 rounded-2xl bg-[#8B5CF6] px-5 py-4 text-sm font-semibold text-white transition-colors hover:bg-violet-500 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-violet-400 disabled:opacity-50",
                            ),
                            rx.cond(
                                OnboardingState.step > 0,
                                rx.el.button(
                                    rx.icon("arrow-left", class_name="h-4 w-4"),
                                    "Back",
                                    on_click=lambda: OnboardingState.move(-1),
                                    disabled=OnboardingState.saving,
                                    class_name="mx-auto mt-4 flex min-h-11 items-center gap-2 rounded-xl px-5 text-sm text-white/55 hover:text-white disabled:opacity-40",
                                ),
                                rx.el.p(
                                    "No purchase required",
                                    class_name="mt-5 text-center text-xs text-white/35",
                                ),
                            ),
                        ),
                        rx.el.p(
                            "Please reload your progress or sign in again to continue.",
                            class_name="text-center text-sm text-white/60",
                        ),
                    ),
                ),
                class_name="w-full max-w-md rounded-[28px] border border-white/8 bg-[#13131C] p-6 sm:p-9",
            ),
            class_name="flex w-full flex-1 items-center justify-center px-4 py-6 sm:py-10",
        ),
        rx.el.footer(
            "SHORTFORGE AI · MADE FOR CREATORS",
            class_name="px-4 pb-6 pt-3 text-center text-[9px] tracking-[0.2em] text-white/25",
        ),
        class_name="flex min-h-dvh w-full flex-col bg-[#0B0B10] font-['Inter'] text-white",
    )
