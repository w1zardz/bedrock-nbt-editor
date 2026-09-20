#!/usr/bin/env python3
"""Check the built multilingual site without making network requests."""
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET

import build


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.lang = None
        self.direction = None
        self.ids = []
        self.links = []
        self.alternates = {}
        self.canonical = None
        self.robots = None
        self.schemas = []
        self.script = None
        self.feed(text)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "html":
            self.lang = attrs.get("lang")
            self.direction = attrs.get("dir")
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])
        if tag in ("script", "img") and "src" in attrs:
            self.links.append(attrs["src"])
        if tag == "link":
            self.links.append(attrs.get("href", ""))
            if attrs.get("rel") == "canonical":
                self.canonical = attrs.get("href")
            if attrs.get("rel") == "alternate" and "hreflang" in attrs:
                self.alternates[attrs["hreflang"]] = attrs.get("href")
        if tag == "meta" and attrs.get("name") == "robots":
            self.robots = attrs.get("content", "")
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self.script = ""

    def handle_data(self, text):
        if self.script is not None:
            self.script += text

    def handle_endtag(self, tag):
        if tag == "script" and self.script is not None:
            self.schemas.append(json.loads(self.script))
            self.script = None


def check():
    root = Path(build.ROOT)
    base = urlsplit(build.BASE)
    pages = {}
    problems = []
    for loc in build.LOCALES:
        code = loc["code"]
        for source in build.PAGES:
            slug = source["slug"]
            path = root / build.page_dir(slug, code) / "index.html"
            text = path.read_text(encoding="utf-8")
            doc = pages[path] = Page(text)
            prefix = str(path.relative_to(root))
            if doc.lang != loc["hreflang"]:
                problems.append(f"{prefix}: wrong document language")
            if loc.get("rtl") and doc.direction != "rtl":
                problems.append(f"{prefix}: RTL direction missing")
            if "noindex" in (doc.robots or "") or not (doc.robots or "").startswith("index,"):
                problems.append(f"{prefix}: complete page is not indexable")
            if doc.canonical != build.url(slug, code):
                problems.append(f"{prefix}: wrong canonical URL")
            expected = {item["hreflang"]: build.url(slug, item["code"])
                        for item in build.LOCALES}
            expected["x-default"] = build.url(slug, "en")
            if doc.alternates != expected:
                problems.append(f"{prefix}: incomplete language alternatives")
            if not any(s.get("@type") == "WebPage" and s.get("inLanguage") == code
                       for s in doc.schemas):
                problems.append(f"{prefix}: localized page schema missing")
            if "__DROPLABEL__" in text or "__HOME__" in text:
                problems.append(f"{prefix}: unresolved template placeholder")
        error_path = root / loc["dir"] / "404.html"
        doc = pages[error_path] = Page(error_path.read_text(encoding="utf-8"))
        if doc.lang != loc["hreflang"] or "noindex" not in (doc.robots or ""):
            problems.append(f"{error_path.relative_to(root)}: invalid localized 404 metadata")
        if loc.get("rtl") and doc.direction != "rtl":
            problems.append(f"{error_path.relative_to(root)}: RTL direction missing")

    for path, doc in pages.items():
        prefix = str(path.relative_to(root))
        duplicates = [identifier for identifier, count in Counter(doc.ids).items() if count > 1]
        if duplicates:
            problems.append(f"{prefix}: duplicate IDs {duplicates}")
        page_url = urljoin(build.BASE, prefix)
        for link in doc.links:
            resolved = urlsplit(urljoin(page_url, link))
            if resolved.netloc != base.netloc or resolved.scheme not in ("http", "https"):
                continue
            if not resolved.path.startswith(base.path):
                continue
            target = root / unquote(resolved.path[len(base.path):])
            if target.is_dir():
                target /= "index.html"
            if not target.is_file():
                problems.append(f"{prefix}: missing local target {link}")
            elif resolved.fragment and target.suffix == ".html":
                target_doc = pages.get(target)
                if target_doc is None:
                    target_doc = Page(target.read_text(encoding="utf-8"))
                if unquote(resolved.fragment) not in target_doc.ids:
                    problems.append(f"{prefix}: missing anchor {link}")

    sitemap = ET.parse(root / "sitemap.xml")
    urls = [node.text for node in sitemap.findall("{*}url/{*}loc")]
    expected_urls = {build.url(page["slug"], locale["code"])
                     for locale in build.LOCALES for page in build.PAGES}
    if set(urls) != expected_urls or len(urls) != len(expected_urls):
        problems.append(f"sitemap: expected exactly {len(expected_urls)} distinct localized URLs")
    return problems, len(pages)


if __name__ == "__main__":
    errors, count = check()
    for error in errors:
        print(error)
    print(f"{count} pages checked; {len(errors)} problem(s)")
    raise SystemExit(bool(errors))
