import reflex as rx
import reflex_enterprise as rxe

from collections.abc import Sequence
from reflex_enterprise.auth import AuthUserState
from app.components.onboarding import brand, illustration


class LoginRedirectState(rx.State):
    @rxe.event(auth=False)
    def continue_to_app(self):
        raw = self.router.page.params.get("redirect_to", "/")
        target = (
            raw
            if isinstance(raw, str)
            and raw.startswith("/")
            and not raw.startswith("//")
            # Browsers treat \ as / and strip tab/CR/LF in URLs, so
            # "/\host" and "/\t/host" both become "//host".
            and not any(c in raw for c in "\t\r\n\\")
            else "/"
        )
        return rx.redirect(target)


def _login_buttons(providers: Sequence) -> list[rx.Component]:
    return [
        provider.get_login_button(
            rx.el.button(
                "Sign in",
                rx.icon("arrow-right", class_name="h-4 w-4"),
                class_name="flex min-h-14 w-full items-center justify-center gap-3 rounded-2xl bg-[#8B5CF6] px-6 py-4 text-sm font-semibold text-white hover:bg-violet-500 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-violet-400",
            )
        )
        for provider in providers
    ]


def login_page(*, providers: Sequence, **context) -> rx.Component:
    return rx.fragment(
        rx.el.main(
            rx.el.header(
                brand(), class_name="mx-auto w-full max-w-5xl px-5 py-6 sm:px-8"
            ),
            rx.el.section(
                rx.el.div(
                    rx.el.p(
                        "YOUR IDEAS DESERVE TO BE SEEN",
                        class_name="mb-7 text-center text-[10px] font-semibold tracking-[0.18em] text-white/45",
                    ),
                    illustration(
                        "sparkles",
                        "From spark to short",
                        "A creative head start, powered by AI",
                    ),
                    rx.el.h1(
                        "Meet your next creative chapter.",
                        class_name="text-center text-3xl font-semibold tracking-tight text-white sm:text-4xl",
                    ),
                    rx.el.p(
                        "Sign in to ShortForge AI and turn your ideas into short videos.",
                        class_name="mx-auto mt-4 max-w-xs text-center text-base leading-relaxed text-white/60",
                    ),
                    rx.el.div(
                        *_login_buttons(providers),
                        class_name="mt-8 flex w-full flex-col gap-3",
                    ),
                    rx.el.p(
                        rx.icon(
                            "shield-check",
                            class_name="h-3.5 w-3.5 text-[#448BFF]",
                        ),
                        "Secure sign-in with your Reflex account",
                        class_name="mt-5 flex items-center justify-center gap-2 text-[11px] text-white/45",
                    ),
                    rx.el.p(
                        "No purchase required to get started",
                        class_name="mt-2 text-center text-[11px] text-white/30",
                    ),
                    class_name="w-full max-w-md rounded-[28px] border border-white/8 bg-[#13131C] p-6 sm:p-9",
                ),
                class_name="flex w-full flex-1 items-center justify-center px-4 py-6",
            ),
            rx.el.footer(
                "SHORTFORGE AI · MADE FOR CREATORS",
                class_name="px-4 pb-6 pt-3 text-center text-[9px] tracking-[0.2em] text-white/25",
            ),
            class_name="flex min-h-dvh w-full flex-col bg-[#0B0B10] font-['Inter'] text-white",
        ),
        rx.cond(
            AuthUserState.provider_name != "",
            rx.el.div(on_mount=LoginRedirectState.continue_to_app),
        ),
    )
