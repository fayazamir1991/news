from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build
import shutil
import json


class DailyBriefings(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.content = self.root / 'content' / 'briefings'
        self.content.mkdir(parents=True)
        (self.root / 'assets').mkdir()
        shutil.copytree(build.ROOT / 'pwa', self.root / 'pwa')

    def write_day(self, key='1405-08-18', repos=0):
        title = build.solar_title(key)
        date_label = title.rsplit(' ', 1)[0]
        repo_items = [f'### {date_label} · test/repo{i}\nتوضیح\n[مخزن](https://github.com/test/repo{i})' for i in range(repos)]
        file = self.content / f'{key}.md'
        file.write_text('\n'.join([f'# {title}', 'لید', *(f'## {s}' for s in build.NEWS_SECTIONS), *repo_items]))
        return file

    def test_full_day_and_same_day_weekly_archive(self):
        archive = '2026-11-09.md'
        (self.content / archive).write_text('\n'.join([
            '# ۱۲ تا ۱۸ آبان ۱۴۰۵', '<!-- weekly-end: 1405-08-18 -->',
            *(f'## {s}' for s in list(build.NEWS_SECTIONS)[:-1]),
        ]))
        self.write_day(repos=5)
        self.write_day('1405-08-17')
        out = self.root / 'dist'
        with patch.object(build, 'ROOT', self.root), patch.object(build, 'OUT', out):
            build.build()
        html = (out / 'index.html').read_text()
        self.assertEqual(html, (out / 'issues/1405-08-18/index.html').read_text())
        self.assertEqual(html.count('<article id="item-'), 5)
        self.assertIn('id="github"', html)
        self.assertIn('مورد تازه و مرتبطی تأیید نشد', html)
        self.assertIn('۱۸ آبان ۱۴۰۵', html)
        old = (out / 'issues/2026-11-09/index.html').read_text()
        self.assertIn('گزارش هفتگی آرشیوی', old)
        self.assertNotIn('نوامبر', old)
        listing = (out / 'archive/index.html').read_text()
        self.assertLess(listing.index('/1405-08-18/'), listing.index('/2026-11-09/'))
        self.assertLess(listing.index('/2026-11-09/'), listing.index('/1405-08-17/'))

    def test_repository_limit(self):
        with self.assertRaisesRegex(ValueError, 'five GitHub'):
            build.parse(self.write_day(repos=6))

    def survey_block(self):
        return '\n'.join([
            '## مقالهٔ مروری روز', '### ۱۸ آبان · درس ردیابی',
            '#### توضیح و تحلیل مقاله', 'تحلیل خواندن کامل مقاله',
            '#### ترجمهٔ کامل مقدمه', 'ترجمهٔ مقدمه <script>نمونه</script>',
            '#### ترجمهٔ کامل نتیجه‌گیری', 'ترجمهٔ نتیجه‌گیری',
            '[مقاله](https://arxiv.org/abs/2506.13457v1)', '',
        ])

    def test_daily_survey_first_with_subsections_and_stable_existing_bookmarks(self):
        path = self.write_day(repos=1)
        old = build.parse(path)
        existing = build.story_record(old, 'گیت‌هاب', old['sections']['گیت‌هاب'][0])
        path.write_text(path.read_text().replace('## پژوهش‌ها', self.survey_block() + '\n## پژوهش‌ها'))
        issue = build.parse(path)
        self.assertEqual(list(issue['sections']), list(build.SECTIONS))
        html = build.issue_page(issue)
        self.assertLess(html.index('<section id="survey"'), html.index('<section id="research"'))
        self.assertIn('<h4>ترجمهٔ کامل مقدمه</h4>', html)
        self.assertIn('&lt;script&gt;نمونه&lt;/script&gt;', html)
        self.assertNotIn('#### ', html)
        self.assertEqual(existing, build.story_record(issue, 'گیت‌هاب', issue['sections']['گیت‌هاب'][0]))
        review = build.story_record(issue, build.SURVEY_SECTION, issue['sections'][build.SURVEY_SECTION][0])
        self.assertNotIn('#### ', review['summary'])

    def test_rejects_survey_after_news_or_multiple_surveys(self):
        path = self.write_day()
        content = path.read_text()
        path.write_text(content + '\n' + self.survey_block())
        with self.assertRaisesRegex(ValueError, 'out-of-order'):
            build.parse(path)
        doubled = self.survey_block().replace('## مقالهٔ مروری روز\n', '')
        path.write_text(content.replace('## پژوهش‌ها', self.survey_block() + doubled + '\n## پژوهش‌ها'))
        with self.assertRaisesRegex(ValueError, 'one daily survey'):
            build.parse(path)

    def test_rejects_missing_or_empty_survey_translation(self):
        path = self.write_day()
        content = path.read_text()
        for broken in [self.survey_block().replace('#### ترجمهٔ کامل مقدمه', '#### مقدمه'),
                       self.survey_block().replace('ترجمهٔ نتیجه‌گیری\n', '')]:
            with self.subTest(block=broken):
                path.write_text(content.replace('## پژوهش‌ها', broken + '\n## پژوهش‌ها'))
                with self.assertRaisesRegex(ValueError, 'survey'):
                    build.parse(path)

    def test_bookmark_ids_and_public_catalog(self):
        path = self.write_day(repos=1)
        out = self.root / 'dist'
        with patch.object(build, 'ROOT', self.root), patch.object(build, 'OUT', out):
            build.build()
            first = json.loads((out / 'items.json').read_text())
            key, record = next(iter(first.items()))
            self.assertRegex(key, r'^[a-f0-9]{64}$')
            self.assertEqual(record['url'], f'/issues/1405-08-18/#item-{key}')
            self.assertNotIn('user_id', record)
            self.assertIn('id="bookmark-list"', (out / 'bookmarks/index.html').read_text())
            self.assertTrue((out / 'auth/callback/index.html').exists())
            path.write_text(path.read_text().replace('توضیح', 'توضیح تازه'))
            build.build()
            self.assertEqual(list(first), list(json.loads((out / 'items.json').read_text())))

    def test_refuses_secret_client_key(self):
        self.write_day()
        with patch.object(build, 'ROOT', self.root), patch.object(build, 'OUT', self.root / 'dist'), patch.dict('os.environ', {
            'SUPABASE_URL': 'https://example.supabase.co', 'SUPABASE_PUBLISHABLE_KEY': 'sb_secret_do-not-expose'
        }):
            with self.assertRaisesRegex(ValueError, 'publishable key'):
                build.build()

    def test_mismatched_story_day(self):
        path = self.write_day(repos=1)
        path.write_text(path.read_text().replace('### ۱۸ آبان', '### ۱۷ آبان'))
        with self.assertRaisesRegex(ValueError, 'article date'):
            build.parse(path)

    def test_requires_direct_repository_link(self):
        path = self.write_day(repos=1)
        path.write_text(path.read_text().replace('github.com/test/repo0', 'example.org/news'))
        with self.assertRaisesRegex(ValueError, 'direct GitHub'):
            build.parse(path)

    def test_last_days_of_solar_months(self):
        self.assertEqual(build.solar_title('1405-06-31'), '۳۱ شهریور ۱۴۰۵')
        self.assertEqual(build.solar_title('1405-01-01'), '۱ فروردین ۱۴۰۵')
        with self.assertRaises(ValueError):
            build.solar_title('1405-08-31')

    def test_execution_metadata_is_optional_and_preserves_bookmarks(self):
        path = self.write_day(repos=1)
        before = build.parse(path)
        self.assertNotIn('execution-summary', build.issue_page(before))
        path.with_suffix('.execution.json').write_text(json.dumps({
            'schema_version': 1, 'models': ['test-model'], 'model_source': 'runner_metadata',
            'tokens': {'input': 15000, 'output': 5000, 'total': 20000,
                       'source': 'provider_usage', 'coverage': 'full_run'},
        }))
        after = build.parse(path)
        html = build.issue_page(after)
        self.assertIn('اجراشده با مدل test-model', html)
        self.assertIn('مصرف توکن: ۲۰٬۰۰۰', html)
        self.assertGreater(html.index('class="execution-summary"'), html.index('id="github"'))
        self.assertEqual(build.story_record(before, 'گیت‌هاب', before['sections']['گیت‌هاب'][0])['id'],
                         build.story_record(after, 'گیت‌هاب', after['sections']['گیت‌هاب'][0])['id'])

    def test_execution_metadata_omits_unknowns_and_marks_partial_usage(self):
        path = self.write_day()
        metadata = path.with_suffix('.execution.json')
        metadata.write_text(json.dumps({'schema_version': 1}))
        self.assertNotIn('execution-summary', build.issue_page(build.parse(path)))
        metadata.write_text(json.dumps({'schema_version': 1, 'tokens': {
            'input': 20, 'output': 5, 'total': 25, 'source': 'runner_usage', 'coverage': 'partial_run'}}))
        html = build.issue_page(build.parse(path))
        self.assertIn('مصرف ثبت‌شدهٔ بخشی از اجرا: ۲۵', html)
        self.assertNotIn('اجراشده با مدل', html)
        self.assertNotIn('در دسترس نیست', html)

    def test_execution_metadata_rejects_false_totals_and_unverified_models(self):
        path = self.write_day()
        metadata = path.with_suffix('.execution.json')
        for counts in [(10, 5, 20), (True, 5, 6), (-1, 5, 4), (None, 5, 5)]:
            with self.subTest(counts=counts):
                metadata.write_text(json.dumps({'schema_version': 1, 'tokens': {
                    **dict(zip(('input', 'output', 'total'), counts)),
                    'source': 'provider_usage', 'coverage': 'full_run'}}))
                with self.assertRaisesRegex(ValueError, 'token counts'):
                    build.parse(path)
        metadata.write_text(json.dumps({'schema_version': 1, 'models': ['example']}))
        with self.assertRaisesRegex(ValueError, 'provenance'):
            build.parse(path)

    def test_execution_metadata_escapes_model_text(self):
        path = self.write_day()
        path.with_suffix('.execution.json').write_text(json.dumps({
            'schema_version': 1, 'models': ['<script>bad</script>'], 'model_source': 'provider_response'}))
        html = build.issue_page(build.parse(path))
        self.assertIn('&lt;script&gt;bad&lt;/script&gt;', html)
        self.assertNotIn('<script>bad</script>', html)


    def dedicated_survey(self):
        path = self.write_day(repos=1)
        metadata = {'arxiv_id': '2506.13457', 'first_issue': '1405-08-18', 'summary': 'موضوع و ارزش خواندن مقاله'}
        directory = self.root / 'content/surveys'
        directory.mkdir(parents=True, exist_ok=True)
        survey = directory / '2506.13457.md'
        survey.write_text('# درس ردیابی\n<!-- survey: ' + json.dumps(metadata, ensure_ascii=False) + ' -->\n' + '\n'.join('## ' + heading + '\nمتن کامل ' + heading for heading in build.SURVEY_HEADINGS) + '\n[مقاله](https://arxiv.org/abs/2506.13457v1)')
        inline = self.survey_block()
        path.write_text(path.read_text().replace('## پژوهش‌ها', inline + '\n## پژوهش‌ها'))
        issue = build.parse(path)
        before = build.story_record(issue, build.SURVEY_SECTION, issue['sections'][build.SURVEY_SECTION][0])
        teaser = '## مقالهٔ مروری روز\n### ۱۸ آبان · درس ردیابی\n' + metadata['summary'] + '\n[مقاله](https://arxiv.org/abs/2506.13457v1)\n[مطالعهٔ مقاله](/surveys/2506.13457/)\n'
        path.write_text(path.read_text().replace(inline, teaser))
        return path, survey, before

    def test_dedicated_survey_teaser_archive_and_stable_id(self):
        path, survey, before = self.dedicated_survey()
        out = self.root / 'dist'
        with patch.object(build, 'ROOT', self.root), patch.object(build, 'OUT', out):
            build.build()
        home = (out / 'index.html').read_text()
        full = (out / 'surveys/2506.13457/index.html').read_text()
        self.assertNotIn('متن کامل', home)
        self.assertNotIn('ترجمهٔ کامل مقدمه', home)
        self.assertIn('متن کامل ترجمهٔ کامل مقدمه', full)
        self.assertIn('موضوع و ارزش خواندن مقاله', home)
        self.assertIn('موضوع و ارزش خواندن مقاله', (out / 'surveys/index.html').read_text())
        records = json.loads((out / 'items.json').read_text())
        self.assertIn(before['id'], records)
        self.assertEqual(records[before['id']]['url'], '/surveys/2506.13457/#item-' + before['id'])
        self.assertIn('data-item-id="' + before['id'] + '"', full)
        self.assertEqual(len(records), 2)
        self.assertIn('id="sign-in"', (out / 'account/index.html').read_text())
        self.assertNotIn('id="sign-in"', home)

    def test_rejects_missing_or_mismatched_dedicated_survey(self):
        path, survey, _ = self.dedicated_survey()
        valid = survey.read_text()
        for broken in [valid.replace('موضوع و ارزش خواندن مقاله', 'خلاصهٔ متفاوت'), valid.replace('2506.13457v1', '2506.13457v2')]:
            survey.write_text(broken)
            with patch.object(build, 'ROOT', self.root), patch.object(build, 'OUT', self.root / 'dist'):
                with self.assertRaisesRegex(ValueError, 'survey reference'):
                    build.build()
        survey.unlink()
        with patch.object(build, 'ROOT', self.root), patch.object(build, 'OUT', self.root / 'dist'):
            with self.assertRaisesRegex(ValueError, 'survey reference'):
                build.build()

    def test_validates_complete_survey_and_single_teaser_paragraph(self):
        path, survey, _ = self.dedicated_survey()
        survey.write_text(survey.read_text().replace('متن کامل ترجمهٔ کامل مقدمه', ''))
        with self.assertRaisesRegex(ValueError, 'complete translations'):
            build.parse_survey(survey)
        path.write_text(path.read_text().replace('موضوع و ارزش خواندن مقاله', 'موضوع و ارزش خواندن مقاله\nبند اضافی'))
        with self.assertRaisesRegex(ValueError, 'one paragraph'):
            build.parse(path)

    def test_internal_survey_links_and_mobile_navigation(self):
        self.assertIn('href="/surveys/2506.13457/"', build.source_line('[مقاله](/surveys/2506.13457/)'))
        for url in ['/surveys/../', '/surveys/a/../../', '/surveys/evil?x=1/', '/surveys/evil#x/', '/surveys/a%2f../']:
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, 'Invalid survey'):
                build.source_line('[مقاله](' + url + ')')
        html = build.navigation('surveys', mobile=True)
        destinations = ['/archive/', '/surveys/', '/', '/account/', '/bookmarks/']
        import re
        self.assertEqual(re.findall(r'href="([^"]+)"', html), destinations)
        self.assertEqual(re.findall(r'<span>(.*?)</span>', html), ['آرشیو', 'مروری‌ها', 'خانه', 'حساب', 'ذخیره‌ها'])
        self.assertEqual(html.count('aria-current="page"'), 1)
        self.assertIn('aria-label="مقالات مروری" aria-current="page"', html)
