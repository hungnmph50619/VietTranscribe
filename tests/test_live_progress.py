import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import transcription as t


class SizedAudio:
    def __len__(self):
        return 600 * t.RATE


class SpeechModel:
    def transcribe(self, audio, **kwargs):
        def segments():
            yield SimpleNamespace(start=0.0, end=60.0, text="Phần một")
            yield SimpleNamespace(start=60.0, end=180.0, text="Phần hai")
            yield SimpleNamespace(start=180.0, end=599.0, text="Phần ba")
        return segments(), None


class LiveProgressTests(unittest.TestCase):
    def test_percent_changes_within_single_ten_minute_chunk(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "audio.m4a"
            source.write_bytes(b"synthetic")
            events = []
            with patch.object(t, "iter_chunks", return_value=iter([(0, 0.0, SizedAudio())])), \
                 patch.object(t, "duration_chunks", return_value=3):
                result = t.transcribe_file(
                    source, root / "out", SpeechModel(), "small", "vi", True,
                    threading.Event(), events.append)
            self.assertIsNotNone(result)
            self.assertTrue(result.is_file())
            progress = [ev["percent"] for ev in events if ev["type"] == "progress"]
            self.assertGreaterEqual(len(progress), 4)
            self.assertGreater(progress[0], 0)
            self.assertLess(progress[0], 33.34)
            self.assertLess(progress[0], progress[1])
            self.assertLess(progress[1], progress[2])
            self.assertEqual(progress[-1], 100)

    def test_progress_does_not_change_checkpoint_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "audio.m4a"
            source.write_bytes(b"recording")
            initial = t.fingerprint(source, "small", "vi", True, "balanced")
            self.assertEqual(initial["version"], 3)
            self.assertEqual(initial["chunk_seconds"], 600)


if __name__ == "__main__":
    unittest.main()
