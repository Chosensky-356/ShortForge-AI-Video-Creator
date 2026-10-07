import reflex as rx

import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.models import CreatorProfile, VideoProject
from app.services.usage import (
    FREE_VIDEO_LIMIT,
    GROWTH_VIDEO_LIMIT,
    MAX_DURATION,
    MONTHLY_EXHAUSTED_MESSAGE,
    STARTER_VIDEO_LIMIT,
    YEARLY_VIDEO_LIMIT,
    UsageError,
    _add_months,
    _attempt,
    _duration,
    _free,
    _parse_access,
    _release,
    _sync_period,
    verify_access,
)


class UsagePolicyTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 2, 15, tzinfo=timezone.utc)
        self.products = {
            "monthly": ("starter", STARTER_VIDEO_LIMIT, 1),
            "quarterly": ("growth", GROWTH_VIDEO_LIMIT, 3),
            "annual": ("yearly", YEARLY_VIDEO_LIMIT, 12),
        }

    def payload(self, product="monthly", expiry="2026-03-01T00:00:00Z"):
        return {
            "subscriber": {
                "entitlements": {
                    "pro": {
                        "product_identifier": product,
                        "expires_date": expiry,
                        "purchase_date": "2026-02-01T00:00:00Z",
                    }
                }
            }
        }

    def test_limits_and_duration(self):
        self.assertEqual(
            (
                FREE_VIDEO_LIMIT,
                STARTER_VIDEO_LIMIT,
                GROWTH_VIDEO_LIMIT,
                YEARLY_VIDEO_LIMIT,
                MAX_DURATION,
            ),
            (3, 25, 80, 360, 60),
        )
        for duration in (1, 30, 60):
            _duration(duration)
        for duration in (0, 61, -1, True, 30.5):
            with self.assertRaises(UsageError):
                _duration(duration)
        self.assertEqual(
            _free("owner", self.now).exhausted_message,
            MONTHLY_EXHAUSTED_MESSAGE,
        )

    def test_only_active_configured_products(self):
        access = _parse_access("owner", self.payload(), self.products, self.now)
        self.assertEqual(
            (access.tier, access.limit, access.months), ("starter", 25, 1)
        )
        self.assertTrue(access.verified)
        for product in ("unknown", "", None):
            access = _parse_access(
                "owner", self.payload(product), self.products, self.now
            )
            self.assertEqual(access.limit, 3)
            self.assertFalse(access.verified)
            self.assertTrue(access.warning)
        expired = _parse_access(
            "owner",
            self.payload(expiry="2026-02-01T00:00:00Z"),
            self.products,
            self.now,
        )
        self.assertEqual(expired.tier, "free")
        lifetime = _parse_access(
            "owner", self.payload(expiry=None), self.products, self.now
        )
        self.assertEqual(lifetime.limit, 3)
        self.assertFalse(lifetime.verified)

    def test_verified_anchored_terms(self):
        growth = _parse_access(
            "owner",
            self.payload("quarterly", "2026-05-01T00:00:00Z"),
            self.products,
            self.now,
        )
        yearly = _parse_access(
            "owner",
            self.payload("annual", "2027-02-01T00:00:00Z"),
            self.products,
            self.now,
        )
        self.assertEqual(growth.months, 3)
        self.assertEqual(yearly.months, 12)
        self.assertIn("three-month", growth.exhausted_message)
        self.assertIn("yearly", yearly.exhausted_message)
        self.assertEqual(
            _add_months(datetime(2024, 1, 31, tzinfo=timezone.utc), 1).day, 29
        )

    def test_rollover_preserves_reservations(self):
        now = datetime.now(timezone.utc)
        access = _free("owner", now)
        profile = CreatorProfile(
            identity_subject="owner",
            onboarding_answers={},
            monthly_videos_used=3,
            monthly_videos_reserved=2,
            usage_period_start=datetime(2020, 1, 1).date(),
            usage_period_end=datetime(2020, 2, 1).date(),
        )
        _sync_period(profile, access)
        self.assertEqual(profile.monthly_videos_used, 0)
        self.assertEqual(profile.monthly_videos_reserved, 2)
        profile.monthly_videos_used = 1
        _sync_period(profile, access)
        self.assertEqual(profile.monthly_videos_used, 1)
        self.assertEqual(profile.monthly_video_allowance, 3)

    def test_release_once_and_stale_attempt(self):
        profile = CreatorProfile(monthly_videos_reserved=1)
        project = VideoProject(
            generation_settings={"_usage": {"held": True, "token": "attempt"}}
        )
        usage = _attempt(project, "attempt")
        _release(profile, project, usage)
        _release(profile, project, _attempt(project, "attempt"))
        self.assertEqual(profile.monthly_videos_reserved, 0)
        with self.assertRaises(UsageError):
            _attempt(project, "old-attempt")


class VerificationFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_configuration_is_free(self):
        with (
            patch.dict("os.environ", {}, clear=True),
            patch(
                "app.services.usage.authenticated_subject",
                AsyncMock(return_value="owner"),
            ),
        ):
            access = await verify_access()
        self.assertEqual(access.limit, 3)
        self.assertFalse(access.verified)
        self.assertTrue(access.warning)

    async def test_network_failure_is_free(self):
        with (
            patch.dict(
                "os.environ",
                {
                    "REVENUECAT_SECRET_API_KEY": "test-only",
                    "REVENUECAT_STARTER_PRODUCT_ID": "monthly",
                },
                clear=True,
            ),
            patch(
                "app.services.usage.authenticated_subject",
                AsyncMock(return_value="owner"),
            ),
            patch(
                "app.services.usage._fetch_subscriber", side_effect=TimeoutError
            ),
            patch("app.services.usage.logging.exception"),
        ):
            access = await verify_access()
        self.assertEqual(access.tier, "free")
        self.assertFalse(access.verified)
        self.assertTrue(access.warning)


if __name__ == "__main__":
    unittest.main()
