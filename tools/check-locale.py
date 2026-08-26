#!/usr/bin/env python3
"""Validate a translation file against the English source.

    python3 tools/check-locale.py ru [ru es de …]

Checks that keys match, that HTML structure and placeholders survived, and that
title/description still fit the search snippet limits. Exit code 1 on failure,
so it can gate flipping a locale from draft to ready.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOC = os.path.join(ROOT, "tools", "locales")
TAG_RE = re.compile(r"<([a-zA-Z0-9]+)[^>]*>")
HREF_RE = re.compile(r'href="([^"]*)"')
PLACEHOLDER_RE = re.compile(r"\{\d+\}|__HOME__")


def texts(value):
    """Yield every string inside a nested value."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for v in value:
            yield from texts(v)
    elif isinstance(value, dict):
        for v in value.values():
            yield from texts(v)


def check(code):
    en = json.load(open(os.path.join(LOC, "en.json")))
    path = os.path.join(LOC, code + ".json")
    if not os.path.exists(path):
        return ["%s.json does not exist" % code], 0
    try:
        tr = json.load(open(path))
    except Exception as exc:
        return ["%s.json is not valid JSON: %s" % (code, exc)], 0

    problems, translated, total = [], 0, 0
    for slug, entry in en.items():
        if slug not in tr:
            problems.append("%s: whole page missing" % (slug or "(home)"))
            continue
        for key, src in entry.items():
            if key not in tr[slug]:
                problems.append("%s.%s: missing" % (slug or "(home)", key))
                continue
            dst = tr[slug][key]
            total += 1
            if dst != src:
                translated += 1
            if type(dst) is not type(src):
                problems.append("%s.%s: type changed" % (slug or "(home)", key))
                continue
            src_text, dst_text = " ".join(texts(src)), " ".join(texts(dst))
            if sorted(TAG_RE.findall(src_text)) != sorted(TAG_RE.findall(dst_text)):
                problems.append("%s.%s: HTML tags changed" % (slug or "(home)", key))
            if sorted(HREF_RE.findall(src_text)) != sorted(HREF_RE.findall(dst_text)):
                problems.append("%s.%s: links changed" % (slug or "(home)", key))
            if sorted(PLACEHOLDER_RE.findall(src_text)) != sorted(PLACEHOLDER_RE.findall(dst_text)):
                problems.append("%s.%s: placeholder lost" % (slug or "(home)", key))
        title = tr[slug].get("title", "")
        desc = tr[slug].get("desc", "")
        rendered = title.replace("&amp;", "&").replace("&mdash;", "—")
        if len(rendered) > 62:
            problems.append("%s.title: %d chars (max 62)" % (slug or "(home)", len(rendered)))
        if desc and not 110 <= len(desc) <= 165:
            problems.append("%s.desc: %d chars (want 120-160)" % (slug or "(home)", len(desc)))
    coverage = round(100.0 * translated / total) if total else 0
    return problems, coverage


def main():
    codes = sys.argv[1:] or [f[:-5] for f in sorted(os.listdir(LOC))
                             if f.endswith(".json") and f != "en.json"]
    failed = False
    for code in codes:
        problems, coverage = check(code)
        head = "%-8s coverage %3d%%  %s" % (code, coverage,
                                            "OK" if not problems else "%d problem(s)" % len(problems))
        print(head)
        for p in problems[:25]:
            print("   ✗", p)
        if len(problems) > 25:
            print("   … %d more" % (len(problems) - 25))
        failed = failed or bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
