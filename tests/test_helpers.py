import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import transcription as t
from app import clock


class Model:
    def __init__(self, stop=None):
        self.calls = 0
        self.stop = stop

    def transcribe(self, audio, **kwargs):
        self.calls += 1
        if self.stop is not None and self.calls == 1:
            self.stop.set()
        return iter([SimpleNamespace(start=3.0, end=4.0,
                                     text=f"Đoạn {self.calls}")]), None


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "bài học.m4a"
        self.source.write_bytes(b"fake audio")
        self.results = self.root / "results"
        self.fake = [(i, float(i*600), [1.0, 2.0]) for i in range(3)]

    def run_job(self, model, stop=None):
        with patch.object(t, "iter_chunks", return_value=iter(self.fake)), \
             patch.object(t, "duration_chunks", return_value=3):
            return t.transcribe_file(
                self.source, self.results, model, "small", "vi", True,
                stop if stop is not None else threading.Event(), lambda x: None
            )

    def test_pause_resume_skip_completed_chunks(self):
        stop = threading.Event()
        first = Model(stop)
        self.assertIsNone(self.run_job(first, stop))
        self.assertEqual(first.calls, 1)
        self.assertEqual(len(list(self.results.rglob("parts/00000.txt"))), 1)
        second = Model()
        final = self.run_job(second)
        self.assertEqual(second.calls, 2)
        self.assertTrue(final.is_file())
        self.assertEqual(len(final.read_text(encoding="utf-8-sig").splitlines()), 3)
        again = Model()
        self.assertEqual(self.run_job(again), final)
        self.assertEqual(again.calls, 0)

    def test_corrupted_saved_part_is_recomputed(self):
        final = self.run_job(Model())
        folder = final.parent
        manifest_file = folder / "manifest.json"
        manifest = json.loads(manifest_file.read_text(encoding="utf-8-sig"))
        manifest["complete"] = False
        t.atomic_write(manifest_file, json.dumps(manifest))
        part = folder / "parts" / "00001.txt"
        part.write_text("CORRUPTED", encoding="utf-8")
        next_model = Model()
        self.run_job(next_model)
        self.assertEqual(next_model.calls, 1)
        self.assertNotIn("CORRUPTED", final.read_text(encoding="utf-8-sig"))

    def test_no_filename_collision(self):
        other = self.root / "sub" / self.source.name
        other.parent.mkdir()
        other.write_bytes(b"different")
        one = t.job_directory(self.source, self.results,
                              t.fingerprint(self.source, "small", "vi", True))
        two = t.job_directory(other, self.results,
                              t.fingerprint(other, "small", "vi", True))
        self.assertNotEqual(one, two)

    def test_merge_excludes_gaps(self):
        settings = t.fingerprint(self.source, "small", "vi", True)
        folder = t.job_directory(self.source, self.results, settings)
        manifest = t.read_manifest(folder, settings)
        t.save_part(folder, manifest, 0, "Đầu tiên\n")
        t.save_part(folder, manifest, 2, "Thứ ba\n")
        output = t.combine(folder, manifest, 3)
        self.assertEqual(output.read_text(encoding="utf-8-sig"), "Đầu tiên\n")

    def test_overlap_filters_earlier_segment(self):
        items = [SimpleNamespace(start=0, end=1, text="Lặp lại"),
                 SimpleNamespace(start=3, end=4, text="Mới")]
        self.assertEqual(t.render_segments(items, 600, 1), "Mới\n")

    def test_speed_modes_and_model_labels(self):
        from app import MODEL_DESCRIPTIONS, MODEL_LABELS, MODE_LABELS, LABEL_TO_MODE
        self.assertEqual(tuple(MODEL_DESCRIPTIONS), ("tiny", "base", "small", "medium", "large-v3"))
        self.assertIn("Nhanh nhất", MODEL_LABELS["tiny"])
        self.assertIn("Chậm nhất", MODEL_LABELS["large-v3"])
        self.assertIn("khuyên dùng", MODEL_LABELS["small"])
        self.assertEqual(LABEL_TO_MODE[MODE_LABELS["balanced"]], "balanced")
        self.assertEqual({mode: t.beam_size_for(mode)
                          for mode in ("fast", "balanced", "accurate")},
                         {"fast": 1, "balanced": 3, "accurate": 5})

    def test_checkpoint_separation_by_mode(self):
        paths = {}
        for mode in ("fast", "balanced", "accurate"):
            settings = t.fingerprint(self.source, "small", "vi", True, mode)
            paths[mode] = t.job_directory(self.source, self.results, settings)
        self.assertEqual(len(set(paths.values())), 3)
        self.assertNotEqual(paths["fast"], paths["balanced"])

    def test_beam_size_passed_to_engine(self):
        seen = []
        class CaptureModel:
            def transcribe(self, audio, **kwargs):
                seen.append(kwargs["beam_size"])
                return iter([SimpleNamespace(start=3.0, end=4.0, text="An toàn")]), None
        for mode in ("fast", "balanced", "accurate"):
            with patch.object(t, "iter_chunks", return_value=iter(self.fake[:1])), \
                 patch.object(t, "duration_chunks", return_value=1):
                t.transcribe_file(self.source, self.results, CaptureModel(),
                                  "small", "vi", True, threading.Event(),
                                  lambda event: None, mode=mode)
        self.assertEqual(seen, [1, 3, 5])

    def test_unicode_atomic_write_and_clock(self):
        path = self.root / "a.txt"
        t.atomic_write(path, "Lái xe an toàn")
        self.assertEqual(path.read_text(encoding="utf-8-sig"), "Lái xe an toàn")
        self.assertEqual(clock(3700), "1:01:40")


if __name__ == "__main__":
    unittest.main()
