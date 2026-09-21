#!/usr/bin/env bash
# 一键启动 (onekey) — Linux / macOS 入口。
# 真正逻辑都在跨平台的 onekey.py 里，这里只负责定位到项目根并调它。
#
#   ./start.sh            首次: 建 venv、装依赖、下 english 权重、起 API
#   ./start.sh server     直接起 API (http://127.0.0.1:8399)
#   ./start.sh gpu        CUDA 版 torch (仅 Linux; macOS 自动用 CPU/MPS)
#   ./start.sh stop       停止服务
#   ./start.sh status     查看状态 + 健康检查
#   ./start.sh gui        图形管理面板
#   ./start.sh detach     后台起服务
set -e
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
exec "$PY" onekey.py "$@"
