#!/usr/bin/env python3
"""Check static SEO, publication boundaries, and analytics; manual review is separate."""
import argparse
from datetime import date, datetime
from pathlib import Path
import re
import struct
import sys
import xml.etree.ElementTree as ET
from cb_site import ROOT, BASE, GA, BOTS, SERIES, INDEX, POSITIONING, Page, pages, posts, local_target, norm, words


class Check:
    def __init__(self, root, selected=None):
        self.root, self.selected = root, selected
        self.errors, self.warnings = [], []
        self.pages = pages(root)
        self.posts = posts(root)
        self.by_path = {p.path.resolve(): p for p in self.pages}

    def require(self, condition, page, message):
        if not condition:
            self.errors.append(f'{page}: {message}')

    def warn(self, page, message):
        self.warnings.append(f'{page}: {message}')

    def image(self, url, label, expected=None):
        try:
            path, _ = local_target(url, BASE + '/', self.root)
            self.require(path is not None and path.is_file(), label, 'image must exist on this site: ' + url)
            if path and path.is_file() and expected:
                data = path.read_bytes()
                size = struct.unpack('>II', data[16:24]) if data[:8] == b'\x89PNG\r\n\x1a\n' else None
                self.require(size == expected, label, f'image must be a {expected[0]}×{expected[1]} PNG: {url}')
        except (ValueError, OSError, struct.error) as exc:
            self.require(False, label, str(exc))

    def faq(self, page, label):
        schema = page.schema('FAQPage')
        visible = page.tree.one(cls='faq')
        if not schema and not visible:
            return
        self.require(bool(schema and visible), label, 'visible FAQ and FAQPage must both exist')
        if not schema or not visible:
            return
        actual = []
        for item in visible.all('details'):
            summary = item.one('summary')
            if not summary:
                continue
            # Ignore the decorative plus icon in the existing landing-page accordion.
            question = norm(summary.text()).removesuffix(' +').strip()
            answers = item.all('p')
            actual.append((question, norm(' '.join(n.text() for n in answers))))
        expected = [(norm(q.get('name', '')), norm(q.get('acceptedAnswer', {}).get('text', '')))
                    for q in schema.get('mainEntity', [])]
        self.require(3 <= len(actual) <= 6, label, 'FAQ must contain 3–6 questions')
        self.require(actual == expected, label, 'FAQPage must match the visible FAQ word for word')

    def page(self, page):
        label = str(page.path.relative_to(self.root))
        template = '_templates' in page.path.parts
        head = page.tree.one('head')
        self.require(head is not None, label, 'missing head')
        source = re.search(r'<head>(.*?)</head>', page.source, re.S)
        head_text = source[1] if source else ''
        scripts = page.tree.all('script')
        analytics = [s for s in scripts if 'googletagmanager.com/gtag/js' in s.attrs.get('src', '')]
        self.require(len(analytics) == 1 and analytics[0].attrs.get('src') ==
                     f'https://www.googletagmanager.com/gtag/js?id={GA}' and 'async' in analytics[0].attrs,
                     label, 'exactly one approved async Google Analytics loader required')
        config = re.findall(r"gtag\(\s*['\"]config['\"]\s*,\s*['\"]([^'\"]+)['\"]", page.source)
        self.require(config == [GA], label, 'exactly one approved analytics configuration required')
        self.require(f'https://www.googletagmanager.com/gtag/js?id={GA}' in head_text and
                     re.search(r"gtag\(\s*['\"]config['\"]\s*,\s*['\"]" + GA, head_text),
                     label, 'analytics loader and configuration must both be in head')
        self.require('window.dataLayer = window.dataLayer || []' in head_text and
                     'function gtag(){dataLayer.push(arguments);}' in head_text,
                     label, 'analytics initialization must be in head')
        for script in scripts:
            src = script.attrs.get('src', '')
            self.require(not src or src == f'https://www.googletagmanager.com/gtag/js?id={GA}',
                         label, 'unapproved external JavaScript: ' + src)
        self.require(not page.tree.all('iframe'), label, 'use a click-through video facade; no preloaded embeds')
        self.require(len(page.tree.all('h1')) == 1, label, 'exactly one h1 required')
        last = 0
        for h in page.tree.all():
            if re.fullmatch(r'h[1-6]', h.tag):
                level = int(h.tag[1])
                self.require(not last or level <= last + 1, label, 'heading level skipped at ' + norm(h.text()))
                last = level
        self.require(page.tree.one('html').attrs.get('lang') in ('en', 'en-US'), label, 'English language required')
        if template:
            self.require(not page.indexed, label, 'templates must stay noindex')
            self.require('choiceboard-meta' in page.source and '{{JSON_LD}}' in page.source,
                         label, 'template metadata and JSON-LD slots required')
            return
        self.require(not page.json_errors, label, 'invalid JSON-LD: ' + '; '.join(page.json_errors))
        self.require(len(page.tree.all('script', type='application/ld+json')) == 1,
                     label, 'use one JSON-LD graph, without duplicate installations')
        types = [node.get('@type') for node in page.graph]
        self.require(len(types) == len(set(str(t) for t in types)), label, 'duplicate structured-data entity types')
        self.require(page.url.startswith(BASE + '/') and page.url.endswith('/'), label, 'canonical must be HTTPS with trailing slash')
        self.require(len(page.tree.all('link', rel='canonical')) == 1, label, 'exactly one canonical required')
        self.require(bool(page.meta.get('robots')), label, 'robots directive required')
        if page.indexed:
            self.require(page.meta.get('robots') == INDEX, label, 'indexed page needs full preview/snippet directives')
        else:
            self.require(page.meta.get('robots') == 'noindex, nofollow', label, 'drafts must be noindex, nofollow')
        for key in ['description', 'theme-color', 'og:type', 'og:site_name', 'og:locale', 'og:url',
                    'og:title', 'og:description', 'og:image', 'og:image:width', 'og:image:height',
                    'og:image:type', 'og:image:alt', 'twitter:card', 'twitter:title',
                    'twitter:description', 'twitter:image', 'twitter:image:alt']:
            self.require(bool(page.meta.get(key)), label, 'missing metadata: ' + key)
        self.require(page.meta.get('og:url') == page.url, label, 'OG URL must match canonical')
        self.require(page.meta.get('og:site_name') == 'ChoiceBoard', label, 'OG site name must match ChoiceBoard')
        self.require(page.meta.get('og:locale') == 'en_US', label, 'OG locale must be en_US')
        self.require(page.meta.get('theme-color') == '#4059D8', label, 'theme-color must match publishing guide')
        self.require(page.meta.get('twitter:card') == 'summary_large_image', label, 'large Twitter card required')
        for n in page.tree.all('link', rel='stylesheet'):
            href = n.attrs.get('href', '')
            if 'fonts.googleapis.com' in href:
                self.require(all(family.split(':')[0] in ('Inter', 'Manrope') for family in re.findall(r'family=([^&]+)', href)), label, 'only site font families are permitted')
        self.require(page.meta.get('og:image') == page.meta.get('twitter:image'), label, 'social images must agree')
        self.require(page.meta.get('og:image:width') == '1200' and page.meta.get('og:image:height') == '630'
                     and page.meta.get('og:image:type') == 'image/png', label, 'OG image metadata must describe a 1200×630 PNG')
        org = page.schema('Organization')
        home_org = Page(self.root / 'index.html').schema('Organization')
        self.require(bool(org) and org.get('@id') == BASE + '/#organization', label, 'Organization entity ID required')
        if org:
            self.require(org.get('description') == home_org.get('description') and org.get('logo') == BASE + '/logo.png',
                         label, 'Organization description/logo must match homepage')
        for img in page.tree.all('img'):
            self.require(bool(img.attrs.get('alt', '').strip()), label, 'descriptive image alt required')
        for node in page.tree.all():
            for attr in ('href', 'src'):
                value = node.attrs.get(attr, '')
                if not value or '{{' in value or value.startswith('data:'):
                    continue
                path, fragment = local_target(value, page.url, self.root)
                if path is None:
                    continue
                self.require(path.exists(), label, 'broken local link or asset: ' + value)
                if fragment and path.exists() and path.suffix == '.html':
                    dest = self.by_path.get(path.resolve()) or Page(path)
                    self.require(dest.tree.one(id=fragment) is not None, label, 'missing anchor: ' + value)
                if value == '#':
                    self.warn(label, 'placeholder destination: ' + norm(node.text()))
        self.faq(page, label)
        if page.indexed:
            self.image(page.meta.get('og:image', ''), label, (1200, 630))
        elif not page.editorial:
            self.warn(label, 'unpublished collection; dedicated social visual and content review required before indexing')
        if page.editorial:
            self.article(page, label)

    def article(self, page, label):
        meta = page.editorial
        for key in ('type', 'series', 'query', 'author', 'og-image', 'published', 'modified'):
            self.require(bool(meta.get(key)) and 'TODO' not in meta.get(key, ''), label, 'complete editorial field: ' + key)
        self.require(meta.get('type') in ('article', 'video', 'story'), label, 'invalid post type')
        self.require(meta.get('series') in SERIES and page.path.parent.parent.name == meta.get('series'), label, 'series/path mismatch')
        self.require(meta.get('og-image') == 'dedicated', label, 'dedicated social image required, including draft review')
        self.require('TODO' not in page.source and '{{' not in page.source, label, 'unfilled draft placeholders remain')
        self.require(50 <= len(page.title) <= 60 and page.title.endswith(' | ChoiceBoard'), label, 'article title must be 50–60 characters, ending | ChoiceBoard')
        self.require(140 <= len(page.meta.get('description', '')) <= 160, label, 'article description must be 140–160 characters')
        self.require(len(page.tree.all('script', type='application/ld+json')) == 1, label, 'one JSON-LD graph required')
        for kind in ('Organization', 'WebSite', 'BlogPosting', 'BreadcrumbList', 'FAQPage'):
            self.require(page.schema(kind) is not None, label, 'missing structured data: ' + kind)
        article = page.tree.one('article', cls='article')
        self.require(article is not None, label, 'article content wrapper required')
        if not article:
            return
        query = meta.get('query', '')
        query_words = [w.lower() for w in words(query)]
        if query and query != 'none':
            first = article.one('p', cls='lead')
            for field, text in [('title', page.title), ('h1', article.one('h1').text()),
                                ('description', page.meta.get('description', '')), ('opening paragraph', first.text() if first else '')]:
                actual = [w.lower() for w in words(text)]
                # Hyphenated words are equivalent to spaced words for query matching.
                actual = re.findall(r'\w+', ' '.join(actual))
                expected = re.findall(r'\w+', ' '.join(query_words))
                self.require(' '.join(expected) in ' '.join(actual), label, f'target query missing from {field}')
                if field == 'title':
                    self.require(actual[:len(expected)] == expected, label, 'target query must open title')
        takeaways = article.one(cls='takeaways')
        self.require(takeaways is not None and 4 <= len(takeaways.all('li')) <= 5, label, '4–5 takeaways required')
        self.require(page.source.find('class="takeaways"') < page.source.find('<h2'), label, 'takeaways must precede first h2')
        self.require(article.one('blockquote') is not None, label, 'signed blockquote required')
        quote = article.one('blockquote')
        self.require(quote is not None and quote.one('footer') is not None and norm(quote.one('footer').text()) == meta.get('author'), label, 'blockquote signature must match author')
        self.require('ChoiceBoard doesn’t hide disagreement, it measures it.' in article.text() or
                     "ChoiceBoard doesn't hide disagreement, it measures it." in article.text(), label, 'product refrain required')
        self.require(len(article.all('a', cls='btn-primary')) == 1, label, 'one primary article CTA required')
        if meta.get('series') == 'guides':
            self.require(article.one('ol') is not None, label, 'guide needs numbered steps')
        if meta.get('series') == 'compare':
            table = article.one('table')
            self.require(table is not None and table.one('caption') and table.one('th'), label, 'comparison needs a captioned table with headers')
        alt = page.tree.one('link', rel='alternate', type='text/markdown')
        self.require(alt is not None and alt.attrs.get('href') == 'index.md', label, 'Markdown alternate required')
        self.require(page.tree.one('link', rel='alternate', type='application/rss+xml') is not None, label, 'RSS alternate required')
        self.require(page.meta.get('og:type') == 'article', label, 'article OG type required')
        tags = page.tree.all('meta', property='article:tag')
        self.require(len(tags) == 3, label, 'exactly three article tags required')
        for key in ('article:published_time', 'article:modified_time', 'article:author', 'article:section'):
            self.require(bool(page.meta.get(key)), label, 'missing metadata: ' + key)
        posting = page.schema('BlogPosting') or {}
        for key in ('headline', 'description', 'image', 'datePublished', 'dateModified', 'author', 'publisher',
                    'isPartOf', 'articleSection', 'keywords', 'inLanguage', 'wordCount', 'timeRequired', 'mainEntityOfPage', 'speakable'):
            self.require(bool(posting.get(key)), label, 'missing BlogPosting field: ' + key)
        self.require(len(posting.get('headline', '')) <= 110, label, 'headline exceeds 110 characters')
        self.require(posting.get('headline') == norm(article.one('h1').text()), label, 'headline/h1 mismatch')
        self.require(posting.get('description') == page.meta.get('description'), label, 'structured description mismatch')
        self.require(posting.get('image') == page.meta.get('og:image'), label, 'structured image mismatch')
        self.require(posting.get('inLanguage') == 'en-US', label, 'structured language must be en-US')
        self.require(posting.get('mainEntityOfPage') == page.url, label, 'mainEntityOfPage mismatch')
        self.require(posting.get('publisher', {}).get('@id') == BASE + '/#organization' and
                     posting.get('isPartOf', {}).get('@id') == BASE + '/#website', label, 'publisher/site references must match canonical entities')
        self.require(posting.get('articleSection') == SERIES.get(meta.get('series')) == page.meta.get('article:section'), label, 'article section must match series')
        self.require(posting.get('speakable', {}).get('cssSelector') == ['.article-hero__head', '.takeaways'], label, 'speakable selectors must match visible regions')
        self.require(bool(re.fullmatch(r'PT(?:\d+H)?(?:\d+M)?(?:\d+S)?', str(posting.get('timeRequired', '')))) and posting.get('timeRequired') != 'PT', label, 'timeRequired must be an ISO duration')
        crumbs = (page.schema('BreadcrumbList') or {}).get('itemListElement', [])
        self.require([c.get('item') for c in crumbs] == [BASE + '/', BASE + '/blog/', BASE + '/blog/' + meta.get('series', '') + '/', page.url], label, 'breadcrumbs must follow Home → Blog → Series → Post')
        count = len(words(article.text()))
        self.require(isinstance(posting.get('wordCount'), int) and abs(posting.get('wordCount', 0) - count) <= count * .25,
                     label, 'wordCount differs from visible article by more than 25%')
        for key, og, editorial in [('datePublished', 'article:published_time', 'published'), ('dateModified', 'article:modified_time', 'modified')]:
            value = posting.get(key, '')
            try:
                parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
                self.require(parsed.tzinfo is not None and parsed.date() <= date.today(), label, 'date must include offset and not be future')
                self.require(value == page.meta.get(og) and parsed.date().isoformat() == meta.get(editorial), label, 'dates must agree across metadata')
                self.require(any(n.attrs.get('datetime', '').startswith(meta.get(editorial, 'MISSING')) for n in article.all('time')),
                             label, 'publication and update dates must be visible')
            except (ValueError, TypeError):
                self.require(False, label, 'invalid ISO date: ' + key)
        self.require(meta.get('published', '') <= meta.get('modified', ''), label, 'modified date precedes publication date')
        for node in article.all('time'):
            try:
                datetime.fromisoformat(node.attrs.get('datetime', '').replace('Z', '+00:00'))
            except ValueError:
                self.require(False, label, 'invalid visible datetime')
        author = meta.get('author')
        byline = article.one(cls='byline')
        self.require(byline is not None and author in byline.text(), label, 'visible byline must match author')
        if author != 'The ChoiceBoard team':
            person = page.schema('Person') or {}
            self.require(person.get('name') == author and person.get('jobTitle') and person.get('sameAs') and person.get('worksFor'), label, 'named author needs complete Person node')
            self.require(posting.get('author', {}).get('@id') == person.get('@id'), label, 'BlogPosting must reference named author')
            self.require(page.meta.get('article:author') in person.get('sameAs', []), label, 'article:author must match author profile')
            card = article.one(cls='authorcard')
            self.require(card is not None and author in card.text() and card.one('a') is not None, label, 'named author card/bio/profile required')
        else:
            self.require(posting.get('author', {}).get('@id') == BASE + '/#organization', label, 'team author must reference Organization')
        image_url = BASE + '/images/blog/' + page.path.parent.name + '/og.png'
        self.require(page.meta.get('og:image') == image_url, label, 'post needs its own image path')
        self.image(image_url, label, (1200, 630))
        self.image(image_url.replace('og.png', 'linkedin-square.png'), label, (1080, 1080))
        links = [a.attrs.get('href', '') for a in article.all('a')]
        outgoing = {local_target(link, page.url, self.root)[0] for link in links}
        peers = {p.path for p in self.posts if p.path != page.path}
        self.require(1 <= len(outgoing & peers) <= 2, label, 'link to one or two other posts')
        self.require(any(link in ('/#pricing', '/#how-it-works', '/#use-cases') for link in links), label, 'relevant landing section link required')
        self.require(any(link.startswith('https://') and not link.startswith(BASE) for link in links), label, 'primary-source citations required')
        if page.indexed:
            self.require(article.one(cls='draft-notice') is None and 'Publication date pending approval' not in article.text(), label, 'remove draft notices and show actual publication dates before indexing')
            incoming = [p for p in self.pages if p.path != page.path and p.indexed and
                        any(local_target(a.attrs.get('href', ''), p.url, self.root)[0] == page.path for a in p.tree.all('a'))]
            self.require(len(incoming) >= 2, label, 'two incoming links from indexed pages required')
            self.require((page.path.parent / 'social.md').exists(), label, 'published post needs social.md')
        else:
            self.warn(label, 'publication still requires author approval and manual review; draft incoming links are checked at go-live')
        if meta.get('type') in ('video', 'story'):
            video = page.schema('VideoObject') or {}
            for key in ('name', 'description', 'thumbnailUrl', 'uploadDate', 'duration', 'embedUrl', 'hasPart'):
                self.require(bool(video.get(key)), label, 'missing video field: ' + key)
            transcript = article.one('details', cls='transcript')
            self.require(transcript is not None and transcript.one('p') is not None, label, 'full HTML transcript required')
            clips = video.get('hasPart', [])
            starts = [n.attrs.get('data-start') for n in article.all('a') if 'data-start' in n.attrs]
            self.require(starts == [str(c.get('startOffset')) for c in clips], label, 'chapter times must match Clip entries')
            self.warn(label, 'manually verify video identity, complete transcript, duration, and chapter content')
        software = page.schema('SoftwareApplication')
        self.require(software is None or (meta.get('series') == 'product' and software == {'@type': 'SoftwareApplication', '@id': BASE + '/#software'}), label, 'SoftwareApplication may only reference homepage from product posts')

    def run(self):
        if self.selected is not None:
            self.require(self.selected in self.by_path, '--post', 'selected HTML page does not exist in this site')
        for page in self.pages:
            if self.selected is None or page.path == self.selected:
                self.page(page)
        robots = (self.root / 'robots.txt').read_text()
        groups = re.split(r'\n\s*\n', robots)
        for bot in BOTS:
            group = next((g for g in groups if re.search(r'^User-agent:\s*' + re.escape(bot) + r'\s*$', g, re.M)), '')
            self.require(re.search(r'^Allow:\s*/\s*$', group, re.M) and not re.search(r'^Disallow:\s*\S', group, re.M), 'robots.txt', 'explicit allow required for ' + bot)
        self.require('Sitemap: ' + BASE + '/sitemap.xml' in robots and BASE + '/llms.txt' in robots, 'robots.txt', 'sitemap and AI-index references required')
        try:
            sitemap = ET.parse(self.root / 'sitemap.xml').getroot()
            mapped = {n.findtext('{*}loc'): n.findtext('{*}lastmod') for n in sitemap.findall('{*}url')}
            feed = ET.parse(self.root / 'blog/feed.xml').getroot()
            feed_urls = {n.findtext('link') for n in feed.findall('./channel/item')}
            indexed_urls = {p.url for p in self.pages if p.indexed and '_templates' not in p.path.parts}
            self.require(set(mapped) == indexed_urls, 'sitemap.xml', 'sitemap must contain exactly indexed canonical pages')
            live_posts = {p.url for p in self.posts if p.indexed}
            self.require(feed_urls == live_posts, 'blog/feed.xml', 'feed must contain exactly published posts')
            for p in self.posts:
                if p.indexed:
                    self.require(mapped.get(p.url) == p.editorial.get('modified'), 'sitemap.xml', 'post lastmod mismatch: ' + p.url)
        except (OSError, ET.ParseError) as exc:
            self.require(False, 'publication files', str(exc))
        for name in ('llms.txt', 'llms-full.txt'):
            file = self.root / name
            self.require(file.exists(), name, 'AI-readable file missing')
            text = file.read_text() if file.exists() else ''
            self.require(POSITIONING in text, name, 'canonical positioning missing')
            for p in self.posts:
                self.require((p.url in text) == p.indexed, name, 'publication mismatch: ' + p.url)
        for page in self.pages:
            if page.schema('ItemList'):
                if page.path == self.root / 'blog' / 'index.html':
                    expected = {p.url for p in self.posts if p.indexed}
                else:
                    expected = {p.url for p in self.posts if p.indexed and p.path.parent.parent == page.path.parent}
                actual = {n.get('url', n.get('item')) for n in page.schema('ItemList').get('itemListElement', [])}
                self.require(actual == expected, str(page.path.relative_to(self.root)), 'ItemList must match published posts in this collection')
        self.warn('manual review', 'source accuracy, author permission, visual layout, rich-result eligibility, analytics receipt, and live indexing cannot be certified by this checker')
        return self.errors, self.warnings


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT, help=argparse.SUPPRESS)
    parser.add_argument('--post', type=Path, help='Validate a finished draft before publication; global publication boundaries still checked.')
    args = parser.parse_args()
    root = args.root.resolve()
    errors, warnings = Check(root, (root / args.post).resolve() if args.post else None).run()
    for message in errors:
        print('ERROR ' + message)
    for message in dict.fromkeys(warnings):
        print('REVIEW ' + message)
    print(f'{len(errors)} errors; {len(set(warnings))} review notes.')
    sys.exit(bool(errors))
