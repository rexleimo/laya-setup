#!/usr/bin/env python3
"""一键启动 图形管理面板 (gui.py)。

用 Python 自带的 tkinter 编写，Windows / Linux / macOS 三端都无需额外
装依赖即可运行。管理 Laya 服务的：启停、健康检查、模型状态、下载权重、
安装 MCP / GPU 依赖，并实时查看服务日志。

启动：  python onekey.py gui      或   python gui.py
"""
import threading
import time
import tkinter as tk
from tkinter import scrolledtext, ttk

import onekey


def run():
    """入口：由 onekey.py gui 调用，也可直接 python gui.py。"""
    try:
        import tkinter  # noqa: F401
    except Exception as exc:  # pragma: no cover
        print("tkinter 不可用: %s" % exc)
        print("Linux 请先安装:  sudo apt install python3-tk   (或 dnf/yum  equivalent)")
        return
    App().mainloop()


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("一键启动 · Laya")
        self.root.geometry("820x560")
        self.root.minsize(680, 520)
        self._build()
        # onekey 的日志通过 emitter 投递到 UI 线程的日志框
        onekey.set_emitter(self._emit)
        self._tail_log()
        self.refresh_full()
        self.root.after(3000, self._tick)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------- UI 构建 ----------------
    def _build(self):
        pad = {"padx": 10, "pady": 6}
        top = ttk.Frame(self.root)
        top.pack(fill="x", **pad)
        ttk.Label(top, text="一键启动 · Laya 本地决策服务",
                  font=("", 15, "bold")).pack(side="left")
        self.url_lbl = ttk.Label(top, text=onekey.web_url(), foreground="#2563eb")
        self.url_lbl.pack(side="right")

        # 状态网格
        st = ttk.LabelFrame(self.root, text="状态")
        st.pack(fill="x", **pad)
        self.vars = {}
        fields = [
            ("platform", "平台"), ("venv", "虚拟环境"), ("torch", "PyTorch"),
            ("model", "模型权重"), ("service", "服务"), ("pid", "PID"),
            ("health", "健康检查"),
        ]
        for i, (key, label) in enumerate(fields):
            ttk.Label(st, text=label + ":", anchor="e", width=10).grid(
                row=i, column=0, sticky="e", padx=(6, 2), pady=2)
            var = tk.StringVar(value="…")
            self.vars[key] = var
            ttk.Label(st, textvariable=var, anchor="w").grid(
                row=i, column=1, sticky="w", padx=(2, 6), pady=2)

        # 按钮行
        btns = ttk.Frame(self.root)
        btns.pack(fill="x", **pad)
        self.btn_start = ttk.Button(btns, text="启动服务", command=lambda: self._spawn(self._do_start))
        self.btn_stop = ttk.Button(btns, text="停止服务", command=lambda: self._spawn(self._do_stop))
        self.btn_refresh = ttk.Button(btns, text="刷新", command=self.refresh_full)
        self.btn_model = ttk.Button(btns, text="下载模型", command=lambda: self._spawn(self._do_download))
        self.btn_mcp = ttk.Button(btns, text="安装 MCP 依赖", command=lambda: self._spawn(self._do_mcp))
        self.btn_gpu = ttk.Button(btns, text="安装 GPU(CUDA)", command=lambda: self._spawn(self._do_gpu))
        self.btn_doctor = ttk.Button(btns, text="环境自检", command=lambda: self._spawn(self._do_doctor))
        self.btn_web = ttk.Button(btns, text="打开状态页", command=onekey.open_web)
        for b in (self.btn_start, self.btn_stop, self.btn_refresh, self.btn_model,
                  self.btn_mcp, self.btn_gpu, self.btn_doctor, self.btn_web):
            b.pack(side="left", padx=4, pady=2)

        # 日志
        lf = ttk.LabelFrame(self.root, text="日志")
        lf.pack(fill="both", expand=True, **pad)
        self.log_box = scrolledtext.ScrolledText(lf, wrap="word", height=12,
                                                  font=("Consolas", 10))
        self.log_box.pack(fill="both", expand=True, padx=4, pady=4)
        self.log_box.configure(state="disabled")

    # ---------------- 日志 ----------------
    def _emit(self, line):
        # 后台线程调用 —— 投递到 UI 线程执行
        self.root.after(0, self._append_log, line)

    def _append_log(self, line):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", "[%s] %s\n" % (time.strftime("%H:%M:%S"), line))
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _tail_log(self):
        try:
            data = onekey.LOG_FILE.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return
        tail = "\n".join(data.splitlines()[-40:])
        if tail:
            self._append_log("---- 历史日志 (尾部) ----\n" + tail)

    # ---------------- 状态 ----------------
    def refresh_quick(self):
        def work():
            st = onekey.collect_status()
            st["health"] = onekey.health()
            self.root.after(0, lambda: self._apply_status(st))
        threading.Thread(target=work, daemon=True).start()

    def refresh_full(self):
        def work():
            st = onekey.collect_status()
            st["health"] = onekey.health()
            st["torch"] = onekey.torch_installed(onekey.venv_python()) if st["venv"] else None
            self.root.after(0, lambda: self._apply_status(st))
        threading.Thread(target=work, daemon=True).start()

    def _apply_status(self, st):
        self.vars["platform"].set(st["platform"])
        self.vars["venv"].set("就绪" if st["venv"] else "缺失")
        self.vars["torch"].set({True: "已安装", False: "未安装", None: "—"}[st["torch"]])
        self.vars["model"].set("已就绪" if st["model"] else "未下载")
        if st.get("external"):
            self.vars["service"].set("运行中(外部)")
        elif st["running"]:
            self.vars["service"].set("运行中")
        else:
            self.vars["service"].set("已停止")
        self.vars["pid"].set(str(st["pid"]) if st["pid"] else "-")
        h = st["health"]
        if h:
            self.vars["health"].set(
                "OK · device=%s · loaded=%s" % (h.get("device"), ",".join(h.get("loaded") or []) or "无"))
        elif st["running"] or st.get("external"):
            self.vars["health"].set("启动中 / 预热 …")
        else:
            self.vars["health"].set("无响应")
        # 按钮可用性
        up = st["running"] or st.get("external")
        self.btn_stop.configure(state="normal" if st["running"] else "disabled")
        self.btn_start.configure(state="disabled" if up else "normal")
        self.btn_web.configure(state="normal" if up else "disabled")

    def _tick(self):
        self.refresh_quick()
        self.root.after(3000, self._tick)

    # ---------------- 动作 (后台线程) ----------------
    def _spawn(self, fn):
        def work():
            try:
                fn()
            except Exception as exc:
                onekey.log("操作失败: %s" % exc)
            finally:
                self.refresh_full()
        threading.Thread(target=work, daemon=True).start()

    def _do_start(self):
        vp = onekey.ensure_venv()
        onekey.install_base(vp)
        onekey.install_torch(vp, "cpu")
        if not onekey.model_ready():
            onekey.log("未发现模型权重，开始下载 …")
            onekey.download_model(vp, "english")
        onekey.start_server(vp, "english", detach=True)

    def _do_stop(self):
        onekey.stop_server()

    def _do_download(self):
        vp = onekey.ensure_venv()
        onekey.download_model(vp, "english")

    def _do_mcp(self):
        vp = onekey.ensure_venv()
        onekey.install_mcp(vp)

    def _do_gpu(self):
        vp = onekey.ensure_venv()
        if onekey.IS_MAC:
            onekey.log("macOS 无 CUDA；默认 torch 已含 CPU/MPS，无需此操作。")
            return
        onekey.log("installing CUDA torch ...")
        onekey.pip_install(vp, ["torch"], index_url=onekey.CUDA_TORCH_INDEX)

    def _do_doctor(self):
        onekey.doctor()

    def _on_close(self):
        onekey.set_emitter(None)
        self.root.destroy()


if __name__ == "__main__":
    run()
