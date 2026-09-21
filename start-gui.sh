#!/usr/bin/env bash
# 一键启动 — 打开 Web 管理面板 (等价于 ./start.sh panel)
set -e
cd "$(dirname "$0")"
exec bash ./start.sh panel "$@"
