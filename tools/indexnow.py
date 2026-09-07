#!/usr/bin/env python3
"""Submit indexed ChoiceBoard URLs only after their matching key file is deployed."""
import argparse
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from cb_site import ROOT, BASE, Page, local_target


def payload(urls, key, root=ROOT):
    if not re.fullmatch(r'[A-Za-z0-9-]{8,128}', key):
        raise ValueError('Set INDEXNOW_KEY to the 8–128 character deployed key.')
    key_file = root / (key + '.txt')
    if not key_file.is_file() or key_file.read_text().strip() != key:
        raise ValueError('Matching UTF-8 key file is required at the site root.')
    for url in urls:
        if not url.startswith(BASE + '/') or not url.endswith('/') or '?' in url or '#' in url:
            raise ValueError('Use canonical HTTPS ChoiceBoard URLs with trailing slashes.')
        path, _ = local_target(url, BASE + '/', root)
        if not path or not path.is_file() or '_templates' in path.parts:
            raise ValueError('URL has no local published page: ' + url)
        page = Page(path)
        if not page.indexed or page.url != url:
            raise ValueError('Refusing a draft or noncanonical URL: ' + url)
    return {'host': 'choiceboard.io', 'key': key, 'keyLocation': BASE + '/' + key + '.txt', 'urlList': urls}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('urls', nargs='+')
    parser.add_argument('--dry-run', action='store_true', help='Validate locally without network requests.')
    args = parser.parse_args()
    try:
        data = payload(args.urls, os.environ.get('INDEXNOW_KEY', ''))
        if args.dry_run:
            print(f'Validated {len(args.urls)} indexed URLs. No submission sent.')
        else:
            with urlopen(data['keyLocation'], timeout=20) as response:
                if response.read().decode().strip() != data['key']:
                    raise ValueError('Live key file does not match. Deploy it before submitting.')
            request = Request('https://api.indexnow.org/indexnow', data=json.dumps(data).encode(),
                              headers={'Content-Type': 'application/json; charset=utf-8'}, method='POST')
            with urlopen(request, timeout=30) as response:
                print(f'HTTP {response.status}: submission accepted; indexing is not guaranteed.')
    except (ValueError, OSError, HTTPError) as exc:
        parser.exit(1, str(exc) + '\n')
