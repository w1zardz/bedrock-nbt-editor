# Translating the site

There are two English sources:

- `tools/locales/en.json`: all 14 pages, exported from the current `PAGES` data and defaults in `tools/build.py`.
- `tools/interface/en.json`: shared controls, dialogs, accessibility labels, runtime errors, format descriptions, structured-data text and the 404 page.

For each configured language, translate both files into the matching `tools/locales/<code>.json` and `tools/interface/<code>.json`. Shared strings belong in the interface catalog, not in 14 copies of page `ui`. Existing page `ui` translations still override runtime defaults for compatibility.

The empty page slug `""` is the home page. Keep all keys, nested object shapes, list lengths and value types. Translate every human-readable text node, including table cells, FAQ answers, instructions, search metadata, footer labels and explanatory fragments between code tags.

## Preserve technical content

1. Preserve every HTML tag and attribute exactly, including link destinations, IDs and classes. Page accessibility attributes are translated centrally from `aria_*` entries in the interface catalog at rendering time.
2. Preserve code, `<code>` and `<pre>` contents, NBT names such as `LevelName`, enum identifiers such as `TAG_Compound`, filenames, extensions, paths and product names. The example world name `hub` corresponds to a literal path and is not prose.
3. Preserve every positional placeholder (`{0}`, `{1}`, etc.) and `__HOME__`, including its occurrence count. A language may reorder placeholders within a sentence.
4. Keep titles and descriptions concise and natural. Search engines have no universal character limit shared by every writing system; there is no artificial minimum that forces padding in Chinese, Japanese or Korean.
5. Use natural search terms in `keywords` and plain, technically accurate language throughout. Do not add marketing claims.
6. Headings are translated as text. The builder derives unique heading IDs from the English headings by position, so internal anchors remain stable across languages. Existing IDs such as `server-software` are preserved.

## Validate and build

Run `python3 tools/checklocale.py <code>` while translating. With no arguments it checks every configured non-English language, including missing files. It reads fresh English source from the builder, not a potentially stale exported JSON file.

Validation checks every nested string, HTML structure and attributes, protected code, placeholders and unchanged English text nodes. Product names, technical identifiers and explicitly documented same-spelling words are exempt; an unchanged English paragraph is never hidden by a percentage threshold. If a legitimate word is spelled identically in both languages, add a narrow language-specific entry in `COGNATES` in `tools/checklocale.py`, after checking the context. Do not add whole English paragraphs or generic exemptions.

Run `python3 tools/test_localization.py` for focused rendering, catalog-validation, language-routing and binary-parser regressions. Run `python3 tools/build.py` once all 16 translations pass. The build validates the complete release before writing anything and stops on any missing, malformed or incomplete catalog. It generates 238 localized content pages plus 17 localized 404 pages. The root 404 chooses the explicit language from the URL; without JavaScript, its English fallback still contains working links.

After building, run `python3 tools/checksite.py` to verify all generated pages, local links and anchors, schemas, language metadata and sitemap coverage.

The build automatically marks validated locales ready and includes them in the sitemap and hreflang links. Do not manually promote an incomplete locale. Importing the builder for checks does not write files or change readiness.
