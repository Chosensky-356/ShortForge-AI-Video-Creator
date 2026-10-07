import reflex as rx
import reflex_enterprise as rxe

from app import models as models
from app.components.dashboard import dashboard
from app.components.short_creator import short_creator
from app.states.short_state import ShortState
from app.components.onboarding import wizard
from app.components.videos import videos_library
from app.components.billing import plans_page, settings_page
from app.states.billing_state import BillingState
from app.states.videos_state import VideosState
from app.states.dashboard_state import DashboardState
from app.states.onboarding_state import OnboardingState
from app.components.ad_creator import ad_creator, ad_detail
from app.states.ad_state import AdState
from app.components.ten_creator import ten_creator
from app.states.ten_state import TenState


def index() -> rx.Component:
    return dashboard()


app = rxe.App(
    theme=rx.theme(appearance="light"),
    head_components=[
        rx.el.link(rel="preconnect", href="https://fonts.googleapis.com"),
        rx.el.link(
            rel="preconnect",
            href="https://fonts.gstatic.com",
            cross_origin="",
        ),
        rx.el.link(
            href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap",
            rel="stylesheet",
        ),
    ],
)
app.add_page(
    index,
    route="/",
    title="ShortForge AI",
    on_load=DashboardState.load_dashboard,
)
app.add_page(
    short_creator,
    route="/create",
    title="Create a Short · ShortForge AI",
    on_load=ShortState.load_creator,
)
app.add_page(
    ten_creator,
    route="/create/ten",
    title="Create 10 Videos · ShortForge AI",
    on_load=TenState.load_creator,
)
app.add_page(
    ad_detail,
    route="/ads/[ad_id]",
    title="Saved ad draft · ShortForge AI",
    on_load=AdState.load_detail,
)
app.add_page(
    ad_creator,
    route="/create/product",
    title="Product Ad · ShortForge AI",
    on_load=AdState.load_creator,
)
app.add_page(
    ad_creator,
    route="/create/ugc",
    title="UGC Ad · ShortForge AI",
    on_load=AdState.load_creator,
)
app.add_page(
    videos_library,
    route="/videos",
    title="My Videos · ShortForge AI",
    on_load=VideosState.load_library,
)
app.add_page(
    plans_page,
    route="/plans",
    title="Unlock ShortForge Pro · ShortForge AI",
    on_load=BillingState.load_plans,
)
app.add_page(
    settings_page,
    route="/settings",
    title="Settings · ShortForge AI",
    on_load=BillingState.load_settings,
)
app.add_page(
    wizard,
    route="/onboarding",
    title="Get started · ShortForge AI",
    on_load=OnboardingState.load_profile(False),
)
