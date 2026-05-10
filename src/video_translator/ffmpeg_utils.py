"""Wrapper quanh ffmpeg: extract audio, build dub track, mux."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path

import imageio_ffmpeg

from .timeline import Segment


def ffmpeg_path() -> str:
    """Trả về đường dẫn ffmpeg, ưu tiên ffmpeg trong PATH, fallback imageio-ffmpeg."""
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def ffprobe_path() -> str | None:
    """Đường dẫn ffprobe nếu có trong PATH (imageio-ffmpeg không kèm ffprobe)."""
    return shutil.which("ffprobe")


def _run(cmd: list[str]) -> subprocess.CompletedProcess[bytes]:
    """Chạy ffmpeg/ffprobe, raise nếu fail. Bắt stderr để báo lỗi rõ."""
    proc = subprocess.run(cmd, check=False, capture_output=True)
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Command failed (exit {proc.returncode}): {' '.join(cmd[:3])} ...\n{stderr[-1500:]}"
        )
    return proc


def get_duration_ms(media_path: str | Path) -> int:
    """Lấy độ dài (ms) của video/audio. Ưu tiên ffprobe, fallback ffmpeg."""
    media_path = str(media_path)
    probe = ffprobe_path()
    if probe:
        proc = _run(
            [
                probe,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                media_path,
            ]
        )
        data = json.loads(proc.stdout.decode("utf-8"))
        seconds = float(data["format"]["duration"])
        return int(seconds * 1000)

    # Fallback: parse `ffmpeg -i` output stderr.
    proc = subprocess.run(
        [ffmpeg_path(), "-hide_banner", "-i", media_path],
        check=False,
        capture_output=True,
    )
    stderr = proc.stderr.decode("utf-8", errors="replace")
    for line in stderr.splitlines():
        line = line.strip()
        if line.startswith("Duration:"):
            # "Duration: 00:01:23.45, start: ..."
            ts = line.split("Duration:", 1)[1].split(",", 1)[0].strip()
            h, m, s = ts.split(":")
            total = (int(h) * 3600 + int(m) * 60 + float(s)) * 1000
            return int(total)
    raise RuntimeError("Không xác định được duration của file.")


def has_audio_stream(media_path: str | Path) -> bool:
    """Trả về True nếu file có ít nhất 1 audio stream."""
    probe = ffprobe_path()
    if probe:
        proc = _run(
            [
                probe,
                "-v", "error",
                "-select_streams", "a",
                "-show_entries", "stream=codec_type",
                "-of", "json",
                str(media_path),
            ]
        )
        data = json.loads(proc.stdout.decode("utf-8"))
        return bool(data.get("streams"))

    proc = subprocess.run(
        [ffmpeg_path(), "-hide_banner", "-i", str(media_path)],
        check=False,
        capture_output=True,
    )
    stderr = proc.stderr.decode("utf-8", errors="replace")
    return "Audio:" in stderr


def extract_audio(
    video_path: str | Path,
    out_wav: str | Path,
    sample_rate: int = 16000,
) -> None:
    """Tách audio từ video → wav mono `sample_rate` Hz."""
    _run(
        [
            ffmpeg_path(),
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-i", str(video_path),
            "-vn",
            "-ac", "1",
            "-ar", str(sample_rate),
            "-f", "wav",
            str(out_wav),
        ]
    )


def build_dub_track(
    segments_with_audio: Iterable[tuple[Segment, str | Path]],
    total_duration_ms: int,
    out_wav: str | Path,
    sample_rate: int = 24000,
) -> None:
    """Ghép các đoạn TTS theo timeline.

    Strategy: dùng filter_complex `adelay` để dịch từng đoạn về đúng `start_ms`,
    sau đó `amix` tất cả lại. Output là WAV mono `sample_rate` Hz có độ dài
    = `total_duration_ms`.
    """
    items = list(segments_with_audio)
    if not items:
        # Không có segment → tạo file silent đúng độ dài
        seconds = total_duration_ms / 1000
        _run(
            [
                ffmpeg_path(),
                "-y",
                "-hide_banner",
                "-loglevel", "error",
                "-f", "lavfi",
                "-i", f"anullsrc=channel_layout=mono:sample_rate={sample_rate}",
                "-t", f"{seconds:.3f}",
                str(out_wav),
            ]
        )
        return

    cmd: list[str] = [
        ffmpeg_path(),
        "-y",
        "-hide_banner",
        "-loglevel", "error",
    ]

    # Input 0: silence base track đúng độ dài
    seconds = total_duration_ms / 1000
    cmd += [
        "-f", "lavfi",
        "-i", f"anullsrc=channel_layout=mono:sample_rate={sample_rate}",
        "-t", f"{seconds:.3f}",
    ]

    # Inputs 1..N: từng file segment audio
    for _seg, audio_path in items:
        cmd += ["-i", str(audio_path)]

    # filter_complex: delay mỗi segment về start_ms, rồi amix với base
    parts: list[str] = []
    mix_inputs: list[str] = ["[0:a]"]
    for i, (seg, _path) in enumerate(items, start=1):
        delay = max(0, int(seg.start_ms))
        parts.append(
            f"[{i}:a]aformat=sample_fmts=fltp:sample_rates={sample_rate}:channel_layouts=mono,"
            f"adelay={delay}|{delay}[s{i}]"
        )
        mix_inputs.append(f"[s{i}]")

    n_inputs = len(mix_inputs)
    parts.append(
        "".join(mix_inputs)
        + f"amix=inputs={n_inputs}:duration=first:dropout_transition=0,"
        + f"atrim=duration={seconds:.3f},"
        + "asetpts=N/SR/TB[mix]"
    )

    filter_complex = ";".join(parts)

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[mix]",
        "-ar", str(sample_rate),
        "-ac", "1",
        str(out_wav),
    ]
    _run(cmd)


def mux_video_with_audio(
    video_path: str | Path,
    audio_path: str | Path,
    out_path: str | Path,
) -> None:
    """Ghép video gốc + audio mới (thay thế audio gốc)."""
    _run(
        [
            ffmpeg_path(),
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(out_path),
        ]
    )
