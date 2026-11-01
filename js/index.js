"use strict";
const list = document.getElementById("week-list");
fetch("data/weeks.json")
  .then(response => { if (!response.ok) throw new Error("Liste nicht verfügbar"); return response.json(); })
  .then(weeks => {
    list.replaceChildren();
    for (const week of weeks.slice().reverse()) {
      const article = document.createElement("article");
      article.className = "card";
      const link = document.createElement("a");
      link.className = "weeklink";
      link.href = week.url;
      const eyebrow = document.createElement("div");
      eyebrow.className = "eyebrow";
      eyebrow.textContent = week.id.replace("-", " · ") + " · " + week.date;
      const heading = document.createElement("h2");
      heading.textContent = week.title;
      const description = document.createElement("p");
      description.className = "meta";
      description.textContent = week.subtitle;
      const action = document.createElement("strong");
      action.textContent = "Wochenplan ansehen ↗";
      link.append(eyebrow, heading, description, action);
      article.append(link);
      list.append(article);
    }
  })
  .catch(() => { list.textContent = "Wochenpläne konnten nicht geladen werden."; });
