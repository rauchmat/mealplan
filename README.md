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

## Rezeptkatalog und Import

- `data/recipes.json`: persistenter, versionierter Rezeptkatalog mit Quellen, Prüfstatus und manuellen Ergänzungen.
- `data/preferences.json`: bestätigte Vorlieben und belegte, noch unbestätigte Geschmackssignale. Leere Werte bedeuten unbekannt.
- `tools/recipe_import/`: Python-Importer für bereinigte JSON-/CSV-Kataloge und öffentliche Rezeptseiten.
- [Importanleitung und Datenmodell](docs/recipe-import.md): Eingabeformate, inkrementelle Prüfung, Datenschutz und Grenzen bei Instagram/TikTok.

```sh
python3.12 -m venv work/venv
work/venv/bin/python -m pip install -r requirements-test.txt
work/venv/bin/python -m tools.recipe_import --validate
work/venv/bin/python -m tools.recipe_import --input private/recipes.json --dry-run
work/venv/bin/python -m tools.recipe_import --input private/recipes.json
work/venv/bin/python -m pytest -q
```

`--dry-run` ruft Links ab und schreibt einen lokalen Bericht, verändert aber den Katalog nicht. `--offline` nimmt nur Eingaben auf. Wiederholte Importe respektieren Prüfintervalle und manuelle Ergänzungen. Der Importer erstellt oder veröffentlicht keine Wochenpläne und führt keine Git-Schreibvorgänge aus.

Der WhatsApp-Rohchat bleibt außerhalb des Repositorys. Nur geprüfte, bereinigte Eingabekataloge verwenden. `private/`, `imports/`, `reports/` und `work/` sind ignoriert; bereits getrackte Dateien schützt `.gitignore` nicht. Vor einem Commit den Diff auf personenbezogene Inhalte prüfen.

Die angekündigten 201 Links und 33 zusätzlichen Gerichtnamen liegen diesem Stand noch nicht als Importdateien vor. Der Katalog startet mit dem vorhandenen Hausrezept, aus dessen lokaler HTML-Datei extrahiert. Eine vollständige Live-Linkprüfung der Sammlung ist daher noch offen.
