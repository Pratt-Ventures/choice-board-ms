#!/usr/bin/env python3
"""Create an unindexed skeleton after the author has completed intake."""
import argparse
from datetime import date
from pathlib import Path
import re
from cb_site import ROOT, BASE, SERIES, Page, json_text, render


def create(args):
    root = args.root.resolve()
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', args.slug):
        raise ValueError('Slug must contain lowercase words separated by hyphens.')
    target = root / 'blog' / args.series / args.slug / 'index.html'
    if target.exists():
        raise ValueError('Post already exists; refusing to overwrite it.')
    if any((root / 'blog' / series / args.slug).exists() for series in SERIES):
        raise ValueError('Slug is already in use by another series; social image paths must be unique.')
    url = f'{BASE}/blog/{args.series}/{args.slug}/'
    stamp = date.today().isoformat()
    organization = Page(root / 'index.html').schema('Organization')
    graph = [organization, {'@type': 'WebSite', '@id': BASE + '/#website', 'url': BASE + '/',
                            'publisher': {'@id': BASE + '/#organization'}},
             {'@type': 'BlogPosting', 'headline': args.title, 'description': 'TODO: Write the description.',
              'image': BASE + '/images/blog/' + args.slug + '/og.png',
              'datePublished': stamp + 'T00:00:00+00:00', 'dateModified': stamp + 'T00:00:00+00:00',
              'author': {'@id': BASE + '/#organization'}, 'publisher': {'@id': BASE + '/#organization'},
              'isPartOf': {'@id': BASE + '/#website'}, 'articleSection': SERIES[args.series],
              'keywords': [], 'inLanguage': 'en-US', 'wordCount': 0, 'timeRequired': 'PT0M',
              'mainEntityOfPage': url,
              'speakable': {'@type': 'SpeakableSpecification',
                            'cssSelector': ['.article-hero__head', '.takeaways']}},
             {'@type': 'BreadcrumbList', 'itemListElement': [
                 {'@type': 'ListItem', 'position': i + 1, 'name': name, 'item': link}
                 for i, (name, link) in enumerate([('Home', BASE + '/'), ('Blog', BASE + '/blog/'),
                      (SERIES[args.series], f'{BASE}/blog/{args.series}/'), (args.title, url)])]},
             {'@type': 'FAQPage', 'mainEntity': [
                 {'@type': 'Question', 'name': f'TODO: Question {i}?',
                  'acceptedAnswer': {'@type': 'Answer', 'text': f'TODO: Answer {i}.'}} for i in range(1, 4)]}]
    if args.type in ('video', 'story'):
        graph.append({'@type': 'VideoObject', 'name': args.title, 'description': 'TODO: Video description.',
                      'thumbnailUrl': 'TODO', 'uploadDate': stamp + 'T00:00:00+00:00',
                      'duration': 'PT0M', 'embedUrl': 'https://www.youtube-nocookie.com/embed/TODO',
                      'hasPart': []})
    values = {'TYPE': args.type, 'SERIES': args.series, 'SERIES_NAME': SERIES[args.series],
              'SLUG': args.slug, 'TITLE': args.title, 'URL': url, 'DATE': stamp,
              'QUERY': args.query or 'TODO: Record the approved query or none.',
              'AUTHOR': args.author or 'TODO: Confirm the author.',
              'JSON_LD': json_text({'@context': 'https://schema.org', '@graph': graph})}
    source = render((root / 'blog' / '_templates' / args.type / 'index.html').read_text(), values)
    target.parent.mkdir(parents=True)
    target.write_text(source)
    print(f'Created {target.relative_to(root)} as noindex. Complete all TODO fields; no publication lists changed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('series', choices=SERIES)
    parser.add_argument('slug')
    parser.add_argument('title')
    parser.add_argument('--type', required=True, choices=['article', 'video', 'story'])
    parser.add_argument('--query')
    parser.add_argument('--author')
    parser.add_argument('--root', type=Path, default=ROOT, help=argparse.SUPPRESS)
    try:
        create(parser.parse_args())
    except (ValueError, OSError) as exc:
        parser.exit(1, str(exc) + '\n')
