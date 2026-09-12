import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

spec = importlib.util.spec_from_file_location("kb", Path(__file__).resolve().parents[1] / "scripts/side_kb.py")
kb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kb)


class IntakeTests(unittest.TestCase):
    def test_empty_dynamic_shell_is_not_read(self):
        result = kb.parse_page('<div id="app"></div><script>renderLater()</script>')
        self.assertEqual(result['status'], 'no_content')

    def test_article_has_body_but_not_full_claim(self):
        html = '<title>标题</title><script type="application/ld+json">' + json.dumps({"@type": "Article", "articleBody": "测试正文：四小时起订", "author": {"name": "测试作者"}}) + '</script>'
        result = kb.parse_page(html)
        self.assertEqual(result["status"], "partial")
        self.assertIn("四小时", result["body"])
        self.assertEqual(result["author"], "测试作者")

    def test_video_description_is_not_transcript(self):
        html = '<script type="application/ld+json">' + json.dumps({"@type": "VideoObject", "description": "这是描述，不是口播"}) + '</script>'
        result = kb.parse_page(html)
        self.assertEqual(result["status"], "metadata_only")
        self.assertFalse(result["body"])

    def test_gate_does_not_become_content(self):
        result = kb.parse_page('<title>登录页面</title><p>登录后查看完整内容</p>')
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["body"], "")

    def test_malformed_embedded_json_falls_back(self):
        result = kb.parse_page('<meta property="og:title" content="真实标题"><script type="application/ld+json">INVALID</script>')
        self.assertEqual(result["status"], "metadata_only")
        self.assertEqual(result["title"], "真实标题")

    def test_url_and_saved_query(self):
        for url in ('https://xiaohongshu.com.evil.example/a', 'http://127.0.0.1/', 'https://www.douyin.com:8080/a', 'https://user:pass@www.douyin.com/'):
            with self.assertRaises(ValueError):
                kb.platform_for(url)
        url = kb.extract_url('看这里 https://www.xiaohongshu.com/explore/abc?xsec_token=private 。')
        self.assertEqual(kb.clean_url(url), 'https://www.xiaohongshu.com/explore/abc')
        self.assertIn('modal_id=123', kb.clean_url('https://www.douyin.com/?modal_id=123&tracking=1'))

    def test_redirect_cannot_leave_platform(self):
        handler = kb.PlatformRedirect('douyin')
        with self.assertRaises(ValueError):
            handler.redirect_request(Request('https://v.douyin.com/a'), None, 302, '', {}, 'https://example.com/')

    def test_http_denial_is_not_success(self):
        with patch.object(kb, 'build_opener') as build:
            build.return_value.open.side_effect = HTTPError('https://www.douyin.com/', 403, 'Denied', {}, None)
            result = kb.fetch_page('https://www.douyin.com/')
        self.assertEqual(result['status'], 'blocked')
        self.assertNotIn('body', result)

    def test_dedup_version_and_search(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / 'input.txt'
            file.write_text('测试内容：小酌补贴', encoding='utf-8')
            a = kb.ingest(root, 'xiaohongshu', file)
            b = kb.ingest(root, 'xiaohongshu', file)
            self.assertEqual(a['record_id'], b['record_id'])
            self.assertTrue(b['deduplicated'])
            file.write_text('修改后的测试内容', encoding='utf-8')
            c = kb.ingest(root, 'xiaohongshu', file)
            self.assertNotEqual(a['record_id'], c['record_id'])
            self.assertEqual(len(list((root / 'research/records').glob('*.json'))), 2)
            self.assertTrue(kb.search(root, '小酌补贴'))

    def test_image_requires_ocr_and_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / 'fixture.png'
            file.write_bytes(b'test-media-fixture')
            result = kb.ingest(root, 'xiaohongshu', file, 'image')
            record = json.loads(Path(result['path']).read_text())
            self.assertEqual(record['status'], 'needs_ocr')
            self.assertEqual((root / record['local_media']).read_bytes(), file.read_bytes())
            self.assertEqual(record['excerpt'], '')

    def test_wrong_platform_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'a.txt'; file.write_text('test')
            with self.assertRaises(ValueError):
                kb.ingest(directory, 'douyin', file, url='https://www.xiaohongshu.com/explore/a')

    def test_official_export_failure_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / 'export.json'
            file.write_text(json.dumps({'data': {'error_code': 0, 'list': [{'title': '测试作品', 'item_id': 'fixture', 'share_url': 'https://www.douyin.com/video/123', 'statistics': {'digg_count': 3}}]}}))
            result = kb.import_douyin_export(root, file)
            record = json.loads(Path(result[0]['path']).read_text())
            self.assertEqual(record['metrics']['digg_count'], 3)
            self.assertEqual(record['status'], 'metadata_only')
            self.assertIsNone(record['metrics_observed_at'])
            file.write_text(json.dumps({'data': {'error_code': 10000, 'list': []}}))
            with self.assertRaises(ValueError):
                kb.import_douyin_export(root, file)


if __name__ == '__main__':
    unittest.main()
