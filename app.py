"""VietTranscribe - Windows GUI for resumable, queued audio transcription."""
from __future__ import annotations

import os
import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from transcription import transcribe_file

MODELS = ("tiny", "base", "small", "medium", "large-v3")


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
        self.geometry("820x630")
        self.minsize(670, 510)
        self.sources = []
        self.destination = tk.StringVar(value=str(Path.home() / "Desktop" / "KetQuaPhienAm"))
        self.model = tk.StringVar(value="small")
        self.language = tk.StringVar(value="vi")
        self.vad = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Sẵn sàng")
        self.metrics = tk.StringVar(value="0% | Tốc độ: -- | Còn lại: --:--")
        self.events = queue.Queue()
        self.cancel_event = threading.Event()
        self.busy = False
        self.build_ui()
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
        self.model_box = ttk.Combobox(row, textvariable=self.model, values=MODELS, state="readonly", width=12)
        self.model_box.pack(side="left", padx=(7, 20))
        ttk.Label(row, text="Ngôn ngữ").pack(side="left")
        self.lang_box = ttk.Combobox(row, textvariable=self.language, values=("vi", "auto", "en"),
                                     state="readonly", width=9)
        self.lang_box.pack(side="left", padx=(7, 20))
        self.vad_box = ttk.Checkbutton(row, text="Lọc im lặng (VAD)", variable=self.vad)
        self.vad_box.pack(side="left")
        ttk.Label(root, text="Chia đoạn: 10 phút · Xử lý trên CPU · Có lưu checkpoint").pack(anchor="w", pady=(8, 12))

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

    def remove_files(self):
        for index in reversed(self.file_list.curselection()):
            del self.sources[index]
            self.file_list.delete(index)

    def clear_files(self):
        self.sources.clear()
        self.file_list.delete(0, "end")

    def choose_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.destination.set(path)

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
        self.cancel_event.clear()
        self.set_busy(True)
        self.progress["value"] = 0
        self.metrics.set("0% | Tốc độ: -- | Còn lại: --:--")
        self.status.set("Đang chuẩn bị mô hình AI...")
        threading.Thread(target=self.worker, daemon=True,
            args=(list(self.sources), Path(self.destination.get().strip()), self.model.get(),
                  self.language.get(), self.vad.get())).start()

    def stop(self):
        self.cancel_event.set()
        self.stop_button.config(state="disabled")
        self.status.set("Đang chờ đoạn hiện tại hoàn thành để dừng...")

    def worker(self, files, destination, model, language, vad):
        try:
            from faster_whisper import WhisperModel
            self.events.put({"type": "log", "message": "Đang tải mô hình AI..."})
            engine = WhisperModel(model, device="cpu", compute_type="int8")
            for i, file in enumerate(files, 1):
                if self.cancel_event.is_set():
                    break
                self.events.put({"type": "status", "message": f"File {i}/{len(files)}: {file.name}"})
                self.events.put({"type": "progress", "percent": 0, "speed": 0, "eta": None})
                self.events.put({"type": "log", "message": f"[{i}/{len(files)}] {file.name}"})
                result = transcribe_file(file, destination, engine, model, language, vad,
                                         self.cancel_event, self.events.put)
                if result is not None:
                    self.events.put({"type": "log", "message": "Đã lưu: " + str(result)})
            self.events.put({"type": "stopped" if self.cancel_event.is_set() else "done"})
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
                                    "Đã dừng, giữ dữ liệu" if kind == "stopped" else "Có lỗi")
                    if kind == "error":
                        self.log(event["message"])
                        messagebox.showerror("Lỗi", event["message"])
                    elif kind == "done":
                        messagebox.showinfo("Hoàn thành", "Đã xử lý hàng đợi. Mở thư mục kết quả để lấy TXT.")
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
        self.destroy()


if __name__ == "__main__":
    VietTranscribe().mainloop()
