# Translating the site

The English source of every translatable string is `tools/locales/en.json`,
regenerated on every `python3 tools/build.py`. A translation is the same file
with the same keys, saved as `tools/locales/<code>.json` (e.g. `ru.json`).

## Structure

```json
{
  "<page slug>": {
    "title": "…", "desc": "…", "keywords": "…", "h1": "…",
    "answer": "…", "body": "…", "faq": [["question", "answer html"], …],
    "chips": ["…"], "howto": {"name": "…", "steps": [["step title", "step text"], …]},
    "ui": {"loaded": "…", …}, "support": "…", …
  }
}
```

The empty slug `""` is the home page. Any key you omit falls back to English,
so a partial translation is valid — it just renders mixed.

## Rules

1. **Values are HTML fragments.** Keep every tag, attribute, `href`, `id` and
   `class` exactly as in the source. Translate only the text between tags.
2. **Never translate code.** Anything inside `<code>`, `<pre>`, NBT tag names
   (`LevelName`, `TAG_Compound`, `GameRules`, `keepInventory`), file names
   (`level.dat`, `.mcstructure`), paths, and product names (PocketMine-MP,
   Nukkit, Paper, Fabric, WorldEdit, NBTExplorer) stay as they are.
3. **Placeholders are literal.** `{0}`, `{1}` in `ui` strings and `__HOME__` in
   `support` must survive untouched, in the same order where the language allows.
4. **`title`** must read under 60 characters, **`desc`** between 120 and 160
   characters — these are the search snippet limits and the build checks them.
5. **`keywords`** should be the real search terms people type in that language,
   not a literal translation of the English list.
6. Keep the meaning technical and plain. This is documentation, not marketing.
7. The file must stay valid JSON (`python3 -c "import json;json.load(open(...))"`).

## Turning a translation on

A locale is listed in `LOCALES` in `tools/build.py`. While its `status` is
`"draft"` the pages are built but marked `noindex` and kept out of the sitemap,
so an unfinished translation cannot hurt search rankings. Flip it to `"ready"`
once the file is complete, then rebuild.
