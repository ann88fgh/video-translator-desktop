"""Cửa sổ Settings — quản lý API key, voice, output dir, ..."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from ..config import VOICE_CHOICES, AppConfig


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, master: ctk.CTk, cfg: AppConfig, on_save: Callable[[AppConfig], None]):
        super().__init__(master)
        self.title("Cấu hình")
        self.geometry("520x460")
        self.resizable(False, False)
        self._cfg = cfg
        self._on_save = on_save

        self.transient(master)
        self.grab_set()

        pad = {"padx": 16, "pady": 8}

        # Soniox API key
        ctk.CTkLabel(self, text="Soniox API Key", anchor="w").pack(fill="x", **pad)
        self.var_api_key = ctk.StringVar(value=cfg.soniox_api_key)
        api_entry = ctk.CTkEntry(self, textvariable=self.var_api_key, show="•")
        api_entry.pack(fill="x", padx=16)

        ctk.CTkLabel(
            self,
            text="Lấy key miễn phí ở https://console.soniox.com",
            text_color="#888",
            anchor="w",
            font=ctk.CTkFont(size=11),
        ).pack(fill="x", padx=16, pady=(2, 6))

        # Voice
        ctk.CTkLabel(self, text="Giọng đọc tiếng Việt", anchor="w").pack(fill="x", **pad)
        voice_labels = [label for _name, label in VOICE_CHOICES]
        cur_label = next((lab for n, lab in VOICE_CHOICES if n == cfg.voice), voice_labels[0])
        self.var_voice = ctk.StringVar(value=cur_label)
        ctk.CTkOptionMenu(self, values=voice_labels, variable=self.var_voice).pack(
            fill="x", padx=16
        )

        # Auto-fit checkbox
        self.var_auto_fit = ctk.BooleanVar(value=cfg.auto_fit)
        ctk.CTkCheckBox(
            self,
            text="Tự tăng tốc độ đọc nếu giọng dịch dài hơn lời thoại gốc",
            variable=self.var_auto_fit,
        ).pack(fill="x", padx=16, pady=(12, 4))

        # Keep temp
        self.var_keep_temp = ctk.BooleanVar(value=cfg.keep_temp)
        ctk.CTkCheckBox(
            self,
            text="Giữ lại file tạm (debug)",
            variable=self.var_keep_temp,
        ).pack(fill="x", padx=16, pady=(0, 12))

        # Output dir
        ctk.CTkLabel(self, text="Thư mục lưu video output", anchor="w").pack(fill="x", **pad)
        out_frame = ctk.CTkFrame(self, fg_color="transparent")
        out_frame.pack(fill="x", padx=16)
        self.var_out = ctk.StringVar(
            value=cfg.output_dir or str(cfg.output_dir_path())
        )
        ctk.CTkEntry(out_frame, textvariable=self.var_out).pack(
            side="left", fill="x", expand=True
        )
        ctk.CTkButton(
            out_frame, text="Chọn...", width=80, command=self._pick_dir
        ).pack(side="left", padx=(8, 0))

        # Buttons
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", side="bottom", padx=16, pady=16)
        ctk.CTkButton(btns, text="Huỷ", fg_color="gray30", command=self.destroy).pack(
            side="right", padx=(8, 0)
        )
        ctk.CTkButton(btns, text="Lưu", command=self._save).pack(side="right")

    def _pick_dir(self) -> None:
        path = filedialog.askdirectory(parent=self, title="Chọn thư mục output")
        if path:
            self.var_out.set(path)

    def _save(self) -> None:
        cfg = self._cfg
        cfg.soniox_api_key = self.var_api_key.get().strip()
        # map label -> name
        label_to_name = {label: name for name, label in VOICE_CHOICES}
        cfg.voice = label_to_name.get(self.var_voice.get(), cfg.voice)
        cfg.auto_fit = bool(self.var_auto_fit.get())
        cfg.keep_temp = bool(self.var_keep_temp.get())
        out = self.var_out.get().strip()
        cfg.output_dir = str(Path(out)) if out else ""
        cfg.save()
        self._on_save(cfg)
        self.destroy()
