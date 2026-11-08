import html
import io
import json
import os
import sys
import unittest
from datetime import datetime, timedelta

import config
from classify_zones import classify_venue
from search import format_time_12hr, normalize_zone, parse_date, parse_time_window, search_slots, time_to_minutes
from sync_catalog import load_cached_catalog

class DummyMockClient:
    def get_slots(self, venue_id, court_uuid, date_str):
        return []

class TestConfigModule(unittest.TestCase):
    def test_default_config_types(self):
        cfg = config.load_config()
        self.assertIsInstance(cfg, dict)
        self.assertIn("telegram_bot_token", cfg)
        self.assertIn("telegram_chat_id", cfg)
        self.assertIn("enable_phase2_sniper", cfg)
        self.assertIn("enable_phase3_autobook", cfg)

    def test_env_precedence(self):
        os.environ["TELEGRAM_BOT_TOKEN"] = "test_env_token_123"
        self.assertEqual(config.get_bot_token(), "test_env_token_123")
        del os.environ["TELEGRAM_BOT_TOKEN"]

    def test_phase_flags_default(self):
        self.assertFalse(config.is_phase2_enabled())
        self.assertFalse(config.is_phase3_enabled())

    def test_phase_flags_env(self):
        os.environ["ENABLE_PHASE2"] = "true"
        self.assertTrue(config.is_phase2_enabled())
        del os.environ["ENABLE_PHASE2"]

class TestSearchParsing(unittest.TestCase):
    def test_parse_date_today(self):
        today_str = datetime.now().strftime("%Y-%m-%d")
        self.assertEqual(parse_date("today"), today_str)
        self.assertEqual(parse_date("t"), today_str)

    def test_parse_date_tomorrow(self):
        tmrw_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        self.assertEqual(parse_date("tomorrow"), tmrw_str)
        self.assertEqual(parse_date("tom"), tmrw_str)

    def test_parse_date_iso(self):
        self.assertEqual(parse_date("2026-12-25"), "2026-12-25")

    def test_parse_date_invalid(self):
        with self.assertRaises(ValueError):
            parse_date("invalid-date")

    def test_parse_time_presets(self):
        self.assertEqual(parse_time_window("all"), (0, 1440))
        self.assertEqual(parse_time_window("morning"), (360, 720))
        self.assertEqual(parse_time_window("evening"), (1080, 1320))
        self.assertEqual(parse_time_window("night"), (1260, 1440))

    def test_parse_time_explicit(self):
        self.assertEqual(parse_time_window("19:00-22:00"), (1140, 1320))
        self.assertEqual(parse_time_window("18-21"), (1080, 1260))

    def test_time_to_minutes(self):
        self.assertEqual(time_to_minutes("19:30:00"), 1170)
        self.assertEqual(time_to_minutes("2026-11-09 20:00:00"), 1200)

    def test_normalize_zone(self):
        self.assertEqual(normalize_zone("sobo"), "south_mumbai")
        self.assertEqual(normalize_zone("south"), "south_mumbai")
        self.assertEqual(normalize_zone("west"), "western_suburbs")
        self.assertEqual(normalize_zone("western"), "western_suburbs")
        self.assertEqual(normalize_zone("east"), "eastern_suburbs")
        self.assertEqual(normalize_zone("central"), "eastern_suburbs")
        self.assertIsNone(normalize_zone(None))

    def test_format_time_12hr(self):
        self.assertEqual(format_time_12hr("2026-11-09 19:30:00"), "07:30 PM")
        self.assertEqual(format_time_12hr("2026-11-09 09:00:00"), "09:00 AM")

class TestStreamSeparation(unittest.TestCase):
    def test_search_slots_logs_to_stderr_not_stdout(self):
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        try:
            # Run search with mock client
            mock_client = DummyMockClient()
            slots = search_slots(
                date_str="2026-11-10",
                venue_filter="nonexistent_venue_test",
                client=mock_client
            )
            stdout_content = sys.stdout.getvalue()
            stderr_content = sys.stderr.getvalue()

            # stdout must be completely silent so JSON piping is clean
            self.assertEqual(stdout_content, "")
            # stderr must receive the scanning diagnostics
            self.assertIn("Scanning slots", stderr_content)
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

class TestZoneClassification(unittest.TestCase):
    def test_south_mumbai_classification(self):
        v = {"name": "Padel Court Colaba", "address": "Near Gateway, Colaba", "slug": "padel-colaba"}
        zone, label = classify_venue(v)
        self.assertEqual(zone, "south_mumbai")

    def test_western_suburbs_classification(self):
        v = {"name": "Bandra Padel Arena", "address": "Pali Hill, Bandra West", "slug": "bandra-arena"}
        zone, label = classify_venue(v)
        self.assertEqual(zone, "western_suburbs")

    def test_eastern_suburbs_classification(self):
        v = {"name": "Powai Court Club", "address": "Hiranandani, Powai", "slug": "powai-padel"}
        zone, label = classify_venue(v)
        self.assertEqual(zone, "eastern_suburbs")

class TestHtmlEntitySafety(unittest.TestCase):
    def test_escaping_ampersands_and_brackets(self):
        unsafe_name = "Urban Sports & Padel Club <Worli>"
        safe_name = html.escape(unsafe_name)
        self.assertEqual(safe_name, "Urban Sports &amp; Padel Club &lt;Worli&gt;")

class TestCatalogIntegrity(unittest.TestCase):
    def test_venues_cache_exists_and_valid(self):
        catalog = load_cached_catalog()
        self.assertGreaterEqual(len(catalog), 40)
        for v in catalog:
            self.assertIn("venue_id", v)
            self.assertIn("name", v)
            self.assertIn("zone", v)
            self.assertIn("courts", v)
            for c in v["courts"]:
                self.assertIn("facility_uuid", c)
                self.assertIn("name", c)
                c_low = c["name"].lower()
                for bad in ["racquet", "ball", "paddle", "machine"]:
                    self.assertNotIn(bad, c_low)

if __name__ == "__main__":
    unittest.main()
