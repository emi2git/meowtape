#!/bin/zsh
# addto.sh <card code> <card folder> <file>...  — add songs to a saved Yoto playlist,
# give them the card's icon (copied from its first track) and clean titles, then Save
S=${0:A:h}; y=$S/yjs; code=$1; card=$2; shift 2
$y -e "location.href='https://my.yotoplay.com/cards/$code'; 1" >/dev/null; sleep 7
before=$($y -e 'document.querySelectorAll("li [data-testid=editable-field]").length'); want=$(( before + $# ))
python3 - "$card" "$@" > $S/addto.js <<'PY'
import json, sys, urllib.parse
card, files = sys.argv[1], sys.argv[2:]
urls = [["http://127.0.0.1:8766/" + urllib.parse.quote(f"Music/{card}/{f}"), f] for f in files]
print("""(async () => {
  const files = [];
  for (const [u, n] of %s) files.push(new File([await (await fetch(u)).blob()], n, {type: "audio/mpeg"}));
  const inp = document.querySelector('input[type=file][accept*=audio]');
  const dt = new DataTransfer(); files.forEach(f => dt.items.add(f));
  inp.files = dt.files; inp.dispatchEvent(new Event("change", {bubbles: true}));
  window.__r = "added " + files.length;
})().catch(e => window.__r = "ERR " + e); "started" """ % json.dumps(urls))
PY
$y -e 'window.__r=""; 1' >/dev/null; $y $S/addto.js >/dev/null
for i in {1..120}; do n=$($y -e '[...document.querySelectorAll("li")].filter(li=>li.querySelector("[data-testid=editable-field]") && / MB/.test(li.innerText)).length'); [[ $n == $want ]] && break; sleep 2; done
echo "$card: $n/$want tracks ($($y -e 'window.__r'))"; [[ $n == $want ]] || exit 1
sleep 2
cat > $S/icons.js <<'JS'
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const rows = () => [...document.querySelectorAll("li")].filter(li => li.querySelector("[data-testid=editable-field]"));
  const src = rows()[0].querySelector("[data-testid=track-icon-button] img").src;
  let n = 0;
  for (const row of rows().filter(li => !li.querySelector("[data-testid=track-icon-button] img"))) {
    row.querySelector("[data-testid=track-icon-button]").click(); await sleep(1500);
    const d = document.querySelector("[role=dialog]");
    d.querySelector("#tab-my-icons").click(); await sleep(1500);
    const img = [...d.querySelectorAll("img")].find(i => i.src === src);
    if (!img) { window.__r = "icon not in My Icons"; return; }
    img.closest("button").click(); await sleep(500);
    [...d.querySelectorAll("button")].find(b => b.innerText.trim() === "Choose Icon").click(); await sleep(1200);
    n++;
  }
  window.__r = "icons set " + n;
})().catch(e => window.__r = "ERR " + e); "started"
JS
$y -e 'window.__r=""; 1' >/dev/null; $y $S/icons.js >/dev/null
for i in {1..40}; do r=$($y -e 'window.__r'); [[ -n $r ]] && break; sleep 2; done; echo "$r"
for k in {1..6}; do $y $S/titles.js >/dev/null; sleep 5; raw=$($y -e '[...document.querySelectorAll("li [data-part=preview]")].filter(p=>/\.mp3$|\[[A-Za-z0-9_-]{11}\]|\(edited\)/.test(p.textContent)).length'); [[ $raw == 0 ]] && break; done
ic=$($y -e 'document.querySelectorAll("li [data-testid=track-icon-button] img").length'); echo "icons $ic/$want, raw titles $raw"
[[ $ic == $want && $raw == 0 ]] || { echo "not saving"; exit 1 }
$y -e '[...document.querySelectorAll("button")].find(b=>b.innerText.trim()==="Save").click(); 1' >/dev/null; sleep 6
$y -e 'setTimeout(()=>location.reload(),50); 1' >/dev/null; sleep 9
$y -e '[...document.querySelectorAll("input")].find(e=>e.type==="text").value + " after reload: tracks " + document.querySelectorAll("li [data-testid=editable-field]").length + ", icons " + document.querySelectorAll("li [data-testid=track-icon-button] img").length + "\n" + [...document.querySelectorAll("li [data-part=preview]")].slice(-'$#').map(p=>"  + "+p.textContent).join("\n")'
