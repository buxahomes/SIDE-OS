#!/usr/bin/env python3
"""Two-request credential/coverage check. Never publish provider content or secrets."""
from collections import Counter
import json
import os
from pathlib import Path
import sys

from side_radar import ROOT, TZ, collect, datetime


def check(transport=None):
    if not os.environ.get("REDFOX_API_KEY", "").strip():
        return {"status": "missing_secret", "requests": 0, "platforms": []}
    cfg = json.loads((ROOT / "config/radar.json").read_text(encoding="utf-8"))
    cfg.update(keywords=["地陪"], page_size=5, pages_per_keyword=1, max_requests=2)
    report = collect(cfg, datetime.now(TZ), **({"transport": transport} if transport else {}))
    retained = Counter(x["platform"] for x in report["items"])
    rows = [{"platform": q["platform"], "status": q["status"],
             "returned": q.get("returned", 0), "retained": retained[q["platform"]],
             "error": q.get("error")} for q in report["queries"]]
    return {"status": "failed" if report["errors"] else "connection_ok",
            "requests": report["request_count"], "platforms": rows}


def main():
    result = check()
    # Only the explicitly allowlisted fields above reach logs or the public summary.
    print(json.dumps(result, ensure_ascii=False, indent=2))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        text = "# RedFox connection check\n\n"
        text += f"Status: {result['status']}. Data requests: {result['requests']}.\n\n"
        text += "| Platform | API status | Returned | Relevant in window | Error |\n|---|---|---:|---:|---|\n"
        for q in result["platforms"]:
            text += f"| {q['platform']} | {q['status']} | {q['returned']} | {q['retained']} | {q['error'] or '-'} |\n"
        text += "\nQuery: 地陪. One page of up to five items per platform, previous seven complete days.\n"
        text += "\nNo post content, API credentials, model analysis or report artifacts are published. An empty result is not evidence of full platform coverage.\n"
        Path(summary).write_text(text, encoding="utf-8")
    return 0 if result["status"] == "connection_ok" else 1


if __name__ == "__main__":
    sys.exit(main())
