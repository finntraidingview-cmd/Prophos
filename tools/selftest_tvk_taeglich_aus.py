#!/usr/bin/env python3
"""Selbsttest: Tages-Fallback der TV-Konten-Aufträge aus (app.py TV_KONTEN_TAEGLICH, pc_tv_konten_auftrag, 04.11.2026, Finn: „Sicherheitsnetz:
zusätzlich liest Puls einmal am Tag je Firma, auch ohne Mail — ne, das nicht."). Ohne Netz: DB-Aufrufe abgefangen, Konten erfunden.
Geprüft: kein Auftrag art 'taeglich' wird angelegt, offene Tages-Aufträge werden als „fehler" (verworfen) geschlossen, ausgegeben werden nur
Mail-Aufträge; mit TV_KONTEN_TAEGLICH = True wie bisher.  Aufruf: python3 tools/selftest_tvk_taeglich_aus.py"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))
import app  # noqa: E402

FEHLER = []


def ok(b, t):
    print(("✓ " if b else "✗ ") + t)
    if not b:
        FEHLER.append(t)


def lauf(taeglich, offen_mail=None):
    """Ein GET /pc/tv-konten-auftrag mit abgefangener DB → (antwort, inserts, updates, selects)."""
    ins, upd, sel = [], [], []
    app.TV_KONTEN_TAEGLICH = taeglich
    app._tv_fallback_merk.clear()
    app._login_uid_mail = lambda: ("00000000-0000-0000-0000-0000000000a1", "x@y", None)
    app.tv_konten_pc_frei = lambda pc: True
    app._sb_all = lambda tab, q: [{"id": "k1", "firm": "Tradeify", "external_id": "FTDFYSLX150000000001", "created_at": "2026-11-01T00:00:00+00:00"}]

    def sb_select(tab, q):
        sel.append((tab, dict(q)))
        if tab == "tv_konten_auftrag" and q.get("select") == "created_at":
            return []                                   # noch nie ein Auftrag → Tages-Auftrag wäre fällig
        if tab == "tv_konten_auftrag" and "faellig_at" in q:
            return [offen_mail] if offen_mail else []
        if tab == "user_settings":
            return [{"value": {}}]
        return []
    app.sb_select = sb_select
    app.sb_insert = lambda tab, row: ins.append((tab, dict(row))) or [row]
    app.sb_update = lambda tab, f, body: upd.append((tab, dict(f), dict(body))) or [{"id": "x"}]
    with app.app.test_request_context("/pc/tv-konten-auftrag?pc=pc-test01"):
        r = app.pc_tv_konten_auftrag()
    return r.get_json(), ins, upd, sel


def main():
    # 1) aus (Standard): nichts Tägliches anlegen, offene schließen, nur Mail-Aufträge holen
    ok(app.TV_KONTEN_TAEGLICH is False, "Standard: TV_KONTEN_TAEGLICH = False")
    j, ins, upd, sel = lauf(False)
    ok(not any(t == "tv_konten_auftrag" and r.get("art") == "taeglich" for t, r in ins), "kein Tages-Auftrag angelegt")
    zu = [u for u in upd if u[1].get("art") == "eq.taeglich"]
    ok(len(zu) == 1 and zu[0][1].get("status") == "eq.offen" and zu[0][2].get("status") == "fehler" and zu[0][2]["ergebnis"].get("code") == "taeglich_aus",
       "offene Tages-Aufträge → „fehler“ (verworfen, code taeglich_aus); laufende bleiben")
    hol = [q for t, q in sel if t == "tv_konten_auftrag" and "faellig_at" in q]
    ok(hol and hol[0].get("art") == "eq.mail", "Abholen nur art = mail")
    ok(j.get("ok") and j.get("auftrag") is None, "ohne Mail-Auftrag: kein Auftrag")
    # 2) Mail-Auftrag fällig → wird wie bisher ausgegeben
    j2, _i, _u, _s = lauf(False, {"id": "11111111-1111-1111-1111-111111111111", "firma": "Tradeify", "art": "mail", "faellig_at": "2026-11-04T00:00:00+00:00"})
    ok(j2.get("auftrag") and j2["auftrag"]["art"] == "mail" and j2["auftrag"]["ext"] == "FTDFYSLX150000000001", "Mail-Auftrag läuft wie bisher")
    # 3) zweiter Abruf binnen 30 min: kein weiterer DB-Schreibzugriff fürs Aufräumen (Takt wie früher das Anlegen)
    app._tv_fallback_merk["00000000-0000-0000-0000-0000000000a1"] = __import__("time").time()
    upd2 = []
    app.sb_update = lambda tab, f, body: upd2.append((tab, dict(f))) or [{"id": "x"}]
    with app.app.test_request_context("/pc/tv-konten-auftrag?pc=pc-test01"):
        app.pc_tv_konten_auftrag()
    ok(not any(f.get("art") == "eq.taeglich" for _t, f in upd2), "Aufräumen höchstens alle 30 min je ID")
    # 3b) Kauf-Mail, während noch ein offener Tages-Auftrag derselben Firma steht (Fremd-Review): Tages-Auftrag verworfen, Mail-Auftrag angelegt
    app.TV_KONTEN_TAEGLICH = False
    ins5, upd5 = [], []
    app.sb_select = lambda tab, q: [{"id": "t1", "art": "taeglich", "status": "offen"}] if tab == "tv_konten_auftrag" else []
    app.sb_update = lambda tab, f, body: upd5.append((dict(f), dict(body))) or [{"id": "t1"}]
    app.sb_insert = lambda tab, row: ins5.append(dict(row)) or [row]
    mail = [{"von": "Tradeify <support@tradeify.co>", "betreff": "Your Tradeify order is confirmed", "text": "", "gmail_msg_id": "m1"}]
    app.tv_konten_mail_auftraege(mail, "00000000-0000-0000-0000-0000000000a1")
    ok(any(f.get("id") == "eq.t1" and b.get("status") == "fehler" for f, b in upd5) and any(r.get("art") == "mail" and r.get("firma") == "Tradeify" for r in ins5),
       "Kauf-Mail neben offenem Tages-Auftrag: Tages-Auftrag verworfen, Mail-Auftrag angelegt")
    ins6, upd6 = [], []
    app.sb_select = lambda tab, q: [{"id": "m0", "art": "mail", "status": "offen"}] if tab == "tv_konten_auftrag" else []
    app.sb_update = lambda tab, f, body: upd6.append(dict(f)) or []
    app.sb_insert = lambda tab, row: ins6.append(dict(row)) or [row]
    app.tv_konten_mail_auftraege(mail, "00000000-0000-0000-0000-0000000000a1")
    ok(not ins6 and not upd6, "offener Mail-Auftrag derselben Firma: bündeln wie bisher (nichts Neues)")
    # 4) Schalter an: wie bis 04.11.2026
    j4, ins4, upd4, sel4 = lauf(True)
    ok(any(r.get("art") == "taeglich" for t, r in ins4) and not any(u[1].get("art") == "eq.taeglich" for u in upd4), "TV_KONTEN_TAEGLICH = True: Tages-Auftrag wie bisher")
    hol4 = [q for t, q in sel4 if t == "tv_konten_auftrag" and "faellig_at" in q]
    ok(hol4 and "art" not in hol4[0], "… und Abholen ohne Art-Filter")
    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("alle Tests bestanden")


if __name__ == "__main__":
    main()
