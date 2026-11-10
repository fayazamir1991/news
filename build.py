"""Render daily Persian briefings and archived weekly editions."""
from html import escape
from pathlib import Path
import re
import shutil
import hashlib
import json
import os
from urllib.parse import urlsplit
from legal import PRIVACY, TERMS

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


def execution_summary(path):
    """Render only verified runner/provider metadata; never estimate missing usage."""
    sidecar = path.with_suffix('.execution.json')
    if not sidecar.exists():
        return ''
    data = json.loads(sidecar.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise ValueError(f'{sidecar}: unsupported execution metadata')
    parts = []
    models = data.get('models', [])
    if not isinstance(models, list) or any(not isinstance(m, str) or not m.strip() or len(m) > 128 for m in models):
        raise ValueError(f'{sidecar}: expected verified model names')
    if models:
        if data.get('model_source') not in ('provider_response', 'runner_metadata'):
            raise ValueError(f'{sidecar}: model provenance required')
        parts.append('اجراشده با مدل ' + '، '.join(dict.fromkeys(models)))
    tokens = data.get('tokens')
    if tokens is not None:
        if not isinstance(tokens, dict):
            raise ValueError(f'{sidecar}: invalid token usage')
        values = [tokens.get(k) for k in ('input', 'output', 'total')]
        if any(type(v) is not int or v < 0 for v in values) or values[0] + values[1] != values[2]:
            raise ValueError(f'{sidecar}: inconsistent token counts')
        if tokens.get('source') not in ('provider_usage', 'runner_usage') or tokens.get('coverage') not in ('full_run', 'partial_run'):
            raise ValueError(f'{sidecar}: usage provenance and coverage required')
        count = lambda value: fa(f'{value:,}').replace(',', '٬')
        label = 'مصرف توکن' if tokens['coverage'] == 'full_run' else 'مصرف ثبت‌شدهٔ بخشی از اجرا'
        parts.append(f'{label}: {count(values[2])} (ورودی: {count(values[0])}، خروجی: {count(values[1])})')
    return ' · '.join(parts)


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
            'intro': ' '.join(intro), 'sections': sections, 'execution': execution_summary(path)}


def page(title, content):
    return f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} | دیده‌بان تصویر</title>
<meta name="theme-color" content="#08665a">
<meta name="google-site-verification" content="aqEiW6dBV0-dlx_m3a5RTEcv61kPb4-rVtOvdC0XI8U">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="دیده‌بان تصویر">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="icon" type="image/png" href="/icons/icon-192.png">
<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png">
<script src="/assets/app.js" defer></script>
<script src="/assets/account-config.js" defer></script>
<script src="/assets/account.js" defer></script>
<link rel="stylesheet" href="/assets/site.css"></head><body><a class="skip" href="#main">رفتن به محتوا</a>
<header><nav><a class="brand" href="/"><img src="/icons/icon-192.png" width="38" height="38" alt="">دیده‌بان تصویر</a>
<a href="/">آخرین شماره</a><a href="/archive/">آرشیو</a><a href="/bookmarks/">ذخیره‌شده‌ها</a>
<button id="sign-in">ورود با Google</button><span id="account-name" hidden></span><button id="sign-out" hidden>خروج</button>
<button id="install-app" hidden>نصب روی گوشی</button></nav></header>
<p id="account-status" role="status" hidden></p>
<p id="install-help" hidden>در Safari دکمهٔ اشتراک‌گذاری را بزنید و «Add to Home Screen» را انتخاب کنید.</p>
<p id="offline-status" role="status" hidden>آفلاین هستید؛ نسخهٔ ذخیره‌شده را می‌خوانید.</p>
<main id="main">{content}</main><footer>دیده‌بان تصویر · خبرنامهٔ روزانهٔ بینایی ماشین و هوش مصنوعی
<nav aria-label="اطلاعات سایت"><a href="/privacy/">حریم خصوصی</a> · <a href="/terms/">شرایط استفاده</a></nav></footer></body></html>'''


def story_record(issue, section, item):
    source = re.search(r'href="([^"]+)"', item['sources'][0]).group(1)
    key = hashlib.sha256(f'{issue["slug"]}|{section}|{source}'.encode()).hexdigest()
    return {'id': key, 'title': item['title'], 'summary': ' '.join(item['body']),
            'section': section, 'issue': issue['title'],
            'url': f'/issues/{issue["slug"]}/#item-{key}'}


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
            record = story_record(issue, title, item)
            body = ''.join(f'<p>{escape(p)}</p>' for p in item['body'])
            parts.append(f'<article id="item-{record["id"]}"><span class="number">{fa(i):s}</span><div><h3>{escape(item["title"])}</h3>'
                         f'{body}{"".join(item["images"])}<div class="links">{" ".join(item["sources"])}'
                         f'<button class="bookmark" data-item-id="{record["id"]}" aria-pressed="false" aria-label="ذخیرهٔ {escape(item["title"], quote=True)}">ذخیره</button></div></div></article>')
        parts.append('</section>')
    if issue.get('execution'):
        parts.append(f'<aside class="execution-summary" aria-label="مشخصات اجرای گزارش"><p>{escape(issue["execution"])}</p></aside>')
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
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / 'assets', OUT / 'assets', dirs_exist_ok=True)
    shutil.copytree(ROOT / 'pwa', OUT, dirs_exist_ok=True)
    defaults_path = ROOT / 'auth-public.json'
    defaults = json.loads(defaults_path.read_text()) if defaults_path.exists() else {}
    auth_url = (os.environ.get('SUPABASE_URL') or defaults.get('url', '')).strip()
    public_key = (os.environ.get('SUPABASE_PUBLISHABLE_KEY') or defaults.get('publishableKey', '')).strip()
    if bool(auth_url) != bool(public_key):
        raise ValueError('Set both SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY')
    if auth_url and (urlsplit(auth_url).scheme != 'https' or not urlsplit(auth_url).hostname):
        raise ValueError('SUPABASE_URL must use HTTPS')
    if public_key and not public_key.startswith('sb_publishable_'):
        raise ValueError('Only a Supabase publishable key may be included in the public site')
    config = json.dumps({'url': auth_url, 'publishableKey': public_key}, ensure_ascii=False)
    (OUT / 'assets/account-config.js').write_text('window.DIDEBAN_AUTH = ' + config + ';\n')
    catalog = {}
    for issue in issues:
        write_page(f'issues/{issue["slug"]}/index.html', issue_page(issue))
        for section, items in issue['sections'].items():
            for item in items:
                record = story_record(issue, section, item)
                if record['id'] in catalog:
                    raise ValueError('Duplicate article source in the same issue section')
                catalog[record['id']] = record
    (OUT / 'items.json').write_text(json.dumps(catalog, ensure_ascii=False))
    write_page('bookmarks/index.html', page('ذخیره‌شده‌ها', '<div class="intro"><h1>ذخیره‌شده‌ها</h1>'
               '<p id="bookmarks-message">برای دیدن لیست اختصاصی خود وارد حساب Google شوید.</p></div><div id="bookmark-list"></div>'))
    write_page('auth/callback/index.html', page('ورود به حساب', '<div class="intro"><h1>ورود به حساب</h1><p>در حال بررسی ورود…</p></div>'))
    write_page('privacy/index.html', page('سیاست حریم خصوصی', PRIVACY))
    write_page('terms/index.html', page('شرایط استفاده', TERMS))
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
    paths = sorted(path for path in OUT.rglob('*') if path.is_file() and path.name != 'sw.js')
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(OUT).as_posix().encode())
        digest.update(path.read_bytes())
    shell = ['/', '/archive/', '/offline.html', '/manifest.webmanifest']
    shell += ['/' + path.relative_to(OUT).as_posix() for path in paths if path.parts[-2] in ('assets', 'icons')]
    worker = (OUT / 'sw.js').read_text().replace('__VERSION__', digest.hexdigest()[:20]).replace('__PRECACHE__', json.dumps(shell))
    (OUT / 'sw.js').write_text(worker)
    print(f'Built {len(issues)} issue(s) in {OUT}')


if __name__ == '__main__':
    build()
