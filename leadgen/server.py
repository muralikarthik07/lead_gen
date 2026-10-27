"""Tiny stdlib HTTP server: static single-page app (leadgen/web) + read-only JSON API over an exported dataset."""
import json
import mimetypes
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from . import evaluate as ev
from . import validate
from .store import Store

WEB = os.path.join(os.path.dirname(__file__), "web")
_lock = threading.Lock()


def make_handler(store, quiet=True):
    def q1(qs, k, d=""):
        return qs.get(k, [d])[0]

    class Handler(BaseHTTPRequestHandler):
        server_version = "LeadScope/1.0"

        def log_message(self, fmt, *args):
            if not quiet:
                super().log_message(fmt, *args)

        def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
            if not isinstance(body, (bytes, bytearray)):
                body = json.dumps(body, separators=(",", ":")).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _err(self, code, msg):
            self._send(code, {"error": msg})

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            u = urlparse(self.path)
            path, qs = unquote(u.path), parse_qs(u.query)
            try:
                if path.startswith("/api/"):
                    return self._api(path[5:].strip("/"), qs)
                return self._static(path)
            except (ValueError, KeyError) as e:
                return self._err(400, f"bad request: {e}")
            except Exception as e:  # pragma: no cover
                return self._err(500, f"server error: {e!r}")

        def do_POST(self):
            path = urlparse(self.path).path
            if path == "/api/revalidate":
                with _lock:
                    s = validate.validate(store.out)
                    e = ev.evaluate(store.out)
                return self._send(200, {"validation": s, "evaluation": e})
            return self._err(404, "unknown endpoint")

        def _static(self, path):
            rel = "index.html" if path in ("", "/") else path.lstrip("/")
            full = os.path.realpath(os.path.join(WEB, rel))
            if not full.startswith(os.path.realpath(WEB) + os.sep) or not os.path.isfile(full):
                full = os.path.join(WEB, "index.html")        # SPA fallback (hash router makes this rare)
                if "." in os.path.basename(rel):
                    return self._err(404, "not found")
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
                ctype += "; charset=utf-8"
            with open(full, "rb") as f:
                self._send(200, f.read(), ctype)

        def _api(self, route, qs):
            truth = q1(qs, "truth") in ("1", "true")
            parts = route.split("/")
            if route == "health":
                return self._send(200, {"status": "ok", "dataset": os.path.abspath(store.out)})
            if route == "overview":
                return self._send(200, store.overview)
            if route == "meta":
                return self._send(200, {"config": store.cfg, "command": store.meta.get("command"), "generator": store.meta.get("generator"),
                                        "manifest": store.json_file("MANIFEST.json"), "env": store.json_file("run_env.json")})
            if route == "leads":
                return self._send(200, store.query_leads(
                    q=q1(qs, "q"), tier=q1(qs, "tier"), status=q1(qs, "status"), source=q1(qs, "source"), territory=q1(qs, "territory"),
                    product=q1(qs, "product"), flag=q1(qs, "flag"), sort=q1(qs, "sort", "created"), direction=q1(qs, "dir", "desc"),
                    page=q1(qs, "page", "1"), size=q1(qs, "size", "25"), truth=truth))
            if len(parts) == 2 and parts[0] == "leads":
                d = store.lead_detail(parts[1], truth=truth)
                return self._send(200, d) if d else self._err(404, "lead not found")
            if route == "opportunities":
                return self._send(200, store.query_opps(stage=q1(qs, "stage"), status=q1(qs, "status"), product=q1(qs, "product"),
                                                         page=q1(qs, "page", "1"), size=q1(qs, "size", "25"), sort=q1(qs, "sort", "created"),
                                                         direction=q1(qs, "dir", "desc")))
            if route == "validation":
                return self._send(200, store.json_file("validation_summary.json") or validate.validate(store.out))
            if route == "evaluation":
                return self._send(200, store.json_file("evaluation_report.json") or ev.evaluate(store.out))
            if route == "anomalies":
                return self._send(200, store.anomalies())
            if route == "dictionary":
                return self._send(200, store.dictionary())
            return self._err(404, "unknown endpoint")

    return Handler


def serve(out, host="127.0.0.1", port=8000, quiet=False, ready=None):
    store = Store(out)
    httpd = ThreadingHTTPServer((host, port), make_handler(store, quiet))
    if ready:
        ready(httpd)
    return httpd
