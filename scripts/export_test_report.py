#!/usr/bin/env python3
"""Repeat the small test and deliver its data only as a recipient-encrypted artifact."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from side_radar import ROOT, TZ, ENDPOINTS, collect, analyze, score, datetime, post_json, normalize, clean_text, clean_url, timedelta


def main():
    required = ("REDFOX_API_KEY", "RADAR_LLM_URL", "RADAR_LLM_API_KEY", "RADAR_LLM_MODEL")
    if any(not os.environ.get(k, "").strip() for k in required):
        print("missing_configuration")
        return 1
    cfg = json.loads((ROOT / "config/radar.json").read_text(encoding="utf-8"))
    cfg.update(keywords=["北京地陪", "北京男大"], page_size=5, pages_per_keyword=1, max_requests=4, analysis_per_platform=3)
    cfg["related_terms"] = list(dict.fromkeys(cfg["related_terms"] + ["男大"]))
    now = datetime.now(TZ)
    end = now.date() - timedelta(days=1)
    start = end - timedelta(days=cfg["lookback_days"] - 1)
    query_audit = []

    def audited_transport(url, headers, payload):
        result = post_json(url, headers, payload)
        platform, (_, _, list_key, _) = next((p, e) for p, e in ENDPOINTS.items() if e[0] == url)
        data = result.get("data")
        rows = data.get(list_key) if isinstance(data, dict) else None
        if result.get("code") == 2000 and isinstance(rows, list):
            for index, raw in enumerate(rows, 1):
                if not isinstance(raw, dict):
                    query_audit.append({"platform": platform, "keyword": payload["keyword"], "row": index, "retained": False, "reason": "invalid_record_object"})
                    continue
                item = normalize(raw, platform, payload["keyword"], cfg, now, start, end)
                if platform == "douyin":
                    title, excerpt = raw.get("content"), raw.get("content")
                    source_url, author, published = raw.get("opusUrl"), raw.get("authorName"), raw.get("publishTime")
                else:
                    title, excerpt = raw.get("title"), raw.get("desc")
                    source_url, author, published = raw.get("shareInfoLink"), raw.get("authorNickname"), raw.get("createTime")
                query_audit.append({"platform": platform, "keyword": payload["keyword"], "row": index,
                                    "retained": item is not None, "retained_id": item["id"] if item else None,
                                    "title": clean_text(title, 200), "excerpt": clean_text(excerpt),
                                    "url": item["url"] if item else clean_url(source_url, platform),
                                    "author": clean_text(author, 80), "published_raw": clean_text(published, 100),
                                    "reason": "retained" if item else "did_not_pass_url_topic_or_date_filter"})
        return result

    report = collect(cfg, now, transport=audited_transport)
    report["query_audit"] = query_audit
    score(report)
    analyze(report, cfg)
    report["export_note"] = "按用户指定关键词北京地陪、北京男大进行的新测试；男大作为关联词，不等同于地陪服务。"
    report["config"] = cfg
    report["run_url"] = "https://github.com/buxahomes/SIDE-OS/actions/runs/" + os.environ.get("GITHUB_RUN_ID", "")
    out = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())) / "side-report.cms"
    with tempfile.TemporaryDirectory() as folder:
        plain = Path(folder) / "report.json"
        plain.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        plain.chmod(0o600)
        subprocess.run(["openssl", "cms", "-encrypt", "-binary", "-aes-256-gcm", "-in", str(plain),
                        "-out", str(out), "-outform", "DER", str(ROOT / "deploy/report-recipient.pem")], check=True)
    print(json.dumps({"collection_status": report["status"], "analysis_status": report["analysis_status"],
                      "items": len(report["items"]), "analyses": len(report["analysis"]),
                      "encrypted_report_ready": True}, ensure_ascii=False))
    return 0 if report["status"] == "ok" and report["analysis_status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
