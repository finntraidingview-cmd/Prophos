#!/usr/bin/env python3
"""Selbsttest NV3 zweiter Weg (Finn 10.11.2026, PC von Marco pc-t8wg97): die Schließ-Wache im Panel schließt Fusion für Topstep/Nova selbst, sobald das
TopstepX-Auge den Master im Plan-Konto flach meldet (scharf_entscheid_tsx, _scharf_runde mit quelle „tsx“). Echte Zeitlinien:
  3d0c3e06 — Master 14:38:28–14:39:10,5 UTC, Auge träge (Messung ~alle 0,4 s, Lücken), Puls lief bis ~14:39:52 → Panel soll ~2 s nach dem Flach schließen.
  937e9256 — Master 14:29:36–14:29:56, Finn schloss während des eigenen Puls-Laufs → ebenso ~2 s.
Gegenproben: anderes Konto, nie gesehen, alte Flach-Serie, ausgeloggt, zwei Tabs, Auge < 0.3.1, alter Stand, mehrdeutige Endung → nie. Ticket nur einmal.
Aufruf:  python3 tools/selftest_panel_tsx_scharf.py"""
import ast
import json
import os
import random
import re
import sys
import tempfile
import threading
import types
from datetime import datetime, timezone

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(W, "mt5-copier", "panel.py"), encoding="utf-8").read()
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


tmp = tempfile.mkdtemp()
uhr = [10000.0]
ns = {"os": os, "re": re, "json": json, "random": random, "threading": threading, "HERE": tmp, "datetime": datetime,
      "time": types.SimpleNamespace(time=lambda: uhr[0], sleep=lambda s: None), "HEDGE_SOLO_LOCK": threading.Lock(), "print": lambda *a, **k: None,
      "_win_leerlauf_s": lambda: 1e9}
for n in ast.parse(SRC).body:
    if isinstance(n, ast.FunctionDef) and n.name == "read_json":
        exec(ast.get_source_segment(SRC, n), ns)
i = SRC.index("SCHARF_PFAD = os.path.join(HERE")
j = SRC.index("_TAB_PULS_OEFFNEN_CODE = (")
exec(SRC[i:j], ns)

K = "EXPRESS-V2-DLL-696284-33122225"
NB = [K, "EXPRESS-V2-DLL-696284-33129999", "50KTC-V2-696284-11112222"]


def T(s):
    h, m, sek = s.split(":")
    return datetime(2026, 11, 10, int(h), int(m), tzinfo=timezone.utc).timestamp() + float(sek)


def eintrag_neu(ticket=500, gesehen=False, ext=K, nb=NB, at=None):
    if os.path.exists(ns["SCHARF_PFAD"]):
        os.remove(ns["SCHARF_PFAD"])
    ok = ns["scharf_setzen"]({"quelle": "tsx", "ext_id": ext, "wurzel": "MNQ", "richtung": "buy", "menge": 1, "nachbarn": nb, "gesehen": gesehen},
                             "3d0c3e06-aaaa", ticket, None)   # kein TradingView-Reader → für Topstep trotzdem gemerkt
    if at is not None:
        l = ns["scharf_laden"]()
        l[0]["at"] = at
        ns["scharf_speichern"](l)
    return ok


def auge(konto=None, pos=False, flach=False, folge=0, seit=None, ts=None, alter=0.1, tabs=1, script="0.3.4", ausgeloggt=False):
    k = konto if konto is not None else {"kontonr": K, "abgekuerzt": False, "liste_offen": False}
    return {"ok": True, "tab": "t1", "tabs": tabs, "alter_s": alter, "script": script,
            "stand": {"ts": ts if ts is not None else uhr[0] * 1000, "konto": k, "ausgeloggt": ausgeloggt,
                      "positionen": [{"symbol": "MNQZ6", "menge": 1, "seite": "buy"}] if pos else [],
                      "flach": flach, "flach_folge": folge, "flach_seit": seit}}


def zeitlinie(start, pos_von, pos_bis, ende, hedge_at, anderes_konto=None, luecken=(), gesehen_tab=False, nie_pos=False):
    """Wache je 0,1 s, Auge misst ~alle 0,4 s (Lücken: keine Messung). → Sekunden vom Flach bis zum ersten Close-Auftrag oder None; Anzahl Aufträge."""
    eintrag_neu(gesehen=gesehen_tab, at=hedge_at)
    auftraege = []
    orig = ns["_scharf_close_senden"]
    ns["_scharf_close_senden"] = lambda e: (auftraege.append(uhr[0]), orig(e))[1]
    messung, flach_seit, folge = 0.0, None, 0
    t = start
    while t <= ende:
        uhr[0] = t
        luecke = any(a <= t < b for a, b in luecken)
        neu = not luecke and t - messung >= 0.4
        konto = {"kontonr": "EXPRESS-V2-DLL-696284-99999999" if (anderes_konto and anderes_konto[0] <= t < anderes_konto[1]) else K, "abgekuerzt": False, "liste_offen": False}
        offen = (not nie_pos) and pos_von <= t < pos_bis
        if neu:
            messung = t
            if not offen and t >= pos_bis and konto["kontonr"] == K:
                flach_seit = flach_seit or t
                folge += 1
            else:
                flach_seit, folge = None, 0
        flach = flach_seit is not None
        a = auge(konto=konto, pos=offen and konto["kontonr"] == K, flach=flach, folge=folge, seit=flach_seit * 1000 if flach else None,
                 ts=messung * 1000, alter=round(t - messung, 3) + 0.02)
        ns["_scharf_runde"](None, t, None, a)
        t = round(t + 0.1, 3)
    ns["_scharf_close_senden"] = orig
    abstand = min([b - a for a, b in zip(auftraege, auftraege[1:])] or [99])
    return (round(auftraege[0] - pos_bis, 2) if auftraege else None), abstand


# ── echte Fälle ──
zu3, n3 = zeitlinie(T("14:38:20"), T("14:38:28"), T("14:39:10.5"), T("14:39:30"), T("14:38:29.6"), luecken=[(T("14:38:32"), T("14:38:34")), (T("14:39:00"), T("14:39:02"))])
check(zu3 is not None and 2.0 <= zu3 < 3.0, f"3d0c3e06: Panel schließt {zu3} s nach dem Flach (Soll 2–3 s, vorher 71,9 s über den Tab)")
check(n3 >= 1.99, f"3d0c3e06: ohne Quittung frühestens nach 2 s ein neuer Auftrag (Copier antwortet dann schon_zu), kleinster Abstand {round(n3, 2)} s")
zu9, n9 = zeitlinie(T("14:29:30"), T("14:29:36"), T("14:29:56"), T("14:30:10"), T("14:29:38.4"))
check(zu9 is not None and 2.0 <= zu9 < 3.0, f"937e9256: Panel schließt {zu9} s nach dem Flach — mitten im Puls-Lauf, kein Puls-Riegel (vorher nie)")

# ── Gegenproben ──
zk, _ = zeitlinie(T("14:38:20"), T("14:38:28"), T("14:39:10.5"), T("14:39:40"), T("14:38:29.6"), anderes_konto=(T("14:39:10"), T("14:39:40")))
check(zk is None, "Auge zeigt ab dem Flach ein anderes Konto: nie zu (Schutz 1)")
zn, _ = zeitlinie(T("14:38:20"), T("14:38:28"), T("14:39:10.5"), T("14:39:40"), T("14:38:29.6"), nie_pos=True)
check(zn is None, "Master nie gesehen, kein Fill-Beleg vom Tab: nie zu (Schutz 2)")
zg, _ = zeitlinie(T("14:39:10"), T("14:38:28"), T("14:39:10.5"), T("14:39:30"), T("14:38:29.6"), gesehen_tab=True)
check(zg is not None and zg < 3.0, f"Panel startet erst nach dem Flach, der Tab hatte den Master gesehen (gesehen=true): zu nach {zg} s")

uhr[0] = T("14:40:00")
jetzt = uhr[0]
basis = {"at": jetzt - 60, "ext_id": K, "wurzel": "MNQ", "richtung": "buy", "nachbarn": NB, "gesehen": True, "gesehen_ts": (jetzt - 10) * 1000, "flach_ts": [1, 2, 3]}
def urteil(a, e=None):
    return ns["scharf_entscheid_tsx"](dict(e or basis), a, jetzt)
gut = dict(flach=True, folge=6, seit=(jetzt - 2.5) * 1000)
check(urteil(auge(**gut))[0] is True, "Grundfall: Plan-Konto, frisch, flach seit 2,5 s, Folge 6, 3 Messungen → zu")
check(urteil(auge(**gut, ausgeloggt=True))[0] is False, "ausgeloggt → nie")
check(urteil(auge(**gut, tabs=2))[0] is False, "zwei TopstepX-Tabs → nie")
check(urteil(auge(**gut, script="0.3.0"))[0] is False, "Auge < 0.3.1 → nie")
check(urteil(auge(**gut, alter=3.2))[0] is False, "Stand 3,2 s alt → nie")
check(urteil(auge(**gut, ts=(jetzt - 2.6) * 1000))[0] is False, "Messung 2,6 s alt → nie")
check(urteil(auge(flach=True, folge=6, seit=(jetzt - 1.5) * 1000))[0] is False, "flach erst 1,5 s → noch nicht")
check(urteil(auge(flach=True, folge=2, seit=(jetzt - 2.5) * 1000))[0] is False, "Folge 2 → noch nicht")
check(urteil(auge(**gut), dict(basis, flach_ts=[]))[0] is False, "erst eine eigene Messung → noch nicht")
check(urteil(auge(**gut), dict(basis, gesehen_ts=(jetzt - 1) * 1000))[0] is False, "Flach-Serie begann vor der letzten Sichtung → nie")
check(urteil(auge(**gut), dict(basis, at=jetzt - 2))[0] is False, "Hedge jünger als 3 s → noch nicht")
check(urteil(auge(**gut, konto={"kontonr": K, "abgekuerzt": False, "liste_offen": True}))[0] is False, "Kontoliste offen → nie")
check(urteil(auge(**gut, konto={"kontonr": K[:-2], "abgekuerzt": True, "liste_offen": False}))[0] is False, "gekürzte Kennung → nie")
check(urteil(auge(**gut, konto={"kontonr": None, "endung": "2225", "liste_offen": False}))[0] is True, "nur Endung …2225, eindeutig unter den TopstepX-Konten der ID → zu")
check(urteil(auge(**gut, konto={"kontonr": None, "endung": "2225", "liste_offen": False}), dict(basis, nachbarn=NB + ["EXPRESS-V2-DLL-1-77772225"]))[0] is False,
      "Endung …2225 bei zwei Konten der ID → nie")
z, e2, g = urteil(auge(pos=True, flach=False))
check(z is False and e2["gesehen"] is True and e2["flach_ts"] == [] and e2["gesehen_ts"] == jetzt * 1000, "Position da → gesehen, Sichtungszeit = Messung, flache Messungen weg")
check(ns["_tsx_wurzel"]("MNQZ6") == "MNQ" and ns["_tsx_wurzel"]("CME_MINI:NQZ2026") == "NQ" and ns["_tsx_wurzel"]("/MNQZ25") == "MNQ", "Wurzel wie tvSymbolWurzel")
z, _, _ = urteil(auge(flach=False, folge=0, seit=None, pos=False, konto={"kontonr": K, "abgekuerzt": False, "liste_offen": False}), dict(basis))
check(z is False, "Positions-Zeile eines anderen Symbols / keine flach-Aussage → nie")
a = auge(**gut)
a["stand"]["positionen"] = [{"symbol": "NQZ6", "menge": 1, "seite": "buy"}]
a["stand"]["flach"] = False
check(urteil(a)[0] is False, "NQ statt MNQ im Konto (keine flach-Aussage des Auges) → nie")

# ── Ticket einmal, Quittung löst, Konto-fest unverändert ──
uhr[0] = 20000.0
eintrag_neu(ticket=777, gesehen=True, at=uhr[0] - 60)
l = ns["scharf_laden"]()
check(len(l) == 1 and l[0].get("quelle") == "tsx" and l[0]["gesehen"] is True, "scharf_setzen ohne TradingView-Reader merkt den Topstep-Eintrag (quelle tsx, gesehen vom Tab)")
check(ns["scharf_konto_fest"]() == [], "scharf_konto_fest: Topstep-Einträge ändern die Puls-Chrome-Neustart-Sperre nicht")
sende = []
orig = ns["_scharf_close_senden"]
ns["_scharf_close_senden"] = lambda e: (sende.append(1), orig(e))[1]
for k in range(4):
    uhr[0] += 0.4
    ns["_scharf_runde"](None, uhr[0], None, auge(flach=True, folge=6 + k, seit=(20000.0 - 3) * 1000, ts=uhr[0] * 1000))
check(len(sende) == 1, f"zu: genau ein Auftrag, solange keine Quittung und < 2 s ({len(sende)})")
cmd = ns["scharf_laden"]()[0]["cmd_id"]
with open(os.path.join(tmp, "hedge_solo_ergebnis.json"), "w") as f:
    json.dump({cmd: {"ok": True}}, f)
uhr[0] += 0.1
ns["_scharf_runde"](None, uhr[0], None, auge(flach=True, folge=12, seit=(20000.0 - 3) * 1000))
check(ns["scharf_laden"]() == [] and len(sende) == 1, "Quittung ok → Eintrag gelöst, kein zweiter Auftrag")
ns["_scharf_close_senden"] = orig
check(ns["_scharf_runde"](None, uhr[0], None, None) == 0, "ohne Auge-Stand (tsx None) und ohne Eintrag: nichts")

# ── Prüfer SOLLTE 1: Master steht 30 s, Auge misst alle 0,25 s, Wache je 0,1 s → hedge_scharf.json höchstens alle 5 s geschrieben ──
uhr[0] = 30000.0
eintrag_neu(ticket=888, at=uhr[0] - 60)
schreib = [0]
orig_sp = ns["scharf_speichern"]
ns["scharf_speichern"] = lambda l: (schreib.__setitem__(0, schreib[0] + 1), orig_sp(l))[1]
mess = uhr[0]
for k in range(300):
    uhr[0] = round(uhr[0] + 0.1, 3)
    if uhr[0] - mess >= 0.25:
        mess = uhr[0]
    ns["_scharf_runde"](None, uhr[0], None, auge(pos=True, ts=mess * 1000, alter=round(uhr[0] - mess, 3)))
ns["scharf_speichern"] = orig_sp
e888 = ns["scharf_laden"]()[0]
check(schreib[0] <= 8 and e888["gesehen"] is True, f"Position steht 30 s: {schreib[0]} Schreibvorgänge (≤ 8, vorher ~120), gesehen bleibt")

# ── Quelltext: Tab meldet tsv2 und beendet den Plan nach dem Panel-Schluss ──
check("if(plan && plan.route === 'tsv2') return (typeof hedgeScharfDatenTsx === 'function') ? hedgeScharfDatenTsx(plan) : null" in HTML,
      "Tab: hedgeScharfDaten liefert für tsv2 die Topstep-Daten (quelle tsx)")
check("quelle: 'tsx', ext_id: ext, wurzel, richtung" in HTML and "nachbarn: tsxKontoExtIdsJetzt()" in HTML, "Tab: Daten mit Plan-Konto, Wurzel, Richtung, TopstepX-Konten der ID")
check("(h.grund === 'master_ende_panel' || (String(h.grund_copier || '') === 'close' && !h.close_at))" in HTML
      and "setInterval(() => { hedgeTsxPanelEndeTick().catch(() => {}) }, 1000)" in HTML,
      "Tab: hedgeTsxPanelEndeTick beendet den Plan nach dem Panel-Schluss (Ring: grund_copier close ohne close_at; Ablauf in selftest_nova_kontinuitaet)")
src_wache = SRC[SRC.index("def _scharf_wache"):SRC.index("def _scharf_wache") + 1600]
check("tsx_stand_ausgabe()" in src_wache and 'x.get("quelle") != "tsx"' in src_wache, "Wache: Auge aus dem Panel-Speicher, Reader nur bei TradingView-Einträgen")

print(f"\n{'ALLES OK' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
sys.exit(1 if FEHLER else 0)
