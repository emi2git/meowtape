import json, os, sys, urllib.parse
card = sys.argv[1]
R = os.environ.get("MP3_DIR") or os.path.expanduser("~/Library/CloudStorage/SynologyDrive-SynologySync/mp3")
songs = sorted(f for f in os.listdir(f"{R}/Music/{card}") if f.lower().endswith(".mp3"))
u = lambda p: "http://127.0.0.1:8766/" + urllib.parse.quote(p)
cfg = {"title": card, "cover": u(f".yoto-art/{card}/cover.png"),
       "songs": [[u(f"Music/{card}/{s}"), s] for s in songs]}
js = """
(async () => {
  const cfg = %s;
  const get = async (url, name, type) => new File([await (await fetch(url)).blob()], name, {type});
  const put = (input, files) => {
    const dt = new DataTransfer(); files.forEach(f => dt.items.add(f));
    input.files = dt.files; input.dispatchEvent(new Event("change", {bubbles: true}));
  };
  window.__r = "title";
  const t = [...document.querySelectorAll('input')].find(e => e.type === 'text');
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(t, cfg.title);
  t.dispatchEvent(new Event("input", {bubbles: true}));
  window.__r = "cover";
  put(document.querySelector('input[type=file][accept*=png]'), [await get(cfg.cover, "cover.png", "image/png")]);
  window.__r = "fetching songs";
  const files = [];
  for (const [url, name] of cfg.songs) files.push(await get(url, name, "audio/mpeg"));
  put(document.querySelector('input[type=file][accept*=audio]'), files);
  window.__r = "handed " + files.length + " songs to Yoto";
})().catch(e => window.__r = "ERR at " + window.__r + ": " + e + " " + e.stack);
"started"
""" % json.dumps(cfg)
open(sys.argv[2], "w").write(js)
