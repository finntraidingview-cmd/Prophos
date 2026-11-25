"""Kaufliste unter Accounts (KP2, 25.11.2026).

Finn 25.11.2026 (Demo demo/kaufplan.html abgenommen, „Design ganz nice“): unter Accounts direkt unter dem Muster-Portfolio eine Liste, eine Zeile
je zu kaufendem Konto, „Gekauft“ (echtes Bulk-Fenster mit Vorlage, nur External IDs einfügen), „Erledigt“ (weg, mit Rückgängig), Kästchen für
mehrere. Normale ID: nur eigene Zeilen. Admin: „Meine | Alle IDs“ und Anlegen für fremde IDs OHNE ID-Wechsel.

Rechnet nichts Neues: die Kaufzahl ist nachkauf.n des Vorrat-Laufs (app.py vorrat2_rechnen_lauf, seit KP2 mit Deckel „max. laufend“ je Firma
und FNF erst ab dem 1. erhaltenen FundedNext-Payout, vorrat_kauf_deckel), wie sie GET /admin/vorrat zeigt — also nach Abzug der seit dem Lauf
angelegten Konten und der offenen „bestellt“-Einträge (vorrat_bestellt, 48 h). „Erledigt“ = POST /admin/vorrat {aktion: 'bestellt'} (gibt es
seit 06.10.2026), Rückgängig = {aktion: 'bestellt_weg', id} — keine neue Tabelle.

Route:
  GET  /admin/kaufliste?alle=0|1     kompakte Zeilen je ID × Firma mit n > 0 (alle=1 nur Admin/Verwalter, Gate kapital_app._gate;
                                     sonst nur die eigene ID)
Anlegen für eine FREMDE ID läuft über die vorhandene Route POST /admin/konto-anlegen (app.py, 29.10.2026: Service-Key, _admin_konto_gate,
Whitelist admin_konto_zeile, Doppel-Schutz, Max DD aus der Schablone, Kauf-Transaktion) — keine zweite Anlege-Route (Slave 5, PA1).
"""
import time

from flask import request, jsonify

import kapital_app as K

A = {}                         # Namensraum von app.py — gefüllt in registrieren()

_cache = {}
CACHE_S = 60                   # GET /admin/vorrat baut die ganze Admin-Basis — die Accounts-Seite fragt höchstens einmal je Minute neu

def zeilen_aus_vorrat(zellen, nur_uid=None, namen=None):
    """REIN RECHNEND (Selbsttest): Zellen von GET /admin/vorrat → Kauflisten-Zeilen (eine je ID × Firma mit n > 0).
    nur_uid: nur diese ID; namen: {user_id: Anzeigename} (people der Vorrat-Antwort). Sortierung wie die Demo: jetzt vor bald, Score, Name."""
    namen = namen or {}
    out = []
    for z in zellen or []:
        uid = str(z.get("user_id") or "")
        if nur_uid and uid != nur_uid:
            continue
        nk = z.get("nachkauf") or {}
        n = nk.get("n")
        if not isinstance(n, int) or n <= 0 or z.get("status") not in (None, "frei") or z.get("kauf_sperre"):
            continue
        if z.get("max_laufend") is None:     # Lauf noch ohne KP2-Deckel (Stand < 9, Neurechnung gescheitert) → lieber nichts als ungedeckelt (Review)
            continue
        out.append({
            "user_id": uid, "name": namen.get(uid) or z.get("user") or uid[:8], "firma": z.get("firma"), "n": n,
            "lage": nk.get("dringlichkeit") or z.get("lage"), "score": z.get("score"),
            "laufend": z.get("laufend_n"), "max": z.get("max_laufend"), "reserve": bool(z.get("reserve")),
            "pack": z.get("kauf_pack"),                     # Apex: 5er-Pack (Zeilen als Pack gruppiert, Gekauft/Erledigt fürs ganze Pack)
            "einheit": nk.get("einheit"), "preis_eur": nk.get("preis_eur"),
            "untergrenze": z.get("untergrenze"), "bestellt": z.get("bestellt"),
        })
    rang = {"jetzt": 0, "bald": 1}
    out.sort(key=lambda x: (rang.get(x["lage"], 2), -(x["score"] or 0), str(x["name"]).lower(), str(x["firma"])))
    return out


def registrieren(app, ns):
    A.update(ns)

    @app.route("/admin/kaufliste", methods=["GET", "OPTIONS"])
    def admin_kaufliste():
        """Kauflisten-Zeilen. ?alle=1 nur für Admin/Verwalter (Gate wie Kapital) — sonst nur die eigene ID, auch für HT-IDs ohne
        admin_zugang-Zeile (die sehen in /admin/vorrat alle Zellen, hier bewusst nicht)."""
        if request.method == "OPTIONS":
            return "", 200
        uid, err = A["_wd_login"]()
        if err:
            return err
        alle = request.args.get("alle") == "1"
        admin = False
        if alle:
            erlaubt, gerr = K._gate()
            if gerr:
                return gerr
            admin = True
        schl = ("alle" if admin else uid, A["_admin_nur_uid"](), tuple(sorted(A["_admin_sicht"]() or ())))
        c = _cache.get(schl)
        # frisch=1 (nach Erledigt/Anlegen) umgeht den Merker höchstens alle 5 s — jede Antwort baut die ganze Admin-Basis (Review: Last)
        if c and (time.time() - c[0] < 5 or (time.time() - c[0] < CACHE_S and request.args.get("frisch") != "1")):
            return jsonify(dict(c[1], ich=str(uid)))
        try:
            antwort_v = A["_vorrat_antwort"](A["admin_build_vorrat"]())
            zellen = antwort_v.get("zellen") or []
            namen = {str(p.get("user_id")): p.get("name") for p in antwort_v.get("people") or []}
            zeilen = zeilen_aus_vorrat(zellen, None if admin else str(uid), namen)
            antwort = {"ok": True, "alle": admin, "zeilen": zeilen, "n": sum(z["n"] for z in zeilen),
                       "lauf_at": antwort_v.get("gerechnet_um"),
                       "naechster_lauf": antwort_v.get("naechster_lauf")}
            _cache[schl] = (time.time(), antwort)
            return jsonify(dict(antwort, ich=str(uid)))
        except Exception as e:
            print(f"[kaufliste] ⚠️ GET: {type(e).__name__}: {e}", flush=True)
            return jsonify({"ok": False, "error": f"Kaufliste nicht ladbar ({type(e).__name__})"}), 500
