"""Test build_dub_track xử lý các segment có audio rỗng/không tồn tại."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from video_translator.ffmpeg_utils import build_dub_track, get_duration_ms
from video_translator.timeline import Segment


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


pytestmark = pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg not available")


def _make_silent_mp3(path: Path, duration_s: float = 1.0) -> None:
    """Tạo MP3 silent ngắn cho test."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=channel_layout=mono:sample_rate=24000:duration={duration_s}",
            "-q:a",
            "9",
            str(path),
        ],
        check=True,
    )


def test_build_dub_skips_zero_byte_audio_files(tmp_path: Path) -> None:
    """Regression: segment với file MP3 0-byte không được phép crash ffmpeg.

    Trước fix: tts.py viết `b""` khi translated_text rỗng → ffmpeg fail
    "Could not seek to 1026 / Invalid argument".
    """
    valid_seg_path = tmp_path / "seg_0001.mp3"
    _make_silent_mp3(valid_seg_path, 0.5)

    empty_seg_path = tmp_path / "seg_0000.mp3"
    empty_seg_path.write_bytes(b"")

    segments = [
        (Segment(index=0, start_ms=0, end_ms=2000, source_text="hi", translated_text=""), empty_seg_path),
        (Segment(index=1, start_ms=2000, end_ms=4000, source_text="bye", translated_text="tạm biệt"), valid_seg_path),
    ]
    out_wav = tmp_path / "dub.wav"
    build_dub_track(segments, total_duration_ms=5000, out_wav=out_wav)

    assert out_wav.exists()
    assert out_wav.stat().st_size > 0
    duration_ms = get_duration_ms(out_wav)
    # Cho phép sai số 50ms cho atrim
    assert abs(duration_ms - 5000) < 50


def test_build_dub_all_empty_yields_silent_track(tmp_path: Path) -> None:
    """Khi tất cả segment đều rỗng/missing, tạo track silent đúng độ dài."""
    missing_path = tmp_path / "seg_does_not_exist.mp3"
    empty_path = tmp_path / "seg_empty.mp3"
    empty_path.write_bytes(b"")

    segments = [
        (Segment(index=0, start_ms=0, end_ms=1000, source_text="x", translated_text=""), missing_path),
        (Segment(index=1, start_ms=1000, end_ms=2000, source_text="y", translated_text=""), empty_path),
    ]
    out_wav = tmp_path / "dub.wav"
    build_dub_track(segments, total_duration_ms=3000, out_wav=out_wav)

    assert out_wav.exists()
    assert out_wav.stat().st_size > 0
    duration_ms = get_duration_ms(out_wav)
    assert abs(duration_ms - 3000) < 50
