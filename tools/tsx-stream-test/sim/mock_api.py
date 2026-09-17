import json, time, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
T0 = time.time(); AUF, ZU = 8, 30
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); body = self.rfile.read(n).decode() if n else ""
        t = time.time() - T0
        if self.path.endswith("/api/Position/searchOpen"):
            pos = [{"id": 1, "accountId": 27613403, "contractId": "CON.F.US.MNQ.Z26", "creationTimestamp": "2026-09-17T10:19:35Z", "type": 1, "size": 1, "averagePrice": 29565.5}] if AUF <= t < ZU else []
            out = {"positions": pos, "success": True, "errorCode": 0, "errorMessage": None}
        elif self.path.endswith("/api/Auth/validate"):
            out = {"success": True, "newToken": "tok2"}
        elif self.path.endswith("/trade"):
            print(f"[{t:5.1f}s] METAAPI /trade  <- {body}", flush=True)
            out = {"numericCode": 10009, "stringCode": "TRADE_RETCODE_DONE", "message": "ok", "orderId": "9001", "positionId": "9001"}
        else:
            out = {"success": False}
        b = json.dumps(out).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
ThreadingHTTPServer(("127.0.0.1", 18801), H).serve_forever()
