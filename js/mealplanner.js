"use strict";
const weekId = location.pathname.split("/").pop().replace(".html", "");
let data;
let servings = 3;
const escapeHtml = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const format = item => {
  const [, name, amount, unit] = item;
  if (amount == null) return name;
  const value = amount * servings / 3;
  return (Number.isInteger(value) ? String(value) : value.toLocaleString("de-AT", {maximumFractionDigits:1})) + " " + unit + " " + name;
};
function render() {
  document.getElementById("servings").textContent = servings;
  const groups = [...new Set(data.ingredients.map(x => x[0]))];
  document.getElementById("shopping").innerHTML = groups.map(group =>
    '<div class="group"><h3>' + escapeHtml(group) + '</h3>' +
    data.ingredients.filter(x => x[0] === group).map(item =>
      '<label class="check"><input type="checkbox"><span>' + escapeHtml(format(item)) + '</span></label>'
    ).join("") + '</div>'
  ).join("");
}
function renderMeals() {
  const container = document.getElementById("meals");
  container.replaceChildren();
  for (const [day, name, tag, minutes, url, emoji, image] of data.meals) {
    const card = document.createElement(url ? "a" : "button");
    card.className = "card recipe-card recipe-card-clickable";
    if (url) {
      card.href = url;
      card.target = "_blank";
      card.rel = "noopener noreferrer";
      card.setAttribute("aria-label", name + " – Rezept öffnen");
    } else {
      card.type = "button";
      card.setAttribute("aria-label", name + " – Zubereitung anzeigen");
      card.addEventListener("click", () => window.alert("Ofenlachs mit Kartoffelpüree & Karotten\\n\\nLachs bei 180 °C ca. 15–20 Minuten garen. Kartoffeln kochen und mit Milch und Butter pürieren. Karotten weich dünsten. Mit Salz, Pfeffer und Zitrone abschmecken."));
    }
    const photo = document.createElement("div");
    photo.className = "photo";
    photo.setAttribute("role", "img");
    photo.setAttribute("aria-label", name);
    if (image && typeof image === "object" && image.src && image.source && image.license) {
      const img = document.createElement("img");
      img.src = image.src;
      img.referrerPolicy = "no-referrer";
      img.alt = name;
      img.loading = "lazy";
      img.addEventListener("error", () => {
        photo.classList.add("photo-fallback");
        photo.textContent = emoji;
      });
      photo.append(img);
    } else {
      photo.classList.add("photo-fallback");
      photo.textContent = emoji;
    }
    const body = document.createElement("div");
    body.className = "card-body";
    body.innerHTML = '<div class="eyebrow">' + escapeHtml(day) + '</div><h3>' +
      escapeHtml(name) + '</h3><p class="meta"><span class="pill">' +
      escapeHtml(tag) + '</span><span class="recipe-time">⏱ ' +
      escapeHtml(minutes) + ' Min.</span></p>';
    const note = document.createElement("span");
    note.className = url ? "recipe-link" : "note";
    note.textContent = url ? "Rezept ansehen ↗" : "Hausrezept · Zubereitung anzeigen ↗";
    body.append(note);
    if (image && typeof image === "object" && image.src && image.source && image.license) {
      const credit = document.createElement("small");
      credit.className = "photo-credit";
      credit.textContent = image.note ? image.note + " · " + image.credit : image.credit;
      body.append(credit);
    }
    card.append(photo, body);
    container.append(card);
  }
}
document.getElementById("minus").onclick = () => { servings = Math.max(2, servings - 1); if (data) render(); };
document.getElementById("plus").onclick = () => { servings = Math.min(4, servings + 1); if (data) render(); };
document.getElementById("copy").onclick = async () => {
  if (!data) return;
  const list = data.ingredients.map(format).join("\n");
  try { await navigator.clipboard.writeText(list); document.getElementById("copy").textContent = "Kopiert ✓"; }
  catch { window.prompt("Einkaufsliste kopieren:", list); }
};
document.getElementById("meals").textContent = "Rezepte werden geladen …";
fetch("../data/" + encodeURIComponent(weekId) + ".json?v=8", {cache:"no-store"})
  .then(response => { if (!response.ok) throw new Error("HTTP " + response.status); return response.json(); })
  .then(week => { data = week; renderMeals(); render(); })
  .catch(error => {
    document.getElementById("meals").textContent = "Wochenplan konnte nicht geladen werden: " + error.message;
    console.error("Rauchski Meal Planner:", error);
  });
