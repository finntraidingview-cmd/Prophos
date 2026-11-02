#!/usr/bin/env python3
"""Selbsttest SCHLIESSEN AUF DEM PC + KONTO FEST (Finn 02.11.2026 ~19:10 „Zurück zu den Basics“, /goal Master-Exit → Fusion zu ≤ 1 s, egal ob der Prophos-Tab
lädt, fehlt oder gedrosselt ist). Panel: scharf_setzen / scharf_entscheid / _scharf_runde (Reader-Stand → close-Auftrag an den Copier), konto_fest_sperre;
order_bot: kein Puls-Chrome-Neustart bei kein_neustart. Fälle: Normalfall ≤ 1 s, Simon (Tab weg, nur Datei + Reader), Konto nicht sicher, Kontowechsel,
blind/alt, nie gesehen, altes Userscript, Kontowechsel-Versuch bei offenem Trade wartet. Ohne Netz. Aufruf: python3 tools/selftest_schliessen_am_pc.py"""
import ast
import json
import os
import random
import re
import sys
import tempfile
import threading
import types

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(W, "mt5-copier", "panel.py"), encoding="utf-8").read()
BOT = open(os.path.join(W, "mt5-copier", "order_bot.py"), encoding="utf-8").read()
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


tmp = tempfile.mkdtemp()
uhr = [10000.0]
ns = {"os": os, "re": re, "json": json, "random": random, "threading": threading, "HERE": tmp, "time": types.SimpleNamespace(time=lambda: uhr[0], sleep=lambda s: None),
      "HEDGE_SOLO_LOCK": threading.Lock(), "print": lambda *a, **k: None}
for n in ast.parse(SRC).body:
    if isinstance(n, ast.FunctionDef) and n.name == "read_json":
        exec(ast.get_source_segment(SRC, n), ns)
i = SRC.index("SCHARF_PFAD = os.path.join(HERE")
j = SRC.index("_TAB_PULS_OEFFNEN_CODE = (")
exec(SRC[i:j], ns)
ID = "FTDFYSLX150811161322"
NB = [ID, "FTDFYSLX150811161399", "FTDFYSLX150811169999", "APEX6416990000045"]   # …161399 beginnt wie ID: gekürzt mehrdeutig


def stand(konto=ID, pos=None, ok=True, alter=0.05, ts=None, version="0.10.9", blind=False, tab="puls-mvz4o89y50p23m", leer=True):
    return {"an": True, "konto": konto, "positionen": pos if pos is not None else [], "positionen_ok": ok, "alter_s": alter, "blind": blind,
            "positionen_ts": ts if ts is not None else uhr[0] * 1000, "script_version": version, "positionen_tab": tab, "leer_beweis": leer}


READER = {"tabs": [{"tab_id": "puls-mvz4o89y50p23m", "rolle": "broker", "version": "0.10.9"}]}


POS = [{"symbol": "MNQZ6", "wurzel": "MNQ", "richtung": "sell", "menge_zahl": 1, "pnl": None}]


def frisch_scharf(ticket=111, ext=ID, nb=NB):
    if os.path.exists(ns["SCHARF_PFAD"]):
        os.remove(ns["SCHARF_PFAD"])
    for f in ("hedge_solo_auftrag.json", "hedge_solo_ergebnis.json"):
        p = os.path.join(tmp, f)
        if os.path.exists(p):
            os.remove(p)
    return ns["scharf_setzen"]({"ext_id": ext, "wurzel": "MNQ", "nachbarn": nb}, "plan-88b28130", ticket, READER)


def auftraege():
    return [a for a in (ns["read_json"](os.path.join(tmp, "hedge_solo_auftrag.json"), []) or []) if a.get("aktion") == "close"]


def lauf(folge, takt=0.1):
    """folge = Liste von Stand-Erzeugern (je Runde frisch, eigener positionen_ts); je Stand eine Runde, dann takt Sekunden weiter
    → Zeitpunkt des ersten Close-Auftrags oder None."""
    for mach in folge:
        n = ns["_scharf_runde"](mach(), uhr[0])
        if n:
            return uhr[0]
        uhr[0] += takt
    return None


# 1) Normalfall: Position gesehen, dann flach → Close ≤ 1 s nach der ersten flachen Lesung
check(frisch_scharf(), "Hedge-Open mit Feld scharf → gemerkt (Datei)")
uhr[0] += 5
lauf([lambda: stand(pos=POS)] * 3)
t_flach = uhr[0]
t_zu = lauf([lambda: stand()] * 15)
check(t_zu is not None and t_zu - t_flach <= 1.0, f"Normalfall: Close {t_zu - t_flach:.2f} s nach der ersten flachen Lesung (≤ 1 s)" if t_zu else "Normalfall: Close")
a = auftraege()
check(len(a) == 1 and a[0]["ticket"] == 111 and a[0]["grund"] == "master_ende_panel", "genau ein close-Auftrag an den Copier (hedge_solo_auftrag.json)")
# Quittung → gelöst
json.dump({a[0]["cmd_id"]: {"ok": True, "ticket": 111}}, open(os.path.join(tmp, "hedge_solo_ergebnis.json"), "w"))
ns["_scharf_runde"](stand(), uhr[0])
check(ns["scharf_laden"]() == [], "Copier quittiert ok → Eintrag gelöst")

# 2) SIMON: Prophos-Tab weg — es braucht nur Datei + Reader (kein Tab-Aufruf im Weg)
frisch_scharf(222)
uhr[0] += 5
w = SRC[SRC.index("def _scharf_runde("):SRC.index("def _scharf_wache():")]
check("mtcApi" not in w and "tradePlans" not in w, "Schließ-Weg ohne Prophos-Tab: nur hedge_scharf.json + Reader-Stand + Copier-Datei")
lauf([lambda: stand(pos=POS)] * 2)
check(lauf([lambda: stand()] * 10) is not None, "Simon-Fall: Tab weg, Reader sieht Position weg → Fusion-Close vom Panel")

# 3) Konto nicht sicher: gekürzt und mehrdeutig (zwei Konten derselben ID beginnen gleich) → nie
frisch_scharf(333)
uhr[0] += 5
kurz = "FTDFYSLX1508111613… 149,969.50 USD"
lauf([lambda: stand(konto=kurz, pos=POS)] * 2)
check(lauf([lambda: stand(konto=kurz)] * 20) is None, "gekürzter Kontotext passt auf zwei Konten der ID → nie schließen (Tab-Weg bleibt)")
frisch_scharf(334, nb=[ID, "APEX6416990000045"])
uhr[0] += 5
lauf([lambda: stand(konto=kurz, pos=POS)] * 2)
check(lauf([lambda: stand(konto=kurz)] * 10) is not None, "gekürzt, aber unter den Konten der ID eindeutig → schließt")

# 4) Kontowechsel: Position im Konto gesehen, dann anderes Konto flach → nie; zurück ins Konto → muss neu gesehen werden
frisch_scharf(444)
uhr[0] += 5
lauf([lambda: stand(pos=POS)] * 2)
check(lauf([lambda: stand(konto="FTDFYSLX150811169999")] * 10) is None, "anderes Konto flach → nie schließen")
check(lauf([lambda: stand()] * 10) is None, "zurück im Konto, aber Position seit dem Wechsel nicht neu gesehen → nie")

# 5) blind / alt / altes Userscript / nie gesehen
frisch_scharf(555)
uhr[0] += 5
lauf([lambda: stand(pos=POS)] * 2)
check(lauf([lambda: stand(ok=False)] * 10 + [lambda: stand(alter=3.0)] * 10 + [lambda: stand(blind=True)] * 10) is None, "blind, alter Stand → nie schließen")
frisch_scharf(556)
uhr[0] += 5
lauf([lambda: stand(pos=POS, version="0.10.7")] * 2)
check(lauf([lambda: stand(version="0.10.7")] * 10) is None, "Userscript älter als 0.10.8 → nie (bestehender Weg)")
frisch_scharf(557)
uhr[0] += 5
check(lauf([lambda: stand()] * 20) is None, "Position im Konto nie gesehen → nie schließen")
# 6) Hedge jünger als 3 s
frisch_scharf(558)
lauf([lambda: stand(pos=POS)])
check(lauf([lambda: stand()] * 10) is None, "Hedge jünger als 3 s → wartet")
# 7) keine Quittung → nach 2 s erneut
frisch_scharf(559)
uhr[0] += 5
lauf([lambda: stand(pos=POS)] * 2)
lauf([lambda: stand()] * 10)
uhr[0] += 2.1
ns["_scharf_runde"](stand(), uhr[0])
check(len(auftraege()) == 2, "ohne Quittung nach 2 s ein zweiter close-Auftrag (Copier antwortet schon_zu, wenn zu)")

# S9: nur Puls-Chrome, Flach nur mit Leer-Beweis
frisch_scharf(700)
uhr[0] += 5
lauf([lambda: stand(pos=POS, tab="t1abc")] * 2)
check(lauf([lambda: stand(tab="t1abc")] * 10) is None, "Reader-Tab im normalen Chrome (nicht „puls-“) → nie schließen")
lauf([lambda: stand(pos=POS)] * 2)
check(lauf([lambda: stand(leer=False)] * 10) is None, "flach ohne Leer-Beweis (leer_beweis false) → nie, der Tab entscheidet")
check(lauf([lambda: stand()] * 10) is not None, "flach mit Leer-Beweis → schließt")
# S9: liegengebliebener Eintrag
frisch_scharf(701)
uhr[0] += 10
ns["_scharf_runde"](None, uhr[0], {999})
check(len(ns["scharf_laden"]()) == 1, "Ticket fehlt in der Copier-Liste, Hedge jünger als 30 s → bleibt")
uhr[0] += 25
ns["_scharf_runde"](None, uhr[0], {999})
check(ns["scharf_laden"]() == [], "Ticket nicht mehr offen im Copier (anders zugegangen) → gelöst")
frisch_scharf(702)
uhr[0] += 60
ns["_scharf_runde"](None, uhr[0], None)
check(len(ns["scharf_laden"]()) == 1, "Copier-Liste nicht prüfbar → nichts lösen")
uhr[0] += 3 * 3600
ns["_scharf_runde"](None, uhr[0], None)
check(ns["scharf_laden"]() == [] and ns["SCHARF_MAX_S"] == 3 * 3600, "Verfall nach 3 h (statt 12 h)")
# S9: scharf nur mit Puls-Reader ≥ 0.10.8
if os.path.exists(ns["SCHARF_PFAD"]):
    os.remove(ns["SCHARF_PFAD"])
check(ns["scharf_setzen"]({"ext_id": ID, "wurzel": "MNQ"}, "p", 800, {"tabs": [{"tab_id": "puls-x", "version": "0.10.7"}]}) is False
      and ns["scharf_setzen"]({"ext_id": ID, "wurzel": "MNQ"}, "p", 801, {"tabs": [{"tab_id": "t-x", "version": "0.10.9"}]}) is False
      and ns["scharf_setzen"]({"ext_id": ID, "wurzel": "MNQ"}, "p", 802, None) is False, "kein Eintrag ohne Puls-Chrome-Reader ≥ 0.10.8 (alt, normales Chrome, Reader weg)")
check(ns["scharf_setzen"]({"ext_id": ID, "wurzel": "MNQ"}, "p", 803, READER) is True, "Puls-Reader 0.10.9 → Eintrag")

# LESE-SPERRE Market Opening (Finn-Korrektur 02.11.2026: kein „Konto fest bei offenem Trade“)
import calendar
def dubai(h, m):   # 02.11.2026 h:m Dubai → epoch
    return calendar.timegm((2026, 11, 2, h, m, 0)) - 4 * 3600
L = ns["lese_sperre_markt"]
check(L(dubai(18, 30))[0] and L(dubai(18, 39) + 59)[0], "18:30–18:39:59 Dubai gesperrt")
check(not L(dubai(18, 29) + 59)[0] and not L(dubai(18, 40))[0] and not L(dubai(17, 0))[0], "18:29:59, 18:40 und 17:00 frei (kein 17:00-Fenster)")
uhr[0] = dubai(18, 35)
r = json.loads(ns["_lese_sperre_antwort"]("ANDERES123456", "/api/tv-lesen"))
check(r["code"] == "puls_beschaeftigt" and r["retry_ok"] and r["lese_sperre"] and "Market Opening" in r["msg"], "Antwort wie ein laufender Lauf (puls_beschaeftigt, retry_ok) → der Aufrufer wartet")
uhr[0] = dubai(18, 45)
check(ns["_lese_sperre_antwort"]("X12345", "/api/tv-lesen") is None, "außerhalb des Fensters → frei")
frisch_scharf(666)
uhr[0] = dubai(19, 0)
check(ns["_lese_sperre_antwort"]("ANDERES123456", "/api/tv-lesen") is None, "offener Trade allein sperrt keine Lesung mehr (Heim-Wache-Regel bleibt)")
check("konto_fest_sperre" not in SRC and "_konto_fest_antwort" not in SRC, "kein „Konto fest bei offenem Trade“ mehr im Panel")
for pfad in ("/api/tv-lesen", "/api/tv-konten-liste"):
    k = SRC.index(f'if u.path == "{pfad}":')
    check("_lese_sperre_antwort(konto, u.path)" in SRC[k:k + 2500], f"{pfad} prüft die Lese-Sperre vor dem Lauf")
k = SRC.index('if u.path == "/api/tv-close":')
check("_lese_sperre_antwort" not in SRC[k:SRC.index('if u.path == "/api/tv-order":')], "tv-close nie gesperrt, auch 18:30–18:40 (Schließen hat Vorrang)")
k = SRC.index('if u.path == "/api/tv-konto":')
check("_lese_sperre_antwort" not in SRC[k:SRC.index('if u.path == "/api/tsx-konto":')], "Trade-Starts (tv-konto) nicht betroffen")
check(SRC.count('cmd["kein_neustart"] = True') == 3, "bleibt: kein Puls-Chrome-Neustart bei offenem TV-Trade mit Hedge (tv-konto, tsx-konto, tsx-lesen)")

# order_bot: Neustart verboten
bns = {}
for n in ast.parse(BOT).body:
    if isinstance(n, ast.FunctionDef) and n.name in ("kein_neustart_grund",):
        exec(ast.get_source_segment(BOT, n), bns)
check(bns["kein_neustart_grund"]({"kein_neustart": True}) and bns["kein_neustart_grund"]({}) is None and bns["kein_neustart_grund"]("x") is None, "kein_neustart_grund")
w2 = BOT[BOT.index("def _puls_mit_neustart("):BOT.index("def _puls_mit_neustart(") + 2500]
check('if verboten and art != "nein":' in w2 and BOT.count("verboten=kein_neustart_grund(") == 2, "Neustart-Wrapper: verboten → kein Neustart (Orbit und Topstep)")
# Tab
check("scharf: scharfOpen" in HTML and "plan.route !== 'tvv2'" in HTML, "Tab schickt scharf nur bei TradingView-Trades (tvv2) mit dem Hedge-Open")
check('scharf_setzen(body.get("scharf"), auftrag.get("plan_id"), erg.get("ticket"), _rs)' in SRC and 'scharf_loesen(auftrag.get("ticket")' in SRC,
      "Panel: scharf nach der Open-Quittung, gelöst beim Close vom Tab")
check("threading.Thread(target=_scharf_wache, daemon=True).start()" in SRC, "Schließ-Wache startet mit dem Panel")
print("ROT:" if FEHLER else "alles grün", FEHLER if FEHLER else "")
sys.exit(1 if FEHLER else 0)
