"""Render daily Persian briefings and archived weekly editions."""
from html import escape
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'dist'
SECTIONS = {'پژوهش‌ها': 'research', 'بینایی ماشین': 'vision', 'هوش مصنوعی': 'ai', 'گیت‌هاب': 'github'}
MONTHS = 'فروردین اردیبهشت خرداد تیر مرداد شهریور مهر آبان آذر دی بهمن اسفند'.split()
ARCHIVE_DATE = re.compile(r'<!-- weekly-end: ([0-9]{4}-[0-9]{2}-[0-9]{2}) -->')
LINK = re.compile(r'(!?)\[([^\]]+)\]\((https?://[^\s]+)\)')


def fa(value):
    return str(value).translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))


def solar_title(key):
    if not re.fullmatch(r'1[34][0-9]{2}-[0-9]{2}-[0-9]{2}', key):
        raise ValueError(f'Expected a Solar Hijri edition date, got {key!r}')
    year, month, day = map(int, key.split('-'))
    if not (1 <= month <= 12 and 1 <= day <= (31 if month <= 6 else 30)):
        raise ValueError(f'Invalid Solar Hijri month/day in {key!r}')
    return f'{fa(day)} {MONTHS[month - 1]} {fa(year)}'


def source_line(line):
    found = LINK.fullmatch(line)
    if not found:
        return None
    image, label, url = found.groups()
    if not urlsplit(url).hostname:
        raise ValueError('Invalid source URL: ' + url)
    href, label = escape(url, quote=True), escape(label, quote=True)
    if image:
        return f'<figure><img loading="lazy" src="{href}" alt="{label}"></figure>'
    return f'<a class="source" rel="noopener noreferrer" href="{href}">{label} ↗</a>'


def parse(path):
    lines = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    if not lines or not lines[0].startswith('# '):
        raise ValueError(f'{path}: missing issue title')
    title = lines.pop(0)[2:]
    archived = ARCHIVE_DATE.fullmatch(lines[0]) if lines else None
    if archived:
        lines.pop(0)
    day_key = archived.group(1) if archived else path.stem
    full_date = solar_title(day_key)
    if not archived and title != full_date:
        raise ValueError(f'{path}: expected title {full_date!r}')
    sections = {}
    intro = []
    section = None
    story = None
    for line in lines:
        if line.startswith('## '):
            section = line[3:]
            if section not in SECTIONS or section in sections:
                raise ValueError(f'{path}: unexpected section {section}')
            sections[section] = []
            story = None
        elif line.startswith('### '):
            if section is None:
                raise ValueError(f'{path}: article before section')
            story = {'title': line[4:], 'body': [], 'sources': [], 'images': []}
            sections[section].append(story)
        elif section is None:
            intro.append(line)
        elif story is None:
            raise ValueError(f'{path}: expected article heading')
        else:
            link = source_line(line)
            if link:
                story['images' if line.startswith('!') else 'sources'].append(link)
            else:
                story['body'].append(line)
    expected = list(SECTIONS)[:-1] if archived else list(SECTIONS)
    if list(sections) != expected:
        raise ValueError(f'{path}: missing or out-of-order section')
    if len(sections.get('گیت‌هاب', [])) > 5:
        raise ValueError(f'{path}: at most five GitHub repositories per issue')
    for name, stories in sections.items():
        for item in stories:
            if not item['sources'] or not item['body']:
                raise ValueError(f'{path}: each article needs a summary and a source')
            if not archived and item['title'].partition(' · ')[0] not in (full_date, full_date.rsplit(' ', 1)[0]):
                raise ValueError(f'{path}: article date must match the issue date')
            if name == 'گیت‌هاب' and not any(re.search(r'href="https://github\.com/[^/?#"]+/[^/?#"]+/?["#?]', link) for link in item['sources']):
                raise ValueError(f'{path}: include the direct GitHub repository link')
    return {'slug': path.stem, 'day_key': day_key, 'daily': not archived, 'title': title,
            'intro': ' '.join(intro), 'sections': sections}


def page(title, content):
    return f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} | دیده‌بان تصویر</title>
<link rel="stylesheet" href="/assets/site.css"></head><body><a class="skip" href="#main">رفتن به محتوا</a>
<header><nav><a class="brand" href="/">دیده‌بان تصویر<span aria-hidden="true">.</span></a>
<a href="/">آخرین شماره</a><a href="/archive/">آرشیو</a></nav></header>
<main id="main">{content}</main><footer>دیده‌بان تصویر · خبرنامهٔ روزانهٔ بینایی ماشین و هوش مصنوعی</footer></body></html>'''


def issue_page(issue):
    edition = 'نسخهٔ آزمایشی روزانه' if issue.get('preview') else ('گزارش روزانه' if issue['daily'] else 'گزارش هفتگی آرشیوی')
    parts = [f'<div class="intro"><p class="kicker">{edition}</p><h1>{escape(issue["title"])}</h1>'
             f'<p class="deck">{escape(issue["intro"])}</p></div><nav class="sections" aria-label="بخش‌های شماره">']
    for title, stories in issue['sections'].items():
        parts.append(f'<a href="#{SECTIONS[title]}">{title} <small>{fa(len(stories))}</small></a>')
    parts.append('</nav>')
    for title, stories in issue['sections'].items():
        parts.append(f'<section id="{SECTIONS[title]}"><h2>{title}</h2>')
        if not stories:
            empty = 'این بخش در نمونهٔ آزمایشی مطلبی ندارد.' if issue.get('preview') else 'برای این روز مورد تازه و مرتبطی تأیید نشد.'
            parts.append(f'<p>{empty}</p>')
        for i, item in enumerate(stories, 1):
            body = ''.join(f'<p>{escape(p)}</p>' for p in item['body'])
            parts.append(f'<article><span class="number">{fa(i):s}</span><div><h3>{escape(item["title"])}</h3>'
                         f'{body}{"".join(item["images"])}<div class="links">{" ".join(item["sources"])}</div></div></article>')
        parts.append('</section>')
    parts.append('<a class="archive" href="/archive/">مشاهدهٔ آرشیو گزارش‌ها ←</a>')
    return page(issue['title'], ''.join(parts))


def write_page(relative_path, html):
    path = OUT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding='utf-8')


def build():
    issues = sorted((parse(path) for path in (ROOT / 'content/briefings').glob('*.md')),
                    key=lambda item: (item['day_key'], item['daily']), reverse=True)
    if not issues:
        raise ValueError('At least one dated briefing is required')
    shutil.copytree(ROOT / 'assets', OUT / 'assets', dirs_exist_ok=True)
    for issue in issues:
        write_page(f'issues/{issue["slug"]}/index.html', issue_page(issue))
    write_page('index.html', issue_page(issues[0]))
    previews = sorted((ROOT / 'content/previews').glob('*.md'), reverse=True)
    preview_rows = []
    for path in previews:
        preview = parse(path)
        preview['preview'] = True
        write_page(f'previews/{preview["slug"]}/index.html', issue_page(preview))
        preview_rows.append(f'<li><a href="/previews/{preview["slug"]}/">{escape(preview["title"])} · آزمایشی</a></li>')
    rows = ''.join(f'<li><a href="/issues/{item["slug"]}/"><strong>{escape(item["title"])}</strong>'
                   f'<span>خواندن گزارش ←</span></a></li>' for item in issues)
    preview_html = '<h2>نسخه‌های آزمایشی</h2><ul class="issues">' + ''.join(preview_rows) + '</ul>' if preview_rows else ''
    write_page('archive/index.html', page('آرشیو', f'<div class="intro"><h1>آرشیو گزارش‌ها</h1></div><ul class="issues">{rows}</ul>{preview_html}'))
    print(f'Built {len(issues)} issue(s) in {OUT}')


if __name__ == '__main__':
    build()
