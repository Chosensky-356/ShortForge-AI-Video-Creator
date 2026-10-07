import reflex as rx

import json
import logging
import math
import struct
import subprocess
import wave
from pathlib import Path


class RenderError(ValueError):
    pass


def _run(arguments: list[str], timeout: int = 180) -> bytes:
    result = subprocess.run(
        arguments,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RenderError(
            "Video rendering or media validation failed. Please try again; no failed video is charged."
        )
    if len(result.stdout) > 65536:
        raise RenderError("Media validation returned an oversized response.")
    return result.stdout


def probe(path: Path) -> dict:
    if not path.is_file() or not 0 < path.stat().st_size <= 64 * 1024 * 1024:
        raise RenderError(
            "Generated media is empty or exceeds the safe 64 MB limit."
        )
    return json.loads(
        _run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type,codec_name,width,height,pix_fmt,duration",
                "-of",
                "json",
                str(path),
            ],
            20,
        )
    )


def speech_timing(path: Path, target: int) -> tuple[float, float, float]:
    info = probe(path)
    audio = [
        s for s in info.get("streams", []) if s.get("codec_type") == "audio"
    ]
    duration = float(info.get("format", {}).get("duration", 0))
    if (
        not audio
        or not math.isfinite(duration)
        or duration <= 0
        or duration > 90
    ):
        raise RenderError(
            "The generated narration could not be verified. Try a shorter idea."
        )
    available = target - 0.5
    pace = max(1.0, duration / available)
    if pace > 1.2:
        raise RenderError(
            "The narration is too long for this duration, even at a safe speaking pace. Try a shorter, more focused idea or choose a longer duration. No video was charged."
        )
    return duration, duration / pace, pace


def compose_music(score: dict, duration: float, output: Path) -> None:
    if not 0 < duration <= 60:
        raise RenderError("Invalid instrumental duration.")
    rate = 16000
    beat = 60 / score["tempo"]
    chords = score["chords"]
    melody = score["melody"]
    with (
        output.open("wb") as raw_file,
        wave.open(raw_file, "wb") as destination,
    ):
        destination.setnchannels(1)
        destination.setsampwidth(2)
        destination.setframerate(rate)
        for start in range(0, math.ceil(duration * rate), 4096):
            buffer = bytearray()
            for sample in range(
                start, min(start + 4096, math.ceil(duration * rate))
            ):
                t = sample / rate
                chord_number = int(t / (beat * 4))
                chord = chords[chord_number % len(chords)]
                chord_time = t % (beat * 4)
                chord_envelope = min(1, chord_time / 0.03) * math.exp(
                    -chord_time * 1.4
                )
                tone = 0.0
                for note in chord:
                    frequency = 440 * 2 ** ((note - 69) / 12)
                    tone += math.sin(2 * math.pi * frequency * t) / len(chord)
                melody_number = int(t / beat)
                melody_time = t % beat
                frequency = 440 * 2 ** (
                    (melody[melody_number % len(melody)] - 69) / 12
                )
                melody_tone = (
                    math.sin(2 * math.pi * frequency * t)
                    * min(1, melody_time / 0.02)
                    * math.exp(-melody_time * 5)
                )
                fade = min(1.0, t / 0.4, max(0, (duration - t) / 0.8))
                value = int(
                    32767
                    * fade
                    * (0.2 * tone * chord_envelope + 0.1 * melody_tone)
                )
                buffer.extend(struct.pack("<h", value))
            destination.writeframesraw(buffer)


def _ass_time(seconds: float) -> str:
    total = max(0, round(seconds * 100))
    minutes, centiseconds = divmod(total, 6000)
    hours, minutes = divmod(minutes, 60)
    whole_seconds, centiseconds = divmod(centiseconds, 100)
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{centiseconds:02d}"


def write_captions(captions: list[dict], style: str, output: Path) -> None:
    font_size = 36 if style == "Bold" else 29
    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 540\nPlayResY: 960\nWrapStyle: 0\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,DejaVu Sans,{font_size},&H00FFFFFF,&H00FFFFFF,&H00101010,&H90000000,-1,0,0,0,100,100,0,0,1,3,0,2,42,42,170,1\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lines = [header]
    for caption in captions:
        # ASS override syntax and explicit line breaks must never come from model text.
        safe = (
            caption["text"]
            .replace("\\", "")
            .replace("{", "(")
            .replace("}", ")")
            .replace("\n", " ")
            .replace("\r", " ")
        )
        lines.append(
            f"Dialogue: 0,{_ass_time(caption['start'])},{_ass_time(caption['end'])},Default,,0,0,0,,{safe}\n"
        )
    output.write_text("".join(lines), encoding="utf-8")


def validate_output(path: Path, target: int, expected: float) -> float:
    info = probe(path)
    streams = info.get("streams", [])
    video = [s for s in streams if s.get("codec_type") == "video"]
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    duration = float(info.get("format", {}).get("duration", 0))
    if (
        len(video) != 1
        or len(audio) != 1
        or video[0].get("codec_name") != "h264"
        or audio[0].get("codec_name") != "aac"
        or video[0].get("width") != 540
        or video[0].get("height") != 960
        or video[0].get("pix_fmt") != "yuv420p"
        or not math.isfinite(duration)
        or not 0 < duration <= min(target, 60)
        or abs(duration - expected) > 0.3
    ):
        raise RenderError(
            "The finished MP4 failed duration, picture or audio checks. No video was charged. Try again."
        )
    audio_duration = float(audio[0].get("duration", 0))
    if (
        not math.isfinite(audio_duration)
        or abs(audio_duration - expected) > 0.3
    ):
        raise RenderError(
            "The finished narration duration could not be verified. No video was charged."
        )
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-v",
            "error",
            "-xerror",
            "-threads",
            "1",
            "-i",
            str(path),
            "-f",
            "null",
            "-",
        ],
        100,
    )
    return duration


def render_video(
    images: list[Path],
    voice: Path,
    music: Path,
    scenes: list[dict],
    captions: list[dict],
    caption_style: str,
    duration: float,
    pace: float,
    target: int,
    output: Path,
) -> float:
    if (
        not 2 <= len(images) <= 4
        or len(images) != len(scenes)
        or not 0 < duration <= target - 0.4
        or not 1 <= pace <= 1.2
        or len(captions) > 40
    ):
        raise RenderError("The render inputs are outside safe limits.")
    root = output.parent.resolve()
    paths = [*images, voice, music, output]
    if any(path.parent.resolve() != root for path in paths):
        raise RenderError("Invalid render media location.")
    segments: list[Path] = []
    try:
        total_frames = math.ceil(duration * 24)
        previous_frame = 0
        for index, image in enumerate(images):
            boundary = (
                total_frames
                if index == len(images) - 1
                else round(scenes[index]["end"] * 24)
            )
            frames = boundary - previous_frame
            if frames < 1:
                raise RenderError("A generated scene is too short to render.")
            previous_frame = boundary
            segment = root / f"segment-{index}.mp4"
            _run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-v",
                    "error",
                    "-nostdin",
                    "-y",
                    "-threads",
                    "1",
                    "-loop",
                    "1",
                    "-framerate",
                    "24",
                    "-i",
                    str(image),
                    "-vf",
                    "scale=540:960:force_original_aspect_ratio=increase,crop=540:960,setsar=1",
                    "-frames:v",
                    str(frames),
                    "-an",
                    "-c:v",
                    "libx264",
                    "-threads",
                    "1",
                    "-preset",
                    "ultrafast",
                    "-crf",
                    "24",
                    "-pix_fmt",
                    "yuv420p",
                    "-filter_threads",
                    "1",
                    "-fs",
                    "24000000",
                    str(segment),
                ],
                150,
            )
            segments.append(segment)
        timeline = root / "timeline.txt"
        timeline.write_text(
            "".join(f"file '{segment.name}'\n" for segment in segments),
            encoding="utf-8",
        )
        joined = root / "joined.mp4"
        _run(
            [
                "ffmpeg",
                "-hide_banner",
                "-v",
                "error",
                "-nostdin",
                "-y",
                "-f",
                "concat",
                "-safe",
                "1",
                "-i",
                str(timeline),
                "-c",
                "copy",
                str(joined),
            ],
            30,
        )
        subtitles = root / "captions.ass"
        filters = f"[1:a]atempo={pace:.8f},aresample=48000,loudnorm=I=-16:TP=-1.5:LRA=7[voice];[2:a]aresample=48000,volume=0.12[music];[voice][music]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.95[audio]"
        video_filter = "null"
        if caption_style != "None":
            write_captions(captions, caption_style, subtitles)
            video_filter = "ass=filename=captions.ass"
        # Fixed safe basenames plus cwd avoid escaping filesystem paths in filter syntax.
        _run_in_directory(
            [
                "ffmpeg",
                "-hide_banner",
                "-v",
                "error",
                "-nostdin",
                "-y",
                "-threads",
                "1",
                "-i",
                "joined.mp4",
                "-i",
                voice.name,
                "-i",
                music.name,
                "-filter_complex_threads",
                "1",
                "-filter_threads",
                "1",
                "-filter_complex",
                filters,
                "-vf",
                video_filter,
                "-map",
                "0:v:0",
                "-map",
                "[audio]",
                "-t",
                f"{duration:.6f}",
                "-c:v",
                "libx264",
                "-threads",
                "1",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-ar",
                "48000",
                "-movflags",
                "+faststart",
                "-fs",
                "63000000",
                output.name,
            ],
            root,
            240,
        )
        return validate_output(output, target, duration)
    finally:
        for segment in segments:
            try:
                segment.unlink(missing_ok=True)
            except OSError as e:
                logging.exception(
                    f"Error: segment cleanup failed ({type(e).__name__})"
                )


def _run_in_directory(
    arguments: list[str], directory: Path, timeout: int
) -> None:
    result = subprocess.run(
        arguments,
        cwd=directory,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RenderError(
            "The video renderer could not finish. Captions or rendering support may be unavailable. No failed video was charged. Please try again."
        )
