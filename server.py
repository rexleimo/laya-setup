#!/usr/bin/env python3
"""Laya local decision API (stdlib only, no extra deps).

Endpoints
---------
GET  /health          liveness + which checkpoints are loaded/available
GET  /v1/models       OpenAI/TypeSafe-style model list
POST /predict         Laya-native  {"state": ..., "questions": {...}, "model"?}
POST /v1/systemone    TypeSafe-compatible drop-in for tools built on the
                      TypeSafe SDK (set TYPESAFE_BASE_URL to this server).
                      Request/response shapes match docs.typesafe.ai/api.
GET  /                tiny HTML status page with examples

Laya never generates text; it answers typed questions with calibrated
probabilities in one forward pass.
"""
import argparse
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from laya_runtime import LayaRuntime, canonical_model, to_typesafe_answers

RUNTIME = None  # type: LayaRuntime

EXAMPLE_QUESTIONS = {
    "department": {
        "type": "choice",
        "instructions": "Which team should handle this request?",
        "criteria": {
            "billing": "invoices, payments, refunds",
            "technical": "bugs, outages, system errors",
            "sales": "pricing, new contracts",
            "other": "everything else",
        },
    },
    "urgency": {
        "type": "score",
        "instructions": "How urgent is this request?",
        "criteria": [
            "no time pressure",
            "needs attention soon",
            "blocking issue or hard deadline",
        ],
    },
    "churn_risk": {
        "type": "noul",
        "instructions": "Does the user threaten to cancel or leave?",
    },
}

HTML_PAGE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>Laya local decision API</title>
<style>
 body{font-family:system-ui,'Segoe UI',sans-serif;max-width:860px;margin:40px auto;padding:0 16px;color:#1a1a2e;background:#fafafc}
 code,pre{background:#eef0f4;border-radius:6px;padding:2px 6px;font-size:13px}
 pre{padding:12px;overflow:auto}
 h1{font-size:26px} h2{font-size:18px;margin-top:28px}
 .ok{color:#0a7d32;font-weight:600}
</style></head><body>
<h1>Laya — local System&nbsp;1 decision API</h1>
<p>Status: <span class="ok">running</span> &middot; device: <code>%(device)s</code>
 &middot; checkpoints on disk: <code>%(available)s</code></p>
<p>Laya answers typed questions (choice / noul / score) with calibrated
probabilities in a single forward pass. It does not generate text.</p>

<h2>POST /predict</h2>
<pre>curl -s http://%(host)s:%(port)s/predict -H "Content-Type: application/json" -d @- &lt;&lt;'EOF'
{
  "state": "We were billed twice for March. Please refund the duplicate today or we will cancel.",
  "questions": %(questions)s
}
EOF</pre>

<h2>POST /v1/systemone &nbsp;<small>(TypeSafe-compatible drop-in)</small></h2>
<pre>curl -s http://%(host)s:%(port)s/v1/systemone -H "Content-Type: application/json" -d @- &lt;&lt;'EOF'
{
  "state": "We were billed twice for March. Please refund the duplicate today or we will cancel.",
  "model": "jev-latest",
  "questions": {"churn_risk": {"type": "noul", "instructions": "Does the user threaten to cancel?"}}
}
EOF</pre>
<p>Point TypeSafe-SDK tooling here with
<code>TYPESAFE_BASE_URL=http://%(host)s:%(port)s</code>.</p>

<h2>GET /health</h2>
<pre>curl -s http://%(host)s:%(port)s/health</pre>
<p><small>API docs: <a href="https://docs.typesafe.ai/api">docs.typesafe.ai/api</a>
 &middot; Laya: <a href="https://github.com/NandhaKishorM/laya">github.com/NandhaKishorM/laya</a></small></p>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "LayaLocalAPI/0.3.4"
    protocol_version = "HTTP/1.1"

    # ---- helpers -----------------------------------------------------
    def _send(self, code, payload, ctype="application/json"):
        if isinstance(payload, (dict, list)):
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        elif isinstance(payload, str):
            body = payload.encode("utf-8")
        else:
            body = payload
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as exc:
            raise ValueError("invalid JSON body: %s" % exc)

    def log_message(self, fmt, *args):
        sys.stdout.write(
            "[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), fmt % args)
        )
        sys.stdout.flush()

    # ---- routes ------------------------------------------------------
    def do_OPTIONS(self):
        self._send(204, b"")

    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        try:
            if path == "/health":
                self._send(
                    200,
                    {
                        "status": "ok",
                        "device": RUNTIME.device,
                        "model_dir": RUNTIME.model_dir,
                        "available": RUNTIME.available(),
                        "loaded": sorted(RUNTIME._agents.keys()),
                    },
                )
            elif path == "/v1/models":
                names = RUNTIME.available() or ["english"]
                self._send(
                    200,
                    {
                        "object": "list",
                        "data": [
                            {
                                "id": "jev-latest" if n == "english" else "laya-" + n,
                                "object": "model",
                                "owned_by": "convaiinnovations",
                                "checkpoint": n,
                            }
                            for n in names
                        ],
                    },
                )
            elif path == "/":
                html = HTML_PAGE % {
                    "device": RUNTIME.device,
                    "available": ", ".join(RUNTIME.available()) or "<none>",
                    "host": self.server.server_address[0],
                    "port": self.server.server_address[1],
                    "questions": json.dumps(EXAMPLE_QUESTIONS, indent=2, ensure_ascii=False),
                }
                self._send(200, html, ctype="text/html")
            else:
                self._send(404, {"error": "not found: %s" % path})
        except Exception as exc:  # pragma: no cover
            self._send(500, {"error": str(exc)})

    def do_POST(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        try:
            body = self._read_json()
            if path == "/predict":
                self._handle_predict(body)
            elif path == "/v1/systemone":
                self._handle_systemone(body)
            else:
                self._send(404, {"error": "not found: %s" % path})
        except ValueError as exc:
            self._send(400, {"error": str(exc)})
        except (KeyError, FileNotFoundError) as exc:
            self._send(400, {"error": str(exc)})
        except Exception as exc:
            self.log_message("internal error: %s", exc)
            self._send(500, {"error": str(exc)})

    # ---- handlers ----------------------------------------------------
    def _handle_predict(self, body):
        state = body.get("state")
        if state is None:
            raise ValueError("'state' is required (text, email, ticket or JSON)")
        questions = body.get("questions")
        result = RUNTIME.predict(state, questions, model=body.get("model"))
        self._send(200, result)

    def _handle_systemone(self, body):
        state = body.get("state")
        if state is None:
            raise ValueError("'state' is required (text, email, ticket or JSON)")
        questions = body.get("questions")
        result = RUNTIME.predict(state, questions, model=body.get("model"))
        self._send(
            200,
            {
                "model": "jev-latest" if result["model"] == "english" else "laya-" + result["model"],
                "usage": {"input_tokens": None, "output_tokens": None},
                "answers": to_typesafe_answers(questions, result["answers"]),
                "laya": {
                    "checkpoint": result["model"],
                    "device": result["device"],
                    "latency_ms": result["latency_ms"],
                },
            },
        )


def main():
    global RUNTIME
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description="Laya local decision API")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8399)
    ap.add_argument("--model-dir", default=os.path.join(here, "models", "laya"))
    ap.add_argument("--device", default="auto", help="auto | cpu | cuda")
    ap.add_argument(
        "--preload",
        default="",
        help="comma-separated checkpoints to load at startup (default: english)",
    )
    args = ap.parse_args()

    RUNTIME = LayaRuntime(model_dir=args.model_dir, device=args.device)
    avail = RUNTIME.available()
    if not avail:
        print(
            "!! No Laya weights found in %s\n"
            "!! Run  start.bat  first (it downloads ~840 MB), or:\n"
            "!!   python download_model.py --variant english" % RUNTIME.model_dir,
            file=sys.stderr,
        )
        sys.exit(2)

    for name in [n.strip() for n in args.preload.split(",") if n.strip()] or ["english"]:
        try:
            RUNTIME.load(name)
            print("loaded checkpoint: %s (%s)" % (name, RUNTIME.device))
        except Exception as exc:
            print("could not preload %r: %s" % (name, exc), file=sys.stderr)

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print("")
    print("  Laya local decision API")
    print("  ------------------------------------------------")
    print("  URL        : http://%s:%d" % (args.host, args.port))
    print("  Device     : %s" % RUNTIME.device)
    print("  Checkpoints: %s" % ", ".join(avail))
    print("  Try        : curl -s http://%s:%d/health" % (args.host, args.port))
    print("  Drop-in    : set TYPESAFE_BASE_URL=http://%s:%d" % (args.host, args.port))
    print("  Stop       : Ctrl+C")
    print("")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
