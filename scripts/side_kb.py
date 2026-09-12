#!/usr/bin/env python3
"""SIDE knowledge intake. Standard library only. No authentication bypass."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit, parse_qs, urlencode
from urllib.request import Request, HTTPRedirectHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
HOSTS = {
    "xiaohongshu": {"xiaohongshu.com", "www.xiaohongshu.com", "xhslink.com", "www.xhslink.com"},
    "douyin": {"douyin.com", "www.douyin.com", "v.douyin.com", "m.douyin.com", "iesdouyin.com", "www.iesdouyin.com"},
}
MAX_HTML = 2 * 1024 * 1024
MAX_INPUT = 250 * 1024 * 1024
BLOCKS = ("请完成安全验证", "请完成验证", "访问过于频繁", "登录后查看", "验证后继续", "安全验证", "captcha", "verify you are human", "access denied")


def now():
    return datetime.now(timezone.utc).isoformat()


def extract_url(text):
    match = re.search(r"https?://[^\s<>\"'，。；！]+", text)
    if not match:
        raise ValueError("未找到HTTP(S)链接")
    return match.group(0).rstrip(".,;!)]}）】")


def platform_for(url):
    p = urlsplit(url)
    if p.scheme not in ("http", "https") or p.username or p.password or p.port not in (None, 80, 443):
        raise ValueError("只接受普通小红书/抖音公开链接")
    for platform, hosts in HOSTS.items():
        if (p.hostname or "").lower() in hosts:
            return platform
    raise ValueError("链接域名不在支持的平台范围内")


def clean_url(url):
    """Keep public identity, discard tracking/signature queries from saved records."""
    platform_for(url)
    p = urlsplit(url)
    query = parse_qs(p.query)
    kept = {k: query[k][0] for k in ("modal_id", "vid", "item_id") if k in query}
    return urlunsplit((p.scheme, p.netloc.lower(), p.path, urlencode(kept), ""))


class PlatformRedirect(HTTPRedirectHandler):
    def __init__(self, platform):
        self.platform = platform

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if platform_for(newurl) != self.platform:
            raise ValueError("重定向离开原平台，已停止")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.title = []
        self.visible = []
        self.jsonld = []
        self.in_title = False
        self.hidden = 0
        self.capture_json = False
        self.script = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            key = attrs.get("property", attrs.get("name", "")).lower()
            self.meta[key] = attrs.get("content", "")
        if tag == "title":
            self.in_title = True
        if tag in ("script", "style", "noscript"):
            self.hidden += 1
        if tag == "script" and attrs.get("type", "").lower() == "application/ld+json":
            self.capture_json = True
            self.script = []

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "script" and self.capture_json:
            self.jsonld.append("".join(self.script))
            self.capture_json = False
        if tag in ("script", "style", "noscript"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if self.capture_json:
            self.script.append(data)
        if self.in_title:
            self.title.append(data)
        if not self.hidden:
            self.visible.append(data)


def objects(value):
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from objects(v)
    elif isinstance(value, list):
        for v in value:
            yield from objects(v)


def text_value(value):
    return value.strip() if isinstance(value, str) else ""


def parse_page(html):
    page = Page()
    page.feed(html)
    title = page.meta.get("og:title") or "".join(page.title).strip()
    description = page.meta.get("og:description") or page.meta.get("description", "")
    visible = " ".join(page.visible).lower()
    if any(marker in visible for marker in BLOCKS):
        return dict(title=title, description="", body="", status="blocked", limitation="检测到登录或验证阻断；没有读取正文")
    body, author, published = "", "", ""
    for script in page.jsonld:
        try:
            payload = json.loads(script)
        except (ValueError, RecursionError):
            continue
        for obj in objects(payload):
            types = obj.get("@type", [])
            if isinstance(types, str):
                types = [types]
            if not isinstance(types, list) or not any(t in ("Article", "NewsArticle", "BlogPosting", "SocialMediaPosting", "VideoObject") for t in types):
                continue
            title = text_value(obj.get("headline")) or text_value(obj.get("name")) or title
            description = text_value(obj.get("description")) or description
            candidate = text_value(obj.get("articleBody"))
            if len(candidate) > len(body):
                body = candidate
            a = obj.get("author", "")
            if isinstance(a, dict):
                author = text_value(a.get("name")) or author
            elif isinstance(a, str):
                author = a
            published = text_value(obj.get("datePublished")) or text_value(obj.get("uploadDate")) or published
    return dict(title=title, description=description, body=body, author=author or None,
                published_at=published or None, status="partial" if body else ("metadata_only" if title or description else "no_content"),
                limitation="仅提取页面明确提供的文本；未验证全文、图片、评论或视频口播")


def fetch_page(raw_url):
    url = extract_url(raw_url)
    platform = platform_for(url)
    result = dict(platform=platform, source_url=clean_url(url), method="public_html", kind="webpage")
    req = Request(url, headers={"User-Agent": "SIDE-KB/1.0 (public content research)", "Accept": "text/html"})
    try:
        with build_opener(PlatformRedirect(platform)).open(req, timeout=15) as response:
            final = response.geturl()
            if platform_for(final) != platform:
                raise ValueError("最终页面平台不匹配")
            result["resolved_url"] = clean_url(final)
            ctype = response.headers.get_content_type()
            if ctype not in ("text/html", "application/xhtml+xml"):
                raise ValueError("响应不是网页HTML")
            data = response.read(MAX_HTML + 1)
            if len(data) > MAX_HTML:
                raise ValueError("响应超过2MiB读取上限")
            encoding = response.headers.get_content_charset() or "utf-8"
            result.update(parse_page(data.decode(encoding, errors="replace")))
    except HTTPError as exc:
        result.update(status="blocked" if exc.code in (401, 403, 429) else "error", limitation=f"HTTP {exc.code}，未取得正文")
    except (URLError, TimeoutError, OSError, ValueError, LookupError) as exc:
        # Do not persist exception URLs, which may contain signed query parameters.
        result.update(status="error", limitation=f"读取未完成（{type(exc).__name__}）；可改为提供正文或字幕")
    return result


def save_record(root, record, body="", media=None):
    root = Path(root)
    record = dict(record)
    record.pop("body", None)
    fingerprint = hashlib.sha256(media.read_bytes() if media else body.encode()).hexdigest()
    key = {k: record.get(k) for k in ("platform", "source_url", "resolved_url", "title", "author", "published_at", "kind", "status", "description", "external_id", "metrics")}
    key["sha256"] = fingerprint
    rid = hashlib.sha256(json.dumps(key, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:20]
    folder = root / "research/records"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (rid + ".json")
    if target.exists():
        return {"record_id": rid, "deduplicated": True, "path": str(target), "status": record["status"]}
    local = root / "research/local" / rid
    if body or media:
        local.mkdir(parents=True, exist_ok=True)
    if body:
        content_file = local / "content.txt"
        content_file.write_text(body, encoding="utf-8")
        record["local_content"] = content_file.relative_to(root).as_posix()
    if media:
        media_file = local / ("attachment" + media.suffix.lower())
        shutil.copyfile(media, media_file)
        record["local_media"] = media_file.relative_to(root).as_posix()
    # Persist only a short source excerpt; full text is local and gitignored.
    record["excerpt"] = body[:120]
    if "description" in record:
        record["description"] = record["description"][:120]
    record.update(record_id=rid, schema_version=1, ingested_at=now(), content_sha256=fingerprint,
                  review_status="unreviewed", rule_status="external_reference_only")
    target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"record_id": rid, "deduplicated": False, "path": str(target), "status": record["status"]}


def ingest(root, platform, file, kind="text", url=None, title="", author=None):
    file = Path(file)
    if not file.is_file() or file.stat().st_size > MAX_INPUT:
        raise ValueError("输入文件不存在或超过250MiB")
    if url:
        url = extract_url(url)
        if platform_for(url) != platform:
            raise ValueError("所选平台与来源链接不匹配")
        url = clean_url(url)
    status = {"text": "provided_text", "transcript": "provided_text", "image": "needs_ocr", "audio": "needs_transcription", "video": "needs_video_review"}[kind]
    record = dict(platform=platform, source_url=url, title=title or file.stem, author=author,
                  kind=kind, method="user_provided", status=status, published_at=None,
                  limitation="来源信息由提供者声明；待核实。媒体附件登记不等于完成识别")
    if kind in ("text", "transcript"):
        body = file.read_text(encoding="utf-8-sig")
        if not body.strip():
            raise ValueError("文本为空")
        return save_record(root, record, body=body)
    return save_record(root, record, media=file)


def import_douyin_export(root, file):
    payload = json.loads(Path(file).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise ValueError("需要官方视频列表响应的data对象")
    data = payload["data"]
    if data.get("error_code") != 0 or not isinstance(data.get("list"), list):
        raise ValueError("接口响应未成功或缺少list，不能标记已读取")
    # Validate the whole batch before writing any records.
    records = []
    for item in data["list"]:
        if not isinstance(item, dict):
            raise ValueError("视频列表格式错误")
        raw = item.get("share_url")
        url = clean_url(raw) if raw else None
        if raw and platform_for(raw) != "douyin":
            raise ValueError("视频列表中的链接不属于抖音")
        stats = item.get("statistics") or {}
        if not isinstance(stats, dict):
            raise ValueError("statistics格式错误")
        metrics = {k: v for k, v in stats.items() if k in ("forward_count", "comment_count", "digg_count", "download_count", "play_count", "share_count") and type(v) in (int, float) and v >= 0}
        records.append(dict(platform="douyin", source_url=url, kind="video_metadata", method="provided_official_export",
                            status="metadata_only", title=text_value(item.get("title")), external_id=str(item.get("item_id") or item.get("video_id") or ""),
                            published_at=item.get("create_time"), metrics=metrics, metrics_observed_at=None,
                            limitation="导出文件来源待复核，统计量采集时点未知；不是口播或视频内容"))
    return [save_record(root, record) for record in records]


def search(root, query, include_archive=False):
    result = []
    roots = ["docs", "templates", "config", "research/records", "research/analysis", "research/local", "assets"]
    if include_archive:
        roots += ["archive", "sources/text"]
    for folder in roots:
        for path in sorted((Path(root) / folder).rglob("*")):
            if not path.is_file() or path.suffix not in (".md", ".txt", ".json", ".csv"):
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if query.casefold() in line.casefold():
                    result.append({"path": path.relative_to(root).as_posix(), "line": number, "text": line[:180]})
                    if len(result) >= 30:
                        return result
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    sub = p.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fetch"); f.add_argument("url")
    i = sub.add_parser("ingest")
    i.add_argument("--platform", choices=HOSTS, required=True)
    i.add_argument("--file", type=Path, required=True)
    i.add_argument("--kind", choices=("text", "transcript", "image", "audio", "video"), default="text")
    i.add_argument("--url"); i.add_argument("--title", default=""); i.add_argument("--author")
    d = sub.add_parser("douyin-export"); d.add_argument("file", type=Path)
    s = sub.add_parser("search"); s.add_argument("query"); s.add_argument("--include-archive", action="store_true")
    args = p.parse_args()
    try:
        if args.command == "fetch":
            record = fetch_page(args.url)
            result = save_record(args.root, record, body=record.get("body", ""))
        elif args.command == "ingest":
            result = ingest(args.root, args.platform, args.file, args.kind, args.url, args.title, args.author)
        elif args.command == "douyin-export":
            result = import_douyin_export(args.root, args.file)
        else:
            result = search(args.root, args.query, args.include_archive)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.command == "fetch" and result["status"] in ("blocked", "error", "no_content"):
            return 2
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
