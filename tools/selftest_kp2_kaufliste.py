"""Selbsttest KP2 Kaufliste (25.11.2026): Deckel „max. laufend“ + FNF-Freischaltung + Apex-5er-Pack im Vorrat-Lauf, Kauflisten-Zeilen,
Finns Regel „erwarteter Stand ≥ Ziel → nichts kaufen“ mit der echten Lauf-Rechnung, Fremd-Anlegen über /admin/konto-anlegen. Ohne Netz: holt die reinen Funktionen per AST aus app.py (kompiliert dabei die ganze Datei = Syntax-Check) und
importiert kaufliste_app mit einem Stub für kapital_app.

Aufruf:  python3 tools/selftest_kp2_kaufliste.py   (Abbruch beim ersten Fehler, Exit-Code 1)
"""
import ast
import os
import sys
import types

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
ok_n = 0


def pruef(bed, text):
    global ok_n
    if not bed:
        print("✗", text)
        sys.exit(1)
    ok_n += 1
    print("✓", text)


# ── 1. app.py: ganze Datei kompilieren, reine KP2-Teile herausholen ──
quelle = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
baum = ast.parse(quelle)
compile(baum, "app.py", "exec")
pruef(True, "app.py kompiliert")
teile = []
for knoten in baum.body:
    if isinstance(knoten, ast.FunctionDef) and knoten.name == "vorrat_kauf_deckel":
        teile.append(knoten)
    if isinstance(knoten, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ("VORRAT_LAUFEND_TYPEN", "VORRAT_FNF_SPERRE", "VORRAT2_STD", "VORRAT2_RECHEN_STAND")
                                              for t in knoten.targets):
        teile.append(knoten)
ns = {}
exec(compile(ast.Module(body=teile, type_ignores=[]), "app.py(kp2)", "exec"), ns)
deckel, STD = ns["vorrat_kauf_deckel"], ns["VORRAT2_STD"]
pruef(ns["VORRAT2_RECHEN_STAND"] >= 9, "RECHEN_STAND hochgezählt (GET rechnet alte Läufe einmal neu)")
ml = STD["max_laufend"]
pruef(ml["Tradeify"] == 4 and ml["Apex Trader"] == 5 and ml["FTMO"] == 2 and ml["FundedNext"] == 2 and ml["FundingPips"] == 2
      and ml["The5%ers"] == 3 and ml["Topstep"] == 3 and ml["Lucid Trading"] == 3 and ml["FTMO Futures"] == 3
      and ml["FundedNext Futures"] == 3 and ml["Tradeify CFD"] == 3 and ml["Blue Guardian"] == 3 and ml["Audacity"] == 2,
      "Finns Werte max. laufend je Firma (KP1c)")

K = lambda stufe, bestand=False: {"stufe": stufe, "im_bestand": bestand}
# neue ID, 0 Konten: Lücke 10 → genau Max
pruef(deckel(10, [], "Tradeify", STD)["n"] == 4, "Tradeify neu: min(10, 4 − 0) = 4")
pruef(deckel(10, [], "Apex Trader", STD)["n"] == 5, "Apex neu: 5")
pruef(deckel(10, [], "FTMO", STD)["n"] == 2, "FTMO neu: 2")
# laufende zählen, Funded/Bestand nicht
d = deckel(10, [K("challenge"), K("challenge"), K("funded"), K("funded_cfd", True)], "Tradeify", STD)
pruef(d["laufend"] == 2 and d["n"] == 2, "Tradeify 2 Challenges laufen, Funded zählt nicht → 2")
pruef(deckel(10, [K("phase1"), K("phase2")], "FundedNext", STD)["n"] == 0, "FundedNext 2/2 laufend → 0")
pruef(deckel(10, [K("phase1")] * 5, "FundedNext", STD)["n"] == 0, "mehr laufend als Max → nie negativ")
pruef(deckel(1, [], "Tradeify", STD)["n"] == 1, "Lücke kleiner als Max → Lücke (1)")
pruef(deckel(0, [], "Tradeify", STD)["n"] == 0, "Lücke 0 → 0")
pruef(deckel(None, [], "Tradeify", STD)["n"] is None, "n_roh None (Sperre) bleibt None")
pruef(deckel(10, [], "Unbekannt GmbH", STD)["max"] == 3, "unbekannte Firma → max_laufend_std 3")
# FNF-Freischaltung
d = deckel(10, [], "FundedNext Futures", STD, fn_payout_ok=False)
pruef(d["n"] == 0 and d["sperre"] == "ab 1. FN-Payout", "FNF ohne FN-Payout → 0 + Sperre")
d = deckel(10, [], "FundedNext Futures", STD, fn_payout_ok=True)
pruef(d["n"] == 3 and d["sperre"] is None, "FNF mit FN-Payout → 3")
pruef(deckel(10, [], "FundedNext", STD, fn_payout_ok=False)["n"] == 2, "Sperre gilt nur für FNF, nicht für FundedNext CFD")

# Lauf-Verdrahtung im Quelltext: Deckel vor dem Totband, Felder an GET durchgereicht
i_dk, i_tb = quelle.find("dk = vorrat_kauf_deckel(nr"), quelle.find("tb = vorrat_totband(nr, vorher.get((uid, f))")
pruef(0 < i_dk < i_tb, "Deckel sitzt im Lauf vor vorrat_totband")
pruef("laufend_n=s.get(\"laufend_n\")" in quelle and "reserve=bool(s.get(\"reserve\"))" in quelle, "GET /admin/vorrat reicht laufend/max/sperre/reserve durch")
pruef("import kaufliste_app" in quelle and "kaufliste_app.registrieren(app, globals())" in quelle, "Modul in app.py registriert")

# Apex 5er-Pack (Finn 25.11.2026): erwartet < Ziel → genau 1 Pack (5), egal wie viele laufen; offenes Pack (laufend ohne Lesung) → 0
pruef(STD["kauf_pack"]["Apex Trader"] == 5, "Apex Kaufeinheit 5er-Pack")
KL_ = lambda stufe, gelesen=True: {"stufe": stufe, "im_bestand": False, "balance_at": "2026-11-25T10:00:00Z" if gelesen else None}
d = deckel(1, [KL_("challenge"), KL_("challenge")], "Apex Trader", STD, True, 6000, 10000)
pruef(d["n"] == 5 and d["pack"] == 5, "Apex: 2 laufen, erwartet 6k < 10k → 1 Pack = 5")
pruef(deckel(0, [], "Apex Trader", STD, True, 6000, 10000)["n"] == 5, "Apex: Lauf sagt 0 (25 %), erwartet < Ziel → trotzdem 1 Pack")
pruef(deckel(3, [], "Apex Trader", STD, True, 10500, 10000)["n"] == 0, "Apex: erwartet ≥ Ziel → 0")
pruef(deckel(3, [KL_("challenge", gelesen=False)], "Apex Trader", STD, True, 6000, 10000)["n"] == 0, "Apex: letztes Pack noch nicht gelesen → 0")
pruef(deckel(3, [], "Apex Trader", STD, True, 6000, 10000, frei=False)["n"] == 0, "Apex pausiert/gesperrt → 0")
pruef(deckel(3, [], "Apex Trader", STD)["n"] == 5, "Apex ohne erwartet/Ziel: Kaufzahl des Laufs > 0 → 1 Pack")
pruef(deckel(10, [], "Tradeify", STD)["pack"] is None, "andere Firmen: kein Pack")

# ── 2. kaufliste_app: Zeilen ──
stub = types.ModuleType("kapital_app")
stub._sb = lambda *a, **k: []
stub._gate = lambda: (None, None)
sys.modules["kapital_app"] = stub
sys.path.insert(0, WURZEL)
import kaufliste_app as KL  # noqa: E402

zellen = [
    {"user_id": "u1", "firma": "Tradeify", "status": "frei", "nachkauf": {"n": 3, "dringlichkeit": "jetzt", "einheit": "150k", "preis_eur": 213},
     "score": 90, "laufend_n": 1, "max_laufend": 4, "reserve": False},
    {"user_id": "u1", "firma": "FTMO", "status": "frei", "nachkauf": {"n": 0}},
    {"user_id": "u2", "firma": "Topstep", "status": "frei", "nachkauf": {"n": 2, "dringlichkeit": "bald"}, "score": 50, "reserve": True, "max_laufend": 3},
    {"user_id": "u2", "firma": "FTMO", "status": "frei", "nachkauf": {"n": 2, "dringlichkeit": "jetzt"}, "score": 99},
    {"user_id": "u2", "firma": "FundedNext Futures", "status": "frei", "nachkauf": {"n": 3}, "kauf_sperre": "ab 1. FN-Payout"},
    {"user_id": "u3", "firma": "FTMO", "status": "gesperrt", "nachkauf": {"n": 2}},
    {"user_id": "u3", "firma": "Apex Trader", "status": "frei", "nachkauf": {"n": None}},
]
z = KL.zeilen_aus_vorrat(zellen, None, {"u1": "Aurel", "u2": "Carsten"})
pruef([x["firma"] for x in z] == ["Tradeify", "Topstep"], "nur n > 0, frei, ohne Sperre, mit KP2-Deckel (max_laufend); jetzt vor bald")
pruef(z[0]["name"] == "Aurel" and z[0]["laufend"] == 1 and z[0]["max"] == 4 and z[0]["einheit"] == "150k", "Name + laufend/max + Einheit")
pruef(z[1]["reserve"] is True, "Reserve-Kennzeichen durchgereicht")
pruef([x["firma"] for x in KL.zeilen_aus_vorrat(zellen, "u2")] == ["Topstep"], "normale ID sieht nur eigene Zeilen")

pruef(not hasattr(KL, "row_pruefen") and "/admin/kaufliste/anlegen" not in open(os.path.join(WURZEL, "kaufliste_app.py"), encoding="utf-8").read(),
      "keine zweite Anlege-Route — fremde IDs über /admin/konto-anlegen")
fe = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
pruef("/admin/konto-anlegen?ansicht=admin" in fe and "bulkKlFremdAnlegen" in fe, "Frontend legt fremde IDs über /admin/konto-anlegen an (Verwalter: ansicht=admin)")

# KP2d „Später": Prüfung des Bodys + pausierte Zellen
U = "11111111-2222-4333-8444-555555555555"
pruef(KL.spaeter_pruefen({"user_id": U, "firma": "Tradeify", "anzahl": 2, "tage": 7})[0] == (U, "Tradeify", 2, 7), "Später: gültig (2 Konten, 7 Tage)")
pruef(KL.spaeter_pruefen({"user_id": U, "firma": "Tradeify", "anzahl": 1})[0][3] == 7, "Später: Standard 7 Tage")
for kaputt, txt in ((dict(tage=5), "nur 3/7/30 Tage"), (dict(anzahl=0), "anzahl ≥ 1"), (dict(anzahl=21), "anzahl ≤ 20"), (dict(anzahl=True), "anzahl kein bool"),
                    (dict(user_id="x"), "user_id uuid"), (dict(firma=""), "firma Pflicht")):
    pruef(KL.spaeter_pruefen(dict({"user_id": U, "firma": "Tradeify", "anzahl": 1, "tage": 7}, **kaputt))[1] is not None, f"Später abgewiesen: {txt}")
pz = [{"user_id": "u1", "firma": "Tradeify", "status": "pausiert"}, {"user_id": "u2", "firma": "The5%ers", "status": "pausiert"},
      {"user_id": "u1", "firma": "FTMO", "status": "frei"}]
pruef([x["firma"] for x in KL.pausiert_aus_vorrat(pz, None, {"u1": "Aurel", "u2": "Carsten"})] == ["Tradeify", "The5%ers"], "pausierte Zellen (Admin: alle)")
pruef([x["firma"] for x in KL.pausiert_aus_vorrat(pz, "u2")] == ["The5%ers"], "pausierte Zellen (normale ID: nur eigene)")
kq = open(os.path.join(WURZEL, "kaufliste_app.py"), encoding="utf-8").read()
pruef('"kaufliste_spaeter"' in kq and "vorrat_bestellt" not in kq.split("def registrieren")[1], "Später schreibt kaufliste_spaeter, nie vorrat_bestellt (keine Rechenwirkung)")
pruef("data-kl-spaeter" in fe and "data-kl-weg" not in fe and "const spaeterN = z =>" in fe, "Frontend: „Später“ statt „Erledigt“, ausgeblendete Zeilen je Zelle abgezogen")
sq = open(os.path.join(WURZEL, "sql", "2026-11-25_kp2d_kaufliste_spaeter.sql"), encoding="utf-8").read()
pruef("enable row level security" in sq and "revoke all on public.kaufliste_spaeter from anon, authenticated" in sq, "SQL: RLS an, anon/authenticated entzogen")

# KP2d Zusatz: Mehrfachauswahl nur gleiche Vorlage; „Alle IDs" nur unter Admin → Alle Accounts (nie unter Accounts)
fe = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
pruef("data-kl-alle" not in fe and 'id="kl-seg"' not in fe, "Accounts ohne Umschalter „Meine | Alle IDs“")
i_k = fe.index('id="adm-pane-konten"'); i_a = fe.index('id="kl-admin-karte"'); i_n = fe.index('id="adm-konten-msg"')
pruef(i_k < i_a < i_n, "Kaufliste aller IDs steht unter Admin → Alle Accounts (vor der Tabelle)")
pruef("window._klAdminOeffnen?.()" in fe and "alle: true, tacho: false" in fe and "pa1Stand(cfg.alle ? { alle: true } : undefined)" in fe,
      "Admin-Ort lädt alle=1 und die Puls-Stände aller IDs, Accounts nur die eigene ID")
pruef("const klVKey = z => z.vorlage ? 'v' + z.vorlage.id" in fe and "nur gleiche Vorlage" in fe and "data-kl-id=" in fe,
      "Kästchen anderer Vorlage gesperrt (Firma × Größe × Phase), IDs auf-/zuklappbar")

# Finn zu „Gekauft": Futures → PA1 ohne Fenster (sofort grün + Countdown), CFD → direkt das Anlegen-Fenster; „Später" mit Uhr-Symbol
pruef("const futures = klFutures(b.z.firma)" in fe and "if(typeof tpFirmIstFutures === 'function') return !!tpFirmIstFutures(f)" in fe
      and "const r = await window.pa1Gekauft({ user_id: b.z.user_id, firma: b.z.firma, vorlage_id: vid, anzahl: b.n })" in fe,
      "Gekauft: nur Futures gehen an PA1, CFD direkt ins Anlegen-Fenster")
pruef("Puls prüft in ${" in fe and "pa.knopf.art !== 'gruen'" in fe, "grüner Knopf mit Countdown bis zur Puls-Prüfung")
pruef("KL_UHR" in fe and "7 Tage ausblenden (alle Zeilen, auch neue), danach wieder da" in fe, "„Später“ mit Uhr-Symbol und Tooltip")
# KP2f: „Später" je ID × Firma — ganze Zelle weg (auch neue Zeilen), alte Einträge mit kleinerer anzahl zählen als ganze Firma, Tacho ruhig „später bis …"
pruef("const spaeterN = z => spaeterBis(z) ? z.n : 0" in fe, "Später blendet die ganze Firma der ID aus (unabhängig von anzahl)")
pruef("später bis ${datum(bis)}" in fe and "kaufen` : `später bis" in fe, "Tacho: „später bis TT.MM.“ statt „+n kaufen“")
pruef("· keine Kaufvorschläge</span>" in fe and "new Set(sp.map(s => s.user_id + '|' + s.firma)).size" in fe, "Abschnitt „n später“ zählt Firmen, nicht Konten")

# PA1b: ein Auftrag je ID × Firma mit posten[] — Zuordnung über vorlage_id ∈ posten[], Slots je Vorlage = posten.anzahl
pruef("const posten = Array.isArray(a.posten) && a.posten.length ? a.posten : [{ vorlage_id: a.vorlage_id, anzahl: a.anzahl }]" in fe
      and "String(x.vorlage_id) === String(vid)" in fe, "PA1b: Knopf-Stand über posten[] je Vorlage")

# KP2g (Finn: „1/3 laufend sieht unnötig aus", Demo abgenommen): Firmen-Kopf je ID × Firma, ruhige Konto-Zeilen ohne Chips
pruef("const firmenKopf = (z, l) =>" in fe and "kaufen · ${lauf} ${lauf === 1 ? 'läuft' : 'laufen'}" in fe and "data-kl-firma-wahl" in fe,
      "Firmen-Kopf: Farbpunkt · Firma · „n kaufen · m laufen · Ist / Soll“ · Kästchen für alle Zeilen der Firma")
pruef("→ ${lauf}/${z.max} laufend" not in fe and 'class="kl-chip res"' not in fe and "kl-fk-res" in fe, "kein „1/3 laufend“-Chip mehr, Reserve nur als Punkt am Kopf")
pruef(KL.zeilen_aus_vorrat([dict(zellen[0], bestand_echt=5000)], None, {})[0]["bestand"] == 5000, "Zeilen liefern den Bestand für „Ist / Soll“")

# KP2i (Bug live .2334: Futures-„Gekauft“ öffnete das Fenster ohne /konto-suche)
fe = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
pruef("if(!neu && vorlagen.liste && vorlagen.liste.length &&" in fe, "leere Vorlagen-Liste wird nie gemerkt (Abfrage vor dem Login)")
pruef("const liste = await klVorlagen(true)" in fe and "if(futures && !manuell){" in fe, "fehlt die Vorlage an der Zeile: frisch holen, dann Futures → PA1")
pruef("klToast(`${b.z.firma}: ${grund} — bitte von Hand anlegen`)" in fe, "Futures fällt nie still ins Fenster — Grund als Toast")
pruef("const LP_MS = 1500, LP_ABBRUCH_MS = 350" in fe and "t: setTimeout(fertig, still ? LP_MS : LP_MS + 400)" in fe and "if(ev.animationName === 'kl-lp-fill' && lp && Date.now() - lp.start >= LP_MS - 200) fertig()" in fe and "void el.offsetWidth; el.classList.add('kl-lp')" in fe and "hinzufuegen(rids, { manuell: true })" in fe and "'pointerdown'" in fe,
      "KP2k: 1,5 s gedrückt halten (Maus + Touch) = Anlegen-Fenster von Hand")
pruef("if(schlucken || Date.now() - lp.start >= LP_ABBRUCH_MS) lpSchluck = Date.now()" in fe and "Date.now() - lpSchluck < 1000" in fe,
      "KP2k: vorher loslassen (ab 0,35 s) = nichts; geschluckt wird nur der Klick direkt danach")
pruef("lp.el.contains(e.target) && !lp.el.contains(e.relatedTarget)) lpStop(true)" in fe and "addEventListener('pointercancel', () => lpStop(true))" in fe,
      "KP2k: vom Knopf wegziehen / Scrollen bricht ab")
pruef(".kl-lp::after{" in fe and "@keyframes kl-lp-fill" in fe and "@media (prefers-reduced-motion:reduce){.kl-lp::after{animation:none" in fe,
      "KP2k: Füllbalken im Knopf (CSS), ohne Bewegung bei prefers-reduced-motion")
pruef('data-kl-zurueck="${klEsc(rid)}"' in fe and "pa.knopf.art === 'gruen' && rid" in fe and "const zr = e.target.closest('[data-kl-zurueck]'); if(zr){ zuruecknehmen(zr); return }" in fe,
      "KP2k: grüner Knopf = Zurücknehmen (nur grün; andere Stände bleiben Anzeige)")
blk = fe[fe.index("async function zuruecknehmen(knopf){"):fe.index("const slotsVon_ = z => pa1Slots(z)")]
pruef("window.pa1Zurueck({ user_id: z.user_id, firma: z.firma, vorlage_id: vid, anzahl: n })" in blk and "klToast(`${z.firma}: ${(r && r.msg) || 'nicht zurückgenommen'}`)" in blk
      and "I.pa1Lokal = au ?" in blk, "KP2k: Zurücknehmen über pa1Zurueck, Fehler als Toast, lokaler Stand wird mit entfernt")
pruef("const el = e.target.closest('[data-kl-gekauft],[data-kl-pack-gekauft]'); if(!el || e.button > 0 || el.disabled) return" in fe,
      "KP2k: Long-Press nur am normalen „Gekauft“ (grüner Knopf hat kein data-kl-gekauft)")
pruef("el.classList.toggle('mp-kl-gesperrt', !!gg)" in fe and "window._klTachoBadges()" in fe, "KP2k: gesperrte Firma am Tacho grau + Chip, auch nach Neuzeichnen")
gz = [{"user_id": "u1", "firma": "FundedNext Futures", "status": "frei", "kauf_sperre": "ab 1. FN-Payout"},
      {"user_id": "u2", "firma": "FundedNext Futures", "status": "frei", "kauf_sperre": None},
      {"user_id": "u1", "firma": "Tradeify", "status": "pausiert", "kauf_sperre": "ab 1. FN-Payout"}]
g = KL.gesperrt_aus_vorrat(gz, None, {"u1": "Aurel"})
pruef(g == [{"user_id": "u1", "name": "Aurel", "firma": "FundedNext Futures", "grund": "ab 1. FN-Payout"}], "KP2k: gesperrt_aus_vorrat nur frei + kauf_sperre")
pruef(KL.gesperrt_aus_vorrat(gz, "u2") == [], "KP2k: normale ID sieht nur eigene Sperren")
pruef('"gesperrt": gesperrt_aus_vorrat(zellen, None if admin else str(uid), namen)' in open(os.path.join(WURZEL, "kaufliste_app.py"), encoding="utf-8").read(), "KP2k: GET /admin/kaufliste liefert gesperrt[]")
pruef("_lokal_at: Date.now()" in fe, "frischer Auftrag bleibt grün, bis die Stand-Abfrage ihn liefert")

# Fremd-Anlegen: die Whitelist von /admin/konto-anlegen behält, was die Bulk-Zeile der Kaufliste schickt (Prüfer S2: Apex-Pack ohne Daily DD → Hedge zu klein)
import re as _re  # noqa: E402
from datetime import datetime as _dt, timezone as _tz  # noqa: E402
teile2 = [k for k in baum.body if (isinstance(k, ast.FunctionDef) and k.name == "admin_konto_zeile")
          or (isinstance(k, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ("ADMIN_KONTO_TYPEN", "ADMIN_KONTO_ZIELE") for t in k.targets))]
ns3 = {"re": _re, "datetime": _dt, "timezone": _tz}
exec(compile(ast.Module(body=teile2, type_ignores=[]), "app.py(konto)", "exec"), ns3)
bulk_apex = {"user_id": "eigene-wird-ersetzt", "name": "100k APEX-1-1 → Challenge", "firm": "Apex Trader", "account_type": "challenge",
             "external_id": "APEX-1-1", "account_size": 100000, "starting_balance": 100000, "purchase_cost": 45, "max_drawdown": 3000,
             "max_daily_drawdown": 1500, "max_loss_per_trade": 1000, "max_profit_per_trade": None, "wd_farm": False}
zk, fk = ns3["admin_konto_zeile"](bulk_apex)
pruef(fk is None and zk["max_daily_drawdown"] == 1500.0 and zk["account_size"] == 100000.0 and zk["starting_balance"] == 100000.0
      and zk["max_loss_per_trade"] == 1000.0 and "max_profit_per_trade" not in zk and "user_id" not in zk,
      "Apex-Pack für fremde ID: Größe, Startbalance, Daily DD, Max Loss je Trade kommen an (user_id setzt die Route)")

# ── 3. Finns Regel (KP2-Zusatz 25.11.2026): erreicht der ERWARTETE Stand (Bestand + Σ Chance × Ertrag) das Ziel, wird nicht nachgekauft ──
# Echte Lauf-Rechnung vorrat2_zelle (Standard-Kaufregel „sicherheit" 25 % mit 15 % Toleranz), geladen wie tools/selftest_vorrat_stufe2.py.
sys.path.insert(0, HIER)
import selftest_vorrat_stufe2 as VS2  # noqa: E402
ns2 = VS2.lade()
zelle = ns2["vorrat2_zelle"]
ZIEL_TR = {"art": "plus_ueber_start", "typen": ["winning_days"], "von": 20000, "bis": 30000, "kauf_groesse": 150000,
           "kauf_stufe": "challenge", "kauf_einheit": "150k Select"}
wd11 = [{"account_id": "w", "typ": "winning_days", "groesse": 150000, "balance": 161000, "alter_tage": 0}]          # 11k in Winning Days
ch = lambda i: {"account_id": f"c{i}", "typ": "challenge", "groesse": 150000, "balance": 150000, "alter_tage": 0}
fu = lambda i: {"account_id": f"f{i}", "typ": "funded", "groesse": 150000, "balance": 150000, "alter_tage": 0}
# a) 11k + 4 frische Challenges: Erwartung der 4 klein (je Chance bis WD × 14.500) → erwartet < Ziel → Lauf will kaufen, Deckel 4/4 → 0
za = zelle(ZIEL_TR, VS2.TRADEIFY, wd11 + [ch(i) for i in range(4)], "frei", seed=7)
pruef(za["erwartet"] < 20000 * 0.85 and (za["nachkauf"]["n_roh"] or 0) > 0,
      f"Tradeify 11k WD + 4 frische Challenges: erwartet {round(za['erwartet'])} < 17k → Lauf will {za['nachkauf']['n_roh']} kaufen")
pruef(deckel(za["nachkauf"]["n_roh"], za["konten"], "Tradeify", STD)["n"] == 0, "… aber 4 von 4 laufen → Deckel 0")
# b) 11k + 3 Funded vor dem Big Trade (je 14.500 × 23,7 %): erwartet ≥ 20k → 0 kaufen, obwohl der Deckel Platz hätte (0 laufende Challenges)
zb = zelle(ZIEL_TR, VS2.TRADEIFY, wd11 + [fu(i) for i in range(3)], "frei", seed=7)
pruef(zb["erwartet"] >= 20000 and zb["nachkauf"]["n_roh"] == 0,
      f"Tradeify 11k WD + 3 Funded: erwartet {round(zb['erwartet'])} ≥ 20k → 0 kaufen")
pruef(deckel(10, zb["konten"], "Tradeify", STD)["n"] == 4, "… der Deckel allein hätte 4 erlaubt (Funded zählt nicht als laufend)")
# c) Toleranz: erwartet zwischen 85 % und 100 % des Ziels → ebenfalls 0 (strenger als Finns 100 %)
zc = zelle(ZIEL_TR, VS2.TRADEIFY, wd11 + [fu(i) for i in range(2)], "frei", seed=7)
pruef(17000 <= zc["erwartet"] < 20000 and zc["nachkauf"]["n_roh"] == 0,
      f"Tradeify 11k WD + 2 Funded: erwartet {round(zc['erwartet'])} (≥ 85 % von 20k) → 0 kaufen (Toleranz)")
# KP2j (26.11.2026): Fällt Futures-„Gekauft" ins Fenster, steht der Puls-Grund (msg + Code, z. B. „Railway 500 (http_500)") fest im Fenster-Kopf
fe = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
pruef("b.hinweis = `Puls hat nicht übernommen: ${grund}`" in fe and "hinweis: b.hinweis || ''" in fe, "Fallback-Grund geht ans Bulk-Fenster")
pruef("(kl.hinweis ? `<span class=\"bkk-hinweis bkk-warn\">${escapeHtml(kl.hinweis)}</span>` : '')" in fe, "Fenster-Kopf zeigt den Grund (escaped)")
pruef("r.code && !String(r.msg || '').includes(r.code) ? `(${r.code})` : ''" in fe and "von Hand anlegen\\s*$/, '')" in fe, "Grund nennt zusätzlich den Code (http_5xx / sql_fehlt)")
print(f"\n{ok_n} Prüfungen grün (mit Lauf-Rechnung)")
