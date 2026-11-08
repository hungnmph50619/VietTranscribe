"""VietTranscribe: lightweight Vietnamese offline speech-to-text Windows GUI."""
from __future__ import annotations

import os
import queue
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

MODELS = ("tiny", "base", "small", "medium", "large-v3")


def timestamp(seconds: float) -> str:
    millis = max(0, round(seconds * 1000))
    hh, millis = divmod(millis, 3_600_000)
    mm, millis = divmod(millis, 60_000)
    ss, millis = divmod(millis, 1000)
    return f"{hh:02}:{mm:02}:{ss:02}.{millis:03}"


def human_time(seconds: float) -> str:
    if seconds < 0 or seconds == float("inf"):
        return "--:--"
    seconds = int(seconds + .5)
    hours, remaining = divmod(seconds, 3600)
    minutes, secs = divmod(remaining, 60)
    return f"{hours}:{minutes:02}:{secs:02}" if hours else f"{minutes:02}:{secs:02}"


def report_metrics(processed: float, total: float, elapsed: float):
    """Returns percentage, processing speed, and estimated remaining wall time."""
    if total <= 0:
        return 0.0, 0.0, None
    processed = max(0.0, min(processed, total))
    percentage = processed / total * 100
    speed = processed / elapsed if elapsed > 0 else 0.0
    remaining = max(0.0, total - processed) / speed if speed > 0 else None
    return percentage, speed, remaining


class VietTranscribe(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("VietTranscribe | Chuyển âm thanh thành văn bản")
        self.geometry("800x580")
        self.minsize(680, 520)
        self.file = tk.StringVar()
        self.destination = tk.StringVar(value=str(Path.home() / "Desktop" / "KetQuaPhienAm"))
        self.model = tk.StringVar(value="small")
        self.language = tk.StringVar(value="vi")
        self.vad = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Sẵn sàng")
        self.progress_text = tk.StringVar(value="0%")
        self.speed_text = tk.StringVar(value="Tốc độ: --")
        self.eta_text = tk.StringVar(value="Còn lại: --:--")
        self.messages = queue.Queue()
        self.stop_event = threading.Event()
        self.busy = False
        self.setup_ui()
        self.protocol("WM_DELETE_WINDOW", self.close_window)
        self.after(150, self.poll)

    def setup_ui(self):
        frame = ttk.Frame(self, padding=22)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="VietTranscribe", font=("Segoe UI", 23, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Phiên âm M4A, MP3, WAV, MP4, FLAC thành văn bản TXT").pack(anchor="w", pady=(3, 22))

        ttk.Label(frame, text="1. File âm thanh hoặc video").pack(anchor="w")
        line = ttk.Frame(frame)
        line.pack(fill="x", pady=(5, 16))
        ttk.Entry(line, textvariable=self.file).pack(side="left", fill="x", expand=True)
        ttk.Button(line, text="Chọn file...", command=self.choose_file).pack(side="right", padx=(7, 0))

        ttk.Label(frame, text="2. Thư mục lưu kết quả").pack(anchor="w")
        line = ttk.Frame(frame)
        line.pack(fill="x", pady=(5, 16))
        ttk.Entry(line, textvariable=self.destination).pack(side="left", fill="x", expand=True)
        ttk.Button(line, text="Chọn thư mục...", command=self.choose_destination).pack(side="right", padx=(7, 0))

        line = ttk.Frame(frame)
        line.pack(fill="x")
        ttk.Label(line, text="Mô hình AI").pack(side="left")
        ttk.Combobox(line, textvariable=self.model, values=MODELS, width=12, state="readonly").pack(side="left", padx=(8, 20))
        ttk.Label(line, text="Ngôn ngữ").pack(side="left")
        ttk.Combobox(line, textvariable=self.language, values=("vi", "auto", "en"), width=9, state="readonly").pack(side="left", padx=8)
        ttk.Checkbutton(frame, text="Lọc khoảng im lặng (VAD)", variable=self.vad).pack(anchor="w", pady=(10, 12))

        line = ttk.Frame(frame)
        line.pack(fill="x")
        self.run_btn = ttk.Button(line, text="BẮT ĐẦU PHIÊN ÂM", command=self.start_job)
        self.run_btn.pack(side="left")
        self.stop_btn = ttk.Button(line, text="DỪNG VÀ GIỮ VĂN BẢN", command=self.stop_job, state="disabled")
        self.stop_btn.pack(side="left", padx=8)
        ttk.Button(line, text="Mở thư mục kết quả", command=self.open_destination).pack(side="left")

        metrics = ttk.Frame(frame)
        metrics.pack(fill="x", pady=(19, 3))
        ttk.Label(metrics, textvariable=self.progress_text).pack(side="left")
        ttk.Label(metrics, textvariable=self.eta_text).pack(side="right", padx=(14, 0))
        ttk.Label(metrics, textvariable=self.speed_text).pack(side="right")
        self.progress = ttk.Progressbar(frame, mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(5, 10))
        ttk.Label(frame, textvariable=self.status).pack(anchor="w")

        ttk.Label(frame, text="Nhật ký", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(15, 5))
        self.log_widget = tk.Text(frame, height=8, wrap="word", state="disabled")
        self.log_widget.pack(fill="both", expand=True)
        ttk.Label(frame, text="Tự lưu sau mỗi đoạn vào .partial.txt; TXT chính thức xuất khi hoàn tất.").pack(anchor="w", pady=(8, 0))

    def choose_file(self):
        selected = filedialog.askopenfilename(
            title="Chọn file", filetypes=[
                ("Âm thanh / Video", "*.m4a *.mp3 *.wav *.mp4 *.flac *.ogg *.aac *.wma *.mkv"),
                ("Tất cả", "*.*")])
        if selected:
            self.file.set(selected)

    def choose_destination(self):
        selected = filedialog.askdirectory(title="Chọn thư mục kết quả")
        if selected:
            self.destination.set(selected)

    def open_destination(self):
        try:
            folder = Path(self.destination.get().strip())
            folder.mkdir(parents=True, exist_ok=True)
            os.startfile(str(folder))
        except OSError as exc:
            messagebox.showerror("Lỗi thư mục", str(exc))

    def log(self, message):
        self.log_widget.configure(state="normal")
        self.log_widget.insert("end", message + "\n")
        self.log_widget.see("end")
        self.log_widget.configure(state="disabled")

    def start_job(self):
        if self.busy:
            return
        source = Path(self.file.get().strip())
        folder = Path(self.destination.get().strip())
        if not source.is_file():
            messagebox.showwarning("Thiếu file", "Hãy chọn một file âm thanh hợp lệ.")
            return
        if not self.destination.get().strip():
            messagebox.showwarning("Thiếu thư mục", "Hãy chọn thư mục lưu kết quả.")
            return
        partial = folder / (source.stem + ".partial.txt")
        if partial.exists() and not messagebox.askyesno(
            "Văn bản đang lưu", f"Đã có {partial.name}.\nBắt đầu lại sẽ ghi đè bản nháp cũ. Tiếp tục?"
        ):
            return
        self.stop_event.clear()
        self.busy = True
        self.run_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress["value"] = 0
        self.progress_text.set("0%")
        self.speed_text.set("Tốc độ: --")
        self.eta_text.set("Còn lại: --:--")
        self.status.set("Đang chuẩn bị mô hình AI...")
        self.log(f"Đang xử lý: {source.name} | {self.model.get()} | {self.language.get()}")
        threading.Thread(
            target=self.transcribe,
            args=(source, folder, self.model.get(), self.language.get(), self.vad.get()),
            daemon=True
        ).start()

    def stop_job(self):
        if not self.busy:
            return
        self.stop_event.set()
        self.stop_btn.configure(state="disabled")
        self.status.set("Đang dừng sau đoạn nhận dạng hiện tại...")
        self.log("Đã yêu cầu dừng. File .partial.txt vẫn được giữ lại.")

    def close_window(self):
        if self.busy:
            if not messagebox.askyesno(
                "Đang phiên âm",
                "Đang xử lý. Đóng cửa sổ có thể dừng ngay lập tức.\n"
                "Phần đã ghi trong .partial.txt vẫn còn. Bạn muốn đóng?"
            ):
                return
            self.stop_event.set()
        self.destroy()

    def transcribe(self, source, folder, model, language, use_vad):
        partial = folder / (source.stem + ".partial.txt")
        final = folder / (source.stem + ".txt")
        processed_segments = 0
        try:
            from faster_whisper import WhisperModel
            folder.mkdir(parents=True, exist_ok=True)
            self.messages.put(("log", "Đang tải mô hình AI (lần đầu cần Internet)..."))
            engine = WhisperModel(model, device="cpu", compute_type="int8")
            if self.stop_event.is_set():
                self.messages.put(("stopped", f"Đã dừng trước khi nhận dạng; chưa ghi văn bản."))
                return
            self.messages.put(("log", "Đã tải mô hình. Đang phân tích âm thanh..."))
            segments, info = engine.transcribe(
                str(source), language=None if language == "auto" else language,
                beam_size=5, vad_filter=use_vad
            )
            duration = float(info.duration)
            start = time.monotonic()
            # utf-8-sig writes the BOM once; each flush keeps the partial file readable.
            with partial.open("w", encoding="utf-8-sig") as writer:
                for segment in segments:
                    if self.stop_event.is_set():
                        break
                    text = segment.text.strip()
                    if text:
                        writer.write(text + "\n")
                        writer.flush()
                        processed_segments += 1
                    elapsed = max(time.monotonic() - start, .001)
                    percentage, speed, eta = report_metrics(segment.end, duration, elapsed)
                    self.messages.put(("progress", {
                        "percent": percentage, "processed": float(segment.end),
                        "duration": duration, "speed": speed, "eta": eta
                    }))
                writer.flush()
            if self.stop_event.is_set():
                self.messages.put(("stopped", f"Đã dừng. Lưu được {processed_segments} đoạn tại: {partial}"))
                return
            if processed_segments == 0:
                self.messages.put(("error", "Không phát hiện lời nói. Thử tắt VAD hoặc chọn file khác."))
                return
            os.replace(partial, final)
            self.messages.put(("done", f"Hoàn thành {processed_segments} đoạn. File TXT: {final}"))
        except Exception as exc:
            self.messages.put(("error", f"{type(exc).__name__}: {exc}\n"
                                        f"Nếu đã ghi nhận dạng, bản nháp nằm tại: {partial}"))

    def poll(self):
        try:
            while True:
                action, message = self.messages.get_nowait()
                if action == "log":
                    self.log(message)
                elif action == "progress":
                    self.progress["value"] = message["percent"]
                    self.progress_text.set(f'{message["percent"]:.1f}%')
                    self.speed_text.set(f'Tốc độ: {message["speed"]:.2f}x')
                    self.eta_text.set(
                        "Còn lại: " + (human_time(message["eta"]) if message["eta"] is not None else "--:--")
                    )
                    self.status.set(
                        f'Đã xử lý tới {timestamp(message["processed"])} / {timestamp(message["duration"])}'
                    )
                else:
                    self.busy = False
                    self.run_btn.configure(state="normal")
                    self.stop_btn.configure(state="disabled")
                    if action == "done":
                        self.progress["value"] = 100
                        self.progress_text.set("100%")
                    self.status.set("Hoàn thành" if action == "done" else
                                    "Đã dừng" if action == "stopped" else "Có lỗi")
                    self.log(message)
                    if action == "done":
                        messagebox.showinfo("Thành công", message)
                    elif action == "stopped":
                        messagebox.showinfo("Đã dừng", message)
                    else:
                        messagebox.showerror("Lỗi phiên âm", message)
        except queue.Empty:
            pass
        self.after(150, self.poll)


if __name__ == "__main__":
    VietTranscribe().mainloop()
