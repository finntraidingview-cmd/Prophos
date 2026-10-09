#!/usr/bin/env python3
"""Selbsttest ARCHIVIERT = KEINE GEPLANTEN TRADES (Finn 09.10.2026 ~03:00 Dubai: „Den Account habe ich schon längst archiviert, den gibt's
gar nicht mehr" — der Nachtlauf hatte den Plan vor dem Archivieren angelegt). Platzhalter-IDs, ohne Netz.
Geprüft: app.py ap_delta_ohne_archiv rein rechnend (geplant ohne archivierte Konten, geclaimte bleiben, offen bleibt, leeres Archiv = gleich);
Quelltext-Proben: Delta + „Zu bestätigen" filtern das Archiv, Handarbeit in allen Gruppen; prophos.html archiveAccount → archivPlaeneEntfernen
(nur planned, ohne Claim, ohne started_at), planKontoSperre liest das Archiv frisch, tpStartUmTick startet archivierte Pläne nie,
tplDaten blendet sie aus.
Aufruf: python3 tools/selftest_archiv_plaene.py"""
import os
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(WURZEL, "app.py")
HTML = os.path.join(WURZEL, "prophos.html")


def block(src, kopf, ende="\n\n\n"):
    i = src.index(kopf)
    return src[i:src.find(ende, i)]


def main():
    app = open(APP, encoding="utf-8").read()
    html = open(HTML, encoding="utf-8").read()
    f = []

    def check(ok, name):
        f.append(0 if ok else 1)
        print(("OK  " if ok else "FEHL") + " " + name)

    ns = {}
    exec(block(app, "\ndef ap_delta_ohne_archiv(").lstrip("\n"), ns)
    weg = ns["ap_delta_ohne_archiv"]
    antwort = {"offen": [{"plan_id": "o1", "konto_id": "k-arch"}],
               "geplant": [{"plan_id": "p1", "konto_id": "k-arch", "geclaimt": False},
                           {"plan_id": "p2", "konto_id": "k-arch", "geclaimt": True},
                           {"plan_id": "p3", "konto_id": "k-aktiv"},
                           {"plan_id": "p4", "konto_id": None}]}
    neu = weg(antwort, {"k-arch"})
    check([z["plan_id"] for z in neu["geplant"]] == ["p2", "p3", "p4"],
          "Delta geplant: archiviertes Konto raus, geclaimter Plan (Start läuft) bleibt, andere bleiben")
    check(neu["offen"] == antwort["offen"] and len(antwort["geplant"]) == 4, "offen[] unberührt, Eingabe nicht verändert")
    check(weg(antwort, set()) is antwort and weg(None, {"k"}) is None, "leeres Archiv / keine Antwort: unverändert")

    exec(block(app, "\ndef ap_ist_waise(").lstrip("\n"), ns)
    w = ns["ap_ist_waise"]
    check(w({"status": "planned", "master_account_id": None}), "Waise: geplant, Konto null, nie gestartet")
    check(not w({"status": "planned", "master_account_id": None, "start_um_gestartet_at": "2026-10-09T08:00:00Z"})
          and not w({"status": "planned", "master_account_id": None, "started_at": "2026-10-09T08:00:00Z"}),
          "geclaimt/gestartet ohne Konto ist keine Waise (dort läuft vielleicht etwas)")
    check(not w({"status": "completed", "master_account_id": None}) and not w({"status": "planned", "master_account_id": "k-1"}) and not w(None),
          "beendet ohne Konto / geplant mit Konto / nichts: keine Waise")
    check("and not ap_ist_waise(p)]" in block(app, "\ndef ap_planen(") and "not ersetzt(p) and not ap_ist_waise(p)]" in block(app, "\ndef _ap_stand_laden("),
          "Planer (plaene) und Stand (Delta/Bot) zählen Waisen nicht")

    from datetime import datetime as _dt, timezone as _tz
    ns.update(datetime=_dt, timezone=_tz, AP_CLAIM_HAENGT_MIN=10)
    exec(block(app, "\ndef ap_claim_haengt(").lstrip("\n"), ns)
    exec(block(app, "\ndef ap_archiv_sweep_ziele(").lstrip("\n"), ns)
    sz = ns["ap_archiv_sweep_ziele"]
    # Hängender Claim (Finn 09.10.2026, FN …0296 1c3f7ecd: geclaimt, start_fehler rot, nie gestartet — Konto geblowt + archiviert)
    J = _dt(2026, 10, 9, 3, 0, tzinfo=_tz.utc)
    rot = {"status": "rot", "unklar": True}
    hc = [{"id": "h1", "status": "planned", "master_account_id": "k-arch", "start_um_gestartet_at": "2026-10-08T23:47:02.822+00:00", "start_fehler": rot},
          {"id": "h2", "status": "planned", "master_account_id": "k-arch", "start_um_gestartet_at": "2026-10-09T02:55:00+00:00", "start_fehler": rot},
          {"id": "h3", "status": "planned", "master_account_id": "k-arch", "start_um_gestartet_at": "2026-10-08T23:47:02Z"},
          {"id": "h4", "status": "planned", "master_account_id": "k-arch", "start_um_gestartet_at": "2026-10-08T23:47:02Z", "start_fehler": rot,
           "orbit_gesendet_at": "x"},
          {"id": "h5", "status": "planned", "master_account_id": "k-aktiv", "start_um_gestartet_at": "2026-10-08T23:47:02Z", "start_fehler": rot},
          {"id": "h6", "status": "planned", "master_account_id": None, "start_um_gestartet_at": "2026-10-08T23:47:02Z", "start_fehler": rot},
          {"id": "h7", "status": "planned", "master_account_id": "k-arch", "start_um_gestartet_at": "2026-10-08T23:47:02Z",
           "mt5_baseline": {"start_fehler": {"status": "gelb"}}}]
    check([p["id"] for p in sz(hc, {"k-arch"}, J)] == ["h1"],
          "hängender Claim (rot, ≥ 10 min, ohne Order) eines archivierten Kontos raus; jung/ohne Fehler/gesendet/aktiv/Waise/nicht rot bleiben")
    check(ns["ap_claim_haengt"](dict(hc[0], start_fehler=None, mt5_baseline={"start_fehler": rot}), J), "start_fehler auch aus mt5_baseline")
    pl = [{"id": "s1", "status": "planned", "master_account_id": "k-arch"},
          {"id": "s2", "status": "planned", "master_account_id": None},
          {"id": "s3", "status": "planned", "master_account_id": "k-aktiv"},
          {"id": "s4", "status": "planned", "master_account_id": "k-arch", "start_um_gestartet_at": "x"},
          {"id": "s5", "status": "planned", "master_account_id": "k-arch", "orbit_gesendet_at": "x"},
          {"id": "s6", "status": "open", "master_account_id": "k-arch"}]
    check([p["id"] for p in sz(pl, {"k-arch"})] == ["s1", "s2"],
          "Sweep: archiviert + Waise raus; aktives Konto, geclaimt, gesendet, laufend bleiben")
    ns_a = {"json": __import__("json"), "_sb_all": lambda t, q: [{"value": {"k1": {"archived": True}, "k2": {"archived": False}, "k3": {"x": 1}}},
                                                                  {"value": '{"k4": {"archived": true}}'}]}
    exec(block(app, "\ndef _ap_archiviert(").lstrip("\n"), ns_a)
    check(ns_a["_ap_archiviert"](streng=True) == {"k1", "k4"} and ns_a["_ap_archiviert"]() == {"k1", "k2", "k3", "k4"},
          "Archiv streng (Sweep löscht): nur archived === true; Anzeige-Lesart unverändert")
    sw = block(app, "\ndef ap_archiv_sweep(")
    check(all(x in sw for x in ('_ap_archiviert(streng=True)', '"status": "eq.planned", "start_um_gestartet_at": "is.null", "started_at": "is.null",',
                                '"orbit_gesendet_at": "is.null", "master_account_id": f"eq.{kid}" if kid else "is.null"', "sb_delete(")),
          "Sweep-DELETE trägt den Wächter in der Anfrage selbst")
    check('"start_um_gestartet_at": f"eq.{p[\'start_um_gestartet_at\']}", "mt5_baseline->start_fehler->>status": "eq.rot"' in sw
          and "start_fehler:mt5_baseline->start_fehler" in sw and '"status": "eq.planned", "started_at": "is.null"})' in sw,
          "Sweep liest Claims mit start_fehler; DELETE eines hängenden Claims nur mit genau diesem Claim + start_fehler rot im Wächter")
    check("ap_archiv_sweep()" in block(app, "\ndef ap_loop("), "Sweep läuft in der Auto-Planer-Schleife")
    check('rest/v1/auto_plan_umplanung' in sw and '"quelle": "bot"' in sw and "Plan entfernt — " in sw,
          "Sweep protokolliert je Plan in auto_plan_umplanung (quelle bot)")

    ns_e = {"json": __import__("json")}
    exec(block(app, "\ndef archiv_ohne_konto(").lstrip("\n"), ns_e)
    exec(block(app, "\ndef entarchivieren_darf(").lstrip("\n"), ns_e)
    aok, darf = ns_e["archiv_ohne_konto"], ns_e["entarchivieren_darf"]
    KF = "aaaaaaaa-0000-4000-8000-000000000001"
    profile = [{"user_id": "u-admin", "value": {KF: {"archived": True, "reason": "blown"}, "k-x": {"archived": True}}},
               {"user_id": "u-besitzer", "value": {"k-y": {"archived": True}}},
               {"user_id": "u-alt", "value": '{"' + KF + '": {"archived": true}}'}]
    nachher = []
    for r in profile:
        neu, weg = aok(r["value"], KF)
        nachher.append(dict(r, value=neu))
    check(all(KF not in (r["value"] if isinstance(r["value"], dict) else {}) for r in nachher) and nachher[0]["value"] == {"k-x": {"archived": True}},
          "Entarchivieren: Eintrag in ALLEN Profilen weg (auch JSON-Text), andere Einträge bleiben")
    check(aok({"k-x": {}}, KF) == ({"k-x": {}}, False) and aok("kaputt", KF) == ("kaputt", False), "kein Eintrag / kaputter Wert: unverändert")
    ns_b = {"json": __import__("json"), "_sb_all": lambda t, q: nachher}
    exec(block(app, "\ndef _ap_archiviert(").lstrip("\n"), ns_b)
    plan_kf = [{"id": "q1", "status": "planned", "master_account_id": KF}]
    check(sz(plan_kf, ns_b["_ap_archiviert"](streng=True)) == [] and sz(plan_kf, {KF}) == plan_kf,
          "Admin archiviert fremdes Konto, Besitzer entarchiviert → Sweep lässt den Plan in Ruhe (vorher: entfernt)")
    check(darf("u-b", False, "u-b", None) and darf(None, True, "u-b", None) and darf("u-v", False, "u-b", {"u-b", "u-c"}),
          "Recht: Besitzer, Admin, Verwalter der Gruppe des Besitzers")
    check(not darf("u-x", False, "u-b", None) and not darf("u-v", False, "u-b", {"u-c"}) and not darf("u-b", False, None, None),
          "kein Recht: fremde ID, Verwalter anderer Gruppe, Konto unbekannt")
    ep = block(app, '@app.route("/account/entarchivieren"')
    check('guard["updated_at"] = f"eq.{row[\'updated_at\']}"' in ep and "range(2)" in ep and '_ap_archiv_merk["wert"] = None' in ep
          and "entarchivieren_darf(uid, admin, besitzer, gruppe)" in ep,
          "Endpunkt: Rechte geprüft, Wächter updated_at mit einem Neu-Lesen, Delta-Archiv sofort neu")
    ua = block(html, "  function unarchiveAccount(", "\n  }\n")
    check("archivUeberallEntfernen(accountId)" in ua and "delete _archNeu[accountId]" in ua, "unarchiveAccount ruft das Backend (alle Profile)")
    asa = block(html, "  function archivSchreibenAbgeglichen(", "\n  }\n")
    check("_origLocalStorageSetItem.call(localStorage, ARCH_LS" in asa and "fetchSetting('archive')" in asa and "{ ...basis, ..._archNeu }" in asa
          and "archivSchreibenAbgeglichen(accountId, arch[accountId])" in block(html, "  function archiveAccount(", "\n  /* ARCHIVIERT"),
          "Archivieren: lokal ohne Upload, dann Cloud-Stand + eigene neue Einträge hochladen (kein alter Tab-Stand)")

    d = block(app, '@app.route("/admin/auto-plan/delta"')
    check("ap_delta_ohne_archiv(antwort, _ap_archiviert_gemerkt())" in d, "GET /admin/auto-plan/delta filtert mit gemerktem Archiv")
    ids = block(app, '@app.route("/admin/auto-plan/ids"')
    check('and p.get("master_account_id") and str(p.get("master_account_id")) not in archiv]' in ids,
          "Zu bestätigen (ids offen[]): archivierte Konten und Waisen raus")
    hg = block(app, "\ndef hand_gruppen(")
    check(hg.count("in archiv") >= 4, "Handarbeit: alle Gruppen prüfen das Archiv")

    ar = block(html, "  function archiveAccount(", "\n  /* ARCHIVIERT")
    check("archivPlaeneEntfernen(accountId)" in ar, "archiveAccount ruft archivPlaeneEntfernen (jeder Grund)")
    ape = block(html, "  async function archivPlaeneEntfernen(", "\n  }\n")
    check(all(x in ape for x in (".eq('master_account_id', kid)", ".eq('status', 'planned')", ".is('start_um_gestartet_at', null)",
                                 ".is('started_at', null)")),
          "archivPlaeneEntfernen löscht nur planned ohne Claim und ohne started_at")
    check("tpWdTagesplanAustragen(r.id, 'Konto archiviert')" in ape and "'geplante Trades'} dieses Kontos entfernt" in ape,
          "Farmer-Plan wird aus dem Tagesplan ausgetragen, Toast „n geplante Trades dieses Kontos entfernt“")
    dl = block(html, "accEls.table.querySelectorAll('[data-acc-del]')", "\n      })\n      })\n")
    i_p, i_a = dl.find("await archivPlaeneEntfernen(id)"), dl.find("from('accounts').delete()")
    check(0 < i_p < i_a, "Konto löschen: erst die nie gestarteten Pläne, dann das Konto (FK setzt sonst null)")
    wpe = block(html, "  async function waisePlanEntfernen(", "\n  }\n")
    check(all(x in wpe for x in (".eq('id', plan.id)", ".eq('status', 'planned')", ".is('master_account_id', null)",
                                 ".is('start_um_gestartet_at', null)", ".is('started_at', null)")),
          "waisePlanEntfernen: nur dieser Plan, nur Waise, nie gestartet")
    pks = block(html, "  async function planKontoSperre(", "\n  }\n")
    check("if(!kid && plan && plan.status === 'planned') return { art: 'waise'" in pks, "planKontoSperre: Waise → kein Start")
    check(".from('user_settings').select('value').eq('user_id', currentUserId).eq('key', 'archive')" in pks
          and "art: 'archiv'" in pks and "isAccountArchived(kid)" in pks,
          "planKontoSperre: Archiv frisch aus user_settings, Rückfall lokaler Stand")
    i_arch, i_ziel = pks.find("imArchiv(rs.data.value)"), pks.find("ra.data.ziel_erreicht_at")
    check(0 < i_arch < i_ziel, "Archiv-Sperre vor Ziel-Sperre")
    tick = block(html, "  async function tpStartUmTick(", "\n  }\n")
    i_a, i_claim = tick.find("sperre.art === 'archiv'"), tick.find("// Claim: nur der Tab")
    check(0 < i_a < i_claim and "archivPlaeneEntfernen(plan.masterAccountId, 'start')" in tick and "await waisePlanEntfernen(plan)" in tick,
          "tpStartUmTick: archivierter Plan / Waise wird vor dem Claim entfernt, nie gestartet")
    td = block(html, "  function tplDaten(", "\n  }\n")
    check("arch[String(t.konto_id)].archived" in td and "!t.geclaimt" in td, "tplDaten: geplante Zeilen archivierter Konten ausgeblendet")

    print("\nARCHIV-PLÄNE:", "alles grün" if not any(f) else f"{sum(f)} FEHLER")
    return 1 if any(f) else 0


if __name__ == "__main__":
    sys.exit(main())
