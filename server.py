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
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Laya local decision API</title>
<link rel="icon" href="data:image/svg+xml,%%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%%3E%%3Crect width='64' height='64' rx='14' fill='%%232563ff'/%%3E%%3Cpath d='M35 8 16 37h12l-2 19 18-29H32l3-19z' fill='%%23fff'/%%3E%%3C/svg%%3E">
<style>
:root{--bg:#fafafa;--card:#ffffff;--soft:#f2f4f7;--line:rgba(27,27,31,.10);--txt:#1b1b1f;
--muted:rgba(27,27,31,.62);--faint:rgba(27,27,31,.45);--brand:#2563ff;--dark:#05060e;
--sans:Inter,-apple-system,'Segoe UI',Roboto,'PingFang SC','Microsoft YaHei',sans-serif;
--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
*{box-sizing:border-box}
body{margin:0;font-family:var(--sans);color:var(--txt);background:var(--bg);
 -webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
.wrap{max-width:860px;margin:0 auto;padding:0 24px}
nav{backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);
 background:rgba(5,6,14,.78);border-bottom:1px solid rgba(255,255,255,.06);color:#fff}
.navin{display:flex;align-items:center;justify-content:space-between;padding:11px 0}
.logo{display:flex;align-items:center;gap:10px;font-weight:600;font-size:15.5px}
.logo small{color:rgba(255,255,255,.45);font-weight:400;font-size:12px;margin-left:2px}
.logochip{width:28px;height:28px;border-radius:8px;background:var(--brand);display:inline-flex;
 align-items:center;justify-content:center;color:#fff;flex:none}
svg.ic{stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.host{font-family:var(--mono);font-size:12px;color:rgba(255,255,255,.55)}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px 22px;margin:16px 0}
.hero{margin-top:24px}
h1{font-size:23px;margin:0 0 10px;letter-spacing:-.01em}
.desc{font-size:14.5px;line-height:1.65;color:var(--muted);margin:0 0 16px}
.badges{display:flex;gap:8px;flex-wrap:wrap}
.badge{display:inline-flex;align-items:center;gap:7px;background:var(--soft);border-radius:999px;
 padding:5px 13px;font-size:12.5px;font-weight:600}
.badge b{font-weight:550;font-family:var(--mono);font-size:12px}
.badge.ok{background:#e8f7ee;color:#0a7d32}
.dot{width:7px;height:7px;border-radius:50%%;background:#16a34a;flex:none}
h2{font-family:var(--mono);font-size:14.5px;font-weight:650;margin:0 0 12px}
h2 small{font-family:var(--sans);color:var(--muted);font-weight:450;font-size:12.5px;margin-left:6px}
pre{font-family:var(--mono);font-size:12.5px;line-height:1.65;color:#a9bce0;background:var(--dark);
 border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:13px 15px;overflow:auto;margin:0}
code{font-family:var(--mono);font-size:12.5px;background:var(--soft);border-radius:6px;padding:2px 7px}
.note{font-size:13.5px;color:var(--muted);margin:12px 0 0}
footer{color:var(--faint);font-size:12.5px;text-align:center;padding:22px 0}
footer a{color:var(--muted)} footer a:hover{color:var(--brand)}
</style></head><body>
<nav><div class="wrap navin">
 <span class="logo"><span class="logochip"><svg class="ic" width="15" height="15" viewBox="0 0 24 24"><path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/></svg></span>Laya <small>local decision API</small></span>
 <span class="host">%(host)s:%(port)s</span>
</div></nav>
<div class="wrap">
<div class="card hero">
 <h1>Laya — local System&nbsp;1 decision API</h1>
 <p class="desc">Laya answers typed questions (choice / noul / score) with calibrated
 probabilities in a single forward pass. It does not generate text.</p>
 <div class="badges">
  <span class="badge ok"><span class="dot"></span>running</span>
  <span class="badge">device <b>%(device)s</b></span>
  <span class="badge">checkpoints <b>%(available)s</b></span>
 </div>
</div>

<div class="card"><h2>POST /predict</h2>
<pre>curl -s http://%(host)s:%(port)s/predict -H "Content-Type: application/json" -d @- &lt;&lt;'EOF'
{
  "state": "We were billed twice for March. Please refund the duplicate today or we will cancel.",
  "questions": %(questions)s
}
EOF</pre>
</div>

<div class="card"><h2>POST /v1/systemone <small>TypeSafe-compatible drop-in</small></h2>
<pre>curl -s http://%(host)s:%(port)s/v1/systemone -H "Content-Type: application/json" -d @- &lt;&lt;'EOF'
{
  "state": "We were billed twice for March. Please refund the duplicate today or we will cancel.",
  "model": "jev-latest",
  "questions": {"churn_risk": {"type": "noul", "instructions": "Does the user threaten to cancel?"}}
}
EOF</pre>
<p class="note">Point TypeSafe-SDK tooling here with
<code>TYPESAFE_BASE_URL=http://%(host)s:%(port)s</code>.</p>
</div>

<div class="card"><h2>GET /health</h2>
<pre>curl -s http://%(host)s:%(port)s/health</pre>
</div>

<footer>API docs: <a href="https://docs.typesafe.ai/api">docs.typesafe.ai/api</a>
 &middot; Laya: <a href="https://github.com/NandhaKishorM/laya">github.com/NandhaKishorM/laya</a>
 &middot; More from RexAI: <a href="https://rexai.top/products/">rexai.top/products</a></footer>
</div></body></html>"""


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
