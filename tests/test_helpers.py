import unittest
from app import timestamp, human_time, report_metrics

class HelperTests(unittest.TestCase):
    def test_timestamp(self):
        self.assertEqual(timestamp(560.36), "00:09:20.360")

    def test_human_time(self):
        self.assertEqual(human_time(90), "01:30")
        self.assertEqual(human_time(3700), "1:01:40")

    def test_percent_and_speed(self):
        percent, speed, eta = report_metrics(600, 1800, 1200)
        self.assertAlmostEqual(percent, 33.333333, places=4)
        self.assertAlmostEqual(speed, 0.5)
        self.assertAlmostEqual(eta, 2400)

    def test_unknown_duration(self):
        self.assertEqual(report_metrics(0, 0, 10), (0.0, 0.0, None))

    def test_progress_is_capped(self):
        percent, _, eta = report_metrics(1900, 1800, 100)
        self.assertEqual(percent, 100)
        self.assertEqual(eta, 0)

if __name__ == "__main__":
    unittest.main()
