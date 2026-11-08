"""Chunked resumable transcription; bounded RAM, atomic UTF-8 checkpoints."""
from __future__ import annotations
import hashlib
import json
import math
import os
import re
import time
from pathlib import Path

RATE = 16000
CHUNK_SECONDS = 600
OVERLAP_SECONDS = 2
SPEED_MODES = {"fast": 1, "balanced": 3, "accurate": 5}


def beam_size_for(mode: str) -> int:
    if mode not in SPEED_MODES:
        raise ValueError("Chế độ phiên âm không hợp lệ: " + str(mode))
    return SPEED_MODES[mode]



def atomic_write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".writing")
    try:
        with tmp.open("w", encoding="utf-8-sig", newline="\n") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def fingerprint(path: Path, model: str, language: str, vad: bool,
                mode: str = "balanced") -> dict:
    beam_size_for(mode)
    stat = path.stat()
    return {"version": 3, "source": str(path.resolve()),
            "size": stat.st_size, "mtime_ns": stat.st_mtime_ns,
            "model": model, "language": language, "vad": vad,
            "mode": mode, "beam_size": beam_size_for(mode),
            "chunk_seconds": CHUNK_SECONDS, "overlap_seconds": OVERLAP_SECONDS}


def job_directory(path: Path, root: Path, settings: dict) -> Path:
    token = hashlib.sha256(json.dumps(settings, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", path.stem).strip(" .")[:70] or "audio"
    return root / (stem + "__" + token)


def read_manifest(folder: Path, settings: dict) -> dict:
    file = folder / "manifest.json"
    if file.exists():
        data = json.loads(file.read_text(encoding="utf-8-sig"))
        if data.get("settings") != settings:
            raise ValueError("Checkpoint không khớp file gốc / cấu hình.")
        return data
    data = {"settings": settings, "chunks": {}}
    atomic_write(file, json.dumps(data, ensure_ascii=False, indent=2))
    return data


def read_part(folder: Path, manifest: dict, i: int):
    record = manifest["chunks"].get(str(i))
    if not isinstance(record, dict):
        return None
    try:
        content = (folder / "parts" / f"{i:05}.txt").read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return None
    checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return content if record.get("sha256") == checksum else None


def save_part(folder: Path, manifest: dict, i: int, content: str):
    atomic_write(folder / "parts" / f"{i:05}.txt", content)
    manifest["chunks"][str(i)] = {"sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()}
    atomic_write(folder / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))


def combine(folder: Path, manifest: dict, count: int, complete=False) -> Path:
    items = []
    for i in range(count):
        part = read_part(folder, manifest, i)
        if part is None:
            break
        if part.strip():
            items.append(part.strip())
    output = folder / ("van_ban_day_du.txt" if complete else "van_ban_dang_xu_ly.partial.txt")
    atomic_write(output, "\n".join(items) + ("\n" if items else ""))
    return output


def duration_chunks(path: Path) -> int:
    try:
        import av
        with av.open(str(path)) as container:
            audio = next((s for s in container.streams if s.type == "audio"), None)
            if audio is None:
                return 0
            if audio.duration is not None and audio.time_base:
                duration = float(audio.duration * audio.time_base)
            elif container.duration:
                duration = container.duration / 1000000
            else:
                return 0
        return max(1, math.ceil(duration / CHUNK_SECONDS))
    except Exception:
        return 0


def iter_chunks(path: Path, chunk_seconds=CHUNK_SECONDS, overlap_seconds=OVERLAP_SECONDS):
    """Decode incrementally. Each iteration holds <= 10 min + 2 sec PCM."""
    import av
    import numpy as np
    target = RATE * chunk_seconds
    overlap = RATE * overlap_seconds
    if target <= overlap or target <= 0 or overlap < 0:
        raise ValueError("Kích thước đoạn không hợp lệ.")
    container = av.open(str(path))
    try:
        audio = next((s for s in container.streams if s.type == "audio"), None)
        if audio is None:
            raise ValueError("File không có luồng âm thanh.")
        converter = av.AudioResampler(format="s16", layout="mono", rate=RATE)
        pieces, size, idx = [], 0, 0

        def add(samples):
            nonlocal pieces, size, idx
            pos = 0
            while pos < len(samples):
                remaining = target + (overlap if idx else 0) - size
                n = min(remaining, len(samples) - pos)
                if n <= 0:
                    raise RuntimeError("Không thể chia âm thanh.")
                pieces.append(samples[pos:pos+n])
                pos += n
                size += n
                if size == target + (overlap if idx else 0):
                    data = np.concatenate(pieces)
                    yield idx, float(idx * chunk_seconds), data
                    idx += 1
                    pieces = [data[-overlap:].copy()] if overlap else []
                    size = overlap if overlap else 0

        def consume(frame):
            for resampled in converter.resample(frame):
                data = resampled.to_ndarray().reshape(-1).astype(np.float32) / 32768.0
                yield from add(data)

        for frame in container.decode(audio):
            yield from consume(frame)
        yield from consume(None)
        if size > (overlap if idx else 0):
            yield idx, float(idx * chunk_seconds), np.concatenate(pieces)
    finally:
        container.close()


def render_segments(segments, nominal_start: float, index: int) -> str:
    """Discard leading overlap segments whose midpoint belongs to prior chunk."""
    offset = max(0, nominal_start - (OVERLAP_SECONDS if index else 0))
    lines = []
    for segment in segments:
        midpoint = offset + (segment.start + segment.end) / 2
        if midpoint + 0.000001 >= nominal_start and segment.text.strip():
            lines.append(segment.text.strip())
    return "\n".join(lines) + ("\n" if lines else "")


def transcribe_file(source: Path, root: Path, engine, model: str,
                    language: str, vad: bool, cancel, emit,
                    mode: str = "balanced") -> Path | None:
    """Resume verified parts; None means stopped. All file writes are atomic."""
    settings = fingerprint(source, model, language, vad, mode)
    folder = job_directory(source, root, settings)
    manifest = read_manifest(folder, settings)
    final = folder / "van_ban_day_du.txt"
    if manifest.get("complete") and final.is_file():
        emit({"type": "log", "message": "Đã hoàn thành trước đây: " + str(final)})
        emit({"type": "progress", "percent": 100, "speed": 0, "eta": 0})
        return final
    estimate = duration_chunks(source)
    begin = time.monotonic()
    fresh, completed = 0, 0
    processed_new_seconds = 0.0
    for index, start, samples in iter_chunks(source):
        if cancel.is_set():
            combine(folder, manifest, max(index+1, estimate), False)
            return None
        previous = read_part(folder, manifest, index)
        if previous is None:
            emit({"type": "log", "message": f"Đang phiên âm đoạn {index+1}/{estimate or '?'}..."})
            emit({"type": "stage", "message": f"Đang nhận dạng đoạn {index+1}/{estimate or '?'}"})
            chunk_audio_seconds = len(samples) / RATE
            overlap = OVERLAP_SECONDS if index else 0
            chunk_new_seconds = max(0.0, chunk_audio_seconds - overlap)
            last_audio_seconds = 0.0

            def tracked_segments(segments):
                nonlocal last_audio_seconds
                for segment in segments:
                    # Whisper yields speech segments progressively. This is genuine
                    # decoded audio progress, not a timer-based percentage.
                    current = min(chunk_new_seconds, max(
                        last_audio_seconds, float(segment.end) - overlap))
                    if current > last_audio_seconds:
                        last_audio_seconds = current
                        elapsed = max(0.001, time.monotonic() - begin)
                        audio_done = min(start + current,
                                         max((index + 1) * CHUNK_SECONDS, estimate * CHUNK_SECONDS))
                        total = max((index + 1) * CHUNK_SECONDS, estimate * CHUNK_SECONDS)
                        speed = (processed_new_seconds + current) / elapsed
                        remaining = max(0.0, total - audio_done)
                        emit({"type": "progress",
                              "percent": min(99.0, audio_done / total * 100),
                              "speed": speed,
                              "eta": remaining / speed if speed > 0 else None})
                    yield segment

            try:
                segments, _ = engine.transcribe(
                    samples, language=None if language == "auto" else language,
                    beam_size=beam_size_for(mode), vad_filter=vad)
                content = render_segments(tracked_segments(segments), start, index)
            except Exception:
                combine(folder, manifest, max(index+1, estimate), False)
                raise
            # Persist only completed chunks. Partial inference never overwrites them.
            save_part(folder, manifest, index, content)
            fresh += 1
            processed_new_seconds += chunk_new_seconds
        else:
            emit({"type": "log", "message": f"Đã có checkpoint đoạn {index+1}, bỏ qua."})
        emit({"type": "stage", "message": f"Đã lưu xong đoạn {index+1}/{estimate or '?'}"})
        completed = index + 1
        combine(folder, manifest, max(completed, estimate), False)
        elapsed = max(.001, time.monotonic() - begin)
        speed = processed_new_seconds / elapsed
        total_seconds = max(completed, estimate) * CHUNK_SECONDS
        processed_seconds = completed * CHUNK_SECONDS
        emit({"type": "progress", "percent": min(99, processed_seconds / total_seconds * 100),
              "speed": speed, "eta": (total_seconds-processed_seconds)/speed if speed else None})
    if cancel.is_set():
        combine(folder, manifest, max(estimate, completed), False)
        return None
    if completed == 0 or any(read_part(folder, manifest, i) is None for i in range(completed)):
        raise RuntimeError("Phiên âm chưa có đủ các đoạn để hoàn tất.")
    final = combine(folder, manifest, completed, True)
    manifest["complete"] = True
    manifest["total_chunks"] = completed
    atomic_write(folder / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    emit({"type": "progress", "percent": 100, "speed": 0, "eta": 0})
    return final
