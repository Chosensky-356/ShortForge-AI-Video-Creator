import reflex as rx

import copy
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ten_generation import (
    ANGLES,
    WORKFLOW,
    build_brief,
    owned_render_brief,
    settings_for,
    validate_concepts,
    create_batch,
)
from app.services.short_generation import GenerationError, ShortBrief
from app.services.usage import (
    UsageError,
    _free,
    _Profile,
    _Project,
    reserve_project,
)


BATCH = "11111111-1111-4111-8111-111111111111"
PROJECT = "22222222-2222-4222-8222-222222222222"


def fixture() -> dict:
    outlines = (
        "Open with a question about starting a walk. Invite viewers to notice their surroundings, then close with a gentle invitation.",
        "Question the assumption that every outing needs elaborate equipment. Show ordinary shoes and a nearby route without claiming measured results.",
        "Explain a three step routine: choose a familiar path, set aside a few minutes, and head out at a comfortable pace.",
        "A hypothetical character leaves a desk, follows a quiet lane, and spots an interesting tree before returning to their fictional day.",
        "Frame the camera as a hypothetical viewer stepping through a doorway. Look left and right, then focus on small details along the pavement.",
        "Name three things to observe outdoors: changing light, leaf shapes, and the texture of walls. End by inviting another suggestion.",
        "Contrast two possible routes: a lively street and a quiet park. Describe different surroundings without declaring a winner or health benefits.",
        "Demonstrate planning a short route using simple landmarks. Show the start, a turning point, and a return path as a visual sequence.",
        "Explore overcomplicating a simple outing as a possible mistake. Replace a long checklist with one small decision and a manageable starting point.",
        "Invite a safe observation challenge: spot one color during a brief stroll. Offer an optional prompt to share the color, not a promised outcome.",
    )
    directions = (
        "A wide doorway view moves into a bright tree lined lane.",
        "Closeups of plain trainers beside the door and a modest path.",
        "Three separate still scenes show a path, a clock, and a walker.",
        "Illustrated fictional desk worker visits a distinctive old tree.",
        "First person views of a threshold and detailed patterned paving.",
        "A collage of pale sunlight, angular leaves, and brick textures.",
        "Side by side busy street and peaceful park still images.",
        "Simple unlabeled route landmarks arranged in a beginning to end sequence.",
        "An overflowing bag contrasts with someone simply putting on shoes.",
        "A single yellow flower becomes the focal point of a safe footpath.",
    )
    return {
        "concepts": [
            {
                "title": f"Walking through the {angle} lens",
                "angle": angle,
                "hook": f"Explore a different walking {angle} today?",
                "outline": outline,
                "visual_direction": direction,
                "cta": "Try noticing something new on your next outing.",
            }
            for angle, outline, direction in zip(ANGLES, outlines, directions)
        ]
    }


class ConceptValidationTests(unittest.TestCase):
    def test_exact_ten_and_canonical_order(self):
        payload = fixture()
        payload["concepts"].reverse()
        concepts = validate_concepts(json.dumps(payload))
        self.assertEqual(tuple(c.angle for c in concepts), ANGLES)
        self.assertEqual(len(concepts), 10)
        self.assertEqual(len({c.hook for c in concepts}), 10)

    def test_count_structure_fields_and_types(self):
        mutations = (
            lambda p: p["concepts"].pop(),
            lambda p: p["concepts"].append(copy.deepcopy(p["concepts"][0])),
            lambda p: p["concepts"][0].update(angle="review"),
            lambda p: p["concepts"][0].update(angle="myth"),
            lambda p: p["concepts"][0].pop("cta"),
            lambda p: p["concepts"][0].update(title=42),
            lambda p: p["concepts"][0].update(extra="forbidden"),
            lambda p: p.update(extra="forbidden"),
            lambda p: p["concepts"][0].update(outline="Too short."),
            lambda p: p["concepts"][0].update(visual_direction="No detail"),
        )
        for mutation in mutations:
            payload = fixture()
            mutation(payload)
            with (
                self.subTest(mutation=mutation),
                self.assertRaises(GenerationError),
            ):
                validate_concepts(payload)

    def test_all_text_limits_blank_and_controls(self):
        for field, limit in (
            ("title", 120),
            ("hook", 180),
            ("outline", 500),
            ("visual_direction", 350),
            ("cta", 160),
        ):
            for invalid in (" ", "x" * (limit + 1), "invalid\x00 text"):
                payload = fixture()
                payload["concepts"][0][field] = invalid
                with (
                    self.subTest(field=field),
                    self.assertRaises(GenerationError),
                ):
                    validate_concepts(payload)

    def test_normalized_duplicates_and_near_duplicate_outlines(self):
        for field in ("title", "hook", "outline", "visual_direction"):
            payload = fixture()
            payload["concepts"][1][field] = (
                f"  {payload['concepts'][0][field].upper()} !!!"
            )
            with self.subTest(field=field), self.assertRaises(GenerationError):
                validate_concepts(payload)
        payload = fixture()
        payload["concepts"][1]["outline"] = payload["concepts"][0][
            "outline"
        ].replace("gentle", "friendly")
        with self.assertRaises(GenerationError):
            validate_concepts(payload)

    def test_malformed_and_oversized_json(self):
        for payload in ("{bad", "", "é" * 12001):
            with self.assertRaises(GenerationError):
                validate_concepts(payload)


class BriefConstructionTests(unittest.TestCase):
    def setUp(self):
        self.original = ShortBrief(
            "A walk through the neighborhood", 45, "Illustrated", "nova", "Bold"
        )
        self.concept = validate_concepts(fixture())[3]
        self.settings = settings_for(self.original, self.concept, BATCH, 4)

    def test_stored_settings_not_client_choices(self):
        brief = build_brief(self.settings)
        self.assertEqual(
            (brief.duration, brief.style, brief.voice, brief.captions),
            (45, "Illustrated", "nova", "Bold"),
        )
        for value in (
            self.concept.angle,
            self.concept.hook,
            self.concept.outline,
            self.concept.visual_direction,
            self.concept.cta,
            self.original.idea,
        ):
            self.assertIn(value, brief.idea)
        self.assertIn("hypothetical", brief.idea)
        self.assertEqual(self.settings["batch_id"], BATCH)
        self.assertEqual(self.settings["batch_order"], 4)
        self.assertNotIn("_usage", self.settings)

    def test_full_length_original_preserved_and_render_brief_bounded(self):
        original = ShortBrief("x" * 2000, 60, "Cinematic", "onyx", "None")
        settings = settings_for(original, self.concept, BATCH, 4)
        brief = build_brief(settings)
        self.assertEqual(settings["original_idea"], original.idea)
        self.assertLessEqual(len(brief.idea), 2000)
        self.assertIn(self.concept.outline, brief.idea)
        self.assertIn(self.concept.visual_direction, brief.idea)

    def test_invalid_saved_settings_rejected(self):
        for key, value in (
            ("workflow", "normal_short_v1"),
            ("duration", True),
            ("duration", 61),
            ("voice", "unknown"),
            ("captions", "unknown"),
            ("style", "unknown"),
            ("original_idea", ""),
            ("concept", {}),
        ):
            settings = copy.deepcopy(self.settings)
            settings[key] = value
            with self.subTest(key=key), self.assertRaises(UsageError):
                build_brief(settings)


def session_context(session):
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=session)
    context.__aexit__ = AsyncMock(return_value=False)
    return context


class PersistenceOwnershipTests(unittest.IsolatedAsyncioTestCase):
    async def test_owned_and_matching_batch_required_before_render(self):
        session = MagicMock()
        result = MagicMock()
        result.first.return_value = None
        session.execute = AsyncMock(return_value=result)
        with (
            patch(
                "app.services.ten_generation.authenticated_subject",
                AsyncMock(return_value="owner"),
            ),
            patch(
                "app.services.ten_generation.rx.asession",
                return_value=session_context(session),
            ),
        ):
            with self.assertRaises(UsageError):
                await owned_render_brief(PROJECT, BATCH)
        statement, params = session.execute.call_args.args
        self.assertIn("owner_subject = :subject", str(statement))
        self.assertIn("project_type = 'short'", str(statement))
        self.assertIn(
            "generation_settings->>'batch_id' = :batch", str(statement)
        )
        self.assertEqual(params["subject"], "owner")
        self.assertEqual(params["batch"], BATCH)

    async def test_running_completed_and_charged_rejected(self):
        settings = settings_for(
            ShortBrief("Walking", 30, "Cinematic", "alloy", "Classic"),
            validate_concepts(fixture())[0],
            BATCH,
            1,
        )
        for status, charged in (
            ("queued", None),
            ("generating", None),
            ("rendering", None),
            ("completed", None),
            ("draft", datetime.now(timezone.utc)),
        ):
            session = MagicMock()
            result = MagicMock()
            result.first.return_value = (settings, status, charged)
            session.execute = AsyncMock(return_value=result)
            with (
                patch(
                    "app.services.ten_generation.authenticated_subject",
                    AsyncMock(return_value="owner"),
                ),
                patch(
                    "app.services.ten_generation.rx.asession",
                    return_value=session_context(session),
                ),
            ):
                with self.subTest(status=status), self.assertRaises(UsageError):
                    await owned_render_brief(PROJECT, BATCH)

    async def test_ten_drafts_single_atomic_parameterized_insert_no_quota(self):
        session = MagicMock()
        result = MagicMock()
        result.scalar.return_value = True
        session.execute = AsyncMock(return_value=result)
        transaction = session_context(session)
        session.begin.return_value = transaction
        concepts = validate_concepts(fixture())
        brief = ShortBrief("Walking", 30, "Cinematic", "alloy", "Classic")
        with (
            patch(
                "app.services.ten_generation.authenticated_subject",
                AsyncMock(return_value="owner"),
            ),
            patch(
                "app.services.ten_generation.rx.asession",
                return_value=session_context(session),
            ),
            patch(
                "app.services.ten_generation.generate_concepts",
                return_value=concepts,
            ),
        ):
            batch_id = await create_batch(brief)
        statement, params = session.execute.call_args.args
        self.assertIn("INSERT INTO video_projects", str(statement))
        self.assertEqual(len(params), 10)
        self.assertEqual({p["subject"] for p in params}, {"owner"})
        self.assertEqual(
            {p["settings"]["batch_id"] for p in params}, {batch_id}
        )
        self.assertEqual(
            {p["settings"]["batch_order"] for p in params}, set(range(1, 11))
        )
        self.assertEqual(len({p["id"] for p in params}), 10)
        self.assertTrue(all("_usage" not in p["settings"] for p in params))
        transaction.__aexit__.assert_awaited_once()


class BatchReservationTests(unittest.IsolatedAsyncioTestCase):
    async def test_conflict_checked_under_profile_lock_before_credit(self):
        access = _free("owner", datetime.now(timezone.utc))
        profile = _Profile(
            "owner", True, {}, 3, 0, 0, access.start.date(), access.end.date()
        )
        project = _Project(
            PROJECT,
            "draft",
            30,
            {"batch_id": BATCH, "workflow": WORKFLOW},
            None,
        )
        session = MagicMock()
        session.begin.return_value = session_context(session)
        conflict = MagicMock()
        conflict.scalar.return_value = True
        session.execute = AsyncMock(return_value=conflict)
        order = []

        async def lock_profile(*args):
            order.append("profile")
            return profile

        async def lock_project(*args):
            order.append("project")
            return project

        with (
            patch(
                "app.services.usage.verify_access",
                AsyncMock(return_value=access),
            ),
            patch(
                "app.services.usage.rx.asession",
                return_value=session_context(session),
            ),
            patch("app.services.usage._lock_profile", lock_profile),
            patch("app.services.usage._lock_project", lock_project),
            patch("app.services.usage._save_profile", AsyncMock()),
            patch("app.services.usage._sync_period"),
        ):
            with self.assertRaisesRegex(UsageError, "Another concept"):
                await reserve_project(PROJECT)
        self.assertEqual(order, ["profile", "project"])
        self.assertEqual(profile.monthly_videos_reserved, 0)
        statement, params = session.execute.call_args.args
        self.assertIn("other.id <> :project_id", str(statement))
        self.assertIn("other.project_type = 'short'", str(statement))
        self.assertIn("'queued', 'generating', 'rendering'", str(statement))
        self.assertEqual(params["batch_id"], BATCH)

    async def test_normal_active_short_keeps_idempotent_token_without_batch_check(
        self,
    ):
        access = _free("owner", datetime.now(timezone.utc))
        profile = _Profile(
            "owner", True, {}, 3, 0, 1, access.start.date(), access.end.date()
        )
        project = _Project(
            PROJECT,
            "generating",
            30,
            {
                "workflow": "normal_short_v1",
                "_usage": {"held": True, "token": "attempt"},
            },
            None,
        )
        session = MagicMock()
        session.begin.return_value = session_context(session)
        session.execute = AsyncMock()
        with (
            patch(
                "app.services.usage.verify_access",
                AsyncMock(return_value=access),
            ),
            patch(
                "app.services.usage.rx.asession",
                return_value=session_context(session),
            ),
            patch(
                "app.services.usage._lock_profile",
                AsyncMock(return_value=profile),
            ),
            patch(
                "app.services.usage._lock_project",
                AsyncMock(return_value=project),
            ),
            patch("app.services.usage._save_profile", AsyncMock()),
            patch("app.services.usage._sync_period"),
        ):
            self.assertEqual(await reserve_project(PROJECT), "attempt")
        session.execute.assert_not_awaited()
        self.assertEqual(profile.monthly_videos_reserved, 1)


if __name__ == "__main__":
    unittest.main()
