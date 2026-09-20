#!/usr/bin/env python3
"""Focused regression checks; does not build or rewrite any generated pages."""
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import build
import checklocale


class CatalogTests(unittest.TestCase):
    def issues(self, src, dst):
        return checklocale.validate_catalog(src, dst, "ru")[0]

    def test_shape_types_and_placeholders(self):
        source = {"faq": [["Question", "Answer {0}"]], "ui": {"label": "Open"}}
        for target in (
            {"faq": [["Вопрос"]], "ui": {"label": "Открыть"}},
            {"faq": [["Вопрос", "Ответ {1}"]], "ui": {"label": "Открыть"}},
            {"faq": [["Вопрос", "Ответ {0}"]], "ui": {"label": ["Открыть"]}},
            {"faq": [["Вопрос", "Ответ {0}"]], "ui": {}},
        ):
            self.assertTrue(self.issues(source, target))
        self.assertFalse(self.issues(source, {"faq": [["Вопрос", "Ответ {0}"]], "ui": {"label": "Открыть"}}))

    def test_english_paragraph_cannot_hide_behind_translated_heading(self):
        source = "<h2>Instructions</h2><p>Open the file in your browser.</p>"
        self.assertTrue(self.issues(source, "<h2>Инструкция</h2><p>Open the file in your browser.</p>"))
        self.assertFalse(self.issues("<p>Java</p><p>Open</p>", "<p>Java</p><p>Открыть</p>"))

    def test_attributes_code_and_placeholder_counts_are_protected(self):
        source = '<p class="lead"><a href="__HOME__#server-software">Open</a> <code>LevelName</code> {0} {0}</p>'
        valid = '<p class="lead"><a href="__HOME__#server-software">Открыть</a> <code>LevelName</code> {0} {0}</p>'
        self.assertFalse(self.issues(source, valid))
        for bad in (valid.replace('class="lead"', 'class="other"'), valid.replace('LevelName', 'Название'), valid.replace('{0} {0}', '{0}')):
            self.assertTrue(self.issues(source, bad))

    def test_plain_filenames_identifiers_and_durations_are_protected(self):
        for source, target in (("Edit LevelName", "Изменить Название"), ("Open level.dat", "Открыть уровень.dat"), ("PT3M", "3 минуты")):
            self.assertTrue(self.issues(source, target))

    def test_missing_configured_locale_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(checklocale, "LOC", directory):
            self.assertTrue(checklocale.check("ko", source={"": {"title": "Editor"}})[0])

    def test_invalid_catalog_stops_build_before_any_writes(self):
        with patch.object(build, "resolve_status", return_value={"id": ["untranslated text"]}), patch.object(build, "write") as writer, patch.object(build, "render") as renderer:
            with self.assertRaises(SystemExit):
                build.main()
            writer.assert_not_called()
            renderer.assert_not_called()

    def test_source_validation_is_fresh(self):
        source = build.source_strings()
        self.assertIn("footerheads", source[""])
        self.assertIn("footernote", build.TRANSLATABLE)
        with patch.object(checklocale, "check", return_value=(["missing fresh field"], 99)) as checker:
            statuses = [loc["status"] for loc in build.LOCALES]
            try:
                build.resolve_status()
                self.assertTrue(all(loc["status"] == "draft" for loc in build.LOCALES[1:]))
                self.assertEqual(checker.call_args.kwargs["source"], build.source_strings())
            finally:
                for loc, status in zip(build.LOCALES, statuses):
                    loc["status"] = status


class RenderingTests(unittest.TestCase):
    def test_anchors_use_english_and_avoid_existing_id(self):
        english = '<section id="server-software"><h2>Server software</h2><h2>More</h2><h2>More</h2></section>'
        translated = '<section id="server-software"><h2>Серверы</h2><h2>Далее</h2><h2>Далее</h2></section>'
        text, toc = build.anchor_headings(translated, english)
        self.assertEqual([id_ for id_, title in toc], ["server-software-2", "more", "more-2"])
        self.assertEqual(text.count('id="server-software"'), 1)

    def test_shared_interface_legacy_page_strings_and_aria_are_rendered(self):
        ui = dict(build.INTERFACES["en"])
        ui.update(choose_file="Выбрать файл", aria_tools="Инструменты", updated="Обновлено {0}.", brand_editor="Редактор NBT")
        page = {"ui": {"loaded": "Загружено: {0}"}, "footernote": "Локализованный подвал", "footerheads": ["А", "Б", "В"]}
        with patch.dict(build.INTERFACES, {"ru": ui}), patch.dict(build.TRANSLATIONS, {"ru": {"": page}}):
            html = build.render_html(build.PAGES[0], "ru")
        self.assertIn(">Выбрать файл</button>", html)
        self.assertIn('aria-label="Инструменты"', html)
        self.assertIn("Локализованный подвал", html)
        self.assertIn('"loaded":"Загружено: {0}"', html)
        self.assertIn("Обновлено " + build.TODAY, html)
        self.assertNotIn("__DROPLABEL__", html)

    def test_drop_label_entities_are_escaped_exactly_once(self):
        html = build.render_html(next(p for p in build.PAGES if p["slug"] == "pocketmine-nbt-editor"), "en")
        self.assertIn("worlds/&lt;World&gt;/level.dat", html)
        self.assertNotIn("&amp;lt;World&amp;gt;", html)

    def test_title_entities_are_escaped_exactly_once(self):
        html = build.render_html(next(p for p in build.PAGES if p["slug"] == "guides/change-world-name"), "en")
        title = re.search(r"<title>(.*?)</title>", html)[1]
        self.assertNotIn("&amp;amp;", title)

    def test_script_strings_cannot_close_script(self):
        encoded = build.script_json({"text": "</script><script>alert(1)</script>"})
        self.assertNotIn("<", encoded)
        self.assertEqual(json.loads(encoded)["text"], "</script><script>alert(1)</script>")

    def test_404_keeps_static_local_links_and_routes_explicit_locale(self):
        html = build.not_found_html("ru")
        self.assertIn('lang="ru"', html)
        self.assertIn(build.url("level-dat-editor", "ru"), html)
        self.assertNotIn("location.replace", html)
        self.assertIn("location.replace", build.not_found_html("en"))

    def test_all_shared_template_text_is_catalogued(self):
        # Exhaustive visible prose check before translation: identifiers remain literal.
        catalog = set(build.INTERFACES["en"].values())
        fragment = checklocale.Fragment(build.EDITOR_WIDGET.replace("Drop <strong>__DROPLABEL__</strong> here", "") + build.MODALS)
        for node in fragment.visible:
            text = " ".join(node.split())
            if text and not checklocale.exempt(text, "ru"):
                self.assertIn(text, catalog)

    def test_all_editorial_aria_labels_are_catalogued(self):
        values = set(build.INTERFACES["en"].values())
        for page in build.PAGES:
            for label in re.findall(r'aria-label="([^"]+)"', page["body"]):
                self.assertIn(label, values)


class RuntimeTests(unittest.TestCase):
    def test_language_routing_normalizes_html_and_legacy_cookie_case(self):
        script = r'''const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(process.argv[1],'utf8');
function run(lang,cookie,prefs){
  let creates=0,redirect='';
  const context={window:{__LANG_URLS__:{en:'/', 'pt-br':'/pt-br/', 'zh-hans':'/zh-hans/'}},
    document:{documentElement:{lang},cookie,addEventListener(){},querySelector(){creates++;return null}},
    navigator:{languages:prefs},sessionStorage:{getItem(){return null},setItem(){}},
    location:{replace(url){redirect=url}}};
  vm.runInNewContext(source,context);return {creates,redirect};
}
assert.deepEqual(run('pt-BR','',['pt-BR']),{creates:0,redirect:''});
assert.deepEqual(run('zh-Hans','',['zh-CN']),{creates:0,redirect:''});
assert.equal(run('en','nbtlang=PT-BR',['en']).redirect,'/pt-br/');
assert.equal(run('en','nbtlang=zh-Hans',['en']).redirect,'/zh-hans/');
'''
        subprocess.run(["node", "-e", script, os.path.join(build.ROOT, "assets", "lang.js")], check=True, capture_output=True, text=True)

    def test_parser_roundtrips_and_localized_errors(self):
        script = r'''
const assert=require('assert');
const element={addEventListener(){},classList:{contains(){return false}},style:{}};
global.window={__NBT_STRINGS__:{err_root:'ROOT {0}',err_tag_type:'TYPE {0}',format_label_java:'JAVA LOCAL'}};
global.document={getElementById(){return element},addEventListener(){}};
require(process.argv[1]);
const NBT=window.NBT,T=NBT.TAG;
const root={type:T.COMPOUND,name:'',value:[
{type:T.STRING,name:'LevelName',value:'Мир 🌍'},
{type:T.LONG,name:'seed',value:9223372036854775807n},
{type:T.LIST,name:'items',listType:T.INT,value:[{type:T.INT,value:-42}]},
{type:T.BYTE_ARRAY,name:'bytes',value:new Int8Array([-1,2])}]};
(async()=>{
for(const format of Object.keys(NBT.FORMATS)){
  for(const compression of ['none','gzip','zlib']){
    const bytes=await NBT.write(root,format,{compression});
    const plain=await NBT.decompress(bytes,compression);
    const parsed=NBT.parseWithFormat(plain,format);
    assert.deepStrictEqual(parsed.root,root);
  }
}
assert.equal(NBT.FORMATS.java.label,'JAVA LOCAL');
assert.throws(()=>NBT.parseWithFormat(new Uint8Array([1,0,0,0]),'java'),/ROOT 1/);
assert.throws(()=>NBT.parseWithFormat(new Uint8Array([10,0,0,99]),'java'),/TYPE 99/);
assert.equal(NBT.toSNBT(root).includes('9223372036854775807L'),true);
})().catch(e=>{console.error(e);process.exit(1)});
'''
        subprocess.run(["node", "-e", script, os.path.join(build.ROOT, "assets", "nbt.js")], check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
