"""VietTranscribe - Windows GUI for resumable, queued audio transcription."""
from __future__ import annotations

import json
import os
import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from transcription import atomic_write, transcribe_file

MODELS = ("tiny", "base", "small", "medium", "large-v3")
MODEL_DESCRIPTIONS = {
    "tiny": ("Nhanh nhất", "Nhẹ nhất; độ chính xác thấp hơn, dễ bỏ sót từ."),
    "base": ("Rất nhanh", "Phù hợp ghi âm rõ tiếng; có thể nhầm thuật ngữ."),
    "small": ("Cân bằng — khuyên dùng", "Cân bằng chất lượng tiếng Việt và tốc độ CPU."),
    "medium": ("Chậm", "Thường nhận dạng tốt hơn, nhưng dùng nhiều RAM và CPU."),
    "large-v3": ("Chậm nhất", "Mô hình lớn nhất trong danh sách; rất nặng với CPU."),
}
MODEL_LABELS = {key: f"{key} — {value[0]}" for key, value in MODEL_DESCRIPTIONS.items()}
LABEL_TO_MODEL = {label: key for key, label in MODEL_LABELS.items()}
MODE_LABELS = {
    "fast": "Nhanh — beam 1",
    "balanced": "Cân bằng — beam 3",
    "accurate": "Chính xác hơn — beam 5",
}
LABEL_TO_MODE = {label: key for key, label in MODE_LABELS.items()}



def clock(seconds):
    if seconds is None:
        return "--:--"
    seconds = max(0, round(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02}:{secs:02}" if hours else f"{minutes:02}:{secs:02}"


class VietTranscribe(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("VietTranscribe | Phiên âm file dài")
        self.geometry("850x700")
        self.minsize(700, 575)
        self.sources = []
        self.queue_path = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "VietTranscribe" / "queue.json"
        self.destination = tk.StringVar(value=str(Path.home() / "Desktop" / "KetQuaPhienAm"))
        self.model = tk.StringVar(value="small")
        self.model_label = tk.StringVar(value=MODEL_LABELS["small"])
        self.model_info = tk.StringVar(value=MODEL_DESCRIPTIONS["small"][1])
        self.speed_mode = tk.StringVar(value="balanced")
        self.speed_label = tk.StringVar(value=MODE_LABELS["balanced"])
        self.language = tk.StringVar(value="vi")
        self.vad = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Sẵn sàng")
        self.metrics = tk.StringVar(value="0% | Tốc độ: -- | Còn lại: --:--")
        self.events = queue.Queue()
        self.cancel_event = threading.Event()
        self.busy = False
        self.build_ui()
        self.restore_queue()
        self.protocol("WM_DELETE_WINDOW", self.close_window)
        self.after(150, self.poll)

    def build_ui(self):
        root = ttk.Frame(self, padding=20)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="VietTranscribe", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ttk.Label(root, text="Xử lý hàng đợi · chia đoạn 10 phút · tự tiếp tục · xuất TXT").pack(anchor="w", pady=(2, 16))
        ttk.Label(root, text="1. Các file âm thanh cần phiên âm").pack(anchor="w")
        area = ttk.Frame(root)
        area.pack(fill="both", expand=True, pady=(5, 8))
        self.file_list = tk.Listbox(area, selectmode="extended", height=7, font=("Segoe UI", 10))
        self.file_list.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(area, orient="vertical", command=self.file_list.yview)
        scroll.pack(side="right", fill="y")
        self.file_list.config(yscrollcommand=scroll.set)

        row = ttk.Frame(root)
        row.pack(fill="x", pady=(0, 12))
        self.add_button = ttk.Button(row, text="Thêm file...", command=self.add_files)
        self.add_button.pack(side="left")
        self.remove_button = ttk.Button(row, text="Xóa file đã chọn", command=self.remove_files)
        self.remove_button.pack(side="left", padx=8)
        self.clear_button = ttk.Button(row, text="Xóa danh sách", command=self.clear_files)
        self.clear_button.pack(side="left")

        ttk.Label(root, text="2. Thư mục xuất kết quả").pack(anchor="w")
        row = ttk.Frame(root)
        row.pack(fill="x", pady=(5, 13))
        ttk.Entry(row, textvariable=self.destination).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Chọn thư mục...", command=self.choose_folder).pack(side="right", padx=(7, 0))

        row = ttk.Frame(root)
        row.pack(fill="x")
        ttk.Label(row, text="Mô hình AI").pack(side="left")
        self.model_box = ttk.Combobox(row, textvariable=self.model_label,
                                      values=tuple(MODEL_LABELS.values()),
                                      state="readonly", width=31)
        self.model_box.pack(side="left", padx=(7, 15))
        self.model_box.bind("<<ComboboxSelected>>", self.change_model)
        ttk.Label(row, text="Ngôn ngữ").pack(side="left")
        self.lang_box = ttk.Combobox(row, textvariable=self.language, values=("vi", "auto", "en"),
                                     state="readonly", width=9)
        self.lang_box.pack(side="left", padx=(7, 10))
        self.vad_box = ttk.Checkbutton(row, text="Lọc im lặng (VAD)", variable=self.vad)
        self.vad_box.pack(side="left")
        ttk.Label(root, textvariable=self.model_info, foreground="#345b78").pack(anchor="w", pady=(6, 2))
        row = ttk.Frame(root)
        row.pack(fill="x", pady=(5, 2))
        ttk.Label(row, text="Chế độ xử lý").pack(side="left")
        self.speed_box = ttk.Combobox(row, textvariable=self.speed_label,
                                      values=tuple(MODE_LABELS.values()),
                                      state="readonly", width=27)
        self.speed_box.pack(side="left", padx=(8, 12))
        self.speed_box.bind("<<ComboboxSelected>>", self.change_mode)
        ttk.Label(row, text="Nhanh hơn có thể giảm độ chính xác.").pack(side="left")
        ttk.Label(root, text="Thứ tự thông thường: tiny > base > small > medium > large-v3 (CPU).").pack(anchor="w")
        ttk.Label(root, text="Chia đoạn: 10 phút · Xử lý trên CPU · Có lưu checkpoint").pack(anchor="w", pady=(5, 12))

        row = ttk.Frame(root)
        row.pack(fill="x")
        self.start_button = ttk.Button(row, text="BẮT ĐẦU / TIẾP TỤC", command=self.start)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(row, text="DỪNG SAU ĐOẠN HIỆN TẠI", command=self.stop,
                                      state="disabled")
        self.stop_button.pack(side="left", padx=8)
        ttk.Button(row, text="Mở thư mục kết quả", command=self.open_folder).pack(side="left")
        self.progress = ttk.Progressbar(root, mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(17, 5))
        ttk.Label(root, textvariable=self.metrics).pack(anchor="w")
        ttk.Label(root, textvariable=self.status).pack(anchor="w", pady=(6, 8))
        ttk.Label(root, text="Nhật ký", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.log_box = tk.Text(root, height=7, state="disabled", wrap="word", font=("Consolas", 9))
        self.log_box.pack(fill="both", expand=True, pady=(5, 7))
        ttk.Label(root, text="Đoạn hoàn thành được lưu ngay; TXT đầy đủ được ghép tự động.").pack(anchor="w")

    def change_model(self, _event=None):
        key = LABEL_TO_MODEL.get(self.model_label.get(), "small")
        self.model.set(key)
        self.model_info.set(MODEL_DESCRIPTIONS[key][1])
        self.save_queue()

    def change_mode(self, _event=None):
        self.speed_mode.set(LABEL_TO_MODE.get(self.speed_label.get(), "balanced"))
        self.save_queue()

    def save_queue(self):
        state = {"files": [str(f) for f in self.sources],
                 "destination": self.destination.get(),
                 "model": self.model.get(), "mode": self.speed_mode.get(),
                 "language": self.language.get(),
                 "vad": self.vad.get()}
        try:
            atomic_write(self.queue_path, json.dumps(state, ensure_ascii=False))
        except OSError as exc:
            self.log("Không lưu được hàng đợi: " + str(exc))

    def restore_queue(self):
        try:
            data = json.loads(self.queue_path.read_text(encoding="utf-8-sig"))
            for value in data.get("files", []):
                path = Path(value)
                if path.is_file() and path not in self.sources:
                    self.sources.append(path)
                    self.file_list.insert("end", f"{path.name} — {path.parent}")
            if data.get("destination"):
                self.destination.set(data["destination"])
            if data.get("model") in MODELS:
                key = data["model"]
                self.model.set(key)
                self.model_label.set(MODEL_LABELS[key])
                self.model_info.set(MODEL_DESCRIPTIONS[key][1])
            if data.get("mode") in MODE_LABELS:
                mode = data["mode"]
                self.speed_mode.set(mode)
                self.speed_label.set(MODE_LABELS[mode])
            if data.get("language") in ("vi", "auto", "en"):
                self.language.set(data["language"])
            self.vad.set(bool(data.get("vad", True)))
        except (OSError, ValueError, TypeError, KeyError):
            pass

    def add_files(self):
        selected = filedialog.askopenfilenames(title="Chọn nhiều file",
            filetypes=[("Audio / Video", "*.m4a *.mp3 *.wav *.flac *.mp4 *.ogg *.aac *.wma *.mkv"),
                       ("Tất cả", "*.*")])
        existing = {str(x).casefold() for x in self.sources}
        for item in selected:
            path = Path(item).resolve()
            if str(path).casefold() not in existing:
                self.sources.append(path)
                self.file_list.insert("end", f"{path.name} — {path.parent}")
                existing.add(str(path).casefold())
        self.save_queue()

    def remove_files(self):
        for index in reversed(self.file_list.curselection()):
            del self.sources[index]
            self.file_list.delete(index)
        self.save_queue()

    def clear_files(self):
        self.sources.clear()
        self.file_list.delete(0, "end")
        self.save_queue()

    def choose_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.destination.set(path)
            self.save_queue()

    def open_folder(self):
        try:
            path = Path(self.destination.get().strip())
            path.mkdir(parents=True, exist_ok=True)
            os.startfile(str(path))
        except OSError as error:
            messagebox.showerror("Không thể mở thư mục", str(error))

    def log(self, content):
        self.log_box.config(state="normal")
        self.log_box.insert("end", content + "\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    def set_busy(self, busy):
        self.busy = busy
        for control in (self.add_button, self.remove_button, self.clear_button, self.start_button, self.vad_box):
            control.config(state="disabled" if busy else "normal")
        self.model_box.config(state="disabled" if busy else "readonly")
        self.lang_box.config(state="disabled" if busy else "readonly")
        self.speed_box.config(state="disabled" if busy else "readonly")
        self.stop_button.config(state="normal" if busy else "disabled")

    def start(self):
        if self.busy:
            return
        if not self.sources:
            messagebox.showwarning("Chưa có file", "Hãy thêm ít nhất một file ghi âm.")
            return
        if any(not file.is_file() for file in self.sources):
            messagebox.showerror("Không tìm thấy file", "Một số file đã bị di chuyển hoặc xóa.")
            return
        if not self.destination.get().strip():
            messagebox.showwarning("Thiếu thư mục", "Hãy chọn thư mục xuất kết quả.")
            return
        self.save_queue()
        self.cancel_event.clear()
        self.set_busy(True)
        self.progress["value"] = 0
        self.metrics.set("0% | Tốc độ: -- | Còn lại: --:--")
        self.status.set("Đang chuẩn bị mô hình AI...")
        threading.Thread(target=self.worker, daemon=True,
            args=(list(self.sources), Path(self.destination.get().strip()), self.model.get(),
                  self.language.get(), self.vad.get(), self.speed_mode.get())).start()

    def stop(self):
        self.cancel_event.set()
        self.stop_button.config(state="disabled")
        self.status.set("Đang chờ đoạn hiện tại hoàn thành để dừng...")

    def worker(self, files, destination, model, language, vad, mode):
        try:
            from faster_whisper import WhisperModel
            self.events.put({"type": "log", "message": f"Cấu hình: {model} · {MODE_LABELS[mode]}"})
            self.events.put({"type": "log", "message": "Đang tải mô hình AI..."})
            engine = WhisperModel(model, device="cpu", compute_type="int8")
            failures = 0
            for i, file in enumerate(files, 1):
                if self.cancel_event.is_set():
                    break
                self.events.put({"type": "status", "message": f"File {i}/{len(files)}: {file.name}"})
                self.events.put({"type": "progress", "percent": 0, "speed": 0, "eta": None})
                self.events.put({"type": "log", "message": f"[{i}/{len(files)}] {file.name}"})
                try:
                    result = transcribe_file(file, destination, engine, model, language, vad,
                                             self.cancel_event, self.events.put, mode=mode)
                    if result is not None:
                        self.events.put({"type": "log", "message": "Đã lưu: " + str(result)})
                except Exception as exc:
                    self.events.put({"type": "log", "message": f"LỖI {file.name}: {exc}"})
                    # A bad file must not stop the rest of the queue.
                    failures += 1
                    continue
            event = "stopped" if self.cancel_event.is_set() else ("done_with_errors" if failures else "done")
            self.events.put({"type": event, "failures": failures})
        except Exception as error:
            self.events.put({"type": "error", "message": f"{type(error).__name__}: {error}"})

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event["type"]
                if kind == "log":
                    self.log(event["message"])
                elif kind == "status":
                    self.status.set(event["message"])
                elif kind == "progress":
                    self.progress["value"] = event["percent"]
                    self.metrics.set(f"{event['percent']:.1f}% | Tốc độ: {event['speed']:.2f}x | "
                                     f"Còn lại (ước tính): {clock(event['eta'])}")
                else:
                    self.set_busy(False)
                    self.status.set("Hoàn thành" if kind == "done" else
                                    "Một số file bị lỗi" if kind == "done_with_errors" else
                                    "Đã dừng, giữ dữ liệu" if kind == "stopped" else "Có lỗi")
                    if kind == "error":
                        self.log(event["message"])
                        messagebox.showerror("Lỗi", event["message"])
                    elif kind == "done":
                        messagebox.showinfo("Hoàn thành", "Đã xử lý hàng đợi. Mở thư mục kết quả để lấy TXT.")
                    elif kind == "done_with_errors":
                        messagebox.showwarning("Có file lỗi", f"{event['failures']} file bị lỗi. Xem nhật ký; các file khác vẫn được xử lý.")
                    else:
                        self.log("Có thể nhấn BẮT ĐẦU / TIẾP TỤC để xử lý các đoạn còn lại.")
        except queue.Empty:
            pass
        self.after(150, self.poll)

    def close_window(self):
        if self.busy and not messagebox.askyesno(
            "Đang xử lý", "Đóng ngay sẽ ngắt đoạn hiện tại, các đoạn đã lưu vẫn được giữ. Tiếp tục?"
        ):
            return
        self.cancel_event.set()
        self.save_queue()
        self.destroy()


if __name__ == "__main__":
    VietTranscribe().mainloop()
