#!/usr/bin/env python3
"""Repeat the small test and deliver its data only as a recipient-encrypted artifact."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from side_radar import ROOT, TZ, collect, analyze, score, datetime


def main():
    required = ("REDFOX_API_KEY", "RADAR_LLM_URL", "RADAR_LLM_API_KEY", "RADAR_LLM_MODEL")
    if any(not os.environ.get(k, "").strip() for k in required):
        print("missing_configuration")
        return 1
    cfg = json.loads((ROOT / "config/radar.json").read_text(encoding="utf-8"))
    cfg.update(keywords=["地陪"], page_size=5, pages_per_keyword=1, max_requests=2, analysis_per_platform=3)
    report = collect(cfg, datetime.now(TZ))
    score(report)
    analyze(report, cfg)
    report["export_note"] = "按原接入测试参数重新采集；不是此前未保存的那次结果。"
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
