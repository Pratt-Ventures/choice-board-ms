"""Shared, standard-library-only helpers for the static publishing tools."""
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import json
import re
from urllib.parse import urljoin, urlsplit, unquote

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://choiceboard.io'
GA = 'G-ZLZMXRHMBS'
POSITIONING = ('ChoiceBoard is group decision-making software. Teams define options and '
               'factors, answer quick head-to-head comparisons, and get a ranked result '
               'with a measured level of agreement — a decision they can defend.')
SERIES = {
    'guides': 'Decision-making guides', 'templates': 'Templates and frameworks',
    'compare': 'Comparisons and alternatives', 'product': 'Product',
    'customers': 'Customer stories', 'company': 'Company',
}
BOTS = ('OAI-SearchBot ChatGPT-User GPTBot Claude-SearchBot Claude-User ClaudeBot '
        'PerplexityBot Perplexity-User Googlebot Google-Extended Bingbot Applebot '
        'Applebot-Extended Meta-ExternalAgent Meta-ExternalFetcher DuckAssistBot '
        'Amazonbot CCBot MistralAI-User').split()
INDEX = 'index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1'
VOID = set('area base br col embed hr img input link meta param source track wbr'.split())


class Node:
    def __init__(self, tag='', attrs=None, parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs or []), parent
        self.children = []

    def all(self, tag=None, cls=None, **attrs):
        found = []
        for child in self.children:
            if isinstance(child, Node):
                if ((tag is None or child.tag == tag)
                        and (cls is None or cls in child.attrs.get('class', '').split())
                        and all(child.attrs.get(k) == v for k, v in attrs.items())):
                    found.append(child)
                found.extend(child.all(tag, cls, **attrs))
        return found

    def one(self, tag=None, cls=None, **attrs):
        return next(iter(self.all(tag, cls, **attrs)), None)

    def text(self):
        return ''.join(c.text() if isinstance(c, Node) else c for c in self.children)


class Tree(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.current = self.root
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in VOID:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        node = self.current
        while node.parent is not None:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent

    def handle_data(self, data):
        self.current.children.append(data)


def norm(text):
    return re.sub(r'\s+', ' ', text).strip()


def words(text):
    return re.findall(r"[\w]+(?:[’'-][\w]+)*", text)


class Page:
    def __init__(self, path):
        self.path = Path(path)
        self.source = self.path.read_text()
        self.tree = Tree(self.source).root
        self.meta = {n.attrs.get('name', n.attrs.get('property')): n.attrs.get('content', '')
                     for n in self.tree.all('meta')}
        self.url = next((n.attrs['href'] for n in self.tree.all('link', rel='canonical')), '')
        self.indexed = 'noindex' not in self.meta.get('robots', '').lower()
        self.title = norm(self.tree.one('title').text()) if self.tree.one('title') else ''
        self.graph, self.json_errors = [], []
        for node in self.tree.all('script', type='application/ld+json'):
            try:
                data = json.loads(node.text())
                self.graph.extend(data.get('@graph', [data]))
            except (ValueError, AttributeError) as exc:
                self.json_errors.append(str(exc))
        match = re.search(r'<!--\s*choiceboard-meta\s+(.*?)-->', self.source, re.S)
        self.editorial = dict(re.findall(r'^\s*([\w-]+):\s*(.*?)\s*$', match[1], re.M)) if match else {}

    def schema(self, kind):
        return next((n for n in self.graph if n.get('@type') == kind), None)


def pages(root=ROOT):
    return [Page(p) for p in sorted(root.rglob('*.html'))
            if not any(part.startswith('.') or part in ('node_modules', 'venv', 'dist')
                       for part in p.relative_to(root).parts)]


def posts(root=ROOT):
    return [Page(p) for series in SERIES for p in sorted((root / 'blog' / series).glob('*/index.html'))]


def local_target(url, current, root=ROOT):
    resolved = urlsplit(urljoin(current, url))
    if resolved.scheme not in ('http', 'https') or resolved.netloc != 'choiceboard.io':
        return None, ''
    path = root / unquote(resolved.path).lstrip('/')
    if resolved.path.endswith('/'):
        path /= 'index.html'
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Local URL escapes the site root')
    return path, unquote(resolved.fragment)


def markdown(node, base=''):
    """Export meaningful HTML, retaining links, nested lists, tables, and transcripts."""
    if isinstance(node, str):
        return re.sub(r'\s+', ' ', node)
    if (node.tag in ('script', 'style', 'nav', 'button', 'svg')
            or 'data-export-exclude' in node.attrs or node.attrs.get('aria-hidden') == 'true'
            or 'plus' in node.attrs.get('class', '').split()):
        return ''
    content = ''.join(markdown(c, base) for c in node.children).strip()
    if re.fullmatch('h[1-6]', node.tag):
        return '\n\n' + '#' * int(node.tag[1]) + ' ' + norm(content) + '\n\n'
    if node.tag == 'a':
        headings = [n for n in node.all() if re.fullmatch('h[1-6]', n.tag)]
        if headings:
            heading = headings[0]
            rest = ''.join(markdown(c, base) for c in node.children if c is not heading)
            return ('\n\n' + '#' * int(heading.tag[1]) + ' [' + norm(heading.text()) + ']('
                    + urljoin(base, node.attrs.get('href', '')) + ')\n\n' + rest + '\n\n')
        return '[' + content + '](' + urljoin(base, node.attrs.get('href', '')) + ')'
    if node.tag == 'img':
        return '![' + node.attrs.get('alt', '') + '](' + urljoin(base, node.attrs.get('src', '')) + ')'
    if node.tag in ('strong', 'b'):
        return '**' + content + '**'
    if node.tag in ('em', 'i'):
        return '*' + content + '*'
    if node.tag == 'code':
        return '`' + content + '`'
    if node.tag == 'br':
        return '\n'
    if node.tag == 'small':
        return ' ' + content + ' '
    if node.tag == 'blockquote':
        return '\n\n' + '\n'.join('> ' + line for line in content.splitlines()) + '\n\n'
    if node.tag == 'li':
        siblings = [c for c in node.parent.children if isinstance(c, Node) and c.tag == 'li']
        prefix = str(siblings.index(node) + 1) + '. ' if node.parent.tag == 'ol' else '- '
        return '\n' + prefix + content.replace('\n', '\n  ') + '\n'
    if node.tag == 'table':
        rows = []
        for row in node.all('tr'):
            cells = [norm(markdown(c, base)).replace('|', '\\|') for c in row.children
                     if isinstance(c, Node) and c.tag in ('th', 'td')]
            rows.append('| ' + ' | '.join(cells) + ' |')
        if rows:
            rows.insert(1, '| ' + ' | '.join('---' for _ in re.findall(r'\|', rows[0])[1:]) + ' |')
        caption = node.one('caption')
        return '\n\n' + (norm(caption.text()) + '\n\n' if caption else '') + '\n'.join(rows) + '\n\n'
    if node.tag in ('p', 'section', 'div', 'article', 'main', 'header', 'footer', 'aside', 'details', 'summary', 'ul', 'ol'):
        return '\n\n' + content + '\n\n'
    return content


def export(page):
    body = page.tree.one('article', cls='article') or page.tree.one('main')
    if body is None:
        raise ValueError(f'{page.path}: missing article/main')
    text = markdown(body, page.url)
    return re.sub(r'\n[ \t]*\n(?:[ \t]*\n)+', '\n\n', text).strip() + '\n'


def json_text(data):
    return json.dumps(data, ensure_ascii=False, indent=2).replace('<', '\\u003c')


def render(template, values):
    def replace(match):
        key = match[1]
        if key not in values:
            raise ValueError(f'Missing template field: {key}')
        return str(values[key]) if key.endswith('_HTML') or key == 'JSON_LD' else escape(str(values[key]), quote=True)
    return re.sub(r'\{\{([A-Z_]+)\}\}', replace, template)
