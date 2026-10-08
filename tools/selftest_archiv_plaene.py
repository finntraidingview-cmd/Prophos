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

    d = block(app, '@app.route("/admin/auto-plan/delta"')
    check("ap_delta_ohne_archiv(antwort, _ap_archiviert_gemerkt())" in d, "GET /admin/auto-plan/delta filtert mit gemerktem Archiv")
    ids = block(app, '@app.route("/admin/auto-plan/ids"')
    check('str(p.get("master_account_id") or "") not in archiv' in ids, "Zu bestätigen (ids offen[]): archivierte Konten raus")
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
    pks = block(html, "  async function planKontoSperre(", "\n  }\n")
    check(".from('user_settings').select('value').eq('user_id', currentUserId).eq('key', 'archive')" in pks
          and "art: 'archiv'" in pks and "isAccountArchived(kid)" in pks,
          "planKontoSperre: Archiv frisch aus user_settings, Rückfall lokaler Stand")
    i_arch, i_ziel = pks.find("imArchiv(rs.data.value)"), pks.find("ra.data.ziel_erreicht_at")
    check(0 < i_arch < i_ziel, "Archiv-Sperre vor Ziel-Sperre")
    tick = block(html, "  async function tpStartUmTick(", "\n  }\n")
    i_a, i_claim = tick.find("sperre.art === 'archiv'"), tick.find("// Claim: nur der Tab")
    check(0 < i_a < i_claim and "archivPlaeneEntfernen(plan.masterAccountId, 'start')" in tick,
          "tpStartUmTick: archivierter Plan wird vor dem Claim entfernt, nie gestartet")
    td = block(html, "  function tplDaten(", "\n  }\n")
    check("arch[String(t.konto_id)].archived" in td and "!t.geclaimt" in td, "tplDaten: geplante Zeilen archivierter Konten ausgeblendet")

    print("\nARCHIV-PLÄNE:", "alles grün" if not any(f) else f"{sum(f)} FEHLER")
    return 1 if any(f) else 0


if __name__ == "__main__":
    sys.exit(main())
