import reflex as rx

from reflex_enterprise.auth import User
from app.components.onboarding import brand
from app.states.dashboard_state import DashboardState, RecentProject


def dashboard_header() -> rx.Component:
    return rx.el.header(
        brand(),
        rx.el.nav(
            rx.el.a(
                "My Videos",
                href="/videos",
                class_name="rounded-lg px-3 py-2 text-xs text-white/60 hover:bg-white/5 hover:text-white focus-visible:outline-2 focus-visible:outline-violet-400",
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


def action_content(
    icon: str, title: str, detail: str, upcoming: bool
) -> rx.Component:
    return rx.fragment(
        rx.el.div(
            rx.icon(icon, class_name="h-6 w-6 text-[#C4B5FD]"),
            rx.cond(
                upcoming,
                rx.el.span(
                    "Coming soon",
                    class_name="w-fit rounded-full bg-white/5 px-2.5 py-1 text-[10px] font-medium text-white/50",
                ),
                rx.icon("arrow-up-right", class_name="h-5 w-5 text-[#C4B5FD]"),
            ),
            class_name="mb-7 flex items-center justify-between gap-3",
        ),
        rx.el.h3(title, class_name="text-lg font-semibold text-white"),
        rx.el.p(
            detail, class_name="mt-2 text-sm leading-relaxed text-white/50"
        ),
    )


def creation_actions() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.h2(
                "What will you create?",
                class_name="text-xl font-semibold tracking-tight text-white",
            ),
            rx.el.p(
                "Choose your next creative direction.",
                class_name="mt-2 text-sm text-white/50",
            ),
            class_name="mb-5",
        ),
        rx.el.div(
            rx.el.a(
                action_content(
                    "clapperboard",
                    "Create a Short",
                    "Turn an idea into a vertical story. Start here.",
                    False,
                ),
                href="/create",
                class_name="block w-full rounded-3xl border border-violet-400/35 bg-violet-500/10 p-6 transition-colors hover:border-violet-400/70 hover:bg-violet-500/15 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-violet-400",
            ),
            rx.el.a(
                action_content(
                    "shopping-bag",
                    "Create a Product Ad",
                    "Photo-grounded script, benefits and a clear CTA. Free draft.",
                    False,
                ),
                href="/create/product",
                class_name="block w-full rounded-3xl border border-white/8 bg-[#13131C] p-6 transition-colors hover:border-violet-400/40 hover:bg-[#191724] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-violet-400",
            ),
            rx.el.a(
                action_content(
                    "video",
                    "Create a UGC Ad",
                    "Conversational creator-style script and demo. Free draft.",
                    False,
                ),
                href="/create/ugc",
                class_name="block w-full rounded-3xl border border-white/8 bg-[#13131C] p-6 transition-colors hover:border-violet-400/40 hover:bg-[#191724] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-violet-400",
            ),
            rx.el.a(
                action_content(
                    "layers",
                    "Create 10 Videos",
                    "One idea, ten distinct concepts. Render one at a time.",
                    False,
                ),
                href="/create/ten",
                class_name="block w-full rounded-3xl border border-white/8 bg-[#13131C] p-6 transition-colors hover:border-violet-400/40 hover:bg-[#191724] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-violet-400",
            ),
            class_name="grid w-full grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4",
        ),
        class_name="mt-9 w-full",
    )


def metric(
    icon: str, label: str, value: rx.Var, detail: rx.Var | str
) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.icon(icon, class_name="h-4 w-4 text-[#A78BFA]"),
            rx.el.span(label, class_name="text-xs font-medium text-white/55"),
            class_name="flex items-center gap-2",
        ),
        rx.el.p(
            value,
            class_name="mt-4 break-words text-3xl font-semibold tracking-tight text-white",
        ),
        rx.el.p(
            detail, class_name="mt-2 text-xs leading-relaxed text-white/45"
        ),
        class_name="w-full rounded-3xl border border-white/8 bg-[#13131C] p-5 sm:p-6",
    )


def plan_summary() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            metric(
                "crown",
                "Current plan",
                DashboardState.plan,
                DashboardState.verification_label,
            ),
            metric(
                "film",
                "Videos remaining",
                DashboardState.remaining,
                f"of {DashboardState.allowance} per {DashboardState.period_label}",
            ),
            metric(
                "circle-check",
                "Videos used",
                DashboardState.used,
                "Charged in this usage period",
            ),
            metric(
                "clock-3",
                "Videos reserved",
                DashboardState.reserved,
                "Held for pending generation",
            ),
            class_name="grid w-full grid-cols-2 gap-3 lg:grid-cols-4 sm:gap-4",
        ),
        rx.el.div(
            rx.el.p(
                rx.icon(
                    "calendar-days",
                    class_name="h-4 w-4 shrink-0 text-[#448BFF]",
                ),
                f"Usage renews {DashboardState.reset_date} · UTC",
                class_name="flex items-center gap-2 text-xs text-white/50",
            ),
            rx.el.button(
                "Quick upgrade",
                rx.icon("arrow-right", class_name="h-4 w-4"),
                on_click=rx.redirect("/plans"),
                class_name="flex w-fit items-center gap-2 rounded-xl bg-violet-500/10 px-4 py-3 text-xs font-semibold text-[#C4B5FD] hover:bg-violet-500/20 focus-visible:outline-2 focus-visible:outline-violet-400",
            ),
            class_name="mt-4 flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center",
        ),
        rx.cond(
            DashboardState.remaining == 0,
            rx.el.p(
                DashboardState.exhausted_message,
                class_name="mt-3 rounded-2xl border border-white/8 bg-white/5 p-4 text-sm leading-relaxed text-white/60",
            ),
        ),
        rx.cond(
            DashboardState.billing_warning != "",
            rx.el.div(
                rx.icon(
                    "shield-alert", class_name="h-5 w-5 shrink-0 text-[#448BFF]"
                ),
                rx.el.p(
                    DashboardState.billing_warning,
                    class_name="text-sm leading-relaxed text-white/70",
                ),
                role="status",
                class_name="mt-4 flex items-start gap-3 rounded-2xl border border-blue-400/20 bg-[#448BFF]/5 p-4",
            ),
        ),
        class_name="mt-7 w-full",
    )


def information_panel() -> rx.Component:
    return rx.cond(
        DashboardState.panel != "",
        rx.el.section(
            rx.el.div(
                rx.icon(
                    "info", class_name="mt-1 h-5 w-5 shrink-0 text-[#448BFF]"
                ),
                rx.el.div(
                    rx.fragment(
                        rx.el.div(
                            rx.el.span(
                                "PLAN INFORMATION",
                                class_name="text-[10px] font-semibold tracking-[0.16em] text-[#448BFF]",
                            ),
                            rx.el.h3(
                                "More room for your ideas",
                                class_name="mt-2 text-xl font-semibold text-white",
                            ),
                            rx.el.p(
                                f"Your current access is {DashboardState.plan}, with {DashboardState.allowance} videos per {DashboardState.period_label}. You have {DashboardState.remaining} available, {DashboardState.used} used and {DashboardState.reserved} reserved.",
                                class_name="mt-3 text-sm leading-relaxed text-white/60",
                            ),
                            rx.el.p(
                                "Free includes 3 videos per UTC calendar month. Starter includes 25 per month, Growth 80 per three-month term, and Yearly 360 per year. Paid access requires server verification of an active supported subscription. No plan is unlimited. Videos are at most 60 seconds; only successful renders are charged. Pending reservations remain held across renewals.",
                                class_name="mt-3 text-sm leading-relaxed text-white/45",
                            ),
                            rx.el.p(
                                "See Plans for pricing and billing availability. This panel does not change your plan, charge you, or unlock generation.",
                                class_name="mt-3 text-sm leading-relaxed text-white/60",
                            ),
                        ),
                    ),
                    class_name="min-w-0 flex-1",
                ),
                rx.el.button(
                    rx.icon("x", class_name="h-5 w-5"),
                    on_click=DashboardState.close_panel,
                    aria_label="Close information panel",
                    class_name="rounded-lg p-2 text-white/50 hover:bg-white/5 hover:text-white focus-visible:outline-2 focus-visible:outline-violet-400",
                ),
                class_name="flex items-start gap-3 sm:gap-4",
            ),
            role="status",
            class_name="mt-6 rounded-3xl border border-blue-400/20 bg-[#448BFF]/5 p-5 sm:p-6",
        ),
    )


def status_badge(status: rx.Var) -> rx.Component:
    return rx.el.span(
        rx.match(
            status,
            ("draft", "Draft"),
            ("queued", "Queued"),
            ("generating", "Generating"),
            ("rendering", "Rendering"),
            ("completed", "Completed"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
            "Unknown",
        ),
        class_name=rx.match(
            status,
            (
                "completed",
                "w-fit rounded-full bg-green-500/10 px-3 py-1 text-xs font-medium text-green-400",
            ),
            (
                "failed",
                "w-fit rounded-full bg-red-500/10 px-3 py-1 text-xs font-medium text-red-400",
            ),
            (
                "generating",
                "w-fit rounded-full bg-violet-500/15 px-3 py-1 text-xs font-medium text-[#C4B5FD]",
            ),
            (
                "rendering",
                "w-fit rounded-full bg-violet-500/15 px-3 py-1 text-xs font-medium text-[#C4B5FD]",
            ),
            (
                "queued",
                "w-fit rounded-full bg-[#448BFF]/10 px-3 py-1 text-xs font-medium text-[#448BFF]",
            ),
            "w-fit rounded-full bg-white/5 px-3 py-1 text-xs font-medium text-white/50",
        ),
    )


def project_card(project: RecentProject) -> rx.Component:
    return rx.el.article(
        rx.el.div(
            rx.el.div(
                rx.icon("film", class_name="h-6 w-6 text-[#A78BFA]"),
                class_name="flex h-14 w-11 shrink-0 items-center justify-center rounded-xl border border-white/8 bg-violet-500/5",
            ),
            rx.el.div(
                rx.el.h3(
                    project["title"],
                    class_name="truncate text-sm font-semibold text-white",
                ),
                rx.el.p(
                    f"{project['duration']}s · {project['created']}",
                    class_name="mt-1.5 text-xs text-white/40",
                ),
                class_name="min-w-0 flex-1",
            ),
            status_badge(project["status"]),
            class_name="flex items-center gap-3",
        ),
        rx.cond(
            project["message"] != "",
            rx.el.p(
                project["message"],
                class_name="mt-4 break-words text-xs leading-relaxed text-white/50",
            ),
        ),
        rx.cond(
            (project["status"] == "generating")
            | (project["status"] == "rendering")
            | (project["status"] == "queued"),
            rx.el.p(
                f"{project['progress']}% complete · Refresh for updates",
                class_name="mt-3 text-xs text-[#A78BFA]",
            ),
        ),
        rx.cond(
            (project["status"] == "completed") & (project["video_url"] != ""),
            rx.el.video(
                src=project["video_url"],
                controls=True,
                preload="metadata",
                class_name="mt-4 max-h-80 w-full rounded-xl bg-black",
            ),
        ),
        rx.cond(
            (project["status"] == "completed") & (project["video_url"] == ""),
            rx.el.p(
                "No playable video is attached to this project yet.",
                class_name="mt-3 text-xs text-white/45",
            ),
        ),
        class_name="min-w-0 rounded-2xl border border-white/8 bg-[#13131C] p-5",
        key=project["id"],
    )


def recent_projects() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.div(
                rx.el.h2(
                    "Recent videos",
                    class_name="text-xl font-semibold text-white",
                ),
                rx.el.p(
                    "Your eight most recent projects, newest first.",
                    class_name="mt-2 text-xs text-white/45",
                ),
            ),
            rx.el.span(
                f"Updated {DashboardState.refreshed_at}",
                class_name="text-[10px] text-white/35",
            ),
            class_name="mb-5 flex flex-wrap items-end justify-between gap-3",
        ),
        rx.cond(
            DashboardState.projects.length() > 0,
            rx.el.div(
                rx.foreach(DashboardState.projects, project_card),
                class_name="grid w-full grid-cols-1 items-start gap-4 lg:grid-cols-2",
            ),
            rx.el.div(
                rx.el.div(
                    rx.icon(
                        "clapperboard", class_name="h-7 w-7 text-[#A78BFA]"
                    ),
                    class_name="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-violet-500/10",
                ),
                rx.el.h3(
                    "Your story starts here",
                    class_name="mt-5 text-lg font-semibold text-white",
                ),
                rx.el.p(
                    "You don't have any video projects yet. Your saved videos will appear here when you start creating.",
                    class_name="mx-auto mt-2 max-w-md text-sm leading-relaxed text-white/50",
                ),
                rx.el.a(
                    "Create a Short",
                    rx.icon("arrow-right", class_name="h-4 w-4"),
                    href="/create",
                    class_name="mx-auto mt-6 flex w-fit items-center gap-2 rounded-xl bg-[#8B5CF6] px-5 py-3 text-sm font-semibold text-white hover:bg-violet-500 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-violet-400",
                ),
                class_name="rounded-3xl border border-dashed border-white/15 bg-[#13131C] px-5 py-10 text-center",
            ),
        ),
        class_name="mt-10 w-full",
    )


def dashboard_feedback() -> rx.Component:
    return rx.el.div(
        rx.cond(
            DashboardState.error != "",
            rx.el.div(
                rx.icon(
                    "circle-alert", class_name="h-5 w-5 shrink-0 text-red-400"
                ),
                rx.el.div(
                    rx.el.p(
                        DashboardState.error,
                        class_name="text-sm leading-relaxed text-red-200",
                    ),
                    rx.el.button(
                        "Try again",
                        on_click=DashboardState.load_dashboard,
                        class_name="mt-3 rounded-lg bg-white/5 px-4 py-2 text-sm text-white hover:bg-white/10",
                    ),
                ),
                role="alert",
                class_name="flex gap-3 rounded-2xl border border-red-400/20 bg-red-500/10 p-5",
            ),
        ),
        rx.cond(
            DashboardState.loading,
            rx.el.div(
                rx.el.p(
                    "Loading your dashboard…",
                    role="status",
                    class_name="mb-6 text-sm text-white/50",
                ),
                rx.el.div(
                    rx.foreach(
                        rx.Var.range(4),
                        lambda i: rx.el.div(
                            key=i,
                            class_name="h-36 animate-pulse rounded-3xl bg-white/5",
                        ),
                    ),
                    class_name="grid grid-cols-2 gap-4 lg:grid-cols-4",
                ),
                rx.el.div(
                    class_name="mt-8 h-64 animate-pulse rounded-3xl bg-white/5"
                ),
            ),
        ),
    )


def dashboard() -> rx.Component:
    return rx.el.main(
        dashboard_header(),
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    rx.el.p(
                        "YOUR CREATIVE SPACE",
                        class_name="text-[10px] font-semibold tracking-[0.18em] text-[#A78BFA]",
                    ),
                    rx.el.h1(
                        "Creator dashboard",
                        class_name="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl",
                    ),
                    rx.cond(
                        DashboardState.ready,
                        rx.el.p(
                            f"Welcome back, {DashboardState.display_name}. Let's make something worth watching.",
                            class_name="mt-3 text-sm leading-relaxed text-white/50",
                        ),
                    ),
                ),
                rx.el.button(
                    rx.icon("refresh-cw", class_name="h-4 w-4"),
                    "Refresh",
                    on_click=DashboardState.load_dashboard,
                    disabled=DashboardState.loading,
                    class_name="flex w-fit items-center gap-2 rounded-xl border border-white/10 bg-[#13131C] px-4 py-3 text-xs font-medium text-white/70 hover:border-white/25 hover:text-white disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-violet-400",
                ),
                class_name="mb-7 flex flex-col items-start justify-between gap-5 sm:flex-row sm:items-center",
            ),
            dashboard_feedback(),
            rx.cond(
                DashboardState.ready,
                rx.fragment(
                    plan_summary(),
                    creation_actions(),
                    information_panel(),
                    recent_projects(),
                ),
            ),
            class_name="mx-auto w-full max-w-7xl flex-1 px-5 py-8 sm:px-8 sm:py-10",
        ),
        rx.el.footer(
            "SHORTFORGE AI · MADE FOR CREATORS",
            class_name="px-5 pb-7 pt-8 text-center text-[9px] tracking-[0.2em] text-white/25",
        ),
        class_name="flex min-h-dvh w-full flex-col bg-[#0B0B10] font-['Inter'] text-white",
    )
