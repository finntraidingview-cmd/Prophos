#!/usr/bin/env python3
"""Selbsttest WD-HAKEN VON SELBST + HEUTE SCHON GETRADET (Finn 03.11.2026 ~01:30 Dubai: „Wenn ein Konto zu Winning Days hinzugefügt wird, soll der Haken
automatisch gesetzt werden. Für den heutigen Tag soll aber kein Trade mehr gemacht werden, weil da eh schon einer gemacht wurde, aber für die zukünftigen ja.")

Aufruf:  python3 tools/selftest_wd_haken_bei_wechsel.py
Ohne Netz. Geprüft:
  sql/2026-11-03_wd_farm_bei_wechsel.sql   Trigger nur beim Wechsel auf winning_days bzw. Anlage als winning_days (Text-Prüfung, keine DB)
  app.py   wd_cme_tag_start (Vortag 17:00 Chicago), wd_erl_konto_umstellen_upd mit wd_farm, /admin/wd-plaene heute_gestartet
  Frontend wdCmeTagStart / wdHeuteGestartet (JavaScriptCore), Haken in accWdUmstellen, Bearbeiten, Anlage, Bulk; wdErwartet/wdKandidaten/Abgleich mit „heute“"""
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
sql = open(os.path.join(WURZEL, "sql", "2026-11-03_wd_farm_bei_wechsel.sql"), encoding="utf-8").read()


def block(name):
    i = src.index(f"\ndef {name}(") + 1
    return src[i:src.find("\n\n\n", i)]


ns = {"datetime": datetime, "timedelta": timedelta, "timezone": timezone}
exec(block("wd_cme_tag_start"), ns)
S = ns["wd_cme_tag_start"]
check(S("2026-11-03") == "2026-11-02T23:00:00Z", "Lauf-Tag Di 03.11. → CME-Tag ab Mo 17:00 CT = 23:00 UTC = 03:00 Dubai (Winter)")
check(S("2026-11-02") == "2026-11-01T23:00:00Z", "Montag 02.11. → Sonntag 17:00 CT (US-Winterzeit seit 01.11.)")
check(S("2026-10-28") == "2026-10-27T22:00:00Z", "Sommerzeit Chicago: 17:00 CDT = 22:00 UTC")
# Mike Apex …0002: Trade e8f2c337 gestern (02.11. Dubai, vor 03:00 Dubai am 03.11.) zählt nicht für den Lauf-Tag 03.11. — ein Trade ab 03:00 Dubai schon
check("2026-11-02T14:00:00Z" < S("2026-11-03") <= "2026-11-02T23:30:00Z", "Grenze: 02.11. 18:00 Dubai gehört zum Vortag, 03.11. 03:30 Dubai zum Lauf-Tag")

# ── Trigger (Text) ──
check(re.search(r"before insert or update of account_type on public\.accounts", sql) is not None, "Trigger: BEFORE INSERT OR UPDATE OF account_type")
check("new.account_type = 'winning_days'" in sql and "tg_op = 'INSERT' or old.account_type is distinct from 'winning_days'" in sql and "new.wd_farm := true" in sql,
      "nur beim Wechsel auf winning_days bzw. Anlage — Ausschalten von Hand ohne Typwechsel bleibt")
check("drop trigger if exists accounts_wd_farm_bei_wechsel" in sql and "create or replace function public.accounts_wd_farm_bei_wechsel" in sql, "wiederholbar")
check(not re.search(r"^\s*(update|delete)\b", sql, re.I | re.M), "keine Daten-Änderung an bestehenden Konten (Mike setzt Finn selbst)")

# ── Backend-Wege ──
check('"account_type": "winning_days", "wd_farm": True' in block("wd_erl_konto_umstellen_upd"), "Abhaken → Winning Days setzt wd_farm (Radar, fremde IDs)")
check('neu = {"account_type": "winning_days", "wd_farm": True}' in src, "Ziel-Wache Funded → Winning Days (schon da)")
r = re.search(r"# HEUTE SCHON GETRADET.*?except Exception as e:", src, re.S)
check(r is not None and '"started_at": f"gte.{ab}"' in r.group(0) and 'k["heute_gestartet"]' in r.group(0), "/admin/wd-plaene: heute_gestartet je Konto ab CME-Tag-Start")

# ── Frontend ──
check("...(ziel === 'winning_days' && acc.type !== 'winning_days' ? { wd_farm: true } : {})" in html, "Knöpfe am Konto (accWdUmstellen): Haken beim Wechsel")
check("acc.type === 'winning_days' && String((accounts.find(x => String(x.id) === String(_editingAccountId)) || {}).type || '') !== 'winning_days'" in html, "Bearbeiten: Haken nur beim Wechsel")
check("wd_farm: !!a.wdFarm || a.type === 'winning_days'" in html and "wd_farm: typRow === 'winning_days'" in html, "Anlage (Modal, Bulk/Nachfolger): als Winning Days → Haken")
check("aktiv: !!(farm && !arch && ext && !heute" in html, "wdErwartet: heute schon getradet → nicht aktiv")   # seit 03.11.2026 dahinter noch „&& !po“ (Payout offen)
check("v.aktiv = !!(k.farm && k.ext && !k.heute)" in html and "v.heute = true; v.aktiv = false; v.hinweis = WD_HINWEIS_HEUTE" in html, "Abgleich bestehender Zeilen: Haken an, aber heute nicht aktiv")
check("if(wdHeuteGestartet(k.acc.id, tag))" in html and "wdKandidaten(tag)" in html, "PC-Tab (wdKandidaten): eigene Pläne, heute schon gestartet → nicht aktiv")
check("if(heute.has(k.id)) k.heute_gestartet = heute.get(k.id)" in html, "RPC-Konten übernehmen heute_gestartet von Railway")


def fn(name, art="function"):
    if art == "const":
        i = html.index(f"\n  const {name} = ") + 1
        return html[i:html.index("\n", i)]
    i = html.index(f"\n  function {name}(") + 1
    return html[i:html.index("\n  }\n", i) + 4]


js = "\n".join([fn("wdJetzt"), fn("wdZeitpunkt"), fn("wdTagPlus", "const"), "const WD_TZ_STD = 'Asia/Dubai';", fn("wdCmeTagStart", "const"), fn("wdHeuteGestartet")])
js += """
var tradePlans = [
  { masterAccountId: 'mike', startedAt: '2026-11-02T10:00:00Z' },      // gestern (Trade e8f2c337-Fall)
  { masterAccountId: 'heute', startedAt: '2026-11-02T23:30:00Z' },     // 03.11. 03:30 Dubai = CME-Tag 03.11.
  { masterAccountId: 'offen', startedAt: null },
];
print(JSON.stringify({ ab: new Date(wdCmeTagStart('2026-11-03')).toISOString(), mike: wdHeuteGestartet('mike', '2026-11-03'), heute: wdHeuteGestartet('heute', '2026-11-03'),
  offen: wdHeuteGestartet('offen', '2026-11-03'), ohneTag: wdHeuteGestartet('heute', ''), mikeTag02: wdHeuteGestartet('mike', '2026-11-02') }));
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
r = subprocess.run(["/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc", d.name], capture_output=True, text=True)
os.unlink(d.name)
check(r.returncode == 0 and r.stdout.strip(), f"jsc läuft ({(r.stderr or r.stdout)[:300]})")
e = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else {}
check(e.get("ab") == "2026-11-02T23:00:00.000Z", f"JS wdCmeTagStart = Python ({e.get('ab')})")
check(e.get("mike") is False, "Trade gestern (Vortag) → heute WD erlaubt")
check(e.get("heute") is True, "Trade im CME-Tag des Lauf-Tags → heute kein WD")
check(e.get("offen") is False and e.get("ohneTag") is False, "ungestartet bzw. ohne Tag → keine Sperre")
check(e.get("mikeTag02") is True, "derselbe Trade sperrt den Lauf-Tag 02.11.")

print("\nselftest_wd_haken_bei_wechsel: " + ("alle Prüfungen grün" if not FEHLER else f"{len(FEHLER)} FEHLER: {FEHLER}"))
sys.exit(1 if FEHLER else 0)
