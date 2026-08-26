#!/usr/bin/env bash
# Renders the Open Graph card for every page. Needs ImageMagick 7 (magick).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p og
ICON=/tmp/og-icon.png
magick -background none favicon.svg -resize 120x120 "$ICON"

card() { # slug  title  subtitle
  local out="og/$1.png" title="$2" sub="$3"
  magick -size 1200x630 xc:'#0d1117' \
    -fill '#161b22' -draw 'roundrectangle 40,40 1160,590 18,18' \
    -fill '#30363d' -draw 'roundrectangle 40,40 1160,44 2,2' \
    "$ICON" -geometry +90+90 -composite \
    \( -background none -fill '#8b949e' -font '/System/Library/Fonts/Supplemental/Arial.ttf' -pointsize 30 \
       label:'Minecraft NBT Editor' \) -geometry +240+130 -composite \
    \( -background none -fill '#e6edf3' -font '/System/Library/Fonts/Supplemental/Arial Bold.ttf' -pointsize 68 \
       -size 1010x caption:"$title" \) -geometry +95+265 -composite \
    \( -background none -fill '#58a6ff' -font '/System/Library/Fonts/Supplemental/Arial.ttf' -pointsize 32 \
       -size 1010x caption:"$sub" \) -geometry +95+480 -composite \
    "$out"
  echo "$out"
}

card home        "Minecraft NBT Editor"            "Java + Bedrock · level.dat, .nbt, .mcstructure, .schem"
card level-dat   "level.dat Editor"                "World name, game mode, spawn, game rules"
card java        "Java Edition NBT Editor"         "Big-endian, gzip · Vanilla, Paper, Fabric, Forge"
card bedrock     "Bedrock NBT Editor"              "Little-endian + 8-byte header · MCPE, BDS"
card pocketmine  "PocketMine-MP level.dat Editor"  "PMMP, Nukkit, PowerNukkitX, BDS"
card mcstructure ".mcstructure Editor"             "Bedrock structure blocks, palette and entities"
card schematic   "Schematic Editor"                "WorldEdit .schem and MCEdit .schematic"
card playerdata  "playerdata Editor"               "Inventory, position, health, attributes"
card viewer      "NBT Viewer"                      "Open, search and export any NBT file as SNBT"
card nbtexplorer "NBTExplorer Online"              "The browser alternative — no install, Bedrock too"
card format      "NBT Format Reference"            "13 tag types, 5 encodings, byte by byte"
card rename      "Change a Minecraft World Name"   "Fix LevelName after copying a world folder"
card fix         "Fix a Corrupted level.dat"       "Diagnose truncation, headers and compression"
card gamerules   "Edit Game Rules in level.dat"    "keepInventory and friends, without commands"
