#!/bin/zsh
# card.sh "<card name>"  — create one Yoto playlist from Music/<card> with its art
S=${0:A:h}; card=$1; y=$S/yjs
n=$(ls "${MP3_DIR:-$HOME/Library/CloudStorage/SynologyDrive-SynologySync/mp3}/Music/$card" | grep -ci '\.mp3$')
enc=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$card")
wait_for() { for i in {1..90}; do r=$($y -e "$1"); [[ $r == true ]] && return 0; sleep 2; done; echo "TIMEOUT: $1"; return 1 }
$y -e 'location.href="https://my.yotoplay.com/cards/new"; 1' >/dev/null; sleep 5
python3 $S/upload.py "$card" $S/up.js && $y $S/up.js >/dev/null
wait_for "[...document.querySelectorAll('li [data-testid=editable-field]')].length === $n && (document.body.innerText.match(/ MB/g)||[]).length === $n && !!document.querySelector('img[alt=\"Cover Artwork\"]')" || exit 1
echo "$card: $n songs + cover uploaded"
$y -e 'document.querySelector("li [data-testid=track-icon-button]").click(); 1' >/dev/null; sleep 2
sed "s#ICONURL#http://127.0.0.1:8766/.yoto-art/$enc/icon.png#" $S/icon.js > $S/i.js; $y $S/i.js >/dev/null
wait_for "window.__r && window.__r.includes('uploaded')" || exit 1; sleep 4
sed "s#ICONURL#http://127.0.0.1:8766/.yoto-art/$enc/icon.png#" $S/match.js > $S/m.js; $y -e 'window.__r=""; 1' >/dev/null; $y $S/m.js >/dev/null
wait_for "window.__r && window.__r.startsWith('[')" || exit 1
best=$($y -e 'JSON.stringify(window.__match)'); echo "icon match: $best"
[[ $best == '[0,0]' ]] || { echo "icon not found exactly — stopping"; exit 1 }
$y -e 'const d=document.querySelector("[role=dialog]"); d.querySelectorAll("img")[0].closest("button").click(); 1' >/dev/null; sleep 1
$y $S/q6.js >/dev/null; sleep 1
$y -e '[...document.querySelector("[role=dialog]").querySelectorAll("button")].find(b=>b.innerText.trim()==="Choose Icon").click(); 1' >/dev/null; sleep 2
for k in {1..6}; do $y $S/titles.js >/dev/null; sleep 5; $y $S/rows.js | grep -q -E '\.mp3 \||\[[A-Za-z0-9_-]{11}\]' || break; done
wait_for "[...document.querySelectorAll('li [data-part=preview]')].every(p => !/\.mp3$|\[[A-Za-z0-9_-]{11}\]/.test(p.textContent))" || exit 1
echo "$($y -e 'window.__r')"
icons=$($y -e '[...document.querySelectorAll("li [data-testid=track-icon-button] img")].length')
echo "tracks with icon: $icons/$n"
[[ $icons == $n ]] || { echo "icons missing — stopping"; exit 1 }
$y -e '[...document.querySelectorAll("button")].find(b=>b.innerText.trim()==="Create playlist").click(); 1' >/dev/null; sleep 6
$y -e 'location.href + " | " + (document.body.innerText.includes("successfully created") ? "CREATED" : "not confirmed")'
