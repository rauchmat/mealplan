"use strict";
const current = document.getElementById("current-week");
const archive = document.getElementById("week-archive");
function weekCard(week, featured) {
  const article = document.createElement("article");
  article.className = featured ? "card featured-week" : "card archive-week";
  const link = document.createElement("a");
  link.className = featured ? "weeklink featured-link" : "weeklink";
  link.href = week.url;
  const eyebrow = document.createElement("div");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = (featured ? "Aktuelle Woche · " : "") + week.id.replace("-W", " · KW ") + " · " + week.date;
  const heading = document.createElement(featured ? "h2" : "h3");
  heading.textContent = week.title;
  const description = document.createElement("p");
  description.className = "meta";
  description.textContent = week.subtitle;
  link.append(eyebrow, heading, description);
  if (featured) {
    const stats = document.createElement("div");
    stats.className = "week-stats";
    const items = [["5", "Gerichte"], ["3", "Vegetarisch/vegan"], ["30–40", "Minuten"]];
    for (const [value, label] of items) {
      const stat = document.createElement("div");
      stat.className = "week-stat";
      const number = document.createElement("strong");
      number.textContent = value;
      const caption = document.createElement("span");
      caption.textContent = label;
      stat.append(number, caption);
      stats.append(stat);
    }
    // Stats are known for week 45 only. Future weeks use their descriptive subtitle.
    if (week.id === "2026-W45") link.append(stats);
  }
  const action = document.createElement("span");
  action.className = "week-action";
  action.textContent = "Wochenplan ansehen ↗";
  link.append(action);
  article.append(link);
  return article;
}
fetch("data/weeks.json?v=7", {cache:"no-store"})
  .then(response => { if (!response.ok) throw new Error("HTTP " + response.status); return response.json(); })
  .then(weeks => {
    if (!Array.isArray(weeks) || weeks.length === 0) {
      current.textContent = "Noch kein Wochenplan vorhanden.";
      archive.textContent = "Hier wächst unsere Rezeptsammlung.";
      return;
    }
    const sorted = [...weeks].sort((a,b) => b.id.localeCompare(a.id));
    current.replaceChildren(weekCard(sorted[0], true));
    archive.replaceChildren();
    if (sorted.length === 1) {
      const message = document.createElement("p");
      message.className = "note";
      message.textContent = "Hier wächst unsere Rezeptsammlung – Woche für Woche.";
      archive.append(message);
    } else for (const week of sorted.slice(1)) archive.append(weekCard(week, false));
  })
  .catch(error => {
    current.textContent = "Wochenpläne konnten nicht geladen werden.";
    archive.textContent = "";
    console.error("Rauchski Meal Planner:", error);
  });
