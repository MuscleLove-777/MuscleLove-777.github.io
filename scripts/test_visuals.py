"""Behavior checks: future article coverage, redirects, missing asset gate, repeat builds."""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

from build_visuals import ROOT, audit, build


class BuildContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for folder in ("assets", "templates"):
            shutil.copytree(ROOT / folder, self.root / folder)
        (self.root / "articles").mkdir()
        self.article = self.root / "articles/new-fitness-guide.html"
        self.article.write_text('<!doctype html><html lang="ja"><head><meta charset="UTF-8"><title>New guide</title><meta property="og:type" content="article"></head><body><main><h1>New guide</h1><p>Original copy.</p></main></body></html>', encoding="utf-8")
        self.stub = self.root / "articles/old.html"
        self.stub.write_text('<html><head><meta http-equiv="refresh" content="0; url=/articles/new-fitness-guide.html"></head><body><h1>Moved</h1></body></html>', encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_new_article_gets_cover_and_home_card_without_touching_redirect(self):
        original = self.stub.read_bytes()
        report = build(self.root)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["articles"], 1)
        self.assertEqual(report["article_cards"], 1)
        self.assertEqual(report["article_image_coverage"], 1)
        self.assertEqual(self.stub.read_bytes(), original)
        self.assertIn("Original copy.", self.article.read_text(encoding="utf-8"))

    def test_second_build_changes_no_bytes(self):
        build(self.root)
        digest = lambda: {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}
        before = digest()
        build(self.root)
        self.assertEqual(before, digest())

    def test_missing_cover_blocks_publication(self):
        build(self.root)
        (self.root / "assets/images/fitness-01.webp").unlink()
        report = audit(self.root)
        self.assertEqual(report["status"], "REVISE")
        self.assertTrue(any("missing_image" in value for value in report["errors"]))

    def test_custom_page_keeps_its_authored_layout(self):
        custom = self.root / "fan" / "index.html"
        custom.parent.mkdir()
        custom.write_text(
            '<!doctype html><html lang="ja"><head><meta charset="UTF-8">'
            '<title>Custom</title></head><body data-ml-visual-build="custom">'
            '<main><h1>Custom fan page</h1><img src="/assets/images/brand-hero.webp" alt="Custom cover"></main>'
            '</body></html>',
            encoding="utf-8",
        )
        original = custom.read_bytes()
        report = build(self.root)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(custom.read_bytes(), original)


class FanSiteContract(unittest.TestCase):
    def setUp(self):
        self.fan = ROOT / "fan"
        self.page = self.fan / "index.html"
        self.soup = __import__("bs4").BeautifulSoup(self.page.read_text(encoding="utf-8"), "html.parser")

    def test_human_and_machine_descriptions_match(self):
        canonical = "MuscleLoveは、架空の成人女性キャラクターによる筋肉美を軸にしたクリエイティブブランドです。"
        self.assertEqual(len(self.soup.find_all("h1")), 1)
        self.assertIn(canonical, self.soup.get_text(" ", strip=True))
        self.assertTrue(all(image.get("alt", "").strip() for image in self.soup.find_all("img")))
        self.assertIsNotNone(self.soup.find("link", rel="describedby", href="https://musclelove-777.github.io/fan/llms.txt"))
        self.assertIsNotNone(self.soup.find("link", rel="alternate", type="text/markdown"))

        graphs = []
        for tag in self.soup.find_all("script", type="application/ld+json"):
            data = json.loads(tag.get_text())
            graphs.extend(data.get("@graph", [data]))
        types = {item.get("@type") for item in graphs}
        self.assertTrue({"Brand", "WebPage", "WebSite", "ItemList", "FAQPage"}.issubset(types))
        brand = next(item for item in graphs if item.get("@type") == "Brand")
        self.assertIn(canonical, brand["description"])

        ai_index = json.loads((self.fan / "ai-index.json").read_text(encoding="utf-8"))
        self.assertIn(canonical, ai_index["entity"]["description_ja"])
        self.assertEqual(ai_index["content_disclosure"]["characters"], "fictional adult women only")
        llms = (self.fan / "llms.txt").read_text(encoding="utf-8")
        self.assertTrue(llms.startswith("# MuscleLove FAN BASE\n\n> "))
        self.assertIn("[Plain-language brand reference]", llms)
        ElementTree.parse(self.fan / "sitemap.xml")

    def test_every_local_page_asset_and_link_resolves(self):
        missing = []
        for tag, attribute in (("a", "href"), ("link", "href"), ("script", "src"), ("img", "src")):
            for node in self.soup.find_all(tag):
                value = node.get(attribute, "")
                parsed = urlsplit(value)
                if not value or parsed.scheme or parsed.netloc or value.startswith(("#", "data:")):
                    continue
                target = ROOT / parsed.path.lstrip("/")
                if target.is_dir() or parsed.path.endswith("/"):
                    target = target / "index.html"
                if not target.is_file():
                    missing.append(value)
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
