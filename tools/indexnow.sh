#!/usr/bin/env bash
# Notifies IndexNow (Bing, Yandex, Seznam, Naver) that the site changed.
# Google does not use IndexNow — submit the sitemap in Search Console instead.
set -euo pipefail
cd "$(dirname "$0")/.."
KEY=0a95e477a102901f3eacd4c271376c51
HOST=w1zardz.github.io
BASE=https://w1zardz.github.io/minecraft-nbt-editor/
URLS=$(grep -o '<loc>[^<]*' sitemap.xml | sed 's|<loc>||' | python3 -c 'import sys,json;print(json.dumps([l.strip() for l in sys.stdin]))')
curl -s -X POST https://api.indexnow.org/indexnow \
  -H 'Content-Type: application/json; charset=utf-8' \
  -d "{\"host\":\"$HOST\",\"key\":\"$KEY\",\"keyLocation\":\"${BASE}0a95e477a102901f3eacd4c271376c51.txt\",\"urlList\":$URLS}" \
  -o /dev/null -w 'IndexNow HTTP %{http_code}\n'
