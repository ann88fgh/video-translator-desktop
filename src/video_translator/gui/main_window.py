"""Cửa sổ chính: chọn video → chạy pipeline → hiển thị tiến trình."""

from __future__ import annotations

import os
import platform
import queue
import subprocess
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from ..config import VOICE_CHOICES, AppConfig
from ..pipeline import PipelineError, run_pipeline
from .settings_dialog import SettingsDialog

VIDEO_EXTENSIONS = (".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v")


class MainWindow(ctk.CTk):
    def __init__(self) -> None:
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")
        super().__init__()

        self.title("Video Translator — Lồng tiếng Việt")
        self.geometry("760x620")
        self.minsize(640, 540)

        self._cfg = AppConfig.load()
        self._video_path: Path | None = None
        self._pipeline_thread: threading.Thread | None = None
        self._progress_queue: queue.Queue[tuple[str, str, float, str]] = queue.Queue()

        self._build_ui()
        self.after(100, self._poll_progress)

    # ─── UI building ─────────────────────────────────────────────────
    def _build_ui(self) -> None:
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent", height=56)
        header.pack(fill="x", padx=16, pady=(16, 0))
        ctk.CTkLabel(
            header,
            text="🎬  Video Translator",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(side="left")
        ctk.CTkButton(
            header, text="⚙  Cấu hình", width=110, command=self._open_settings
        ).pack(side="right")

        # Drop zone
        self.drop_zone = ctk.CTkFrame(self, height=160, corner_radius=12)
        self.drop_zone.pack(fill="x", padx=16, pady=(16, 8))
        self.drop_label = ctk.CTkLabel(
            self.drop_zone,
            text="📁  Bấm để chọn file video\n(.mp4 .mkv .mov .webm)",
            font=ctk.CTkFont(size=14),
            text_color="#888",
        )
        self.drop_label.pack(expand=True, fill="both", padx=20, pady=20)
        self.drop_zone.bind("<Button-1>", lambda _e: self._pick_video())
        self.drop_label.bind("<Button-1>", lambda _e: self._pick_video())

        # Voice picker row
        voice_row = ctk.CTkFrame(self, fg_color="transparent")
        voice_row.pack(fill="x", padx=16, pady=(8, 8))
        ctk.CTkLabel(voice_row, text="Giọng đọc:").pack(side="left", padx=(0, 8))
        voice_labels = [label for _name, label in VOICE_CHOICES]
        cur_label = next(
            (lab for n, lab in VOICE_CHOICES if n == self._cfg.voice),
            voice_labels[0],
        )
        self._voice_var = ctk.StringVar(value=cur_label)
        ctk.CTkOptionMenu(
            voice_row, values=voice_labels, variable=self._voice_var, width=240
        ).pack(side="left")

        # Action button
        self.start_btn = ctk.CTkButton(
            self,
            text="▶  Bắt đầu lồng tiếng",
            height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._on_start_clicked,
            state="disabled",
        )
        self.start_btn.pack(fill="x", padx=16, pady=(8, 12))

        # Progress
        self.progress_bar = ctk.CTkProgressBar(self, height=14)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=16, pady=(0, 4))
        self.stage_label = ctk.CTkLabel(
            self, text="Sẵn sàng.", anchor="w", text_color="#888"
        )
        self.stage_label.pack(fill="x", padx=16)

        # Log
        log_frame = ctk.CTkFrame(self)
        log_frame.pack(fill="both", expand=True, padx=16, pady=(8, 16))
        self.log_box = ctk.CTkTextbox(
            log_frame, font=ctk.CTkFont(family="Courier", size=12)
        )
        self.log_box.pack(fill="both", expand=True, padx=8, pady=8)
        self.log_box.configure(state="disabled")

    # ─── Actions ─────────────────────────────────────────────────────
    def _pick_video(self) -> None:
        path = filedialog.askopenfilename(
            title="Chọn video",
            filetypes=[
                ("Video files", "*.mp4 *.mkv *.mov *.webm *.avi *.m4v"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        self._set_video(Path(path))

    def _set_video(self, path: Path) -> None:
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            messagebox.showwarning(
                "Định dạng lạ", f"Đuôi file '{path.suffix}' không quen, vẫn thử nhé."
            )
        self._video_path = path
        self.drop_label.configure(
            text=f"📁  {path.name}\n{_human_size(path)}",
            text_color=("gray10", "gray90"),
        )
        self.start_btn.configure(state="normal")
        self._log(f"Đã chọn file: {path}")

    def _open_settings(self) -> None:
        SettingsDialog(self, self._cfg, on_save=self._on_settings_saved)

    def _on_settings_saved(self, cfg: AppConfig) -> None:
        self._cfg = cfg
        # Cập nhật voice picker nếu user đổi voice trong settings
        cur_label = next(
            (lab for n, lab in VOICE_CHOICES if n == cfg.voice),
            VOICE_CHOICES[0][1],
        )
        self._voice_var.set(cur_label)
        self._log("Đã lưu cấu hình.")

    def _on_start_clicked(self) -> None:
        if self._pipeline_thread and self._pipeline_thread.is_alive():
            return
        if not self._video_path:
            messagebox.showinfo("Chưa chọn video", "Bạn cần chọn 1 file video trước.")
            return
        if not self._cfg.soniox_api_key.strip():
            messagebox.showwarning(
                "Thiếu API key",
                "Bạn cần nhập Soniox API key trong Cấu hình trước (lấy ở "
                "https://console.soniox.com).",
            )
            self._open_settings()
            return

        # Sync voice picker → config (không lưu file, chỉ runtime)
        label_to_name = {label: name for name, label in VOICE_CHOICES}
        self._cfg.voice = label_to_name.get(self._voice_var.get(), self._cfg.voice)

        self.start_btn.configure(state="disabled", text="Đang xử lý...")
        self.progress_bar.set(0)
        self.stage_label.configure(text="Khởi động pipeline...")
        self._log("\n=== Bắt đầu pipeline ===")

        self._pipeline_thread = threading.Thread(
            target=self._run_pipeline_background, daemon=True
        )
        self._pipeline_thread.start()

    def _run_pipeline_background(self) -> None:
        assert self._video_path is not None
        try:
            result = run_pipeline(
                self._video_path,
                self._cfg,
                progress=self._enqueue_progress,
            )
            self._progress_queue.put(("done", "Hoàn tất", 1.0, str(result.output_path)))
        except PipelineError as e:
            self._progress_queue.put(("error", "Lỗi", 0.0, str(e)))
        except Exception as e:  # noqa: BLE001
            self._progress_queue.put(("error", "Lỗi không xác định", 0.0, repr(e)))

    def _enqueue_progress(self, stage: str, percent: float, detail: str = "") -> None:
        self._progress_queue.put(("progress", stage, percent, detail))

    # ─── Progress polling (chạy trên main thread) ───────────────────
    def _poll_progress(self) -> None:
        try:
            while True:
                kind, stage, percent, detail = self._progress_queue.get_nowait()
                if kind == "progress":
                    self.progress_bar.set(max(0.0, min(1.0, percent)))
                    self.stage_label.configure(
                        text=f"[{int(percent * 100):3d}%] {stage} — {detail}"
                    )
                    self._log(f"[{int(percent * 100):3d}%] {stage}: {detail}")
                elif kind == "done":
                    self._on_done(Path(detail))
                elif kind == "error":
                    self._on_error(stage, detail)
        except queue.Empty:
            pass
        self.after(100, self._poll_progress)

    def _on_done(self, output_path: Path) -> None:
        self.progress_bar.set(1.0)
        self.stage_label.configure(text=f"✓ Hoàn tất: {output_path.name}")
        self._log(f"\n=== HOÀN TẤT ===\nFile output: {output_path}\n")
        self.start_btn.configure(state="normal", text="▶  Bắt đầu lồng tiếng")
        if messagebox.askyesno(
            "Hoàn tất",
            f"Đã ghi file:\n{output_path}\n\nMở thư mục chứa file?",
        ):
            _open_in_explorer(output_path)

    def _on_error(self, stage: str, detail: str) -> None:
        self.stage_label.configure(text=f"✗ {stage}")
        self._log(f"\n=== LỖI: {stage} ===\n{detail}\n")
        self.start_btn.configure(state="normal", text="▶  Bắt đầu lồng tiếng")
        messagebox.showerror(stage, detail)

    def _log(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")


# ─── Helpers ─────────────────────────────────────────────────────────
def _human_size(path: Path) -> str:
    try:
        n = path.stat().st_size
    except OSError:
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _open_in_explorer(path: Path) -> None:
    folder = str(path.parent)
    try:
        if platform.system() == "Windows":
            os.startfile(folder)  # noqa: SIM115
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])
    except OSError:
        pass
