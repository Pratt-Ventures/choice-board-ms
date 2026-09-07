#!/usr/bin/env python3
"""Regression tests for publication boundaries and substantive SEO failures."""
import importlib.util
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from cb_site import ROOT, BASE, INDEX, Page, Tree, markdown, words, json_text


def module(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'tools' / (name + '.py'))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


checker = module('check-seo')
builder = module('build-llms')
indexnow = module('indexnow')


class PublishingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='choiceboard-publishing-')
        self.root = Path(self.temp.name).resolve()
        for name in ['index.html', 'robots.txt', 'sitemap.xml', 'llms.txt', 'llms-full.txt', 'logo.svg', 'logo.png', 'og-image.png']:
            shutil.copy2(ROOT / name, self.root / name)
        shutil.copytree(ROOT / 'blog', self.root / 'blog')

    def tearDown(self):
        self.temp.cleanup()

    def run_tool(self, tool, *args, success=True):
        result = subprocess.run([sys.executable, str(ROOT / 'tools' / tool), *args, '--root', str(self.root)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def create_draft(self, slug='test-boundary', typ='article'):
        self.run_tool('new-article.py', 'guides', slug, 'Test publication boundary', '--type', typ,
                      '--query', 'none', '--author', 'The ChoiceBoard team')
        return self.root / 'blog/guides' / slug / 'index.html'

    def errors(self):
        return checker.Check(self.root).run()[0]

    def test_foundation_passes(self):
        self.assertEqual(self.errors(), [])

    def test_generator_preserves_drafts_and_refuses_overwrite_or_escape(self):
        for typ in ['article', 'video', 'story']:
            path = self.create_draft('test-' + typ, typ)
            page = Page(path)
            self.assertFalse(page.indexed)
            self.assertEqual(page.json_errors, [])
            self.assertEqual(page.source.count("gtag('config', 'G-ZLZMXRHMBS')"), 1)
        self.run_tool('new-article.py', 'guides', 'test-article', 'Overwrite', '--type', 'article', success=False)
        self.run_tool('new-article.py', 'guides', '../../escape', 'Escape', '--type', 'article', success=False)

    def test_duplicate_analytics_is_rejected(self):
        path = self.root / 'index.html'
        path.write_text(path.read_text().replace('</head>', "<script>gtag('config', 'G-ZLZMXRHMBS');</script></head>"))
        self.assertTrue(any('analytics configuration' in error for error in self.errors()))

    def test_faq_drift_is_rejected(self):
        path = self.root / 'index.html'
        path.write_text(path.read_text().replace('What is pairwise comparison?</summary>', 'Different question?</summary>'))
        # The production summary also contains a plus icon; alter that form if needed.
        path.write_text(path.read_text().replace('What is pairwise comparison? <span', 'Different question? <span'))
        self.assertTrue(any('FAQPage must match' in error for error in self.errors()))

    def test_broken_link_is_rejected(self):
        path = self.root / 'index.html'
        path.write_text(path.read_text().replace('</main>', '<a href="/missing/">Missing</a></main>'))
        self.assertTrue(any('broken local link' in error for error in self.errors()))

    def test_draft_export_never_enters_aggregate(self):
        path = self.create_draft()
        builder.build(self.root)
        self.assertTrue(path.with_suffix('.md').read_text().startswith('> Draft'))
        url = Page(path).url
        for name in ['llms.txt', 'llms-full.txt']:
            self.assertNotIn(url, (self.root / name).read_text())
        path.write_text(path.read_text().replace('noindex, nofollow', INDEX))
        builder.build(self.root)
        self.assertIn(url, (self.root / 'llms.txt').read_text())
        path.write_text(path.read_text().replace(INDEX, 'noindex, nofollow'))
        builder.build(self.root)
        self.assertNotIn(url, (self.root / 'llms-full.txt').read_text())

    def test_draft_in_sitemap_is_rejected(self):
        draft = Page(self.create_draft())
        path = self.root / 'sitemap.xml'
        path.write_text(path.read_text().replace('</urlset>', '<url><loc>' + draft.url + '</loc></url></urlset>'))
        self.assertTrue(any('exactly indexed' in error for error in self.errors()))

    def test_indexnow_refuses_drafts_and_offsite_urls(self):
        draft = Page(self.create_draft())
        key = 'test-key-123456789'
        (self.root / (key + '.txt')).write_text(key)
        with self.assertRaisesRegex(ValueError, 'draft'):
            indexnow.payload([draft.url], key, self.root)
        with self.assertRaises(ValueError):
            indexnow.payload(['https://example.org/'], key, self.root)
        self.assertEqual(indexnow.payload([BASE + '/'], key, self.root)['urlList'], [BASE + '/'])

    def test_export_preserves_table_links_lists_and_transcript(self):
        source = '<main><h1>Test</h1><ol><li>Compare <a href="/">options</a></li><li>Review</li></ol><table><caption>Scores</caption><tr><th>Option</th><th>Score</th></tr><tr><td>A</td><td>2</td></tr></table><details class="transcript"><summary>Transcript</summary><p>Full spoken words.</p></details></main>'
        text = markdown(Tree(source).root, BASE + '/')
        for part in ['# Test', '1. Compare', '2. Review', '[options](https://choiceboard.io/)', '| Option | Score |', '| --- | --- |', 'Full spoken words.']:
            self.assertIn(part, text)

    def test_unfinished_post_cannot_pass(self):
        self.create_draft()
        errors = self.errors()
        for part in ['unfilled draft placeholders', 'dedicated social image required', 'wordCount']:
            self.assertTrue(any(part in error for error in errors), part)

    def test_social_images_have_correct_dimensions_and_reject_unfinished_copy(self):
        from PIL import Image
        path = self.create_draft()
        self.run_tool('social-images.py', 'guides', 'test-boundary', '--source', 'generated', success=False)
        path.write_text(path.read_text().replace('TODO: First sourced takeaway.', 'This is a test fixture for the image generator.'))
        self.run_tool('social-images.py', 'guides', 'test-boundary', '--source', 'generated', '--story')
        for name, size in [('og.png', (1200, 630)), ('linkedin-square.png', (1080, 1080)), ('story.png', (1080, 1920))]:
            with Image.open(self.root / 'images/blog/test-boundary' / name) as image:
                self.assertEqual(image.size, size)

    def test_complete_draft_can_pass_prepublication_checks(self):
        from PIL import Image
        path = self.create_draft()
        self.create_draft('test-peer')
        source = path.read_text().replace('Test publication boundary', 'Group decision making process for teams')
        source = source.replace('og-image: pending', 'og-image: dedicated')
        description = 'A test fixture for the publishing checker that verifies a complete article can pass draft review with matching metadata, images, source links, and dates.'
        source = source.replace('TODO: Write a 140–160 character description.', description)
        source = source.replace('TODO: Link to one or two related published posts.', '<a href="/blog/guides/test-peer/">Peer fixture</a> <a href="https://asq.org/quality-resources/decision-matrix">Source fixture</a>')
        source = re.sub(r'TODO:[^<"\n]+', 'Fixture text.', source)
        # Replace the graph independently after filling visible text.
        original = Page(path)
        graph = original.graph
        tree = Tree(source).root
        posting = next(n for n in graph if n.get('@type') == 'BlogPosting')
        posting.update(headline='Group decision making process for teams', description=description,
                       keywords=['test'], timeRequired='PT1M', wordCount=len(words(tree.one('article', cls='article').text())))
        faq = next(n for n in graph if n.get('@type') == 'FAQPage')
        faq['mainEntity'] = [{'@type': 'Question', 'name': d.one('summary').text(), 'acceptedAnswer': {'@type':'Answer', 'text':d.one('p').text()}} for d in tree.one(cls='faq').all('details')]
        source = re.sub(r'<script type="application/ld\+json">.*?</script>', lambda _: '<script type="application/ld+json">' + json_text({'@context':'https://schema.org','@graph':graph}) + '</script>', source, flags=re.S)
        path.write_text(source)
        image_dir = self.root / 'images/blog/test-boundary'
        image_dir.mkdir(parents=True)
        for name, size in [('og.png', (1200,630)), ('linkedin-square.png',(1080,1080))]:
            Image.new('RGB',size).save(image_dir/name)
        builder.build(self.root)
        errors, _ = checker.Check(self.root, path).run()
        self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main()
