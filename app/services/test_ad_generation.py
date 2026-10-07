import reflex as rx

import copy
import json
import shutil
import struct
import unittest
import zlib
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from openai import AuthenticationError, APITimeoutError

from app.services.ad_generation import (
    AdError,
    MAX_BYTES,
    validate_brief,
    validate_response,
    image_magic,
    normalize_photo,
    read_photo,
    generate_ad,
)


def brief_fixture(kind: str = "product_ad") -> dict[str, str]:
    return {
        "product_name": "Desk stand",
        "description": "A folding desk stand",
        "audience": "Desk workers",
        "problem": "Cluttered workspace",
        "benefit": "Folds for storage",
        "tone": "Practical and friendly",
        "cta": "Explore the stand.",
        "claims": "Visible folding hinge only; no performance promises",
        "offer": "",
        "url": "",
        "duration": "15",
        "style": "Casual" if kind == "ugc_ad" else "Studio",
        "platform": "TikTok",
        "persona": "Practical presenter",
        "situation": "Desk in daylight",
        "demonstration": "Show the folding hinge",
        "objection": "Does it fold for storage?",
    }


def response_fixture(kind: str = "product_ad") -> dict:
    purposes = (
        ["hook", "demo", "cta"]
        if kind == "ugc_ad"
        else ["hook", "benefit", "proof", "cta"]
    )
    segments = (
        ["Need desk space?", "See this folding stand.", "Explore the stand."]
        if kind == "ugc_ad"
        else [
            "Need desk space?",
            "See this folding stand.",
            "Show the hinge in action.",
            "Explore the stand.",
        ]
    )
    return {
        "title": "A simpler desk setup",
        "hook": segments[0],
        "script": " ".join(segments),
        "voiceover_text": " ".join(segments),
        "cta": segments[-1],
        "image_observations": "A stand with a hinge is visible.",
        "claim_notes": "No results or customer claims included.",
        "scenes": [
            {
                "purpose": purpose,
                "visual": "Show a close-up of the stand.",
                "narration": segments[index],
                "start": float(index * 15 / len(purposes)),
                "end": float((index + 1) * 15 / len(purposes)),
            }
            for index, purpose in enumerate(purposes)
        ],
        "captions": [],
    }


def png_fixture(width: int = 32, height: int = 32) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    raw = b"".join(b"\0" + b"\x84\x5c\xd6" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


class BriefTests(unittest.TestCase):
    def test_distinct_workflows(self):
        for kind in ("product_ad", "ugc_ad"):
            self.assertEqual(
                validate_brief(brief_fixture(kind), kind)["duration"], "15"
            )
            self.assertTrue(
                validate_response(
                    json.dumps(response_fixture(kind)),
                    brief_fixture(kind),
                    kind,
                ).scenes
            )

    def test_invalid_server_inputs(self):
        for key, value in (
            ("duration", True),
            ("duration", "015"),
            ("style", "Casual"),
            ("platform", "Other"),
            ("product_name", ""),
            ("tone", "x\x00"),
            ("description", "x" * 1201),
            ("url", "javascript:alert(1)"),
            ("url", "https://user:secret@example.com"),
            ("url", "https://127.0.0.1"),
            ("url", "https://example.local"),
        ):
            brief = brief_fixture()
            brief[key] = value
            with (
                self.subTest(key=key, value=str(value)[:40]),
                self.assertRaises(AdError),
            ):
                validate_brief(brief, "product_ad")
        brief = brief_fixture("ugc_ad")
        brief["persona"] = ""
        with self.assertRaises(AdError):
            validate_brief(brief, "ugc_ad")


class ResponseTests(unittest.TestCase):
    def test_invalid_responses(self):
        mutations = [
            lambda p: p.update(title="x" * 201),
            lambda p: p.update(script="I love this product."),
            lambda p: p.update(voiceover_text="Different words"),
            lambda p: p["scenes"][0].update(start=1.0),
            lambda p: p["scenes"][0].update(end=float("nan")),
            lambda p: p["scenes"][1].update(purpose="demo"),
            lambda p: p["scenes"][1].update(
                visual="Show fake five-star reviews."
            ),
            lambda p: p.update(
                captions=[{"text": "Wrong words", "start": 0.0, "end": 15.0}]
            ),
            lambda p: p.update(extra="unexpected"),
        ]
        for mutation in mutations:
            payload = copy.deepcopy(response_fixture())
            mutation(payload)
            with self.assertRaises(AdError):
                validate_response(
                    json.dumps(payload), brief_fixture(), "product_ad"
                )
        for raw in ("{bad", "x" * 24001):
            with self.assertRaises(AdError):
                validate_response(raw, brief_fixture(), "product_ad")

    def test_vision_request_is_local_data_not_url_fetch(self):
        result = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(
                        content=json.dumps(response_fixture()), refusal=None
                    ),
                )
            ]
        )
        with (
            patch(
                "app.services.ad_generation.read_photo",
                return_value=png_fixture(),
            ),
            patch("app.services.ad_generation.OpenAI") as provider,
        ):
            client = provider.return_value.__enter__.return_value
            client.chat.completions.create.return_value = result
            generate_ad(brief_fixture(), "product_ad", "server-owned-photo")
            request = client.chat.completions.create.call_args.kwargs
            self.assertEqual(request["model"], "gpt-4o-mini")
            self.assertTrue(
                request["messages"][1]["content"][1]["image_url"][
                    "url"
                ].startswith("data:image/png;base64,")
            )
            self.assertEqual(request["response_format"]["type"], "json_schema")


class GenerationTests(unittest.TestCase):
    def _result(
        self,
        payload: dict | str,
        refusal: str | None = None,
        finish: str = "stop",
    ):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason=finish,
                    message=SimpleNamespace(
                        content=json.dumps(payload)
                        if isinstance(payload, dict)
                        else payload,
                        refusal=refusal,
                    ),
                )
            ]
        )

    def _generate(
        self, results: list, kind: str = "product_ad", duration: str = "15"
    ):
        brief = brief_fixture(kind)
        brief["duration"] = duration
        with (
            patch(
                "app.services.ad_generation.read_photo",
                return_value=png_fixture(),
            ),
            patch("app.services.ad_generation.OpenAI") as provider,
        ):
            client = provider.return_value.__enter__.return_value
            calls = []

            def respond(**request):
                calls.append(copy.deepcopy(request))
                result = results[len(calls) - 1]
                if isinstance(result, BaseException):
                    raise result
                return result

            client.chat.completions.create.side_effect = respond
            try:
                story = generate_ad(brief, kind, "server-owned-photo")
            finally:
                self.calls = calls
                provider.assert_called_once_with(timeout=55, max_retries=0)
            return story

    def test_scene_narration_is_canonical_without_new_copy(self):
        payload = response_fixture()
        payload.update(
            script="A different proposed script.",
            voiceover_text="An unrelated voiceover.",
            hook="A different hook.",
            cta="A different CTA.",
            captions=[
                {
                    "text": "Folds away for a clearer desk.",
                    "start": 0.0,
                    "end": 15.0,
                }
            ],
        )
        original = copy.deepcopy(payload)
        with self.assertRaises(AdError):
            validate_response(
                json.dumps(payload), brief_fixture(), "product_ad"
            )
        story = self._generate([self._result(payload)])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(
            story.script,
            "Need desk space? See this folding stand. Show the hinge in action. Explore the stand.",
        )
        self.assertEqual(story.hook, "Need desk space?")
        self.assertEqual(story.cta, "Explore the stand.")
        self.assertEqual(story.voiceover_text, story.script)
        self.assertEqual(story.captions, [])
        self.assertEqual(
            [s.model_dump() for s in story.scenes], original["scenes"]
        )
        self.assertEqual(story.claim_notes, original["claim_notes"])
        self.assertEqual(
            story.image_observations, original["image_observations"]
        )
        self.assertEqual(payload, original)

    def test_matching_captions_are_preserved_and_validated(self):
        payload = response_fixture()
        payload["captions"] = [
            {"text": s["narration"], "start": s["start"], "end": s["end"]}
            for s in payload["scenes"]
        ]
        story = self._generate([self._result(payload)])
        self.assertEqual(
            [c.model_dump() for c in story.captions], payload["captions"]
        )
        payload["captions"][0]["start"] = 1.0
        story = self._generate(
            [self._result(payload), self._result(response_fixture())]
        )
        self.assertEqual(len(self.calls), 2)
        self.assertIn(
            "invalid estimated timing", self.calls[1]["messages"][-1]["content"]
        )

    def test_observed_five_scene_42_word_shape_gets_one_rewrite(self):
        payload = response_fixture()
        narrations = [
            "Need more room on your busy desk today?",
            "This folding stand keeps your setup simple and tidy.",
            "See the visible hinge fold in this close-up demonstration.",
            "Place the stand on your desk then fold it.",
            "Explore the stand for your workspace now.",
        ]
        self.assertEqual(len(" ".join(narrations).split()), 42)
        payload["scenes"] = [
            {
                "purpose": purpose,
                "visual": "Show the stand and folding hinge.",
                "narration": narration,
                "start": float(index * 3),
                "end": float((index + 1) * 3),
            }
            for index, (purpose, narration) in enumerate(
                zip(["hook", "benefit", "proof", "demo", "cta"], narrations)
            )
        ]
        payload["script"] = " ".join(narrations)
        payload["captions"] = [
            {"text": "A simpler desk setup.", "start": 0.0, "end": 15.0}
        ]
        corrected = response_fixture()
        story = self._generate([self._result(payload), self._result(corrected)])
        self.assertEqual(story.script, corrected["script"])
        self.assertEqual(
            [s.purpose for s in story.scenes],
            ["hook", "benefit", "proof", "cta"],
        )
        self.assertLessEqual(len(story.script.split()), 31)
        self.assertEqual(len(self.calls), 2)
        rewrite = self.calls[1]["messages"][-1]["content"]
        self.assertIn("5–31", rewrite)
        self.assertIn("hook / benefit / proof / cta", rewrite)
        self.assertIn("did not fit the requested duration", rewrite)
        self.assertEqual(
            json.loads(self.calls[1]["messages"][-2]["content"]), payload
        )
        for call in self.calls:
            self.assertEqual(call["max_completion_tokens"], 4200)
            self.assertTrue(call["response_format"]["json_schema"]["strict"])
            self.assertTrue(
                call["messages"][1]["content"][1]["image_url"][
                    "url"
                ].startswith("data:image/png;base64,")
            )

    def test_validation_failures_request_exact_issue_then_revalidate(self):
        cases = [
            (
                lambda p: p["scenes"][1].update(purpose="demo"),
                "wrong storyboard structure",
            ),
            (
                lambda p: p["scenes"][0].update(
                    narration="Need space? This stand is clinically proven."
                ),
                "unsupported high-risk claim",
            ),
            (
                lambda p: p["scenes"][0].update(start=1.0),
                "invalid estimated timing",
            ),
            (
                lambda p: p["scenes"][0].update(end=float("nan")),
                "invalid estimated timing",
            ),
            (lambda p: p["scenes"][-1].update(end=14.0), "does not cover"),
            (
                lambda p: p["scenes"][1].update(
                    visual="Show fake five-star reviews."
                ),
                "fabricated endorsements",
            ),
            (lambda p: p.update(title="x" * 201), "title:"),
            (lambda p: p.update(extra="unexpected"), "extra_forbidden"),
            (lambda p: p["scenes"][0].update(narration=42), "string_type"),
            (lambda p: p.update(scenes=[]), "wrong storyboard structure"),
        ]
        for mutation, issue in cases:
            with self.subTest(issue=issue):
                payload = response_fixture()
                mutation(payload)
                story = self._generate(
                    [self._result(payload), self._result(response_fixture())]
                )
                self.assertEqual(story.script, response_fixture()["script"])
                self.assertEqual(len(self.calls), 2)
                self.assertIn(issue, self.calls[1]["messages"][-1]["content"])

    def test_rewrite_budget_for_each_duration_and_workflow(self):
        for kind in ("product_ad", "ugc_ad"):
            for duration in (15, 30, 45, 60):
                with self.subTest(kind=kind, duration=duration):
                    payload = response_fixture(kind)
                    for scene in payload["scenes"]:
                        scene["start"] *= duration / 15
                        scene["end"] *= duration / 15
                    invalid = copy.deepcopy(payload)
                    invalid["scenes"][0]["start"] = 1.0
                    self._generate(
                        [self._result(invalid), self._result(payload)],
                        kind,
                        str(duration),
                    )
                    rewrite = self.calls[1]["messages"][-1]["content"]
                    self.assertIn(f"5–{int(duration * 2.1)}", rewrite)
                    self.assertIn(
                        "hook / demo / cta"
                        if kind == "ugc_ad"
                        else "hook / benefit / proof / cta",
                        rewrite,
                    )

    def test_still_invalid_rewrite_never_returns_a_result(self):
        for second in (
            "{bad",
            json.dumps({**response_fixture(), "extra": True}),
            "x" * 24001,
        ):
            with self.subTest(second=second[:30]):
                invalid = response_fixture()
                invalid["scenes"][1]["purpose"] = "demo"
                with self.assertRaises(AdError):
                    self._generate(
                        [self._result(invalid), self._result(second)]
                    )
                self.assertEqual(len(self.calls), 2)
        invalid = response_fixture()
        invalid["scenes"][0]["start"] = 1.0
        with self.assertRaisesRegex(
            AdError, "No draft result was accepted and no video credit was used"
        ):
            self._generate([self._result(invalid), self._result(invalid)])
        self.assertEqual(len(self.calls), 2)

    def test_refusal_and_incomplete_responses_are_not_blindly_retried(self):
        for result in (
            self._result("", refusal="Unsafe brief"),
            self._result("", finish="content_filter"),
            self._result("{", finish="length"),
            SimpleNamespace(choices=[]),
            self._result("x" * 24001),
        ):
            with self.subTest(result=result), self.assertRaises(AdError):
                self._generate([result])
            self.assertEqual(len(self.calls), 1)
        invalid = response_fixture()
        invalid["scenes"][0]["start"] = 1.0
        with self.assertRaisesRegex(
            AdError, "declined this brief for safety reasons"
        ):
            self._generate(
                [
                    self._result(invalid),
                    self._result("", refusal="Unsafe brief"),
                ]
            )
        self.assertEqual(len(self.calls), 2)

    def test_provider_auth_and_timeout_propagate_on_either_attempt(self):
        request = httpx.Request("POST", "https://example.com")
        errors = [
            APITimeoutError(request=request),
            AuthenticationError(
                "Unavailable",
                response=httpx.Response(401, request=request),
                body=None,
            ),
        ]
        invalid = response_fixture()
        invalid["scenes"][0]["start"] = 1.0
        for error in errors:
            for prefix in ([], [self._result(invalid)]):
                with (
                    self.subTest(
                        error=type(error).__name__, attempt=len(prefix)
                    ),
                    self.assertRaises(type(error)) as caught,
                ):
                    self._generate([*prefix, error])
                self.assertIs(caught.exception, error)
                self.assertEqual(len(self.calls), len(prefix) + 1)


class UploadTests(unittest.TestCase):
    def test_bad_magic_size_and_paths(self):
        for data in (
            b"",
            b"<svg onload='alert(1)'/>",
            b"GIF89a",
            b"x" * (MAX_BYTES + 1),
        ):
            with self.assertRaises(AdError):
                image_magic(data)
        for path in (
            "../../etc/passwd",
            "/etc/passwd",
            "https://example.com/a.png",
            "ad-photo-evil.png",
        ):
            with self.assertRaises(AdError):
                read_photo(path)

    @unittest.skipUnless(
        shutil.which("ffmpeg") and shutil.which("ffprobe"),
        "Media decoders required",
    )
    def test_real_decode_and_dimensions(self):
        clean, width, height = normalize_photo(png_fixture())
        self.assertEqual((width, height), (32, 32))
        self.assertEqual(image_magic(clean), "png")
        for data in (
            png_fixture()[:30],
            png_fixture(16, 32),
            png_fixture() + b"acTL",
        ):
            with self.assertRaises(AdError):
                normalize_photo(data)


if __name__ == "__main__":
    unittest.main()
