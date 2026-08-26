#!/usr/bin/env python3
"""Static site generator for the Minecraft NBT Editor.

No dependencies. Renders every page from the PAGES list in content.py-style
dicts below, sharing one header, one editor widget, one footer and one set of
assets so the whole site stays a single HTML file per URL with two cacheable
assets.

    python3 tools/build.py
"""
import hashlib
import json
import os
import posixpath
import re
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://w1zardz.github.io/bedrock-nbt-editor/"
SITE_NAME = "Minecraft NBT Editor"
AUTHOR = "w1zardz"
AUTHOR_URL = "https://github.com/w1zardz"
REPO = "https://github.com/w1zardz/bedrock-nbt-editor"
TODAY = datetime.date.today().isoformat()

# Locales. "ready" locales are indexed, get hreflang and go into the sitemap;
# "draft" locales are built (so the switcher works) but marked noindex until the
# translation lands in tools/locales/<code>.json.
LOCALES = [
    # code / directory / native name / hreflang / og:locale / rtl / status
    {"code": "en",      "dir": "",       "name": "English",           "hreflang": "en",      "og": "en_US", "status": "ready"},
    {"code": "ru",      "dir": "ru",     "name": "Русский",           "hreflang": "ru",      "og": "ru_RU", "status": "draft"},
    {"code": "es",      "dir": "es",     "name": "Español",           "hreflang": "es",      "og": "es_ES", "status": "draft"},
    {"code": "pt-br",   "dir": "pt-br",  "name": "Português (BR)",    "hreflang": "pt-BR",   "og": "pt_BR", "status": "draft"},
    {"code": "de",      "dir": "de",     "name": "Deutsch",           "hreflang": "de",      "og": "de_DE", "status": "draft"},
    {"code": "fr",      "dir": "fr",     "name": "Français",          "hreflang": "fr",      "og": "fr_FR", "status": "draft"},
    {"code": "it",      "dir": "it",     "name": "Italiano",          "hreflang": "it",      "og": "it_IT", "status": "draft"},
    {"code": "pl",      "dir": "pl",     "name": "Polski",            "hreflang": "pl",      "og": "pl_PL", "status": "draft"},
    {"code": "uk",      "dir": "uk",     "name": "Українська",        "hreflang": "uk",      "og": "uk_UA", "status": "draft"},
    {"code": "tr",      "dir": "tr",     "name": "Türkçe",            "hreflang": "tr",      "og": "tr_TR", "status": "draft"},
    {"code": "id",      "dir": "id",     "name": "Bahasa Indonesia",  "hreflang": "id",      "og": "id_ID", "status": "draft"},
    {"code": "vi",      "dir": "vi",     "name": "Tiếng Việt",        "hreflang": "vi",      "og": "vi_VN", "status": "draft"},
    {"code": "th",      "dir": "th",     "name": "ไทย",                "hreflang": "th",      "og": "th_TH", "status": "draft"},
    {"code": "zh-hans", "dir": "zh-hans","name": "简体中文",            "hreflang": "zh-Hans", "og": "zh_CN", "status": "draft"},
    {"code": "ja",      "dir": "ja",     "name": "日本語",              "hreflang": "ja",      "og": "ja_JP", "status": "draft"},
    {"code": "ko",      "dir": "ko",     "name": "한국어",              "hreflang": "ko",      "og": "ko_KR", "status": "draft"},
    {"code": "ar",      "dir": "ar",     "name": "العربية",            "hreflang": "ar",      "og": "ar_AR", "status": "draft", "rtl": True},
]
LOCALE_BY_CODE = {loc["code"]: loc for loc in LOCALES}
TRANSLATABLE = ("title", "ogtitle", "desc", "keywords", "h1", "crumb", "reltitle",
                "reldesc", "answer", "droplabel", "body", "chips", "faq", "faqtitle",
                "howto", "support", "ui")


def load_translations(code):
    path = os.path.join(ROOT, "tools", "locales", code + ".json")
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        return json.load(fh)


def localized(page, code):
    """English page dict with the locale's overrides merged on top."""
    if code == "en":
        return page
    tr = TRANSLATIONS.get(code, {}).get(page["slug"], {})
    merged = dict(page)
    for key in TRANSLATABLE:
        if key in tr and tr[key]:
            merged[key] = tr[key]
    return merged


def asset_version(name):
    """Short content hash so a deploy busts the browser cache for that asset."""
    with open(os.path.join(ROOT, "assets", name), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:8]

# ---------------------------------------------------------------- primitives

def rel(depth):
    return "../" * depth


def url(slug, code="en"):
    d = LOCALE_BY_CODE[code]["dir"]
    path = "/".join(x for x in (d, slug) if x)
    return BASE + (path + "/" if path else "")


def page_dir(slug, code):
    """Repo-relative directory a page is written to."""
    d = LOCALE_BY_CODE[code]["dir"]
    return "/".join(x for x in (d, slug) if x)


def href_between(from_slug, from_code, to_slug, to_code):
    """Relative href from one built page to another, locale included."""
    src = page_dir(from_slug, from_code) or "."
    dst = page_dir(to_slug, to_code) or "."
    rel_path = posixpath.relpath(dst, src)
    if rel_path == ".":
        return "./"
    return rel_path + "/"


def plain(s):
    """Strip inline markup and entities so a heading can be used as plain text."""
    s = re.sub(r"<[^>]+>", "", s)
    return (s.replace("&amp;", "&").replace("&lt;", "<")
             .replace("&gt;", ">").replace("&nbsp;", " "))


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def slugify(text):
    text = plain(text).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "section"


def anchor_headings(body):
    """Give every h2 a stable id and return (body, [(id, text)])."""
    found = []

    def sub(m):
        inner = m.group(1)
        anchor = slugify(inner)
        found.append((anchor, plain(inner)))
        return '<h2 id="%s">%s</h2>' % (anchor, inner)

    return re.sub(r"<h2>(.*?)</h2>", sub, body, flags=re.S), found


def toc_html(items, title="On this page"):
    if len(items) < 4:
        return ""
    links = "".join('<li><a href="#%s">%s</a></li>' % (a, esc(t)) for a, t in items)
    return ('<nav class="toc" aria-label="%s"><h2 id="on-this-page">%s</h2>'
            '<ul>%s</ul></nav>' % (esc(title), esc(title), links))


NAV = [
    ("", "Editor"),
    ("level-dat-editor", "level.dat"),
    ("java-nbt-editor", "Java"),
    ("mcpe-nbt-editor", "Bedrock"),
    ("mcstructure-editor", ".mcstructure"),
    ("schematic-editor", ".schem"),
    ("playerdata-editor", "playerdata"),
    ("nbt-format", "NBT format"),
]


def nav_html(current, code):
    out = []
    for slug, label in NAV:
        href = href_between(current, code, slug, code)
        cls = ' class="active"' if slug == current else ""
        out.append('<a href="%s"%s>%s</a>' % (href, cls, esc(label)))
    return "\n".join(out)


def lang_switch_html(slug, code):
    """Dropdown of real links — crawlable, and the cookie is set on click."""
    cur = LOCALE_BY_CODE[code]
    items = []
    for loc in LOCALES:
        if loc["code"] == code:
            continue
        label = loc["name"] + ("" if loc["status"] == "ready" else " (beta)")
        items.append('<a href="%s" hreflang="%s" data-lang="%s" rel="alternate">%s</a>'
                     % (href_between(slug, code, slug, loc["code"]), loc["hreflang"],
                        loc["code"], esc(label)))
    if not items:
        return ""
    return ('<details class="lang-switch"><summary aria-label="Language">'
            '<span aria-hidden="true">🌐</span> %s</summary>'
            '<div class="lang-menu">%s</div></details>'
            % (esc(cur["name"]), "".join(items)))


def lang_urls_json(slug, code):
    return json.dumps({loc["code"]: href_between(slug, code, slug, loc["code"])
                       for loc in LOCALES}, separators=(",", ":"))


def hreflang_html(slug, code):
    out = []
    for loc in LOCALES:
        if loc["status"] != "ready":
            continue
        out.append('<link rel="alternate" hreflang="%s" href="%s">'
                   % (loc["hreflang"], url(slug, loc["code"])))
    out.append('<link rel="alternate" hreflang="x-default" href="%s">' % url(slug, "en"))
    return "\n".join(out)


EDITOR_WIDGET = """
<div class="dropzone" id="dropZone" role="button" tabindex="0" aria-label="Drop an NBT file here or click to browse">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M12 16V4m0 0L8 8m4-4l4 4"/><path d="M20 16v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2"/></svg>
<p>Drop <strong>__DROPLABEL__</strong> here</p>
<button class="btn-pick" type="button" onclick="document.getElementById('fileInput').click()">Choose File</button>
<span class="hint">level.dat &middot; .nbt &middot; .mcstructure &middot; .schem &middot; .schematic &middot; .dat &middot; chunk dumps</span>
<input type="file" id="fileInput">
</div>

<div id="editorArea">
<div class="file-info" id="fileInfo"></div>

<div class="out-bar" id="outBar">
<label>Output format
<select id="outFormat">
<option value="java">Java — big-endian, named root</option>
<option value="java-network">Java network — big-endian, nameless root</option>
<option value="bedrock-level">Bedrock level.dat — little-endian + 8-byte header</option>
<option value="bedrock">Bedrock raw — little-endian</option>
<option value="bedrock-network">Bedrock network — little-endian varint</option>
</select>
</label>
<label>Compression
<select id="outCompression">
<option value="none">None (raw)</option>
<option value="gzip">gzip</option>
<option value="zlib">zlib (deflate)</option>
</select>
</label>
</div>

<div class="search-bar">
<input type="search" id="searchInput" placeholder="Search tag name or value…" autocomplete="off" spellcheck="false" aria-label="Search NBT tags">
<button type="button" id="btnSearch">Search</button>
<button type="button" id="btnCollapse">Collapse all</button>
</div>
<div class="search-results" id="searchResults"></div>

<div class="tree" id="treeRoot"></div>
</div>

<div class="bottom-bar" id="bottomBar">
<button class="btn-add" id="btnAddRoot" type="button">+ Add Tag</button>
<button class="btn-save" id="btnSave" type="button">Save &amp; Download</button>
<button class="btn-snbt" id="btnSnbt" type="button">Export SNBT</button>
<button class="btn-close" id="btnCloseFile" type="button">Close</button>
</div>
"""

MODALS = """
<div class="toast-container" id="toastContainer" aria-live="polite"></div>

<div class="modal-overlay" id="addTagModal">
<div class="modal">
<h3>Add New Tag</h3>
<label for="newTagName">Tag Name</label>
<input type="text" id="newTagName" placeholder="e.g. MyTag" autocomplete="off">
<label for="newTagType">Tag Type</label>
<select id="newTagType">
<option value="1">TAG_Byte</option>
<option value="2">TAG_Short</option>
<option value="3">TAG_Int</option>
<option value="4">TAG_Long</option>
<option value="5">TAG_Float</option>
<option value="6">TAG_Double</option>
<option value="7">TAG_Byte_Array</option>
<option value="8" selected>TAG_String</option>
<option value="9">TAG_List</option>
<option value="10">TAG_Compound</option>
<option value="11">TAG_Int_Array</option>
<option value="12">TAG_Long_Array</option>
</select>
<label for="newTagValue">Value</label>
<input type="text" id="newTagValue" placeholder="Value" autocomplete="off">
<div id="listSubtypeRow" style="display:none">
<label for="newListSubtype">List Element Type</label>
<select id="newListSubtype">
<option value="1">TAG_Byte</option>
<option value="2">TAG_Short</option>
<option value="3">TAG_Int</option>
<option value="4">TAG_Long</option>
<option value="5">TAG_Float</option>
<option value="6">TAG_Double</option>
<option value="7">TAG_Byte_Array</option>
<option value="8">TAG_String</option>
<option value="9">TAG_List</option>
<option value="10">TAG_Compound</option>
<option value="11">TAG_Int_Array</option>
<option value="12">TAG_Long_Array</option>
</select>
</div>
<div class="modal-btns">
<button class="btn-cancel" type="button" id="addTagCancel">Cancel</button>
<button class="btn-confirm" type="button" id="addTagConfirm">Add</button>
</div>
</div>
</div>

<div class="modal-overlay" id="arrayModal">
<div class="modal">
<h3 id="arrayModalTitle">Edit Array</h3>
<label for="arrayModalText">Comma-separated values</label>
<textarea id="arrayModalText" spellcheck="false" autocomplete="off"></textarea>
<div class="modal-btns">
<button class="btn-cancel" type="button" id="arrayModalCancel">Cancel</button>
<button class="btn-confirm" type="button" id="arrayModalConfirm">Apply</button>
</div>
</div>
</div>
"""

# ---------------------------------------------------------------- structured data

def software_schema():
    return {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": SITE_NAME,
        "alternateName": ["NBT Editor Online", "Bedrock NBT Editor", "level.dat editor"],
        "url": BASE,
        "applicationCategory": "DeveloperApplication",
        "applicationSubCategory": "Game file editor",
        "operatingSystem": "Any (browser)",
        "browserRequirements": "Modern browser with BigInt and Compression Streams support",
        "softwareVersion": "2.0",
        "isAccessibleForFree": True,
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        "author": {"@type": "Person", "name": AUTHOR, "url": AUTHOR_URL},
        "publisher": {"@type": "Person", "name": AUTHOR, "url": AUTHOR_URL},
        "license": "https://opensource.org/licenses/MIT",
        "codeRepository": REPO,
        "featureList": [
            "Java Edition big-endian NBT",
            "Bedrock Edition little-endian NBT",
            "Bedrock network NBT (varint)",
            "Java network NBT (nameless root)",
            "gzip and zlib compression",
            "All 13 NBT tag types with 64-bit precision",
            "SNBT export",
            "Runs fully client-side",
        ],
    }


def breadcrumb_schema(slug, title, code="en"):
    items = [{"@type": "ListItem", "position": 1, "name": "NBT Editor",
              "item": url("", code)}]
    if slug:
        parts = slug.split("/")
        acc = ""
        for i, part in enumerate(parts):
            acc = acc + part + "/"
            name = title if i == len(parts) - 1 else part.replace("-", " ").title()
            items.append({"@type": "ListItem", "position": i + 2, "name": name,
                          "item": url(acc.rstrip("/"), code)})
    return {"@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": items}


def faq_schema(faq):
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"<[^>]+>", "", a)}}
            for q, a in faq
        ],
    }


def webpage_schema(page, code="en"):
    return {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": plain(page["title"]),
        "headline": plain(page["h1"]),
        "description": page["desc"],
        "url": url(page["slug"], code),
        "inLanguage": code,
        "datePublished": "2026-05-29",
        "dateModified": TODAY,
        "isPartOf": {"@type": "WebSite", "name": SITE_NAME, "url": BASE},
        "author": {"@type": "Person", "name": AUTHOR, "url": AUTHOR_URL},
        "primaryImageOfPage": {"@type": "ImageObject", "url": BASE + page["og"]},
        "about": {"@type": "Thing", "name": "Minecraft NBT data format"},
    }


def howto_schema(page, code="en"):
    return {
        "@context": "https://schema.org",
        "@type": "HowTo",
        "name": page["howto"]["name"],
        "description": page["desc"],
        "totalTime": page["howto"].get("time", "PT3M"),
        "tool": [{"@type": "HowToTool", "name": SITE_NAME}],
        "step": [
            {"@type": "HowToStep", "position": i + 1, "name": s[0], "text": s[1],
             "url": url(page["slug"], code) + "#step-%d" % (i + 1)}
            for i, s in enumerate(page["howto"]["steps"])
        ],
    }


# ---------------------------------------------------------------- page shell

HEAD = """<!DOCTYPE html>
<html lang="{lang}"{dirattr}>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta name="keywords" content="{keywords}">
<meta name="robots" content="{robots}">
<meta name="author" content="{author}">
<link rel="canonical" href="{canonical}">
{hreflang}
<link rel="icon" href="{r}favicon.svg" type="image/svg+xml">
<link rel="alternate icon" href="{r}favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="{r}apple-touch-icon.png">
<link rel="manifest" href="{r}site.webmanifest">
<meta property="og:type" content="{ogtype}">
<meta property="og:title" content="{ogtitle}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="{site}">
<meta property="og:image" content="{ogimage}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="{oglocale}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{ogtitle}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{ogimage}">
<meta property="article:modified_time" content="{today}">
<meta property="og:updated_time" content="{today}">
<meta name="theme-color" content="#0d1117">
<meta name="application-name" content="{site}">
<meta name="apple-mobile-web-app-title" content="NBT Editor">
<link rel="preload" href="{r}assets/nbt.js?v={jsv}" as="script">
<script>window.__LANG_URLS__={langurls};window.__NBT_STRINGS__={uistrings};</script>
<script src="{r}assets/lang.js?v={langv}" defer></script>
<link rel="stylesheet" href="{r}assets/app.css?v={cssv}">
{schema}
</head>
<body>
<a class="skip-link" href="#editor">Skip to the editor</a>
<header class="site-header">
<div class="container">
<a class="brand" href="{home}"><span>Minecraft</span> NBT Editor</a>
<span class="badge">{badge}</span>
<nav class="site-nav" aria-label="Tools">
{nav}
</nav>
{langswitch}
</div>
</header>
<main>
"""

FOOT = """</main>

<footer class="site-footer">
<div class="container footer-grid">
{footerlinks}
</div>
<p class="footer-note">{updated} {site} — {footernote}</p>
</footer>
{modals}
<script src="{r}assets/nbt.js?v={jsv}" defer></script>
</body>
</html>
"""


FOOTER_GROUPS = [
    ("Editors", ["", "level-dat-editor", "java-nbt-editor", "mcpe-nbt-editor",
                 "pocketmine-nbt-editor"]),
    ("File types", ["mcstructure-editor", "schematic-editor", "playerdata-editor",
                    "nbt-viewer", "nbtexplorer-online"]),
    ("Reference", ["nbt-format", "guides/change-world-name",
                   "guides/fix-corrupted-level-dat", "guides/edit-gamerules"]),
]


def footer_html(page, code, site_root):
    blocks = []
    heads = page.get("footerheads") or [g[0] for g in FOOTER_GROUPS]
    for (default_head, slugs), head in zip(FOOTER_GROUPS, heads):
        links = []
        for slug in slugs:
            target = localized(next(p for p in PAGES if p["slug"] == slug), code)
            links.append('<a href="%s">%s</a>'
                         % (href_between(page["slug"], code, slug, code),
                            esc(target["reltitle"])))
        blocks.append("<div><h4>%s</h4>%s</div>" % (esc(head), "".join(links)))
    blocks.append('<div><h4>%s</h4><a href="%s" rel="noopener">%s</a><a href="%s">llms.txt</a></div>'
                  % (esc(page.get("sourcehead", "Source")), REPO,
                     esc(page.get("sourcelink", "Code on GitHub")),
                     site_root + "llms.txt"))
    return "\n".join(blocks)


def related_html(page, code):
    items = []
    for slug in page.get("related", []):
        target = localized(next(p for p in PAGES if p["slug"] == slug), code)
        items.append(
            '<a class="rel-card" href="%s"><strong>%s</strong><span>%s</span></a>'
            % (href_between(page["slug"], code, slug, code),
               esc(target["reltitle"]), esc(target["reldesc"]))
        )
    if not items:
        return ""
    return ('<section class="content" aria-label="Related tools"><h2>%s</h2>'
            '<div class="rel-grid">%s</div></section>'
            % (esc(page.get("relatedtitle", "Related tools")), "".join(items)))


def breadcrumb_html(page, code):
    if not page["slug"]:
        return ""
    parts = page["slug"].split("/")
    crumbs = ['<a href="%s">%s</a>' % (href_between(page["slug"], code, "", code),
                                       esc(page.get("homecrumb", "NBT Editor")))]
    acc = ""
    for i, part in enumerate(parts):
        acc += part + "/"
        label = page["crumb"] if i == len(parts) - 1 else part.replace("-", " ").title()
        crumbs.append("<span>%s</span>" % label)
    return ('<nav class="breadcrumbs container" aria-label="Breadcrumb">'
            + ' <span class="sep">/</span> '.join(crumbs) + "</nav>")


UI_DEFAULTS = {
    "loaded": "Loaded as {0}",
    "trailing": "{0} trailing byte(s) after the root tag were ignored",
    "error": "Error: {0}",
    "readfail": "Could not read the file",
    "nofile": "No file loaded",
    "saved": "Saved {0} ({1}, {2})",
    "savefail": "Save error: {0}",
    "exported": "Exported {0}",
    "snbtfail": "SNBT error: {0}",
    "tagadded": "Tag added",
    "tagremoved": "Tag removed",
    "arrayupdated": "Array updated",
    "badvalue": "Invalid value: {0}",
    "badarray": "Invalid array: {0}",
    "nameneeded": "Tag name is required",
    "nametaken": "A tag named {0} already exists here",
    "listtype": "List already holds {0} entries",
    "editlevelname": "✎ Edit LevelName",
    "showmore": "Show {0} more of {1} …",
    "matches": "{0} match(es)",
    "nomatch": "No tag matches \"{0}\"",
    "arraytoobig": "Array has {0} entries — expand it and edit elements individually",
    "uncompressed": "uncompressed",
    "storage": "storage v{0}",
    "entries": "{0} entries",
    "langprompt": "Open this page in {0}?",
    "langyes": "Switch",
    "langno": "Stay",
}


def render(page_en, code):
    page = localized(page_en, code)
    slug = page["slug"]
    loc = LOCALE_BY_CODE[code]
    depth = len((page_dir(slug, code) or "").split("/")) if page_dir(slug, code) else 0
    r = rel(depth)
    ready = loc["status"] == "ready"

    schemas = [webpage_schema(page, code), breadcrumb_schema(slug, plain(page["h1"]), code)]
    if page.get("faq"):
        schemas.append(faq_schema(page["faq"]))
    if page.get("howto"):
        schemas.append(howto_schema(page, code))
    if not slug:
        schemas.append(software_schema())
        schemas.append({
            "@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME,
            "url": BASE, "inLanguage": code,
            "publisher": {"@type": "Person", "name": AUTHOR, "url": AUTHOR_URL},
        })
    schema_html = "\n".join(
        '<script type="application/ld+json">%s</script>' % json.dumps(s, separators=(",", ":"))
        for s in schemas)

    ui = dict(UI_DEFAULTS)
    ui.update(page.get("ui") or {})

    head = HEAD.format(
        title=esc(page["title"]), desc=esc(page["desc"]), keywords=esc(page["keywords"]),
        canonical=url(slug, code), r=r, ogtype="website" if not slug else "article",
        ogtitle=esc(plain(page.get("ogtitle", page["h1"]))), site=SITE_NAME,
        ogimage=BASE + page["og"], schema=schema_html, nav=nav_html(slug, code),
        author=AUTHOR, today=TODAY, jsv=asset_version("nbt.js"), cssv=asset_version("app.css"),
        langv=asset_version("lang.js"), lang=loc["hreflang"],
        robots=("index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1"
                if ready else "noindex, follow"),
        hreflang=hreflang_html(slug, code) if ready else
                 '<link rel="alternate" hreflang="x-default" href="%s">' % url(slug, "en"),
        oglocale=loc["og"], dirattr=' dir="rtl"' if loc.get("rtl") else "",
        home=href_between(slug, code, "", code), badge=esc(page.get("badge", "Java + Bedrock")),
        langswitch=lang_switch_html(slug, code), langurls=lang_urls_json(slug, code),
        uistrings=json.dumps(ui, separators=(",", ":"), ensure_ascii=False))

    faq_html = ""
    if page.get("faq"):
        blocks = "".join(
            "<details><summary>%s</summary><div class=\"faq-body\">%s</div></details>" % (esc(q), a)
            for q, a in page["faq"])
        faq_html = ('<section class="content" aria-label="Frequently asked questions">'
                    '<h2>%s</h2>%s</section>'
                    % (esc(page.get("faqtitle", "Frequently Asked Questions")), blocks))

    widget = EDITOR_WIDGET.replace("__DROPLABEL__", page.get("droplabel", "any NBT file"))
    body_html, headings = anchor_headings(page["body"])
    body_html = toc_html(headings, page.get("toctitle", "On this page")) + body_html

    body = """
<section class="hero" aria-label="Introduction">
<div class="container">
<h1>{h1}</h1>
<p class="support-line">{support}</p>
<p class="lede">{answer}</p>
{chips}
</div>
</section>
<div id="editor">
{widget}
</div>
<div id="contentSections">
{body}
{faq}
{related}
</div>
""".format(h1=page["h1"], answer=page["answer"], widget=widget, body=body_html,
           faq=faq_html, related=related_html(page, code),
           support=page.get("support", SUPPORT_LINE).replace("__HOME__",
                                                             href_between(slug, code, "", code)),
           chips=('<div class="chips">%s</div>' % "".join(
               '<span class="chip">%s</span>' % esc(c) for c in page.get("chips", []))
               if page.get("chips") else ""))

    html = (head + breadcrumb_html(page, code) + body
            + FOOT.format(r=r, site=SITE_NAME, modals=MODALS, repo=REPO,
                          jsv=asset_version("nbt.js"),
                          footerlinks=footer_html(page, code, r),
                          updated=page.get("updated", "Last updated %s." % TODAY),
                          footernote=page.get("footernote", FOOTER_NOTE)))
    out_dir = os.path.join(ROOT, page_dir(slug, code)) if page_dir(slug, code) else ROOT
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "index.html"), "w") as fh:
        fh.write(html)
    return os.path.join(page_dir(slug, code), "index.html")


SUPPORT_LINE = ('<strong>Supports Minecraft Bedrock Edition and Java Edition</strong> — and every '
                'server core for both, popular or obscure: Vanilla, Paper, Spigot, Purpur, Folia, '
                'Fabric, Forge, NeoForge, Mohist, Sponge, Bedrock Dedicated Server, PocketMine-MP, '
                'Nukkit, PowerNukkitX, Cloudburst, Dragonfly, Endstone, LeviLamina and the rest. '
                '<a href="__HOME__#server-software">Full list</a>.')
FOOTER_NOTE = ('free, open source (MIT), runs entirely in your browser. Not affiliated with '
               'Mojang Studios or Microsoft. Minecraft is a trademark of Mojang Studios.')


# ---------------------------------------------------------------- content

CORE_CHIPS = ["Bedrock Edition", "Java Edition", "Vanilla", "Paper", "Spigot", "Purpur",
              "Pufferfish", "Folia", "Leaves", "Fabric", "Quilt", "Forge", "NeoForge",
              "Mohist", "Arclight", "Sponge", "Bedrock Dedicated Server", "PocketMine-MP",
              "Nukkit", "PowerNukkitX", "Nukkit-MOT", "Cloudburst", "Dragonfly", "Endstone",
              "LeviLamina", "Allay", "JukeboxMC", "GoMint", "Geyser", "WaterdogPE"]

PAGES = [

{
"slug": "",
"title": "Bedrock NBT Editor Online — level.dat, MCPE, Java Too",
"ogtitle": "Bedrock &amp; Java NBT Editor — online, no upload",
"desc": "Free online NBT editor for Minecraft Bedrock and Java. Open level.dat, .mcstructure, playerdata, .nbt or .schem, edit any tag, download it back.",
"keywords": "bedrock nbt editor, nbt editor, online nbt editor, minecraft nbt editor, mcpe nbt editor, bedrock level.dat editor, nbt editor online free, level.dat editor, nbt file editor, nbt viewer, edit nbt online, minecraft save editor, nbtexplorer online",
"h1": "Bedrock NBT Editor — and Java Edition Too",
"crumb": "Editor",
"reltitle": "Minecraft NBT editor",
"reldesc": "The universal editor — every edition, every NBT file type.",
"og": "og/home.png",
"droplabel": "any NBT file",
"chips": CORE_CHIPS,
"answer": "<strong>Bedrock Edition is supported, with every Bedrock server core — and so is Java Edition, with every Java server core, down to the obscure ones.</strong> Drop a <code>level.dat</code>, <code>playerdata</code>, <code>.nbt</code>, <code>.mcstructure</code>, <code>.schem</code> or <code>.schematic</code> file into the box below, edit any tag in the tree, and download it back in exactly the same binary format. Byte order, header and compression are detected automatically. Everything runs in your browser — no upload, no account, no install.",
"body": """
<section class="content" aria-label="Supported files">
<h2>Every NBT file Minecraft writes</h2>
<p>NBT (Named Binary Tag) is one format with several encodings, and every Minecraft edition, launcher and server core uses a different combination of them. This editor implements all of them and picks the right one from the bytes themselves, so you never have to know which variant a file is before you open it.</p>
<div class="table-wrap">
<table class="matrix">
<thead><tr><th>File</th><th>Comes from</th><th>Encoding</th><th>Compression</th></tr></thead>
<tbody>
<tr><td><code>level.dat</code></td><td>Java world — Vanilla, Paper, Spigot, Fabric, Forge</td><td>Big-endian, named root</td><td>gzip</td></tr>
<tr><td><code>level.dat</code></td><td>Bedrock world — BDS, PocketMine-MP, Nukkit, MCPE</td><td>Little-endian + 8-byte header</td><td>None</td></tr>
<tr><td><code>&lt;uuid&gt;.dat</code></td><td>Java <code>playerdata/</code></td><td>Big-endian</td><td>gzip</td></tr>
<tr><td><code>servers.dat</code>, <code>hotbar.nbt</code></td><td>Java client</td><td>Big-endian</td><td>None</td></tr>
<tr><td><code>idcounts.dat</code>, <code>raids.dat</code>, <code>map_*.dat</code></td><td>Java world <code>data/</code></td><td>Big-endian</td><td>gzip</td></tr>
<tr><td><code>.nbt</code></td><td>Structure blocks, datapack structures</td><td>Big-endian</td><td>gzip</td></tr>
<tr><td><code>.schem</code>, <code>.schematic</code></td><td>WorldEdit, Sponge, MCEdit</td><td>Big-endian</td><td>gzip</td></tr>
<tr><td><code>.mcstructure</code></td><td>Bedrock structure blocks</td><td>Little-endian</td><td>None</td></tr>
<tr><td>Chunk payload</td><td>Region <code>.mca</code> extract, LevelDB value</td><td>Either byte order</td><td>zlib or none</td></tr>
<tr><td>Packet dump</td><td>Bedrock protocol, Java 1.20.2+ protocol</td><td>Varint LE / nameless BE</td><td>None</td></tr>
</tbody>
</table>
</div>
</section>

<section class="content" aria-label="How to use">
<h2>How to edit an NBT file</h2>
<div class="card">
<ol class="steps">
<li><strong>Get the file off the server or device.</strong> Java servers keep it in <code>world/</code>, Bedrock servers in <code>worlds/YourWorld/</code>, Android in <code>games/com.mojang/minecraftWorlds/&lt;id&gt;/</code>. Stop the server first so the file is not being written while you copy it.</li>
<li><strong>Drop it into the editor.</strong> The badge above the tree tells you what was detected — edition, encoding, compression and, for Bedrock, the storage version from the header.</li>
<li><strong>Edit.</strong> Tap a value to change it in place. Use search to jump to a tag by name or value, <strong>+</strong> to add tags to any compound or list, <strong>×</strong> to remove them.</li>
<li><strong>Save &amp; Download.</strong> The output format and compression selectors default to whatever the file arrived as, so a plain edit is a byte-faithful round trip.</li>
<li><strong>Put it back and restart.</strong> Keep the original as a backup until the world has loaded once and looks right.</li>
</ol>
</div>
</section>

<section class="content" aria-label="Features">
<h2>What makes this editor different</h2>
<div class="features-grid">
<article class="feature-card"><h3>Five encodings, one drop zone</h3><p>Java big-endian, Bedrock little-endian, Bedrock varint network NBT, nameless-root network NBT from Java 1.20.2+, and Bedrock's headered <code>level.dat</code>. Detected, not guessed.</p></article>
<article class="feature-card"><h3>gzip and zlib in the browser</h3><p>Decompression and recompression use the native Compression Streams API, so a Java <code>level.dat</code> round-trips into a file the game accepts unchanged.</p></article>
<article class="feature-card"><h3>Real 64-bit longs</h3><p><code>TAG_Long</code> values are held as <code>BigInt</code>. World seeds and UUID halves survive editing instead of being mangled by floating-point rounding, which is where most browser NBT tools break.</p></article>
<article class="feature-card"><h3>Correct string encoding</h3><p>Java writes modified UTF-8 (CESU-8), Bedrock writes standard UTF-8. The editor encodes per edition, so emoji and non-Latin world names come out intact.</p></article>
<article class="feature-card"><h3>Built for big files</h3><p>Arrays live in typed arrays and the tree renders lazily, 200 entries at a time. A megabyte of chunk NBT opens without freezing the tab.</p></article>
<article class="feature-card"><h3>Search across the tree</h3><p>Find any tag by name or value anywhere in the file and jump straight to it with the path expanded.</p></article>
<article class="feature-card"><h3>SNBT export</h3><p>Dump the whole tree as SNBT — the text form used by <code>/data</code> and datapacks — for diffing, sharing or pasting into a command.</p></article>
<article class="feature-card"><h3>Format conversion</h3><p>Read a Bedrock file, write Java big-endian gzip, or the reverse. Useful for protocol work, tests and tooling.</p></article>
<article class="feature-card"><h3>Nothing leaves your device</h3><p>The file is read with <code>FileReader</code>, parsed in JavaScript, and handed back as an in-memory blob. No upload endpoint exists.</p></article>
</div>
</section>

<section class="content" aria-label="Supported server software" id="server-software">
<h2>Supported server software — all of it</h2>
<p>NBT is written by the game, not by the server implementation, so any core that stores a Minecraft world stores it in one of the encodings this editor reads. That is the whole list below, and it is not a marketing list: a core that writes a world writes it in Vanilla's shape, because the client on the other end has to read it.</p>
<div class="card">
<h3>Bedrock Edition — little-endian NBT, 8-byte <code>level.dat</code> header</h3>
<p><strong>Bedrock Dedicated Server (BDS)</strong>, <strong>PocketMine-MP</strong> (PM3, PM4, PM5), <strong>Nukkit</strong>, <strong>Nukkit-MOT</strong>, <strong>PowerNukkitX</strong>, <strong>Cloudburst Server</strong>, <strong>Dragonfly</strong>, <strong>Endstone</strong>, <strong>LeviLamina</strong> and <strong>BDSX</strong>, <strong>Allay</strong>, <strong>JukeboxMC</strong>, <strong>GoMint</strong>, <strong>Sculk</strong>, <strong>ElementZero</strong>, <strong>LiteLoaderBDS</strong>, plus the <strong>MCPE</strong> and <strong>MCBE</strong> clients themselves on Android, iOS, Windows, console and Switch. Same <code>worlds/&lt;World&gt;/level.dat</code>, same header, same tags — see the <a href="pocketmine-nbt-editor/">server-side workflow</a>.</p>
<h3>Java Edition — big-endian NBT, gzip</h3>
<p><strong>Vanilla</strong>, <strong>CraftBukkit</strong>, <strong>Spigot</strong>, <strong>Paper</strong>, <strong>Purpur</strong>, <strong>Pufferfish</strong>, <strong>Folia</strong>, <strong>Leaves</strong>, <strong>Gale</strong>, <strong>Petal</strong>, <strong>Airplane</strong>, <strong>Sponge</strong> (SpongeVanilla, SpongeForge), <strong>Fabric</strong>, <strong>Quilt</strong>, <strong>Forge</strong>, <strong>NeoForge</strong>, <strong>Mohist</strong>, <strong>Arclight</strong>, <strong>Magma</strong>, <strong>Ketting</strong>, <strong>Banner</strong>, <strong>Cardboard</strong>, <strong>Glowstone</strong>, <strong>Thermos</strong>, <strong>Uberbukkit</strong> and every other fork, modpack server or ancient legacy build. If it writes <code>world/level.dat</code>, this editor opens it — <a href="java-nbt-editor/">details here</a>.</p>
<h3>Proxies and bridges</h3>
<p><strong>Geyser</strong>, <strong>WaterdogPE</strong>, <strong>Waterfall</strong>, <strong>Velocity</strong> and <strong>BungeeCord</strong> do not own worlds; they move NBT over the wire. Captures from those sockets are network NBT — varint little-endian on the Bedrock side, nameless-root big-endian on Java 1.20.2+ — and both open here directly.</p>
<h3>Anything not on this list</h3>
<p>Custom forks, private cores, teaching projects, a server you wrote yourself: if the file is NBT, the editor detects which of the five encodings it is and opens it. Nothing here is keyed to a core's name.</p>
</div>
</section>

<section class="content" aria-label="Scripting">
<h2>Use the parser from your own code</h2>
<p>The page exposes its engine on <code>window.NBT</code>, so the same parser that powers the UI can be driven from the browser console or reused in a userscript:</p>
<pre class="code"><code>const bytes = new Uint8Array(await file.arrayBuffer());
const { root, format, compression, headerVersion } = await NBT.read(bytes);

root.value.find(t =&gt; t.name === "LevelName").value = "New World";

const out = await NBT.write(root, format, { compression, headerVersion });</code></pre>
<p>Tags are plain objects — <code>{ type, name, value, listType }</code> — arrays are <code>Int8Array</code>, <code>Int32Array</code> and <code>BigInt64Array</code>, and longs are <code>BigInt</code>. The full <a href="nbt-format/">NBT format reference</a> documents every tag type and how each encoding differs.</p>
</section>
""",
"faq": [
("Is this NBT editor free?", "<p>Yes, and open source under the MIT licence. There is no paid tier, no sign-up and no upload quota, because there is no server component at all — the whole editor is one static page plus two asset files.</p>"),
("Does it work with Java Edition and Bedrock Edition?", "<p>Both. Java Edition files are big-endian and usually gzip-compressed; Bedrock files are little-endian, and <code>level.dat</code> carries an extra 8-byte header. The editor detects which one it received and writes the same variant back on save.</p>"),
("Is my world file uploaded anywhere?", "<p>No. The file is read locally with the FileReader API and the download is produced from an in-memory blob. Once the page has loaded you can disconnect from the network and it still works.</p>"),
("Can I use it on Android or iOS?", "<p>Yes. The layout is mobile-first with 44&nbsp;px tap targets and a fixed action bar. On Android you can pick a world file straight out of a file manager; on iOS the file has to be in the Files app first because of sandboxing.</p>"),
("What is the difference between NBT and SNBT?", "<p>NBT is the binary encoding Minecraft stores on disk. SNBT is its text form, the syntax you type into commands like <code>/data merge</code>. This editor reads binary NBT and can export SNBT, which makes it easy to diff two files or paste a structure into a command.</p>"),
("Which tools does this replace?", "<p>Desktop NBT editors such as NBTExplorer, plus the various single-purpose web tools that only handle one edition. See the <a href=\"nbtexplorer-online/\">NBTExplorer online comparison</a> for what carries over and what does not.</p>"),
],
"related": ["level-dat-editor", "java-nbt-editor", "mcpe-nbt-editor", "nbt-format",
            "mcstructure-editor", "guides/change-world-name"],
},

{
"slug": "level-dat-editor",
"title": "level.dat Editor Online — Edit Minecraft World Settings",
"ogtitle": "level.dat Editor — edit any world setting online",
"desc": "Edit Minecraft level.dat online: world name, game mode, difficulty, spawn, seed and game rules, for Java and Bedrock worlds. Nothing is uploaded.",
"keywords": "level.dat editor, edit level.dat, level dat editor online, minecraft level.dat, level.dat editor online free, change world name level.dat, level.dat viewer, world settings editor",
"h1": "level.dat Editor — Edit Minecraft World Settings Online",
"crumb": "level.dat editor",
"reltitle": "level.dat editor",
"reldesc": "World name, game mode, spawn, difficulty and game rules.",
"og": "og/level-dat.png",
"droplabel": "level.dat",
"chips": ["Java level.dat", "Bedrock level.dat", "level.dat_old", "gzip", "8-byte header"],
"answer": "<code>level.dat</code> is the file that holds everything a Minecraft world knows about itself: its name, game mode, difficulty, spawn point, game rules, weather state and the version it was last opened with. Drop it below to edit any of those values directly. Java files (gzip, big-endian) and Bedrock files (little-endian with an 8-byte header) are both handled, and the file is written back in the format it arrived in.",
"body": """
<section class="content" aria-label="Tags in level.dat">
<h2>The tags people actually edit</h2>
<p>A Java <code>level.dat</code> keeps almost everything inside a single <code>Data</code> compound; a Bedrock <code>level.dat</code> keeps its tags flat at the root. The names below are the ones worth knowing — search for any of them in the tree and the editor will jump to it.</p>
<div class="table-wrap">
<table class="matrix">
<thead><tr><th>Tag</th><th>Type</th><th>Edition</th><th>What it controls</th></tr></thead>
<tbody>
<tr><td><code>LevelName</code></td><td>String</td><td>Both</td><td>The world's display name. Stale after copying a world folder — the <a href="../guides/change-world-name/">rename guide</a> covers it.</td></tr>
<tr><td><code>GameType</code> / <code>gameType</code></td><td>Int</td><td>Both</td><td>0 survival, 1 creative, 2 adventure, 3 spectator.</td></tr>
<tr><td><code>Difficulty</code></td><td>Byte / Int</td><td>Both</td><td>0 peaceful, 1 easy, 2 normal, 3 hard.</td></tr>
<tr><td><code>hardcore</code></td><td>Byte</td><td>Both</td><td>1 locks the world to hardcore rules.</td></tr>
<tr><td><code>allowCommands</code> / <code>commandsEnabled</code></td><td>Byte</td><td>Java / Bedrock</td><td>Whether cheats are enabled.</td></tr>
<tr><td><code>SpawnX</code>, <code>SpawnY</code>, <code>SpawnZ</code></td><td>Int</td><td>Both</td><td>World spawn coordinates.</td></tr>
<tr><td><code>Time</code>, <code>DayTime</code></td><td>Long</td><td>Java</td><td>Total ticks and the time of day.</td></tr>
<tr><td><code>currentTick</code></td><td>Int</td><td>Bedrock</td><td>Bedrock's equivalent world clock.</td></tr>
<tr><td><code>RandomSeed</code> / <code>WorldGenSettings.seed</code></td><td>Long</td><td>Java</td><td>World seed. Held as a real 64-bit value here, not a rounded double.</td></tr>
<tr><td><code>GameRules</code> / individual gamerule tags</td><td>Compound / Byte</td><td>Java / Bedrock</td><td>Everything <code>/gamerule</code> sets — see the <a href="../guides/edit-gamerules/">game rules guide</a>.</td></tr>
<tr><td><code>DataVersion</code></td><td>Int</td><td>Java</td><td>The world format version. Check it before moving a world between Minecraft versions.</td></tr>
<tr><td><code>lastOpenedWithVersion</code></td><td>List of Int</td><td>Bedrock</td><td>The Bedrock client or server build that last wrote the world.</td></tr>
<tr><td><code>Player</code></td><td>Compound</td><td>Both</td><td>Single-player inventory, position and stats embedded in the world file.</td></tr>
</tbody>
</table>
</div>
</section>

<section class="content" aria-label="Where to find level.dat">
<h2>Where <code>level.dat</code> lives</h2>
<div class="table-wrap">
<table class="matrix">
<thead><tr><th>Platform</th><th>Path</th></tr></thead>
<tbody>
<tr><td>Java server (Vanilla, Paper, Spigot, Fabric, Forge)</td><td><code>world/level.dat</code>, next to <code>region/</code> and <code>playerdata/</code></td></tr>
<tr><td>Java client, Windows</td><td><code>%APPDATA%\\.minecraft\\saves\\&lt;World&gt;\\level.dat</code></td></tr>
<tr><td>Java client, macOS</td><td><code>~/Library/Application Support/minecraft/saves/&lt;World&gt;/level.dat</code></td></tr>
<tr><td>Java client, Linux</td><td><code>~/.minecraft/saves/&lt;World&gt;/level.dat</code></td></tr>
<tr><td>Bedrock Dedicated Server, PocketMine-MP, Nukkit</td><td><code>worlds/&lt;World&gt;/level.dat</code></td></tr>
<tr><td>Bedrock on Android</td><td><code>Android/data/com.mojang.minecraftpe/files/games/com.mojang/minecraftWorlds/&lt;id&gt;/level.dat</code></td></tr>
<tr><td>Bedrock on Windows</td><td><code>%LOCALAPPDATA%\\Packages\\Microsoft.MinecraftUWP_*\\LocalState\\games\\com.mojang\\minecraftWorlds\\&lt;id&gt;\\level.dat</code></td></tr>
</tbody>
</table>
</div>
<p>Minecraft also writes a <code>level.dat_old</code> next to it — the previous save. It opens in this editor too, and it is the first thing to try if the current file will not load.</p>
</section>

<section class="content" aria-label="Safety">
<h2>Editing safely</h2>
<div class="card">
<ul>
<li><strong>Stop the server or close the game first.</strong> Minecraft rewrites <code>level.dat</code> on autosave and on shutdown, and a running server will overwrite your edit — or worse, write over a half-copied file.</li>
<li><strong>Keep the original.</strong> This editor never modifies the file you dropped in; it produces a new download. Keep the old copy until the world has loaded once.</li>
<li><strong>Do not change tag types.</strong> Changing <code>Difficulty</code> from Byte to Int, or renaming a tag Minecraft expects, is how a world stops loading. Edit values, not the structure, unless you know why.</li>
<li><strong>Keep the Bedrock header intact.</strong> The 8-byte header carries the storage version and payload length. The editor rewrites the length automatically and preserves the version; hand-edited files that lose it will not load.</li>
</ul>
</div>
</section>
""",
"faq": [
("Can I edit level.dat without downloading software?", "<p>Yes — that is what this page is. The parser runs in your browser, so there is nothing to install and no operating system requirement beyond a current browser.</p>"),
("Why does my world still show the old name?", "<p>Because the name in the world list comes from <code>LevelName</code> inside <code>level.dat</code>, not from the folder name. Copying or renaming a folder leaves the tag untouched. Edit the tag and the list updates.</p>"),
("Does this work with level.dat_old?", "<p>Yes. <code>level.dat_old</code> is the previous save in the same format. If the current file is corrupt, open the <code>_old</code> copy, confirm it looks sane, and restore it under the original name.</p>"),
("Can I change the world seed here?", "<p>You can edit the seed tag, but it only affects terrain generated after the change — chunks already on disk keep the shape they were generated with, so the join between old and new terrain will be visible.</p>"),
("Will editing level.dat get me banned or corrupt my world?", "<p>It is your own save file, so there is nothing to ban. Corruption comes from editing while the server is running, or from changing tag types and names rather than values. Stop the server, edit values, keep a backup.</p>"),
],
"related": ["", "java-nbt-editor", "mcpe-nbt-editor", "guides/change-world-name",
            "guides/fix-corrupted-level-dat", "guides/edit-gamerules"],
},

]

PAGES += [

{
"slug": "java-nbt-editor",
"title": "Java Edition NBT Editor — level.dat, playerdata, .nbt Online",
"ogtitle": "Java Edition NBT Editor — big-endian, gzip, online",
"desc": "Online NBT editor for Minecraft Java Edition: gzip big-endian level.dat, playerdata, servers.dat and structure .nbt from Paper, Spigot, Fabric, Forge.",
"keywords": "java nbt editor, minecraft java edition nbt, java level.dat editor, paper level.dat, spigot nbt editor, fabric nbt, forge nbt editor, playerdata editor java, big-endian nbt, gzip nbt editor",
"h1": "Java Edition NBT Editor",
"crumb": "Java",
"reltitle": "Java Edition NBT editor",
"reldesc": "Big-endian, gzip — Vanilla, Paper, Spigot, Fabric, Forge.",
"og": "og/java.png",
"droplabel": "a Java NBT file",
"chips": ["Vanilla", "Paper", "Spigot", "Purpur", "Folia", "Fabric", "Quilt", "Forge", "NeoForge", "Sponge"],
"answer": "Minecraft Java Edition stores its data as big-endian NBT, almost always gzip-compressed. Drop any Java file below — <code>level.dat</code>, a <code>playerdata</code> UUID file, <code>servers.dat</code>, a structure <code>.nbt</code>, a WorldEdit schematic — and the editor decompresses it, parses it big-endian and writes it back gzip-compressed so the game accepts it unchanged.",
"body": """
<section class="content" aria-label="Java NBT files">
<h2>What a Java world is made of</h2>
<p>Everything below opens in the editor above. Region files themselves (<code>.mca</code>) are a container of many compressed chunks rather than a single NBT document, so extract a chunk payload first — the editor reads the zlib-compressed chunk NBT that comes out.</p>
<div class="table-wrap">
<table class="matrix">
<thead><tr><th>Path</th><th>Contents</th><th>Compression</th></tr></thead>
<tbody>
<tr><td><code>world/level.dat</code></td><td>World name, game mode, rules, spawn, <code>DataVersion</code></td><td>gzip</td></tr>
<tr><td><code>world/level.dat_old</code></td><td>Previous save of the same file</td><td>gzip</td></tr>
<tr><td><code>world/playerdata/&lt;uuid&gt;.dat</code></td><td>Inventory, ender chest, position, health, XP, attributes</td><td>gzip</td></tr>
<tr><td><code>world/data/raids.dat</code>, <code>idcounts.dat</code>, <code>map_*.dat</code></td><td>Raid state, entity id counters, map items</td><td>gzip</td></tr>
<tr><td><code>world/data/scoreboard.dat</code></td><td>Objectives, teams, scores</td><td>gzip</td></tr>
<tr><td><code>world/region/*.mca</code></td><td>Chunk NBT inside a region container</td><td>zlib per chunk</td></tr>
<tr><td><code>servers.dat</code></td><td>Multiplayer server list from the client</td><td>none</td></tr>
<tr><td><code>hotbar.nbt</code></td><td>Saved creative hotbars</td><td>none</td></tr>
<tr><td><code>*.nbt</code> in datapacks</td><td>Structures placed by structure blocks and jigsaws</td><td>gzip</td></tr>
</tbody>
</table>
</div>
</section>

<section class="content" aria-label="Java NBT encoding">
<h2>How Java encodes NBT</h2>
<div class="card">
<ul>
<li><strong>Big-endian.</strong> Every integer and float is stored most-significant byte first, matching Java's <code>DataOutputStream</code>.</li>
<li><strong>Named root.</strong> The file starts with tag type <code>0x0A</code>, then a UTF-8 length-prefixed root name — historically empty in <code>level.dat</code>.</li>
<li><strong>Modified UTF-8.</strong> Strings use Java's <code>writeUTF</code> encoding: a two-byte length, NUL written as <code>C0 80</code>, and characters outside the basic plane split into two three-byte halves (CESU-8). A tool that treats this as plain UTF-8 mangles emoji in world names; this editor encodes it correctly.</li>
<li><strong>gzip by default.</strong> <code>NbtIo.readCompressed</code> expects a gzip stream. Files written uncompressed load in some tools but not in the game.</li>
<li><strong>Nameless root on the network.</strong> Since 1.20.2 the protocol sends NBT without the root name. Packet dumps in that shape are detected as <em>Java network</em> here.</li>
</ul>
</div>
</section>

<section class="content" aria-label="Server cores">
<h2>Paper, Spigot, Fabric, Forge — same files</h2>
<p>Forks and mod loaders change how the server runs, not how the world is written. Paper, Purpur, Pufferfish, Folia, Fabric, Quilt, Forge, NeoForge, Mohist, Arclight and Sponge all use Vanilla's NBT layout, so anything on this page applies to them unchanged. What forks do add is extra files beside the world — <code>paper-world.yml</code>, mod configs — which are YAML or TOML and unrelated to NBT.</p>
<p>Mods and plugins may add their own compounds inside <code>level.dat</code> or <code>playerdata</code>. Those tags open here like any other; leave them alone unless you know what the mod does with them.</p>
</section>

<section class="content" aria-label="DataVersion">
<h2><code>DataVersion</code> and version migration</h2>
<p>Java worlds carry a <code>DataVersion</code> integer that identifies the world format, incremented on every snapshot. Some useful anchors: 1.16.5 is 2586, 1.17.1 is 2730, 1.18.2 is 2975, 1.19.4 is 3337, 1.20.4 is 3700, 1.21 is 3953. Opening a world in an older client than the one that wrote it is refused precisely because of this tag, and lowering it by hand does not downgrade the chunk data behind it — it just removes the guard rail. Read it to find out what wrote a world; do not edit it to force a downgrade.</p>
</section>
""",
"faq": [
("Can I open a Java level.dat that will not load in game?", "<p>Usually yes — the editor is more tolerant than the game about trailing bytes, and it reports exactly where parsing stopped if the file is truncated. If it refuses too, try <code>level.dat_old</code>, which is the previous autosave.</p>"),
("Does it support 1.20.2+ network NBT?", "<p>Yes. From 1.20.2 the protocol omits the root name. A dump in that shape is detected as the <em>Java network</em> format and can be re-saved either as network NBT or as a normal named-root file.</p>"),
("Can I edit a chunk from a .mca region file?", "<p>You can edit chunk NBT once it is extracted from the region container. The <code>.mca</code> itself is an index plus many zlib-compressed chunk payloads, and this editor works on a single NBT document, not on the container.</p>"),
("Will editing playerdata break the player?", "<p>Only if the server is running while you do it — it holds player state in memory and writes it out on logout, overwriting your file. Take the player offline, edit, then let them reconnect. See the <a href=\"../playerdata-editor/\">playerdata editor</a>.</p>"),
("Is a gzip level.dat required?", "<p>The vanilla loader reads gzip. Save with compression set to gzip — the default when the file arrived that way — and the game will accept it.</p>"),
],
"related": ["", "level-dat-editor", "playerdata-editor", "schematic-editor", "nbt-format", "mcpe-nbt-editor"],
},

{
"slug": "mcpe-nbt-editor",
"title": "MCPE NBT Editor — Pocket Edition level.dat, Android &amp; iOS",
"ogtitle": "Bedrock NBT Editor — level.dat, MCPE, MCBE",
"desc": "Edit MCPE and Bedrock world files online: level.dat with its 8-byte header, .mcstructure and little-endian NBT, from Android, iOS, Windows or a server.",
"keywords": "mcpe nbt editor, minecraft pe nbt editor, pocket edition level.dat, bedrock nbt editor, mcbe nbt editor, bedrock level.dat editor, minecraft pe level.dat, little-endian nbt, bedrock world editor, edit level.dat android, bedrock dedicated server level.dat",
"h1": "MCPE NBT Editor — Minecraft Pocket Edition Files",
"crumb": "MCPE",
"reltitle": "MCPE NBT editor",
"reldesc": "Little-endian NBT and the 8-byte level.dat header.",
"og": "og/bedrock.png",
"droplabel": "a Bedrock level.dat",
"chips": ["MCPE", "MCBE", "Bedrock Dedicated Server", "PocketMine-MP", "Nukkit", "PowerNukkitX", "Cloudburst", "Dragonfly", "Endstone"],
"answer": "Bedrock Edition writes NBT little-endian, and its <code>level.dat</code> is preceded by an 8-byte header holding the storage version and the payload length. Drop a Bedrock file below — <code>level.dat</code>, <code>.mcstructure</code>, a LevelDB value, a protocol dump — and the editor reads it, keeps the header intact, recalculates the length on save, and hands the file back ready to drop into the world folder.",
"body": """
<section class="content" aria-label="Bedrock level.dat header">
<h2>The 8-byte header, and why it matters</h2>
<p>A Bedrock <code>level.dat</code> is not raw NBT. The first four bytes are a little-endian storage version (8 and 10 are the values in the wild), the next four are the byte length of the NBT payload, and the tags follow uncompressed. Edit the payload without fixing that length and the game rejects the file — which is exactly what happens when people open Bedrock saves in a Java-only NBT tool.</p>
<div class="table-wrap">
<table class="matrix">
<thead><tr><th>Offset</th><th>Size</th><th>Field</th></tr></thead>
<tbody>
<tr><td>0</td><td>4 bytes</td><td>Storage version, little-endian int</td></tr>
<tr><td>4</td><td>4 bytes</td><td>Payload length in bytes, little-endian unsigned</td></tr>
<tr><td>8</td><td>rest</td><td>Little-endian NBT, root compound, uncompressed</td></tr>
</tbody>
</table>
</div>
<p>This editor shows the storage version in the file bar, preserves it, and rewrites the length for you every time you save.</p>
</section>

<section class="content" aria-label="Bedrock tags">
<h2>Bedrock tags worth knowing</h2>
<p>Bedrock keeps its settings flat at the root of <code>level.dat</code> rather than nesting them under a <code>Data</code> compound the way Java does, and game rules are individual tags instead of a <code>GameRules</code> child.</p>
<div class="table-wrap">
<table class="matrix">
<thead><tr><th>Tag</th><th>Type</th><th>Meaning</th></tr></thead>
<tbody>
<tr><td><code>LevelName</code></td><td>String</td><td>World name shown in the world list and in server output</td></tr>
<tr><td><code>GameType</code></td><td>Int</td><td>0 survival, 1 creative, 2 adventure</td></tr>
<tr><td><code>Difficulty</code></td><td>Int</td><td>0 peaceful … 3 hard</td></tr>
<tr><td><code>commandsEnabled</code></td><td>Byte</td><td>Cheats on or off</td></tr>
<tr><td><code>SpawnX</code>, <code>SpawnY</code>, <code>SpawnZ</code></td><td>Int</td><td>World spawn</td></tr>
<tr><td><code>RandomSeed</code></td><td>Long</td><td>World seed, a true 64-bit value</td></tr>
<tr><td><code>lastOpenedWithVersion</code></td><td>List of Int</td><td>Client or server build that last wrote the world</td></tr>
<tr><td><code>StorageVersion</code></td><td>Int</td><td>World storage revision, mirrors the header</td></tr>
<tr><td><code>experiments</code></td><td>Compound</td><td>Experimental toggles enabled for the world</td></tr>
<tr><td><code>keepinventory</code>, <code>domobspawning</code>, …</td><td>Byte</td><td>Game rules, one lowercase tag each</td></tr>
</tbody>
</table>
</div>
</section>

<section class="content" aria-label="Where Bedrock files live">
<h2>Finding the file on each platform</h2>
<ul>
<li><strong>Android:</strong> <code>Android/data/com.mojang.minecraftpe/files/games/com.mojang/minecraftWorlds/&lt;id&gt;/level.dat</code>. Newer Android releases restrict that folder — use the in-game world export, or a file manager with the right access.</li>
<li><strong>iOS:</strong> export the world to a <code>.mcworld</code> from the game, open it in the Files app, and unzip it there — <code>level.dat</code> sits at the archive root.</li>
<li><strong>Windows:</strong> <code>%LOCALAPPDATA%\\Packages\\Microsoft.MinecraftUWP_8wekyb3d8bbwe\\LocalState\\games\\com.mojang\\minecraftWorlds\\&lt;id&gt;\\level.dat</code>.</li>
<li><strong>Bedrock Dedicated Server:</strong> <code>worlds/&lt;World&gt;/level.dat</code>.</li>
<li><strong>PocketMine-MP, Nukkit, PowerNukkitX:</strong> <code>worlds/&lt;World&gt;/level.dat</code> — see the <a href="../pocketmine-nbt-editor/">server-side guide</a>.</li>
</ul>
<p>The world folder name is a random id, not the world name. Sort by modification time, or open a few <code>level.dat</code> files here and read <code>LevelName</code> to identify the right one.</p>
</section>

<section class="content" aria-label="Other Bedrock NBT">
<h2>Beyond <code>level.dat</code></h2>
<p>Bedrock keeps chunks, entities and block entities in a LevelDB database in the <code>db/</code> folder, with little-endian NBT as the value of many keys. Extract a value and it opens here as <em>Bedrock raw</em> — no header, no compression. Structure files use the same encoding: see the <a href="../mcstructure-editor/">.mcstructure editor</a>. Protocol captures use the varint variant, which the editor detects as <em>Bedrock network</em>.</p>
</section>
""",
"faq": [
("Why will not my Bedrock level.dat open in NBTExplorer?", "<p>Because NBTExplorer expects Java's big-endian layout and does not know about the 8-byte Bedrock header. This editor handles both, and rewrites the header length when it saves.</p>"),
("Can I edit an MCPE world on my phone?", "<p>Yes. Open this page in the phone's browser, pick the file from your file manager, edit and save. The download lands in your Downloads folder; copy it back over the original.</p>"),
("What is the difference between storage version 8 and 10?", "<p>They mark revisions of the Bedrock world storage format; 10 is what current clients write. The editor keeps whatever value the file had rather than forcing one, because rewriting it does not migrate the world data behind it.</p>"),
("Does this work with .mcworld files?", "<p>Not directly — a <code>.mcworld</code> is a zip archive. Unzip it, edit <code>level.dat</code> here, put it back in the archive, and rename it back to <code>.mcworld</code>.</p>"),
("Does it work with Bedrock game rules?", "<p>Yes. Bedrock stores each rule as its own lowercase byte tag at the root — <code>keepinventory</code>, <code>domobspawning</code>, <code>showcoordinates</code> and so on. Set the byte to 1 or 0. The <a href=\"../guides/edit-gamerules/\">game rules guide</a> lists them.</p>"),
],
"related": ["", "level-dat-editor", "pocketmine-nbt-editor", "mcstructure-editor", "java-nbt-editor", "guides/change-world-name"],
},

{
"slug": "pocketmine-nbt-editor",
"title": "PocketMine-MP level.dat Editor — PMMP, Nukkit, BDS Online",
"ogtitle": "PocketMine-MP & Nukkit level.dat editor",
"desc": "Edit level.dat for PocketMine-MP, Nukkit, PowerNukkitX and Bedrock Dedicated Server online. Fix duplicate world names after copying a world folder.",
"keywords": "pocketmine level.dat, pmmp nbt editor, pocketmine world name, nukkit level.dat editor, powernukkitx nbt, bedrock dedicated server level.dat, bds world name, pocketmine world editor",
"h1": "PocketMine-MP &amp; Bedrock Server level.dat Editor",
"crumb": "PocketMine-MP",
"reltitle": "PocketMine-MP editor",
"reldesc": "Server-side level.dat for PMMP, Nukkit and BDS.",
"og": "og/pocketmine.png",
"droplabel": "worlds/&lt;World&gt;/level.dat",
"chips": ["PocketMine-MP", "Nukkit", "PowerNukkitX", "Cloudburst", "Bedrock Dedicated Server", "Dragonfly", "Endstone", "WaterdogPE"],
"answer": "Bedrock server software — PocketMine-MP, Nukkit, PowerNukkitX, Cloudburst, Dragonfly and the official Bedrock Dedicated Server — all read the same little-endian <code>level.dat</code> with an 8-byte header from <code>worlds/&lt;World&gt;/</code>. Drop yours below to fix the world name after duplicating a folder, move spawn, flip game rules or check which build last wrote the world.",
"body": """
<section class="content" aria-label="Duplicate world names">
<h2>The duplicated-world-name problem</h2>
<p>Every Bedrock server admin hits this. You copy <code>worlds/hub</code> to <code>worlds/hub2</code> to make a second arena, and the console, the world manager and every plugin that reports a world name keep calling both of them <em>hub</em>. The folder name changed; <code>LevelName</code> inside <code>level.dat</code> did not.</p>
<p>The consequences are not cosmetic. Plugins that look worlds up by their internal name — teleport pads, per-world configs, region protection — can resolve to the wrong world, and world-management commands become ambiguous. Fix it by editing the tag: drop the file above and the editor jumps straight to <code>LevelName</code> and opens it for editing.</p>
<div class="card">
<ol class="steps">
<li>Stop the server. A running server rewrites <code>level.dat</code> on save and will undo the edit.</li>
<li>Download <code>worlds/&lt;World&gt;/level.dat</code> over SFTP or from your panel's file manager.</li>
<li>Drop it into the editor, change <code>LevelName</code> to the new name, save.</li>
<li>Upload it back over the original, keeping the old file as a backup.</li>
<li>Start the server and check the console line that reports loaded worlds.</li>
</ol>
</div>
</section>

<section class="content" aria-label="Core specifics">
<h2>Core-by-core notes</h2>
<div class="table-wrap">
<table class="matrix">
<thead><tr><th>Core</th><th>World path</th><th>Notes</th></tr></thead>
<tbody>
<tr><td>PocketMine-MP (PM5)</td><td><code>worlds/&lt;World&gt;/</code></td><td>Default world set by <code>level-name</code> in <code>server.properties</code>; that value is the folder, while <code>LevelName</code> is what the world calls itself.</td></tr>
<tr><td>Nukkit / PowerNukkitX</td><td><code>worlds/&lt;World&gt;/</code></td><td>Same Bedrock layout; PNX adds its own settings files alongside.</td></tr>
<tr><td>Bedrock Dedicated Server</td><td><code>worlds/&lt;World&gt;/</code></td><td><code>level-name</code> in <code>server.properties</code> picks the folder; the header storage version is typically 10.</td></tr>
<tr><td>Cloudburst / Dragonfly</td><td><code>worlds/&lt;World&gt;/</code></td><td>Read the same <code>level.dat</code>; Dragonfly may keep extra state in its own database.</td></tr>
<tr><td>WaterdogPE, Geyser</td><td>—</td><td>Proxies. They do not own worlds; NBT only passes through them on the wire as network NBT.</td></tr>
</tbody>
</table>
</div>
</section>

<section class="content" aria-label="Server workflow">
<h2>Doing it without breaking production</h2>
<div class="card">
<ul>
<li><strong>Back up the whole world folder,</strong> not just <code>level.dat</code>. It costs seconds and it is the only thing that makes a bad edit reversible.</li>
<li><strong>Never edit a live file over SFTP.</strong> Download, edit, upload while the server is stopped. Editing in place while the server holds the world open is how you end up with a truncated file.</li>
<li><strong>Copying a world for a new mode?</strong> Change <code>LevelName</code> immediately after copying, before the server sees it, so nothing ever caches the wrong name.</li>
<li><strong>Check the file bar after loading.</strong> It shows the detected format and the storage version — if a Bedrock file is reported as anything but <em>Bedrock level.dat</em>, you grabbed the wrong file or it is corrupt.</li>
</ul>
</div>
</section>
""",
"faq": [
("Does PocketMine-MP use the same level.dat as Bedrock?", "<p>Yes. PocketMine-MP implements the Bedrock world format, so its <code>level.dat</code> is little-endian NBT with the 8-byte header, byte-for-byte the same shape the vanilla Bedrock server writes.</p>"),
("Why do two worlds show the same name in console?", "<p>Because both were copied from one folder and share a <code>LevelName</code>. The folder name and the tag are independent; change the tag.</p>"),
("Can I rename a world without restarting the server?", "<p>No. The world is loaded in memory and rewritten on save, so an edit made while it is running is discarded. Stop, edit, start.</p>"),
("Does this work with Nukkit and PowerNukkitX?", "<p>Yes — same format, same file path, same procedure.</p>"),
("How do I convert a Bedrock world to Java?", "<p>Not with an NBT editor. Byte order is the easy part; the tag layout, block palettes and chunk storage differ completely. Use a purpose-built converter, then use this editor for the leftover metadata.</p>"),
],
"related": ["mcpe-nbt-editor", "level-dat-editor", "guides/change-world-name", "", "mcstructure-editor", "guides/edit-gamerules"],
},

]

PAGES += [

{
"slug": "mcstructure-editor",
"title": ".mcstructure Editor Online — Bedrock Structure Files",
"ogtitle": ".mcstructure editor — open and edit Bedrock structures",
"desc": "Open and edit Bedrock .mcstructure files online: block palette, size, block indices and block entity data, saved back in the same encoding.",
"keywords": "mcstructure editor, mcstructure viewer, edit mcstructure, open mcstructure file, bedrock structure block file, mcstructure online, minecraft bedrock structure editor",
"h1": ".mcstructure Editor — Bedrock Structure Files",
"crumb": ".mcstructure",
"reltitle": ".mcstructure editor",
"reldesc": "Bedrock structure blocks: palette, size, block entities.",
"og": "og/mcstructure.png",
"droplabel": "a .mcstructure file",
"chips": ["Structure blocks", "Bedrock add-ons", "Behavior packs", "Little-endian NBT"],
"answer": "A <code>.mcstructure</code> file is uncompressed little-endian NBT written by a Bedrock structure block. Drop one below to read its size, block palette, block indices and block entity data, edit any of it, and download the file back in the same encoding — which is what add-on and map makers need when a structure has to be patched without reopening the world.",
"body": """
<section class="content" aria-label="Inside a mcstructure file">
<h2>What is inside a <code>.mcstructure</code></h2>
<div class="table-wrap">
<table class="matrix">
<thead><tr><th>Tag</th><th>Type</th><th>What it holds</th></tr></thead>
<tbody>
<tr><td><code>format_version</code></td><td>Int</td><td>Structure format revision, 1 in current files</td></tr>
<tr><td><code>size</code></td><td>List of Int</td><td>X, Y, Z dimensions of the captured volume</td></tr>
<tr><td><code>structure_world_origin</code></td><td>List of Int</td><td>Where the structure was captured in the world</td></tr>
<tr><td><code>structure</code></td><td>Compound</td><td>Everything below lives here</td></tr>
<tr><td><code>structure.block_indices</code></td><td>List of Int[]</td><td>Two layers of palette indices — normally blocks and waterlogging; <code>-1</code> means "leave whatever is there"</td></tr>
<tr><td><code>structure.entities</code></td><td>List of Compound</td><td>Entities captured with the structure</td></tr>
<tr><td><code>structure.palette.default.block_palette</code></td><td>List of Compound</td><td>Every distinct block state: <code>name</code>, <code>states</code>, <code>version</code></td></tr>
<tr><td><code>structure.palette.default.block_position_data</code></td><td>Compound</td><td>Block entity NBT keyed by the flat index of the position</td></tr>
</tbody>
</table>
</div>
<p>Indices in <code>block_indices</code> run X, then Z, then Y — a flat index of <code>(x * sizeZ + z) * sizeY + y</code> into the palette list. That mapping is what lets you fix a single mis-set block without regenerating the structure.</p>
</section>

<section class="content" aria-label="Typical edits">
<h2>What people change here</h2>
<ul>
<li><strong>Swap a block type everywhere</strong> by editing one entry in <code>block_palette</code> — every position pointing at that index changes with it.</li>
<li><strong>Fix a block state</strong> such as a wrong <code>facing</code> or an accidental <code>waterlogged</code> in the <code>states</code> compound.</li>
<li><strong>Strip entities</strong> that were caught by accident, by removing entries from the <code>entities</code> list.</li>
<li><strong>Repair block entity data</strong> — chest contents, sign text, spawner settings — inside <code>block_position_data</code>.</li>
<li><strong>Check the version stamp</strong> on palette entries when a structure imports with the wrong blocks after a game update.</li>
</ul>
</section>

<section class="content" aria-label="Where mcstructure files live">
<h2>Where the files are</h2>
<p>Structure blocks save into the world's <code>structures/</code> folder inside the world directory, in files named <code>&lt;namespace&gt;_&lt;name&gt;.mcstructure</code>. Behaviour packs ship them under <code>structures/</code> in the pack, where the game loads them by namespace. Both are the same format and both open here.</p>
<p>Java Edition's equivalent is the gzip big-endian <code>.nbt</code> structure file — a different encoding with a different tag layout. The <a href="../java-nbt-editor/">Java editor page</a> covers those, and this editor opens them too.</p>
</section>
""",
"faq": [
("Can I convert a .mcstructure to a Java .nbt structure?", "<p>The editor can re-encode the bytes to big-endian gzip, but the tag layout differs — Java structures use <code>palette</code>/<code>blocks</code> with different keys and block names. A re-encoded file is readable, not a valid Java structure.</p>"),
("Why is my .mcstructure not compressed?", "<p>Bedrock writes structure files as raw little-endian NBT with no gzip wrapper. That is normal; the editor detects it as <em>Bedrock raw</em>.</p>"),
("What does an index of -1 mean in block_indices?", "<p>It marks a position the structure does not touch, so the existing block in the world is kept when the structure is placed.</p>"),
("Can I resize a structure by editing size?", "<p>Not on its own — <code>block_indices</code> has one entry per position, so the array length has to match the new volume exactly. Changing <code>size</code> alone produces a file the game refuses.</p>"),
],
"related": ["mcpe-nbt-editor", "schematic-editor", "", "nbt-format", "pocketmine-nbt-editor", "nbt-viewer"],
},

{
"slug": "schematic-editor",
"title": ".schem &amp; .schematic Editor Online — WorldEdit, MCEdit",
"ogtitle": ".schem / .schematic editor — WorldEdit and MCEdit files",
"desc": "Open WorldEdit .schem and MCEdit .schematic files online. Read the palette, size, offsets and block entities, edit tags and download the schematic.",
"keywords": "schematic editor, schem editor, worldedit schematic editor, open .schem file, mcedit schematic viewer, sponge schematic format, minecraft schematic nbt, schematic viewer online",
"h1": "Schematic Editor — .schem and .schematic Online",
"crumb": ".schem",
"reltitle": "Schematic editor",
"reldesc": "WorldEdit .schem and legacy MCEdit .schematic.",
"og": "og/schematic.png",
"droplabel": "a .schem or .schematic file",
"chips": ["WorldEdit", "FastAsyncWorldEdit", "Sponge Schematic v2/v3", "MCEdit legacy", "Litematica adjacent"],
"answer": "Schematics are gzip-compressed big-endian NBT. Drop a modern WorldEdit <code>.schem</code> (Sponge Schematic format) or a legacy MCEdit <code>.schematic</code> below to inspect the palette, dimensions, offsets, block entity list and metadata, edit any tag and download the file back ready for <code>//paste</code>.",
"body": """
<section class="content" aria-label="Schematic formats">
<h2>Two formats, one file extension family</h2>
<div class="table-wrap">
<table class="matrix">
<thead><tr><th>Format</th><th>Extension</th><th>Key tags</th></tr></thead>
<tbody>
<tr><td>Sponge Schematic v2 (WorldEdit 7)</td><td><code>.schem</code></td><td><code>Version</code>, <code>DataVersion</code>, <code>Width</code>, <code>Height</code>, <code>Length</code>, <code>Palette</code>, <code>BlockData</code>, <code>BlockEntities</code>, <code>Offset</code>, <code>Metadata</code></td></tr>
<tr><td>Sponge Schematic v3</td><td><code>.schem</code></td><td>Same data nested under a <code>Schematic</code> compound, with <code>Blocks</code> holding <code>Palette</code> and <code>Data</code></td></tr>
<tr><td>MCEdit legacy</td><td><code>.schematic</code></td><td><code>Width</code>, <code>Height</code>, <code>Length</code>, <code>Blocks</code>, <code>Data</code>, <code>Entities</code>, <code>TileEntities</code>, <code>Materials</code></td></tr>
</tbody>
</table>
</div>
<p><code>BlockData</code> in the Sponge formats is a byte array of varint palette indices, not one byte per block — long ids continue across several bytes. The legacy format instead stores raw numeric block ids in <code>Blocks</code> with a parallel <code>Data</code> array of metadata nibbles, which is why old schematics lose fidelity on modern versions.</p>
</section>

<section class="content" aria-label="Editing schematics">
<h2>What is worth editing by hand</h2>
<ul>
<li><strong>Palette entries.</strong> Rewriting <code>minecraft:oak_planks</code> to <code>minecraft:spruce_planks</code> in <code>Palette</code> re-skins every matching block in the schematic at once.</li>
<li><strong>Offset and origin.</strong> <code>Offset</code> decides where the paste lands relative to your position — the fastest fix for a build that always arrives three blocks off.</li>
<li><strong>Block entities.</strong> Chest inventories, sign lines and spawner data live in <code>BlockEntities</code> and can be cleaned before sharing a build.</li>
<li><strong>Metadata.</strong> <code>Metadata</code> carries the author and the WorldEdit origin; harmless to edit and often worth clearing before publishing.</li>
<li><strong>DataVersion.</strong> Tells you which Minecraft version produced the schematic, which explains most "unknown block" errors on paste.</li>
</ul>
</section>

<section class="content" aria-label="Compatibility">
<h2>Loader compatibility</h2>
<p>WorldEdit and FastAsyncWorldEdit read <code>.schem</code> from <code>plugins/WorldEdit/schematics/</code>; legacy <code>.schematic</code> files still load but are converted on the way in. Litematica uses its own <code>.litematic</code> container — also NBT, and it opens in this editor, though its layout differs from the Sponge one. Whatever the flavour, the editor reads it as NBT and writes it back gzip-compressed, so the loader sees the file it expects.</p>
</section>
""",
"faq": [
("Can I open a .schem without a server or WorldEdit?", "<p>Yes. A <code>.schem</code> is just gzip big-endian NBT; the editor opens it in the browser with nothing else installed.</p>"),
("Why does my schematic paste with wrong blocks?", "<p>Usually a version mismatch — check <code>DataVersion</code> and the palette. A schematic exported on a newer version can reference block states an older server does not know.</p>"),
("Can I change a schematic's size here?", "<p>Not by editing <code>Width</code>/<code>Height</code>/<code>Length</code> alone. <code>BlockData</code> is sized to the volume, so the dimensions and the data have to change together — that is a job for WorldEdit, not a tag editor.</p>"),
("Does it open .litematic files?", "<p>Yes, as NBT. Litematica's own tag layout is not the Sponge one, so what you see is its native structure rather than a schematic palette.</p>"),
],
"related": ["java-nbt-editor", "mcstructure-editor", "", "nbt-format", "nbt-viewer", "level-dat-editor"],
},

{
"slug": "playerdata-editor",
"title": "Minecraft playerdata Editor — Edit player .dat Files Online",
"ogtitle": "playerdata editor — inventory, position, stats",
"desc": "Edit Minecraft playerdata .dat files online: fix a stuck player position, drop a corrupted inventory item, adjust health, XP or game mode.",
"keywords": "playerdata editor, minecraft player.dat editor, edit player inventory nbt, player data nbt editor, uuid.dat minecraft, stuck player position fix, minecraft inventory editor online",
"h1": "playerdata Editor — Minecraft Player .dat Files",
"crumb": "playerdata",
"reltitle": "playerdata editor",
"reldesc": "Inventory, position, health and stats per player.",
"og": "og/playerdata.png",
"droplabel": "a playerdata .dat file",
"chips": ["Java playerdata", "Ender chest", "Inventory", "Position", "Attributes", "Advancement-adjacent"],
"answer": "Java Edition writes one gzip big-endian NBT file per player in <code>world/playerdata/&lt;uuid&gt;.dat</code>, holding inventory, ender chest, position, dimension, health, hunger, XP and attributes. Drop one below to fix a player stuck inside terrain, drop a crash-inducing item, or reset stats — with the server stopped, or at least with that player offline.",
"body": """
<section class="content" aria-label="playerdata tags">
<h2>The tags in a player file</h2>
<div class="table-wrap">
<table class="matrix">
<thead><tr><th>Tag</th><th>Type</th><th>What it is</th></tr></thead>
<tbody>
<tr><td><code>Pos</code></td><td>List of Double</td><td>X, Y, Z. The fix for a player stuck in a wall or below bedrock.</td></tr>
<tr><td><code>Rotation</code></td><td>List of Float</td><td>Yaw and pitch.</td></tr>
<tr><td><code>Dimension</code></td><td>String / Int</td><td>Which dimension the player logs into.</td></tr>
<tr><td><code>Inventory</code></td><td>List of Compound</td><td>One entry per stack: <code>id</code>, <code>Count</code>, <code>Slot</code>, <code>components</code> or <code>tag</code>.</td></tr>
<tr><td><code>EnderItems</code></td><td>List of Compound</td><td>Ender chest contents, same shape.</td></tr>
<tr><td><code>Health</code>, <code>foodLevel</code>, <code>XpLevel</code>, <code>XpTotal</code></td><td>Float / Int</td><td>Vitals and experience.</td></tr>
<tr><td><code>playerGameType</code></td><td>Int</td><td>Per-player game mode.</td></tr>
<tr><td><code>abilities</code></td><td>Compound</td><td>Flying, invulnerable, walk and fly speed.</td></tr>
<tr><td><code>Attributes</code></td><td>List of Compound</td><td>Max health, movement speed and other modifiers.</td></tr>
<tr><td><code>SpawnX</code>/<code>SpawnY</code>/<code>SpawnZ</code> or <code>respawn</code></td><td>Int / Compound</td><td>Personal respawn point, depending on version.</td></tr>
<tr><td><code>UUID</code></td><td>Int[4]</td><td>The player's UUID as four ints in modern versions.</td></tr>
</tbody>
</table>
</div>
<p>Item stacks changed shape in 1.20.5: custom data moved from a single <code>tag</code> compound to individual <code>components</code>. Both shapes open here; edit whichever your version writes.</p>
</section>

<section class="content" aria-label="Common repairs">
<h2>Common repairs</h2>
<div class="card">
<ul>
<li><strong>Player stuck in terrain or falling forever.</strong> Set <code>Pos</code> to safe coordinates — three doubles, in order X, Y, Z — and clear <code>Motion</code> if it holds a huge value.</li>
<li><strong>Client crashes on login.</strong> A malformed item is the usual cause. Remove the offending entry from <code>Inventory</code> rather than wiping the whole list.</li>
<li><strong>Wrong dimension after a portal bug.</strong> Set <code>Dimension</code> back to <code>minecraft:overworld</code> and give <code>Pos</code> matching coordinates.</li>
<li><strong>Stuck in spectator.</strong> Set <code>playerGameType</code> to 0 for survival, 1 for creative.</li>
<li><strong>Attribute modifiers left by a removed plugin.</strong> Delete the stale entries in <code>Attributes</code>.</li>
</ul>
</div>
</section>

<section class="content" aria-label="Server safety">
<h2>Do it with the player offline</h2>
<p>The server holds player state in memory and writes it out on logout and on autosave. Editing the file while that player is online guarantees your changes are overwritten, and editing during a save can truncate the file. Take the player offline — or stop the server — copy the file, edit, and put it back before they reconnect. Keep the original until the login works.</p>
<p>Bedrock servers do not use this layout: player data lives in the world's LevelDB under keys such as <code>player_&lt;uuid&gt;</code>, whose values are little-endian NBT. Extract a value and it opens here as <em>Bedrock raw</em>.</p>
</section>
""",
"faq": [
("Which file is my player?", "<p>Files are named by UUID. Look the player's UUID up on a Mojang API viewer, or sort <code>playerdata/</code> by modification time and match against the last login.</p>"),
("Can I give myself items by editing playerdata?", "<p>On your own server, yes — add an entry to the <code>Inventory</code> list with <code>id</code>, <code>Count</code> and <code>Slot</code>. On someone else's server that is an intrusion, and it will not work anyway because the live server rewrites the file.</p>"),
("Why did my edit disappear?", "<p>The server or the player was online when you edited. Player state in memory wins on the next save.</p>"),
("Is playerdata the same in Bedrock?", "<p>No. Bedrock keeps players inside the world LevelDB rather than in per-UUID files. The NBT inside those values is little-endian and opens here once extracted.</p>"),
],
"related": ["java-nbt-editor", "", "level-dat-editor", "nbt-format", "nbt-viewer", "guides/fix-corrupted-level-dat"],
},

{
"slug": "nbt-viewer",
"title": "NBT Viewer Online — Open and Read .nbt and .dat Files",
"ogtitle": "NBT viewer — open any .nbt or .dat file in the browser",
"desc": "Open and read any Minecraft NBT file online. View the full tag tree of .nbt, .dat, .mcstructure or .schem, search it and export it as SNBT text.",
"keywords": "nbt viewer, nbt viewer online, open nbt file, read .dat file minecraft, nbt file reader, view nbt online, minecraft dat file viewer, nbt to json, snbt export",
"h1": "NBT Viewer — Open Any Minecraft NBT File",
"crumb": "NBT viewer",
"reltitle": "NBT viewer",
"reldesc": "Read-only inspection, search and SNBT export.",
"og": "og/viewer.png",
"droplabel": "any .nbt or .dat file",
"chips": [".nbt", ".dat", ".mcstructure", ".schem", ".schematic", "SNBT export", "Search"],
"answer": "Need to look inside a Minecraft file rather than change it? Drop any <code>.nbt</code>, <code>.dat</code>, <code>.mcstructure</code>, <code>.schem</code> or raw NBT dump below to see its full tag tree with types and values, search it by name or value, and export the whole thing as SNBT text. Nothing is uploaded and nothing is written unless you click save.",
"body": """
<section class="content" aria-label="What you can inspect">
<h2>Reading a file you did not write</h2>
<p>Half the reason to open an NBT file is diagnosis: what version wrote this, why does this world refuse to load, what is actually inside the schematic somebody sent you. The viewer shows every tag with its exact type, so you can tell a <code>TAG_Byte</code> of 1 from a <code>TAG_Int</code> of 1 — a distinction that matters to Minecraft and that text dumps usually lose.</p>
<ul>
<li><strong>Type badges on every row</strong> — Byte, Short, Int, Long, Float, Double, Byte[], String, List, Compound, Int[], Long[].</li>
<li><strong>Full 64-bit longs</strong> shown exactly, so seeds and UUID halves read correctly instead of being rounded.</li>
<li><strong>Search</strong> across the whole tree by tag name or value, with a jump straight to the match.</li>
<li><strong>Detected format</strong> shown in the file bar: edition, byte order, compression and Bedrock storage version.</li>
<li><strong>SNBT export</strong> to get the whole document as text you can diff, paste into a command or hand to another tool.</li>
</ul>
</section>

<section class="content" aria-label="SNBT">
<h2>NBT versus SNBT</h2>
<p>SNBT is the text form of NBT — what <code>/data get</code> prints and what commands accept. It keeps type information as suffixes: <code>3b</code> is a byte, <code>3s</code> a short, <code>3L</code> a long, <code>3.0f</code> a float, <code>3.0d</code> a double, <code>[I;1,2,3]</code> an int array. The export button produces exactly that, so a binary file becomes something you can paste into a command block or check into git and diff line by line.</p>
<p>JSON is not a substitute: it has one number type and no byte arrays, so converting NBT to JSON silently loses the distinctions Minecraft cares about. That is why this tool exports SNBT rather than JSON.</p>
</section>

<section class="content" aria-label="File types">
<h2>Files that open here</h2>
<p>Anything whose payload is a single NBT document: Java and Bedrock <a href="../level-dat-editor/">level.dat</a>, <a href="../playerdata-editor/">playerdata</a>, <code>servers.dat</code>, <code>hotbar.nbt</code>, <code>idcounts.dat</code>, <code>raids.dat</code>, <code>scoreboard.dat</code>, map data, structure <code>.nbt</code>, <a href="../schematic-editor/">.schem and .schematic</a>, <a href="../mcstructure-editor/">.mcstructure</a>, <code>.litematic</code>, extracted chunk payloads and packet dumps. Containers such as <code>.mca</code> regions, <code>.mcworld</code> archives and LevelDB folders need one document extracted from them first.</p>
</section>
""",
"faq": [
("Can I view an NBT file without editing it?", "<p>Yes. The editor only writes a file when you click Save &amp; Download, and it never touches the file you dropped in.</p>"),
("Can it convert NBT to JSON?", "<p>It exports SNBT, which preserves tag types. JSON would flatten bytes, shorts, ints, longs and floats into one number type and lose byte arrays, so it is the wrong target for round-tripping Minecraft data.</p>"),
("Why does my file show as a different edition than I expected?", "<p>The format is detected from the bytes, not the extension. A file reported as Java when you expected Bedrock is usually a file from the other edition, or a fragment that happens to parse — check the offsets reported if it warns about trailing bytes.</p>"),
("How big a file can it open?", "<p>Multi-megabyte documents are fine: arrays are kept in typed arrays and the tree renders lazily, so only the rows you expand exist in the page.</p>"),
],
"related": ["", "nbtexplorer-online", "nbt-format", "schematic-editor", "mcstructure-editor", "playerdata-editor"],
},

]

PAGES += [

{
"slug": "nbtexplorer-online",
"title": "NBTExplorer Online — Browser Alternative, No Download",
"ogtitle": "NBTExplorer online — the browser alternative",
"desc": "A browser alternative to NBTExplorer: the same tag tree editing for Minecraft files, plus Bedrock little-endian support, with nothing to install.",
"keywords": "nbtexplorer online, nbtexplorer alternative, nbt editor no download, nbtexplorer mac, nbtexplorer bedrock, online nbt explorer, nbtexplorer web, nbt editor without java",
"h1": "NBTExplorer Online — Browser Alternative",
"crumb": "NBTExplorer online",
"reltitle": "NBTExplorer online",
"reldesc": "What carries over from the desktop tool, and what does not.",
"og": "og/nbtexplorer.png",
"droplabel": "any NBT file",
"chips": ["No install", "Windows", "macOS", "Linux", "Android", "ChromeOS"],
"answer": "NBTExplorer is the desktop tag editor most Minecraft players know, and it needs .NET or Mono, a download and a desktop. This page does the same job — tag tree, inline editing, add and remove tags — in the browser, on any operating system including phones, and it also reads Bedrock little-endian files, which NBTExplorer does not.",
"body": """
<section class="content" aria-label="Comparison">
<h2>How it compares</h2>
<div class="table-wrap">
<table class="matrix">
<thead><tr><th>Capability</th><th>NBTExplorer (desktop)</th><th>This editor (browser)</th></tr></thead>
<tbody>
<tr><td>Install required</td><td>Yes — .NET / Mono runtime</td><td>No</td></tr>
<tr><td>Java big-endian NBT</td><td>Yes</td><td>Yes</td></tr>
<tr><td>gzip / zlib</td><td>Yes</td><td>Yes, via the browser's native compression streams</td></tr>
<tr><td>Bedrock little-endian NBT</td><td>No</td><td>Yes, including the 8-byte <code>level.dat</code> header</td></tr>
<tr><td>Bedrock network / varint NBT</td><td>No</td><td>Yes</td></tr>
<tr><td>Browse <code>.mca</code> regions and folders</td><td>Yes — its main advantage</td><td>No, one document at a time</td></tr>
<tr><td>Bedrock LevelDB browsing</td><td>No</td><td>No, extract the value first</td></tr>
<tr><td>Search across the tree</td><td>Yes</td><td>Yes</td></tr>
<tr><td>SNBT export</td><td>No</td><td>Yes</td></tr>
<tr><td>Runs on a phone</td><td>No</td><td>Yes</td></tr>
<tr><td>Sends your file anywhere</td><td>No</td><td>No</td></tr>
</tbody>
</table>
</div>
<p>The honest summary: if you need to walk a whole region folder and open chunks by coordinate, the desktop tool still wins. If you need to open one file — a <code>level.dat</code>, a player file, a schematic, a Bedrock world — on whatever machine you happen to be at, this is faster and covers editions the desktop tool never learned.</p>
</section>

<section class="content" aria-label="Migrating">
<h2>Coming from the desktop tool</h2>
<ul>
<li><strong>The tree works the same way.</strong> Expand compounds and lists, click a value to edit it, use + and × for structure.</li>
<li><strong>Types are enforced the same way.</strong> A byte stays a byte; out-of-range values are rejected instead of being silently truncated.</li>
<li><strong>Saving is a download,</strong> not an in-place write. The file you dropped in is never modified, so your backup is automatic.</li>
<li><strong>Compression is round-tripped.</strong> A gzip file goes back out gzip, so the game accepts it without a manual recompress step.</li>
<li><strong>Bedrock just works.</strong> No separate tool, no hex editor to fix the header length after an edit.</li>
</ul>
</section>

<section class="content" aria-label="Other tools">
<h2>Where other tools still fit</h2>
<p>Use <strong>NBTExplorer</strong> or <strong>NBTStudio</strong> for bulk region browsing. Use <strong>Amulet</strong> or <strong>MCA Selector</strong> for chunk-level surgery and world trimming. Use <strong>WorldEdit</strong> for anything geometric. Use this page when the job is "open this one file, change these tags, give it back" — which is most of the time — or when the file is Bedrock and the desktop tools refuse it.</p>
</section>
""",
"faq": [
("Is there an official NBTExplorer web version?", "<p>No. NBTExplorer is a desktop application; this is an independent editor that covers the same everyday tasks in the browser and adds Bedrock support.</p>"),
("Does it work on macOS and Linux without Mono?", "<p>Yes — it is a web page. Any current browser on macOS, Linux, Windows, Android or ChromeOS runs it.</p>"),
("Can it open a whole region file like NBTExplorer does?", "<p>No. It edits a single NBT document at a time. Extract a chunk from the <code>.mca</code> first, then drop the payload here.</p>"),
("Is it safe to use for my only save?", "<p>It never writes to the file you open — edits come back as a new download — but keep your own backup anyway, as with any editor.</p>"),
],
"related": ["", "nbt-viewer", "java-nbt-editor", "mcpe-nbt-editor", "nbt-format", "level-dat-editor"],
},

{
"slug": "nbt-format",
"title": "NBT Format Reference — Tag Types, Encodings, Byte Layout",
"ogtitle": "NBT format reference — tags, encodings, byte layout",
"desc": "Reference for Minecraft's NBT format: all 13 tag types with byte layout, Java big-endian vs Bedrock little-endian vs varint network NBT, and SNBT.",
"keywords": "nbt format, nbt file format, minecraft nbt specification, nbt tag types, tag_compound, little-endian nbt, varint nbt, network nbt, snbt syntax, nbt byte layout",
"h1": "NBT Format Reference",
"crumb": "NBT format",
"reltitle": "NBT format reference",
"reldesc": "All 13 tag types, every encoding, byte by byte.",
"og": "og/format.png",
"droplabel": "any NBT file to inspect",
"chips": ["13 tag types", "Big-endian", "Little-endian", "Varint", "gzip", "zlib", "SNBT"],
"answer": "NBT (Named Binary Tag) is Minecraft's binary tree format: a tag is a one-byte type, a length-prefixed name and a payload, and compounds nest until a <code>TAG_End</code> byte closes them. There are 13 tag types and five encodings in circulation across Java and Bedrock. This page documents all of them, and the editor above lets you check any claim against a real file.",
"body": """
<section class="content" aria-label="Tag types">
<h2>The 13 tag types</h2>
<div class="table-wrap">
<table class="matrix">
<thead><tr><th>Id</th><th>Tag</th><th>Payload</th><th>SNBT</th></tr></thead>
<tbody>
<tr><td>0</td><td><code>TAG_End</code></td><td>None — closes a compound</td><td>—</td></tr>
<tr><td>1</td><td><code>TAG_Byte</code></td><td>1 byte, signed −128…127</td><td><code>1b</code></td></tr>
<tr><td>2</td><td><code>TAG_Short</code></td><td>2 bytes, signed</td><td><code>1s</code></td></tr>
<tr><td>3</td><td><code>TAG_Int</code></td><td>4 bytes, signed</td><td><code>1</code></td></tr>
<tr><td>4</td><td><code>TAG_Long</code></td><td>8 bytes, signed</td><td><code>1L</code></td></tr>
<tr><td>5</td><td><code>TAG_Float</code></td><td>4 bytes, IEEE 754</td><td><code>1.0f</code></td></tr>
<tr><td>6</td><td><code>TAG_Double</code></td><td>8 bytes, IEEE 754</td><td><code>1.0d</code></td></tr>
<tr><td>7</td><td><code>TAG_Byte_Array</code></td><td>int length, then that many bytes</td><td><code>[B;1b,2b]</code></td></tr>
<tr><td>8</td><td><code>TAG_String</code></td><td>unsigned short length, then UTF-8 bytes</td><td><code>"text"</code></td></tr>
<tr><td>9</td><td><code>TAG_List</code></td><td>element type byte, int length, then payloads with no names</td><td><code>[1,2]</code></td></tr>
<tr><td>10</td><td><code>TAG_Compound</code></td><td>type + name + payload repeated until <code>TAG_End</code></td><td><code>{a:1}</code></td></tr>
<tr><td>11</td><td><code>TAG_Int_Array</code></td><td>int length, then that many 4-byte ints</td><td><code>[I;1,2]</code></td></tr>
<tr><td>12</td><td><code>TAG_Long_Array</code></td><td>int length, then that many 8-byte longs</td><td><code>[L;1L,2L]</code></td></tr>
</tbody>
</table>
</div>
<p>A file is a single root <code>TAG_Compound</code>: one type byte <code>0x0A</code>, a name, then the compound's contents. Named tags appear only inside compounds — list elements carry payloads only, which is why a list is homogeneous.</p>
</section>

<section class="content" aria-label="Encodings">
<h2>Five encodings in the wild</h2>
<div class="table-wrap">
<table class="matrix">
<thead><tr><th>Encoding</th><th>Integers</th><th>String length</th><th>Root</th><th>Used by</th></tr></thead>
<tbody>
<tr><td>Java (classic)</td><td>Big-endian fixed width</td><td>2-byte big-endian</td><td>Named</td><td>Java worlds, structures, schematics</td></tr>
<tr><td>Java network (1.20.2+)</td><td>Big-endian fixed width</td><td>2-byte big-endian</td><td>Nameless</td><td>Java protocol</td></tr>
<tr><td>Bedrock</td><td>Little-endian fixed width</td><td>2-byte little-endian</td><td>Named</td><td>Bedrock worlds, <code>.mcstructure</code>, LevelDB values</td></tr>
<tr><td>Bedrock <code>level.dat</code></td><td>Little-endian fixed width</td><td>2-byte little-endian</td><td>Named, after an 8-byte header</td><td>Bedrock world metadata</td></tr>
<tr><td>Bedrock network</td><td>Zigzag varint for int and long</td><td>Unsigned varint</td><td>Named</td><td>Bedrock protocol</td></tr>
</tbody>
</table>
</div>
<p>In the varint encoding, <code>TAG_Short</code>, <code>TAG_Float</code> and <code>TAG_Double</code> stay fixed-width little-endian; only <code>TAG_Int</code> and <code>TAG_Long</code> become zigzag varints, and array and list lengths follow whatever <code>TAG_Int</code> does. String lengths are unsigned varints, which also lifts the 65535-byte ceiling that the fixed encodings impose.</p>
</section>

<section class="content" aria-label="Strings">
<h2>Strings: modified UTF-8 versus UTF-8</h2>
<p>Java serialises strings with <code>DataOutputStream.writeUTF</code>, which is <em>modified</em> UTF-8: a NUL character is written as <code>C0 80</code> rather than <code>00</code>, and characters outside the Basic Multilingual Plane are written as two three-byte surrogate halves (CESU-8) instead of one four-byte sequence. Bedrock uses standard UTF-8. A tool that assumes one encoding for both will corrupt emoji and some CJK text on save — this editor encodes per format, which is why a world named with an emoji survives a round trip here.</p>
</section>

<section class="content" aria-label="Compression">
<h2>Compression</h2>
<p>NBT itself is not compressed; the container decides. Java files are usually gzip (magic <code>1F 8B</code>), chunk payloads inside region files are zlib (magic <code>78 01</code>, <code>78 9C</code> or <code>78 DA</code>), and Bedrock stores <code>level.dat</code> and structure files uncompressed. Detection is by magic bytes, so the same parser handles all three — and a file saved with the wrong compression is the single most common reason a hand-edited world will not load.</p>
</section>

<section class="content" aria-label="Byte walkthrough">
<h2>A minimal file, byte by byte</h2>
<p>The canonical <code>hello_world.nbt</code>: a root compound named <code>hello world</code> holding one string tag <code>name</code> with the value <code>Bananrama</code>. In Java's big-endian encoding:</p>
<pre class="code"><code>0A                          TAG_Compound
00 0B 68 65 6C 6C 6F 20 77 6F 72 6C 64   name length 11, "hello world"
   08                       TAG_String
   00 04 6E 61 6D 65        name length 4, "name"
   00 09 42 61 6E 61 6E 72 61 6D 61      value length 9, "Bananrama"
00                          TAG_End</code></pre>
<p>The same document in Bedrock's little-endian encoding differs only in the byte order of the two length fields: <code>0B 00</code> instead of <code>00 0B</code>. In Bedrock network NBT the lengths become single varint bytes, <code>0B</code> and <code>04</code>, with no padding at all. Drop any of the three into the editor above and it will tell you which one it received.</p>
</section>

<section class="content" aria-label="SNBT">
<h2>SNBT</h2>
<p>SNBT is NBT written as text, and it is what commands consume: <code>/data merge entity @s {Invulnerable:1b}</code>. Type suffixes are what keep it lossless — <code>b</code> byte, <code>s</code> short, <code>L</code> long, <code>f</code> float, <code>d</code> double, none for int — and typed array literals are written <code>[B;…]</code>, <code>[I;…]</code>, <code>[L;…]</code>. The editor exports SNBT from any loaded file, which makes two versions of a world diffable in a normal text diff.</p>
</section>
""",
"faq": [
("Is there an official NBT specification?", "<p>No formal spec from Mojang. The format was documented by Notch in 2010 and has been maintained by the community since; the tag ids and layout on this page match what the game reads and writes today.</p>"),
("Why does Bedrock use little-endian?", "<p>Bedrock's engine is C++ and targets little-endian hardware, so it stores values in native order. Java's serialisation is big-endian because that is what the Java DataOutput contract specifies.</p>"),
("What is zigzag varint encoding?", "<p>A way of writing integers in as few bytes as possible while keeping negatives short: the sign is folded into the low bit, so −1 encodes as 1 and 1 encodes as 2. Bedrock's protocol uses it for ints and longs.</p>"),
("Can a TAG_List hold mixed types?", "<p>No. A list declares one element type and every entry has to match it. Mixed data needs a list of compounds.</p>"),
("What is the maximum string length?", "<p>65535 bytes in the fixed encodings, because the length field is an unsigned short. The varint network encoding has no practical limit.</p>"),
],
"related": ["", "nbt-viewer", "java-nbt-editor", "mcpe-nbt-editor", "nbtexplorer-online", "schematic-editor"],
},

]

PAGES += [

{
"slug": "guides/change-world-name",
"title": "How to Change a Minecraft World Name (Java &amp; Bedrock)",
"ogtitle": "How to change a Minecraft world name",
"desc": "Rename a Minecraft world properly by editing LevelName in level.dat: Java and Bedrock, single player and servers, plus the duplicate-name fix.",
"keywords": "how to change minecraft world name, rename minecraft world, change world name server, levelname level.dat, rename bedrock world, minecraft world still shows old name, duplicate world name server",
"h1": "How to Change a Minecraft World Name",
"crumb": "Change world name",
"reltitle": "Rename a world",
"reldesc": "Fix LevelName after copying a world folder.",
"og": "og/rename.png",
"droplabel": "level.dat",
"chips": ["Java", "Bedrock", "Servers", "Single player", "2 minutes"],
"answer": "A world's display name lives in the <code>LevelName</code> tag inside <code>level.dat</code>, not in the folder name. Renaming the folder changes nothing the game shows, which is why a copied world keeps announcing itself under the original name. Drop <code>level.dat</code> into the editor below — it jumps straight to <code>LevelName</code> — change the value, save, and put the file back.",
"howto": {
  "name": "Change a Minecraft world name by editing level.dat",
  "time": "PT3M",
  "steps": [
    ("Stop the game or server", "Close the world or stop the server. Minecraft rewrites level.dat on autosave and shutdown, and a running instance will overwrite the edit."),
    ("Locate level.dat", "Java: world/level.dat on a server, or saves/<World>/level.dat in the client. Bedrock: worlds/<World>/level.dat on a server, or the world id folder under minecraftWorlds on a device."),
    ("Open it in the editor", "Drop the file into the NBT editor. It detects the edition and encoding and jumps to the LevelName tag automatically."),
    ("Edit LevelName", "Click the value, type the new name, press Enter. Keep it to plain characters if the name has to survive being printed in a console."),
    ("Save and download", "Click Save & Download. The output format and compression stay exactly as the file arrived, so nothing else about the file changes."),
    ("Replace the original", "Copy the downloaded file over the original, keeping a backup, then start the game or server and confirm the new name in the world list."),
  ],
},
"body": """
<section class="content" aria-label="Why the folder name is not the world name">
<h2>Why renaming the folder does nothing</h2>
<p>Minecraft treats the folder as an address and <code>LevelName</code> as the label. The world list, the server console, world-manager plugins and anything printing "world" to chat read the tag. So a folder copy — <code>cp -r worlds/hub worlds/hub2</code> — produces two worlds that insist they are both <em>hub</em>, and the only fix is inside the file.</p>
<p>On a server the duplicate is worse than confusing. Plugins that resolve worlds by internal name can act on the wrong one: teleport pads, per-world configs, protection regions, economy multipliers. Rename the tag the moment you copy a world, before anything caches it.</p>
</section>

<section class="content" aria-label="Per platform">
<h2>Per platform</h2>
<div class="card">
<h3>Java single player</h3>
<p>The client offers a rename in the world options screen and it edits <code>LevelName</code> for you. Editing the file by hand matters when the world will not load, when you are working on a copy, or when you want the folder and the label to differ deliberately.</p>
<h3>Java server</h3>
<p><code>level-name</code> in <code>server.properties</code> selects the <em>folder</em> to load. It does not rename anything. Change <code>LevelName</code> in <code>world/level.dat</code> for the label.</p>
<h3>Bedrock and MCPE</h3>
<p>The in-game world edit screen renames the world. When the world lives on a server, or you are patching an exported <code>.mcworld</code>, edit <code>LevelName</code> in <code>level.dat</code> directly — Bedrock stores it flat at the root, uncompressed, behind the 8-byte header the editor handles for you.</p>
<h3>Bedrock servers (PocketMine-MP, Nukkit, BDS)</h3>
<p>Same file, same tag, and the same warning about stopping the server first. The <a href="../../pocketmine-nbt-editor/">server page</a> has the full workflow including the folder-copy case.</p>
</div>
</section>

<section class="content" aria-label="Troubleshooting">
<h2>If the name does not change</h2>
<ul>
<li><strong>The server was running.</strong> Its in-memory copy was written back over your file on the next save. Stop it and redo the edit.</li>
<li><strong>You edited the wrong world.</strong> Bedrock world folders are random ids. Open the file and read <code>LevelName</code> to confirm you have the right one before editing.</li>
<li><strong>You edited <code>level.dat_old</code>.</strong> That is the previous save, not the live file.</li>
<li><strong>A launcher or panel caches the name.</strong> Some hosting panels show a name from their own database rather than the world file; the game itself will be correct.</li>
<li><strong>The world will not load at all now.</strong> Restore the backup and see <a href="../fix-corrupted-level-dat/">fixing a broken level.dat</a>.</li>
</ul>
</section>
""",
"faq": [
("Does renaming a world delete anything?", "<p>No. <code>LevelName</code> is a label. Terrain, players, inventories and entities live in other files and are untouched.</p>"),
("Can I use spaces, colours or emoji in a world name?", "<p>Spaces are fine. Section-sign colour codes work on some server software and show as literal characters elsewhere. Emoji survive the round trip here because the editor uses the right string encoding per edition, but consoles and log files may render them badly.</p>"),
("Do I have to rename the folder too?", "<p>No, and often you should not — a server's <code>level-name</code> setting or a plugin config may point at the folder path. Change one thing at a time.</p>"),
("Will players see the new name immediately?", "<p>After the world reloads, yes. Clients that cached a server list entry may need a refresh.</p>"),
],
"related": ["level-dat-editor", "pocketmine-nbt-editor", "mcpe-nbt-editor", "guides/fix-corrupted-level-dat", "", "guides/edit-gamerules"],
},

{
"slug": "guides/fix-corrupted-level-dat",
"title": "Fix a Corrupted level.dat — Minecraft World Will Not Load",
"ogtitle": "Fix a corrupted level.dat",
"desc": "Repair a Minecraft world that will not load: restore level.dat_old, inspect the file in an NBT editor, and find what actually broke it.",
"keywords": "corrupted level.dat, minecraft world will not load, failed to load level.dat, level.dat_old restore, minecraft world corrupted fix, repair minecraft world, level.dat error server",
"h1": "Fix a Corrupted <code>level.dat</code>",
"crumb": "Fix a broken level.dat",
"reltitle": "Fix a broken level.dat",
"reldesc": "Diagnose why a world refuses to load, and repair it.",
"og": "og/fix.png",
"droplabel": "level.dat or level.dat_old",
"chips": ["Diagnosis", "level.dat_old", "Header", "Compression", "Truncation"],
"answer": "A world that refuses to load usually has one of four problems: a truncated <code>level.dat</code> from a crash during save, the wrong compression after a hand edit, a broken Bedrock header length, or a tag whose type was changed. Drop the file below — the editor reports exactly where parsing stopped, which narrows it to one of the four in seconds.",
"howto": {
  "name": "Diagnose and repair a corrupted level.dat",
  "time": "PT10M",
  "steps": [
    ("Back up the world folder", "Copy the entire world directory before touching anything. Every step below is reversible only if you have this copy."),
    ("Try level.dat_old", "Minecraft keeps the previous save as level.dat_old. Open it in the NBT editor: if it parses cleanly, copy it over level.dat and start the world."),
    ("Open the broken file", "Drop level.dat into the editor. A clean parse means the file is intact and the problem lies elsewhere — chunks, mods or the server itself."),
    ("Read the error", "The editor names the failure: unexpected end of data means truncation, an implausible storage version means a damaged Bedrock header, and no recognizable format means the file is not NBT at all."),
    ("Check compression and format", "If it loads, look at the file bar. A Java level.dat must be saved as gzip big-endian; a Bedrock one as little-endian with the header. Re-saving with the correct settings fixes files broken by another tool."),
    ("Rebuild only what is missing", "If a single tag was deleted, add it back with the correct type. If the file is truncated, prefer level.dat_old or a backup — a partially parsed file is missing data no editor can invent."),
  ],
},
"body": """
<section class="content" aria-label="Causes">
<h2>What actually breaks</h2>
<div class="table-wrap">
<table class="matrix">
<thead><tr><th>Symptom</th><th>Cause</th><th>Fix</th></tr></thead>
<tbody>
<tr><td>Editor reports "Unexpected end of data"</td><td>Truncated file — the process died mid-save, or the disk filled up</td><td>Restore <code>level.dat_old</code> or a backup; the missing bytes are gone</td></tr>
<tr><td>Game says the world is corrupted, editor loads it fine</td><td>Wrong compression or byte order written by another tool</td><td>Re-save here with the correct format for the edition</td></tr>
<tr><td>Bedrock world missing from the list</td><td>Header length no longer matches the payload</td><td>Open and save here — the length is recalculated automatically</td></tr>
<tr><td>Server logs a class-cast or type error on load</td><td>A tag's type was changed by hand (Byte where an Int is expected)</td><td>Set the tag back to the type the game expects</td></tr>
<tr><td>World loads but spawns you in a fresh world</td><td><code>level.dat</code> was replaced by a newly generated one</td><td>Restore the backup; the chunks in <code>region/</code> or <code>db/</code> are usually still fine</td></tr>
<tr><td>Nothing parses, including <code>_old</code></td><td>Storage failure — the filesystem returned zeros or garbage for both</td><td>Restore from an off-machine backup; check the disk before trusting the host</td></tr>
</tbody>
</table>
</div>
</section>

<section class="content" aria-label="Salvage">
<h2>Salvaging a world without <code>level.dat</code></h2>
<p>The world's terrain, chests and players do not live in <code>level.dat</code> — they are in <code>region/</code> (Java) or <code>db/</code> (Bedrock). If the metadata file is beyond repair, create a fresh world with the same version and settings, then move the chunk data into it and set <code>LevelName</code>, spawn coordinates and game rules on the new file. You lose the metadata, not the builds. Confirm the version first: a Java world carries <code>DataVersion</code>, and the freshly generated file must not be older than the chunks you are importing.</p>
</section>

<section class="content" aria-label="Prevention">
<h2>Preventing the next one</h2>
<ul>
<li><strong>Stop the server before copying or editing.</strong> Most corruption starts as a file copied while it was being written.</li>
<li><strong>Snapshot on a schedule, off the machine.</strong> A backup on the same disk does not survive the storage failure that caused the problem.</li>
<li><strong>Use <code>save-off</code> / <code>save-all</code> around live snapshots</strong> so the copy is taken against a quiesced world.</li>
<li><strong>Watch disk space.</strong> A full disk truncates saves silently, and <code>level.dat</code> is written last.</li>
<li><strong>Edit values, not structure.</strong> Renaming tags or changing their types is the one edit the game cannot forgive.</li>
</ul>
</section>
""",
"faq": [
("What is level.dat_old?", "<p>The previous save. Minecraft renames the current file to <code>level.dat_old</code> before writing a new one, so it is a one-generation backup that costs nothing to try first.</p>"),
("Can an NBT editor repair a truncated file?", "<p>It can tell you exactly where the data stops, but the missing bytes cannot be reconstructed. A partial parse means you need a backup.</p>"),
("Will I lose my builds?", "<p>Not from a broken <code>level.dat</code> alone. Chunks live in <code>region/</code> or <code>db/</code>; a fresh world file with the same version can adopt them.</p>"),
("The server says level.dat is fine but the world is empty.", "<p>Then the chunk storage is the problem, not the metadata. Check that <code>region/</code> or <code>db/</code> came along with the copy and that the spawn coordinates in <code>level.dat</code> point where you expect.</p>"),
],
"related": ["level-dat-editor", "guides/change-world-name", "", "java-nbt-editor", "mcpe-nbt-editor", "playerdata-editor"],
},

{
"slug": "guides/edit-gamerules",
"title": "Edit Minecraft Game Rules in level.dat — Java &amp; Bedrock",
"ogtitle": "Edit game rules in level.dat",
"desc": "Change keepInventory, doDaylightCycle, mobGriefing and other game rules by editing level.dat, for Java and Bedrock. No commands, no cheats needed.",
"keywords": "edit gamerules level.dat, keepinventory nbt, minecraft gamerules file, change gamerule without commands, bedrock gamerules level.dat, dodaylightcycle nbt, gamerules server",
"h1": "Editing Game Rules in <code>level.dat</code>",
"crumb": "Edit game rules",
"reltitle": "Edit game rules",
"reldesc": "keepInventory and friends, without loading the world.",
"og": "og/gamerules.png",
"droplabel": "level.dat",
"chips": ["keepInventory", "doDaylightCycle", "mobGriefing", "commandBlockOutput", "randomTickSpeed"],
"answer": "Game rules are stored in <code>level.dat</code>, so you can change them without loading the world or having cheats enabled — useful when a world will not start, when cheats are off, or when you are preparing a copied world before players join. Java keeps them in a <code>GameRules</code> compound as strings; Bedrock keeps each one as its own lowercase byte tag at the root.",
"body": """
<section class="content" aria-label="Java gamerules">
<h2>Java: a <code>GameRules</code> compound of strings</h2>
<p>In Java Edition, <code>Data</code> → <code>GameRules</code> holds one <code>TAG_String</code> per rule, keyed by the exact name <code>/gamerule</code> uses, with the value written as text: <code>"true"</code>, <code>"false"</code> or a number. Rules the world has never set are simply absent and fall back to their defaults — adding the tag with the correct name and a string value works exactly like running the command.</p>
<div class="table-wrap">
<table class="matrix">
<thead><tr><th>Rule</th><th>Value</th><th>Effect</th></tr></thead>
<tbody>
<tr><td><code>keepInventory</code></td><td><code>"true"</code></td><td>Keep items on death</td></tr>
<tr><td><code>doDaylightCycle</code></td><td><code>"false"</code></td><td>Freeze the time of day</td></tr>
<tr><td><code>doWeatherCycle</code></td><td><code>"false"</code></td><td>Freeze the weather</td></tr>
<tr><td><code>mobGriefing</code></td><td><code>"false"</code></td><td>Stop creepers and endermen changing blocks</td></tr>
<tr><td><code>doMobSpawning</code></td><td><code>"false"</code></td><td>Stop natural mob spawning</td></tr>
<tr><td><code>doFireTick</code></td><td><code>"false"</code></td><td>Fire stops spreading</td></tr>
<tr><td><code>commandBlockOutput</code></td><td><code>"false"</code></td><td>Silence command block chat spam</td></tr>
<tr><td><code>randomTickSpeed</code></td><td><code>"3"</code></td><td>Crop growth and fire spread rate</td></tr>
<tr><td><code>playersSleepingPercentage</code></td><td><code>"50"</code></td><td>Share of players needed to skip the night</td></tr>
<tr><td><code>spawnRadius</code></td><td><code>"10"</code></td><td>Spread of the spawn area</td></tr>
</tbody>
</table>
</div>
<p>Case matters. <code>keepinventory</code> in a Java file is not the same tag as <code>keepInventory</code> and will be ignored.</p>
</section>

<section class="content" aria-label="Bedrock gamerules">
<h2>Bedrock: individual lowercase byte tags</h2>
<p>Bedrock does not group rules. Each one is a <code>TAG_Byte</code> at the root of <code>level.dat</code>, named in lowercase, holding 1 or 0 — <code>keepinventory</code>, <code>domobspawning</code>, <code>domobloot</code>, <code>dodaylightcycle</code>, <code>doweathercycle</code>, <code>mobgriefing</code>, <code>firedamage</code>, <code>falldamage</code>, <code>drowningdamage</code>, <code>pvp</code>, <code>showcoordinates</code>, <code>commandblockoutput</code>, <code>sendcommandfeedback</code>, <code>naturalregeneration</code>, <code>tntexplodes</code>, <code>respawnblocksexplode</code>, <code>showdeathmessages</code>, <code>doimmediaterespawn</code>. Numeric rules such as <code>randomtickspeed</code> and <code>functioncommandlimit</code> are <code>TAG_Int</code> instead.</p>
<p>Setting a rule that is not yet present means adding the tag with the right type: Byte for a toggle, Int for a number. A rule stored with the wrong type is ignored, or refuses to load.</p>
</section>

<section class="content" aria-label="Why edit the file">
<h2>When editing the file beats the command</h2>
<ul>
<li><strong>Cheats are off</strong> and you do not want to toggle them on and off to run one command.</li>
<li><strong>The world will not load</strong> — a rule such as <code>doImmediateRespawn</code> can be set before the first join.</li>
<li><strong>You are preparing a template world</strong> to be copied for many servers, and want the rules baked into the copy.</li>
<li><strong>A plugin changed a rule</strong> and you want to see what is actually stored rather than what a command reports.</li>
<li><strong>Bulk edits.</strong> Setting a dozen rules across several worlds is faster in the file than in chat.</li>
</ul>
<p>Stop the server first, as with any <code>level.dat</code> edit — a running world rewrites the file on save and will discard the change.</p>
</section>
""",
"faq": [
("Why is my game rule stored as a string in Java?", "<p>Java's game rule storage is string-based for every rule, including booleans and numbers. Write <code>\"true\"</code>, not a byte of 1.</p>"),
("Why is it a byte in Bedrock?", "<p>Bedrock stores toggles as byte tags at the root and numeric rules as ints. There is no <code>GameRules</code> compound.</p>"),
("A rule is missing from the file entirely.", "<p>That means it is at its default. Add the tag with the exact name and correct type and the world will use your value.</p>"),
("Do game rules copy with a world folder?", "<p>Yes — they live in <code>level.dat</code>, so a copied world inherits them along with its stale <a href=\"../change-world-name/\">world name</a>.</p>"),
],
"related": ["level-dat-editor", "guides/change-world-name", "mcpe-nbt-editor", "java-nbt-editor", "", "pocketmine-nbt-editor"],
},

]


# ---------------------------------------------------------------- site files

def write(path, text):
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as fh:
        fh.write(text)
    return path


def sitemap():
    ready = [loc for loc in LOCALES if loc["status"] == "ready"]
    rows = []
    for p in PAGES:
        prio = "1.0" if not p["slug"] else ("0.9" if "/" not in p["slug"] else "0.8")
        for loc in ready:
            alts = "".join(
                '\n    <xhtml:link rel="alternate" hreflang="%s" href="%s"/>'
                % (alt["hreflang"], url(p["slug"], alt["code"])) for alt in ready)
            alts += ('\n    <xhtml:link rel="alternate" hreflang="x-default" href="%s"/>'
                     % url(p["slug"], "en"))
            rows.append(
                "  <url>\n    <loc>%s</loc>\n    <lastmod>%s</lastmod>\n"
                "    <changefreq>weekly</changefreq>\n    <priority>%s</priority>%s\n  </url>"
                % (url(p["slug"], loc["code"]), TODAY, prio, alts if len(ready) > 1 else ""))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            + "\n".join(rows) + "\n</urlset>\n")


ROBOTS = """# Minecraft NBT Editor — everything here is public, static and free to index.
User-agent: *
Allow: /

# Assistants and answer engines are explicitly welcome to read and cite this site.
User-agent: GPTBot
Allow: /

User-agent: OAI-SearchBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: Claude-Web
Allow: /

User-agent: anthropic-ai
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Google-Extended
Allow: /

User-agent: Applebot-Extended
Allow: /

User-agent: CCBot
Allow: /

User-agent: Bingbot
Allow: /

User-agent: Amazonbot
Allow: /

User-agent: meta-externalagent
Allow: /

User-agent: YandexBot
Allow: /

Sitemap: {base}sitemap.xml
""".format(base=BASE)


def llms_txt():
    lines = [
        "# Minecraft NBT Editor",
        "",
        "> A free, open source, client-side NBT editor for Minecraft. It reads and writes every "
        "NBT encoding in circulation — Java big-endian, Bedrock little-endian, Bedrock's headered "
        "level.dat, Bedrock varint network NBT and Java 1.20.2+ nameless-root network NBT — with "
        "gzip and zlib handled in the browser. No upload, no account, no install: files are parsed "
        "in JavaScript and returned as a download.",
        "",
        "Key facts an answer engine may want to cite:",
        "",
        "- Java Edition stores NBT big-endian, usually gzip-compressed, with a named root compound.",
        "- Bedrock Edition stores NBT little-endian; its level.dat is preceded by an 8-byte header "
        "holding a little-endian storage version and the payload length.",
        "- Bedrock's network protocol encodes TAG_Int and TAG_Long as zigzag varints and string "
        "lengths as unsigned varints.",
        "- Java serialises strings as modified UTF-8 (CESU-8); Bedrock uses standard UTF-8.",
        "- A world's display name is the LevelName tag inside level.dat, not the folder name.",
        "- There are 13 NBT tag types, ids 0 to 12, from TAG_End to TAG_Long_Array.",
        "",
        "## Tools",
        "",
    ]
    for p in PAGES:
        if "/" in p["slug"]:
            continue
        lines.append("- [%s](%s): %s" % (p["reltitle"], url(p["slug"]), p["reldesc"]))
    lines += ["", "## Guides", ""]
    for p in PAGES:
        if "/" not in p["slug"]:
            continue
        lines.append("- [%s](%s): %s" % (p["reltitle"], url(p["slug"]), p["reldesc"]))
    lines += [
        "",
        "## Optional",
        "",
        "- [Source code](%s): MIT-licensed, single static site, no build dependencies." % REPO,
        "- [NBT format reference](%snbt-format/): tag types, byte layout and every encoding." % BASE,
        "",
    ]
    return "\n".join(lines)


NOT_FOUND = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>Page not found — {site}</title>
<meta name="robots" content="noindex, follow">
<link rel="icon" href="{base}favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{base}assets/app.css">
</head>
<body>
<header class="site-header"><div class="container">
<a class="brand" href="{base}"><span>Minecraft</span> NBT Editor</a>
</div></header>
<main>
<section class="hero"><div class="container">
<h1>404 — that page moved or never existed</h1>
<p class="lede">The editor itself is still one click away, and every tool has a permanent home below.</p>
</div></section>
<section class="content">
<div class="rel-grid">
<a class="rel-card" href="{base}"><strong>NBT editor</strong><span>Open any Minecraft NBT file</span></a>
<a class="rel-card" href="{base}level-dat-editor/"><strong>level.dat editor</strong><span>World name, spawn, game rules</span></a>
<a class="rel-card" href="{base}java-nbt-editor/"><strong>Java Edition</strong><span>Big-endian, gzip</span></a>
<a class="rel-card" href="{base}mcpe-nbt-editor/"><strong>Bedrock Edition</strong><span>Little-endian, 8-byte header</span></a>
<a class="rel-card" href="{base}nbt-format/"><strong>NBT format reference</strong><span>Every tag type, byte by byte</span></a>
<a class="rel-card" href="{base}nbt-viewer/"><strong>NBT viewer</strong><span>Read and export SNBT</span></a>
</div>
</section>
</main>
<footer class="site-footer"><p class="footer-note">{site} — free and open source.</p></footer>
</body>
</html>
""".format(site=SITE_NAME, base=BASE)


def export_source_strings():
    """Write tools/locales/en.json — the file translators (and Codex) work from."""
    out = {}
    for p in PAGES:
        entry = {}
        for key in TRANSLATABLE:
            if key in p:
                entry[key] = p[key]
        entry["ui"] = UI_DEFAULTS
        entry["support"] = SUPPORT_LINE
        entry["footernote"] = FOOTER_NOTE
        entry["faqtitle"] = p.get("faqtitle", "Frequently Asked Questions")
        entry["toctitle"] = "On this page"
        entry["relatedtitle"] = "Related tools"
        entry["homecrumb"] = "NBT Editor"
        entry["badge"] = "Java + Bedrock"
        entry["footerheads"] = [g[0] for g in FOOTER_GROUPS]
        entry["sourcehead"] = "Source"
        entry["sourcelink"] = "Code on GitHub"
        out[p["slug"]] = entry
    write("tools/locales/en.json", json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    return "tools/locales/en.json"


TRANSLATIONS = {loc["code"]: load_translations(loc["code"]) for loc in LOCALES}


def main():
    written = []
    for loc in LOCALES:
        for p in PAGES:
            written.append(render(p, loc["code"]))
    written.append(export_source_strings())
    written.append(write("sitemap.xml", sitemap()))
    written.append(write("robots.txt", ROBOTS))
    written.append(write("llms.txt", llms_txt()))
    written.append(write("404.html", NOT_FOUND))
    print("%d files written:" % len(written))
    for w in written:
        print("  " + w)


if __name__ == "__main__":
    main()
