import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from worker import read_master, settings, validate_batch


SAMPLE = {
    "schema_version": "1.0",
    "readings": [{
        "device_id": "motor-01",
        "timestamp": "2026-11-10T15:00:00Z",
        "quality": "good",
        "values": {"temperature_c": 47.4, "vibration_mm_s": 2.1, "rpm": 1450}
    }]
}


class TestConfiguration(unittest.TestCase):
    def test_default_is_simulated(self):
        cfg = settings({})
        self.assertEqual(cfg["mode"], "simulated")
        self.assertIn("iotlink-master", cfg["url"])

    def test_real_source_is_configurable(self):
        cfg = settings({
            "IOTLINK_MASTER_MODE": "real",
            "IOTLINK_REAL_MASTER_URL": "http://192.168.1.40/api/v1/measurements",
            "IOTLINK_REAL_MASTER_TOKEN": "example",
        })
        self.assertEqual(cfg["mode"], "real")
        self.assertEqual(cfg["token"], "example")

    def test_real_mode_needs_url(self):
        with self.assertRaises(ValueError):
            settings({"IOTLINK_MASTER_MODE": "real"})

    def test_invalid_interval(self):
        with self.assertRaises(ValueError):
            settings({"IOTLINK_POLL_INTERVAL_SECONDS": "0"})

    def test_embedded_credentials_rejected(self):
        with self.assertRaises(ValueError):
            settings({
                "IOTLINK_MASTER_MODE": "real",
                "IOTLINK_REAL_MASTER_URL": "http://user:password@host/api",
            })


class TestContract(unittest.TestCase):
    def test_valid_values(self):
        readings = validate_batch(SAMPLE)
        self.assertEqual(readings[0]["device_id"], "motor-01")
        self.assertEqual(readings[0]["values"]["rpm"], 1450)

    def test_schema_mismatch(self):
        with self.assertRaises(ValueError):
            validate_batch({"schema_version": "2.0", "readings": []})

    def test_missing_timezone(self):
        payload = json.loads(json.dumps(SAMPLE))
        payload["readings"][0]["timestamp"] = "2026-11-10T15:00:00"
        with self.assertRaises(ValueError):
            validate_batch(payload)

    def test_bad_numeric_value(self):
        payload = json.loads(json.dumps(SAMPLE))
        payload["readings"][0]["values"]["rpm"] = True
        with self.assertRaises(ValueError):
            validate_batch(payload)

    @patch("worker.urlopen")
    def test_fetch_and_token(self, mock_urlopen):
        mock_urlopen.return_value.__enter__.return_value = io.BytesIO(
            json.dumps(SAMPLE).encode("utf-8")
        )
        cfg = settings({
            "IOTLINK_MASTER_MODE": "real",
            "IOTLINK_REAL_MASTER_URL": "http://192.168.1.40/api/v1/measurements",
            "IOTLINK_REAL_MASTER_TOKEN": "example",
        })
        values = read_master(cfg)
        self.assertEqual(values[0]["device_id"], "motor-01")
        sent = mock_urlopen.call_args.args[0]
        self.assertEqual(sent.get_header("Authorization"), "Bearer example")


if __name__ == "__main__":
    unittest.main()
