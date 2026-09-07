#!/usr/bin/env python3
"""Make brand typographic cards or frame an author-provided visual. Requires Pillow."""
import argparse
from pathlib import Path
import os
import re
from cb_site import ROOT, BASE, SERIES, Page, norm


def font_path(explicit, family):
    candidates = [explicit, os.environ.get('CHOICEBOARD_' + family.upper() + '_FONT')]
    directories = [ROOT / 'tools' / 'fonts', Path.home() / 'Library/Fonts', Path('/Library/Fonts')]
    for directory in directories:
        if directory.exists():
            candidates.extend(str(p) for p in directory.rglob('*')
                              if family.lower() in p.name.lower() and p.suffix.lower() in ('.ttf', '.otf'))
    found = next((Path(p) for p in candidates if p and Path(p).is_file()), None)
    if found is None:
        raise ValueError(f'{family} font missing. Pass --{family.lower()}-font PATH; no substitute font will be used.')
    return found


def wrap(draw, text, font, width):
    lines, line = [], ''
    for word in text.split():
        if draw.textlength(word, font=font) > width:
            raise ValueError('A word is too long for this card; shorten the title or takeaway.')
        candidate = (line + ' ' + word).strip()
        if draw.textlength(candidate, font=font) <= width:
            line = candidate
        else:
            lines.append(line)
            line = word
    return lines + ([line] if line else [])


def create(args):
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    root = args.root.resolve()
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', args.slug):
        raise ValueError('Invalid slug.')
    page = Page(root / 'blog' / args.series / args.slug / 'index.html')
    title = norm(page.tree.one('h1').text())
    takeaways = page.tree.one(cls='takeaways')
    takeaway = norm(takeaways.one('li').text()) if takeaways and takeaways.one('li') else ''
    if 'TODO' in title + takeaway or not takeaway:
        raise ValueError('Finish the title and first takeaway before producing images.')
    manrope, inter = font_path(args.manrope_font, 'Manrope'), font_path(args.inter_font, 'Inter')
    tokens = dict(re.findall(r'--([\w-]+):\s*(#[\da-fA-F]{6})', (root / 'index.html').read_text()))
    provided = None
    if args.source != 'generated':
        kind, sep, path = args.source.partition(':')
        if not sep or kind not in ('image', 'screenshot'):
            raise ValueError('Source must be generated, image:PATH, or screenshot:PATH.')
        provided = ImageOps.exif_transpose(Image.open(path)).convert('RGBA')
    # logo.png is the repository's raster counterpart of logo.svg, never a redrawn mark.
    mark = Image.open(root / 'logo.png').convert('RGBA')
    output = root / 'images/blog' / args.slug
    sizes = [('og.png', 1200, 630), ('linkedin-square.png', 1080, 1080)]
    if args.story:
        sizes.append(('story.png', 1080, 1920))
    rendered = []
    for name, width, height in sizes:
        card = Image.new('RGB', (width, height), tokens['cream'])
        draw = ImageDraw.Draw(card)
        margin = 64
        draw.rectangle((0, 0, 16, height), fill=tokens['brand'])
        label_font = ImageFont.truetype(str(inter), 24)
        draw.text((margin, 48), SERIES[args.series], fill=tokens['brand'], font=label_font)
        max_title_height = 245 if height == 630 else 360
        for point in range(64, 31, -2):
            headline = ImageFont.truetype(str(manrope), point)
            lines = wrap(draw, title, headline, width - margin * 2)
            if len(lines) * (point + 14) <= max_title_height:
                break
        else:
            raise ValueError('Title does not fit; shorten it before generating images.')
        y = 112
        for line in lines:
            draw.text((margin, y), line, fill=tokens['ink'], font=headline)
            y += point + 14
        if provided:
            top = y + 20
            space = (width - margin * 2, height - top - 110)
            if min(space) < 80:
                raise ValueError('Title leaves too little room for the provided visual.')
            visual = ImageOps.contain(provided, space)
            card.paste(visual, (margin + (space[0] - visual.width) // 2, top), visual)
        else:
            body = ImageFont.truetype(str(inter), 28 if height == 630 else 34)
            body_lines = wrap(draw, takeaway, body, width - margin * 2)
            y += 28
            for line in body_lines:
                if y + body.size + 8 > height - 120:
                    raise ValueError('Takeaway does not fit; shorten it before generating images.')
                draw.text((margin, y), line, fill=tokens['muted'], font=body)
                y += body.size + 12
        small_mark = ImageOps.contain(mark, (48, 48))
        card.paste(small_mark, (margin, height - 88), small_mark)
        draw.text((margin + 64, height - 80), 'ChoiceBoard', fill=tokens['ink'], font=label_font)
        rendered.append((name, card))
    # Render the whole set before writing so a layout error cannot leave a partial set.
    output.mkdir(parents=True, exist_ok=True)
    for name, card in rendered:
        card.save(output / name)
    url = BASE + '/images/blog/' + args.slug + '/og.png'
    print(f'Created {len(rendered)} images in {output.relative_to(root)}. Review before setting og-image: dedicated.')
    print(f'<meta property="og:image" content="{url}">\n<meta name="twitter:image" content="{url}">')
    print('Set JSON-LD image to the same URL and write descriptive og:image:alt/twitter:image:alt text.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('series', choices=SERIES)
    parser.add_argument('slug')
    parser.add_argument('--source', required=True)
    parser.add_argument('--story', action='store_true')
    parser.add_argument('--manrope-font')
    parser.add_argument('--inter-font')
    parser.add_argument('--root', type=Path, default=ROOT, help=argparse.SUPPRESS)
    try:
        create(parser.parse_args())
    except (ValueError, OSError, ImportError) as exc:
        parser.exit(1, str(exc) + '\n')
