(async () => {
  const px = async blob => { const b = await createImageBitmap(blob); const c = new OffscreenCanvas(16, 16); const g = c.getContext("2d"); g.imageSmoothingEnabled = false; g.drawImage(b, 0, 0, 16, 16); return g.getImageData(0, 0, 16, 16).data; };
  const mine = await px(await (await fetch("ICONURL")).blob());
  const imgs = [...document.querySelector("[role=dialog]").querySelectorAll("img")];
  const out = [];
  for (let i = 0; i < imgs.length; i++) {
    try { const d = await px(await (await fetch(imgs[i].src)).blob()); let diff = 0; for (let k = 0; k < d.length; k++) diff += Math.abs(d[k] - mine[k]); out.push([i, diff]); }
    catch (e) { out.push([i, "E:" + e.message.slice(0, 30)]); }
  }
  out.sort((a, b) => (typeof a[1] === "number" ? a[1] : 1e12) - (typeof b[1] === "number" ? b[1] : 1e12));
  window.__match = out[0]; window.__r = JSON.stringify(out.slice(0, 4));
})().catch(e => window.__r = "ERR " + e);
"started"
