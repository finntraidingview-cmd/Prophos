#!/usr/bin/env python3
"""Selbsttest UNT6 (Master 05.11.2026, K3 Teil C — nur Anzeige): Krone, Start der Kachel „Gesamtkosten" und Unternehmensnamen kommen vom Server
bzw. aus id_gruppen.name statt aus festen Listen im Tab; fehlt etwas, bleibt der bisherige Wert. Rein rechnend mit den echten Funktionen aus app.py
(Blöcke per exec), dazu prophos.html als Text. Platzhalter-IDs, keine echten Konten. Aufruf: python3 tools/selftest_unt6_anzeige.py"""
import os
import re
import sys
from datetime import datetime, timezone

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(W, "app.py"), encoding="utf-8").read()
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def block(name):
    i = SRC.index(f"\ndef {name}(") + 1
    return SRC[i:SRC.find("\n\n\n", i)]


ns = {"datetime": datetime, "timezone": timezone, "re": re}
exec("\n\n".join(block(n) for n in ("_ap_ts", "adm_krone", "adm_gk_start_iso", "adm_gk_start_eintragen")), ns)
krone, start_iso, eintragen = ns["adm_krone"], ns["adm_gk_start_iso"], ns["adm_gk_start_eintragen"]

HT, EM = "g-ht", "g-em"
D = {"gruppen": [{"id": HT, "name": "Hermann Technologies", "verwalter_id": None}, {"id": EM, "name": "Emin", "verwalter_id": "emin"}],
     "mitglieder": [{"user_id": "fp", "gruppe_id": HT}, {"user_id": "pascal", "gruppe_id": HT}, {"user_id": "mike", "gruppe_id": HT},
                    {"user_id": "amir", "gruppe_id": EM}]}
VOLL = frozenset({"fp", "pascal"})

# ── C1 Krone = admin_voll oder Verwalter (heute genau die drei festen IDs des Tabs)
check(krone("fp", D, VOLL) and krone("pascal", D, VOLL) and krone("emin", D, VOLL), "Krone: Voll-Admins und Verwalter")
check(not krone("mike", D, VOLL) and not krone("amir", D, VOLL) and not krone("", D, VOLL) and not krone(None, D, VOLL),
      "keine Krone: HT-Mitglied, Mitglied der Verwalter-Gruppe, ohne Login")

# ── C2 Start = 00:00 deutscher Zeit am Anlagetag, live-Wert von Emin bitgleich zum alten Literal
check(start_iso("2026-10-08 20:01:17.925266+00") == "2026-10-08T00:00:00+02:00", "Emin live (08.10. 22:01 deutsch) → genau das alte Literal")
check(start_iso("2026-10-08T23:30:00Z") == "2026-10-09T00:00:00+02:00", "nach Mitternacht deutscher Zeit → nächster Tag")
check(start_iso("2026-12-01T10:00:00+00:00") == "2026-12-01T00:00:00+01:00", "Winterzeit: Offset +01:00")
check(start_iso(None) is None and start_iso("kaputt") is None, "nicht lesbar → None (Tab nimmt die alte Liste)")
check(start_iso("2026-10-08T20:01:17.9+00:00") == "2026-10-08T00:00:00+02:00" and start_iso("2026-10-08T20:01:17.92526+00:00") == "2026-10-08T00:00:00+02:00",
      "PostgREST-Formen mit 1–5 Nachkommastellen gehen auch (Python 3.9)")

ANG = {HT: "2026-10-08 20:01:17+00", EM: "2026-10-08 20:01:17+00"}
info = {"gruppen": [{"id": HT, "name": "Hermann Technologies", "ht": True}, {"id": EM, "name": "Emin", "ht": False}]}
eintragen(info, D, ANG, None)
check("gk_start" not in info["gruppen"][0] and info["gruppen"][1].get("gk_start") == "2026-10-08T00:00:00+02:00",
      "Voll-Admin: nur die Verwalter-Gruppe bekommt gk_start, HT nie (wie bisher: HT ohne Start)")
i2 = {"gruppen": []}
eintragen(i2, D, ANG, "emin")
check(i2.get("gruppe_eigen") == [{"id": EM, "name": "Emin", "gk_start": "2026-10-08T00:00:00+02:00"}], "Verwalter Emin: eigene Gruppe mit Start")
i3 = {"gruppen": []}
eintragen(i3, D, ANG, "amir")
check(i3.get("gruppe_eigen") == [{"id": EM, "name": "Emin", "gk_start": "2026-10-08T00:00:00+02:00"}], "Mitglied der Verwalter-Gruppe: dieselbe Gruppe")
i4 = {"gruppen": []}
eintragen(i4, D, ANG, "mike")
check(i4.get("gruppe_eigen") == [], "eingeschränkte HT-ID: keine Gruppe mit Start, keine fremde Gruppe")
i5 = {"gruppen": [{"id": EM, "name": "Emin", "ht": False}]}
eintragen(i5, D, {}, None)
check("gk_start" not in i5["gruppen"][0], "angelegt_at fehlt → kein gk_start (Tab nimmt die Liste nach Name)")

# ── Route: eigene try je Feld, krone nach Login-ID, Gruppen-Daten unverändert
ov = SRC[SRC.index("def admin_build_overview("):SRC.index("# excluded_uids zusaetzlich zu den E-Mails")]
check('gruppen_info["krone"] = adm_krone(getattr(g, "login_uid", None), admin_gruppen_daten(), admin_voll_uids())' in ov
      and "adm_gk_start_eintragen(gruppen_info, admin_gruppen_daten(), _adm_gruppen_angelegt(), _admin_nur_uid())" in ov
      and ov.count("except Exception as e:\n        print(f\"[admin] ⚠️ krone") == 1 and "[admin] ⚠️ gk_start" in ov, "Übersicht: krone + gk_start je eigener try")
check('gr = sb_select("id_gruppen", {"select": "id,name,verwalter_user_id"})' in SRC, "admin_gruppen_daten (Sicht/Rechte) unverändert")

# ── Frontend: Server-Wert zuerst, Rückfall auf die alten Werte
check("const ADMIN_KRONE_IDS = new Set(['48f272b4-913e-4598-a06a-1dcc3d5679fb'" in HTML
      and "if(kr && d && typeof d.krone === 'boolean' && String(uid || '') === String(currentUserId || '')) kr.hidden = !d.krone" in HTML
      and "admKroneSetzen(d, uid)   // UNT6" in HTML,
      "C1: Krone nach d.krone, feste Liste bleibt Rückfall in hydrateUser")
check("const ADM_GK_START_JE_GRUPPE = { 'Emin': '2026-10-08T00:00:00+02:00' }" in HTML
      and "const iso = g && (g.gk_start || ADM_GK_START_JE_GRUPPE[String(g.name || '').trim()])" in HTML
      and "const eig = (admData.gruppe_eigen || []).find(x => x && x.gk_start)" in HTML, "C2: gk_start je gruppe_id zuerst, Liste nach Name als Rückfall")
check("escapeHtml(kisUntName(g))" in HTML and "kisUntName(d.gruppe) + ' · '" in HTML
      and "const kisUntName = g => !g ? '' : (String(g.name || '').trim() || (g.ht ? 'Hermann Technologies' : ''))" in HTML,
      "C3: Gruppenname aus id_gruppen.name, leer → „Hermann Technologies“ wie bisher")
check("Quelle: ${escapeHtml(kisGkName())}s Sheet" in HTML and "Anfangsstand Geschäftskonto (${kisGkName()}/Bank)" in HTML
      and "return (g && !g.ht && String(g.name || '').trim()) || 'Emin'" in HTML
      and "'Hermann Technologies' : g.name)" not in HTML and "Quelle: Emins Sheet" not in HTML, "C3: Geschäftskonto-Texte mit dem Unternehmensnamen, Rückfall „Emin“")

print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
