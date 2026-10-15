#!/usr/bin/env python3
"""
Ruft die aktuelle Auslastung des Studios ab und haengt sie an eine CSV-Datei an.

Konfiguration ausschliesslich ueber Umgebungsvariablen (in GitHub als "Secrets"):

  REQUEST_URL       (Pflicht)  Adresse, die die App fuer die Auslastung aufruft
  REQUEST_METHOD    (optional) GET (Standard) oder POST
  REQUEST_HEADERS   (optional) JSON-Objekt, z.B. {"Authorization": "Bearer {token}"}
  REQUEST_BODY      (optional) Body fuer POST (Text/JSON)
  VALUE_PATH        (optional) Pfad zum Prozentwert im JSON, z.B. data.utilization
                               oder items[isCurrent=true].percentage
                               Leer = automatische Suche nach typischen Feldnamen.
  MAX_PATH          (optional) Pfad zur Hoechstzahl. Ist er gesetzt, ist VALUE_PATH
                               eine Personenzahl und der Prozentwert wird berechnet
                               (fit+: VALUE_PATH=checkins_number,
                                      MAX_PATH=maximum_checkins_number)

  Falls das Token regelmaessig ablaeuft, optional ein Login vorschalten:
  LOGIN_URL         Adresse des Logins
  LOGIN_HEADERS     JSON-Objekt mit Headern fuer den Login
  LOGIN_BODY        Body des Logins (meist JSON mit E-Mail/Passwort)
  LOGIN_TOKEN_PATH  Pfad zum Token in der Login-Antwort, z.B. access_token
  -> Das Token wird dann ueberall fuer {token} eingesetzt.
  STATIC_TOKEN      (optional) festes Token fuer {token}. Ist zusaetzlich LOGIN_* gesetzt,
                               wird nur bei 401/403 neu eingeloggt.

Ausgabe: data/YYYY-MM.csv  (Spalten: timestamp_utc,percent,count,max)
         data/index.json   (Liste der Monatsdateien fuer das Dashboard)
"""
import csv
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request

DATA_DIR = os.environ.get("DATA_DIR", "data")
TIMEOUT = 30
UA = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Mobile"

AUTO_KEYS = ("percentage", "percent", "utilization", "utilisation", "auslastung",
             "occupancy", "capacity", "load", "value", "current")


def env(name, default=""):
    return (os.environ.get(name) or default).strip()


def http(url, method="GET", headers=None, body=None):
    h = {"User-Agent": UA, "Accept": "application/json, text/plain, */*"}
    h.update(headers or {})
    data = body.encode("utf-8") if body else None
    if data and not any(k.lower() == "content-type" for k in h):
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        raw = r.read().decode("utf-8", errors="replace")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw  # z.B. reiner Text "42"


def get_path(obj, path):
    """Einfacher Pfad: a.b[0].c  oder  items[isCurrent=true].percentage"""
    for part in re.findall(r"[^.\[\]]+|\[[^\]]*\]", path):
        if part.startswith("["):
            inner = part[1:-1]
            if "=" in inner:
                k, v = inner.split("=", 1)
                v = v.strip().strip('"\'')
                match = None
                for item in obj:
                    if isinstance(item, dict) and str(item.get(k.strip())).lower() == v.lower():
                        match = item
                        break
                if match is None:
                    raise KeyError(f"Kein Element mit {k}={v}")
                obj = match
            else:
                obj = obj[int(inner)]
        else:
            obj = obj[int(part)] if isinstance(obj, list) else obj[part]
    return obj


def auto_find(obj):
    """Sucht rekursiv nach einem Zahlenwert 0..100 unter typischen Feldnamen."""
    found = []

    def walk(o, depth=0):
        if depth > 8:
            return
        if isinstance(o, dict):
            # "isCurrent"-Muster (stuendliche Listen) bevorzugen
            if o.get("isCurrent") is True or o.get("current") is True:
                for k in AUTO_KEYS:
                    if isinstance(o.get(k), (int, float)):
                        found.insert(0, o[k])
            for k, v in o.items():
                if k.lower() in AUTO_KEYS and isinstance(v, (int, float)) and not isinstance(v, bool):
                    found.append(v)
                walk(v, depth + 1)
        elif isinstance(o, list):
            for v in o:
                walk(v, depth + 1)

    if isinstance(obj, (int, float)):
        return obj
    if isinstance(obj, str):
        m = re.search(r"(\d{1,3}(?:[.,]\d+)?)\s*%", obj) or re.fullmatch(r"\s*(\d{1,3}(?:[.,]\d+)?)\s*", obj)
        return float(m.group(1).replace(",", ".")) if m else None
    walk(obj)
    for v in found:
        if 0 <= v <= 100:
            return v
        if 0 <= v <= 1:
            return v * 100
    return None


def to_percent(v):
    if isinstance(v, str):
        v = float(v.replace("%", "").replace(",", ".").strip())
    v = float(v)
    if 0 < v <= 1 and env("VALUE_IS_FRACTION", "auto") != "false" and not float(v).is_integer():
        v *= 100  # 0.42 -> 42 %
    return round(v, 1)


def fill(text, token):
    return text.replace("{token}", token) if token else text


def login():
    url = env("LOGIN_URL")
    if not url:
        return ""
    headers = json.loads(env("LOGIN_HEADERS", "{}"))
    resp = http(url, "POST", headers, env("LOGIN_BODY") or None)
    path = env("LOGIN_TOKEN_PATH", "access_token")
    token = str(get_path(resp, path))
    print("Login ok, Token erhalten.")
    return token


def request(token):
    headers = json.loads(fill(env("REQUEST_HEADERS", "{}"), token))
    return http(fill(env("REQUEST_URL"), token), env("REQUEST_METHOD", "GET").upper(), headers,
                fill(env("REQUEST_BODY"), token) or None)


def fetch():
    """Liefert (prozent, personen|None, maximum|None)."""
    if not env("REQUEST_URL"):
        raise SystemExit("REQUEST_URL fehlt. Bitte als Secret eintragen (siehe README).")
    token = env("STATIC_TOKEN")
    if not token:
        token = login()
    try:
        resp = request(token)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403) and env("STATIC_TOKEN") and env("LOGIN_URL"):
            print("Token abgelehnt, melde neu an …")
            resp = request(login())
        else:
            raise
    path, max_path = env("VALUE_PATH"), env("MAX_PATH")
    if max_path:
        count, mx = float(get_path(resp, path)), float(get_path(resp, max_path))
        if mx <= 0:
            raise ValueError(f"Maximum ist {mx}, Prozent nicht berechenbar")
        return round(count / mx * 100, 1), int(count), int(mx)
    value = get_path(resp, path) if path else auto_find(resp)
    if value is None:
        snippet = json.dumps(resp)[:500] if not isinstance(resp, str) else resp[:500]
        raise ValueError(f"Kein Prozentwert gefunden. Antwort (Auszug): {snippet}")
    return to_percent(value), None, None


def append(now, percent, count=None, mx=None):
    os.makedirs(DATA_DIR, exist_ok=True)
    month = now.strftime("%Y-%m")
    path = os.path.join(DATA_DIR, f"{month}.csv")
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp_utc", "percent", "count", "max"])
        w.writerow([now.strftime("%Y-%m-%dT%H:%M:%SZ"), "" if percent is None else percent,
                    "" if count is None else count, "" if mx is None else mx])
    months = sorted(p[:-4] for p in os.listdir(DATA_DIR) if re.fullmatch(r"\d{4}-\d{2}\.csv", p))
    with open(os.path.join(DATA_DIR, "index.json"), "w") as f:
        json.dump({"months": months, "updated": now.strftime("%Y-%m-%dT%H:%M:%SZ")}, f)


def main():
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    try:
        percent, count, mx = fetch()
        extra = f"  ({count} von {mx} Personen)" if count is not None else ""
        print(f"{now.isoformat()}  Auslastung: {percent} %{extra}")
        append(now, percent, count, mx)
    except urllib.error.HTTPError as e:
        print(f"HTTP-Fehler {e.code}: {e.read()[:300]!r}", file=sys.stderr)
        if e.code in (401, 403):
            print("-> Token abgelaufen? Neues Token eintragen oder LOGIN_* einrichten.", file=sys.stderr)
        sys.exit(1)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        print(f"Fehler: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
