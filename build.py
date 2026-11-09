"""Build a static Persian weekly from the Markdown subset in PUBLISHING.md."""
from datetime import date
from html import escape
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'dist'
SECTIONS = {'پژوهش‌ها': 'research', 'بینایی ماشین': 'vision', 'هوش مصنوعی': 'ai'}
LINK = re.compile(r'(!?)\[([^\]]+)\]\((https?://[^\s]+)\)')


def fa(value):
    return str(value).translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))


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
    sections = {}
    intro = []
    section = None
    story = None
    for line in lines[1:]:
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
    if list(sections) != list(SECTIONS):
        raise ValueError(f'{path}: missing or out-of-order section')
    for stories in sections.values():
        for item in stories:
            if not item['sources'] or not item['body']:
                raise ValueError(f'{path}: each article needs a summary and a source')
    return {'slug': date.fromisoformat(path.stem).isoformat(), 'title': lines[0][2:],
            'intro': ' '.join(intro), 'sections': sections}


def page(title, content):
    return f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} | دیده‌بان تصویر</title>
<link rel="stylesheet" href="/assets/site.css"></head><body><a class="skip" href="#main">رفتن به محتوا</a>
<header><nav><a class="brand" href="/">دیده‌بان تصویر<span aria-hidden="true">.</span></a>
<a href="/">آخرین شماره</a><a href="/archive/">آرشیو</a></nav></header>
<main id="main">{content}</main><footer>دیده‌بان تصویر · هفته‌نامهٔ بینایی ماشین و هوش مصنوعی</footer></body></html>'''


def issue_page(issue):
    parts = [f'<div class="intro"><p class="kicker">گزارش هفتگی</p><h1>{escape(issue["title"])}</h1>'
             f'<p class="deck">{escape(issue["intro"])}</p></div><nav class="sections" aria-label="بخش‌های شماره">']
    for title, stories in issue['sections'].items():
        parts.append(f'<a href="#{SECTIONS[title]}">{title} <small>{fa(len(stories))}</small></a>')
    parts.append('</nav>')
    for title, stories in issue['sections'].items():
        parts.append(f'<section id="{SECTIONS[title]}"><h2>{title}</h2>')
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
    issues = [parse(path) for path in sorted((ROOT / 'content/briefings').glob('*.md'), reverse=True)]
    if not issues:
        raise ValueError('At least one dated briefing is required')
    shutil.copytree(ROOT / 'assets', OUT / 'assets', dirs_exist_ok=True)
    for issue in issues:
        write_page(f'issues/{issue["slug"]}/index.html', issue_page(issue))
    write_page('index.html', issue_page(issues[0]))
    rows = ''.join(f'<li><a href="/issues/{item["slug"]}/"><strong>{escape(item["title"])}</strong>'
                   f'<span>خواندن گزارش ←</span></a></li>' for item in issues)
    write_page('archive/index.html', page('آرشیو', f'<div class="intro"><h1>آرشیو گزارش‌ها</h1></div><ul class="issues">{rows}</ul>'))
    print(f'Built {len(issues)} issue(s) in {OUT}')


if __name__ == '__main__':
    build()
