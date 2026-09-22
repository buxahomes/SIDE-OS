"""Synthetic data only: checks do not make paid API requests."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("radar", Path(__file__).resolve().parents[1] / "scripts/side_radar.py")
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)
CFG = json.loads((r.ROOT / "config/radar.json").read_text())
NOW = r.datetime(2026, 9, 12, 0, 30, tzinfo=r.TZ)


def row(i="1", likes=100):
    return {"content": "北京地陪陪你逛胡同", "opusUrl": "https://www.douyin.com/video/" + i,
            "publishTime": "2026-09-11 12:00:00", "likeCount": likes,
            "commentCount": 2, "collectCount": 3, "shareCount": 4}


def item(raw=None):
    return r.normalize(raw or row(), "douyin", "地陪", CFG, NOW,
                       r.datetime(2026, 9, 5).date(), r.datetime(2026, 9, 11).date())


class RadarTests(unittest.TestCase):
    def test_missing_approximate_metrics(self):
        self.assertIsNone(r.metric(None))
        self.assertIsNone(r.metric("未知"))
        self.assertEqual(r.metric("0")["value"], 0)
        self.assertTrue(r.metric("1.5万+")["approximate"])
        self.assertEqual(r.metric("1.5万+")["value"], 15000)

    def test_links_strip_secrets_and_reject_unrelated_domains(self):
        self.assertEqual(r.clean_url("https://www.douyin.com/video/1?token=secret#x", "douyin"), "https://www.douyin.com/video/1")
        self.assertEqual(r.clean_url("https://douyin.com.evil.example/a", "douyin"), "")
        self.assertEqual(r.clean_url("javascript:alert(1)", "douyin"), "")
        self.assertNotIn("secret", r.clean_text("https://xhslink.cn/o/a?xsec_token=secret token=secret"))

    def test_date_and_topic_filter(self):
        data = row()
        data["publishTime"] = "2020-01-01"
        self.assertIsNone(item(data))
        data["publishTime"] = "not-a-date"
        self.assertIn("发布时间", item(data)["missing"])
        data["content"] = "汽车维修"
        self.assertIsNone(item(data))

    def test_deduplication_and_partial_failure(self):
        calls = []
        def fake(url, headers, payload):
            calls.append(url)
            if "xhs" in url:
                raise r.RadarError("http_401")
            return {"code": 2000, "data": {"list": [row()]}}
        report = r.collect(CFG, NOW, fake)
        self.assertEqual(len(calls), 12)
        self.assertEqual(len(report["items"]), 1)
        self.assertEqual(len(report["items"][0]["matched_queries"]), 6)
        self.assertEqual(report["status"], "partial")
        self.assertEqual(len(report["errors"]), 6)

    def test_schema_mismatch_is_error_not_zero(self):
        report = r.collect(CFG, NOW, lambda *args: {"code": 2000, "data": {"unexpected": []}})
        self.assertEqual(report["status"], "empty_or_failed")
        self.assertTrue(all(x["error"] == "provider_schema_mismatch" for x in report["errors"]))

    def test_missing_metric_ties_and_growth(self):
        items = [item(row("1")), item(row("2")), item(row("3", None))]
        previous = {"items": [dict(items[0], observed_at=(NOW - r.timedelta(hours=26)).isoformat(), interaction_total=100)]}
        report = {"generated_at": NOW.isoformat(), "items": items}
        r.score(report, previous)
        by_id = {x["id"]: x for x in report["items"]}
        self.assertEqual(by_id["douyin:1"]["score_components"]["热度"], 50)
        self.assertEqual(by_id["douyin:2"]["score_components"]["热度"], 50)
        self.assertIsNone(by_id["douyin:3"]["screening_score"])
        self.assertEqual(by_id["douyin:1"]["growth"]["delta"], 9)
        self.assertEqual(by_id["douyin:1"]["growth"]["hours"], 26)

    def test_budget_validation(self):
        with self.assertRaises(r.RadarError):
            r.validate_config(dict(CFG, pages_per_keyword=2))

    def test_llm_rejects_fabricated_evidence_and_unknown_ids(self):
        x = item()
        a = {"id": x["id"], "side_fit_score": 80, "evidence": "北京地陪", "reason": "示例", "angle": "示例", "demand_hypothesis": "待验证", "limits": "未看图片"}
        self.assertEqual(len(r.validate_analysis({"items": [a]}, [x])), 1)
        for bad in (dict(a, evidence="实际成交100单"), dict(a, id="unknown"), dict(a, side_fit_score=101)):
            with self.assertRaises(r.RadarError):
                r.validate_analysis({"items": [bad]}, [x])

    def test_llm_failure_preserves_data(self):
        report = {"items": [item()]}
        with patch.dict(os.environ, {"RADAR_LLM_URL": "https://example.test/chat/completions", "RADAR_LLM_API_KEY": "test", "RADAR_LLM_MODEL": "test"}):
            r.analyze(report, CFG, lambda *args: {"choices": [{"message": {"content": "{}"}}]})
        self.assertEqual(report["analysis_status"], "failed_validation_or_request")
        self.assertEqual(len(report["items"]), 1)

    def test_html_escapes_external_content_and_saves_archive(self):
        report = r.collect(CFG, NOW, lambda *args: {"code": 2000, "data": {"list": [], "articles": []}})
        x = item()
        x["title"] = "<script>alert(1)</script>地陪"
        report["items"] = [x]
        r.score(report)
        report.update(analysis=[], analysis_status="not_requested")
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            r.write_report(report, out)
            html = (out / "latest.html").read_text()
            self.assertNotIn("<script>", html)
            self.assertIn("&lt;script&gt;", html)
            self.assertEqual(len(list(out.glob("*.json"))), 2)
            self.assertEqual((out / "latest.json").stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
