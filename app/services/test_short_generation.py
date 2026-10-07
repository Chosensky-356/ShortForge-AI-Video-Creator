import reflex as rx

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError

from app.services.short_generation import (
    GenerationError,
    ShortBrief,
    _story,
    generate_short,
    validate_script,
)
from app.services.short_render import (
    RenderError,
    compose_music,
    render_video,
    speech_timing,
    validate_output,
    write_captions,
)


def story_fixture() -> dict:
    return {
        "title": "A little walk, a fresh perspective",
        "hook": "Need a reset?",
        "narration": "Need a reset? Take a walk outside and notice the world. Try it today.",
        "cta": "Try it today.",
        "scenes": [
            {
                "visual_prompt": "A person stepping into a sunlit garden, warm cinematic lighting, no text",
                "start": 0.0,
                "end": 7.0,
            },
            {
                "visual_prompt": "Close-up of leaves moving in a gentle breeze, bright morning light, no text",
                "start": 7.0,
                "end": 15.0,
            },
        ],
        "captions": [
            {"text": "Need a reset?", "start": 0.0, "end": 3.0},
            {
                "text": "Take a walk outside and notice the world.",
                "start": 3.0,
                "end": 12.0,
            },
            {"text": "Try it today.", "start": 12.0, "end": 15.0},
        ],
        "music": {
            "mood": "Warm and hopeful",
            "tempo": 90,
            "chords": [[48, 52, 55], [53, 57, 60]],
            "melody": [60, 64, 67, 65],
        },
    }


class ScriptValidationTests(unittest.TestCase):
    def test_valid_structured_story(self):
        result = validate_script(json.dumps(story_fixture()), 15)
        self.assertEqual(len(result.scenes), 2)
        self.assertEqual(result.captions[-1].end, 15)

    def test_input_limits_and_enum_validation(self):
        ShortBrief.validate_inputs(
            "A daily walking habit", "30", "Cinematic", "alloy", "Classic"
        )
        for idea, duration, style, voice, captions in (
            (" ", "30", "Cinematic", "alloy", "Classic"),
            ("x" * 2001, "30", "Cinematic", "alloy", "Classic"),
            ("x\x00", "30", "Cinematic", "alloy", "Classic"),
            ("x", "61", "Cinematic", "alloy", "Classic"),
            ("x", "30", "unknown", "alloy", "Classic"),
            ("x", "30", "Cinematic", "unknown", "Classic"),
            ("x", "30", "Cinematic", "alloy", "unknown"),
        ):
            with self.subTest(
                idea=idea[:10],
                duration=duration,
                style=style,
                voice=voice,
                captions=captions,
            ):
                with self.assertRaises(ValueError):
                    ShortBrief.validate_inputs(
                        idea, duration, style, voice, captions
                    )

    def test_exact_duration_types_and_options(self):
        for duration in (15, "15", 30, "30", 45, "45", 60, "60"):
            with self.subTest(duration=duration):
                ShortBrief.validate_inputs(
                    "A daily walking habit",
                    duration,
                    "Cinematic",
                    "alloy",
                    "Classic",
                )
        for duration in (
            True,
            False,
            15.0,
            30.0,
            45.0,
            60.0,
            None,
            0,
            16,
            "015",
            "15.0",
            " 15",
            "15 ",
            "",
            [],
            {},
        ):
            with self.subTest(duration=duration):
                with self.assertRaises(ValueError):
                    ShortBrief.validate_inputs(
                        "A daily walking habit",
                        duration,
                        "Cinematic",
                        "alloy",
                        "Classic",
                    )

    def test_scene_caption_and_score_bounds(self):
        mutations = [
            lambda p: p["scenes"].extend(copy.deepcopy(p["scenes"]) * 2),
            lambda p: p["scenes"][0].update(end=float("nan")),
            lambda p: p["scenes"][1].update(start=8),
            lambda p: p["captions"][-1].update(end=16),
            lambda p: p["captions"][1].update(
                text="This does not match the spoken words."
            ),
            lambda p: p.update(hook="An unrelated opening"),
            lambda p: p.update(narration="word " * 100),
            lambda p: p["music"].update(tempo=500),
            lambda p: p["music"].update(chords=[[1, 2], [53, 57]]),
            lambda p: p["music"].update(melody=[60] * 33),
            lambda p: p.update(extra_field="not supported"),
        ]
        for mutation in mutations:
            payload = story_fixture()
            mutation(payload)
            with self.assertRaises((GenerationError, ValidationError)):
                validate_script(payload, 15)
        with self.assertRaises(GenerationError):
            validate_script("x" * 32001, 15)


class StoryResponseTests(unittest.TestCase):
    def _generate(self, raw: str):
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content=raw, refusal=None),
                )
            ]
        )
        with patch("app.services.short_generation.OpenAI") as provider:
            client = provider.return_value.__enter__.return_value
            client.chat.completions.create.return_value = response
            return _story(
                ShortBrief(
                    "Why walking clears your head",
                    15,
                    "Cinematic",
                    "alloy",
                    "Classic",
                )
            )

    def test_generated_captions_are_source_of_spoken_text(self):
        payload = story_fixture()
        payload.update(
            narration="Different generated narration.",
            hook="Different generated hook.",
            cta="Different generated closing line.",
        )
        result = self._generate(json.dumps(payload))
        self.assertEqual(
            result.narration,
            " ".join(caption["text"] for caption in payload["captions"]),
        )
        self.assertEqual(result.hook, payload["captions"][0]["text"])
        self.assertEqual(result.cta, payload["captions"][-1]["text"])
        self.assertEqual(
            [caption.model_dump() for caption in result.captions],
            payload["captions"],
        )
        self.assertEqual(
            [scene.model_dump() for scene in result.scenes], payload["scenes"]
        )

    def test_normalization_does_not_bypass_strict_validation(self):
        mutations = [
            lambda p: p.update(captions=[]),
            lambda p: p["captions"][0].update(text=123),
            lambda p: p["captions"][0].update(text=" "),
            lambda p: p["captions"][0].pop("start"),
            lambda p: p["captions"][1].update(start=4),
            lambda p: p["captions"][-1].update(end=16),
            lambda p: p["captions"][1].update(text="word " * 13),
            lambda p: p["captions"][0].update(text="Need\x00 a reset?"),
            lambda p: p["music"].update(tempo=500),
            lambda p: p.update(extra_field="not supported"),
        ]
        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=index):
                payload = story_fixture()
                mutation(payload)
                with self.assertRaises((GenerationError, ValidationError)):
                    self._generate(json.dumps(payload))

    def test_response_is_byte_bounded_before_parsing(self):
        with patch("app.services.short_generation.json.loads") as parse:
            with self.assertRaisesRegex(GenerationError, "too large"):
                self._generate("é" * 16001)
            parse.assert_not_called()

    def test_malformed_json_is_rejected(self):
        with self.assertRaises(GenerationError):
            self._generate("{not valid JSON}")


class PipelineLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.brief = ShortBrief(
            "Why walking clears your head", 15, "Cinematic", "alloy", "Classic"
        )
        self.spec = validate_script(story_fixture(), 15)
        self.patches = []
        self.mocks = {}
        replacements = {
            "reserve_project": AsyncMock(return_value="attempt"),
            "mark_stage": AsyncMock(return_value=True),
            "_progress": AsyncMock(),
            "_persist_story": AsyncMock(),
            "_asset": AsyncMock(return_value="asset"),
            "complete_render": AsyncMock(),
            "_release_failure": AsyncMock(return_value=True),
            "_story": lambda brief: copy.deepcopy(self.spec),
            "_image": lambda prompt, style, path: path.write_bytes(b"image"),
            "_speech": lambda text, voice, path: path.write_bytes(b"voice"),
            "speech_timing": lambda path, target: (14.0, 14.0, 1.0),
            "compose_music": lambda score, duration, path: path.write_bytes(
                b"music"
            ),
            "render_video": lambda *args: 14.0,
        }
        for name, replacement in replacements.items():
            patcher = patch(
                f"app.services.short_generation.{name}", replacement
            )
            patcher.start()
            self.patches.append(patcher)
            self.mocks[name] = replacement
        patcher = patch(
            "app.services.short_generation.rx.get_upload_dir",
            return_value=self.root,
        )
        patcher.start()
        self.patches.append(patcher)
        self.addCleanup(self.temporary.cleanup)
        for patcher in self.patches:
            self.addCleanup(patcher.stop)

    async def test_charge_only_after_video_asset_commit(self):
        order = []

        async def save_asset(*args, **kwargs):
            order.append(args[3])
            return "ready-video" if args[3] == "video" else "other-asset"

        async def finish(project_id, token, asset_id):
            self.assertEqual(order[-1], "video")
            self.assertEqual(asset_id, "ready-video")
            order.append("charged")

        self.mocks["_asset"].side_effect = save_asset
        self.mocks["complete_render"].side_effect = finish
        result = await generate_short("project", self.brief, AsyncMock())
        self.assertEqual(result.duration, 14)
        self.assertEqual(
            order, ["image", "image", "voiceover", "music", "video", "charged"]
        )
        self.assertEqual(self.mocks["reserve_project"].await_count, 5)
        self.mocks["_release_failure"].assert_not_awaited()

    async def test_provider_failure_releases_without_charge(self):
        with patch(
            "app.services.short_generation._story", side_effect=TimeoutError
        ):
            with self.assertRaises(TimeoutError):
                await generate_short("project", self.brief, AsyncMock())
        self.mocks["_release_failure"].assert_awaited_once()
        self.mocks["complete_render"].assert_not_awaited()

    async def test_image_failure_releases_without_charge(self):
        with patch(
            "app.services.short_generation._image",
            side_effect=GenerationError("Scene unavailable"),
        ):
            with self.assertRaises(GenerationError):
                await generate_short("project", self.brief, AsyncMock())
        self.mocks["_release_failure"].assert_awaited_once()
        self.mocks["complete_render"].assert_not_awaited()

    async def test_render_validation_failure_releases_without_charge(self):
        with patch(
            "app.services.short_generation.render_video",
            side_effect=RenderError("Invalid MP4"),
        ):
            with self.assertRaises(RenderError):
                await generate_short("project", self.brief, AsyncMock())
        self.mocks["_release_failure"].assert_awaited_once()
        self.mocks["complete_render"].assert_not_awaited()
        self.assertFalse(
            any(
                call.args[3] == "video"
                for call in self.mocks["_asset"].await_args_list
            )
        )

    async def test_database_asset_failure_releases_without_charge(self):
        self.mocks["_asset"].side_effect = RuntimeError("transaction failed")
        with self.assertRaises(RuntimeError):
            await generate_short("project", self.brief, AsyncMock())
        self.mocks["_release_failure"].assert_awaited_once()
        self.mocks["complete_render"].assert_not_awaited()

    async def test_completion_failure_releases_reservation(self):
        self.mocks["complete_render"].side_effect = RuntimeError(
            "commit failed"
        )
        with self.assertRaises(RuntimeError):
            await generate_short("project", self.brief, AsyncMock())
        self.mocks["_release_failure"].assert_awaited_once()

    async def test_duplicate_worker_does_not_release_other_worker(self):
        self.mocks["mark_stage"].return_value = False
        with self.assertRaises(GenerationError):
            await generate_short("project", self.brief, AsyncMock())
        self.mocks["_release_failure"].assert_not_awaited()
        self.mocks["complete_render"].assert_not_awaited()

    async def test_stage_database_failure_releases_reservation(self):
        self.mocks["mark_stage"].side_effect = RuntimeError(
            "stage update failed"
        )
        with self.assertRaises(RuntimeError):
            await generate_short("project", self.brief, AsyncMock())
        self.mocks["_release_failure"].assert_awaited_once()

    async def test_quota_rejection_makes_no_provider_call(self):
        from app.services.usage import UsageError

        self.mocks["reserve_project"].side_effect = UsageError("Limit reached")
        with patch("app.services.short_generation._story") as story:
            with self.assertRaises(UsageError):
                await generate_short("project", self.brief, AsyncMock())
            story.assert_not_called()
        self.mocks["complete_render"].assert_not_awaited()


class RenderingTests(unittest.TestCase):
    def test_safe_pacing_and_no_truncation(self):
        with patch(
            "app.services.short_render.probe",
            return_value={
                "streams": [{"codec_type": "audio"}],
                "format": {"duration": "16"},
            },
        ):
            source, duration, pace = speech_timing(Path("voice.mp3"), 15)
            self.assertEqual(source, 16)
            self.assertAlmostEqual(duration, 14.5)
            self.assertTrue(1 < pace <= 1.2)
        with patch(
            "app.services.short_render.probe",
            return_value={
                "streams": [{"codec_type": "audio"}],
                "format": {"duration": "19"},
            },
        ):
            with self.assertRaisesRegex(RenderError, "too long"):
                speech_timing(Path("voice.mp3"), 15)

    def test_rejects_wrong_codec_dimensions_and_duration(self):
        good = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 540,
                    "height": 960,
                    "pix_fmt": "yuv420p",
                },
                {"codec_type": "audio", "codec_name": "aac", "duration": "14"},
            ],
            "format": {"duration": "14"},
        }
        for key, value in (("width", 360), ("codec_name", "mpeg4")):
            bad = copy.deepcopy(good)
            bad["streams"][0][key] = value
            with patch("app.services.short_render.probe", return_value=bad):
                with self.assertRaises(RenderError):
                    validate_output(Path("short.mp4"), 15, 14)
        bad = copy.deepcopy(good)
        bad["format"]["duration"] = "15.1"
        with patch("app.services.short_render.probe", return_value=bad):
            with self.assertRaises(RenderError):
                validate_output(Path("short.mp4"), 15, 15)

    def test_music_and_caption_sanitisation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            compose_music(story_fixture()["music"], 2, root / "music.wav")
            with wave.open(str(root / "music.wav")) as audio:
                self.assertEqual(audio.getnframes(), 32000)
                self.assertEqual(audio.getnchannels(), 1)
            write_captions(
                [{"text": "Hello {\\pos(0,0)} world", "start": 0, "end": 2}],
                "Bold",
                root / "captions.ass",
            )
            content = (root / "captions.ass").read_text()
            self.assertNotIn("\\pos", content)
            self.assertIn("Hello", content)

    @unittest.skipUnless(
        shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg required"
    )
    def test_real_h264_aac_render_and_full_decode(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            images = []
            for index, color in enumerate(("purple", "blue")):
                image = root / f"scene-{index}.png"
                subprocess.run(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-f",
                        "lavfi",
                        "-i",
                        f"color=c={color}:s=540x960",
                        "-frames:v",
                        "1",
                        "-threads",
                        "1",
                        str(image),
                    ],
                    check=True,
                    timeout=20,
                )
                images.append(image)
            voice = root / "voice.wav"
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=2",
                    str(voice),
                ],
                check=True,
                timeout=20,
            )
            music = root / "music.wav"
            compose_music(story_fixture()["music"], 2, music)
            duration = render_video(
                images,
                voice,
                music,
                [{"start": 0, "end": 1}, {"start": 1, "end": 2}],
                [{"text": "A new perspective", "start": 0, "end": 2}],
                "Classic",
                2,
                1,
                15,
                root / "short.mp4",
            )
            self.assertTrue(1.9 < duration < 2.2)
            self.assertGreater((root / "short.mp4").stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
