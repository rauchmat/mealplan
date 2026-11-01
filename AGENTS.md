# Rauchski Meal Planner — AI-Arbeitsanleitung

Diese Anweisungen gelten für ChatGPT-Assistenten, die Wochenpläne im Repository `rauchmat/mealplan` erstellen oder verändern. Antworte auf Deutsch.

## Ablauf und Freigabe

1. Lies zuerst `README.md`, `data/settings.json`, `data/weeks.json`, die letzte Wochen-JSON und die vorhandenen HTML-/JS-Vorlagen direkt aus GitHub.
2. Zeige zunächst fünf Rezeptvorschläge mit Links, Dauer und Kategorie. Besprich Änderungen mit dem Nutzer.
3. Veröffentliche **nur nach ausdrücklicher Freigabe**. Ein Entwurfsauftrag ist keine Freigabe.
4. Prüfe vor jedem GitHub-Schreibvorgang den aktuellen Dateiinhalt und SHA. Andere Familienmitglieder können parallel arbeiten.
5. Ändere ausschließlich die gewünschte Woche und deren abhängige Dateien. Erhalte bestehende Wochen und die funktionierende Bring!-Integration.
6. Nach Veröffentlichung betroffene URLs nennen; GitHub Pages kann verzögert aktualisieren.

## Rezeptplanung

- Genau fünf Abendessen, Montag bis Freitag, richtige ISO-Kalenderwoche und Datumsangaben.
- Mindestens zwei vegetarisch/vegan; internationale Abwechslung, saisonale und alltagstaugliche Gerichte, moderater Einkaufsaufwand.
- Standard drei Portionen je Gericht, auswählbar zwei bis vier. `data/settings.json` ist maßgeblich.
- Vorherige Wochen auf kürzlich wiederholte Gerichte prüfen.
- Externe Rezeptlinks müssen zum konkreten Gericht passen. Keine erfundenen URLs.
- Ausschließlich echtes Original-Rezeptfoto mit zulässiger Nutzung, sonst Emoji. Keine Ersatz- oder KI-Food-Fotos.
- Hausrezepte erhalten eigene HTML-Seiten in `recipes/`, mit Zutaten und Zubereitung; keine JavaScript-Alerts.

## Datenmodell

Für jede Woche eine Datei `data/YYYY-Www.json` nach `data/2026-W45.json` erstellen:

- `week`: z. B. `2026-W45`
- `date`: lesbarer Datumsbereich
- `quote`: kurzer Wochenspruch
- `meals`: fünf Arrays mit `[Tag, Name, Kategorie, Minuten, URL, Emoji, optionales Bildobjekt]`
- `ingredients`: aggregierte Einkaufsliste als Arrays `[Kategorie, Zutat, Menge, Einheit]`

Externe Rezept-URLs sind absolut (HTTPS). Eigene Rezepte aus `weeks/` relativ als `../recipes/datei.html` verlinken.

**Wichtig:** Die Zutatenliste enthält die Gesamtmengen für **alle fünf Gerichte bei drei Portionen pro Gericht**. Gleiche Zutaten zusammenfassen, Einheiten vereinheitlichen, Mengen anhand der konkreten Rezepte nachvollziehen. Die JS-Anzeige skaliert mit Faktor `servings / 3`. `null` bedeutet Menge nicht angegeben. Aktuell gibt es keine Zutatenlisten pro Einzelrezept; Vollständigkeit daher besonders prüfen.

## Veröffentlichung einer neuen Woche

1. `data/YYYY-Www.json` mit fünf Gerichten und vollständiger Einkaufsliste erstellen.
2. `weeks/YYYY-Www.html` auf Grundlage von `weeks/2026-W45.html` erstellen; alle KW-Angaben, Titel, Texte, Links, Social-Metadaten und Script-Pfade anpassen.
3. `data/weeks.json` um einen Eintrag mit `id`, `title`, `date`, `subtitle`, `url` ergänzen. Alte Einträge erhalten. Die Startseite sortiert nach Wochen-ID.
4. Gegebenenfalls eigene `recipes/*.html` erstellen.
5. Drei Bring!-Importseiten `bring/YYYY-Www-2.html`, `-3.html`, `-4.html` nach den funktionierenden Vorlagen der KW45 erstellen.
6. Links, Mengen, Portionsumschaltung, Einkaufsliste und Bring!-Seiten prüfen.

## Bring!-Import — unbedingt erhalten

Die Pilotwoche verwendet öffentlich erreichbare HTML-Seiten mit `schema.org/Recipe`-JSON-LD. Entscheidend sind `recipeIngredient` (gesamte skalierte Wochenliste), `recipeYield`, `name` und `url`.

Behalte die bestehende Kombination aus Bring!-Widget-Script `https://platform.getbring.com/widgets/import.js`, Widget-Platzhalter und eigenem Deeplink auf `https://api.getbring.com/rest/bringrecipes/deeplink` bei. **Die Familie hat die Entfernung des Widgets ausdrücklich rückgängig machen lassen.** Beide Importmöglichkeiten nicht eigenmächtig entfernen.

Die Wochenseite verlinkt mit `id="bring"` auf die Importseite der ausgewählten Portionszahl; `js/mealplanner.js` aktualisiert die URL. Alle drei Seiten müssen existieren. Zutatenwerte für zwei, drei und vier Portionen mit Faktoren 2/3, 1 und 4/3 aus derselben Wochenliste ableiten. Sichtbare Zutatenliste und JSON-LD müssen übereinstimmen.

## Branding und Design

- Mobilfreundliches, schlichtes Design; vorhandenes `css/style.css` wiederverwenden.
- Auf allen Seiten voller Schriftzug **Rauchski Meal Planner** und Ruby-Logo `assets/ruby-minimal.svg`, relative Pfade beachten; 72 px Desktop, 58 px mobil.
- Auf jeder Seite **identischer Footer** wie in `index.html`: „Est. 2026 · Rauchski · Mit Ruby im Herzen gekocht.“
- Startseitenüberschrift: **„Was gibt's zum Essen?“**; jede Woche hat einen individuellen Titel.
- Social-Metadaten pro Seite setzen; Vorschau-Bild `https://rauchmat.github.io/mealplan/assets/ruby-share.png` verwenden, sofern veröffentlicht.
- Eigene Rezepte als klickbare Karten auf eigene HTML-Seiten führen.
- Vorhandene Inhalte nicht ohne Auftrag umgestalten.

## Abschlusscheck

- Fünf Gerichte, mindestens zwei vegetarisch/vegan, korrekte Kalenderwoche.
- Alle Rezeptlinks geprüft; eigene Rezeptseiten vorhanden.
- Einkaufsliste vollständig und aggregiert; Mengen plausibel.
- Bring!-Importseiten für 2/3/4 Portionen konsistent, inklusive Widget und Deeplink.
- Neuer Indexeintrag vorhanden; Header/Footer/Logo konsistent.
- Keine kaputten Pfade; keine unbeabsichtigten Änderungen an älteren Wochen.
- Veröffentlichung nur nach Freigabe. Kein ungetestetes Ergebnis als erfolgreich bestätigen.

## Bekannte Einschränkungen

Neue Wochen erfordern derzeit mehrere manuelle Dateiänderungen. `js/index.js` zeigt spezielle Statistik-Kacheln nur für KW45. Ein echter Bring!-App-End-to-End-Test ist nicht automatisiert. GitHub-Pages-Deployment und Social-Preview-Caches können verzögert sein.
