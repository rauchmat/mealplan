# Rauchski Meal Planner

Familien-Wochenpläne mit Rezepten, Einkaufsliste und Bring!-Import.

Website: https://rauchmat.github.io/mealplan/

## Mit ChatGPT einen Wochenplan erstellen

Beide Familienmitglieder können mit ihrem eigenen ChatGPT-Account und verbundenem GitHub-Zugang arbeiten.

**Startprompt:**

> Arbeite mit dem GitHub-Repository rauchmat/mealplan. Lies zuerst README.md, AGENTS.md, data/settings.json und die bisherigen Wochenpläne. Erstelle fünf Abendessen für nächste Woche und zeige mir zunächst nur den Entwurf mit Rezeptlinks. Veröffentliche erst nach meiner ausdrücklichen Freigabe. Nach der Freigabe erstelle auch die Einkaufsliste und alle Bring!-Importseiten gemäß AGENTS.md.

**Bestehende Woche ändern:**

> Lies AGENTS.md im Repository rauchmat/mealplan. Ich möchte KW [Nummer] ändern: [Wunsch]. Zeige mir zuerst die Auswirkungen auf die Rezepte und Einkaufsliste und warte vor GitHub-Änderungen auf meine Freigabe.

## Grundregeln

- Montag bis Freitag, fünf Abendessen, mindestens zwei vegetarisch oder vegan.
- Drei Portionen als Standard; zwei bis vier auswählbar.
- Abwechslungsreich, alltagstauglich, möglichst wenig Einkaufsaufwand.
- Nur geprüfte Rezeptlinks; Original-Rezeptfoto mit Nutzungsrecht oder Emoji.
- Hausrezepte haben eigene HTML-Seiten.
- Gemeinsame, aggregierte Einkaufsliste und Bring!-Import für 2, 3 und 4 Portionen.
- Veröffentlichung ausschließlich nach Freigabe.

## Dateien

- `index.html`: Startseite mit aktueller Woche und Archiv
- `data/settings.json`: Einstellungen
- `data/weeks.json`: Index aller Wochen
- `data/YYYY-Www.json`: Gerichte und aggregierte Zutaten
- `weeks/YYYY-Www.html`: Wochenansicht
- `recipes/*.html`: Hausrezepte
- `bring/YYYY-Www-{2,3,4}.html`: Bring!-Import
- `AGENTS.md`: detaillierte Arbeitsanleitung für ChatGPT

Die Website wird mit GitHub Pages veröffentlicht. Nach Änderungen kann die Veröffentlichung verzögert sein.
