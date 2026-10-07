import reflex as rx

import unittest
import subprocess
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.services.analytics import append_event, subscription_transition
from app.services.billing import (
    PRODUCT_IDS,
    EXPECTED_TERMS,
    catalogue_config,
    checkout_config,
    product_ids,
    public_sdk_key,
    validate_catalogue,
    safe_https_url,
    web_operation,
)
import json
from app.services.usage import _Profile, _free, _parse_access, sync_usage


class BillingGuardrailTests(unittest.TestCase):
    def test_generated_javascript_syntax(self):
        config = {
            "key": "test_synthetic_fixture",
            "subject": "synthetic-user",
            "products": json.dumps(PRODUCT_IDS),
            "tier": "starter",
            "product": PRODUCT_IDS["starter"],
        }
        for operation in ("offerings", "purchase", "restore"):
            with self.subTest(operation=operation):
                result = subprocess.run(
                    ["node", "--check"],
                    input=web_operation(config, operation),
                    text=True,
                    capture_output=True,
                    timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_management_url_validation(self):
        self.assertEqual(
            safe_https_url("https://example.com/manage"),
            "https://example.com/manage",
        )
        for value in (
            "http://example.com",
            "javascript:alert(1)",
            "//example.com",
            "https://user:password@example.com",
            "https://example.com/%0a",
            "https://example.com\\evil",
            "https://example.com:8080",
        ):
            self.assertEqual(safe_https_url(value), "")

    def test_missing_config_disables_checkout(self):
        with patch.dict("os.environ", {}, clear=True):
            for tier in ("starter", "growth", "yearly"):
                self.assertEqual(checkout_config(tier), {})

    def test_only_public_key_in_browser_config(self):
        with patch.dict(
            "os.environ",
            {
                "REVENUECAT_SECRET_API_KEY": "server-only-test-value",
                "REVENUECAT_WEB_PUBLIC_API_KEY": "rcb_test_public",
                "REVENUECAT_STARTER_PRODUCT_ID": "monthly",
                "REVENUECAT_GROWTH_PRODUCT_ID": "quarterly",
                "REVENUECAT_YEARLY_PRODUCT_ID": "annual",
                "REVENUECAT_STARTER_PACKAGE_ID": "$rc_monthly",
            },
            clear=True,
        ):
            config = checkout_config("starter")
        self.assertEqual(config["product"], "monthly")
        self.assertNotIn(
            "server-only-test-value", web_operation(config, "purchase")
        )
        self.assertIn("offerings.current", web_operation(config, "purchase"))
        self.assertNotIn(
            "offerings.all['default']", web_operation(config, "purchase")
        )
        self.assertNotIn("restorePurchases", web_operation(config, "restore"))

    def test_default_mapping_and_configuration_gates(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(
                product_ids(),
                {
                    "starter": "starter",
                    "yearly": "pro",
                    "growth": "shortforge_growth_3months",
                },
            )
            self.assertEqual(public_sdk_key(), "")
        for prefix in ("test_", "rcb_"):
            with patch.dict(
                "os.environ",
                {"VITE_REVENUECAT_API_KEY": f"{prefix}synthetic_fixture"},
                clear=True,
            ):
                self.assertTrue(catalogue_config())
                self.assertEqual(checkout_config("starter"), {})
                with patch.dict(
                    "os.environ",
                    {"REVENUECAT_SECRET_API_KEY": "server-only-fixture"},
                ):
                    for tier, product in PRODUCT_IDS.items():
                        self.assertEqual(
                            checkout_config(tier)["product"], product
                        )
        with patch.dict(
            "os.environ",
            {
                "VITE_REVENUECAT_API_KEY": "sk_rejected",
                "REVENUECAT_WEB_PUBLIC_API_KEY": "rcb_fixture",
            },
            clear=True,
        ):
            self.assertFalse(public_sdk_key())
        with patch.dict(
            "os.environ",
            {"REVENUECAT_WEB_PUBLIC_API_KEY": "rcb_fixture"},
            clear=True,
        ):
            self.assertEqual(public_sdk_key(), "rcb_fixture")

    def test_catalogue_validation_and_read_only_script(self):
        with patch.dict(
            "os.environ",
            {"VITE_REVENUECAT_API_KEY": "test_synthetic_fixture"},
            clear=True,
        ):
            config = catalogue_config()
            script = web_operation(config, "offerings")
            self.assertIn("purchases-js@1.67.1", script)
            self.assertIn("currency: 'USD'", script)
            self.assertIn("webBillingProduct", script)
            self.assertIn("offerings.current", script)
            self.assertIn("missing_default", script)
            self.assertNotIn("purchases.purchase(", script)
            self.assertNotIn("entitlements", script)
            rows = [
                {
                    "productId": PRODUCT_IDS[tier],
                    "price": {
                        "formattedPrice": f"${micros / 1_000_000:.2f}",
                        "amountMicros": micros,
                        "currency": "USD",
                    },
                    "period": {"number": number, "unit": unit},
                    "packages": [tier],
                }
                for tier, (micros, number, unit) in EXPECTED_TERMS.items()
            ]
            self.assertEqual(
                validate_catalogue(json.dumps({"products": rows})),
                {"starter": "$19.99", "growth": "$49.99", "yearly": "$149.99"},
            )
            for field, bad in (
                ("currency", "EUR"),
                ("amountMicros", 1),
                ("amountMicros", True),
                ("formattedPrice", ""),
            ):
                changed = json.loads(json.dumps(rows))
                changed[0]["price"][field] = bad
                with self.assertRaises(ValueError):
                    validate_catalogue(json.dumps({"products": changed}))
            for invalid in (
                "sdk",
                "network",
                "missing_default",
                "mapping",
                "{}",
                "null",
                "not json",
                json.dumps({"products": rows[:2]}),
            ):
                with self.assertRaises(ValueError):
                    validate_catalogue(invalid)
            rows[0]["period"]["number"] = 3
            with self.assertRaises(ValueError):
                validate_catalogue(json.dumps({"products": rows}))
        purchase = web_operation(
            {
                "key": "rcb_fixture",
                "products": json.dumps(PRODUCT_IDS),
                "tier": "starter",
            },
            "purchase",
        )
        self.assertLess(
            purchase.index("period.number !== expected.number"),
            purchase.index("purchases.purchase("),
        )
        self.assertIn("matches.length !== 1", purchase)

    def test_configured_entitlement_and_compatibility(self):
        now = datetime(2026, 2, 15, tzinfo=timezone.utc)
        entitlement = {
            "product_identifier": "starter",
            "purchase_date": "2026-02-01T00:00:00Z",
            "expires_date": "2026-03-01T00:00:00Z",
        }
        products = {"starter": ("starter", 25, 1)}
        with patch.dict(
            "os.environ",
            {"VITE_REVENUECAT_ENTITLEMENT": "creator_access"},
            clear=True,
        ):
            self.assertEqual(
                _parse_access(
                    "owner",
                    {
                        "subscriber": {
                            "entitlements": {"creator_access": entitlement}
                        }
                    },
                    products,
                    now,
                ).limit,
                25,
            )
            self.assertEqual(
                _parse_access(
                    "owner",
                    {"subscriber": {"entitlements": {"pro": entitlement}}},
                    products,
                    now,
                ).limit,
                3,
            )
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(
                _parse_access(
                    "owner",
                    {"subscriber": {"entitlements": {"pro": entitlement}}},
                    products,
                    now,
                ).limit,
                25,
            )

    def test_active_cancellation_keeps_access(self):
        payload = {
            "subscriber": {
                "management_url": "https://example.com/manage",
                "entitlements": {
                    "pro": {
                        "product_identifier": "monthly",
                        "purchase_date": "2026-02-01T00:00:00Z",
                        "expires_date": "2026-03-01T00:00:00Z",
                    }
                },
                "subscriptions": {
                    "monthly": {
                        "purchase_date": "2026-02-01T00:00:00Z",
                        "unsubscribe_detected_at": "2026-02-10T00:00:00Z",
                    }
                },
            }
        }
        access = _parse_access(
            "owner",
            payload,
            {"monthly": ("starter", 25, 1)},
            datetime(2026, 2, 15, tzinfo=timezone.utc),
        )
        self.assertTrue(access.verified)
        self.assertEqual(access.tier, "starter")
        self.assertIn("renewal cancelled", access.subscription_status)
        self.assertTrue(access.renewal_cancelled)
        payload["subscriber"]["subscriptions"]["monthly"][
            "billing_issues_detected_at"
        ] = "2026-02-11T00:00:00Z"
        billing_issue = _parse_access(
            "owner",
            payload,
            {"monthly": ("starter", 25, 1)},
            datetime(2026, 2, 15, tzinfo=timezone.utc),
        )
        self.assertIn("billing issue", billing_issue.subscription_status)
        self.assertTrue(billing_issue.renewal_cancelled)
        expired = _parse_access(
            "owner",
            payload,
            {"monthly": ("starter", 25, 1)},
            datetime(2026, 3, 2, tzinfo=timezone.utc),
        )
        self.assertEqual(expired.tier, "free")
        self.assertIn("Expired", expired.subscription_status)

    def test_transitions_only_on_change(self):
        self.assertEqual(
            subscription_transition(False, True), "subscription_started"
        )
        self.assertEqual(
            subscription_transition(True, False), "subscription_cancelled"
        )
        self.assertEqual(subscription_transition(True, True), "")
        self.assertEqual(subscription_transition(False, False), "")
        self.assertEqual(
            subscription_transition(True, True, False, True),
            "subscription_cancelled",
        )
        self.assertEqual(subscription_transition(True, True, True, True), "")
        self.assertEqual(subscription_transition(True, False, True, False), "")
        self.assertEqual(subscription_transition(True, True, True, False), "")
        self.assertEqual(
            subscription_transition(False, True, False, True),
            "subscription_started",
        )


class AnalyticsGuardrailTests(unittest.IsolatedAsyncioTestCase):
    async def test_verified_cancellation_lifecycle(self):
        now = datetime.now(timezone.utc)
        free = _free("authenticated-owner", now, verified=True)
        paid = replace(free, tier="starter", limit=25)
        cancelled = replace(paid, renewal_cancelled=True)
        outage = _free("authenticated-owner", now)
        profile = _Profile(
            identity_subject=free.subject,
            onboarding_completed=True,
            onboarding_answers={"creator_goal": "videos"},
            monthly_video_allowance=3,
            monthly_videos_used=2,
            monthly_videos_reserved=1,
            usage_period_start=free.start.date(),
            usage_period_end=free.end.date(),
        )
        session = AsyncMock()
        with (
            patch(
                "app.services.usage._lock_profile",
                AsyncMock(return_value=profile),
            ),
            patch("app.services.usage._save_profile", AsyncMock()) as save,
            patch(
                "app.services.analytics.User.current",
                AsyncMock(
                    return_value={
                        "sub": free.subject,
                        "email": "not-in-metadata",
                    }
                ),
            ),
        ):
            for access, expected in (
                (free, ""),
                (paid, "subscription_started"),
                (paid, ""),
                (outage, ""),
                (cancelled, "subscription_cancelled"),
                (cancelled, ""),
                (outage, ""),
                (free, ""),
                (free, ""),
                (paid, "subscription_started"),
                (cancelled, "subscription_cancelled"),
                (paid, ""),
                (cancelled, "subscription_cancelled"),
                (free, ""),
                (paid, "subscription_started"),
                (free, "subscription_cancelled"),
            ):
                session.execute.reset_mock()
                prior = dict(
                    profile.onboarding_answers.get("_verified_subscription", {})
                )
                snapshot = await sync_usage(session, access)
                if expected:
                    session.execute.assert_awaited_once()
                    self.assertEqual(
                        session.execute.call_args.args[1]["event"], expected
                    )
                else:
                    session.execute.assert_not_awaited()
                ledger = profile.onboarding_answers["_verified_subscription"]
                if access.verified:
                    self.assertEqual(ledger["active"], access.tier != "free")
                    self.assertEqual(
                        ledger["renewal_cancelled"], access.renewal_cancelled
                    )
                    self.assertEqual(
                        set(ledger),
                        {"active", "renewal_cancelled", "checked_at"},
                    )
                else:
                    self.assertEqual(ledger, prior)
                self.assertEqual(snapshot.access, access)
                self.assertEqual(snapshot.used, 2)
                self.assertEqual(snapshot.reserved, 1)
                self.assertEqual(profile.monthly_video_allowance, access.limit)
                self.assertEqual(
                    profile.onboarding_answers["creator_goal"], "videos"
                )
                save.assert_awaited_with(session, profile)
        session.commit.assert_not_awaited()
        session.rollback.assert_not_awaited()

    async def test_legacy_active_metadata_detects_cancellation_once(self):
        now = datetime.now(timezone.utc)
        paid = replace(
            _free("owner", now, verified=True), tier="starter", limit=25
        )
        profile = _Profile(
            "owner",
            True,
            {"_verified_subscription": {"active": True}},
            25,
            0,
            0,
            paid.start.date(),
            paid.end.date(),
        )
        session = AsyncMock()
        with (
            patch(
                "app.services.usage._lock_profile",
                AsyncMock(return_value=profile),
            ),
            patch("app.services.usage._save_profile", AsyncMock()),
            patch("app.services.usage.append_event", AsyncMock()) as append,
        ):
            await sync_usage(session, replace(paid, renewal_cancelled=True))
            await sync_usage(session, replace(paid, renewal_cancelled=True))
            await sync_usage(session, _free("owner", now, verified=True))
        append.assert_awaited_once_with(session, "subscription_cancelled")

    async def test_first_verified_cancelled_access_starts_subscription(self):
        now = datetime.now(timezone.utc)
        access = replace(
            _free("owner", now, verified=True),
            tier="starter",
            limit=25,
            renewal_cancelled=True,
        )
        profile = _Profile(
            "owner",
            True,
            {},
            3,
            0,
            0,
            access.start.date(),
            access.end.date(),
        )
        session = AsyncMock()
        with (
            patch(
                "app.services.usage._lock_profile",
                AsyncMock(return_value=profile),
            ),
            patch("app.services.usage._save_profile", AsyncMock()),
            patch("app.services.usage.append_event", AsyncMock()) as append,
        ):
            await sync_usage(session, access)
            await sync_usage(session, access)
            await sync_usage(session, _free("owner", now, verified=True))
        append.assert_awaited_once_with(session, "subscription_started")

    async def test_allowlist_and_owner(self):
        session = AsyncMock()
        with self.assertRaises(ValueError):
            await append_event(session, "fictional_event")
        session.execute.assert_not_called()
        with patch(
            "app.services.analytics.User.current",
            AsyncMock(
                return_value={
                    "sub": "authenticated-owner",
                    "email": "not-in-event",
                }
            ),
        ):
            await append_event(session, "paywall_viewed")
        parameters = session.execute.call_args.args[1]
        self.assertEqual(parameters["subject"], "authenticated-owner")
        self.assertEqual(set(parameters), {"id", "subject", "event", "project"})
        self.assertNotIn("not-in-event", str(parameters))

    async def test_append_sql_casts_every_repeated_parameter(self):
        session = AsyncMock()
        with patch(
            "app.services.analytics.User.current",
            AsyncMock(return_value={"sub": "authenticated-owner"}),
        ):
            for project_id in (None, "00000000-0000-0000-0000-000000000001"):
                with self.subTest(project_id=project_id):
                    session.execute.reset_mock()
                    await append_event(session, "signup", project_id)
                    session.execute.assert_awaited_once()
                    statement, parameters = session.execute.call_args.args
                    sql = " ".join(str(statement).split())
                    for name, column_type in (
                        ("subject", "VARCHAR(512)"),
                        ("project", "VARCHAR(36)"),
                        ("id", "UUID"),
                        ("event", "VARCHAR(32)"),
                    ):
                        cast = f"CAST(:{name} AS {column_type})"
                        self.assertEqual(
                            sql.count(cast),
                            3 if name in ("subject", "project") else 1,
                        )
                        self.assertNotIn(f":{name}", sql.replace(cast, ""))
                    self.assertIn(
                        "WHERE identity_subject = CAST(:subject AS VARCHAR(512))",
                        sql,
                    )
                    self.assertIn(
                        "CAST(:project AS VARCHAR(36)) IS NULL OR EXISTS",
                        sql,
                    )
                    self.assertIn(
                        "WHERE id = CAST(:project AS VARCHAR(36)) "
                        "AND owner_subject = CAST(:subject AS VARCHAR(512))",
                        sql,
                    )
                    self.assertEqual(parameters["project"], project_id)
                    self.assertEqual(
                        parameters["subject"], "authenticated-owner"
                    )
                    self.assertEqual(parameters["event"], "signup")
        session.commit.assert_not_awaited()
        session.rollback.assert_not_awaited()

    async def test_signed_out_cannot_append(self):
        session = AsyncMock()
        with (
            patch(
                "app.services.analytics.User.current",
                AsyncMock(return_value={}),
            ),
            self.assertRaises(ValueError),
        ):
            await append_event(session, "restore")
        session.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
