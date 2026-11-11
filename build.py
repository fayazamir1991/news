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
NEWS_SECTIONS = {'پژوهش‌ها': 'research', 'بینایی ماشین': 'vision', 'هوش مصنوعی': 'ai', 'گیت‌هاب': 'github'}
SURVEY_SECTION = 'مقالهٔ مروری روز'
SURVEY_HEADINGS = ('توضیح و تحلیل مقاله', 'ترجمهٔ کامل مقدمه', 'ترجمهٔ کامل نتیجه‌گیری')
SECTIONS = {SURVEY_SECTION: 'survey', **NEWS_SECTIONS}
MONTHS = 'فروردین اردیبهشت خرداد تیر مرداد شهریور مهر آبان آذر دی بهمن اسفند'.split()
ARCHIVE_DATE = re.compile(r'<!-- weekly-end: ([0-9]{4}-[0-9]{2}-[0-9]{2}) -->')
LINK = re.compile(r'(!?)\[([^\]]+)\]\((https?://[^\s]+|/surveys/[^\s]+)\)')


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
    if url.startswith('/'):
        if image or not re.fullmatch(r'/surveys/[a-z0-9][a-z0-9.-]*/', url) or '..' in url:
            raise ValueError('Invalid survey link: ' + url)
        return f'<a class="survey-link" href="{escape(url, quote=True)}">{escape(label)} ←</a>'
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
        elif section == SURVEY_SECTION and re.match(r'^(ارسال به arXiv|انتشار مقاله): ', line):
            if story.get('paper_date_line'):
                raise ValueError(f'{path}: duplicate survey paper date')
            story['paper_date_line'] = line
        else:
            link = source_line(line)
            if link:
                story['images' if line.startswith('!') else 'sources'].append(link)
                if 'class="survey-link"' in link:
                    slug = re.search(r'href="/surveys/([^/]+)/"', link).group(1)
                    if section != SURVEY_SECTION or story.get('survey_slug'):
                        raise ValueError(f'{path}: unexpected or duplicate survey link')
                    story['survey_slug'] = slug
            else:
                story['body'].append(line)
    expected = (list(NEWS_SECTIONS)[:-1] if archived else
                list(SECTIONS) if SURVEY_SECTION in sections else list(NEWS_SECTIONS))
    if list(sections) != expected:
        raise ValueError(f'{path}: missing or out-of-order section')
    if len(sections.get(SURVEY_SECTION, [])) > 1:
        raise ValueError(f'{path}: at most one daily survey')
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
            if name == SURVEY_SECTION and item.get('survey_slug'):
                if len(item['body']) != 1 or item['body'][0].startswith('#'):
                    raise ValueError(f'{path}: survey teaser needs exactly one paragraph')
                if not re.search(r'href="https://arxiv.org/(abs|html|pdf)/', item['sources'][0]):
                    raise ValueError(f'{path}: keep the original arXiv source first')
            elif name == SURVEY_SECTION:
                headings = [line[5:] for line in item['body'] if line.startswith('#### ')]
                if headings != list(SURVEY_HEADINGS):
                    raise ValueError(f'{path}: survey needs analysis and two complete translation headings')
                for index, line in enumerate(item['body']):
                    if line.startswith('#### ') and (index + 1 == len(item['body']) or item['body'][index + 1].startswith('#### ')):
                        raise ValueError(f'{path}: empty survey subsection')
    return {'slug': path.stem, 'day_key': day_key, 'daily': not archived, 'title': title,
            'intro': ' '.join(intro), 'sections': sections, 'execution': execution_summary(path)}



def parse_survey(path):
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]*', path.stem) or '..' in path.stem:
        raise ValueError(f'{path}: invalid survey slug')
    lines = [line.strip() for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if len(lines) < 3 or not lines[0].startswith('# '):
        raise ValueError(f'{path}: missing survey title')
    metadata = re.fullmatch(r'<!-- survey: (.+) -->', lines[1])
    if not metadata:
        raise ValueError(f'{path}: missing survey metadata')
    data = json.loads(metadata.group(1))
    if not isinstance(data, dict) or not all(isinstance(data.get(k), str) and data[k].strip() for k in ('arxiv_id', 'first_issue', 'summary', 'paper_date', 'paper_date_kind', 'paper_date_source')):
        raise ValueError(f'{path}: invalid survey metadata')
    if data['arxiv_id'] != path.stem or any(c in data['summary'] for c in '\r\n'):
        raise ValueError(f'{path}: invalid survey identity or summary')
    solar_title(data['first_issue'])
    solar_title(data['paper_date'])
    if data['paper_date_kind'] not in ('submitted', 'published'):
        raise ValueError(f'{path}: invalid survey paper date kind')
    if urlsplit(data['paper_date_source']).scheme != 'https' or not urlsplit(data['paper_date_source']).hostname:
        raise ValueError(f'{path}: invalid survey paper date source')
    sections, sources, images = {}, [], []
    current = None
    for line in lines[2:]:
        if line.startswith('## '):
            current = line[3:]
            if current not in SURVEY_HEADINGS or current in sections:
                raise ValueError(f'{path}: unexpected survey subsection')
            sections[current] = []
        else:
            link = source_line(line)
            if link:
                if 'class="survey-link"' in link:
                    raise ValueError(f'{path}: survey sources must be external')
                (images if line.startswith('!') else sources).append(link)
            elif current:
                sections[current].append(line)
            else:
                raise ValueError(f'{path}: paragraph before survey subsection')
    if list(sections) != list(SURVEY_HEADINGS) or not all(sections.values()) or not sources:
        raise ValueError(f'{path}: survey needs analysis, complete translations and sources')
    if not any(f'href="{escape(data["paper_date_source"], quote=True)}"' in source for source in sources):
        raise ValueError(f'{path}: include the primary survey date source')
    return {**data, 'slug': path.stem, 'title': lines[0][2:], 'sections': sections, 'sources': sources, 'images': images}


NAV_ITEMS = (
    ('archive', '/archive/', 'آرشیو', 'آرشیو گزارش‌ها', '<rect x="4" y="4" width="16" height="4" rx="1"/><path d="M5 8v12h14V8M9 12h6"/>'),
    ('surveys', '/surveys/', 'مروری‌ها', 'مقالات مروری', '<path d="M12 5v15M12 5C8 2 3 4 3 4v15s5-2 9 1c4-3 9-1 9-1V4s-5-2-9 1Z"/>'),
    ('home', '/', 'خانه', 'خانه؛ آخرین شماره', '<path d="m3 10 9-7 9 7M5 9v12h14V9M9 21v-8h6v8"/>'),
    ('account', '/account/', 'حساب', 'حساب کاربری', '<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>'),
    ('bookmarks', '/bookmarks/', 'ذخیره‌ها', 'ذخیره‌شده‌ها', '<path d="M6 3h12v18l-6-4-6 4Z"/>'),
)


def navigation(active, mobile=False):
    links = []
    for key, url, short, full, icon in NAV_ITEMS:
        current = ' aria-current="page"' if key == active else ''
        graphic = f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{icon}</svg>' if mobile else ''
        label = short if mobile else ('آخرین شماره' if key == 'home' else full)
        links.append(f'<a href="{url}" aria-label="{full}"{current}>{graphic}<span>{label}</span></a>')
    return ''.join(links)


def page(title, content, active=None):
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
<header><nav aria-label="ناوبری اصلی"><a class="brand" href="/"><img src="/icons/icon-192.png" width="38" height="38" alt="">دیده‌بان تصویر</a>
<div class="desktop-nav">{navigation(active)}</div></nav></header>
<nav class="bottom-nav" aria-label="ناوبری موبایل">{navigation(active, mobile=True)}</nav>
<p id="account-status" role="status" hidden></p>
<p id="install-help" hidden>در Safari دکمهٔ اشتراک‌گذاری را بزنید و «Add to Home Screen» را انتخاب کنید.</p>
<p id="offline-status" role="status" hidden>آفلاین هستید؛ نسخهٔ ذخیره‌شده را می‌خوانید.</p>
<main id="main">{content}</main><footer>دیده‌بان تصویر · خبرنامهٔ روزانهٔ بینایی ماشین و هوش مصنوعی
<nav aria-label="اطلاعات سایت"><a href="/privacy/">حریم خصوصی</a> · <a href="/terms/">شرایط استفاده</a></nav></footer></body></html>'''


def story_record(issue, section, item):
    source = re.search(r'href="([^"]+)"', item['sources'][0]).group(1)
    key = hashlib.sha256(f'{issue["slug"]}|{section}|{source}'.encode()).hexdigest()
    summary = ' '.join(p for p in item['body'] if section != SURVEY_SECTION or not p.startswith('#### '))
    return {'id': key, 'title': item['title'], 'summary': summary,
            'section': section, 'issue': issue['title'],
            'url': (f'/surveys/{item["survey_slug"]}/#item-{key}' if item.get('survey_slug') else f'/issues/{issue["slug"]}/#item-{key}')}


ACTION_ICONS = {
    'bookmark': '<path d="M6 3h12v18l-6-4-6 4Z"/>',
    'like': '<path d="M7 10v11H3V10h4ZM7 10l4-8a3 3 0 0 1 3 3v4h5a2 2 0 0 1 2 2.4l-1.5 7A3 3 0 0 1 16.6 21H7"/>',
    'dislike': '<path d="M7 14V3H3v11h4ZM7 14l4 8a3 3 0 0 0 3-3v-4h5a2 2 0 0 0 2-2.4l-1.5-7A3 3 0 0 0 16.6 3H7"/>',
}


def action_icon(name):
    return (f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ACTION_ICONS[name]}</svg>')


def item_actions(item_id):
    return (f'<div class="item-actions" role="group" aria-label="ذخیره و علاقه به این مطلب">'
            f'<button class="bookmark icon-action" data-item-id="{item_id}" aria-pressed="false" aria-label="ذخیرهٔ مطلب" title="ذخیرهٔ مطلب">{action_icon("bookmark")}</button>'
            f'<button class="reaction icon-action" data-item-id="{item_id}" data-value="1" aria-pressed="false" aria-label="لایک" title="لایک">{action_icon("like")}</button>'
            f'<button class="reaction icon-action" data-item-id="{item_id}" data-value="-1" aria-pressed="false" aria-label="دیسلایک" title="دیسلایک">{action_icon("dislike")}</button></div>')


def paper_date_html(label):
    return escape(label).replace('arXiv', '<bdi dir="ltr">arXiv</bdi>')


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
            body = ''.join(f'<h4>{escape(p[5:])}</h4>' if title == SURVEY_SECTION and p.startswith('#### ')
                           else f'<p>{escape(p)}</p>' for p in item['body'])
            heading = f'<a href="/surveys/{item["survey_slug"]}/">{escape(item["title"])}</a>' if item.get('survey_slug') else escape(item['title'])
            visible_sources = [link for link in item['sources'] if 'class="survey-link"' in link] if item.get('survey_slug') else item['sources']
            paper_date = f'<p class="survey-dates" dir="rtl"><span>{paper_date_html(item["paper_date_line"])}</span></p>' if item.get('paper_date_line') else ''
            parts.append(f'<article id="item-{record["id"]}"><span class="number">{fa(i):s}</span><div><h3>{heading}</h3>'
                         f'{paper_date}{body}{"".join(item["images"])}<div class="links">{" ".join(visible_sources)}'
                         f'</div>{item_actions(record["id"])}</div></article>')
        parts.append('</section>')
    if issue.get('execution'):
        parts.append(f'<aside class="execution-summary" aria-label="مشخصات اجرای گزارش"><p>{escape(issue["execution"])}</p></aside>')
    parts.append('<a class="archive" href="/archive/">مشاهدهٔ آرشیو گزارش‌ها ←</a>')
    return page(issue['title'], ''.join(parts), 'home')


def survey_date_label(survey):
    label = 'ارسال به arXiv' if survey['paper_date_kind'] == 'submitted' else 'انتشار مقاله'
    return f'{label}: {solar_title(survey["paper_date"])}'


def survey_page(survey, record):
    contents = ''.join(f'<a href="#part-{i}">{escape(heading)}</a>' for i, heading in enumerate(SURVEY_HEADINGS))
    sections = ''.join(f'<section id="part-{i}"><h2>{escape(heading)}</h2>' + ''.join(f'<p>{escape(p)}</p>' for p in paragraphs) + '</section>' for i, (heading, paragraphs) in enumerate(survey['sections'].items()))
    tools = f'<div class="survey-tools"><nav class="survey-contents" aria-label="بخش‌های مقاله"><p class="tool-label">در این مقاله</p><div class="tool-links">{contents}</div></nav>'
    tools += f'<aside class="survey-sources" aria-label="لینک‌های مستقیم مقاله"><p class="tool-label">مقاله و منابع اصلی</p><div class="tool-links">{" ".join(survey["sources"])}</div></aside></div>'
    return page(survey['title'], f'<div class="intro"><p class="kicker">مقالهٔ مروری · درسنامهٔ بینایی ماشین</p><h1>{escape(survey["title"])}</h1><p class="deck">{escape(survey["summary"])}</p>'
        f'<div class="survey-dates"><span>معرفی در <a href="/issues/{survey["first_issue"]}/">{solar_title(survey["first_issue"])}</a></span>'
        f'<span><a href="{escape(survey["paper_date_source"], quote=True)}" rel="noopener noreferrer">{paper_date_html(survey_date_label(survey))}</a></span></div></div>'
        f'{tools}<article class="survey-article" id="item-{record["id"]}"><div>{sections}{"".join(survey["images"])}<div class="links">'
        f'</div>{item_actions(record["id"])}</div></article>'
        '<a class="archive" href="/surveys/">همهٔ مقالات مروری ←</a>', 'surveys')


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
    surveys = {path.stem: parse_survey(path) for path in (ROOT / 'content/surveys').glob('*.md')}
    survey_records = {}
    catalog = {}
    for issue in issues:
        write_page(f'issues/{issue["slug"]}/index.html', issue_page(issue))
        for section, items in issue['sections'].items():
            for item in items:
                record = story_record(issue, section, item)
                if record['id'] in catalog:
                    raise ValueError('Duplicate article source in the same issue section')
                catalog[record['id']] = record
                if item.get('survey_slug'):
                    survey = surveys.get(item['survey_slug'])
                    if not survey or survey['first_issue'] != issue['slug'] or survey['sources'][0] != item['sources'][0] or survey['summary'] != item['body'][0] or item.get('paper_date_line') != survey_date_label(survey):
                        raise ValueError('Missing or mismatched dedicated survey reference')
                    if survey['slug'] in survey_records:
                        raise ValueError('Duplicate survey introduction')
                    survey_records[survey['slug']] = record
    for slug, survey in surveys.items():
        if slug not in survey_records:
            raise ValueError('Dedicated survey must have its originating issue teaser')
        write_page(f'surveys/{slug}/index.html', survey_page(survey, survey_records[slug]))
    survey_rows = ''.join(f'<li><a href="/surveys/{survey["slug"]}/"><div><span class="kicker">{solar_title(survey["first_issue"])}</span><h2>{escape(survey["title"])}</h2><p>{escape(survey["summary"])}</p><span class="read-more">مطالعهٔ مقاله ←</span></div></a></li>' for survey in sorted(surveys.values(), key=lambda s: s['first_issue'], reverse=True))
    survey_intro = '<div class="intro"><p class="kicker">کتابخانهٔ یادگیری</p><h1>مقالات مروری</h1><p class="deck">برای تسلط بر ادبیات بینایی ماشین؛ تحلیل مقاله و ترجمهٔ کامل مقدمه و نتیجه‌گیری.</p></div>'
    write_page('surveys/index.html', page('مقالات مروری', survey_intro + ('<ul class="survey-list">' + survey_rows + '</ul>' if survey_rows else '<p>هنوز مقالهٔ مروری منتشر نشده است.</p>'), 'surveys'))
    (OUT / 'items.json').write_text(json.dumps(catalog, ensure_ascii=False))
    write_page('bookmarks/index.html', page('ذخیره‌شده‌ها', '<div class="intro"><h1>ذخیره‌شده‌ها</h1>'
               '<p id="bookmarks-message">برای دیدن لیست اختصاصی خود وارد حساب Google شوید.</p><a href="/account/">مدیریت حساب و ورود ←</a></div><div id="bookmark-list"></div>', 'bookmarks'))
    write_page('account/index.html', page('حساب کاربری', '<div class="intro"><p class="kicker">فضای شخصی شما</p><h1>حساب کاربری</h1><p class="deck">با حساب Google وارد شوید تا مطالب دلخواهتان را ذخیره کنید و همیشه به آن‌ها دسترسی داشته باشید.</p></div>'
        '<section class="account-panel"><h2>ورود و حساب</h2><p id="account-name" hidden></p><div class="links"><button id="sign-in">ورود با Google</button><button id="sign-out" hidden>خروج از حساب</button><a href="/bookmarks/">ذخیره‌شده‌های من ←</a></div></section>'
        '<section class="account-panel"><h2>دیده‌بان روی گوشی</h2><p>برای دسترسی سریع، دیده‌بان تصویر را روی صفحهٔ اصلی گوشی نصب کنید.</p><button id="install-app" hidden>نصب روی گوشی</button></section>', 'account'))
    write_page('auth/callback/index.html', page('ورود به حساب', '<div class="intro"><h1>ورود به حساب</h1><p>در حال بررسی ورود…</p></div>', 'account'))
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
    write_page('archive/index.html', page('آرشیو', f'<div class="intro"><h1>آرشیو گزارش‌ها</h1></div><ul class="issues">{rows}</ul>{preview_html}', 'archive'))
    paths = sorted(path for path in OUT.rglob('*') if path.is_file() and path.name != 'sw.js')
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(OUT).as_posix().encode())
        digest.update(path.read_bytes())
    shell = ['/', '/archive/', '/surveys/', '/account/', '/offline.html', '/manifest.webmanifest']
    shell += ['/' + path.relative_to(OUT).as_posix() for path in paths if path.parts[-2] in ('assets', 'icons')]
    worker = (OUT / 'sw.js').read_text().replace('__VERSION__', digest.hexdigest()[:20]).replace('__PRECACHE__', json.dumps(shell))
    (OUT / 'sw.js').write_text(worker)
    print(f'Built {len(issues)} issue(s) in {OUT}')


if __name__ == '__main__':
    build()
