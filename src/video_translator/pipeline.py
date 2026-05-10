"""Pipeline orchestrator: chạy tuần tự 6 bước từ video in → video out."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import ffmpeg_utils, soniox_client, tts
from .config import AppConfig
from .segments import build_segments
from .timeline import Segment

ProgressCb = Callable[[str, float, str], None]


def _noop(stage: str, percent: float, detail: str = "") -> None:
    pass


@dataclass
class PipelineResult:
    output_path: Path
    n_segments: int
    duration_ms: int
    segments: list[Segment]


class PipelineError(RuntimeError):
    pass


def run_pipeline(
    video_path: str | Path,
    cfg: AppConfig,
    *,
    output_path: str | Path | None = None,
    progress: ProgressCb | None = None,
) -> PipelineResult:
    """Chạy toàn bộ pipeline. Đây là entry point cho thread chạy nền của GUI.

    Stages (% trong tổng):
      0–5%   extract audio
      5–60%  Soniox transcribe + translate
      60–65% build segments
      65–90% TTS
      90–95% build dub track
      95–100% mux video
    """
    cb = progress or _noop
    video_path = Path(video_path)

    if not video_path.exists():
        raise PipelineError(f"File video không tồn tại: {video_path}")
    if not cfg.soniox_api_key.strip():
        raise PipelineError(
            "Chưa có Soniox API key. Mở Settings để nhập key (lấy ở https://console.soniox.com)."
        )

    out_dir = cfg.output_dir_path()
    out_dir.mkdir(parents=True, exist_ok=True)
    if output_path is None:
        output_path = out_dir / f"{video_path.stem}.vi.mp4"
    output_path = Path(output_path)

    work_dir = Path(tempfile.mkdtemp(prefix="vidtrans_"))
    audio_wav = work_dir / "source.wav"
    dub_wav = work_dir / "dub.wav"
    seg_dir = work_dir / "segments"

    try:
        # ── 1. Extract audio ─────────────────────────────────────────
        cb("Extract audio", 0.01, "Đang tách audio từ video...")
        if not ffmpeg_utils.has_audio_stream(video_path):
            raise PipelineError("Video không chứa audio stream để dịch.")
        ffmpeg_utils.extract_audio(video_path, audio_wav)
        total_ms = ffmpeg_utils.get_duration_ms(video_path)
        cb("Extract audio", 0.05, f"Độ dài video: {total_ms / 1000:.1f}s")

        # ── 2. Soniox ─────────────────────────────────────────────────
        def _stt_progress(stage: str, p: float, detail: str = "") -> None:
            cb(stage, 0.05 + p * 0.55, detail)

        tokens = soniox_client.transcribe_and_translate(
            audio_wav,
            api_key=cfg.soniox_api_key,
            target_language=cfg.target_language,
            language_hints=cfg.language_hints,
            progress_cb=_stt_progress,
        )

        # ── 3. Segments ───────────────────────────────────────────────
        cb("Tách câu", 0.62, "Gom tokens thành segments...")
        segments = build_segments(tokens)
        if not segments:
            raise PipelineError(
                "Không nhận được lời thoại nào từ Soniox (có thể video không có giọng nói)."
            )
        cb("Tách câu", 0.65, f"Tổng {len(segments)} đoạn lời thoại")

        # ── 4. TTS song song ─────────────────────────────────────────
        def _tts_progress(stage: str, p: float, detail: str = "") -> None:
            cb(stage, 0.65 + p * 0.25, detail)

        seg_audio = asyncio.run(
            tts.synthesize_all(
                segments,
                voice=cfg.voice,
                out_dir=seg_dir,
                pitch=cfg.pitch,
                auto_fit=cfg.auto_fit,
                progress_cb=_tts_progress,
            )
        )

        # ── 5. Build dub track ───────────────────────────────────────
        cb("Ghép audio", 0.92, "Đang ghép timeline tiếng Việt...")
        ffmpeg_utils.build_dub_track(seg_audio, total_ms, dub_wav)

        # ── 6. Mux ───────────────────────────────────────────────────
        cb("Ghép video", 0.97, "Đang ghép video gốc với audio mới...")
        ffmpeg_utils.mux_video_with_audio(video_path, dub_wav, output_path)

        cb("Hoàn tất", 1.0, f"Đã ghi: {output_path}")
        return PipelineResult(
            output_path=output_path,
            n_segments=len(segments),
            duration_ms=total_ms,
            segments=segments,
        )
    finally:
        if not cfg.keep_temp:
            shutil.rmtree(work_dir, ignore_errors=True)
