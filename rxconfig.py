import reflex as rx
import reflex_enterprise as rxe

config = rxe.Config(
    app_name="app",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
        rxe.AuthPlugin(auth=True, login_page="app.pages.auth_login.login_page"),
    ],
)
