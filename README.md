# Studio-Auslastung – Monitor & Statistik

Fragt alle 5 Minuten die Live-Auslastung deines fit+ Studios ab, speichert jeden Wert und zeigt dir daraus ein Dashboard: echte Stoßzeiten, beste Trainingszeiten, Heatmap Wochentag × Uhrzeit, Tagesverlauf je Wochentag, Vergleich „heute vs. normal“.

Alles läuft kostenlos auf GitHub – kein Server, kein PC, der durchlaufen muss.

```
GitHub Actions (alle 5 Min)  ──►  fragt fit+ Schnittstelle ab
          │
          ▼
Branch "data": data/2026-10.csv, data/2026-11.csv …
          │
          ▼
GitHub Pages: docs/index.html  ──►  dein Dashboard (Handy & PC)
```

---

## Schritt 1 – Die Adresse der Auslastung aus der App herausfinden (einmalig, ~15 Min.)

fit+ zeigt die Auslastung nur in der App, nicht auf der Website. Du musst einmal mitschneiden, welche Adresse die App dafür aufruft.

### Mit iPhone (am einfachsten)
1. App **Proxyman** (oder „HTTP Catcher“) aus dem App Store installieren.
2. In der App den Anweisungen folgen: VPN-Profil + Zertifikat installieren und unter
   *Einstellungen → Allgemein → Info → Zertifikatsvertrauenseinstellungen* das Zertifikat aktivieren.
3. Mitschnitt starten, dann die **fit+ App** öffnen und die Seite mit der Auslastung anzeigen.
4. Zurück zu Proxyman: Suche die Anfrage, deren Antwort die Prozentzahl enthält
   (Suchbegriffe: `utilization`, `auslastung`, `occupancy`, `checkin`, `capacity`, `percentage`).
5. Die Anfrage „als cURL kopieren“ und dir zusätzlich die **Antwort** kopieren.
6. Danach VPN-Profil in Proxyman wieder ausschalten.

### Mit Android
Android-Apps vertrauen normalen Mitschnitt-Zertifikaten seit Android 7 nicht mehr. Möglich ist es mit
**HTTP Toolkit** (httptoolkit.com) am PC + einem Android-Emulator aus Android Studio (Image *ohne* „Google Play“).
Wenn ein iPhone in der Nähe ist, geht's dort deutlich schneller.

### Prüfen: Läuft das Token ab?
Schau in der kopierten Anfrage nach einem Header wie `Authorization: Bearer eyJ…`.
Fängt das Token mit `eyJ` an, kannst du es auf jwt.io einfügen und beim Feld `exp` sehen, wann es abläuft.
- Läuft es nach Monaten/gar nicht ab → einfach so eintragen.
- Läuft es nach Stunden/Tagen ab → zusätzlich die **Login-Anfrage** der App mitschneiden (App abmelden, neu anmelden, Anfrage mit E-Mail/Passwort suchen) und unten die `LOGIN_*`-Felder nutzen.

> Tipp: Schick die kopierte Anfrage + Antwort an Claude (Passwort/Token vorher durch `XXX` ersetzen), dann bekommst du die fertigen Werte für Schritt 3.

---

## Schritt 2 – Projekt auf GitHub anlegen

1. Kostenloses Konto auf github.com anlegen.
2. **New repository** → Name z. B. `gym-monitor` → **Public** (nötig für kostenloses GitHub Pages; öffentlich sind nur die Prozentwerte, deine Zugangsdaten bleiben geheim) → *Create*.
3. *uploading an existing file* anklicken und **alle Dateien und Ordner** aus diesem ZIP hineinziehen (inkl. `.github`-Ordner – am Mac vorher mit `Cmd+Shift+.` versteckte Ordner einblenden) → *Commit changes*.

## Schritt 3 – Zugangsdaten als Secrets eintragen

Repository → **Settings → Secrets and variables → Actions → New repository secret**.

### Fertige Werte für fit+ Markkleeberg

| Secret | Wert |
|---|---|
| `REQUEST_URL` | `https://dnmq-rest.iconiq-solutions.com/api/poi/poi::e1107d9c-ea47-4cad-87fb-91de4859ba43?detach=1&include=checkins_number%2Cservices%2Cmanager_profile%2Csub_project%2Csub_sub_project%2CuserRating%2Creferences.sub_sub_project%2Cintroduction.at_first_checkin%2Cintroduction.at_every_checkin%2Cintroduction.at_first_login&includeFlags=1` |
| `REQUEST_HEADERS` | `{"x-access-token": "{token}", "x-lang": "de", "User-Agent": "fit/16.84 (iPhone; iOS 27.0.1; Scale/3.00)"}` |
| `VALUE_PATH` | `checkins_number` |
| `MAX_PATH` | `maximum_checkins_number` |
| `STATIC_TOKEN` | dein Token: in Proxyman bei einer Anfrage an `/api/poi/…` → Request → Header `x-access-token` → Wert kopieren (beginnt mit `eyJ`) |

Damit wird alle 5 Minuten „eingecheckte Personen ÷ Maximum“ gespeichert (z. B. 7 von 40 = 17,5 %).

Optional, damit es auch weiterläuft, falls das Token irgendwann ungültig wird (z. B. nach Ab-/Anmelden in der App):

| Secret | Wert |
|---|---|
| `LOGIN_URL` | URL der Anfrage `POST /auth/login?project=…` aus Proxyman (komplett kopieren) |
| `LOGIN_BODY` | `{"username": "DEINE-EMAIL", "password": "DEIN-PASSWORT", "projectId": "…"}` – `projectId` aus dem Body derselben Login-Anfrage übernehmen |
| `LOGIN_TOKEN_PATH` | `token` |

### Allgemein (andere Studios/Apps)

| Secret | Pflicht? | Beispiel |
|---|---|---|
| `REQUEST_URL` | ja | `https://api.beispiel.de/v1/studios/1234/utilization` |
| `REQUEST_HEADERS` | meist | `{"Authorization": "Bearer eyJhbGci…", "x-tenant": "fitplus"}` |
| `REQUEST_METHOD` | nein | `GET` (Standard) oder `POST` |
| `REQUEST_BODY` | nur bei POST | `{"studioId": 1234}` |
| `VALUE_PATH` | nein | `data.utilization` oder `items[isCurrent=true].percentage` – leer = automatische Suche |
| `LOGIN_URL` | nur wenn Token abläuft | `https://api.beispiel.de/auth/login` |
| `LOGIN_BODY` | – | `{"email": "du@mail.de", "password": "…"}` |
| `LOGIN_HEADERS` | – | `{"x-tenant": "fitplus"}` |
| `LOGIN_TOKEN_PATH` | – | `access_token` oder `data.token` |

Mit Login: In `REQUEST_HEADERS`/`REQUEST_URL` überall `{token}` schreiben, z. B. `{"Authorization": "Bearer {token}"}` – das frische Token wird bei jedem Abruf automatisch eingesetzt.

## Schritt 4 – Sammler starten & testen

1. Reiter **Actions** → ggf. „I understand my workflows, enable them“ klicken.
2. Links **Auslastung erfassen** → **Run workflow**.
3. Nach ~30 Sek. sollte der Lauf grün sein und im Log `Auslastung: 37.0 %` stehen.
   Ab jetzt läuft er automatisch alle 5 Minuten (GitHub startet teils ein paar Minuten später – für Statistiken egal).

Fehler im Log?
- `HTTP-Fehler 401/403` → Token abgelaufen → neues Token eintragen oder Login einrichten.
- `Kein Prozentwert gefunden` → im Log steht ein Auszug der Antwort; daraus `VALUE_PATH` setzen.

## Schritt 5 – Dashboard einschalten

**Settings → Pages** → Source: *Deploy from a branch* → Branch `main`, Ordner **`/docs`** → *Save*.
Nach 1–2 Minuten ist dein Dashboard unter `https://DEINNAME.github.io/gym-monitor/` erreichbar.
Tipp: Im Handy-Browser „Zum Home-Bildschirm“ – dann ist es wie eine App.

Aussagekräftige Stoßzeiten gibt es nach ca. 2 Wochen Daten, richtig stabil nach 4–6 Wochen.

---

## Gut zu wissen
- **Kosten:** 0 €. Öffentliche Repositories haben unbegrenzte Actions-Minuten.
- **Pause nach 60 Tagen:** Falls GitHub dir eine Mail schickt, dass geplante Workflows wegen Inaktivität pausiert wurden, einfach in *Actions* auf *Enable workflow* klicken.
- **Daten herunterladen:** Branch `data` → Ordner `data` → CSV-Dateien (öffnen sich in Excel).
- **Fair bleiben:** Ein Abruf alle 5 Minuten entspricht einem App-Nutzer, der ab und zu reinschaut. Nicht häufiger einstellen.
- **Lokal testen:** `REQUEST_URL=… python3 collector/collect.py` – braucht nur Python 3, keine Pakete.
