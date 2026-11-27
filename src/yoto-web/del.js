(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const rows = [...document.querySelectorAll("li")].filter(li => li.querySelector("[data-testid=editable-field]"));
  const row = rows.find(li => li.querySelector("[data-part=preview]").textContent.startsWith(TITLE));
  if (!row) { window.__r = "no such track"; return; }
  const trig = row.querySelector("[data-part=trigger]");
  trig.focus();
  trig.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter", bubbles: true}));
  await sleep(700);
  const content = row.querySelector("[data-part=content]");
  window.__r = "menu " + content.dataset.state;
  if (content.dataset.state !== "open") return;
  const del = [...content.querySelectorAll("[role=menuitem]")].find(i => i.dataset.value === "Delete");
  content.focus();
  for (const i of content.querySelectorAll("[role=menuitem]")) { if (i === del) break; content.dispatchEvent(new KeyboardEvent("keydown", {key: "ArrowDown", bubbles: true})); await sleep(80); }
  content.dispatchEvent(new KeyboardEvent("keydown", {key: "ArrowDown", bubbles: true})); await sleep(80);
  content.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter", bubbles: true})); await sleep(800);
  window.__r += " | rows now " + [...document.querySelectorAll("li")].filter(li => li.querySelector("[data-testid=editable-field]")).length;
})().catch(e => window.__r = "ERR " + e); "started"
