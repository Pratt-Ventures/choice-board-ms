#!/usr/bin/env python3
"""Create dedicated ChoiceBoard Open Graph cards for blog collection pages."""
import argparse
from pathlib import Path
import re

from cb_site import ROOT


CARDS = {
    'hub': ('The ChoiceBoard blog', 'Guides, templates, and practical methods for defensible team decisions.'),
    'guides': ('Decision-making guides', 'Clear processes for comparing options, surfacing disagreement, and making the call.'),
    'templates': ('Templates and frameworks', 'Reusable tools for weighing options, testing assumptions, and explaining the result.'),
}


def variable_font(path, size, weight):
    from PIL import ImageFont
    font = ImageFont.truetype(str(path), size)
    axes = font.get_variation_axes()
    font.set_variation_by_axes([
        weight if axis.get('name') == b'Weight' else axis.get('default')
        for axis in axes
    ])
    return font


def wrapped(draw, text, font, width):
    lines, line = [], ''
    for word in text.split():
        candidate = (line + ' ' + word).strip()
        if draw.textlength(candidate, font=font) <= width:
            line = candidate
        else:
            lines.append(line)
            line = word
    return lines + ([line] if line else [])


def create(name, root):
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    title, description = CARDS[name]
    tokens = dict(re.findall(r'--([\w-]+):\s*(#[\da-fA-F]{6})', (root / 'index.html').read_text()))
    image = Image.new('RGB', (1200, 630), tokens['cream'])
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 16, 630), fill=tokens['brand'])
    manrope = root / 'tools/fonts/Manrope.ttf'
    inter = root / 'tools/fonts/Inter.ttf'
    label = variable_font(inter, 24, 600)
    headline = variable_font(manrope, 68, 800)
    body = variable_font(inter, 30, 400)
    draw.text((64, 48), 'The ChoiceBoard blog', fill=tokens['brand'], font=label)
    y = 125
    for line in wrapped(draw, title, headline, 1072):
        draw.text((64, y), line, fill=tokens['ink'], font=headline)
        y += 82
    y += 22
    for line in wrapped(draw, description, body, 1072):
        draw.text((64, y), line, fill=tokens['muted'], font=body)
        y += 44
    mark = ImageOps.contain(Image.open(root / 'logo.png').convert('RGBA'), (48, 48))
    image.paste(mark, (64, 542), mark)
    draw.text((128, 550), 'ChoiceBoard', fill=tokens['ink'], font=label)
    output = root / 'images/blog' / name / 'og.png'
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    print(output.relative_to(root))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('collection', choices=CARDS)
    parser.add_argument('--root', type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args()
    create(args.collection, args.root.resolve())
