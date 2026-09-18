import math
import re
from pathlib import Path

from moviepy import CompositeVideoClip, TextClip, VideoFileClip


PROJECT_ROOT = Path(__file__).resolve().parents[1]

# fonts-dejavu-core (installed in the GitHub Actions workflow) provides these.
# Add more candidates if you run this locally on macOS/Windows.
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
]


def _resolve_font() -> str:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    raise FileNotFoundError(
        "No usable caption font was found. Install 'fonts-dejavu-core' (Linux) or add the "
        "correct font path to FONT_CANDIDATES in caption_burner.py."
    )


def _clip_duration(clip: object) -> float:
    duration = getattr(clip, "duration", None)
    if duration is None:
        raise ValueError("MoviePy clip has no duration metadata.")
    return float(duration)


def _with_timing(clip: object, start: float, duration: float):
    if hasattr(clip, "with_start"):
        clip = clip.with_start(start)
    else:
        clip = clip.set_start(start)

    if hasattr(clip, "with_duration"):
        return clip.with_duration(duration)
    return clip.set_duration(duration)


def _with_position(clip: object, position: tuple[str, str]):
    if hasattr(clip, "with_position"):
        return clip.with_position(position)
    return clip.set_position(position)


def _write_video(clip: object, output_path: Path) -> None:
    clip.write_videofile(
        str(output_path),
        codec="libx264",
        audio_codec="aac",
        fps=30,
        preset="medium",
        threads=4,
        logger=None,
    )


def _caption_units(text_script: str) -> list[str]:
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text_script.strip())
        if sentence.strip()
    ]
    if sentences and max(len(sentence.split()) for sentence in sentences) <= 14:
        return sentences

    words = re.findall(r"\S+", text_script)
    units = []
    for index in range(0, len(words), 5):
        units.append(" ".join(words[index : index + 5]))
    return units


def _make_text_clip(text: str, video_width: int):
    clip_width = max(320, int(video_width * 0.86))
    font_size = max(34, min(74, int(video_width * 0.052)))
    return TextClip(
        font=_resolve_font(),
        text=text,
        font_size=font_size,
        color="white",
        stroke_color="black",
        stroke_width=3,
        method="caption",
        size=(clip_width, None),
        margin=(20, 12),
        text_align="center",
    )


def burn_captions(video_path: str, text_script: str, output_path: str) -> str:
    source = Path(video_path)
    if not source.exists():
        raise FileNotFoundError(f"Video file does not exist: {source}")
    if not text_script.strip():
        raise ValueError("text_script is empty; cannot create captions.")

    destination = Path(output_path)
    if not destination.is_absolute():
        destination = PROJECT_ROOT / "assets" / "outputs" / destination
    destination.parent.mkdir(parents=True, exist_ok=True)

    video = VideoFileClip(str(source))
    final = None
    caption_clips = []
    try:
        duration = _clip_duration(video)
        units = _caption_units(text_script)
        unit_duration = max(0.75, duration / max(1, len(units)))

        for index, unit in enumerate(units):
            start = min(duration, index * unit_duration)
            remaining = max(0.1, duration - start)
            active_duration = min(unit_duration, remaining)
            text_clip = _make_text_clip(unit, int(video.w))
            text_clip = _with_position(text_clip, ("center", "center"))
            text_clip = _with_timing(text_clip, start, active_duration)
            caption_clips.append(text_clip)

        final = CompositeVideoClip([video, *caption_clips])
        _write_video(final, destination)
    finally:
        if final is not None:
            final.close()
        for caption_clip in caption_clips:
            caption_clip.close()
        video.close()

    return str(destination)
