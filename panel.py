#!/usr/bin/env python3
"""一键启动 — Web 管理面板 (panel.py)。

用 Python 标准库 http.server 起一个本地管理服务 (默认 127.0.0.1:8398)，
浏览器打开即是图形化管理界面：启停服务、看健康/模型状态、下载权重、
安装依赖、看实时日志。

为什么不再用 tkinter：很多 Python (尤其 uv 安装的 standalone 版、精简安装)
默认不带 tkinter，双击 GUI 会因 import tkinter 失败而"毫无反应"。改用浏览器
面板后，跨平台 100% 可用 (浏览器人人都有)，也更好看。

启动：  python onekey.py panel      (或 start-gui.bat / start-gui.sh)
"""
import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import onekey

HOST = "127.0.0.1"
PORT = 8398

# onekey 的日志统一进内存缓冲，供前端 /api/logs 拉取
_LOG = []
_LOCK = threading.Lock()
_TORCH = {"v": None}


def _emit(line):
    with _LOCK:
        _LOG.append(line)


onekey.set_emitter(_emit)


def torch_status():
    if _TORCH["v"] is None:
        vp = onekey.venv_python()
        _TORCH["v"] = onekey.torch_installed(vp) if vp.exists() else None
    return _TORCH["v"]


def status():
    st = onekey.collect_status()
    st["health"] = onekey.health()
    st["torch"] = torch_status()
    return st


def logs():
    with _LOCK:
        buf = list(_LOG[-300:])
    tail = ""
    try:
        tail = "\n".join(onekey.LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-60:])
    except Exception:
        pass
    return "\n".join(buf) + (("\n" + tail) if tail else "")


# ---- 后台动作 (可能耗时，放线程里跑，HTTP 立即返回) ----
def _bg(fn):
    def run():
        try:
            fn()
        except Exception as exc:
            _emit("[panel] 操作失败: %s" % exc)
    threading.Thread(target=run, daemon=True).start()


def do_start():
    vp = onekey.ensure_venv()
    onekey.install_base(vp)
    onekey.install_torch(vp, "cpu")
    if not onekey.model_ready():
        onekey.log("未发现模型权重，开始下载 …")
        onekey.download_model(vp, "english")
    onekey.start_server(vp, "english", detach=True)


def do_download():
    vp = onekey.ensure_venv()
    onekey.download_model(vp, "english")


def do_mcp():
    onekey.install_mcp(onekey.ensure_venv())


def do_gpu():
    if onekey.IS_MAC:
        onekey.log("macOS 无 CUDA；默认 torch 已含 CPU/MPS。")
        return
    onekey.install_torch(onekey.ensure_venv(), "gpu")
    _TORCH["v"] = None  # 让下次刷新重新探测


def do_doctor():
    onekey.doctor()


def do_web():
    webbrowser.open(onekey.web_url())


ROUTES = {
    "start": do_start, "stop": onekey.stop_server, "download": do_download,
    "mcp": do_mcp, "gpu": do_gpu, "doctor": do_doctor, "web": do_web,
}


HTML = r"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>一键启动 · 管理面板</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='90'%3E%E2%9A%A1%3C/text%3E%3C/svg%3E">
<style>
:root{--bg:#0b1020;--bg2:#121a3a;--card:#151d3b;--line:#243056;--txt:#e8ecf8;--muted:#9aa6c9;
--brand:#6ea8fe;--brand2:#a78bfa;--ok:#34d399;--warn:#fbbf24;--err:#f87171;--code:#0e1630;
--sans:system-ui,-apple-system,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif;
--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
*{box-sizing:border-box}
body{margin:0;font-family:var(--sans);color:var(--txt);
background:radial-gradient(1000px 500px at 75% -10%,#1b2a5e 0,transparent 60%),linear-gradient(180deg,var(--bg),var(--bg2));min-height:100vh}
.wrap{max-width:960px;margin:0 auto;padding:0 20px}
a{color:var(--brand);text-decoration:none}
.top{display:flex;align-items:center;justify-content:space-between;padding:22px 0 6px}
.top h1{font-size:22px;margin:0}
.lamp{display:inline-flex;align-items:center;gap:8px;font-size:13px;color:var(--muted)}
.dot{width:10px;height:10px;border-radius:50%;background:#555;display:inline-block}
.dot.on{background:var(--ok);box-shadow:0 0 10px var(--ok)}
.dot.off{background:var(--err)}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px;margin:16px 0}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.row{display:flex;justify-content:space-between;font-size:14px;padding:8px 10px;background:rgba(255,255,255,.02);border-radius:10px}
.row span:first-child{color:var(--muted)}
.btns{display:flex;gap:8px;flex-wrap:wrap;margin-top:4px}
button{background:var(--code);border:1px solid var(--line);color:var(--muted);border-radius:10px;padding:9px 14px;font-size:13.5px;cursor:pointer;transition:.15s}
button:hover{color:var(--txt);border-color:var(--brand)}
button.pri{background:linear-gradient(90deg,var(--brand),var(--brand2));color:#0b1020;font-weight:700;border-color:transparent}
button:disabled{opacity:.5;cursor:wait}
#log{white-space:pre-wrap;font-family:var(--mono);font-size:12.5px;line-height:1.6;color:#a9d6ff;
background:var(--code);border:1px solid var(--line);border-radius:12px;padding:14px;height:220px;overflow:auto}
h2{font-size:14px;color:var(--muted);margin:0 0 12px;font-weight:600}
footer{color:var(--muted);font-size:13px;text-align:center;padding:18px 0}
@media(max-width:720px){.grid{grid-template-columns:1fr}}
</style></head><body><div class="wrap">
<div class="top">
  <h1>⚡ 一键启动 · 管理面板</h1>
  <span class="lamp"><span id="lamp" class="dot"></span><span id="lamptxt">检测中…</span></span>
</div>

<div class="card"><h2>状态</h2>
<div class="grid">
  <div class="row"><span>平台</span><span id="platform">–</span></div>
  <div class="row"><span>虚拟环境</span><span id="venv">–</span></div>
  <div class="row"><span>PyTorch</span><span id="torch">–</span></div>
  <div class="row"><span>模型权重</span><span id="model">–</span></div>
  <div class="row"><span>服务</span><span id="service">–</span></div>
  <div class="row"><span>PID</span><span id="pid">–</span></div>
  <div class="row" style="grid-column:1/-1"><span>健康检查</span><span id="health">–</span></div>
</div></div>

<div class="card"><h2>操作</h2>
<div class="btns">
  <button class="pri" onclick="act('start')">▶ 启动服务</button>
  <button onclick="act('stop')">■ 停止服务</button>
  <button onclick="act('download')">⬇ 下载模型</button>
  <button onclick="act('mcp')">🔌 安装 MCP 依赖</button>
  <button onclick="act('gpu')">🎮 安装 GPU(CUDA)</button>
  <button onclick="act('doctor')">🩺 环境自检</button>
  <button onclick="act('web')">🌐 打开状态页</button>
  <a href="demo.html" target="_blank"><button>🧪 在线试用</button></a>
</div></div>

<div class="card"><h2>日志</h2><div id="log">等待操作…</div></div>

<footer>⚡ 一键启动 Laya · 本地推理 · <a href="index.html">首页</a> · <a href="https://github.com/rexleimo/laya-setup" target="_blank">GitHub</a></footer>
</div>
<script>
function tf(v){return {true:"已安装",false:"未安装",null:"—"}[v];}
async function refresh(){
  try{
    const s=await (await fetch("/api/status")).json();
    platform.textContent=s.platform; venv.textContent=s.venv?"就绪":"缺失";
    torch.textContent=tf(s.torch); model.textContent=s.model?"已就绪":"未下载";
    const up=s.running||s.external;
    service.textContent=s.external?"运行中(外部)":(s.running?"运行中":"已停止");
    pid.textContent=s.pid||"-";
    if(s.health) health.textContent="OK · device="+s.health.device+" · loaded="+((s.health.loaded||[]).join(",")||"无");
    else health.textContent=up?"启动中 / 预热 …":"无响应";
    lamp.className="dot "+(up?"on":"off"); lamptxt.textContent=up?"运行中":"已停止";
  }catch(e){ lamptxt.textContent="面板错误"; }
  try{ const l=await (await fetch("/api/logs")).json(); log.textContent=l.logs||"(暂无)"; log.scrollTop=log.scrollHeight; }catch(e){}
}
function act(n){ fetch("/api/"+n,{method:"POST"}).then(refresh); }
refresh(); setInterval(refresh,3000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def do_GET(self):
        p = self.path.split("?", 1)[0]
        if p == "/":
            self._send(200, HTML, "text/html")
        elif p == "/api/status":
            self._send(200, json.dumps(status(), ensure_ascii=False))
        elif p == "/api/logs":
            self._send(200, json.dumps({"logs": logs()}, ensure_ascii=False))
        else:
            self._send(404, '{"error":"not found"}')

    def do_POST(self):
        key = self.path.split("?", 1)[0].rsplit("/", 1)[-1]
        if key in ROUTES:
            _bg(ROUTES[key])
            self._send(200, '{"ok":true}')
        else:
            self._send(404, '{"error":"not found"}')


def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = "http://%s:%d/" % (HOST, PORT)
    print("[panel] 管理面板已启动: %s" % url)
    print("[panel] 已尝试用默认浏览器打开；若未打开请手动访问上面的地址。")
    print("[panel] 按 Ctrl+C 停止面板。")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\n[panel] 已停止。")


if __name__ == "__main__":
    main()
