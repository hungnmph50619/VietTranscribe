import unittest
from app import MODEL_DESCRIPTIONS, MODEL_LABELS, LABEL_TO_MODEL, MODE_LABELS, LABEL_TO_MODE, clock

class UiConfigurationTests(unittest.TestCase):
    def test_all_models_have_speed_and_description(self):
        self.assertEqual(tuple(MODEL_DESCRIPTIONS), ("tiny", "base", "small", "medium", "large-v3"))
        for model, label in MODEL_LABELS.items():
            self.assertEqual(LABEL_TO_MODEL[label], model)
            self.assertTrue(MODEL_DESCRIPTIONS[model][1])

    def test_speed_mode_labels_roundtrip(self):
        self.assertEqual(set(MODE_LABELS), {"fast", "balanced", "accurate"})
        for mode, label in MODE_LABELS.items():
            self.assertEqual(LABEL_TO_MODE[label], mode)

    def test_clock(self):
        self.assertEqual(clock(None), "--:--")
        self.assertEqual(clock(120), "02:00")

if __name__ == "__main__":
    unittest.main()
