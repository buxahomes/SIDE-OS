#!/usr/bin/env python3
"""Bounded annual keyword search with auditable strict thresholds; encrypted export only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from collections import Counter
from side_radar import ROOT, TZ, ENDPOINTS, datetime, normalize, clean_text, clean_url, metric, parse_date, post_json, RadarError


def main():
    if not os.environ.get('REDFOX_API_KEY', '').strip():
        print('missing_configuration')
        return 1
    now = datetime.now(TZ)
    start, end = now.date().replace(month=1, day=1), now.date()
    cfg = json.loads((ROOT / 'config/radar.json').read_text(encoding='utf-8'))
    cfg.update(keywords=['北京男地陪', '北京男大'], page_size=50, pages_per_keyword=15, max_requests=11,
               target_per_platform=10, start_date=str(start), end_date=str(end),
               continuation_pages={'douyin:北京男地陪': [6, 15], 'xiaohongshu:北京男大': [2, 2]})
    cfg.pop('lookback_days', None)
    cfg['related_terms'] = list(dict.fromkeys(cfg['related_terms'] + ['男大', '北京']))
    report = {'generated_at': now.isoformat(), 'period': [str(start), str(end)], 'config': cfg,
              'coverage': '红狐接口收录样本；请求本年日期范围。小红书公开说明仅近30天热门库，不能据此声称覆盖全年。',
              'queries': [], 'query_audit': [], 'items': [], 'errors': [], 'request_count': 0,
              'analysis': [], 'analysis_status': 'not_requested_for_search_test',
              'thresholds': {'douyin': {'metric': 'likes', 'operator': '>', 'value': 10000},
                             'xiaohongshu': {'metric': 'likes+comments+saves+shares', 'operator': '>=', 'value': 1000}},
              'continuation_of_run': '34697587823',
              'selection_note': 'items为数值门槛通过的候选，最终由报告审阅排除综艺、系统广告、非北京或无法确认北京关联的内容，再每平台取最多10条。',
              'run_url': 'https://github.com/buxahomes/SIDE-OS/actions/runs/' + os.environ.get('GITHUB_RUN_ID', '')}
    unique = {}
    for platform, (url, header, list_key, source) in ENDPOINTS.items():
        for keyword in cfg['keywords']:
            continuation = {('douyin', '北京男地陪'): (6, 15), ('xiaohongshu', '北京男大'): (2, 2)}
            if (platform, keyword) not in continuation:
                continue
            first_page, last_page = continuation[(platform, keyword)]
            seen_pages = set()
            for page in range(first_page, last_page + 1):
                q = {'platform': platform, 'keyword': keyword, 'page': page, 'requested_page_size': 50}
                report['request_count'] += 1
                try:
                    result = post_json(url, {header: os.environ['REDFOX_API_KEY']},
                                       {'keyword': keyword, 'source': source, 'pageNum': page, 'pageSize': 50,
                                        'startDate': str(start), 'endDate': str(end)})
                    if result.get('code') != 2000:
                        raise RadarError('provider_rejected_request')
                    data = result.get('data')
                    if not isinstance(data, dict) or not isinstance(data.get(list_key), list):
                        raise RadarError('provider_schema_mismatch')
                    rows = data[list_key]
                    q.update(status='ok' if rows else 'empty', returned=len(rows), possibly_truncated=len(rows) >= 50)
                    for key in ('total', 'pageNum', 'pageSize', 'has_more', 'hasMore'):
                        if type(data.get(key)) in (int, bool):
                            q['provider_' + key] = data[key]
                    page_signature = []
                    for row_no, raw in enumerate(rows, 1):
                        audit = {'platform': platform, 'keyword': keyword, 'page': page, 'row': row_no}
                        if not isinstance(raw, dict):
                            audit.update(retained=False, reasons=['invalid_record_object'])
                            report['query_audit'].append(audit)
                            continue
                        if platform == 'douyin':
                            title, excerpt, author, published, link = (raw.get(k) for k in ('content', 'content', 'authorName', 'publishTime', 'opusUrl'))
                            fields = ('likeCount', 'commentCount', 'collectCount', 'shareCount')
                        else:
                            title, excerpt, author, published, link = (raw.get(k) for k in ('title', 'desc', 'authorNickname', 'createTime', 'shareInfoLink'))
                            fields = ('likedCount', 'commentsCount', 'collectedCount', 'sharedCount')
                        counts = dict(zip(('likes', 'comments', 'saves', 'shares'), (metric(raw.get(k)) for k in fields)))
                        total = sum(v['value'] for v in counts.values()) if all(v is not None for v in counts.values()) else None
                        item = normalize(raw, platform, keyword, cfg, now, start, end)
                        reasons = []
                        date = parse_date(published)
                        if date is None: reasons.append('missing_publish_date')
                        elif not start <= date.date() <= end: reasons.append('outside_requested_year')
                        if platform == 'douyin':
                            m = counts['likes']
                            if m is None: reasons.append('missing_like_count')
                            elif m['approximate']: reasons.append('approximate_like_count_requires_review')
                            elif m['value'] <= 10000: reasons.append('likes_not_above_10000')
                        else:
                            if total is None: reasons.append('missing_interaction_count')
                            elif any(v['approximate'] for v in counts.values()): reasons.append('approximate_interaction_count_requires_review')
                            elif total < 1000: reasons.append('interactions_below_1000')
                        if item is None: reasons.append('failed_url_topic_or_date_normalization')
                        audit.update(title=clean_text(title, 200), excerpt=clean_text(excerpt), author=clean_text(author, 80),
                                     published_raw=clean_text(published, 100), counts=counts, interaction_total=total,
                                     url=item['url'] if item else clean_url(link, platform),
                                     retained=not reasons, retained_id=item['id'] if item else None, reasons=reasons)
                        report['query_audit'].append(audit)
                        page_signature.append((audit['url'], audit['title']))
                        if item and not reasons:
                            prior = unique.get(item['id'])
                            if prior: item['matched_queries'] = sorted(set(prior['matched_queries'] + [keyword]))
                            unique[item['id']] = item
                    signature = tuple(page_signature)
                    if signature and signature in seen_pages:
                        q['stop_reason'] = 'repeated_page'
                    elif not rows: q['stop_reason'] = 'empty_page'
                    elif data.get('has_more') is False or data.get('hasMore') is False: q['stop_reason'] = 'provider_no_more'
                    elif type(data.get('total')) is int and data['total'] <= page * 50: q['stop_reason'] = 'provider_total_reached'
                    elif len(rows) < 50 and data.get('has_more') is not True and data.get('hasMore') is not True and not (type(data.get('total')) is int and data['total'] > page * 50): q['stop_reason'] = 'short_page'
                    elif page == last_page: q['stop_reason'] = 'page_budget_reached'
                    seen_pages.add(signature)
                except RadarError as exc:
                    q.update(status='error', error=str(exc), stop_reason='request_error')
                    report['errors'].append(dict(q))
                report['queries'].append(q)
                if q.get('stop_reason'): break
                time.sleep(0.25)
    report['items'] = sorted(unique.values(), key=lambda x: (x['platform'], -(x['counts']['likes']['value'] if x['platform']=='douyin' else x['interaction_total']), x['id']))
    report['status'] = 'ok' if not report['errors'] else 'partial'
    report['numeric_candidates_by_platform'] = dict(Counter(x['platform'] for x in report['items']))
    out = Path(os.environ.get('RUNNER_TEMP', tempfile.gettempdir())) / 'side-report.cms'
    with tempfile.TemporaryDirectory() as folder:
        plain = Path(folder) / 'report.json'
        plain.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        plain.chmod(0o600)
        subprocess.run(['openssl','cms','-encrypt','-binary','-aes-256-gcm','-in',str(plain),'-out',str(out),'-outform','DER',str(ROOT/'deploy/report-recipient.pem')],check=True)
    print(json.dumps({'collection_status':report['status'],'returned_rows':len(report['query_audit']),
                      'numeric_candidates':len(report['items']),'requests':report['request_count'],'encrypted_report_ready':True}))
    return 0 if not report['errors'] else 1


if __name__ == '__main__':
    sys.exit(main())
