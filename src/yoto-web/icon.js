(async () => {
  const d = document.querySelector("[role=dialog]");
  const inp = [...d.querySelectorAll("input[type=file]")][0];
  if (!inp) { window.__r = "no file input; buttons: " + [...d.querySelectorAll("button")].map(b => b.innerText).filter(Boolean).join("|"); return; }
  window.__r = "accept=" + inp.accept;
  const blob = await (await fetch("ICONURL")).blob();
  const dt = new DataTransfer(); dt.items.add(new File([blob], "icon.png", {type: "image/png"}));
  inp.files = dt.files; inp.dispatchEvent(new Event("change", {bubbles: true}));
  window.__r += " | uploaded";
})().catch(e => window.__r = "ERR " + e);
"started"
