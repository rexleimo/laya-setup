#!/usr/bin/env bash
# 一键启动 — 打开图形管理面板 (等价于 ./start.sh gui)
set -e
cd "$(dirname "$0")"
exec bash ./start.sh gui "$@"
