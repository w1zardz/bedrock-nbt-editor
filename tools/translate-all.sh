#!/usr/bin/env bash
# Hands every draft locale to Codex, one at a time, and validates each result.
#
#   bash tools/translate-all.sh              # every locale that is not complete
#   bash tools/translate-all.sh es de fr     # only these
#
# Each run writes tools/locales/<code>.json. Validation output goes to
# tools/locales/_report.txt so a failed locale is obvious afterwards.
set -uo pipefail
cd "$(dirname "$0")/.."
RUNNER="$HOME/.claude/bin/codex-task.sh"
REPORT=tools/locales/_report.txt

declare -a ALL=(ru es pt-br de fr it pl uk tr id vi th zh-hans ja ko ar)
declare -A NAME=(
  [ru]="Russian" [es]="Spanish (neutral Latin American)" [pt-br]="Brazilian Portuguese"
  [de]="German" [fr]="French" [it]="Italian" [pl]="Polish" [uk]="Ukrainian"
  [tr]="Turkish" [id]="Indonesian" [vi]="Vietnamese" [th]="Thai"
  [zh-hans]="Simplified Chinese" [ja]="Japanese" [ko]="Korean" [ar]="Arabic"
)

TARGETS=("$@")
if [ ${#TARGETS[@]} -eq 0 ]; then TARGETS=("${ALL[@]}"); fi

for code in "${TARGETS[@]}"; do
  lang="${NAME[$code]:-$code}"
  if python3 tools/check-locale.py "$code" >/dev/null 2>&1; then
    echo "[$code] already complete, skipping" | tee -a "$REPORT"
    continue
  fi
  echo "[$code] translating into $lang …" | tee -a "$REPORT"
  "$RUNNER" -C "$PWD" --timeout 7200 "Translate this site into ${lang}.

Source of truth: tools/locales/en.json — 14 page entries of English HTML fragments and UI strings.
Deliverable: tools/locales/${code}.json — the SAME JSON structure, the SAME keys, values translated into ${lang}.

Read tools/locales/TRANSLATION.md first and obey it. The rules that break the build if ignored:
- values are HTML fragments: every tag, attribute, href target, id and class must stay byte-identical; translate only the human-readable text between tags;
- never translate code, NBT tag names (LevelName, TAG_Compound, GameRules, keepInventory), file names (level.dat, .mcstructure, .schem), paths, or product names (PocketMine-MP, Nukkit, Paper, Spigot, Fabric, Forge, WorldEdit, NBTExplorer, Bedrock Dedicated Server);
- the placeholders {0} {1} in the 'ui' object and __HOME__ in 'support' must survive exactly;
- 'title' must render under 60 characters and 'desc' must be 120-160 characters — count them, these are search snippet limits;
- 'keywords' must be the terms ${lang} speakers actually type into Google for this tool, not a word-for-word translation of the English list;
- tone is technical documentation for server admins and players: plain, precise, no marketing language.

Work slug by slug, keeping the file valid JSON after every save. Verify when done:
  python3 tools/check-locale.py ${code}
and fix whatever it reports until it passes.

Do not touch any other file. Do not commit, push or run git."
  echo "[$code] validation:" | tee -a "$REPORT"
  python3 tools/check-locale.py "$code" 2>&1 | tee -a "$REPORT"
done

echo "=== all done ===" | tee -a "$REPORT"
python3 tools/check-locale.py 2>&1 | tee -a "$REPORT"
