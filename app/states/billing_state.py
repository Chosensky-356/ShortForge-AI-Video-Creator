import reflex as rx
import reflex_enterprise as rxe

import json
import logging
import os
import re
from typing import Any

from app.services.analytics import record_event
from app.services.billing import (
    checkout_config,
    catalogue_config,
    public_sdk_key,
    validate_catalogue,
    web_operation,
    safe_https_url,
)
from uuid import uuid4
from app.services.usage import authenticated_subject, sync_usage, verify_access
from sqlalchemy import text


class BillingState(rx.State):
    busy: bool = False
    ready: bool = False
    error: str = ""
    message: str = ""
    plan: str = "Free"
    status: str = "Paid status not verified"
    warning: str = ""
    remaining: int = 0
    used: int = 0
    reserved: int = 0
    allowance: int = 3
    period: str = "month"
    renews: str = ""
    management_available: bool = False
    checkout_enabled: dict[str, bool] = {
        "starter": False,
        "growth": False,
        "yearly": False,
    }
    catalogue_loading: bool = False
    catalogue_status: str = "Target prices · catalogue not verified"
    catalogue_prices: dict[str, str] = {
        "starter": "",
        "growth": "",
        "yearly": "",
    }
    catalogue_request: str = rxe.field("", auth=True)
    notifications: bool = False
    language: str = "en"
    links: dict[str, str] = {
        "privacy": "",
        "terms": "",
        "help": "",
        "support": "",
    }
    pending_operation: str = rxe.field("", auth=True)

    @rxe.event
    async def load_plans(self):
        self.message = ""
        self.error = ""
        self.busy = False
        self.pending_operation = ""
        self._clear_catalogue()
        yield BillingState.refresh_subscription
        yield BillingState.fetch_catalogue
        try:
            await record_event("paywall_viewed")
        except Exception as e:
            logging.exception(
                f"Error: analytics unavailable ({type(e).__name__})"
            )

    def _clear_catalogue(self):
        self.catalogue_request = str(uuid4())
        self.catalogue_loading = False
        self.catalogue_prices = {"starter": "", "growth": "", "yearly": ""}
        self.checkout_enabled = {
            "starter": False,
            "growth": False,
            "yearly": False,
        }
        self.catalogue_status = "Target prices · catalogue not verified"

    def _update_checkout(self):
        matches = all(self.catalogue_prices.values())
        self.checkout_enabled = {
            tier: matches and bool(checkout_config(tier))
            for tier in ("starter", "growth", "yearly")
        }

    @rxe.event
    async def fetch_catalogue(self):
        if self.busy:
            return
        self._clear_catalogue()
        config = catalogue_config()
        if not config:
            self.catalogue_status = "Catalogue unavailable: missing or invalid public SDK key. Add the Test Store public key in app Secrets; target prices are unverified."
            return
        self.catalogue_loading = True
        self.catalogue_status = (
            "Loading Default offering · target prices are unverified…"
        )
        request = self.catalogue_request
        yield
        try:
            config["subject"] = await authenticated_subject()
            yield rx.call_script(
                web_operation(config, "offerings"),
                callback=lambda result: BillingState.catalogue_result(
                    result, request
                ),
            )
        except Exception as e:
            logging.exception(
                f"Error: catalogue unavailable ({type(e).__name__})"
            )
            self.catalogue_loading = False
            self.catalogue_status = "Catalogue could not be loaded. Target prices remain unverified; retry shortly."

    @rxe.event
    def catalogue_result(self, result: str, request: str):
        if request != self.catalogue_request or not self.catalogue_loading:
            return
        self.catalogue_loading = False
        try:
            self.catalogue_prices = validate_catalogue(result)
            self._update_checkout()
            suffix = "Checkout available; paid access still requires server confirmation."
            if not all(self.checkout_enabled.values()):
                suffix = (
                    "Checkout disabled: server verification is not configured."
                )
            self.catalogue_status = f"Verified USD catalogue · prices and billing terms match all three targets. {suffix}"
        except ValueError as e:
            self.catalogue_prices = {"starter": "", "growth": "", "yearly": ""}
            self._update_checkout()
            self.catalogue_status = str(e)

    @rxe.event
    def load_settings(self):
        self.message = ""
        return BillingState.refresh_subscription

    async def _refresh(self) -> bool:
        self.ready = False
        self.management_available = False
        access = await verify_access()
        async with rx.asession() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT onboarding_completed, onboarding_answers FROM creator_profiles WHERE identity_subject = :subject LIMIT 1"
                    ),
                    {"subject": access.subject},
                )
            ).one_or_none()
            if row is None or not row[0]:
                return False
            snapshot = await sync_usage(session, access)
            await session.commit()
        answers = row[1] if isinstance(row[1], dict) else {}
        preferences = answers.get("preferences", {})
        if not isinstance(preferences, dict):
            preferences = {}
        self.notifications = preferences.get("notifications") is True
        language = preferences.get("language", "en")
        self.language = (
            language if language in ("en", "es", "fr", "de", "pt") else "en"
        )
        self.plan = {
            "free": "Free",
            "starter": "Starter",
            "growth": "Growth",
            "yearly": "Pro Yearly",
        }[access.tier]
        self.status = access.subscription_status
        self.warning = access.warning
        self.management_available = bool(
            access.verified and access.management_url
        )
        self.used, self.reserved = snapshot.used, snapshot.reserved
        self.remaining, self.allowance = snapshot.remaining, access.limit
        self.period = access.period_label
        self.renews = snapshot.reset_at.strftime("%b %d, %Y at %H:%M UTC")
        self._update_checkout()
        self.links = {
            "privacy": safe_https_url(
                os.getenv("SHORTFORGE_PRIVACY_POLICY_URL", "")
            ),
            "terms": safe_https_url(os.getenv("SHORTFORGE_TERMS_URL", "")),
            "help": safe_https_url(os.getenv("SHORTFORGE_HELP_URL", "")),
            "support": "",
        }
        email = os.getenv("SHORTFORGE_SUPPORT_EMAIL", "").strip()
        if re.fullmatch(
            r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+",
            email,
        ):
            self.links["support"] = f"mailto:{email}"
        self.ready = True
        return True

    @rxe.event
    async def refresh_subscription(self):
        if self.busy:
            return
        self.busy = True
        self.error = ""
        yield
        try:
            if not await self._refresh():
                yield rx.redirect("/onboarding")
        except Exception as e:
            logging.exception(
                f"Error: subscription refresh failed ({type(e).__name__})"
            )
            self.error = "Your subscription could not be refreshed. No paid access was granted. Please try again."
        finally:
            self.busy = False

    @rxe.event
    async def start_checkout(self, tier: str):
        if self.busy or tier not in ("starter", "growth", "yearly"):
            return
        config = checkout_config(tier)
        if (
            not config
            or not all(self.catalogue_prices.values())
            or self.catalogue_loading
        ):
            self.message = "Checkout is unavailable until the catalogue matches all target prices and server verification is configured. No payment has been taken."
            return
        self.busy = True
        self.error = ""
        self.message = "Opening secure checkout… Cancel checkout to return without purchasing."
        self.pending_operation = "purchase"
        try:
            subject = await authenticated_subject()
            config["subject"] = subject
            yield rx.call_script(
                web_operation(config, "purchase"),
                callback=BillingState.web_result,
            )
        except Exception as e:
            logging.exception(
                f"Error: checkout unavailable ({type(e).__name__})"
            )
            self.busy = False
            self.error = "Checkout could not be opened. Please try again."

    @rxe.event
    async def restore_purchases(self):
        if self.busy:
            return
        self.busy = True
        self.error = ""
        self.message = "Checking purchases for your signed-in account…"
        self.pending_operation = "restore"
        yield
        try:
            await record_event("restore")
            subject = await authenticated_subject()
            key = public_sdk_key()
            if key:
                yield rx.call_script(
                    web_operation({"key": key, "subject": subject}, "restore"),
                    callback=BillingState.web_result,
                )
            else:
                if not await self._refresh():
                    yield rx.redirect("/onboarding")
                self.message = "Account re-check complete. Billing is not configured; no paid subscription could be verified. Web restore checks the same account, not Apple or Google receipts."
                self.busy = False
        except Exception as e:
            logging.exception(
                f"Error: restore unavailable ({type(e).__name__})"
            )
            self.busy = False
            self.error = "Purchases could not be checked. No subscription changes were made."

    @rxe.event
    async def web_result(self, result: str):
        if self.pending_operation not in ("purchase", "restore"):
            return
        operation = self.pending_operation
        self.pending_operation = ""
        try:
            if not await self._refresh():
                yield rx.redirect("/onboarding")
                return
            messages = {
                "cancelled": "Checkout cancelled. No subscription was confirmed.",
                "payment": "Payment could not be completed. Check your payment method and try again.",
                "network": "Billing could not be reached. Check your connection and try again.",
                "mapping": "The Default offering or matching package, USD price, or billing term is unavailable. Checkout was not started.",
                "missing_default": "The Default offering is missing. Checkout was not started.",
                "missing_key": "A valid public billing SDK key is unavailable. Checkout was not started.",
                "sdk": "The browser billing SDK could not load. Check your connection or content blocker and try again.",
                "failed": "Billing could not complete this request. Please try again.",
            }
            if result != "ok":
                if operation == "purchase":
                    self._clear_catalogue()
                    self.catalogue_status = "Catalogue needs a fresh check after checkout did not complete. Target prices are unverified."
                self.error = messages.get(result, messages["failed"])
                self.message = ""
            elif self.plan != "Free" and self.status.startswith("Active"):
                self.message = "Subscription verified. Your current plan and usage are shown below."
            elif operation == "restore" and not self.warning:
                self.message = "Account checked. No active supported paid subscription was found. Web restore re-fetches this account; it does not restore native store receipts."
            else:
                self.message = "Browser billing completed, but an active paid subscription has not been verified by the server. No paid access was granted. Refresh again shortly."
        except Exception as e:
            logging.exception(
                f"Error: billing confirmation unavailable ({type(e).__name__})"
            )
            self.error = "Payment status could not be verified. Do not purchase again; refresh your subscription first."
        finally:
            self.busy = False

    @rxe.event
    def stop_waiting(self):
        self.busy = False
        self.pending_operation = ""
        self.message = "No purchase has been confirmed here. If checkout is still open, close it first. Refresh your subscription before trying another purchase."

    @rxe.event
    async def manage_subscription(self):
        if self.busy:
            return
        self.busy = True
        self.error = ""
        yield
        try:
            access = await verify_access()
            url = safe_https_url(access.management_url)
            if access.verified and url:
                yield rx.redirect(url, external=True)
            else:
                self.message = "A verified subscription management link is unavailable. Refresh your subscription or contact support when configured."
        except Exception as e:
            logging.exception(
                f"Error: subscription management unavailable ({type(e).__name__})"
            )
            self.error = (
                "Subscription management could not be opened. Please try again."
            )
        finally:
            self.busy = False

    @rxe.event
    async def save_preferences(self, form_data: dict[str, Any]):
        if self.busy:
            return
        language = str(form_data.get("language", "en"))
        if language not in ("en", "es", "fr", "de", "pt"):
            self.error = "Select a supported language."
            return
        enabled = form_data.get("notifications") in (True, "on", "true")
        self.busy = True
        self.error = ""
        yield
        try:
            subject = await authenticated_subject()
            preferences = json.dumps(
                {"notifications": enabled, "language": language}
            )
            async with rx.asession() as session:
                result = await session.execute(
                    text("""
                    UPDATE creator_profiles SET onboarding_answers =
                    jsonb_set(COALESCE(onboarding_answers, '{}'::jsonb), '{preferences}', CAST(:preferences AS jsonb), true),
                    updated_at = CURRENT_TIMESTAMP WHERE identity_subject = :subject
                """),
                    {"subject": subject, "preferences": preferences},
                )
                if result.rowcount != 1:
                    raise ValueError("Profile unavailable")
                await session.commit()
            self.notifications = enabled
            self.language = language
            self.message = "Preferences saved. Notification delivery and translated creator output are not available yet."
        except Exception as e:
            logging.exception(
                f"Error: preferences not saved ({type(e).__name__})"
            )
            self.error = "Preferences could not be saved. Please try again."
        finally:
            self.busy = False
