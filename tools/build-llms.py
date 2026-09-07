#!/usr/bin/env python3
"""Regenerate published AI indexes; draft alternates remain local to each draft."""
import argparse
from pathlib import Path
from cb_site import ROOT, BASE, POSITIONING, Page, posts, export


def build(root):
    home = Page(root / 'index.html')
    live = []
    for page in posts(root):
        alternate = export(page)
        # A draft's alternate carries an explicit editorial status and is never aggregated.
        prefix = '' if page.indexed else '> Draft — not published.\n\n'
        page.path.with_suffix('.md').write_text(prefix + alternate)
        if page.indexed:
            live.append((page, alternate))
    index = '# ChoiceBoard\n\n' + POSITIONING + '\n\n## Website\n\n'
    index += f'- [ChoiceBoard]({BASE}/): Product overview, how it works, and pricing.\n'
    index += '\n## Published articles\n\n'
    index += ''.join(f'- [{p.title.removesuffix(" | ChoiceBoard")}]({p.url}): {p.meta.get("description", "")}\n'
                     for p, _ in live) or 'No articles have been published yet.\n'
    (root / 'llms.txt').write_text(index)
    full = '# ChoiceBoard\n\n' + POSITIONING + '\n\n'
    full += f'Source: {BASE}/\n\n' + export(home)
    for page, alternate in live:
        full += '\n---\n\nSource: ' + page.url + '\n\n' + alternate
    (root / 'llms-full.txt').write_text(full)
    print(f'Generated AI indexes from the homepage and {len(live)} indexed posts; drafts excluded.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT, help=argparse.SUPPRESS)
    build(parser.parse_args().root.resolve())
