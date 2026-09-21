#!/usr/bin/env python3
"""一键启动 — Web 管理面板 (panel.py)。

用 Python 标准库 http.server 起一个本地管理服务 (默认 127.0.0.1:8398)，
浏览器打开即是图形化管理界面：启停服务、看健康/模型状态、下载权重、
安装依赖、看实时日志。HTMX 工程方式：panel.html 只是外壳，页面内容
由本文件渲染成 HTML 片段 (GET /frag/*)，htmx 负责轮询换片，前端零渲染逻辑。

启动：  python onekey.py panel      (或 start-gui.bat / start-gui.sh)
"""
import re
import threading
import time
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import onekey

HERE = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8398

# 面板只对外提供自己的界面 (外壳 + htmx 库)。demo.html / index.html / hero.png
# 是仓库里的静态体验页，不属于运行时，不在这里暴露——运行时能访问的
# 只有本面板 (8398) 与 API 服务 (8399)。
STATIC = {
    "/": ("panel.html", "text/html"),
    "/panel.html": ("panel.html", "text/html"),
    "/htmx.min.js": ("htmx.min.js", "application/javascript"),
    "/idiomorph-ext.min.js": ("idiomorph-ext.min.js", "application/javascript"),
}

# onekey 的日志统一进内存环形缓冲，供前端拉取；server.log 由 _pump_server_log
# 增量泵入同一个缓冲，前端只读这一份，不会出现重复/拼接到一起的日志。
_LOG = deque(maxlen=500)
_LOCK = threading.Lock()
_TORCH = {"v": None}

# 后台任务状态：同一时刻只允许一个耗时操作 (装依赖/下模型会互相踩)，
# 忙时新请求直接拒绝，前端据此禁用按钮并给出提示。
_TASK = {"name": None, "state": None, "done": 0}
_TASK_LOCK = threading.Lock()

# 面板自己每 2.5s 轮询一次健康检查，server.log 会随之记一笔访问日志；
# 不过滤的话日志框很快就被心跳刷屏，真正有用的内容被顶掉。
_LOG_NOISE = re.compile(r'"GET /(health|v1/models)[^"]*" 200')


def _emit(line):
    with _LOCK:
        _LOG.append(line)


onekey.set_emitter(_emit)


def _pump_server_log():
    """把 .onekey/server.log 的增量内容追加进内存缓冲。

    面板启动时先读入文件末尾若干行 (保留上次运行的现场)，之后每次只读
    新增字节；文件被截断/轮转则从头再读。
    """
    global _LOG_OFFSET
    try:
        size = onekey.LOG_FILE.stat().st_size
    except OSError:
        return
    if size < _LOG_OFFSET:  # 日志被清空/重建
        _LOG_OFFSET = 0
    if size == _LOG_OFFSET:
        return
    try:
        with open(onekey.LOG_FILE, "rb") as f:
            if _LOG_OFFSET == 0 and size > 16 * 1024:
                f.seek(size - 16 * 1024)  # 首次只回看最后 16KB
                f.readline()  # 丢掉半行
                _LOG_OFFSET = f.tell()
            f.seek(_LOG_OFFSET)
            data = f.read()
        _LOG_OFFSET += len(data)
        lines = [ln for ln in data.decode("utf-8", "replace").splitlines() if ln.strip()]
        lines = [ln for ln in lines if not _LOG_NOISE.search(ln)]
        with _LOCK:
            _LOG.extend(lines)
    except OSError:
        pass


_LOG_OFFSET = 0
_pump_server_log()


def torch_status():
    if _TORCH["v"] is None:
        vp = onekey.venv_python()
        _TORCH["v"] = onekey.torch_installed(vp) if vp.exists() else None
    return _TORCH["v"]


def state():
    """一次轮询要用的全部数据：状态 + 任务 + 日志，减少请求数。"""
    h = onekey.health()
    st = onekey.collect_status(health_result=h)
    st["torch"] = torch_status()
    with _TASK_LOCK:
        st["task"] = dict(_TASK)
    _pump_server_log()
    with _LOCK:
        st["logs"] = list(_LOG)[-300:]
    return st


# ---- 后台动作 (可能耗时，放线程里跑，HTTP 立即返回) ----
def _bg(name, fn):
    """提交一个后台任务。有任务在跑时返回 False (忙)，避免并发装环境。"""
    with _TASK_LOCK:
        if _TASK["state"] == "running":
            return False
        _TASK["name"] = name
        _TASK["state"] = "running"
        _TASK["done"] = 0

    def run():
        try:
            fn()
            _TASK["state"] = "ok"
        except Exception as exc:
            _TASK["state"] = "error"
            _emit("[panel] ✗ %s 失败: %s" % (name, exc))
        finally:
            _TASK["done"] = time.time()

    threading.Thread(target=run, daemon=True).start()
    return True


def do_start():
    vp = onekey.ensure_venv()
    onekey.install_base(vp)
    onekey.install_torch(vp, "cpu")
    if not onekey.model_ready():
        onekey.log("未发现模型权重，开始下载 …")
        onekey.download_model(vp, "english")
    onekey.start_server(vp, "english", detach=True)
    _TORCH["v"] = None  # torch 可能刚装上，让下次刷新重新探测


def do_download():
    vp = onekey.ensure_venv()
    onekey.download_model(vp, "english")


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
    "start": ("启动服务", do_start),
    "stop": ("停止服务", onekey.stop_server),
    "download": ("下载模型", do_download),
    "gpu": ("安装 GPU torch", do_gpu),
    "doctor": ("环境自检", do_doctor),
    "web": ("打开状态页", do_web),
}




# ---- HTML 片段渲染 (HTMX：服务端吐片段，前端零渲染逻辑) ----
def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# 任务完成提示只发一次：记下上次已提醒的 done 时间戳
_NOTIFIED = {"done": 0}


# Lucide 图标 (stroke=currentColor)，按钮内联使用，替代文字前后的装饰符号
_IC = {
    "play": '<path d="m6 3 14 9-14 9V3z"/>',
    "stop": '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    "ext": ('<path d="M15 3h6v6"/><path d="M10 14 21 3"/>'
            '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>'),
    "down": ('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
             '<path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>'),
    "box": ('<path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/>'
            '<path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>'),
    "zap": ('<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>'),
    "shield": ('<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>'
               '<path d="m9 12 2 2 4-4"/>'),
}


def _ic(name):
    return '<svg class="ic" width="14" height="14" viewBox="0 0 24 24">%s</svg>' % _IC[name]


def _tile(k, v, vcls="", dot=""):
    """状态卡里的一个小瓦片；dot 给服务这类带状态灯的值。"""
    d = '<span class="cdot %s"></span>' % dot if dot else ""
    vc = ' %s' % vcls if vcls else ""
    return '<div class="tile"><div class="k">%s</div><div class="v%s">%s%s</div></div>' % (k, vc, d, v)


def _button(key, label, task, icon, pri=False, danger=False, confirm=""):
    """key 是 ROUTES 动作名，label 是按钮文案；有任务在跑时整排禁用（当前任务高亮）。
    pri=蓝色主按钮（未运行时的「启动服务」），danger=红色（运行中的「停止服务」）。"""
    ic = _ic(icon)
    if task["state"] == "running":
        if task["name"] == ROUTES[key][0]:
            return '<button class="busy" disabled>%s %s …</button>' % (ic, label)
        return '<button disabled>%s %s</button>' % (ic, label)
    cls = "pri" if pri else ("danger" if danger else "")
    attr = ' class="%s"' % cls if cls else ""
    cf = ' hx-confirm="%s"' % confirm if confirm else ""
    return ('<button%s hx-post="/api/action/%s" hx-target="#toasts" hx-swap="beforeend"'
            ' hx-disabled-elt="this"%s>%s %s</button>') % (attr, key, cf, ic, label)


def _lamp(task, up):
    if task["state"] == "running":
        cls, txt = "dot busy", task["name"] + " …"
    elif up:
        cls, txt = "dot on", "运行中"
    else:
        cls, txt = "dot off", "已停止"
    return ('<span class="lamp" id="lampbox" hx-swap-oob="outerHTML">'
            '<span class="%s"></span><span>%s</span></span>' % (cls, txt))


def frag_state():
    """主区域片段：状态 + 服务控制 + 环境维护三张卡片，附带 oob 的顶栏状态灯。"""
    st = state()
    task = st["task"]
    up = st["running"] or st["external"]

    svc_cls, svc_txt = ("warn", "运行中 (外部进程)") if st["external"] else \
                       (("ok", "运行中") if up else ("err", "已停止"))
    if st["health"]:
        health = "OK · device=%s · loaded=%s" % (
            st["health"].get("device", "?"),
            ",".join(st["health"].get("loaded") or []) or "无")
        h_cls = "ok"
    else:
        health = "启动中 / 模型预热 …（首次约 30 秒）" if up else "无响应"
        h_cls = "warn" if up else "err"
    torch_txt = {True: "已安装", False: "未安装"}.get(st["torch"], "—")

    if not st["venv"] or st["torch"] is False or not st["model"]:
        tip = "环境不完整：点「启动服务」会自动补齐依赖并下载权重。"
    elif not up and task["state"] != "running":
        tip = "环境就绪，点「启动服务」即可（模型加载约 30 秒）。"
    elif up and st["health"]:
        tip = "服务正常。可在 8399 状态页试用，或直接 POST /predict。"
    else:
        tip = ""

    out = ['<div id="ui" hx-get="/frag/state" hx-trigger="every 2.5s" hx-swap="morph:outerHTML">']

    out.append('<div class="card"><div class="cardhead"><h2>状态</h2>'
               '<span class="sync">自动刷新 · %s</span></div><div class="grid">'
               % time.strftime("%H:%M:%S"))
    dot = "warn" if st["external"] else ("on" if up else "off")
    out.append(_tile("服务", svc_txt, svc_cls, dot))
    out.append(_tile("PID", st["pid"] or "-"))
    out.append(_tile("模型权重", "已就绪" if st["model"] else "未下载",
                     "ok" if st["model"] else "err"))
    out.append(_tile("虚拟环境", "就绪" if st["venv"] else "缺失",
                     "ok" if st["venv"] else "err"))
    out.append(_tile("PyTorch", torch_txt, "ok" if st["torch"] else "err"))
    out.append(_tile("平台", _esc(st.get("platform", "—"))))
    out.append('<div class="tile wide"><div class="k">健康检查</div>'
               '<div class="v %s">%s</div></div>' % (h_cls, _esc(health)))
    out.append('</div><p class="hint">%s</p></div>' % tip)

    out.append('<div class="card"><h2>服务控制</h2><div class="btns">')
    out.append(_button("start", "启动服务", task, "play", pri=not up))
    out.append(_button("stop", "停止服务", task, "stop", danger=up))
    out.append(_button("web", "打开状态页", task, "ext"))
    out.append('</div><p class="hint">首次启动会自动安装依赖并下载模型权重（约 840 MB），'
               '需要几分钟，进度见下方日志。</p></div>')

    out.append('<div class="card"><h2>环境维护</h2><div class="btns">')
    out.append(_button("download", "下载模型权重", task, "down"))
    out.append(_button("gpu", "安装 GPU (CUDA) torch", task, "zap",
                       confirm="安装 GPU 版 torch 会下载数 GB 的 CUDA 运行库，且仅在 NVIDIA 显卡上有用。继续？"))
    out.append(_button("doctor", "环境自检", task, "shield"))
    out.append('</div><p class="hint">GPU 版仅 NVIDIA 显卡需要，会重新下载数 GB 的 CUDA torch；'
               'macOS 不适用。</p></div>')

    out.append("</div>")
    out.append(_lamp(task, up))

    # 任务结束提示：结束后第一轮轮询弹一次 toast（hx-swap-oob 追加进 #toasts）
    if task["state"] in ("ok", "error") and task["done"] and task["done"] != _NOTIFIED["done"]:
        _NOTIFIED["done"] = task["done"]
        cls = "ok" if task["state"] == "ok" else "warn"
        mark, word = ("✓", "完成") if task["state"] == "ok" else ("✗", "失败，请查看日志")
        out.append('<div class="toast %s" hx-swap-oob="beforeend: #toasts">%s %s%s</div>'
                   % (cls, mark, task["name"], word))

    return "".join(out)


def frag_logs():
    _pump_server_log()
    with _LOCK:
        lines = list(_LOG)[-300:]
    return _esc("\n".join(lines)) if lines else "(暂无日志，点上面的操作试试)"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="text/html"):
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
        if p == "/frag/state":
            try:
                self._send(200, frag_state())
            except Exception as exc:
                self._send(500, "state error: %s" % _esc(exc))
        elif p == "/frag/logs":
            self._send(200, frag_logs())
        elif p in STATIC:
            fname, ctype = STATIC[p]
            try:
                self._send(200, (HERE / fname).read_bytes(), ctype)
            except OSError:
                self._send(404, "file missing")
        else:
            self._send(404, "not found")

    def do_POST(self):
        p = self.path.split("?", 1)[0]
        if p == "/api/clear_logs":
            with _LOCK:
                _LOG.clear()
            self._send(200, "(已清空)")
            return
        if p.startswith("/api/action/"):
            key = p.rsplit("/", 1)[-1]
            if key in ROUTES:
                label, fn = ROUTES[key]
                if _bg(label, fn):
                    msg = "已在浏览器打开状态页" if key == "web" else "已开始：" + label
                    self._send(200, '<div class="toast ok">%s</div>' % msg)
                else:
                    self._send(200, '<div class="toast warn">有操作正在进行，请等它结束</div>')
                return
        self._send(404, "not found")


def main():
    url = "http://%s:%d/" % (HOST, PORT)
    try:
        srv = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        # 多半是面板已经开着一个：直接把浏览器带过去，而不是甩一堆堆栈
        print("[panel] 面板已在运行: %s (已尝试打开浏览器)" % url)
        try:
            webbrowser.open(url)
        except Exception:
            pass
        return 0
    threading.Thread(target=srv.serve_forever, daemon=True).start()
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
    return 0


if __name__ == "__main__":
    main()
