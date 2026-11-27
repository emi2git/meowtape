(() => { try { const d = document.querySelector("[role=dialog]");
  const cb = d.querySelector("input[type=checkbox]"); if (!cb.checked) cb.click();
  const btn = [...d.querySelectorAll("button")].find(b => b.innerText.trim() === "Choose Icon");
  return "checked=" + cb.checked + " choose disabled=" + btn.disabled + " selected=" + [...d.querySelectorAll("ul li button")].slice(0,3).map(b => b.getAttribute("aria-pressed") + "/" + b.getAttribute("data-selected") + "/" + b.className.slice(0,40)).join(" ; ");
} catch (e) { return "ERR " + e.stack; } })()
