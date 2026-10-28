import copy
import json
import unittest
from estimate_vehicle import estimate_vehicle, finalize, response_text, validate_input, price_summary, format_report, main
from unittest.mock import patch
import io
import tempfile
from pathlib import Path


DATA = {"vehicle": {"year": 2025, "make": "Toyota", "model": "4Runner",
                    "trim": "TRD Pro Hybrid", "mileage": 4956},
        "photo_urls": ["https://images.example.com/front.jpg"]}
SOURCES = {f"https://dealer.example.com/car/{n}" for n in range(3)}


def fixture():
    return {"market_rate_range": {"range": {"low": 68000, "high": 72000},
            "rationale": "Mock research only", "comparables": [
                {"url": url, "description": "Mock comparable", "asking_price": 70000,
                 "mileage": 5000, "adjustment_notes": "None"} for url in sorted(SOURCES)]},
            "expected_repair_cost": {"items": [
                {"description": "Bumper", "parts": {"low": 1000, "high": 1500},
                 "labor": {"low": 500, "high": 800}, "basis": "Mock only"},
                {"description": "Calibration", "parts": {"low": 0, "high": 0},
                 "labor": {"low": 300, "high": 500}, "basis": "Mock only"}],
                "assumptions": [], "possible_hidden_damage": [], "confidence": "medium"},
            "damage_description": {"summary": "Mock bumper damage", "visible_damage": [],
                                   "suspected_damage": [], "inspections_needed": []}}


def response(text):
    return {"status": "completed", "output": [{"type": "message", "content": [
        {"type": "output_text", "text": text}]}]}


class EstimatorTests(unittest.TestCase):
    def test_requested_price_format(self):
        value = fixture()
        self.assertEqual(price_summary(value)["on_road_price"], {"low": 51000, "high": 54000})
        self.assertEqual(price_summary(value)["savings"], {"low": 17000, "high": 18000})
        self.assertEqual(format_report(value),
                         "On road price : $51,000–$54,000\n"
                         "Market price : $68,000–$72,000\n"
                         "Savings ($) : $17,000–$18,000\n"
                         "Damage description: Mock bumper damage\n")

    def test_unavailable_market_has_no_derived_prices(self):
        value = fixture()
        value["market_rate_range"]["range"] = None
        summary = price_summary(value)
        self.assertIsNone(summary["on_road_price"])
        self.assertIsNone(summary["savings"])
        self.assertEqual(format_report(value).count("Unavailable"), 3)

    def test_cents_rounding_and_endpoint_subtraction(self):
        value = fixture()
        value["market_rate_range"]["range"] = {"low": 100.01, "high": 200.03}
        summary = price_summary(value)
        self.assertEqual(summary["on_road_price"], {"low": 75.01, "high": 150.02})
        self.assertEqual(summary["savings"], {"low": 25, "high": 50.01})

    def test_cli_text_default_and_json_opt_in(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text(json.dumps(DATA))
            for flags in ([], ["--format", "json"]):
                stdout = io.StringIO()
                with patch("sys.argv", ["estimate_vehicle.py", str(path), *flags]), \
                     patch("estimate_vehicle.estimate_vehicle", return_value=fixture()), \
                     patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"}), \
                     patch("sys.stdout", stdout):
                    self.assertEqual(main(), 0)
                if flags:
                    self.assertIn("expected_repair_cost", json.loads(stdout.getvalue()))
                else:
                    self.assertEqual(stdout.getvalue(), format_report(fixture()))

    def test_two_stage_request_and_totals(self):
        calls = []
        research = response("Mock sourced listings")
        research["output"].append({"type": "web_search_call", "action": {
            "sources": [{"url": url} for url in SOURCES]}})
        replies = iter([research, response(json.dumps(fixture()))])
        def fake(payload, key):
            calls.append(payload)
            return next(replies)
        result = estimate_vehicle(DATA, api_key="test-only", transport=fake)
        self.assertEqual(result["expected_repair_cost"]["total"], {"low": 1800, "high": 2800})
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["tool_choice"], "required")
        self.assertFalse(calls[1]["store"])
        self.assertTrue(calls[1]["text"]["format"]["strict"])
        self.assertEqual(calls[1]["input"][0]["content"][1]["image_url"], DATA["photo_urls"][0])

    def test_insufficient_and_invented_sources_null_market(self):
        result = finalize(fixture(), {next(iter(SOURCES))})
        self.assertIsNone(result["market_rate_range"]["range"])
        self.assertEqual(len(result["market_rate_range"]["comparables"]), 1)

    def test_duplicate_urls_do_not_count_as_three(self):
        value = fixture()
        comp = value["market_rate_range"]["comparables"][0]
        value["market_rate_range"]["comparables"] = [comp, comp, comp]
        self.assertIsNone(finalize(value, SOURCES)["market_rate_range"]["range"])

    def test_invalid_images_rejected(self):
        for url in ("http://images.example/a.jpg", "https://chatgpt.com/library?file_id=x",
                    "https://127.0.0.1/a.jpg", "https://u:p@example.com/a.jpg"):
            data = copy.deepcopy(DATA)
            data["photo_urls"] = [url]
            with self.assertRaises(ValueError):
                validate_input(data)

    def test_invalid_money_rejected(self):
        for money in ({"low": 20, "high": 10}, {"low": -1, "high": 10},
                      {"low": float("nan"), "high": 10}):
            value = fixture()
            value["expected_repair_cost"]["items"][0]["parts"] = money
            with self.assertRaises(ValueError):
                finalize(value, SOURCES)

    def test_incomplete_and_refused_outputs_fail(self):
        for value in ({"status": "incomplete"}, {"status": "completed", "output": [
                {"content": [{"type": "refusal"}]}]}):
            with self.assertRaises(RuntimeError):
                response_text(value)

    def test_missing_input(self):
        with self.assertRaises(ValueError):
            validate_input({"vehicle": {}, "photo_urls": []})


if __name__ == "__main__":
    unittest.main()
