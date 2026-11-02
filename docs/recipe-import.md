# Rezeptimport

Der Importer ergänzt die statische GitHub-Pages-Anwendung um einen lokalen Python-Arbeitsschritt. Wochenpläne entstehen weiterhin über den in `AGENTS.md` beschriebenen Entwurfs- und Freigabeprozess. Es gibt keinen neuen Server, Scheduler oder automatischen Bring!-Aufruf.

## Installation und Eingaben

Python 3.12 verwenden. Befehle aus dem Repository-Stamm ausführen:

```sh
python3.12 -m venv work/venv
work/venv/bin/python -m pip install -r requirements-test.txt
```

Für reine Nutzung genügt `requirements-import.txt`. Direkte Abhängigkeiten sind versioniert; transitive Abhängigkeiten werden vom Paketmanager aufgelöst.

Der originale WhatsApp-Export gehört außerhalb des Checkout-Verzeichnisses aufbewahrt. Dieses Werkzeug verarbeitet ausschließlich bereits bereinigte JSON-/CSV-Dateien. Die tatsächlichen Mampfi-Importdateien müssen vor dem ersten Import auf ihre Struktur und personenbezogene Inhalte geprüft werden; ein unbekanntes Format wird nicht automatisch geraten.

Unterstützte JSON-Formate:

```json
{
  "links": [
    {"url": "https://example.org/rezept", "title": "Optionaler Importtitel"},
    "https://www.instagram.com/reel/BEITRAG/"
  ],
  "dishes": ["Gericht ohne Rezeptlink"]
}
```

Alternativ eine Liste von URLs/Gerichtnamen/Objekten oder `{"recipes": [...]}`. Pro Objekt sind ausschließlich `url`/`link` und `title`/`name` erlaubt. CSV verwendet dieselben Spaltennamen und Komma, Semikolon oder Tab als Trennzeichen; Texte mit Trennzeichen müssen CSV-konform quotiert sein. UTF-8 mit optionalem BOM wird unterstützt. Zutaten und Chatmetadaten werden nicht aus beliebigen Eingabespalten übernommen.

Dateien unter `private/` oder `imports/` ablegen, zum Beispiel `private/mampfi.json`. Beide Verzeichnisse sind ignoriert. Maximal 5 MB Eingabedaten; Titel maximal 500 Zeichen und ohne Zeilenumbrüche. Unzulässige Felder brechen den Import ab. Zurückgewiesene Zeilen verhindern einen Katalog-Schreibvorgang; der Bericht nennt Zeilennummer und Fehlercode ohne den problematischen URL-Text. Vorherige Katalogdaten bleiben erhalten.

## Aufrufe

```sh
# Eingaben prüfen, Links abrufen, nur einen lokalen Bericht schreiben
work/venv/bin/python -m tools.recipe_import --input private/mampfi.json --dry-run

# Linkprüfung und persistenter Import
work/venv/bin/python -m tools.recipe_import --input private/mampfi.json

# Nur Link-/Namenseinträge aufnehmen oder nach manueller Korrektur Qualität neu berechnen
work/venv/bin/python -m tools.recipe_import --input private/mampfi.json --offline
work/venv/bin/python -m tools.recipe_import --offline

# Bestehenden Katalog inkrementell prüfen, höchstens 10 Einträge
work/venv/bin/python -m tools.recipe_import --limit 10

# Auch noch nicht fällige Einträge erneut prüfen
work/venv/bin/python -m tools.recipe_import --force --limit 5

# Schema, eindeutige IDs/URLs und Profilbelege ohne Netzwerk prüfen
work/venv/bin/python -m tools.recipe_import --validate
```

`--catalog`, `--preferences` und `--report` erlauben alternative Pfade. Standardbericht: `reports/recipe-import.json`. `--dry-run` führt HTTP-Abfragen aus; mit `--offline` kombinieren, wenn keinerlei Netzwerkverkehr gewünscht ist. `--limit` begrenzt geprüfte Katalogeinträge, nicht HTTP-Anfragen: robots.txt, Weiterleitungen, Wiederholungen und ein verlinktes Rezept können zusätzliche Anfragen verursachen. Neue Eingaben werden auch dann aufgenommen, wenn das Abruflimit erreicht ist, bleiben aber ausdrücklich ungeprüft.

Exitcode 0 bedeutet, dass der Lauf technisch abgeschlossen wurde, nicht dass alle Quellen gelesen werden konnten. Abruffehler stehen pro Eintrag im Bericht und Katalog. Exitcode 2 bedeutet einen Eingabe-, Validierungs- oder Schreibfehler. Keine automatische Git-Operation und keine Veröffentlichung.

## Datenmodell, Version 1

`data/recipes.json` enthält `schema_version: 1` und `recipes`. IDs sind stabil und werden aus der ersten bereinigten URL beziehungsweise dem normalisierten Gerichtnamen erzeugt. Bei einer Zusammenführung bleibt eine der vorhandenen IDs bestehen. Reine Namenseinträge werden nicht automatisch mit ähnlich benannten Linkeinträgen verschmolzen.

Jeder Datensatz enthält:

- `urls`: bereinigte Quell-URLs und bestätigte Weiterleitungs-/Rezeptlink-Aliasse; `platform`: ursprünglicher Quelltyp.
- `data`: `title`, `ingredients` (Originaltexte), `servings` (eindeutige Personen-/Portionszahl), `yield_text`, `prep_minutes`, `cook_minutes`, `total_minutes`, `category`, `tags`, `instructions`.
- `provenance`: URL und Methode je automatisch belegtem Feld, etwa `jsonld`, `microdata`, `rdfa`, `house_html`, `public_caption` oder `import_label`. `import_label` bezeichnet einen Eingabetitel, keine Bestätigung durch die Website.
- `manual`: explizite menschliche Korrekturen derselben Datenfelder. Sie überlagern `data`, ohne die extrahierten Ausgangswerte zu löschen. Auch explizites `null`/`[]` ist als Korrektur möglich. Diese Felder werden beim Import nicht verändert.
- `experience`: `unrated`, `tried`, `liked` oder `disliked`, unabhängig vom technischen Abrufstatus.
- `reviewed_for_planning`: menschliche Prüfung der Zutaten, Mengen, Portionen, Kategorie und Rezeptzuordnung. Anfangs `false`; automatisch geänderte Daten setzen sie zurück.
- `check`: Abrufstatus, UTC-Zeitpunkte `last_attempt`, `last_success`, `next_attempt`, HTTP-Status, stabiler Fehlercode sowie ETag/Last-Modified mit zugehöriger `validator_url`.
- `quality`: abgeleitete Vollständigkeit, fehlende Felder, Hinweise und `planning_ready`.

`null`/`[]` mit Eintrag in `quality.missing` bedeutet unbekannt. Es werden keine Mengen aus Zutaten geraten, keine Portionsbereiche aufgelöst und keine Gesamtzeiten durch Addition vermeintlich aufeinanderfolgender Schritte erfunden. `12 Kekse` ist keine Personenanzahl; `2–4 Portionen` bleibt mehrdeutig. Die Kategorie wird aus der Quelle übernommen, nicht pauschal aus Zutaten erraten. Diät- und Küchenangaben werden als Quell-Tags bewahrt.

`complete` verlangt Titel, Zutaten, eindeutige Portionen, Zubereitung, Gesamtzeit und Kategorie. `partial` enthält zumindest Zutaten oder Schritte; `name_only` ist ein nicht ausreichend beschriebenes Gericht oder ein reiner Metadateneintrag. Ein `complete`-Rezept braucht zusätzlich eine menschliche Prüfung, akzeptablen Abrufstatus und darf nicht abgelehnt sein, bevor `planning_ready` wahr wird. Auch dann müssen vor dem Wocheneinkauf die Mengen auf drei Portionen nachvollziehbar skaliert und für Bring! aggregiert werden. Dafür werden keine Wochenzutaten automatisch umgeschrieben.

Ändern sich zuvor belegte Werte, erscheint `conflicting_fields`. Bei später fehlenden Daten bleiben die letzten erfolgreichen Werte erhalten; `source_now_incomplete` und eine zurückgesetzte Prüfung verhindern eine unbemerkte Übernahme. Unterschiedliche manuelle Korrekturen oder Bewertungen verhindern eine automatische Weiterleitungs-Zusammenführung (`redirect_merge_conflict`). Im Bericht und per Feldherkunft lässt sich die Zuordnung prüfen. Konflikte nach menschlicher Klärung beheben und den Katalog offline neu berechnen lassen.

Die Startsammlung enthält nur das aus dem vorhandenen lokalen Hausrezept gelesene Rezept. `check.status: local_source` ist ausdrücklich kein Live-Abruf. Das Rezept wird weder als Favorit noch als bereits gekocht vorausgesetzt. Die Mampfi-Sammlung ist erst nach Bereitstellung ihrer bereinigten Kataloge importierbar.

## Extraktion und Plattformgrenzen

1. Recipe-JSON-LD, auch Arrays, `@graph`, interne Referenzen und verschachtelte Schritte; keine entfernten JSON-LD-Kontexte laden.
2. Recipe-Microdata/RDFa mit normalisierten Schema-Schlüsseln und internen Referenzen.
3. Gezielt die vorhandene Hausrezept-HTML-Struktur. Eigene Bring!-Seiten werden als Wocheneinkaufsliste ausgeschlossen.
4. Allgemeine Seiten liefern höchstens ihren Seitentitel; Zutaten werden nicht aus beliebigen Textabsätzen geraten.

Instagram/TikTok verwenden dieselbe strukturierte Extraktion und zusätzlich öffentlich gelieferte Beschreibungen bzw. eingebettete `desc`-/`caption`-Texte. Nur eindeutig bezeichnete Abschnitte `Zutaten:`/`Ingredients:` und `Zubereitung:`/`Instructions:`/`Preparation:` mit Zeilenumbrüchen werden übernommen. Ganze Captions und Videodateien werden nicht gespeichert. Mehrere unterschiedliche Captions werden als mehrdeutig gekennzeichnet. Ein eindeutig enthaltener externer Link kann genau eine Ebene tief als Rezeptquelle geprüft werden; bei mehreren Links wird keine Auswahl geraten.

Private Beiträge, Login-Seiten, Captchas, reine Videos, Bilder mit Zutaten oder JavaScript-only-Inhalte können nicht vollständig automatisch gelesen werden. Es gibt keinen Login, Cookie-Import, Browser-Fallback, Video-Download oder Umgehung von Zugriffsbeschränkungen. Nicht jeder HTTP-200-Inhalt ist ein Rezept; erkannte Anmeldeseiten erhalten `blocked`. Plattformtitel oder werbliche Captions sind kein Beleg für Zutaten. Manuelle, nachvollziehbare Ergänzungen sind der vorgesehene Weg für solche Quellen.

## Abrufstrategie und inkrementelle Verarbeitung

- Ausschließlich öffentliche HTTP(S)-Ziele auf Standardports; keine URL-Zugangsdaten. Private/lokale IPs und DNS-Ziele werden vor jedem Hop und Retry abgelehnt. TLS-Prüfung und vorhandene Proxy-/Netzwerkregeln bleiben aktiv. Eine zusätzliche Egress-Sperre für private Ziele bleibt bei Betrieb hinter fremd auflösenden Proxys sinnvoll, da lokale DNS-Prüfung deren DNS-Auflösung nicht fixieren kann.
- Sequentielle Abrufe, mindestens zwei Sekunden Pause je Host; robots.txt, Crawl-delay und Request-rate beachten. Mehr als 60 Sekunden nötige Wartezeit wird als nächster Prüftermin gespeichert, statt den Prozess lange schlafen zu lassen.
- Maximal fünf Weiterleitungen; maximal 2 MB entpacktes HTML, 512 KB robots.txt; 20 Sekunden Netzwerk-Timeout je Phase. robots.txt-Fehler werden konservativ behandelt. 404/410 für robots.txt erlaubt die Prüfung, 401/403 verbietet sie, temporäre Fehler verschieben sie.
- Höchstens drei Versuche bei Rezept-Netzwerkfehlern/5xx mit wachsendem Abstand. HTTP 429 respektiert `Retry-After` (Sekunden oder HTTP-Datum) und sperrt weitere Anfragen zum Host für diese Laufzeit. robots.txt-Netzwerkfehler werden im nächsten Lauf erneut geprüft.
- Typische Status: `ok`, `blocked`, `not_found`, `rate_limited`, `network_error`, `robots_denied`, `robots_unavailable`, `unsafe_url`, `unsupported_content`. Unvollständigkeit steht getrennt in `quality`.
- Vollständige erfolgreiche Einträge werden nach 30 Tagen, andere standardmäßig nach sieben Tagen erneut geprüft; temporäre Fehler nach einer Stunde beziehungsweise der Servervorgabe. ETag/Last-Modified gelten nur für exakt dieselbe primäre URL. `--force` übergeht Fälligkeit, aber keine Host-Sperre oder robots.txt-Regel.
- Wiederholte Eingaben erzeugen keine neuen URL-Dubletten. Nur bekannte Trackingparameter und Fragmente werden entfernt; funktionale Queryparameter bleiben erhalten. Offensichtlich sensible Queryparameter führen zur Zurückweisung. Instagram-Beiträge werden anhand des Beitragspfads normalisiert, TikTok-Videolinks ohne Sharingparameter gespeichert.
- Ähnliche Titel und gleiche Zutatenlisten ab drei Positionen erzeugen nur Dublettenkandidaten. Bestätigte Weiterleitungsziele bzw. eindeutige verlinkte Rezeptseiten werden zusammengeführt, sofern manuelle Angaben nicht widersprechen.
- Schreiben erfolgt nach Validierung über temporäre Datei und atomaren Austausch; Lockdatei und Inhaltsvergleich erkennen konkurrierende Importer beziehungsweise zwischenzeitliche Änderungen. Gegen externe Editoren bleibt zwischen finalem Vergleich und Dateiaustausch ein kleines Zeitfenster: bei paralleler Familienarbeit vor einem Commit zusätzlich den aktuellen GitHub-Stand vergleichen. Nach einem harten Prozessabbruch eine verbliebene `.json.lock` erst nach Prüfung entfernen.

Es wird nur die letzte strukturierte Extraktion gespeichert, kein HTML-Archiv. Ein fehlgeschlagener Abruf entfernt keine erfolgreich gelesenen Rezeptdaten oder manuellen Korrekturen.

## Geschmacksprofil und Planung

`data/preferences.json` enthält:

- `confirmed`: ausdrücklich bestätigte Zutatenvorlieben, Abneigungen, Küchen, Ernährungsrestriktionen und optionales Zeitlimit. Leere Listen/`null` bedeuten nicht erhoben.
- `inferred`: unbestätigte Signale mit `signal`, belegenden `recipe_ids` und `confirmed: false`. Die erste Version erzeugt daraus keine automatischen Ernährungsverbote und befüllt sie ohne Sammlung nicht mit Vermutungen.
- `planning`: optionale Zielzahlen für bekannte/neue Gerichte und Wiederholungspause. Sind beide Zielzahlen gesetzt, müssen sie zusammen fünf ergeben. Ohne bestätigte Vorgabe bleiben sie `null`.

Planungsassistenten lesen Profil und Katalog gemäß `AGENTS.md`. Neue Rezepte können anhand bestätigter Vorlieben gesucht und als unbewertet ergänzt werden. Das Profil ersetzt keine Einstellungen: Portionszahlen und Mindestanzahl vegetarischer Gerichte bleiben in `data/settings.json`. Es werden keine vermeintlichen Vorlieben aus der Pilotwoche als persönliche Fakten gespeichert.

## Datenschutz und Veröffentlichung

Keine Rohchats, Teilnehmerdaten, Nachrichten oder Chatzeitstempel in Eingaben, Rezeptdaten oder öffentliche Berichte übernehmen. Ignorierte Verzeichnisse sind kein Schutz für bereits getrackte Dateien oder Dateien an anderen Orten. Vor Git-Schreibvorgängen den Diff einschließlich Quell-URLs, Titeln und extrahierten Texten kontrollieren. Seltene persönliche Angaben in URL-Pfaden oder Rezepttexten kann ein allgemeiner Parser nicht zuverlässig erkennen; die bereinigten Kataloge und das Ergebnis brauchen deshalb eine menschliche Sichtprüfung.

Gespeichert werden Rezeptfakten und Quellen, keine Bilder, Videos oder ganzen Social-Beiträge. Öffentliche Erreichbarkeit bedeutet keine pauschale Erlaubnis zur Wiederveröffentlichung geschützter Texte/Fotos. Bei unklaren Rechten nur erlaubte Fakten/Links übernehmen und längere Anleitungen entsprechend kuratieren. Die vorhandene Regel für Originalfotos mit zulässiger Nutzung bleibt bestehen.

## Tests und bekannte Grenzen

```sh
work/venv/bin/python -m pytest -q
work/venv/bin/python -m tools.recipe_import --validate
```

Tests verwenden synthetische Fixtures und simuliertes HTTP. Sie prüfen Extraktion, Mehrdeutigkeit, Zugriffssperren, SSRF-Ziele, Rate-Limits, Wiederholungen, inkrementelle Aktualisierung, Herkunft, manuelle Korrekturen, atomare Speicherung und CLI-Verhalten. Regressionstests prüfen die existierenden 2/3/4-Portionen-Bring!-Seiten einschließlich sichtbarer Zutaten, JSON-LD, Skalierung, Widget und Deeplink sowie die Wochenstruktur.

Die CI führt diese Offline-Tests aus und schreibt keine Kataloge oder Wochen. Ein echter Import in die Bring!-App und aktuelle Plattform-Erreichbarkeit sind damit nicht nachgewiesen. Für die vollständige Mampfi-Prüfung fehlen noch die bereinigten Eingabedateien; im eingeschränkten Ausführungsnetz müssen die konkreten Rezept- und Social-Domains erreichbar sein. Ein Netzwerkfehler der Umgebung darf nicht als gelöschtes Rezept gewertet werden.
