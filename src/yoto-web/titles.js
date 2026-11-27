(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
  const clean = s => s.replace(/\.mp3$/i, "").replace(/\s*\(edited\)\s*$/, "").replace(/\s*\[[A-Za-z0-9_-]{11}\]/g, "").replace(/\s+/g, " ").trim();
  const done = [];
  for (const f of document.querySelectorAll("li [data-testid=editable-field]")) {
    const inp = f.querySelector("input"), prev = f.querySelector("[data-part=preview]");
    const want = clean(inp.value);
    if (want === inp.value) continue;
    prev.focus(); prev.click(); await sleep(150);
    inp.focus(); set.call(inp, want); inp.dispatchEvent(new Event("input", {bubbles: true}));
    await sleep(100);
    inp.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter", bubbles: true}));
    await sleep(200);
    done.push(inp.value === want && f.querySelector("[data-part=preview]").textContent === want);
  }
  window.__r = "titles " + JSON.stringify(done);
})().catch(e => window.__r = "ERR " + e);
"started"
