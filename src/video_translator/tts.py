"""Tạo TTS bằng edge-tts cho từng segment, có auto-fit duration."""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

import edge_tts

from .ffmpeg_utils import get_duration_ms
from .timeline import Segment


async def _synthesize_once(
    text: str,
    voice: str,
    rate: str,
    pitch: str,
    out_path: str | Path,
) -> None:
    """Gọi edge-tts một lần, ghi MP3 ra `out_path`."""
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
    await communicate.save(str(out_path))


def _rate_str(percent: int) -> str:
    """Định dạng rate cho edge-tts (e.g. "+15%", "-5%")."""
    sign = "+" if percent >= 0 else ""
    return f"{sign}{percent}%"


async def synthesize_segment_with_fit(
    seg: Segment,
    voice: str,
    out_path: str | Path,
    *,
    base_rate_pct: int = 0,
    pitch: str = "+0Hz",
    auto_fit: bool = True,
    max_speedup_pct: int = 50,
    fit_tolerance: float = 1.05,
) -> Path:
    """Tạo TTS cho 1 segment, tự tăng tốc độ nếu vượt thời gian cho phép.

    Tăng tốc theo các nấc 0%, +10%, +20%, +35%, +50%. Nếu vẫn không vừa,
    chấp nhận output dài hơn (sẽ bị ghép chồng nhẹ với segment kế tiếp).
    """
    out_path = Path(out_path)
    if not seg.translated_text:
        # Tạo file silent rất ngắn để giữ index
        out_path.write_bytes(b"")
        return out_path

    target_ms = seg.duration_ms

    # Lần đầu thử với base_rate_pct
    await _synthesize_once(
        seg.translated_text, voice, _rate_str(base_rate_pct), pitch, out_path
    )

    if not auto_fit or target_ms <= 0:
        return out_path

    actual_ms = _try_get_duration(out_path)
    if actual_ms <= target_ms * fit_tolerance:
        return out_path

    # Đoán rate cần thiết: rate_factor = actual / target → cần tăng
    # speedup_pct sao cho actual / (1 + speedup/100) ≈ target.
    needed_pct = int(((actual_ms / target_ms) - 1.0) * 100) + base_rate_pct + 5
    needed_pct = min(needed_pct, max_speedup_pct)
    if needed_pct <= base_rate_pct:
        return out_path

    await _synthesize_once(
        seg.translated_text, voice, _rate_str(needed_pct), pitch, out_path
    )
    return out_path


def _try_get_duration(path: str | Path) -> int:
    try:
        return get_duration_ms(path)
    except Exception:
        return 0


async def synthesize_all(
    segments: list[Segment],
    voice: str,
    out_dir: str | Path,
    *,
    pitch: str = "+0Hz",
    auto_fit: bool = True,
    concurrency: int = 4,
    progress_cb=None,
) -> list[tuple[Segment, Path]]:
    """Synthesize tất cả segment song song (giới hạn `concurrency`)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sem = asyncio.Semaphore(concurrency)
    results: list[tuple[Segment, Path]] = []
    done_count = 0

    async def _one(seg: Segment) -> None:
        nonlocal done_count
        async with sem:
            path = out_dir / f"seg_{seg.index:04d}.mp3"
            try:
                await synthesize_segment_with_fit(
                    seg, voice=voice, out_path=path, pitch=pitch, auto_fit=auto_fit
                )
            except Exception as e:  # noqa: BLE001
                # Ghi log nhưng vẫn tạo file rỗng để pipeline tiếp tục
                print(f"[tts] segment #{seg.index} failed: {e}")
                with contextlib.suppress(Exception):
                    path.write_bytes(b"")
            results.append((seg, path))
            done_count += 1
            if progress_cb is not None:
                progress_cb(
                    "TTS",
                    done_count / max(1, len(segments)),
                    f"Đoạn {done_count}/{len(segments)}",
                )

    await asyncio.gather(*[_one(s) for s in segments])
    # Sắp xếp lại theo index gốc
    results.sort(key=lambda r: r[0].index)
    return results
