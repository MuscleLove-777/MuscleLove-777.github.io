"""Behavior checks: future article coverage, redirects, missing asset gate, repeat builds."""
import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
