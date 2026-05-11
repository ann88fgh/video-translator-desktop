"""Gọi Soniox async API: upload audio → transcribe + dịch → trả tokens.

Reference: https://soniox.com/docs/sdk/python-SDK/stt/async-transcription
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from soniox import SonioxClient
from soniox.types import CreateTranscriptionConfig, TranslationConfig

from .timeline import Token

ProgressCb = Callable[[str, float, str], None]


def _noop_progress(stage: str, percent: float, detail: str = "") -> None:
    pass


def transcribe_and_translate(
    audio_path: str | Path,
    api_key: str,
    *,
    target_language: str = "vi",
    language_hints: list[str] | None = None,
    progress_cb: ProgressCb | None = None,
    cleanup: bool = True,
) -> list[Token]:
    """Pipeline async của Soniox.

    Args:
        audio_path: file audio (wav/mp3/flac/...).
        api_key: Soniox API key.
        target_language: ISO ngôn ngữ đích (mặc định "vi").
        language_hints: gợi ý ngôn ngữ nguồn để tăng độ chính xác.
        progress_cb: callback(stage, percent_0_to_1, detail).
        cleanup: xoá file + transcription trên server sau khi xong.

    Returns:
        list[Token]: tất cả tokens (cả original lẫn translation).
    """
    cb = progress_cb or _noop_progress
    client = SonioxClient(api_key=api_key)

    cb("Soniox: upload", 0.0, "Đang tải file lên Soniox...")
    file_obj = client.files.upload(str(audio_path))

    cb("Soniox: create job", 0.1, "Tạo phiên transcription...")
    config = CreateTranscriptionConfig(
        model="stt-async-v4",
        language_hints=language_hints or ["en", "vi"],
        enable_language_identification=True,
        translation=TranslationConfig(
            type="one_way",
            target_language=target_language,
        ),
    )
    transcription = client.stt.create(config=config, file_id=file_obj.id)

    cb("Soniox: transcribe", 0.2, "Đang nhận dạng + dịch...")
    client.stt.wait(transcription.id)

    cb("Soniox: fetch", 0.95, "Lấy kết quả...")
    transcript = client.stt.get_transcript(transcription.id)

    tokens: list[Token] = []
    for raw in transcript.tokens:
        # SDK trả về Pydantic-like object; truy cập attributes an toàn
        tokens.append(
            Token(
                text=getattr(raw, "text", "") or "",
                start_ms=int(getattr(raw, "start_ms", 0) or 0),
                end_ms=int(getattr(raw, "end_ms", 0) or 0),
                translation_status=getattr(raw, "translation_status", None),
                source_language=getattr(raw, "source_language", None),
                language=getattr(raw, "language", None),
                speaker=getattr(raw, "speaker", None),
            )
        )

    if cleanup:
        try:
            client.stt.delete(transcription.id)
        except Exception:
            pass
        try:
            client.files.delete(file_obj.id)
        except Exception:
            pass

    cb("Soniox: done", 1.0, f"Nhận được {len(tokens)} tokens")
    return tokens
