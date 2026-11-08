"""VietTranscribe - Vietnamese offline speech-to-text Windows GUI."""
from __future__ import annotations

import json
import os
import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

MODELS = ("tiny", "base", "small", "medium", "large-v3")


def timestamp(seconds: float, srt: bool = False) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3600000)
    minutes, milliseconds = divmod(milliseconds, 60000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    separator = "," if srt else "."
    return f"{hours:02}:{minutes:02}:{seconds:02}{separator}{milliseconds:03}"


def export_files(source: Path, folder: Path, segments: list, language: str):
    folder.mkdir(parents=True, exist_ok=True)
    base = folder / source.stem
    base.with_suffix(".txt").write_text(
        "\n".join(item["text"] for item in segments) + "\n", encoding="utf-8-sig"
    )
    with base.with_suffix(".srt").open("w", encoding="utf-8-sig") as f:
        for i, item in enumerate(segments, 1):
            f.write(f'{i}\n{timestamp(item["start"], True)} --> {timestamp(item["end"], True)}\n{item["text"]}\n\n')
    with base.with_suffix(".vtt").open("w", encoding="utf-8-sig") as f:
        f.write("WEBVTT\n\n")
        for item in segments:
            f.write(f'{timestamp(item["start"])} --> {timestamp(item["end"])}\n{item["text"]}\n\n')
    base.with_suffix(".json").write_text(
        json.dumps({"source": source.name, "language": language, "segments": segments},
                   ensure_ascii=False, indent=2), encoding="utf-8"
    )


class VietTranscribe(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("VietTranscribe | Chuyển âm thanh thành văn bản")
        self.geometry("790x560")
        self.minsize(650, 480)
        self.file = tk.StringVar()
        self.destination = tk.StringVar(value=str(Path.home() / "Desktop" / "KetQuaPhienAm"))
        self.model = tk.StringVar(value="small")
        self.language = tk.StringVar(value="vi")
        self.vad = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Sẵn sàng")
        self.messages = queue.Queue()
        self.busy = False
        self.setup_ui()
        self.after(150, self.poll)

    def setup_ui(self):
        frame = ttk.Frame(self, padding=22)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="VietTranscribe", font=("Segoe UI", 23, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Phiên âm M4A, MP3, WAV, MP4, FLAC sang TXT / SRT / VTT / JSON").pack(anchor="w", pady=(3, 22))
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
        ttk.Button(line, text="Mở thư mục kết quả", command=self.open_destination).pack(side="left", padx=10)
        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.pack(fill="x", pady=(17, 8))
        ttk.Label(frame, textvariable=self.status).pack(anchor="w")
        ttk.Label(frame, text="Nhật ký", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(15, 5))
        self.log_widget = tk.Text(frame, height=8, wrap="word", state="disabled")
        self.log_widget.pack(fill="both", expand=True)
        ttk.Label(frame, text="Lần đầu cần Internet để tải mô hình; những lần sau có thể chạy offline.").pack(anchor="w", pady=(8, 0))

    def choose_file(self):
        selected = filedialog.askopenfilename(
            title="Chọn file",
            filetypes=[("Âm thanh / Video", "*.m4a *.mp3 *.wav *.mp4 *.flac *.ogg *.aac *.wma *.mkv"),
                       ("Tất cả", "*.*")]
        )
        if selected:
            self.file.set(selected)

    def choose_destination(self):
        selected = filedialog.askdirectory(title="Chọn thư mục kết quả")
        if selected:
            self.destination.set(selected)

    def open_destination(self):
        folder = Path(self.destination.get().strip())
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(str(folder))

    def log(self, message: str):
        self.log_widget.configure(state="normal")
        self.log_widget.insert("end", message + "\n")
        self.log_widget.see("end")
        self.log_widget.configure(state="disabled")

    def start_job(self):
        if self.busy:
            return
        file = Path(self.file.get().strip())
        if not file.is_file():
            messagebox.showwarning("Thiếu file", "Hãy chọn một file âm thanh hợp lệ.")
            return
        if not self.destination.get().strip():
            messagebox.showwarning("Thiếu thư mục", "Hãy chọn thư mục lưu kết quả.")
            return
        self.busy = True
        self.run_btn.configure(state="disabled")
        self.progress.start(12)
        self.status.set("Đang phiên âm...")
        self.log(f"Đang xử lý: {file.name} | {self.model.get()} | {self.language.get()}")
        threading.Thread(
            target=self.transcribe,
            args=(file, Path(self.destination.get().strip()), self.model.get(),
                  self.language.get(), self.vad.get()), daemon=True
        ).start()

    def transcribe(self, source, folder, model, language, use_vad):
        try:
            from faster_whisper import WhisperModel
            self.messages.put(("log", "Đang tải mô hình AI (lần đầu cần Internet)..."))
            engine = WhisperModel(model, device="cpu", compute_type="int8")
            segments, info = engine.transcribe(
                str(source), language=None if language == "auto" else language,
                beam_size=5, vad_filter=use_vad
            )
            result = []
            for i, segment in enumerate(segments, 1):
                text = segment.text.strip()
                if text:
                    result.append({"start": round(segment.start, 3),
                                   "end": round(segment.end, 3), "text": text})
                if i % 5 == 0:
                    self.messages.put(("status", f"Đã xử lý tới {timestamp(segment.end)}"))
            if not result:
                raise RuntimeError("Không phát hiện lời nói. Thử tắt VAD hoặc chọn file khác.")
            export_files(source, folder, result, info.language)
            self.messages.put(("done", f"Hoàn thành {len(result)} đoạn. Kết quả: {folder}"))
        except Exception as exc:
            self.messages.put(("error", f"{type(exc).__name__}: {exc}"))

    def poll(self):
        try:
            while True:
                action, message = self.messages.get_nowait()
                if action == "log":
                    self.log(message)
                elif action == "status":
                    self.status.set(message)
                else:
                    self.busy = False
                    self.run_btn.configure(state="normal")
                    self.progress.stop()
                    self.status.set("Hoàn thành" if action == "done" else "Có lỗi")
                    self.log(message)
                    if action == "done":
                        messagebox.showinfo("Thành công", message)
                    else:
                        messagebox.showerror("Lỗi phiên âm", message)
        except queue.Empty:
            pass
        self.after(150, self.poll)


if __name__ == "__main__":
    VietTranscribe().mainloop()
