#!/usr/bin/env python3
"""End-to-end credential and structured-analysis check; only metrics reach logs."""
from collections import Counter
import json
import os
from pathlib import Path
import sys

from side_radar import ROOT, TZ, analyze, collect, datetime, score


def check(data_transport=None, model_transport=None):
    required = ("REDFOX_API_KEY", "RADAR_LLM_URL", "RADAR_LLM_API_KEY", "RADAR_LLM_MODEL")
    missing = [k for k in required if not os.environ.get(k, "").strip()]
    if missing:
        return {"status": "missing_config", "missing": missing, "data_requests": 0, "model_requests": 0}
    cfg = json.loads((ROOT / "config/radar.json").read_text(encoding="utf-8"))
    cfg.update(keywords=["地陪"], page_size=5, pages_per_keyword=1, max_requests=2, analysis_per_platform=3)
    report = collect(cfg, datetime.now(TZ), **({"transport": data_transport} if data_transport else {}))
    score(report)
    calls = []
    from side_radar import post_json
    def counted_transport(*args):
        calls.append(True)
        return (model_transport or post_json)(*args)
    analyze(report, cfg, counted_transport)
    counts = Counter(x["platform"] for x in report["items"])
    items = {x["id"]: x for x in report["items"]}
    analyzed = Counter(items[a["id"]]["platform"] for a in report["analysis"])
    # Do not log URLs, titles, author data, excerpts, free-form model output or provider bodies.
    return {"status": "ok" if report["status"] == "ok" and report["analysis_status"] == "ok" else "incomplete",
            "collection_status": report["status"], "analysis_status": report["analysis_status"],
            "analysis_error": report.get("analysis_error"),
            "data_requests": report["request_count"], "model_requests": len(calls),
            "platforms": [{"platform": p, "retained": counts[p], "analyzed": analyzed[p]} for p in ("douyin", "xiaohongshu")],
            "validated_analyses": len(report["analysis"]), "usage": report.get("analysis_usage", {}),
            "data_errors": [{"platform": x["platform"], "error": x["error"]} for x in report["errors"]]}


def main():
    result = check()
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        Path(summary).write_text("# Side analysis connection check\n\n```json\n" + text + "\n```\n\nOnly status, counts and token usage are published. Evidence validation checks quoted spans and item IDs; it does not establish that model judgments are correct. Daily collection is not enabled.\n", encoding="utf-8")
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
