"""Cấu hình app: load/save từ file JSON + .env."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from dotenv import load_dotenv


def _config_dir() -> Path:
    """Thư mục chứa settings.json (per-user)."""
    base = os.environ.get("XDG_CONFIG_HOME") or os.environ.get("APPDATA")
    if base:
        return Path(base) / "video-translator"
    return Path.home() / ".config" / "video-translator"


def _config_file() -> Path:
    return _config_dir() / "settings.json"


@dataclass
class AppConfig:
    soniox_api_key: str = ""
    target_language: str = "vi"
    voice: str = "vi-VN-HoaiMyNeural"
    rate: str = "+0%"
    pitch: str = "+0Hz"
    auto_fit: bool = True
    keep_temp: bool = False
    output_dir: str = ""
    language_hints: list[str] = field(
        default_factory=lambda: ["en", "vi", "ja", "ko", "zh", "fr", "es"]
    )

    @classmethod
    def load(cls) -> AppConfig:
        load_dotenv(override=False)

        # Bắt đầu từ defaults, override bằng settings.json (nếu có), rồi env vars
        cfg = cls()

        path = _config_file()
        if path.exists():
            try:
                stored = json.loads(path.read_text(encoding="utf-8"))
                for k, v in stored.items():
                    if hasattr(cfg, k):
                        setattr(cfg, k, v)
            except (OSError, json.JSONDecodeError):
                pass

        env_key = os.environ.get("SONIOX_API_KEY", "").strip()
        if env_key:
            cfg.soniox_api_key = env_key

        return cfg

    def save(self) -> None:
        path = _config_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        # Tránh ghi soniox_api_key ra settings.json nếu nó đến từ env var
        # (khó phân biệt — vẫn ghi để đơn giản; user có thể xoá thủ công)
        path.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def output_dir_path(self) -> Path:
        if self.output_dir:
            return Path(self.output_dir).expanduser()
        return Path.home() / "Videos" / "video-translator-output"


VOICE_CHOICES: list[tuple[str, str]] = [
    ("vi-VN-HoaiMyNeural", "Hoài My (nữ)"),
    ("vi-VN-NamMinhNeural", "Nam Minh (nam)"),
]
