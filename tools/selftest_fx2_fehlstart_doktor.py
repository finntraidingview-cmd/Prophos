#!/usr/bin/env python3
"""Selbsttest FX2 Fehlstart-Doktor (10.11.2026, Master; Konstrukt FX1). Gehirn (app.py fd_*: Rezepte, Riegel, Protokoll, Aufträge, Nachplanen, Meldungen,
Endpunkte /doktor/*) und Hände am Mac (pc-fernzugriff/mac/doktor.py: feste Befehlsliste, Handelszeit, Akku, nur ausführen nach Riegel-OK). Ohne Netz, DB und
pc.sh nachgebaut — nie ein echter PC.
Aufruf: python3 tools/selftest_fx2_fehlstart_doktor.py"""
import os
import random
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
sys.path.insert(0, os.path.join(WURZEL, "pc-fernzugriff", "mac"))
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402
import doktor  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


DNS = ("Geclaimt vor 5 min, Plan nicht offen — letzte Order-Antwort: Riegel-Prüfung (Gegenrichtung) nicht erreichbar: <urlopen error [Errno 11001] "
       "getaddrinfo failed> — nichts gesendet, der Start wird später erneut versucht.")
KONTO = "Tradovate-Login 'X' nicht geschafft (abgebrochen): ('Error! Failed to login: No active accounts found for this environment.')"
UAC = "Terminal-Verbindung fehlgeschlagen — Windows-Sicherheitsabfrage offen (consent.exe läuft)"

print("1) Rezepte")
R = app.fd_rezept
check(R({"msg": DNS})["key"] == "dns" and R({"msg": KONTO})["key"] == "konto" and R({"msg": UAC})["key"] == "uac"
      and R({"schritt": "auge_blind", "msg": "x"})["key"] == "auge" and R({"schritt": "tab_nicht_erreichbar", "msg": ""})["key"] == "tab"
      and R({"msg": "⚠ Ergebnis UNKLAR — erst nachsehen"})["key"] == "unklar" and R({"msg": DNS, "unklar": True})["key"] == "unklar"
      and R({"msg": "irgendwas Neues"})["key"] == "unbekannt", "DNS, Konto, UAC, Auge, Tab, UNKLAR (Text und Flag), unbekannt")
check(R({"msg": "Terms of Use bitte akzeptieren"})["art"] == "finn" and R({"msg": KONTO})["art"] == "finn", "TopstepX-Dialog und Konto: nur melden")
B = app.fd_befehle
check(B(R({"msg": DNS}), False) == ["dns_test"] and B(R({"msg": UAC}), False) == ["uac_lesen"] and B(R({"msg": UAC}), True) == ["uac_lesen", "mt5_update", "uac_lesen"]
      and B(R({"schritt": "auge_blind"}), False) == [] and B(R({"schritt": "auge_blind"}), True) == ["augen_neu"],
      "Befehle: lesen immer, Reparatur nur mit „reparieren“, UAC danach noch einmal lesen")
check(set(app.FD_BEFEHLE) == set(doktor.BEFEHLE), "Mac und Railway kennen genau dieselben Befehls-Schlüssel")

print("2) Riegel je ID")
JETZT = datetime(2026, 11, 10, 6, 0, tzinfo=timezone.utc)
U = "11111111-1111-1111-1111-111111111111"
LAGE = {}


def sel_riegel(t, p):
    if LAGE.get("fehler"):
        raise RuntimeError("weg")
    if t == "trade_plans" and p.get("status") == "eq.open":
        return [{"id": "x"}] if LAGE.get("open") else []
    if t == "trade_plans" and "and" in p:
        return [{"id": "x"}] if LAGE.get("bald") else []
    if t == "trade_plans" and "start_um_gestartet_at" in p:
        return [{"id": "x"}] if LAGE.get("claim") else []
    if t == "order_signale":
        return [{"id": "x"}] if LAGE.get("signal") else []
    return []


app.sb_select = sel_riegel
F = app.fd_riegel
ok = F(U, JETZT) == ""
for k, t in (("open", "offener Trade"), ("bald", "≤ 10 min"), ("claim", "Puls läuft"), ("signal", "Order-Signal"), ("fehler", "unklar")):
    LAGE.clear(); LAGE[k] = True
    ok &= t in F(U, JETZT)
LAGE.clear()
check(ok and "unklar" in F("", JETZT), "frei nur ohne offenen Trade, Start ≤ 10 min, Claim, offenes Signal; Lesefehler/keine ID = unklar (fail-closed)")

print("3) Urteil nach den Mac-Befehlen")
E = app.fd_ergebnis_urteil
check(E("dns", [{"key": "dns_test", "rc": 0, "text": "dns_ok"}]) == ("behoben", "DNS antwortet am PC wieder", False, True)
      and E("dns", [{"key": "dns_test", "rc": 0, "text": "dns_fehlt"}])[2] is True, "DNS: antwortet → behoben + nachplanen; sonst braucht Finn")
check(E("dns", [{"key": "dns_test", "rc": 1, "text": "== PC von X (pc-a) offline im Tailnet"}]) == ("fertig", "PC über den Lotsen nicht erreichbar — nichts entschieden", False, False)
      and E("uac", [{"key": "uac_lesen", "rc": 255, "text": "ssh: connect to host 100.1.2.3 port 22: Connection timed out"}])[2] is False
      and E("auge", [])[2] is False and E("dns", [{"key": "dns_test", "rc": 0, "text": "???"}])[2] is False,
      "Lotse erreicht den PC nicht / Ausgabe unklar → nichts entschieden, kein „braucht dich“ aus einem Verbindungsfehler")
check(E("uac", [{"key": "uac_lesen", "rc": 0, "text": "consent=1"}, {"key": "mt5_update", "rc": 0, "text": "OK"}, {"key": "uac_lesen", "rc": 0, "text": "consent=0"}])[0] == "behoben"
      and E("uac", [{"key": "uac_lesen", "rc": 0, "text": "consent=1"}])[2] is True, "UAC: nach der Update-Aufgabe weg → behoben; offen → braucht Finn („Ja“)")
check(E("auge", [{"key": "augen_neu", "rc": 0, "text": "Augen (cdp) gelesen"}])[0] == "behoben" and E("auge", [{"key": "augen_neu", "rc": 1, "text": ""}])[2] is True,
      "Auge: neu gelesen → behoben, sonst braucht Finn")

print("4) Nachplanen")
NU = app.fd_nachplan_urteil
p0 = {"status": "planned", "started_at": None, "orbit_gesendet_at": None, "start_um": (JETZT - timedelta(minutes=40)).isoformat(),
      "mt5_baseline": {"start_fehler": {"versuche": 1}}}
check(NU(p0, JETZT)[0] is True and NU(dict(p0, start_um=(JETZT - timedelta(minutes=5)).isoformat()), JETZT)[0] is False
      and NU(dict(p0, start_um=(JETZT - timedelta(minutes=5)).isoformat(), mt5_baseline={"start_fehler": {"versuche": 3}}), JETZT)[0] is True,
      "nur wenn der Tab ihn nicht mehr selbst neu startet (Start hängt > 30 min oder 3 Fehlversuche)")
check(NU(dict(p0, orbit_gesendet_at="x"), JETZT)[0] is False and NU(dict(p0, mt5_baseline={"puls_unklar": {"at": "x"}}), JETZT)[0] is False
      and NU(dict(p0, status="open"), JETZT)[0] is False and NU(dict(p0, start_um=(JETZT - timedelta(days=1)).isoformat()), JETZT)[0] is False,
      "nie nach Senden, nie bei UNKLAR, nie offen, nie vom Vortag")
UPD = []
PLAN = dict(p0, id="p-1", user_id=U, updated_at="u1")
ANDERE = [{"start_um": (JETZT + timedelta(minutes=20)).isoformat()}]


def sel_plan(t, p):
    if t == "trade_plans" and p.get("id") == "eq.p-1":
        return [dict(PLAN)]
    if t == "trade_plans":
        return list(ANDERE)
    return []


app.sb_select = sel_plan
app.sb_update = lambda t, f, u: UPD.append((t, f, u)) or [u]
RPC = []
app._sb_anfrage = lambda *a, **k: RPC.append(k.get("json"))
txt = app.fd_nachplanen("p-1", JETZT, random.Random(3))
neu = app._ap_ts(UPD[0][2]["start_um"]) if UPD else None
check(neu and 15 * 60 <= (neu - JETZT).total_seconds() and abs((neu - app._ap_ts(ANDERE[0]["start_um"])).total_seconds()) >= 300
      and UPD[0][1] == {"id": "eq.p-1", "status": "eq.planned", "started_at": "is.null", "orbit_gesendet_at": "is.null", "updated_at": "eq.u1"}
      and UPD[0][2]["start_um_gestartet_at"] is None and RPC and RPC[0]["p_key"] == "start_fehler" and RPC[0]["p_patch"]["status"] == "neu"
      and txt.startswith("nachgeplant auf"), f"Supabase-Nachplanen: ≥ 15 min, ≥ 5 min zu anderen Starts der ID, Claim zurück, start_fehler neu ({txt})")

print("5) Voller Lauf (Gehirn)")
E_ = "33333333-3333-3333-3333-333333333333"
DB = {"fehl": [], "proto": [], "regel": {"id": 1, "an": True, "reparieren": True, "stand_at": None, "bericht_tag": None}, "alarm": [], "log": [], "upd": [], "lage": {}}


def sel(t, p):
    if t == "fehlstart_doktor_regel":
        return [dict(DB["regel"])]
    if t == "puls_fehlstarts":
        return [dict(x) for x in DB["fehl"]]
    if t == "fehlstart_doktor" and "fehlstart_id" in p:
        return [{"fehlstart_id": z["fehlstart_id"]} for z in DB["proto"]]
    if t == "fehlstart_doktor" and p.get("status") == "in.(wartet_mac,laeuft)":
        return [{"pc": z["pc"]} for z in DB["proto"] if z["status"] in ("wartet_mac", "laeuft")]
    if t == "fehlstart_doktor" and "braucht_finn" in p:
        return [z for z in DB["proto"] if z.get("braucht_finn") and z.get("pc") == p["pc"][3:]]
    if t == "fehlstart_doktor" and p.get("status") == "eq.wartet_mac":
        return [dict(z, id=i) for i, z in enumerate(DB["proto"]) if z["status"] == "wartet_mac"]
    if t == "fehlstart_doktor" and "id" in p:
        i = int(p["id"][3:])
        return [dict(DB["proto"][i], id=i)] if 0 <= i < len(DB["proto"]) else []
    if t == "alarm_log":
        return [{"id": 1}] if any(k == p["schluessel"][3:] for k in DB["log"]) else []
    if t == "trade_plans" and p.get("status") == "eq.open":
        return [{"id": "x"}] if DB["lage"].get(p["user_id"][3:]) == "open" else []
    return []


def upd(t, f, u):
    DB["upd"].append((t, f, u))
    if t == "fehlstart_doktor" and f.get("id"):
        i = int(f["id"][3:])
        if f.get("status") and DB["proto"][i]["status"] != f["status"][3:]:
            return []
        DB["proto"][i].update(u)
        return [u]
    if t == "fehlstart_doktor_regel":
        DB["regel"].update(u)
    return [u]


def alarm(*a, **k):
    DB["alarm"].append((a, k))
    DB["log"].append(k.get("schluessel"))
    return 1, 1


app.sb_select, app.sb_update = sel, upd
app.sb_insert = lambda t, z: DB["proto"].append(dict(z)) or z
app.alarm_senden = alarm
app.admin_gruppen_daten = lambda: {"gruppen": [{"id": "ht", "verwalter_id": None}, {"id": "e", "verwalter_id": E_}],
                                   "mitglieder": [{"user_id": U, "gruppe_id": "ht"}, {"user_id": "22222222-2222-2222-2222-222222222222", "gruppe_id": "ht"},
                                                  {"user_id": E_, "gruppe_id": "e"}]}
app._pc_namen_daten = lambda: {"pc-aaaa01": {"name": "HT-1"}, "pc-bbbb02": {"name": "HT-2"}}
U2 = "22222222-2222-2222-2222-222222222222"
t0 = (JETZT - timedelta(minutes=20)).isoformat()
DB["fehl"] = [{"id": 1, "at": t0, "user_id": U, "plan_id": "p-1", "pc": "pc-aaaa01", "schritt": "m5still", "msg": DNS},
              {"id": 2, "at": t0, "user_id": U, "plan_id": "p-2", "pc": "pc-aaaa01", "schritt": "m5still", "msg": DNS},         # 2. Auftrag am selben PC → nur Protokoll
              {"id": 3, "at": t0, "user_id": U2, "plan_id": "p-3", "pc": "pc-bbbb02", "schritt": "konto", "msg": KONTO},
              {"id": 4, "at": t0, "user_id": U2, "plan_id": "p-4", "pc": "pc-bbbb02", "schritt": "x", "msg": UAC},              # offener Trade → Riegel
              {"id": 5, "at": t0, "user_id": E_, "plan_id": "p-5", "pc": "pc-eeee05", "schritt": "x", "msg": DNS}]              # Emins Gruppe → nie
DB["lage"] = {U2: "open"}
app.fd_riegel = (lambda _orig: (lambda uid, j: "offener Trade auf diesem PC" if DB["lage"].get(uid) == "open" else ""))(app.fd_riegel)
e = app.fd_tick(JETZT)
st = {z["fehlstart_id"]: z for z in DB["proto"]}
check(st[1]["status"] == "wartet_mac" and st[1]["befehle"] == ["dns_test"] and st[2]["status"] == "nichts" and 5 not in st,
      "DNS: ein Auftrag je PC für den Mac, zweiter Fall am selben PC nur protokolliert; Emins Gruppe nie angefasst")
check(st[3]["status"] == "gemeldet" and st[3]["braucht_finn"] and st[4]["status"] == "gesperrt" and "offener Trade" in st[4]["ergebnis"],
      "Konto: braucht Finn; UAC bei offenem Trade: Riegel, nichts am PC")
check(len(DB["alarm"]) == 1 and DB["alarm"][0][0][0] == 2 and "Braucht dich: PC von HT-2 (pc-bbbb02)" in DB["alarm"][0][0][2]
      and "1) Login/Konto" in DB["alarm"][0][0][3], "🟠 einmal je PC und Tag, mit Namen und Liste")
check(DB["regel"]["stand_at"] == t0 and e["neu"] == 4 and e["auftraege"] == 1, f"Stand fortgeschrieben, Zähler stimmen ({e})")
DB["alarm"].clear()
app.fd_tick(JETZT)
check(len(DB["proto"]) == 4 and not DB["alarm"], "zweiter Lauf: nichts doppelt, keine zweite Meldung")
DB["regel"]["an"] = False
check(app.fd_tick(JETZT) == {"aus": True}, "Schalter aus → nichts")
DB["regel"]["an"] = True

print("6) Endpunkte für den Mac")
c = app.app.test_client()
os.environ.pop("DOKTOR_KEY", None)
check(c.get("/doktor/auftraege").status_code == 503, "ohne DOKTOR_KEY auf Railway: 503, der Mac tut nichts")
os.environ["DOKTOR_KEY"] = "k" * 32
check(c.get("/doktor/auftraege", headers={"X-Doktor-Key": "falsch"}).status_code == 403, "falscher Schlüssel: 403")
H = {"X-Doktor-Key": "k" * 32}
a = c.get("/doktor/auftraege", headers=H).get_json()
check(a["an"] and [x["pc"] for x in a["auftraege"]] == ["pc-aaaa01"] and a["auftraege"][0]["befehle"] == ["dns_test"], "Aufträge: einer je PC, nur Listen-Schlüssel")
aid = a["auftraege"][0]["id"]
DB["lage"][U] = "open"
r = c.post("/doktor/auftrag/start", json={"id": aid}, headers=H).get_json()
check(r["ok"] is False and DB["proto"][aid]["status"] == "gesperrt", "Riegel direkt vor der Ausführung (offener Trade) → gesperrt, der Mac führt nichts aus")
DB["proto"][aid].update(status="wartet_mac")
DB["lage"].pop(U)
r = c.post("/doktor/auftrag/start", json={"id": aid}, headers=H).get_json()
check(r["ok"] and r["befehle"] == ["dns_test"] and DB["proto"][aid]["status"] == "laeuft", "frei → läuft, Befehle zurück")
check(c.post("/doktor/auftrag/start", json={"id": aid}, headers=H).status_code == 409, "zweimal starten geht nicht (Guard)")
NACH = []
app.fd_nachplanen = lambda pid, j, rnd=None: NACH.append(pid) or "nachgeplant auf 10:20 Dubai"
r = c.post("/doktor/auftrag/ergebnis", json={"id": aid, "ausgabe": [{"key": "dns_test", "rc": 0, "text": "dns_ok"}, {"key": "boese", "rc": 0, "text": "x"}]},
           headers=H).get_json()
check(r["status"] == "behoben" and NACH == ["p-1"] and DB["proto"][aid]["aktion"] == "dns_test" and "nachgeplant" in DB["proto"][aid]["ergebnis"],
      "Ergebnis DNS ok → behoben + nachgeplant; fremde Schlüssel in der Ausgabe verworfen")

print("7) Tagesbericht")
DB["alarm"].clear()
abend = datetime(2026, 11, 10, 16, 40, tzinfo=timezone.utc)      # 20:40 Dubai
app.sb_select = lambda t, p: [{"pc": "pc-aaaa01", "user_id": U, "status": "behoben", "braucht_finn": False},
                              {"pc": "pc-bbbb02", "user_id": U2, "status": "gemeldet", "braucht_finn": True}] if t == "fehlstart_doktor" else []
check(app.fd_bericht(abend, DB["regel"]) and DB["alarm"] and DB["alarm"][0][0][0] == 3 and "Fehlstarts heute: 2 · selbst behoben: 1 · brauchen dich: 1" in DB["alarm"][0][0][3],
      "⚪ ab 20:30 Dubai mit drei Zahlen und den PCs")
check(app.fd_bericht(abend, DB["regel"]) is False and app.fd_bericht(datetime(2026, 11, 10, 15, 0, tzinfo=timezone.utc), {}) is False,
      "einmal je Tag, nicht vor 20:30")

print("8) Hände am Mac")
check(doktor.handelszeit(datetime(2026, 11, 10, 3, 0, tzinfo=timezone.utc)) and not doktor.handelszeit(datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc))
      and doktor.handelszeit(datetime(2026, 11, 15, 22, 30, tzinfo=timezone.utc)) and not doktor.handelszeit(datetime(2026, 11, 13, 22, 30, tzinfo=timezone.utc)),
      "Handelszeit So 22:00 – Fr 22:00 UTC")
check(doktor.akku_urteil("Now drawing from 'AC Power'\n -InternalBattery-0 15%; charging", 1)[0] is True
      and doktor.akku_urteil("Now drawing from 'Battery Power'\n -InternalBattery-0 15%; discharging", 5)[0] is False
      and doktor.akku_urteil("Now drawing from 'Battery Power'\n -InternalBattery-0 80%; discharging", 3)[0] is False
      and doktor.akku_urteil("Now drawing from 'Battery Power'\n -InternalBattery-0 80%; discharging", 5)[0] is True,
      "Netzteil immer; Akku < 20 % nie; Akku sonst nur jeder 5. Lauf")
AUFRUFE = []


class R_:
    def __init__(self, out):
        self.stdout, self.stderr, self.returncode = out, "", 0


doktor.pc_sh = lambda: "/x/pc.sh"
lf = lambda argv: AUFRUFE.append(argv) or R_("== PC\ndns_ok")   # noqa: E731
check(doktor.befehl_ausfuehren("pc-aaaa01", "rm -rf", lf)["rc"] == -1 and not AUFRUFE, "unbekannter Befehl: nie ausgeführt")
SCHLAF = []
HTTP = {"GET /doktor/auftraege": {"ok": True, "an": True, "auftraege": [{"id": 7, "pc": "pc-aaaa01"}, {"id": 8, "pc": "pc-bbbb02"}]}}
GESENDET = []


def http_f(m, pfad, key, body=None, timeout=20):
    GESENDET.append((m, pfad, body))
    if pfad == "/doktor/auftrag/start":
        return {"ok": True, "pc": "pc-aaaa01", "befehle": ["uac_lesen", "mt5_update", "uac_lesen"]} if body["id"] == 7 else {"ok": False, "grund": "Start in ≤ 10 min"}
    if pfad == "/doktor/auftrag/ergebnis":
        return {"ok": True, "status": "behoben"}
    return HTTP.get(f"{m} {pfad}", {})


erg = doktor.lauf("k" * 32, laeufer=lf, schlafen=lambda s: SCHLAF.append(s), http_f=http_f)
gesendet_erg = [b for m, p, b in GESENDET if p == "/doktor/auftrag/ergebnis"]
check(len(AUFRUFE) == 3 and all(a[2] == "pc-aaaa01" and a[4] == doktor.BEFEHLE[k] for a, k in zip(AUFRUFE, ["uac_lesen", "mt5_update", "uac_lesen"]))
      and len(SCHLAF) == 1 and 25 <= SCHLAF[0] <= 40 and len(gesendet_erg) == 1 and gesendet_erg[0]["id"] == 7,
      "Mac: nur nach Start-OK, nur Listen-Befehle in Reihenfolge, nach dem Update gestreut warten; Auftrag 8 (Riegel) bleibt unberührt")
src = open(os.path.join(WURZEL, "pc-fernzugriff", "mac", "doktor-installieren.sh"), encoding="utf-8").read()
dsrc = open(os.path.join(WURZEL, "pc-fernzugriff", "mac", "doktor.py"), encoding="utf-8").read()
plist = src[src.index("<plist"):src.index("</plist>")]
check("<key>StartInterval</key><integer>120</integer>" in plist and "KeepAlive" not in plist and "caffeinate" not in plist
      and '"caffeinate"' not in dsrc and "'caffeinate'" not in dsrc and "pmset -a" not in dsrc + src and "pmset -g batt" not in plist,
      "launchd: alle 120 s, kein KeepAlive, nirgends caffeinate (hält den Mac nie wach)")
asrc = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
check("_fd_takt()                            # FX2" in asrc, "Takt in ap_loop")

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
