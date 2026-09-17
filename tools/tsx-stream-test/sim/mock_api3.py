import json, time, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
T0 = time.time()
def orders(t):
    o = lambda oid, typ, **kw: dict({"id": oid, "accountId": 27613403, "contractId": "CON.F.US.MNQ.Z26", "status": 1, "type": typ, "side": 1, "size": 1, "limitPrice": None, "stopPrice": None}, **kw)
    if t < 10: return []
    if t < 18: return [o(1, 4, stopPrice=29515.5), o(2, 1, limitPrice=29665.5)]
    if t < 26: return [o(1, 4, stopPrice=29580.0), o(2, 1, limitPrice=29700.0)]   # SL in den Gewinn gezogen
    return [o(1, 4, stopPrice=29590.0)]                                            # TP entfernt
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _out(self, out):
        b = json.dumps(out).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if "/symbols/" in self.path: return self._out({"symbol": "NAS100", "digits": 2, "point": 0.01})
        if "/positions/" in self.path: return self._out({"id": "9001", "type": "POSITION_TYPE_SELL", "symbol": "NAS100", "openPrice": 29350.25, "volume": 0.02})
        self._out({})
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); body = self.rfile.read(n).decode() if n else ""
        t = time.time() - T0
        if self.path.endswith("/api/Position/searchOpen"):
            pos = [{"id": 1, "accountId": 27613403, "contractId": "CON.F.US.MNQ.Z26", "type": 1, "size": 1, "averagePrice": 29565.5}] if 6 <= t < 40 else []
            return self._out({"positions": pos, "success": True})
        if self.path.endswith("/api/Order/searchOpen"):
            return self._out({"orders": orders(t), "success": True})
        if self.path.endswith("/api/Auth/validate"):
            return self._out({"success": True, "newToken": "tok2"})
        if self.path.endswith("/trade"):
            print(f"[{t:5.1f}s] METAAPI /trade <- {body}", flush=True)
            return self._out({"numericCode": 10009, "stringCode": "TRADE_RETCODE_DONE", "orderId": "9001", "positionId": "9001"})
        self._out({"success": False})
ThreadingHTTPServer(("127.0.0.1", 18801), H).serve_forever()
