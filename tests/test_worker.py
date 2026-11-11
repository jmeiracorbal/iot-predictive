import io
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "iotlink" / "worker"))
from worker import generate_batch, publish, settings


CONFIG = {
    "IOTLINK_MASTER_URL": "http://iotlink-master:1880/api/v1/measurements",
    "IOTLINK_GENERATION_INTERVAL_SECONDS": "5",
    "IOTLINK_HTTP_TIMEOUT_SECONDS": "5",
    "IOTLINK_RUN_ONCE": "false",
}


class SettingsTests(unittest.TestCase):
    def test_configuration(self):
        cfg = settings(CONFIG)
        self.assertEqual(cfg["url"], CONFIG["IOTLINK_MASTER_URL"])
        self.assertEqual(cfg["interval"], 5.0)
        self.assertFalse(cfg["once"])

    def test_explicit_endpoint(self):
        cfg = settings({
            **CONFIG,
            "IOTLINK_MASTER_URL": "http://192.168.1.40/api/v1/measurements",
        })
        self.assertEqual(cfg["url"], "http://192.168.1.40/api/v1/measurements")

    def test_missing_variable(self):
        with self.assertRaisesRegex(ValueError, "IOTLINK_MASTER_URL is required"):
            settings({k: v for k, v in CONFIG.items() if k != "IOTLINK_MASTER_URL"})

    def test_bad_interval(self):
        with self.assertRaises(ValueError):
            settings({**CONFIG, "IOTLINK_GENERATION_INTERVAL_SECONDS": "0"})

    def test_bad_boolean(self):
        with self.assertRaises(ValueError):
            settings({**CONFIG, "IOTLINK_RUN_ONCE": "sometimes"})


class GeneratorTests(unittest.TestCase):
    def test_measures_two_motors(self):
        now = datetime(2026, 11, 11, 10, 0, tzinfo=timezone.utc)
        data = generate_batch(1, now)
        self.assertEqual(data["schema_version"], "1.0")
        self.assertEqual(len(data["readings"]), 2)
        self.assertEqual(data["readings"][0]["device_id"], "motor-01")
        self.assertIn("vibration_mm_s", data["readings"][1]["values"])
        self.assertTrue(data["readings"][0]["timestamp"].endswith("+00:00"))

    def test_progressive_motor_fault(self):
        first = generate_batch(1)["readings"][1]["values"]["vibration_mm_s"]
        last = generate_batch(100)["readings"][1]["values"]["vibration_mm_s"]
        self.assertGreater(last, first)

    def test_sequence_must_be_positive(self):
        with self.assertRaises(ValueError):
            generate_batch(0)


class ApiTests(unittest.TestCase):
    @patch("worker.urlopen")
    def test_post_and_acknowledgement(self, mocked_urlopen):
        payload = generate_batch(1)
        response = io.BytesIO(b'{"accepted":2}')
        response.status = 202
        mocked_urlopen.return_value.__enter__.return_value = response
        accepted = publish(CONFIG["IOTLINK_MASTER_URL"], payload, 5.0)
        self.assertEqual(accepted, 2)

        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(json.loads(request.data)["schema_version"], "1.0")

    @patch("worker.urlopen")
    def test_incomplete_acknowledgement(self, mocked_urlopen):
        response = io.BytesIO(b'{"accepted":1}')
        response.status = 202
        mocked_urlopen.return_value.__enter__.return_value = response
        with self.assertRaisesRegex(ValueError, "acknowledge"):
            publish(CONFIG["IOTLINK_MASTER_URL"], generate_batch(1), 5.0)


if __name__ == "__main__":
    unittest.main()
