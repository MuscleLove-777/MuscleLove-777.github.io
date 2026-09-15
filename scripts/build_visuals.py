"""Build shared visuals and the complete article index. Local files only; idempotent.

Runs before every Pages deployment. All renderable HTML is included, except
redirect stubs, verification files, templates and build tooling. Never fetches
images from third parties. Asset provenance is kept in assets/image-sources.json.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
HOST = "musclelove-777.github.io"
BASE = f"https://{HOST}"
COVERS = {
    "sport": ("/assets/images/competition.webp", "架空のプロレス会場とリングのイメージイラスト", 1536, 1024),
    "art": ("/assets/images/brand-hero.webp", "筋肉美を表現した架空の成人女性のオリジナルイラスト", 1536, 1024),
    "ai": ("/assets/images/ai-studio.webp", "AIクリエイティブをイメージしたパソコンと光るキューブ", 1536, 1024),
    "fitness": ("/assets/images/fitness-01.webp", "筋肉美を表現した架空の成人女性のAIイメージ", 720, 1080),
}
LABELS = {"art": "作品ガイド", "ai": "AI・つくる", "fitness": "筋肉・競技"}
NAV = '''<nav class="ml-nav" aria-label="メインナビゲーション"><a class="ml-brand" href="/">Muscle<span>Love</span></a><button class="ml-menu" type="button" aria-expanded="false" aria-controls="ml-nav-links">メニュー</button><div class="ml-nav-links" id="ml-nav-links"><a href="/#explore">テーマから探す</a><a href="/#articles">記事を読む</a><a href="/#gallery">ギャラリー</a><a class="ml-nav-cta" href="/patreon/" data-ml-revenue-cta="patreon_visual_nav" data-ml-revenue-destination="patreon">限定作品を見る ↗</a></div></nav>'''
CAPTION = "AIによるイメージ画像です。人物は架空の成人女性で、実在の選手・人物や実際の大会写真ではありません。"


def soup_of(path):
    return BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")


def pages(root):
    for path in sorted(root.rglob("*.html")):
        if any(part in {".git", "templates", "scripts", "tests", "node_modules"} for part in path.relative_to(root).parts):
            continue
        yield path


def redirect(soup):
    return any(str(t.get("http-equiv", "")).lower() == "refresh" for t in soup.find_all("meta"))


def is_article(path, soup):
    # Content folders are the normal contract; schema/og:type also catches new layouts.
    return bool({"articles", "posts"}.intersection(path.parts) or soup.find("meta", property="og:type", content="article") or
                any('"Article"' in t.get_text() or '"BlogPosting"' in t.get_text() for t in soup.find_all("script", type="application/ld+json")))


def category(path):
    name = str(path).lower()
    if any(word in name for word in ("lovable", "ai-tool", "claude", "flux-ai", "antigravity", "elevenlabs", "network/ai", "academy")):
        return "ai"
    if any(word in name for word in ("booth", "patreon", "eronavi", "anime-navi", "ntr", "vr-eros", "oppai", "entsuma", "games")):
        return "art"
    return "fitness"


def cover_for(path):
    key = category(path)
    if key == "fitness" and any(word in str(path) for word in ("prowrestling", "iwatani", "stardom", "wwe")):
        return COVERS["sport"]
    if key == "fitness" and any(word in str(path) for word in ("takenaka", "championship")):
        # An explicitly fictional drawing cannot be mistaken for a named athlete's photo.
        return COVERS["art"]
    return COVERS[key]


def url_for(path):
    value = "/" + path.as_posix()
    return value.removesuffix("index.html")


def local_image(root, page, src):
    parsed = urlsplit(src)
    if parsed.netloc and parsed.netloc.lower() != HOST:
        return None
    if parsed.scheme not in ("", "http", "https"):
        return None
    value = unquote(parsed.path)
    target = (root / value.lstrip("/")) if value.startswith("/") else (page.parent / value)
    target = target.resolve()
    return target if target.is_relative_to(root.resolve()) else None


def fragment(value):
    return BeautifulSoup(value, "html.parser")


def image_markup(cover, css="", eager=False):
    src, alt, width, height = cover
    return f'<img src="{src}" alt="{html.escape(alt)}" width="{width}" height="{height}" class="{css}" loading="{"eager" if eager else "lazy"}" decoding="async" data-ml-fallback="{COVERS["art"][0]}">'


def set_meta(soup, attr, key, content):
    tag = soup.find("meta", attrs={attr: key})
    if tag is None:
        tag = soup.new_tag("meta", attrs={attr: key})
        soup.head.append(tag)
    tag["content"] = content


def schema_images(soup, src):
    def visit(value):
        if isinstance(value, dict):
            types = value.get("@type", [])
            if isinstance(types, str):
                types = [types]
            if any(t in types for t in ("Article", "BlogPosting", "NewsArticle")):
                value["image"] = BASE + src
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.get_text())
        except (ValueError, TypeError):
            continue
        visit(data)
        tag.string = json.dumps(data, ensure_ascii=False)


def enhance(root, path, soup):
    relative = path.relative_to(root)
    if not soup.body or not soup.head or not soup.h1 or redirect(soup):
        return False
    if relative.as_posix() == "index.html":
        return False
    classes = soup.body.get("class", [])
    if "ml-page" not in classes:
        soup.body["class"] = classes + ["ml-page"]
    if not soup.find("link", href="/assets/css/visual.css"):
        soup.head.append(soup.new_tag("link", rel="stylesheet", href="/assets/css/visual.css"))
    if not soup.find("script", src="/assets/js/visual.js"):
        soup.head.append(soup.new_tag("script", src="/assets/js/visual.js", defer=""))
    if not soup.select_one(".ml-nav"):
        soup.body.insert(0, fragment(NAV))
    cover = cover_for(relative.as_posix())
    article = is_article(relative, soup)
    caption = "AIによるクリエイティブのイメージ画像です。" if category(relative.as_posix()) == "ai" else CAPTION
    if cover == COVERS["sport"]:
        caption = "AIによる架空の競技会場のイメージです。実際の大会・会場の写真ではありません。"
    existing = soup.select_one(".ml-cover")
    if existing:
        existing.clear()
        existing.append(fragment(image_markup(cover, eager=True)))
        existing.append(fragment(f"<figcaption>{caption}</figcaption>"))
    else:
        figure = fragment(f'<figure class="ml-cover">{image_markup(cover, eager=True)}<figcaption>{caption}</figcaption></figure>')
        # The real page content follows the cover; existing article copy is preserved.
        main = soup.find("main") or soup.body
        heading_container = soup.h1.find_parent("header")
        if heading_container and heading_container.parent == main:
            heading_container.insert_after(figure)
        else:
            main.insert(0, figure)
    set_meta(soup, "property", "og:image", BASE + cover[0])
    set_meta(soup, "name", "twitter:image", BASE + cover[0])
    set_meta(soup, "name", "twitter:card", "summary_large_image")
    schema_images(soup, cover[0])
    for card in soup.select("a.card, a.mini, a.link-card, a.site-card"):
        own_image = card.select_one(".ml-card-image")
        if own_image:
            chosen = cover_for(card.get("href", ""))
            own_image["src"], own_image["width"], own_image["height"] = chosen[0], str(chosen[2]), str(chosen[3])
            continue
        if card.find("img") or not card.get_text(strip=True):
            continue
        target = card.get("href", "")
        markup = fragment(image_markup(cover_for(target), "ml-card-image"))
        markup.img["alt"] = ""  # Adjacent card title names the destination.
        card.insert(0, markup)
        card["class"] = card.get("class", []) + ["ml-visual-card"]
    if article and not soup.select_one(".ml-brand-footer"):
        ad = fragment('''<aside class="ml-brand-footer" aria-label="MuscleLoveの作品と更新情報"><h2>筋肉美の世界を、もっと楽しむ。</h2><p>オリジナル作品や新しいコンテンツは、公式ページで。</p><a href="/patreon/" data-ml-revenue-cta="patreon_article_footer" data-ml-revenue-destination="patreon">限定作品を見る ↗</a><a href="https://x.com/MuscleGirlLove7" target="_blank" rel="noopener">公式Xで更新をチェック ↗</a></aside>''')
        footer = soup.find("footer")
        if footer:
            footer.insert_before(ad)
        else:
            (soup.find("main") or soup.body).append(ad)
    new = re.sub(r"(<!DOCTYPE[^>]*>)\s*", r"\1\n", str(soup), count=1, flags=re.I)
    if new != path.read_text(encoding="utf-8"):
        path.write_text(new, encoding="utf-8")
        return True
    return False


def article_data(root):
    items = []
    for path in pages(root):
        soup = soup_of(path)
        relative = path.relative_to(root)
        if not soup.h1 or redirect(soup) or not is_article(relative, soup):
            continue
        description = soup.find("meta", attrs={"name": "description"})
        desc = description.get("content", "") if description else ""
        # Operational instructions belong in repo docs, never new visitor-facing copy.
        desc = desc.split("内部リンク")[0].split("導線も")[0].split("。")[:1][0].strip()[:95]
        if any(word in desc for word in ("localhost", "GA4", "GSC", "収益", "回遊", "導線")):
            desc = {"ai": "AIでつくるためのヒントと使い方を紹介します。", "fitness": "競技や筋肉美について、見どころを紹介します。", "art": "オリジナル作品の特徴と楽しみ方を紹介します。"}[category(relative.as_posix())]
        items.append({"url":url_for(relative), "title":soup.h1.get_text(" ", strip=True).replace("導線", "ガイド"), "description":desc,
                      "category":category(relative.as_posix()), "cover":cover_for(relative.as_posix())[0]})
    return items


def build_home(root, items):
    # Interleave themes so the opening row is varied; all articles remain visible without JS.
    buckets = {key: [item for item in items if item["category"] == key] for key in ("fitness", "art", "ai")}
    ordered = []
    while any(buckets.values()):
        for bucket in buckets.values():
            if bucket:
                ordered.append(bucket.pop(0))
    cards = []
    for item in ordered:
        esc = lambda key: html.escape(item[key], quote=True)
        cover = cover_for(item["url"])
        cards.append(f'''<article class="ml-story" data-category="{esc('category')}"><a href="{esc('url')}"><div class="ml-story-media">{image_markup(cover)}<span class="ml-story-tag">{LABELS[item['category']]}</span></div><h3>{esc('title')}</h3><p>{esc('description')}</p><span class="ml-story-more">記事を読む <span aria-hidden="true">↗</span></span></a></article>''')
    source = (root / "templates/home.html").read_text(encoding="utf-8")
    source = source.replace("<!-- NAV -->", NAV).replace("<!-- ARTICLE_COUNT -->", str(len(items))).replace("<!-- ARTICLE_GRID -->", "\n".join(cards))
    target = root / "index.html"
    if not target.exists() or target.read_text(encoding="utf-8") != source:
        target.write_text(source, encoding="utf-8")


def audit(root):
    errors, entries, redirects = [], [], []
    manifest = json.loads((root / "assets/image-sources.json").read_text(encoding="utf-8"))
    verified = {item["asset"]: item for item in manifest}
    for src, _, _, _ in COVERS.values():
        record = verified.get(src, {})
        asset = root / src.lstrip("/")
        if not record.get("female_only_verified") or not asset.is_file():
            errors.append(f"unverified_cover:{src}")
        elif hashlib.sha256(asset.read_bytes()).hexdigest() != record.get("sha256"):
            errors.append(f"cover_changed_without_review:{src}")
    for path in pages(root):
        soup = soup_of(path)
        rel = path.relative_to(root).as_posix()
        if redirect(soup):
            redirects.append(rel)
            continue
        if not soup.h1:
            continue
        is_story = is_article(Path(rel), soup)
        images = soup.find_all("img")
        if not images:
            errors.append(f"no_visible_image:{rel}")
        if is_story and not soup.select_one(".ml-cover img"):
            errors.append(f"no_article_cover:{rel}")
        for img in images:
            src = img.get("src", "")
            local = local_image(root, path, src)
            if local is not None and (not local.is_file() or local.stat().st_size == 0):
                errors.append(f"missing_image:{rel}:{src}")
            if "alt" not in img.attrs:
                errors.append(f"missing_alt:{rel}:{src}")
        entries.append({"path":rel, "article":is_story, "images":len(images), "has_cover":bool(soup.select_one(".ml-cover img"))})
    home = soup_of(root / "index.html")
    actual = {url_for(Path(item["path"])) for item in entries if item["article"]}
    indexed = {a["href"] for a in home.select(".ml-story > a")}
    if actual != indexed:
        errors.append("article_index_coverage_mismatch")
    return {"status":"PASS" if not errors else "REVISE", "pages":len(entries), "articles":len(actual),
            "article_cards":len(indexed), "article_image_coverage":sum(p["has_cover"] for p in entries if p["article"]),
            "homepage_images":len(home.find_all("img")), "redirects_preserved":redirects, "errors":errors, "inventory":entries}


def build(root):
    for path in pages(root):
        enhance(root, path, soup_of(path))
    build_home(root, article_data(root))
    report = audit(root)
    target = root / "assets/data/visual-report.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Read-only coverage and missing-image audit")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    report = audit(args.root.resolve()) if args.check else build(args.root.resolve())
    print(json.dumps({k:v for k,v in report.items() if k != "inventory"}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
