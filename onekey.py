#!/usr/bin/env python3
"""一键启动 (onekey) — Laya 本地决策服务跨平台启动 / 管理入口。

一个文件覆盖 Windows / Linux / macOS：建 venv、装依赖、下模型权重、
启动 / 停止 API 服务、查看状态与健康检查。三个平台的启动器
(start.bat / start.sh) 都很薄，最终都调到这里。

用法 (命令行):
    python onekey.py            首次：建 venv、装依赖、下 english 权重、起 API
    python onekey.py server     直接起 API (跳过环境搭建)
    python onekey.py gpu        装 CUDA 版 torch 再起服务 (仅 Windows/Linux)
    python onekey.py stop       停止正在运行的服务
    python onekey.py status     打印当前状态 + 健康检查
    python onekey.py doctor     环境预检 (Python/uv/venv/磁盘/模型/下载源)
    python onekey.py model      下载模型权重 (--source mirror|official 选下载源)
    python onekey.py panel      打开 Web 管理面板 (浏览器, 最通用; gui 为别名)
    python onekey.py web        用默认浏览器打开状态页
    python onekey.py detach     后台方式起服务 (不占用当前终端)
"""
import argparse
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE_DIR = HERE / ".onekey"
PID_FILE = STATE_DIR / "server.pid"
LOG_FILE = STATE_DIR / "server.log"

IS_WINDOWS = os.name == "nt"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8399
CPU_TORCH_INDEX = "https://download.pytorch.org/whl/cpu"
CUDA_TORCH_INDEX = "https://download.pytorch.org/whl/cu121"

# 模型下载源：HuggingFace 官方 + 国内镜像 + ModelScope (引导用户按网络选择)。
HF_MIRROR = "https://hf-mirror.com"
HF_OFFICIAL = "https://huggingface.co"
HF_REPO = "convaiinnovations/laya"
MODELSCOPE_URL = "https://www.modelscope.cn/models/convaiinnovations/laya"

# 日志发射器：命令行下打印到 stdout；GUI 下由 gui.py 注入，转发到日志框。
_EMIT = None


def set_emitter(fn):
    global _EMIT
    _EMIT = fn


def log(msg):
    line = "[onekey] " + str(msg)
    if _EMIT is not None:
        _EMIT(line)
    else:
        print(line, flush=True)


# --------------------------------------------------------------------------
# 平台 / 路径
# --------------------------------------------------------------------------
def plat_name():
    if IS_WINDOWS:
        return "Windows"
    if IS_MAC:
        return "macOS"
    if IS_LINUX:
        return "Linux"
    return platform.system() or "unknown"


def venv_dir():
    return HERE / ".venv"


def venv_python():
    """虚拟环境里的 python 可执行文件 (跨平台路径)。"""
    if IS_WINDOWS:
        return venv_dir() / "Scripts" / "python.exe"
    return venv_dir() / "bin" / "python"


def find_uv():
    """优先随包发布的 bin/uv.exe (Windows)，否则系统 PATH 里的 uv。"""
    local = HERE / "bin" / ("uv.exe" if IS_WINDOWS else "uv")
    if local.exists():
        return str(local)
    return shutil.which("uv")


def run(cmd, **kw):
    """跑一条命令，返回退出码。

    命令行模式：输出直接透传到终端。
    面板模式 (注入了 emitter)：捕获子进程输出并逐行转发进面板日志，
    否则装依赖 / 下模型的进度全写进了后台终端，浏览器里只能干等。
    非终端环境下 pip / uv / huggingface_hub 本来就输出纯文本行，
    再关掉各自的进度条即可保证日志干净。
    """
    log("$ " + " ".join(str(c) for c in cmd))
    if _EMIT is not None and not kw.pop("passthrough", False):
        return _run_captured(cmd, **kw)
    try:
        return subprocess.call([str(c) for c in cmd], **kw)
    except FileNotFoundError as exc:
        log("command not found: %s (%s)" % (cmd[0], exc))
        return 127


def _run_captured(cmd, **kw):
    env = dict(os.environ)
    env.setdefault("PIP_PROGRESS_BAR", "off")
    env.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    kw.setdefault("cwd", str(HERE))
    try:
        proc = subprocess.Popen(
            [str(c) for c in cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=env, **kw,
        )
    except FileNotFoundError as exc:
        log("command not found: %s (%s)" % (cmd[0], exc))
        return 127
    assert proc.stdout is not None
    while True:
        raw = proc.stdout.readline()
        if not raw:
            break
        line = raw.decode("utf-8", "replace").rstrip()
        if line:
            log("  | " + line[:400])
    return proc.wait()


# --------------------------------------------------------------------------
# venv / 依赖
# --------------------------------------------------------------------------
def ensure_venv():
    """确保 .venv 存在，返回 venv 的 python 路径。"""
    vp = venv_python()
    if vp.exists():
        return vp
    log("creating virtual environment in %s ..." % venv_dir())
    STATE_DIR.mkdir(exist_ok=True)
    uv = find_uv()
    if uv:
        rc = run([uv, "venv", str(venv_dir())])
    else:
        # 没有 uv 就用当前解释器自建 (Unix 一般自带 python3 -m venv)
        rc = run([sys.executable, "-m", "venv", str(venv_dir())])
    if rc != 0 or not vp.exists():
        raise RuntimeError("failed to create venv (rc=%s)" % rc)
    log("venv ready: %s" % vp)
    return vp


def pip_install(vp, packages, index_url=None):
    """装包：有 uv 用 uv，否则回退 venv 自带的 pip。"""
    uv = find_uv()
    if uv:
        cmd = [uv, "pip", "install", "--python", str(vp)]
        if index_url:
            cmd += ["--index-url", index_url]
        cmd += list(packages)
        return run(cmd)
    cmd = [str(vp), "-m", "pip", "install"]
    if index_url:
        cmd += ["--index-url", index_url]
    cmd += list(packages)
    return run(cmd)


def torch_installed(vp):
    return subprocess.call(
        [str(vp), "-c", "import torch"], cwd=str(HERE),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ) == 0


def torch_index(mode):
    """根据平台 / 模式决定 torch 安装源。macOS 用默认源 (CPU/MPS 轮子)。"""
    if IS_MAC:
        return None  # macOS 无 CUDA；默认源即含 CPU/MPS 版本
    if mode == "gpu":
        return CUDA_TORCH_INDEX
    return CPU_TORCH_INDEX


def install_base(vp):
    log("installing base dependencies (requirements.txt) ...")
    rc = pip_install(vp, ["-r", str(HERE / "requirements.txt")])
    if rc != 0:
        raise RuntimeError("failed to install base dependencies (rc=%s)" % rc)


def install_torch(vp, mode):
    if torch_installed(vp):
        log("torch already installed.")
        return
    idx = torch_index(mode)
    if idx:
        log("installing torch from %s ..." % idx)
        rc = pip_install(vp, ["torch"], index_url=idx)
    else:
        log("installing torch (default index; macOS CPU/MPS) ...")
        rc = pip_install(vp, ["torch"])
    if rc != 0:
        raise RuntimeError("failed to install torch (rc=%s)" % rc)


# --------------------------------------------------------------------------
# 模型权重
# --------------------------------------------------------------------------
def model_ready():
    return (HERE / "models" / "laya" / "model.safetensors").exists()


def _warn_if_low_disk(need_gb=3):
    """下载 ~840MB 模型前检查磁盘，空间不足先警告，避免下到一半失败。"""
    try:
        free_gb = shutil.disk_usage(HERE).free / 1e9
        if free_gb < need_gb:
            log("! 磁盘仅剩 %.1f GB，下载模型建议预留 >= %d GB，可能空间不足。" % (free_gb, need_gb))
        else:
            log("disk: %.1f GB free (ok for ~840 MB model)." % free_gb)
    except Exception:
        pass


def current_endpoint():
    """当前生效的下载源 (HF_ENDPOINT)，未设置则默认国内镜像。"""
    return os.environ.get("HF_ENDPOINT") or HF_MIRROR


def pick_source(source):
    """按用户选择设置下载源并返回 endpoint。
    source: 'mirror'(国内镜像) | 'official'(HF 官方) | None(用当前/默认)。"""
    mapping = {"mirror": HF_MIRROR, "official": HF_OFFICIAL}
    endpoint = mapping.get(source) or current_endpoint()
    os.environ["HF_ENDPOINT"] = endpoint
    return endpoint


def download_guide():
    """不自动探测区域，直接引导用户去对应的下载源。"""
    log("准备下载模型权重 (~840 MB)。请按你的网络环境选择下载源：")
    log("  国内用户 (推荐，速度快): 镜像源 %s" % HF_MIRROR)
    log("      切换: Windows `set HF_ENDPOINT=%s`  /  Linux/macOS `export HF_ENDPOINT=%s`"
        % (HF_MIRROR, HF_MIRROR))
    log("      或运行: onekey.py model --source mirror")
    log("  海外用户 (官方源): %s" % HF_OFFICIAL)
    log("      切换: export HF_ENDPOINT=%s  或  onekey.py model --source official" % HF_OFFICIAL)
    log("  也可手动下载后放入 models/laya/ :")
    log("      国内镜像  : %s/%s" % (HF_MIRROR, HF_REPO))
    log("      官方      : %s/%s" % (HF_OFFICIAL, HF_REPO))
    log("      ModelScope: %s" % MODELSCOPE_URL)
    log("  本次使用: %s" % current_endpoint())


def download_model(vp, variant="english", source=None, guide=True):
    if guide:
        download_guide()
        _warn_if_low_disk()
    endpoint = pick_source(source)
    log("downloading %s from %s (~840 MB) ..." % (variant, endpoint))
    rc = run([str(vp), str(HERE / "download_model.py"), "--variant", variant], cwd=str(HERE))
    if rc != 0:
        log("下载失败。可换源重试，或手动下载后放入 models/laya/ :")
        log("  国内镜像  : %s/%s" % (HF_MIRROR, HF_REPO))
        log("  官方      : %s/%s" % (HF_OFFICIAL, HF_REPO))
        log("  ModelScope: %s" % MODELSCOPE_URL)
        log("  手动放好后再运行: onekey.py server")
        raise RuntimeError("model download failed (rc=%s)" % rc)


# --------------------------------------------------------------------------
# 服务进程管理 (PID 文件)
# --------------------------------------------------------------------------
def read_pid():
    try:
        return int(PID_FILE.read_text().strip())
    except Exception:
        return None


def clear_pid():
    try:
        PID_FILE.unlink()
    except FileNotFoundError:
        pass


def write_pid(pid):
    STATE_DIR.mkdir(exist_ok=True)
    PID_FILE.write_text(str(pid))


STILL_ACTIVE = 259  # Windows GetExitCodeProcess: 进程仍在运行的退出码


def pid_alive(pid):
    """跨平台判断进程是否存活。

    Windows 上 os.kill(pid, 0) 不可靠 (对存在的进程也抛 WinError 87)，
    故用 OpenProcess + GetExitCodeProcess；Unix 用 os.kill(pid, 0)。
    """
    if not pid:
        return False
    if IS_WINDOWS:
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not handle:
                return False
            try:
                code = ctypes.c_ulong()
                if kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                    return code.value == STILL_ACTIVE
                return True
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # 存在但不属于当前用户
    except OSError:
        return False
    return True


def is_running():
    pid = read_pid()
    if pid and pid_alive(pid):
        return pid
    return None


def start_server(vp, preload="english", detach=False):
    pid = is_running()
    if pid:
        log("service already running (pid %d) at http://%s:%d" % (pid, DEFAULT_HOST, DEFAULT_PORT))
        return pid
    if health() is not None:
        log("a service is already responding on %s (not started by onekey); "
            "not starting a second one." % web_url())
        return None
    if not model_ready():
        log("!! no model weights found; run  onekey.py  (default) to download first.")
        return None
    STATE_DIR.mkdir(exist_ok=True)
    cmd = [str(vp), str(HERE / "server.py"), "--preload", preload]
    log("starting API: " + " ".join(cmd))
    if detach:
        logf = open(LOG_FILE, "a", encoding="utf-8")
        kwargs = dict(stdout=logf, stderr=subprocess.STDOUT, cwd=str(HERE))
        if IS_WINDOWS:
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        proc = subprocess.Popen(cmd, **kwargs)
        write_pid(proc.pid)
        log("started in background (pid %d). log: %s" % (proc.pid, LOG_FILE))
        return proc.pid
    # 前台：透传输出，Ctrl+C 时优雅停止并清理 PID 文件
    proc = subprocess.Popen(cmd, cwd=str(HERE))
    write_pid(proc.pid)
    log("running in foreground (pid %d). Ctrl+C to stop." % proc.pid)
    try:
        return proc.wait()
    except KeyboardInterrupt:
        log("stopping ...")
        try:
            proc.terminate()
        except Exception:
            pass
        return 0
    finally:
        clear_pid()


def stop_server():
    pid = is_running()
    if not pid:
        clear_pid()
        log("service is not running.")
        return True
    if IS_WINDOWS:
        run(["taskkill", "/PID", str(pid), "/T", "/F"])
    else:
        try:
            os.kill(pid, signal.SIGTERM)
            # 等最多 5 秒优雅退出，否则强杀
            for _ in range(50):
                if not pid_alive(pid):
                    break
                time.sleep(0.1)
            if pid_alive(pid):
                os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    clear_pid()
    log("stopped (pid %d)." % pid)
    return True


def health(timeout=3):
    """GET /health，成功返回 dict，失败返回 None。"""
    url = "http://%s:%d/health" % (DEFAULT_HOST, DEFAULT_PORT)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def web_url():
    return "http://%s:%d/" % (DEFAULT_HOST, DEFAULT_PORT)


def open_web():
    url = web_url()
    log("opening %s" % url)
    try:
        webbrowser.open(url)
    except Exception as exc:
        log("could not open browser: %s" % exc)


# --------------------------------------------------------------------------
# 环境预检 (doctor)：帮用户确认并引导把环境装好
# --------------------------------------------------------------------------
def doctor():
    v = sys.version_info
    log("环境预检 (doctor) - %s / Python %d.%d.%d" % (plat_name(), v[0], v[1], v[2]))
    ok = True

    if v < (3, 9):
        log("  x Python %d.%d 过低，建议 >= 3.9  (%s)" % (v[0], v[1], sys.executable)); ok = False
    else:
        log("  + Python %d.%d.%d  (%s)" % (v[0], v[1], v[2], sys.executable))

    uv = find_uv()
    if uv:
        log("  + uv: %s" % uv)
    else:
        log("  - uv: 未找到；将回退 python -m venv / pip (可选装 uv 加速: https://astral.sh/uv)")

    vp = venv_python()
    if vp.exists():
        log("  + 虚拟环境: 就绪 %s" % vp)
    else:
        log("  - 虚拟环境: 未创建 (首次运行自动创建)")

    try:
        free_gb = shutil.disk_usage(HERE).free / 1e9
        if free_gb >= 3:
            log("  + 磁盘: %.1f GB 可用 (足够下载 ~840MB 模型)" % free_gb)
        else:
            log("  x 磁盘: 仅 %.1f GB，下载模型至少需 ~3 GB" % free_gb); ok = False
    except Exception:
        pass

    if model_ready():
        log("  + 模型权重: 已就绪 (models/laya/)")
    else:
        log("  - 模型权重: 未下载 (首次运行自动下载，或 onekey.py model)")

    log("  - 下载源: HF_ENDPOINT=%s" % (os.environ.get("HF_ENDPOINT") or "(未设置 -> 默认国内镜像 %s)" % HF_MIRROR))
    log("预检%s。可随时运行 onekey.py 开始一键启动。" % ("通过" if ok else "发现问题，请按上面 x 项处理"))
    return ok


# --------------------------------------------------------------------------
# 状态汇总 (命令行 status + GUI 刷新共用)
# --------------------------------------------------------------------------
def collect_status(health_result=None):
    """汇总当前状态。health_result 可传入已查好的 /health 结果，
    避免面板轮询时把 3s 超时的健康检查跑两遍。"""
    pid = is_running()
    h = health_result if health_result is not None else health()
    running = bool(pid)
    external = (not running) and (h is not None)  # 有服务在跑但非 onekey 启动
    return {
        "platform": plat_name(),
        "python": venv_python().name,
        "venv": venv_python().exists(),
        "torch": None,  # 由调用方按需填充 (检查较慢)
        "model": model_ready(),
        "running": running,
        "external": external,
        "pid": pid,
        "port": DEFAULT_PORT,
        "url": web_url(),
        "health": h,
    }


def print_status():
    st = collect_status()
    log("platform : %s" % st["platform"])
    log("venv     : %s" % ("ready" if st["venv"] else "missing"))
    log("model    : %s" % ("present" if st["model"] else "missing"))
    if st["external"]:
        log("service  : running (external — not started by onekey, so onekey can't stop it)")
    elif st["running"]:
        log("service  : running (pid %s)" % st["pid"])
    else:
        log("service  : stopped")
    if st["health"]:
        h = st["health"]
        log("health   : OK  device=%s  loaded=%s  available=%s"
            % (h.get("device"), h.get("loaded"), h.get("available")))
    else:
        log("health   : no response on %s" % st["url"])


# --------------------------------------------------------------------------
# 编排
# --------------------------------------------------------------------------
def full_setup(mode):
    """首次完整流程：venv -> 依赖 -> torch -> 模型 -> 起服务。"""
    if mode == "gpu" and IS_MAC:
        log("note: macOS has no CUDA; using default torch (CPU/MPS).")
        mode = "cpu"
    vp = ensure_venv()
    install_base(vp)
    install_torch(vp, mode)
    if not model_ready():
        _warn_if_low_disk()
        download_model(vp, "english")
    else:
        log("english checkpoint present.")
    start_server(vp, "english", detach=False)
    return 0


def build_parser():
    ap = argparse.ArgumentParser(prog="onekey", description="一键启动 — Laya 跨平台启动/管理入口")
    ap.add_argument("command", nargs="?", default="run",
                    choices=["run", "server", "gpu", "stop", "status",
                             "gui", "web", "detach", "doctor", "model", "panel"],
                    help="run=完整流程(默认) server=直接起 gpu=CUDA "
                         "stop=停止 status=状态 panel=Web管理面板 (gui 为别名) "
                         "web=打开状态页 detach=后台起服务 doctor=环境预检 model=下载模型")
    ap.add_argument("--source", choices=["mirror", "official"], default=None,
                    help="配合 model 命令选择下载源: mirror=国内镜像(默认) official=HuggingFace 官方")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    cmd = args.command

    if cmd in ("panel", "gui"):  # gui 为旧命令名，统一走 Web 面板
        import panel  # 同目录
        panel.main()
        return 0
    if cmd == "web":
        open_web()
        return 0
    if cmd == "stop":
        stop_server()
        return 0
    if cmd == "status":
        print_status()
        return 0
    if cmd == "doctor":
        doctor()
        return 0
    if cmd == "model":
        vp = ensure_venv()
        download_model(vp, "english", source=args.source)
        return 0

    if cmd == "detach":
        vp = ensure_venv()
        if not model_ready():
            log("!! no model weights; run  onekey.py  first to download.")
            return 2
        start_server(vp, "english", detach=True)
        return 0

    if cmd == "server":
        vp = venv_python()
        if not vp.exists():
            log("venv missing; run  onekey.py  (default) for first-time setup.")
            return 2
        if not model_ready():
            log("!! no model weights; run  onekey.py  first to download.")
            return 2
        start_server(vp, "english", detach=False)
        return 0

    if cmd == "gpu":
        return full_setup("gpu")

    # default: run
    return full_setup("cpu")


if __name__ == "__main__":
    sys.exit(main())
