from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build
import shutil


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
        file.write_text('\n'.join([f'# {title}', 'لید', *(f'## {s}' for s in build.SECTIONS), *repo_items]))
        return file

    def test_full_day_and_same_day_weekly_archive(self):
        archive = '2026-11-09.md'
        (self.content / archive).write_text('\n'.join([
            '# ۱۲ تا ۱۸ آبان ۱۴۰۵', '<!-- weekly-end: 1405-08-18 -->',
            *(f'## {s}' for s in list(build.SECTIONS)[:-1]),
        ]))
        self.write_day(repos=5)
        self.write_day('1405-08-17')
        out = self.root / 'dist'
        with patch.object(build, 'ROOT', self.root), patch.object(build, 'OUT', out):
            build.build()
        html = (out / 'index.html').read_text()
        self.assertEqual(html, (out / 'issues/1405-08-18/index.html').read_text())
        self.assertEqual(html.count('<article>'), 5)
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
