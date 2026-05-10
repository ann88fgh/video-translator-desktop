"""Data models cho tokens và segments trên trục thời gian."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Token:
    """Một token (từ / sub-word) trả về từ Soniox.

    Token có thể là:
      - "original": token nhận dạng được từ ngôn ngữ gốc
      - "translation": token là bản dịch (mới được tạo bởi Soniox)
      - "none": ký tự đệm / dấu câu không thuộc loại nào
    """

    text: str
    start_ms: int
    end_ms: int
    translation_status: str | None = None  # "original" | "translation" | "none"
    source_language: str | None = None
    language: str | None = None
    speaker: str | None = None

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)


@dataclass
class Segment:
    """Một đoạn lời thoại liên tục (gốc + dịch)."""

    index: int
    start_ms: int
    end_ms: int
    source_text: str = ""
    translated_text: str = ""
    source_tokens: list[Token] = field(default_factory=list)
    translation_tokens: list[Token] = field(default_factory=list)

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)

    def __repr__(self) -> str:  # pragma: no cover - debug
        src = self.source_text[:30] + ("…" if len(self.source_text) > 30 else "")
        tgt = self.translated_text[:30] + ("…" if len(self.translated_text) > 30 else "")
        return (
            f"Segment(#{self.index} {self.start_ms}->{self.end_ms}ms "
            f"src='{src}' tgt='{tgt}')"
        )
