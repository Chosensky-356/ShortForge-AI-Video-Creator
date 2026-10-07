import reflex as rx

from reflex_enterprise.auth import User
from app.components.onboarding import brand
from app.states.billing_state import BillingState


def billing_header() -> rx.Component:
    return rx.el.header(
        brand(),
        rx.el.nav(
            rx.el.a(
                "Dashboard",
                href="/",
                class_name="rounded-lg px-3 py-2 text-xs text-white/60 hover:bg-white/5 hover:text-white",
            ),
            rx.el.a(
                "My Videos",
                href="/videos",
                class_name="rounded-lg px-3 py-2 text-xs text-white/60 hover:bg-white/5 hover:text-white",
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
            aria_label="Main navigation",
            class_name="flex flex-wrap items-center gap-1",
        ),
        class_name="flex w-full flex-wrap items-center justify-between gap-3 border-b border-white/8 px-5 py-5 sm:px-8",
    )


def billing_feedback() -> rx.Component:
    return rx.el.div(
        rx.cond(
            BillingState.error != "",
            rx.el.p(
                BillingState.error,
                role="alert",
                class_name="mb-4 rounded-2xl border border-red-400/20 bg-red-500/10 p-4 text-sm leading-relaxed text-red-200",
            ),
        ),
        rx.cond(
            BillingState.message != "",
            rx.el.p(
                BillingState.message,
                role="status",
                class_name="mb-4 rounded-2xl border border-blue-400/20 bg-[#448BFF]/5 p-4 text-sm leading-relaxed text-white/70",
            ),
        ),
        rx.cond(
            BillingState.warning != "",
            rx.el.p(
                BillingState.warning,
                role="status",
                class_name="mb-4 rounded-2xl border border-blue-400/20 bg-[#448BFF]/5 p-4 text-sm leading-relaxed text-white/70",
            ),
        ),
        rx.cond(
            BillingState.busy,
            rx.el.div(
                rx.el.p(
                    "Checking billing or waiting for checkout…",
                    role="status",
                    class_name="text-sm text-white/60",
                ),
                rx.el.button(
                    "Checkout closed or stuck? Stop waiting",
                    on_click=BillingState.stop_waiting,
                    class_name="mt-2 rounded-lg bg-white/5 px-3 py-2 text-xs text-[#C4B5FD] hover:bg-white/10",
                ),
                class_name="mb-5 rounded-2xl border border-white/10 bg-[#13131C] p-4",
            ),
        ),
        class_name="w-full",
    )


def subscription_panel() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.icon("shield-check", class_name="h-5 w-5 text-[#448BFF]"),
            rx.el.h2(
                "Your subscription",
                class_name="text-xl font-semibold text-white",
            ),
            class_name="flex items-center gap-3",
        ),
        rx.el.p(
            BillingState.plan,
            class_name="mt-4 text-2xl font-semibold text-white",
        ),
        rx.el.p(BillingState.status, class_name="mt-2 text-sm text-white/60"),
        rx.el.p(
            "Cancelling renewal keeps access until the paid term expires. An unverified browser payment never unlocks a plan.",
            class_name="mt-3 text-xs leading-relaxed text-white/45",
        ),
        rx.el.div(
            rx.el.button(
                "Refresh subscription",
                on_click=BillingState.refresh_subscription,
                disabled=BillingState.busy,
                class_name="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-xs text-white/80 hover:bg-white/10 disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-violet-400",
            ),
            rx.el.button(
                "Restore Purchases",
                on_click=BillingState.restore_purchases,
                disabled=BillingState.busy,
                class_name="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-xs text-white/80 hover:bg-white/10 disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-violet-400",
            ),
            rx.el.button(
                "Manage Subscription",
                on_click=BillingState.manage_subscription,
                disabled=BillingState.busy
                | (~BillingState.management_available),
                title="Requires a server-verified HTTPS management URL",
                class_name="rounded-xl bg-[#8B5CF6] px-4 py-3 text-xs font-semibold text-white hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-violet-400",
            ),
            class_name="mt-5 flex flex-wrap gap-3",
        ),
        rx.cond(
            ~BillingState.management_available,
            rx.el.p(
                "Subscription management is unavailable until RevenueCat returns a verified management link for this account.",
                class_name="mt-3 text-xs text-white/40",
            ),
        ),
        rx.el.p(
            "Web restore re-fetches customer information for your current signed-in account. It does not invoke Apple or Google receipt restoration.",
            class_name="mt-4 text-xs leading-relaxed text-white/45",
        ),
        class_name="w-full rounded-3xl border border-white/8 bg-[#13131C] p-5 sm:p-7",
    )


def usage_panel() -> rx.Component:
    return rx.el.section(
        rx.el.h2("Usage", class_name="text-xl font-semibold text-white"),
        rx.el.div(
            rx.el.div(
                rx.el.p(
                    BillingState.remaining,
                    class_name="text-3xl font-semibold text-white",
                ),
                rx.el.p("Remaining", class_name="mt-2 text-xs text-white/50"),
            ),
            rx.el.div(
                rx.el.p(
                    BillingState.used,
                    class_name="text-3xl font-semibold text-white",
                ),
                rx.el.p("Used", class_name="mt-2 text-xs text-white/50"),
            ),
            rx.el.div(
                rx.el.p(
                    BillingState.reserved,
                    class_name="text-3xl font-semibold text-white",
                ),
                rx.el.p("Reserved", class_name="mt-2 text-xs text-white/50"),
            ),
            class_name="mt-5 grid w-full grid-cols-3 gap-4",
        ),
        rx.el.p(
            f"{BillingState.allowance} videos per {BillingState.period} · Usage renews {BillingState.renews}",
            class_name="mt-5 text-xs leading-relaxed text-white/60",
        ),
        rx.el.p(
            "Up to 60 seconds per video. Only successful renders are charged. Pending reservations stay held across renewals. No plan is unlimited.",
            class_name="mt-3 text-xs leading-relaxed text-white/40",
        ),
        class_name="w-full rounded-3xl border border-white/8 bg-[#13131C] p-5 sm:p-7",
    )


def price_card(
    tier: str,
    title: str,
    price: str,
    term: str,
    quota: str,
    average: str,
    best: bool,
) -> rx.Component:
    return rx.el.article(
        rx.el.div(
            rx.el.h2(title, class_name="text-lg font-semibold text-white"),
            rx.cond(
                best,
                rx.el.span(
                    "BEST VALUE",
                    class_name="w-fit rounded-full bg-[#448BFF]/15 px-2.5 py-1 text-[9px] font-semibold tracking-wider text-[#448BFF]",
                ),
            ),
            class_name="flex min-h-8 flex-wrap items-center justify-between gap-2",
        ),
        rx.el.p(
            rx.cond(
                BillingState.catalogue_prices.get(tier, "") != "",
                BillingState.catalogue_prices.get(tier, ""),
                price,
            ),
            class_name="mt-5 text-3xl font-semibold tracking-tight text-white",
        ),
        rx.el.p(term, class_name="mt-1 text-xs text-white/50"),
        rx.cond(
            tier != "free",
            rx.el.p(
                rx.cond(
                    BillingState.catalogue_prices.get(tier, "") != "",
                    "Verified catalogue price · USD",
                    "Target price · unverified",
                ),
                class_name="mt-2 text-[10px] text-[#C4B5FD]",
            ),
        ),
        rx.el.p(quota, class_name="mt-6 text-sm font-semibold text-[#C4B5FD]"),
        rx.el.p(
            average,
            class_name="mt-2 min-h-8 text-xs leading-relaxed text-white/45",
        ),
        rx.el.div(
            rx.icon("check", class_name="h-4 w-4 shrink-0 text-[#A78BFA]"),
            rx.cond(
                tier == "free", "Basic plan benefits", "All Pro plan benefits"
            ),
            class_name="mt-3 flex items-center gap-2 text-xs text-white/60",
        ),
        rx.cond(
            tier == "free",
            rx.el.a(
                "Continue with Free",
                href="/",
                class_name="mt-7 block w-full rounded-xl border border-white/15 bg-white/5 px-4 py-3 text-center text-sm font-semibold text-white/80 hover:bg-white/10",
            ),
            rx.el.div(
                rx.el.button(
                    "Start Pro",
                    on_click=lambda: BillingState.start_checkout(tier),
                    disabled=BillingState.busy
                    | (~BillingState.checkout_enabled.get(tier, False)),
                    class_name="mt-7 w-full rounded-xl bg-[#8B5CF6] px-4 py-3 text-sm font-semibold text-white hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-35 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-violet-400",
                ),
                rx.cond(
                    ~BillingState.checkout_enabled.get(tier, False),
                    rx.el.p(
                        "Checkout unavailable · catalogue and server verification required",
                        class_name="mt-3 text-center text-[10px] text-white/40",
                    ),
                ),
            ),
        ),
        class_name=rx.cond(
            best,
            "flex w-full flex-col rounded-3xl border border-violet-400/35 bg-violet-500/8 p-5 sm:p-6",
            "flex w-full flex-col rounded-3xl border border-white/8 bg-[#13131C] p-5 sm:p-6",
        ),
    )


def benefit_row(feature: str, free: str, paid: str) -> rx.Component:
    return rx.el.tr(
        rx.el.th(
            feature,
            scope="row",
            class_name="w-1/3 px-4 py-4 text-left text-xs font-medium text-white/80 sm:px-6",
        ),
        rx.el.td(
            free,
            class_name="px-4 py-4 text-xs leading-relaxed text-white/50 sm:px-6",
        ),
        rx.el.td(
            paid,
            class_name="px-4 py-4 text-xs leading-relaxed text-[#C4B5FD] sm:px-6",
        ),
        class_name="border-t border-white/8 bg-transparent hover:bg-white/3",
    )


def benefit_matrix() -> rx.Component:
    return rx.el.section(
        rx.el.h2(
            "Compare your creative toolkit",
            class_name="text-xl font-semibold text-white",
        ),
        rx.el.p(
            "Plan benefits describe intended access, not currently working generation features. AI creation, premium voices, avatar/UGC generation, bulk rendering and premium exports are not yet wired. Buying a plan does not make those features available today.",
            class_name="mt-3 text-sm leading-relaxed text-white/55",
        ),
        rx.el.div(
            rx.el.table(
                rx.el.thead(
                    rx.el.tr(
                        rx.el.th(
                            rx.icon(
                                "sparkles",
                                class_name="mr-2 inline h-4 w-4 text-[#A78BFA]",
                            ),
                            "Benefit",
                            class_name="px-4 py-4 text-left text-xs font-semibold text-white sm:px-6",
                        ),
                        rx.el.th(
                            rx.icon(
                                "user",
                                class_name="mr-2 inline h-4 w-4 text-white/50",
                            ),
                            "Free",
                            class_name="px-4 py-4 text-left text-xs font-semibold text-white sm:px-6",
                        ),
                        rx.el.th(
                            rx.icon(
                                "crown",
                                class_name="mr-2 inline h-4 w-4 text-[#A78BFA]",
                            ),
                            "All paid plans",
                            class_name="px-4 py-4 text-left text-xs font-semibold text-white sm:px-6",
                        ),
                    )
                ),
                rx.el.tbody(
                    benefit_row(
                        "Video allowance",
                        "3 / month",
                        "25 / month · 80 / 3 months · 360 / year",
                    ),
                    benefit_row(
                        "Voices & styles",
                        "Basic voices and styles",
                        "Premium voices and styles · planned",
                    ),
                    benefit_row(
                        "Watermark",
                        "Watermarked output · planned",
                        "No watermark · planned",
                    ),
                    benefit_row(
                        "Export",
                        "Standard export · planned",
                        "Premium export · planned",
                    ),
                    benefit_row(
                        "Premium UGC",
                        "Not included",
                        "Pro access · planned; avatar video unavailable",
                    ),
                    benefit_row(
                        "Bulk creation",
                        "Not included",
                        "Pro access · planned; no automatic batch rendering",
                    ),
                    benefit_row(
                        "Shorts & product ads",
                        "Basic workflows · planned",
                        "Pro creative workflows · planned",
                    ),
                    benefit_row(
                        "Video length", "Up to 60 seconds", "Up to 60 seconds"
                    ),
                ),
                class_name="table-auto w-full min-w-[480px] bg-[#13131C]",
            ),
            class_name="mt-6 overflow-hidden overflow-x-auto rounded-2xl border border-white/10",
        ),
        class_name="mt-10 w-full",
    )


def plans_page() -> rx.Component:
    return rx.el.main(
        billing_header(),
        rx.el.div(
            rx.el.div(
                rx.el.span(
                    "MORE ROOM FOR YOUR IDEAS",
                    class_name="text-[10px] font-semibold tracking-[0.18em] text-[#A78BFA]",
                ),
                rx.el.h1(
                    "Unlock ShortForge Pro",
                    class_name="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-5xl",
                ),
                rx.el.p(
                    "Create more content. Create better ads. Grow faster.",
                    class_name="mt-4 text-sm text-white/60 sm:text-base",
                ),
                class_name="mb-8 text-center",
            ),
            billing_feedback(),
            rx.el.div(
                rx.icon(
                    "shield-check", class_name="h-5 w-5 shrink-0 text-[#A78BFA]"
                ),
                rx.el.div(
                    rx.el.p(
                        BillingState.catalogue_status,
                        role="status",
                        class_name="text-sm leading-relaxed text-white/70",
                    ),
                    rx.el.button(
                        "Refresh catalogue",
                        on_click=BillingState.fetch_catalogue,
                        disabled=BillingState.busy
                        | BillingState.catalogue_loading,
                        class_name="mt-3 rounded-lg bg-white/5 px-3 py-2 text-xs text-[#C4B5FD] hover:bg-white/10 disabled:opacity-40",
                    ),
                ),
                class_name="mb-5 flex gap-3 rounded-2xl border border-violet-400/20 bg-[#13131C] p-4",
            ),
            rx.el.div(
                price_card(
                    "free",
                    "Free",
                    "$0",
                    "Free plan",
                    "3 videos / month",
                    "Resets each UTC calendar month",
                    False,
                ),
                price_card(
                    "starter",
                    "Starter",
                    "$19.99",
                    "/ month",
                    "25 videos / month",
                    "Monthly billing term",
                    False,
                ),
                price_card(
                    "growth",
                    "Growth",
                    "$49.99",
                    "every 3 months",
                    "80 videos / 3-month term",
                    "26/mo average · allowance is per term, not monthly",
                    True,
                ),
                price_card(
                    "yearly",
                    "Pro Yearly",
                    "$149.99",
                    "/ year",
                    "360 videos / year",
                    "30/mo average · allowance is annual, not monthly",
                    True,
                ),
                class_name="grid w-full grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4",
            ),
            rx.el.p(
                "Prices are in USD. Paid plans are recurring subscriptions. Checkout must show the matching price and billing term before you authorize payment. Taxes, if applicable, are shown at checkout. Averages do not create monthly sub-allowances.",
                class_name="mt-5 text-xs leading-relaxed text-white/45",
            ),
            rx.el.div(
                rx.icon("info", class_name="h-5 w-5 shrink-0 text-[#448BFF]"),
                rx.el.p(
                    "Checkout remains disabled until all three Default offering prices and terms match the targets and server verification is configured. Test Store checkout is for testing only. Generation and rendering are not available yet. No payment, video, or paid access is simulated.",
                    class_name="text-sm leading-relaxed text-white/65",
                ),
                class_name="mt-6 flex gap-3 rounded-2xl border border-blue-400/20 bg-[#448BFF]/5 p-5",
            ),
            benefit_matrix(),
            rx.el.div(
                subscription_panel(),
                usage_panel(),
                class_name="mt-8 grid w-full grid-cols-1 gap-5 lg:grid-cols-2",
            ),
            class_name="mx-auto w-full max-w-7xl px-5 py-10 sm:px-8",
        ),
        class_name="min-h-dvh w-full bg-[#0B0B10] font-['Inter'] text-white",
    )


def preferences_panel() -> rx.Component:
    return rx.el.section(
        rx.el.h2("Preferences", class_name="text-xl font-semibold text-white"),
        rx.el.form(
            rx.el.label(
                rx.el.input(
                    type="checkbox",
                    name="notifications",
                    default_checked=BillingState.notifications,
                    key=BillingState.notifications.to_string(),
                    class_name="h-4 w-4 accent-violet-500",
                ),
                "Notifications",
                class_name="mt-5 flex items-center gap-3 text-sm text-white/80",
            ),
            rx.el.p(
                "Save your notification preference. No notification service is connected yet.",
                class_name="mt-2 text-xs text-white/45",
            ),
            rx.el.label(
                "Language",
                html_for="settings-language",
                class_name="mt-5 block text-sm text-white/80",
            ),
            rx.el.div(
                rx.el.select(
                    rx.el.option("English", value="en"),
                    rx.el.option("Español", value="es"),
                    rx.el.option("Français", value="fr"),
                    rx.el.option("Deutsch", value="de"),
                    rx.el.option("Português", value="pt"),
                    id="settings-language",
                    name="language",
                    default_value=BillingState.language,
                    key=BillingState.language,
                    class_name="w-full appearance-none rounded-xl border border-white/15 bg-[#0B0B10] px-4 py-3 pr-10 text-sm text-white focus:outline-2 focus:outline-violet-400",
                ),
                rx.icon(
                    "chevron-down",
                    class_name="pointer-events-none absolute right-4 top-3.5 h-4 w-4 text-white/50",
                ),
                class_name="relative mt-2",
            ),
            rx.el.p(
                "Language is saved as a preference; this app and creator output are not translated yet.",
                class_name="mt-2 text-xs leading-relaxed text-white/45",
            ),
            rx.el.button(
                "Save preferences",
                type="submit",
                disabled=BillingState.busy | (~BillingState.ready),
                class_name="mt-5 rounded-xl bg-[#8B5CF6] px-5 py-3 text-xs font-semibold text-white hover:bg-violet-500 disabled:opacity-40",
            ),
            on_submit=BillingState.save_preferences,
        ),
        class_name="w-full rounded-3xl border border-white/8 bg-[#13131C] p-5 sm:p-7",
    )


def resource_link(label: str, key: str) -> rx.Component:
    return rx.cond(
        BillingState.links[key] != "",
        rx.el.a(
            label,
            rx.icon("arrow-up-right", class_name="h-4 w-4"),
            href=BillingState.links[key],
            target="_blank",
            rel="noopener noreferrer",
            class_name="flex items-center justify-between rounded-xl border border-white/10 bg-white/3 px-4 py-3 text-sm text-white/80 hover:bg-white/8",
        ),
        rx.el.div(
            label,
            rx.el.span(
                "Unavailable · not configured",
                class_name="text-[10px] text-white/35",
            ),
            class_name="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-white/5 bg-transparent px-4 py-3 text-sm text-white/45",
        ),
    )


def settings_page() -> rx.Component:
    return rx.el.main(
        billing_header(),
        rx.el.div(
            rx.el.h1(
                "Settings",
                class_name="mb-3 text-3xl font-semibold tracking-tight text-white",
            ),
            rx.el.p(
                "Your account, subscription and creator preferences.",
                class_name="mb-8 text-sm text-white/50",
            ),
            billing_feedback(),
            rx.el.div(
                rx.el.section(
                    rx.el.h2(
                        "Account", class_name="text-xl font-semibold text-white"
                    ),
                    rx.el.p(
                        User.name,
                        class_name="mt-5 break-words text-base font-medium text-white",
                    ),
                    rx.el.p(
                        User.email,
                        class_name="mt-2 break-words text-sm text-white/55",
                    ),
                    rx.el.p(
                        "Identity is managed by your sign-in provider. Your settings and library are private to this signed-in account.",
                        class_name="mt-4 text-xs leading-relaxed text-white/45",
                    ),
                    rx.el.button(
                        rx.icon("log-out", class_name="h-4 w-4"),
                        "Sign Out",
                        on_click=User.logout,
                        class_name="mt-5 flex w-fit items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-xs text-white/70 hover:bg-white/10",
                    ),
                    class_name="w-full rounded-3xl border border-white/8 bg-[#13131C] p-5 sm:p-7",
                ),
                subscription_panel(),
                usage_panel(),
                preferences_panel(),
                rx.el.section(
                    rx.el.h2(
                        "Privacy & support",
                        class_name="text-xl font-semibold text-white",
                    ),
                    rx.el.div(
                        resource_link("Privacy Policy", "privacy"),
                        resource_link("Terms", "terms"),
                        resource_link("Help", "help"),
                        resource_link("Contact Support", "support"),
                        class_name="mt-5 flex flex-col gap-3",
                    ),
                    rx.el.p(
                        "Usage analytics records only allowlisted lifecycle events, account ownership, project IDs where applicable, and timestamps. No scripts, product briefs, names, emails or payment details are stored in analytics events.",
                        class_name="mt-5 text-xs leading-relaxed text-white/45",
                    ),
                    class_name="w-full rounded-3xl border border-white/8 bg-[#13131C] p-5 sm:p-7 lg:col-span-2",
                ),
                class_name="grid w-full grid-cols-1 items-start gap-5 lg:grid-cols-2",
            ),
            class_name="mx-auto w-full max-w-7xl px-5 py-8 sm:px-8 sm:py-10",
        ),
        class_name="min-h-dvh w-full bg-[#0B0B10] font-['Inter'] text-white",
    )
