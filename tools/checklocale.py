#!/usr/bin/env python3
"""Validate all configured locales against fresh source and the shared interface."""
from collections import Counter
from html import unescape
from html.parser import HTMLParser
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOC = os.path.join(ROOT, "tools", "locales")
INTERFACE = os.path.join(ROOT, "tools", "interface")
PLACEHOLDER_RE = re.compile(r"\{\d+\}|__[A-Z][A-Z_]*__")
IDENTIFIER_RE = re.compile(
    r"\b(?:TAG_[A-Za-z_]+|LevelName|DataVersion|GameRules|keepInventory|commandBlockOutput|doDaylightCycle|mobGriefing|randomTickSpeed)\b"
    r"|(?<![\w.])(?:[\w*<>-]+/)*(?:[\w*<>-]+)?\.(?:dat(?:_old)?|nbt|mcstructure|schem|schematic|mca)(?![A-Za-z_])"
)
# These are names and format identifiers, not a blanket English-prose exemption.
PROTECTED_NAMES = {
    "Minecraft", "Minecraft Bedrock Edition", "Minecraft Java Edition", "Minecraft: Java Edition",
    "Java Edition", "Bedrock Edition", "Java", "Bedrock", "MCPE", "NBT", "SNBT", "MIT", "ID",
    "Vanilla", "Paper", "Spigot", "Purpur", "Pufferfish", "Folia", "Leaves", "Fabric", "Quilt",
    "Forge", "NeoForge", "Mohist", "Arclight", "Sponge", "SpongeVanilla", "SpongeForge", "BDS",
    "Bedrock Dedicated Server", "PocketMine-MP", "Nukkit", "PowerNukkitX", "Nukkit-MOT", "Cloudburst",
    "Dragonfly", "Endstone", "LeviLamina", "Allay", "JukeboxMC", "GoMint", "Geyser", "WaterdogPE",
    "WorldEdit", "MCEdit", "Litematica", "NBTExplorer", "NBT Studio", "nbtlib", "nbt", "GZip",
    "gzip", "zlib", "zlib (deflate)", "deflate", "BigInt", "DataVersion", "LevelDB", "JSON",
    "Windows", "Linux", "macOS", "Android", "iOS", "iPadOS", "GitHub", "UTF-8", "CESU-8",
    "big-endian", "little-endian", "Big-endian", "Little-endian", "Varint LE / nameless BE",
    "Byte", "Short", "Int", "Long", "Float", "Double", "byte", "short", "int", "long", "float", "double", "String", "List", "Compound", "End",
    "Byte[]", "Int[]", "Long[]", "Int[4]", "Java + Bedrock", "PT3M", "PT5M", "PT10M",
    "BDSX", "Sculk", "ElementZero", "LiteLoaderBDS", "MCBE", "CraftBukkit", "Gale", "Petal",
    "Airplane", "Magma", "Ketting", "Banner", "Cardboard", "Glowstone", "Thermos", "Uberbukkit",
    "Waterfall", "Velocity", "BungeeCord", "Cloudburst Server", "Amulet", "ChromeOS",
    "FastAsyncWorldEdit", "MCA Selector", "NBTStudio", "PM3", "PM4", "PM5", "Id", "Varint",
    "Bedrock Dedicated Server (BDS)", "PocketMine-MP (PM5)", "Sponge Schematic v2 (WorldEdit 7)",
    "Sponge Schematic v2/v3", "Sponge Schematic v3", "playerdata", "level.dat_old", "keepInventory",
    "hub", "Java level.dat", "Bedrock level.dat", "Java playerdata", "Java big-endian", "Bedrock little-endian",
    "commandBlockOutput", "doDaylightCycle", "mobGriefing", "randomTickSpeed", "beta",
}
# Genuine identical words in the named language. Never exempt a whole sentence.
COGNATES = {
    "fr": {"Guides", "Causes", "Introduction", "2 minutes", "Cause", "Extension", "Position", "Type", "Compression", "Version", "Format", "Structure", "Compatible", "Source", "Versions", "Modification"},
    "de": {"in", "Tag", "Offset", "Header", "Symptom", "Edition", "Tags in level.dat", "Position", "Array", "Editor", "Format", "Version", "Server", "Byte", "String"},
    "es": {"Error: {0}", "No", "Editor", "Version", "Local", "Compatible", "Format"},
    "pt-br": {"Use", "A", "Tag", "Offset", "Strings", "NBTExplorer (desktop)", "Array", "Editor", "Local", "Compatible"},
    "it": {"in", "In Java Edition", ", Android in", "No", "Tag", "Offset", "Payload", "NBTExplorer (desktop)", "NBTExplorer online", "Big-endian, gzip — Vanilla, Paper, Spigot, Fabric, Forge", "Android in", "Array", "Editor", "File", "Version", "Format", "Server", "Byte"},
    "pl": {"NBTExplorer online", "folder", "Editor", "Format", "Tag"},
    "id": {"Platform", "folder", "Diagnosis", "Header", "NBTExplorer (desktop)", "Offset", "Metadata", "Array", "Editor", "Format", "File", "Server", "Byte", "Tag", "Data"},
    "tr": {"Platform", "Format", "Byte"},
    "vi": {"Byte"},
}


class Fragment(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.structure = []
        self.protected = []
        self.visible = []
        self.code_depth = 0
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.structure.append(("start", tag, self.get_starttag_text()))
        if tag in ("code", "pre"):
            self.code_depth += 1

    def handle_startendtag(self, tag, attrs):
        self.structure.append(("empty", tag, self.get_starttag_text()))

    def handle_endtag(self, tag):
        self.structure.append(("end", tag))
        if tag in ("code", "pre"):
            self.code_depth = max(0, self.code_depth - 1)

    def handle_data(self, data):
        if self.code_depth:
            self.protected.append(data)
        else:
            self.visible.append(data)


def exempt(text, code):
    text = " ".join(unescape(text).split()).strip()
    text = text.strip(" —,:;").rstrip(".")
    if code in ("es", "pt-br") and re.fullmatch(r"(?:\[\{\d+\} bytes\]|\d+ bytes(?:, IEEE 754)?)", text):
        return True
    if not re.search(r"[A-Za-z]", text):
        return True
    if text in PROTECTED_NAMES or text.strip("()") in PROTECTED_NAMES or text in COGNATES.get(code, set()):
        return True
    # File names, enum identifiers, durations, and lists containing only brands.
    if re.fullmatch(r"(?:TAG_[A-Za-z_]+|(?:[\w*<>/-]+)?\.(?:dat|nbt|mcstructure|schem|schematic|mca|txt)|PT\d+M)", text):
        return True
    parts = re.split(r"\s*[,·/+|]\s*", text)
    if len(parts) > 1 and all(part.strip("()") in PROTECTED_NAMES or not re.search('[A-Za-z]', part) for part in parts):
        return True
    return False


def validate_value(source, target, path, code, problems, counts):
    if type(target) is not type(source):
        problems.append(path + ": type changed")
        return
    if isinstance(source, dict):
        for key in source.keys() - target.keys():
            problems.append(path + "." + key + ": missing")
        for key in target.keys() - source.keys():
            problems.append(path + "." + key + ": unknown key")
        for key in source.keys() & target.keys():
            validate_value(source[key], target[key], path + "." + key, code, problems, counts)
    elif isinstance(source, list):
        if len(target) != len(source):
            problems.append(path + ": list length changed")
        for index, (src, dst) in enumerate(zip(source, target)):
            validate_value(src, dst, "%s[%d]" % (path, index), code, problems, counts)
    elif isinstance(source, str):
        before = len(problems)
        if source.strip() and not target.strip():
            problems.append(path + ": empty translation")
        if Counter(PLACEHOLDER_RE.findall(source)) != Counter(PLACEHOLDER_RE.findall(target)):
            problems.append(path + ": placeholder changed")
        src, dst = Fragment(source), Fragment(target)
        # Filenames/NBT identifiers outside code spans are still machine-readable
        # values in interface/dropzone fields (for example the LevelName shortcut).
        # Editorial headings and search keywords may legitimately abbreviate names;
        # code spans in their content remain protected independently.
        if path.count(".") <= 1 or ".ui." in path or path.endswith(".droplabel"):
            src_identifiers = IDENTIFIER_RE.findall(unescape(source))
            if any(unescape(target).count(token) < count for token, count in Counter(src_identifiers).items()):
                problems.append(path + ": filename or NBT identifier changed")
        if re.fullmatch(r"PT\d+[HMS]", source) and source != target:
            problems.append(path + ": duration identifier changed")
        if src.structure != dst.structure:
            problems.append(path + ": HTML tags or attributes changed")
        if src.protected != dst.protected:
            problems.append(path + ": code/pre text changed")
        # Inspect every visible source node rather than averaging page-level fields.
        # A translated heading cannot hide an untouched English paragraph/table cell.
        dst_nodes = {" ".join(v.split()) for v in dst.visible}
        for node in src.visible:
            normalized = " ".join(node.split())
            if normalized and not exempt(normalized, code):
                counts[1] += 1
                if normalized in dst_nodes:
                    problems.append(path + ": untranslated text: " + normalized[:100])
                else:
                    counts[0] += 1
        if not src.visible and source != target:
            # Strings composed solely of markup/code must remain semantically exact.
            if len(problems) == before and source.strip() and not target.strip():
                problems.append(path + ": protected content missing")
    elif source != target:
        problems.append(path + ": non-text value changed")


def validate_catalog(source, target, code):
    problems, counts = [], [0, 0]
    validate_value(source, target, code, code, problems, counts)
    coverage = round(100 * counts[0] / counts[1], 1) if counts[1] else 100
    return problems, coverage


def check(code, source=None):
    if source is None:
        import build
        source = build.source_strings()
    problems, coverage = [], []
    for directory, english, label in ((LOC, source, "pages"), (INTERFACE, None, "interface")):
        try:
            if english is None:
                with open(os.path.join(directory, "en.json"), encoding="utf-8") as fh:
                    english = json.load(fh)
            with open(os.path.join(directory, code + ".json"), encoding="utf-8") as fh:
                translation = json.load(fh)
        except (OSError, ValueError) as exc:
            problems.append("%s/%s.json: %s" % (label, code, exc))
            coverage.append(0)
            continue
        found, score = validate_catalog(english, translation, code)
        problems.extend(label + ": " + problem for problem in found)
        coverage.append(score)
    return problems, min(coverage)


def main():
    import build
    configured = [loc["code"] for loc in build.LOCALES if loc["code"] != "en"]
    codes = sys.argv[1:] or configured
    failed = False
    for code in codes:
        if code not in configured:
            print(code + ": unknown locale")
            failed = True
            continue
        problems, coverage = check(code, source=build.source_strings())
        print("%-8s coverage %5.1f%%  %s" % (code, coverage, "OK" if not problems else "%d problem(s)" % len(problems)))
        for problem in problems[:25]:
            print("   ✗", problem)
        if len(problems) > 25:
            print("   … %d more" % (len(problems) - 25))
        failed = failed or bool(problems)
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
