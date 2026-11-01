"use strict";
const data = JSON.parse(document.getElementById("week-data").textContent);
let servings = 3;
const format = (item) => {
  const [category, name, amount, unit] = item;
  if (amount === null) return name;
  const value = amount * servings / 3;
  const display = Number.isInteger(value) ? String(value) : value.toLocaleString("de-AT", {maximumFractionDigits: 1});
  return display + " " + unit + " " + name;
};
document.getElementById("meals").innerHTML = data.meals.map(([day,name,tag,minutes,url,emoji]) => `
  <article class="card">
    <div class="photo" role="img" aria-label="Illustration: ${name}">${emoji}</div>
    <div class="card-body"><div class="eyebrow">${day}</div><h3>${name}</h3>
      <p class="meta"><span class="pill">${tag}</span> &nbsp; ⏱ ${minutes} Min.</p>
      ${url ? `<a href="${url}" target="_blank" rel="noopener">Zum Rezept ↗</a>` : "<span class='note'>Hausrezept · 180 °C, 15–20 Min. Lachs</span>"}
    </div>
  </article>`).join("");
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
render();