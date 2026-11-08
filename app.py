"""VietTranscribe — compact Windows 11-style UI, CPU transcription to TXT."""
from __future__ import annotations

import json
import os
import queue
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from transcription import atomic_write, fingerprint, job_directory, transcribe_file

MODELS = ("tiny", "base", "small", "medium", "large-v3")
MODEL_DESCRIPTIONS = {
    "tiny": ("Nhanh nhất", "Nhẹ nhất; dễ nhận dạng sai hoặc bỏ sót từ."),
    "base": ("Rất nhanh", "Phù hợp file rõ tiếng; có thể nhầm thuật ngữ."),
    "small": ("Cân bằng · khuyên dùng", "Phù hợp phiên âm tiếng Việt trên CPU."),
    "medium": ("Chậm", "Thường chính xác hơn, đổi lại tốn CPU và RAM."),
    "large-v3": ("Chậm nhất", "Mô hình lớn, rất nặng khi chỉ dùng CPU."),
}
MODEL_LABELS = {key: f"{key} — {value[0]}" for key, value in MODEL_DESCRIPTIONS.items()}
LABEL_TO_MODEL = {value: key for key, value in MODEL_LABELS.items()}
MODE_LABELS = {
    "fast": "Nhanh · beam 1",
    "balanced": "Cân bằng · beam 3",
    "accurate": "Chính xác hơn · beam 5",
}
LABEL_TO_MODE = {value: key for key, value in MODE_LABELS.items()}

BG = "#F5F7FB"
WHITE = "#FFFFFF"
INK = "#17263C"
MUTED = "#62748A"
BLUE = "#2563EB"
BORDER = "#DFE6F0"
GREEN = "#15803D"
ORANGE = "#A66308"


def clock(seconds):
    if seconds is None:
        return "--:--"
    seconds = max(0, round(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02}:{secs:02}" if hours else f"{minutes:02}:{secs:02}"


class VietTranscribe(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        # Normalize CustomTkinter sizes on Windows with 125%-200% DPI scaling.
        ctk.set_widget_scaling(1.0)
        ctk.set_window_scaling(1.0)
        super().__init__()
        self.title("VietTranscribe | Chuyển âm thanh thành TXT")
        self.geometry("920x710")
        self.minsize(720, 550)
        self.configure(fg_color=BG)
        self.sources = []
        self.row_widgets = {}
        self.file_states = {}
        self.selected = None
        self.current_file = None
        self.last_result = None
        self.queue_path = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "VietTranscribe" / "queue.json"
        self.destination = tk.StringVar(value=str(Path.home() / "Desktop" / "KetQuaPhienAm"))
        self.model = tk.StringVar(value="small")
        self.speed_mode = tk.StringVar(value="balanced")
        self.language = tk.StringVar(value="vi")
        self.vad = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Sẵn sàng · thêm file để bắt đầu")
        self.metrics = tk.StringVar(value="Tốc độ: --    ·    Còn lại: --:--")
        self.percent = tk.StringVar(value="0%")
        self.events = queue.Queue()
        self.cancel_event = threading.Event()
        self.busy = False
        self.logs_visible = False
        self.started_at = None
        self.last_progress_at = None
        self.current_stage = ""
        self.current_speed = 0.0
        self.current_eta = None
        self.build_ui()
        self.enable_drag_drop()
        self.restore_queue()
        self.protocol("WM_DELETE_WINDOW", self.close_window)
        self.after(150, self.poll)

    def text(self, parent, label="", size=13, color=INK, weight="normal", **kwargs):
        return ctk.CTkLabel(parent, text=label, font=("Segoe UI", size, weight),
                            text_color=color, **kwargs)

    def card(self, parent):
        return ctk.CTkFrame(parent, fg_color=WHITE, corner_radius=14,
                            border_width=1, border_color=BORDER)

    def build_ui(self):
        # The main view scrolls when the taskbar or screen scaling reduces usable height.
        # Keep the main controls reachable even on 1366x768 displays.
        self.outer = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                             corner_radius=0)
        self.outer.pack(fill="both", expand=True, padx=12, pady=8)

        header = ctk.CTkFrame(self.outer, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))
        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left")
        self.text(left, "VietTranscribe", 25, INK, "bold").pack(anchor="w")
        self.text(left, "Chọn file  →  Phiên âm  →  Lấy văn bản TXT", 12, MUTED).pack(anchor="w")
        badge = ctk.CTkFrame(header, fg_color="#E9F2FF", corner_radius=10)
        badge.pack(side="right", pady=10)
        self.text(badge, "CPU  ·  Offline sau lần tải đầu", 11, BLUE, "bold").pack(padx=12, pady=7)

        self.files_card = self.card(self.outer)
        self.files_card.pack(fill="x", pady=(0, 12))
        line = ctk.CTkFrame(self.files_card, fg_color="transparent")
        line.pack(fill="x", padx=17, pady=(14, 8))
        self.text(line, "Danh sách ghi âm", 15, INK, "bold").pack(side="left")
        self.file_count = self.text(line, "0 file", 12, MUTED)
        self.file_count.pack(side="left", padx=12)
        self.add_button = ctk.CTkButton(line, text="+ Thêm file", command=self.add_files,
                                         width=112, height=34, corner_radius=9)
        self.add_button.pack(side="right")
        self.file_area = ctk.CTkScrollableFrame(self.files_card, fg_color="#F9FBFE",
                                                corner_radius=9, height=72)
        self.file_area.pack(fill="x", padx=16, pady=(0, 8))
        self.empty_label = self.text(self.file_area,
                                     "Kéo thả file vào đây hoặc nhấn “+ Thêm file”",
                                     12, MUTED)
        self.empty_label.pack(pady=16)
        row = ctk.CTkFrame(self.files_card, fg_color="transparent")
        row.pack(fill="x", padx=17, pady=(0, 13))
        self.remove_button = ctk.CTkButton(row, text="Xóa file đã chọn", width=128,
                                            height=28, command=self.remove_files,
                                            fg_color="transparent", text_color=MUTED,
                                            hover_color="#EEF3F9")
        self.remove_button.pack(side="left")
        self.clear_button = ctk.CTkButton(row, text="Xóa tất cả", width=87, height=28,
                                           command=self.clear_files, fg_color="transparent",
                                           text_color=MUTED, hover_color="#EEF3F9")
        self.clear_button.pack(side="left")

        self.settings_card = self.card(self.outer)
        self.settings_card.pack(fill="x", pady=(0, 12))
        self.text(self.settings_card, "Thiết lập phiên âm", 15, INK, "bold").pack(
            anchor="w", padx=18, pady=(13, 10))
        opts = ctk.CTkFrame(self.settings_card, fg_color="transparent")
        opts.pack(fill="x", padx=18)
        opts.grid_columnconfigure(0, weight=1)
        opts.grid_columnconfigure(1, weight=1)
        self.text(opts, "Mô hình AI", 12, MUTED).grid(row=0, column=0, sticky="w")
        self.text(opts, "Chế độ xử lý", 12, MUTED).grid(row=0, column=1, sticky="w", padx=(12, 0))
        self.model_box = ctk.CTkOptionMenu(opts, values=list(MODEL_LABELS.values()),
                                            height=36, corner_radius=8, fg_color="#EEF3F9",
                                            button_color="#E0E9F4", button_hover_color="#D1DDEB",
                                            text_color=INK, command=self.change_model)
        self.model_box.grid(row=1, column=0, sticky="ew", pady=(4, 0), padx=(0, 7))
        self.model_box.set(MODEL_LABELS["small"])
        self.speed_box = ctk.CTkOptionMenu(opts, values=list(MODE_LABELS.values()),
                                            height=36, corner_radius=8, fg_color="#EEF3F9",
                                            button_color="#E0E9F4", button_hover_color="#D1DDEB",
                                            text_color=INK, command=self.change_mode)
        self.speed_box.grid(row=1, column=1, sticky="ew", pady=(4, 0), padx=(12, 0))
        self.speed_box.set(MODE_LABELS["balanced"])
        self.model_help = self.text(self.settings_card, MODEL_DESCRIPTIONS["small"][1], 11, MUTED)
        self.model_help.pack(anchor="w", padx=18, pady=(7, 0))
        small = ctk.CTkFrame(self.settings_card, fg_color="transparent")
        small.pack(fill="x", padx=18, pady=(9, 13))
        self.vad_box = ctk.CTkCheckBox(small, text="Lọc khoảng im lặng", variable=self.vad,
                                       font=("Segoe UI", 12), text_color=INK,
                                       width=158, command=self.save_queue)
        self.vad_box.pack(side="left")
        self.text(small, "Tiếng Việt · đoạn 10 phút · có lưu tiến độ", 11, MUTED).pack(side="right")

        self.progress_card = self.card(self.outer)
        self.progress_card.pack(fill="x", pady=(0, 12))
        row = ctk.CTkFrame(self.progress_card, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(13, 7))
        self.text(row, "Tiến độ", 15, INK, "bold").pack(side="left")
        self.text(row, "", 17, BLUE, "bold", textvariable=self.percent).pack(side="right")
        self.progress = ctk.CTkProgressBar(self.progress_card, height=11, corner_radius=7,
                                            fg_color="#E7ECF4", progress_color=BLUE)
        self.progress.pack(fill="x", padx=18, pady=5)
        self.progress.set(0)
        self.text(self.progress_card, "", 12, INK, textvariable=self.status, anchor="w").pack(
            fill="x", padx=18, pady=(6, 0))
        self.text(self.progress_card, "", 11, MUTED, textvariable=self.metrics).pack(
            anchor="w", padx=18, pady=(4, 12))

        action = ctk.CTkFrame(self.outer, fg_color="transparent")
        action.pack(fill="x", pady=(0, 10))
        self.start_button = ctk.CTkButton(action, text="▶  BẮT ĐẦU / TIẾP TỤC",
                                           height=43, width=220, corner_radius=10,
                                           command=self.start, font=("Segoe UI", 13, "bold"))
        self.start_button.pack(side="left")
        self.stop_button = ctk.CTkButton(action, text="Dừng sau đoạn này",
                                          height=43, width=155, corner_radius=10,
                                          command=self.stop, state="disabled",
                                          fg_color="#E9EDF4", text_color=INK,
                                          hover_color="#DCE5F0")
        self.stop_button.pack(side="left", padx=10)
        self.open_txt_button = ctk.CTkButton(action, text="Mở TXT",
                                              height=43, width=100, corner_radius=10,
                                              state="disabled", command=self.open_txt,
                                              fg_color="#DCFCE7", hover_color="#BBF7D0",
                                              text_color=GREEN)
        self.open_txt_button.pack(side="right")

        foot = ctk.CTkFrame(self.outer, fg_color="transparent")
        foot.pack(fill="x")
        self.folder_button = ctk.CTkButton(foot, text="📁  Chọn thư mục kết quả",
                                            height=30, width=185,
                                            command=self.choose_folder,
                                            fg_color="transparent", text_color=BLUE,
                                            hover_color="#E7F0FF")
        self.folder_button.pack(side="left")
        self.folder_label = self.text(foot, "", 11, MUTED)
        self.folder_label.pack(side="left", padx=5, fill="x", expand=True)
        self.update_folder_label()
        self.logs_button = ctk.CTkButton(foot, text="Chi tiết xử lý ▾", height=30,
                                          width=126, command=self.toggle_logs,
                                          fg_color="transparent", text_color=MUTED,
                                          hover_color="#EDF2F8")
        self.logs_button.pack(side="right")
        self.log_panel = ctk.CTkFrame(self.outer, fg_color=WHITE, corner_radius=12)
        self.log_box = ctk.CTkTextbox(self.log_panel, height=110, wrap="word",
                                       fg_color="#F8FAFC", text_color=INK,
                                       font=("Consolas", 11))
        self.log_box.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_box.configure(state="disabled")

    def toggle_logs(self):
        self.logs_visible = not self.logs_visible
        if self.logs_visible:
            self.log_panel.pack(fill="x", pady=(8, 0))
        else:
            self.log_panel.pack_forget()
        self.logs_button.configure(text="Ẩn chi tiết ▴" if self.logs_visible else "Chi tiết xử lý ▾")

    def log(self, content):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", str(content) + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def update_folder_label(self):
        self.folder_label.configure(text=self.destination.get())

    def refresh_files(self):
        for widget in self.file_area.winfo_children():
            widget.destroy()
        self.row_widgets = {}
        self.file_count.configure(text=f"{len(self.sources)} file")
        # Never reserve hundreds of empty pixels for one short row.
        self.file_area.configure(height=max(72, min(len(self.sources), 4) * 45 + 26))
        if not self.sources:
            self.empty_label = self.text(self.file_area,
                "Kéo thả file vào đây hoặc nhấn “+ Thêm file”", 12, MUTED)
            self.empty_label.pack(pady=16)
            self.selected = None
            return
        if self.selected not in self.sources:
            self.selected = self.sources[0]
        for index, path in enumerate(self.sources):
            selected = self.selected == path
            line = ctk.CTkFrame(self.file_area,
                                fg_color="#EAF2FF" if selected else WHITE,
                                corner_radius=9, height=40,
                                border_width=1,
                                border_color="#B7D2FC" if selected else BORDER)
            line.pack(fill="x", padx=3, pady=3)
            line.grid_columnconfigure(0, weight=1)
            display = f"{index+1:02}.  {path.name}"
            name = ctk.CTkButton(line, text=display, anchor="w", height=38,
                                  fg_color="transparent", hover_color="#E5EFFC",
                                  text_color=INK, font=("Segoe UI", 12),
                                  command=lambda p=path: self.select_file(p))
            name.grid(row=0, column=0, padx=5, sticky="ew")
            status = self.file_states.get(path, "Chờ xử lý")
            tone = GREEN if status == "Hoàn thành" else BLUE if status == "Đang xử lý" else ORANGE if status == "Lỗi" else MUTED
            badge = self.text(line, status, 11, tone)
            badge.grid(row=0, column=1, padx=10)
            result_btn = ctk.CTkButton(line, text="TXT", width=44, height=27,
                                        fg_color="#E3F7EB", text_color=GREEN,
                                        hover_color="#C5EAD2",
                                        command=lambda p=path: self.open_txt(p))
            result_btn.grid(row=0, column=2, padx=(0, 8))
            self.row_widgets[path] = (line, badge)
        self.refresh_open_button()

    def select_file(self, path):
        self.selected = path
        self.refresh_files()

    def result_path(self, source):
        if not source or not source.is_file():
            return None
        try:
            settings = fingerprint(source, self.model.get(), self.language.get(),
                                   self.vad.get(), self.speed_mode.get())
            result = job_directory(source, Path(self.destination.get()), settings) / "van_ban_day_du.txt"
            return result if result.is_file() else None
        except (OSError, ValueError):
            return None

    def refresh_open_button(self):
        result = self.result_path(self.selected)
        self.open_txt_button.configure(state="normal" if result else "disabled")

    def open_txt(self, source=None):
        source = source if isinstance(source, Path) else self.selected
        result = self.result_path(source)
        if result is None:
            messagebox.showinfo("Chưa có TXT", "File chưa phiên âm xong với cấu hình hiện tại.")
            return
        try:
            os.startfile(str(result))
        except OSError as exc:
            messagebox.showerror("Không thể mở TXT", str(exc))

    def change_model(self, label):
        key = LABEL_TO_MODEL.get(label, "small")
        self.model.set(key)
        self.model_help.configure(text=MODEL_DESCRIPTIONS[key][1])
        self.save_queue()
        self.refresh_open_button()

    def change_mode(self, label):
        self.speed_mode.set(LABEL_TO_MODE.get(label, "balanced"))
        self.save_queue()
        self.refresh_open_button()

    def save_queue(self):
        state = {
            "files": [str(x) for x in self.sources],
            "destination": self.destination.get(), "model": self.model.get(),
            "mode": self.speed_mode.get(), "language": self.language.get(),
            "vad": self.vad.get(),
        }
        try:
            atomic_write(self.queue_path, json.dumps(state, ensure_ascii=False))
        except OSError as exc:
            self.log("Không lưu được danh sách file: " + str(exc))

    def restore_queue(self):
        try:
            data = json.loads(self.queue_path.read_text(encoding="utf-8-sig"))
            for value in data.get("files", []):
                path = Path(value)
                if path.is_file() and path not in self.sources:
                    self.sources.append(path)
            if data.get("destination"):
                self.destination.set(data["destination"])
            model = data.get("model")
            if model in MODELS:
                self.model.set(model)
                self.model_box.set(MODEL_LABELS[model])
                self.model_help.configure(text=MODEL_DESCRIPTIONS[model][1])
            mode = data.get("mode")
            if mode in MODE_LABELS:
                self.speed_mode.set(mode)
                self.speed_box.set(MODE_LABELS[mode])
            if data.get("language") in ("vi", "auto", "en"):
                self.language.set(data["language"])
            self.vad.set(bool(data.get("vad", True)))
        except (OSError, ValueError, TypeError, KeyError):
            pass
        self.refresh_files()
        self.update_folder_label()

    def enable_drag_drop(self):
        """Enable native Windows file drops if tkdnd is available."""
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD
            TkinterDnD.DnDWrapper._require(self)
            TkinterDnD.DnDWrapper.drop_target_register(self, DND_FILES)
            TkinterDnD.DnDWrapper.dnd_bind(self, "<<Drop>>", self.on_drop)
            self.log("Kéo thả file vào cửa sổ đã sẵn sàng.")
        except Exception as exc:
            self.log("Kéo thả không khả dụng; vẫn có thể chọn file: " + str(exc))

    def on_drop(self, event):
        try:
            paths = self.tk.splitlist(event.data)
            self.append_files(paths)
        except (tk.TclError, OSError, ValueError) as exc:
            self.log("Không đọc được file kéo thả: " + str(exc))

    def append_files(self, paths):
        if self.busy:
            self.log("Đang phiên âm, không thể thêm file vào hàng đợi lúc này.")
            return
        allowed = {".m4a", ".mp3", ".wav", ".flac", ".mp4",
                   ".ogg", ".aac", ".wma", ".mkv"}
        existing = {str(p).casefold() for p in self.sources}
        for value in paths:
            path = Path(value).resolve()
            if path.is_file() and path.suffix.lower() in allowed and str(path).casefold() not in existing:
                self.sources.append(path)
                existing.add(str(path).casefold())
        self.refresh_files()
        self.save_queue()

    def add_files(self):
        selected = filedialog.askopenfilenames(
            title="Chọn file âm thanh",
            filetypes=[("Audio / Video", "*.m4a *.mp3 *.wav *.flac *.mp4 *.ogg *.aac *.wma *.mkv"),
                       ("Tất cả", "*.*")])
        self.append_files(selected)

    def remove_files(self):
        if self.selected is not None and self.selected in self.sources:
            self.sources.remove(self.selected)
            self.file_states.pop(self.selected, None)
        self.refresh_files()
        self.save_queue()

    def clear_files(self):
        self.sources.clear()
        self.file_states.clear()
        self.refresh_files()
        self.save_queue()

    def choose_folder(self):
        folder = filedialog.askdirectory(title="Chọn thư mục lưu kết quả")
        if folder:
            self.destination.set(folder)
            self.update_folder_label()
            self.refresh_open_button()
            self.save_queue()

    def open_folder(self):
        try:
            folder = Path(self.destination.get())
            folder.mkdir(parents=True, exist_ok=True)
            os.startfile(str(folder))
        except OSError as exc:
            messagebox.showerror("Không mở được thư mục", str(exc))

    def set_busy(self, busy):
        self.busy = busy
        for item in (self.add_button, self.remove_button, self.clear_button,
                     self.start_button, self.model_box, self.speed_box, self.vad_box,
                     self.folder_button):
            item.configure(state="disabled" if busy else "normal")
        self.stop_button.configure(state="normal" if busy else "disabled")

    def start(self):
        if self.busy:
            return
        if not self.sources:
            messagebox.showwarning("Chưa có file", "Hãy thêm ít nhất một file ghi âm.")
            return
        if any(not path.is_file() for path in self.sources):
            messagebox.showwarning("Thiếu file", "Một số file không còn tồn tại, hãy kiểm tra danh sách.")
            return
        if not self.destination.get().strip():
            messagebox.showwarning("Thiếu thư mục", "Hãy chọn thư mục lưu kết quả.")
            return
        self.save_queue()
        self.cancel_event.clear()
        self.file_states = {path: "Chờ xử lý" for path in self.sources}
        self.set_busy(True)
        self.refresh_files()
        self.progress.set(0)
        self.percent.set("0%")
        self.started_at = time.monotonic()
        self.last_progress_at = self.started_at
        self.current_speed = 0.0
        self.current_eta = None
        self.current_stage = "Đang chuẩn bị mô hình AI..."
        self.metrics.set("Tốc độ: -- · Đã chạy: 00:00 · Còn lại: --:--")
        self.status.set(self.current_stage)
        args = (list(self.sources), Path(self.destination.get()),
                self.model.get(), self.language.get(), self.vad.get(), self.speed_mode.get())
        threading.Thread(target=self.worker, args=args, daemon=True).start()

    def stop(self):
        self.cancel_event.set()
        self.stop_button.configure(state="disabled")
        self.status.set("Đang dừng sau đoạn hiện tại...")

    def worker(self, files, destination, model, language, vad, mode):
        try:
            from faster_whisper import WhisperModel
            self.events.put({"type": "log", "message": f"Mô hình {model} · {MODE_LABELS[mode]} · CPU"})
            engine = WhisperModel(model, device="cpu", compute_type="int8")
            failed = 0
            for i, path in enumerate(files, 1):
                if self.cancel_event.is_set():
                    break
                self.events.put({"type": "file", "path": path,
                                 "state": "Đang xử lý", "number": i, "total": len(files)})
                self.events.put({"type": "log", "message": f"[{i}/{len(files)}] {path.name}"})
                self.events.put({"type": "progress", "percent": 0, "speed": 0, "eta": None})
                try:
                    result = transcribe_file(
                        path, destination, engine, model, language, vad,
                        self.cancel_event, self.events.put, mode=mode
                    )
                    if result is not None:
                        self.events.put({"type": "file", "path": path, "state": "Hoàn thành",
                                         "number": i, "total": len(files)})
                        self.events.put({"type": "log", "message": f"Đã lưu: {result}"})
                    else:
                        self.events.put({"type": "file", "path": path, "state": "Tạm dừng",
                                         "number": i, "total": len(files)})
                except Exception as exc:
                    failed += 1
                    self.events.put({"type": "file", "path": path, "state": "Lỗi",
                                     "number": i, "total": len(files)})
                    self.events.put({"type": "log", "message": f"LỖI {path.name}: {exc}"})
            state = "stopped" if self.cancel_event.is_set() else "done_with_errors" if failed else "done"
            self.events.put({"type": state, "failures": failed})
        except Exception as exc:
            self.events.put({"type": "error", "message": f"{type(exc).__name__}: {exc}"})

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event["type"]
                if kind == "log":
                    self.log(event["message"])
                elif kind == "file":
                    path = event["path"]
                    self.current_file = path
                    self.file_states[path] = event["state"]
                    self.current_stage = f'File {event["number"]}/{event["total"]}: {path.name} · {event["state"]}'
                    self.status.set(self.current_stage)
                    self.refresh_files()
                elif kind == "stage":
                    self.current_stage = event["message"]
                    self.status.set(self.current_stage)
                elif kind == "progress":
                    val = max(0, min(100, float(event["percent"])))
                    self.progress.set(val / 100)
                    self.percent.set(f"{val:.1f}%")
                    self.current_speed = float(event["speed"])
                    self.current_eta = event["eta"]
                    self.last_progress_at = time.monotonic()
                else:
                    self.set_busy(False)
                    self.refresh_open_button()
                    if kind == "done":
                        self.status.set("Đã xử lý xong tất cả file.")
                        messagebox.showinfo("Hoàn thành", "Đã xử lý xong hàng đợi. Chọn file và nhấn Mở TXT.")
                    elif kind == "stopped":
                        self.status.set("Đã dừng. Các đoạn đã lưu vẫn còn.")
                        self.log("Nhấn Bắt đầu / Tiếp tục để xử lý các đoạn còn lại.")
                    elif kind == "done_with_errors":
                        self.status.set("Đã xử lý hàng đợi, một số file gặp lỗi.")
                        messagebox.showwarning("Có file lỗi", f'{event["failures"]} file bị lỗi. Xem Chi tiết xử lý.')
                    else:
                        self.status.set("Không thể hoàn tất.")
                        self.log(event["message"])
                        messagebox.showerror("Lỗi phiên âm", event["message"])
        except queue.Empty:
            pass
        if self.busy and self.started_at is not None:
            now = time.monotonic()
            elapsed = clock(now - self.started_at)
            eta = clock(self.current_eta)
            self.metrics.set(
                f"Tốc độ: {self.current_speed:.2f}x · Đã chạy: {elapsed} · "
                f"Còn lại (ước tính): {eta}"
            )
            # The counter continues even if Whisper hasn't returned the next speech
            # segment. Percentage only advances after actual model progress.
            if self.last_progress_at and now - self.last_progress_at > 25:
                self.status.set(self.current_stage +
                    " · Đang tính toán, chưa có mốc âm thanh mới")
        self.after(150, self.poll)

    def close_window(self):
        if self.busy and not messagebox.askyesno(
            "Đang phiên âm",
            "Đóng ngay sẽ ngắt đoạn hiện tại. Các đoạn đã lưu vẫn được giữ. Bạn muốn đóng?"
        ):
            return
        self.cancel_event.set()
        self.save_queue()
        self.destroy()


if __name__ == "__main__":
    VietTranscribe().mainloop()
