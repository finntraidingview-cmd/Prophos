#!/usr/bin/env python3
"""Selbsttest NG2 + MT1 (06.11.2026, Finn: „Account startet nicht / P&L fehlt / hängende unklar-Zeilen sollen nicht mehr vorkommen").
NG2: Orbit/Topstep-Plan (tvv2/tsv2), nie gestartet, nach dem Tagesreset vom Puls flach gelesen, Balance = Vergleichs-Balance ±1 $ → gelöscht statt
unklar unter Abhaken (Fall Mike Lucid 5b2a2fd1). MT1: Echo-Plan „unklar", weil das Master-Terminal zu war → der Tab öffnet es zum Lesen und liest die
Deals ~10 min später (Fall Marco e5e3995a). Prüft die Verdrahtung in prophos.html und spielt ng2Urteil / ng2NotizBalance nach.
Aufruf: python3 tools/selftest_ng2_mt1.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def notiz_balance(notes):
    m = re.search(r"Balance ([\d.]+(?:,\d+)?) \((?:TV|TopstepX|TSX)\)", str(notes or ""))
    if not m:
        return None
    n = float(m.group(1).replace(".", "").replace(",", "."))
    return n if n > 0 else None


def alnum(v):
    return re.sub(r"[^0-9a-z]", "", str(v or ""), flags=re.I).upper()


def urteil(r, ref, ext="LFE15098258480001"):
    """Python-Spiegel von ng2Urteil: '' = darf weg."""
    if not r:
        return "kein Plan"
    if r.get("status") != "review":
        return "nicht review"
    if r.get("route") not in ("tvv2", "tsv2"):
        return "kein Orbit/Topstep"
    if r.get("started_at") or r.get("orbit_gesendet_at"):
        return "gestartet"
    if r.get("master_pl") is not None:
        return "P&L"
    if r.get("slave_pl") is not None and float(r["slave_pl"]) != 0:
        return "Fusion-P&L"
    b = r.get("mt5_baseline") or {}
    f = b.get("final") or {}
    if f.get("grund") != "tagesende_unklar" or f.get("quelle") != "puls":
        return "keine Endlesung"
    import datetime as _dt
    def ts(x):
        try:
            return _dt.datetime.fromisoformat(str(x).replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    pa, ta = ts(f.get("puls_at")), ts(f.get("tagesreset_at"))
    if not (pa is not None and ta is not None and pa > ta):
        return "Lesung nicht nach dem Tagesreset"
    if f.get("puls_flach") != "tabelle":
        return "nicht über die Tabelle flach"
    if len(alnum(ext)) < 6 or alnum(ext) not in alnum(f.get("puls_konto")):
        return "anderes Konto"
    if not (float(f.get("balance_end") or 0) > 0):
        return "keine Balance"
    if any(f.get(k) for k in ("exit_fill", "einstieg", "einstieg_fill", "einstieg_nq", "preis", "ticket", "konto_geblowt", "konto_weg")) or f.get("master_pl_schaetzung") is not None:
        return "Fill"
    if b.get("manuell"):
        return "manuell"
    if b.get("puls_pause") or r.get("polar_lauf"):
        return "Pause/Polar"
    if b.get("hedge") or b.get("ticket") or b.get("versuche_alt") or b.get("polar") or (b.get("live") or {}).get("offen") or (isinstance(b.get("tv"), dict) and b["tv"]):
        return "Spur"
    if ref is None or not (ref > 0):
        return "keine Vergleichs-Balance"
    if abs(float(f["balance_end"]) - ref) > 0.01:
        return "Balance anders"
    return ""


def main():
    html = open(os.path.join(HIER, "..", "prophos.html"), encoding="utf-8").read()
    u = html[html.index("function ng2Urteil(r, refBal, extId){"):html.index("window._ng2Urteil = ng2Urteil")]
    check("f.grund !== 'tagesende_unklar' || f.quelle !== 'puls'" in u and "if(f.puls_flach !== 'tabelle') return" in u and "Math.abs(Number(f.balance_end) - Number(refBal)) > 0.01" in u
          and "Date.parse(f.puls_at || '') > Date.parse(f.tagesreset_at || '')" in u and "!ng2Alnum(f.puls_konto).includes(ext)" in u
          and "f.master_pl_schaetzung != null" in u and "if(b.puls_pause || r.polar_lauf) return" in u
          and "if(r.started_at || r.orbit_gesendet_at) return" in u and "if(r.master_pl != null) return" in u
          and "f.exit_fill || f.einstieg || f.einstieg_fill || f.einstieg_nq || f.preis || f.ticket || f.konto_geblowt || f.konto_weg" in u
          and "(b.tv && typeof b.tv === 'object' && Object.keys(b.tv).length)" in u and "if(b.manuell) return" in u, "NG2: JS-Regel = Spiegel hier")
    check("today_pnl" not in u, "NG2: Today's P&L zählt nie als Beweis (Tagesreset liest nach dem Handelstag)")
    t = html[html.index("async function ng2Tick(){"):html.index("setInterval(ng2Tick, 60000)")]
    check(".eq('status', 'review').is('master_pl', null)" in t and ".is('started_at', null).in('route', ['tvv2', 'tsv2'])" in t and ".eq('user_id', uid)" in t,
          "NG2: nur eigene Orbit/Topstep-Pläne in Überprüfen, nie gestartet, ohne P&L")
    vb = html[html.index("function ng2VergleichsBalance("):html.index("function ng2Urteil(")]
    check("Date.parse(bn.at) < c" in vb and "isFinite(lz) && lz < c" in vb and "fe.puls_at || fe.lesen_at" in vb and "ended_at" not in vb,
          "Gegenprüfung NG2: Vergleichs-Balance nur aus einer LESUNG vor dem Claim (nicht ended_at)")
    check("from('accounts').select('external_id').eq('id', r.master_account_id)" in t and "ng2Urteil(r, ref, extId)" in t, "Gegenprüfung NG2: External ID des Kontos frisch aus der DB")
    check("let ref = ng2VergleichsBalance(r.id, claim, vor)" in t and ".or(`started_at.gte.${seit},start_um_gestartet_at.gte.${seit}`).limit(1)" in t
          and "new Date(r.created_at || claim).toISOString()" in t
          and "if(eDz || (dazw && dazw.length)) continue" in t and "ref = ng2NotizBalance(r.notes)" in t,
          "NG2: Vergleichs-Balance = Ende eines früheren Plans, sonst Planer-Notiz nur ohne Zwischen-Trade")
    check("from('fremd_positionen')" in t and "if(eFp || (fp && fp.length)) continue" in t, "NG2: Hand-Trade im Fenster → bleibt")
    check("const nein = ng2Urteil(r, ref, extId)" in t and "await deWeg(r," in t and t.index("const nein = ng2Urteil(r, ref, extId)") < t.index("await deWeg(r,"),
          "NG2: Löschen nur nach dem vollen Urteil, über deWeg (Guard review/nie gestartet/P&L leer/updated_at)")
    d = html[html.index("async function deTick(){"):html.index("setInterval(deTick, 60000)")]
    mt = d[d.index("/* MT1 (06.11.2026"):d.index("if(u.art === 'offen') continue")]
    check("res.lesbar === false && /Master-Terminal läuft nicht/" in mt and "n < DE_OEFFNEN_MAX && frei" in mt and "ebnStartNah()" in mt and "polarLaeuft()" in mt
          and "mt5KontoBalanceJetzt(r.master_account_id, ri.masterLogin, {})" in mt and "_deVersucht.set(String(r.id), Date.now() - DE_PLAN_MS + 5 * 60000)" in mt
          and "if(lb && lb.ok){" in mt and mt.index("if(lb && lb.ok){") < mt.index("_deOeffnet.set(String(r.id), n + 1)")
          and "setTimeout(() => { _deAt = 0; deTick() }, 5 * 60000 + Math.floor(Math.random() * 120000))" in mt,
          "MT1: Terminal zu → zum Lesen öffnen (höchstens 2 echte Öffnungen je Plan, nie bei anstehendem Start/Polar), Deals nach 5–7 min (vor dem Leerlauf-Schließen 15–19 min)")
    check("const DE_OEFFNEN_MAX = 2, _deOeffnet = new Map()" in html, "MT1: Öffnen je Plan begrenzt")
    check(d.index("/* MT1 (06.11.2026") > d.index("const u = deUrteil(res, refBal)") and "if(u.art === 'unklar'){" in d[d.index("/* MT1 (06.11.2026"):],
          "MT1: danach bleibt der Plan unklar (Grund am Plan) — aufgelöst wird erst mit Deals (NG1-Weg)")
    ks = html[html.index("async function mt5KontoBalanceJetzt("):html.index("async function mt5KontoBalanceJetzt(") + 6000]
    check("master-order" not in ks and "start-terminal?file=" in ks and "mt5PulsBelegt()" in ks, "MT1: der Öffnen-Weg sendet nie eine Order und wartet, solange Puls arbeitet")

    # Fall Mike Lucid 5b2a2fd1 (Stand vor dem Abhaken)
    fall = {"status": "review", "route": "tvv2", "started_at": None, "master_pl": None, "slave_pl": None, "orbit_gesendet_at": None,
            "notes": "Auto-Planer · Etappe · Rest 9.000 $ bis Ziel · Balance 150.000 (TV)",
            "mt5_baseline": {"puls_unklar": {"code": "unklar"}, "start_fehler": {"unklar": True},
                             "final": {"grund": "tagesende_unklar", "quelle": "puls", "puls_flach": "tabelle", "balance_end": 150000, "today_pnl": 0,
                                       "puls_at": "2026-11-05T21:31:25.377Z", "tagesreset_at": "2026-11-05T21:30:01.381157+00:00", "puls_konto": "LFE15098258480001 150,000.00 USD",
                                       "exit_diag": {"fehler": "Exit-Fill über CDP kommt mit K4"}}}}
    check(notiz_balance(fall["notes"]) == 150000.0 and notiz_balance("Balance 97.537 (TV)") == 97537.0 and notiz_balance("Balance 91.636 (Echo)") is None,
          "Planer-Notiz: „Balance 150.000 (TV)“ → 150000, Echo-Notiz zählt hier nicht")
    check(urteil(fall, 150000.0) == "", "Fall Lucid 5b2a2fd1: flach, 150.000 = vorher → weg")
    check(urteil(fall, 150000.004) == "" and urteil(fall, 149999.76) == "Balance anders", "±0,01 $ (ein Tick + Gebühren ≈ −0,24 $ → bleibt)")
    def mit(**kw):
        r = {**fall, "mt5_baseline": {**fall["mt5_baseline"], "final": dict(fall["mt5_baseline"]["final"])}}
        for k, v in kw.items():
            if k.startswith("f_"):
                r["mt5_baseline"]["final"][k[2:]] = v
            elif k.startswith("b_"):
                r["mt5_baseline"][k[2:]] = v
            else:
                r[k] = v
        return r
    check(urteil(mit(f_puls_flach=None), 150000) != "", "nicht flach gelesen → bleibt")
    check(urteil(mit(f_puls_flach="unrealized_0"), 150000) != "" and urteil(mit(f_puls_flach="equity_gleich_balance"), 150000) != "", "nur die Positions-Tabelle zählt als flach")
    check(urteil(fall, 150000, ext="LFE15098258480002") != "" and urteil(mit(f_puls_konto=None), 150000) != "", "Lesung auf anderem/unbekanntem Konto → bleibt")
    check(urteil(mit(f_puls_at="2026-11-05T21:00:00Z"), 150000) != "", "Lesung vor dem Tagesreset → bleibt")
    check(urteil(mit(b_puls_pause={"at": "x"}), 150000) != "" and urteil(mit(polar_lauf=[{"id": 1}]), 150000) != "" and urteil(mit(f_master_pl_schaetzung=12.5), 150000) != "",
          "Puls-Pause / Polar / P&L-Schätzung → bleibt")
    check(urteil(mit(f_quelle="tagesreset"), 150000) != "", "noch keine Puls-Endlesung → bleibt")
    check(urteil(mit(f_exit_fill={"preis": 1}), 150000) != "" and urteil(mit(f_einstieg=26600), 150000) != "", "Fill/Einstieg → bleibt")
    check(urteil(mit(b_tv={"balance_start": 150000}), 150000) != "" and urteil(mit(b_hedge={"status": "offen"}), 150000) != "", "TV-Spur/Hedge → bleibt")
    check(urteil(mit(started_at="x"), 150000) != "" and urteil(mit(master_pl=0), 150000) != "" and urteil(mit(status="completed"), 150000) != "",
          "gestartet / P&L / schon abgehakt → bleibt")
    check(urteil(fall, None) != "" and urteil(mit(route="mt5"), 150000) != "", "ohne Vergleichs-Balance / Echo-Plan → bleibt (Echo über NG1)")
    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
