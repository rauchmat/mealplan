"use strict";
const weekId = location.pathname.split("/").pop().replace(".html", "");
let data;
let servings = 3;
const escapeHtml = (value) => String(value).replace(/[&<>"\x27]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","\x27":"&#39;"}[char]));
const format = (item) => {
  const [category, name, amount, unit] = item;
  if (amount === null) return name;
  const value = amount * servings / 3;
  const display = Number.isInteger(value) ? String(value) : value.toLocaleString("de-AT", {maximumFractionDigits: 1});
  return display + " " + unit + " " + name;
};
function render() {
  document.getElementById("servings").textContent = servings;
  const groups = [...new Set(data.ingredients.map(x => x[0]))];
  document.getElementById("shopping").innerHTML = groups.map(group => `
    <div class="group"><h3>${group}</h3>${data.ingredients.filter(x => x[0] === group).map((item,i) =>
      `<label class="check"><input type="checkbox"><span>${format(item)}</span></label>`).join("")}</div>`).join("");
}
document.getElementById("minus").onclick = () => { servings = Math.max(2, servings - 1); render(); };
document.getElementById("plus").onclick = () => { servings = Math.min(4, servings + 1); render(); };
document.getElementById("copy").onclick = async () => {
  const list = data.ingredients.map(format).join("\n");
  try { await navigator.clipboard.writeText(list); document.getElementById("copy").textContent = "Kopiert ✓"; }
  catch { window.prompt("Einkaufsliste kopieren:", list); }
};
fetch("../data/" + encodeURIComponent(weekId) + ".json")
  .then(response => { if (!response.ok) throw new Error("Wochenplan nicht gefunden"); return response.json(); })
  .then(week => {
    data = week;
    document.getElementById("meals").innerHTML = data.meals.map((meal) => {
      const [day, name, tag, minutes, url, emoji, image] = meal;
      const photo = image
        ? `<img src="${escapeHtml(image)}" alt="${escapeHtml(name)}" loading="lazy" decoding="async">`
        : `<span aria-hidden="true">${escapeHtml(emoji)}</span>`;
      return `
        <article class="card recipe-card">
          <div class="photo ${image ? "has-image" : "photo-fallback"}" role="img" aria-label="${escapeHtml(name)}">${photo}</div>
          <div class="card-body">
            <div class="eyebrow">${escapeHtml(day)}</div>
            <h3>${escapeHtml(name)}</h3>
            <p class="meta"><span class="pill">${escapeHtml(tag)}</span><span class="recipe-time">⏱ ${Number(minutes)} Min.</span></p>
            ${url ? `<a class="recipe-link" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Rezept ansehen ↗</a>` : `<span class="note">Hausrezept · Lachs bei 180 °C ca. 15–20 Min. garen</span>`}
          </div>
        </article>`;
    }).join("");
    render();
  })
  .catch(() => { document.getElementById("meals").textContent = "Wochenplan konnte nicht geladen werden."; });
