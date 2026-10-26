"""The DecKoOS website: it builds from the repo as it is, every internal link and #anchor lands somewhere, nothing
loads from another site, and the server stays inside the site folder and resumes downloads."""
import re
import sys
import tempfile
import threading
import unittest
import unittest.mock
import urllib.error
import urllib.request
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / 'site'
sys.path.insert(0, str(SITE))
import build  # noqa: E402
import serve  # noqa: E402


class SiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / 'public'
        cls.site = build.Site(cls.out, iso=False, url='https://example.org')
        cls.site.build()
        cls.html = {p: (cls.out / p).read_text() for p in cls.site.pages}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_pages(self):
        for p in ('index.html', 'download.html', 'releases.html', 'docs/index.html', 'docs/install.html',
                  'source.html', 'security.html', '404.html'):
            self.assertIn(p, self.html)
        self.assertIn(build.FINGERPRINT, self.html['download.html'])
        self.assertIn('<loc>https://example.org/docs/install.html</loc>', (self.out / 'sitemap.xml').read_text())

    def test_every_internal_link_lands(self):
        ids = {p: set(re.findall(r'\bid="([^"]+)"', h)) for p, h in self.html.items()}
        for page, h in self.html.items():
            for url in re.findall(r'(?:href|src)="([^"]+)"', h):
                if re.match(r'[a-z]+:', url):
                    continue
                path, _, frag = url.split('?')[0].partition('#')
                target = page if not path else path.lstrip('/')
                if not path:
                    target = page
                if target.endswith('/') or target == '':
                    target += 'index.html'
                with self.subTest(page=page, url=url):
                    self.assertTrue((self.out / target).exists(), f'{page} links to missing {url}')
                    if frag and target.endswith('.html'):
                        self.assertIn(frag, ids.get(target, set()), f'{page}: no #{frag} on {target}')

    def test_nothing_from_other_sites(self):
        for page, h in self.html.items():
            with self.subTest(page=page):
                # A canonical link names this site's own address: it isn't a request
                self.assertNotRegex(h, r'<(script|img)\b[^>]*src="https?://|<link\b(?![^>]*rel="canonical")[^>]*href="https?://',
                                    'no third-party requests')

    def test_without_inter_installed(self):
        # CI and other PCs may not have Inter: no font links to a file that isn't there
        with tempfile.TemporaryDirectory() as tmp, unittest.mock.patch.object(build, 'FONT_SOURCES', []):
            out = Path(tmp) / 'public'
            site = build.Site(out, iso=False)
            site.build()
            self.assertNotIn('inter.woff2', (out / 'index.html').read_text())
            self.assertNotIn('@font-face', (out / 'style.css').read_text())

    def test_markdown_escapes_html(self):
        out = build.Markdown().render('# Hi\n\n<script>alert(1)</script> and `<b>` and **bold**')
        self.assertNotIn('<script>', out)
        self.assertIn('&lt;b&gt;', out)
        self.assertIn('<strong>bold</strong>', out)

    def test_github_anchors(self):
        self.assertEqual(build.slug('Display blackouts on Radeon cards'), 'display-blackouts-on-radeon-cards')
        self.assertEqual(build.slug('Get DecKoOS'), 'get-deckoos')


class ServeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name) / 'public'
        root.mkdir()
        (root / 'index.html').write_text('home')
        (root / '404.html').write_text('missing')
        (Path(self.tmp.name) / 'secret.txt').write_text('outside')
        (root / 'big.iso').write_bytes(bytes(range(256)) * 4)
        serve.Handler.root = root.resolve()
        self.srv = serve.ThreadingHTTPServer(('127.0.0.1', 0), serve.Handler)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f'http://127.0.0.1:{self.srv.server_port}'

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.tmp.cleanup()

    def get(self, path, headers=None):
        try:
            with urllib.request.urlopen(urllib.request.Request(self.base + path, headers=headers or {})) as r:
                return r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers

    def test_stays_inside_the_site(self):
        for path in ('/../secret.txt', '/%2e%2e/secret.txt', '/downloads/../../secret.txt'):
            with self.subTest(path=path):
                status, body, _ = self.get(path)
                self.assertEqual(status, 404)
                self.assertNotIn(b'outside', body)

    def test_resumes_downloads(self):
        status, body, h = self.get('/big.iso', {'Range': 'bytes=1000-'})
        self.assertEqual(status, 206)
        self.assertEqual(body, (bytes(range(256)) * 4)[1000:])
        self.assertEqual(h['Content-Range'], 'bytes 1000-1023/1024')
        self.assertEqual(self.get('/big.iso', {'Range': 'bytes=5000-'})[0], 416)
        self.assertIn('nosniff', self.get('/')[2]['X-Content-Type-Options'])


if __name__ == '__main__':
    unittest.main()
