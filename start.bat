@echo off
REM 一键启动 (onekey) — Windows 入口。跨平台逻辑都在 onekey.py，这里只负责引导。
REM   start.bat            首次: 建 venv、装依赖、下 english 权重、起 API
REM   start.bat server     直接起 API (http://127.0.0.1:8399)
REM   start.bat gpu        CUDA 版 torch
REM   start.bat mcp        装 MCP 桥接依赖
REM   start.bat stop       停止服务
REM   start.bat status     查看状态 + 健康检查
REM   start.bat gui        图形管理面板
REM   start.bat detach     后台起服务
setlocal
cd /d %~dp0

set VPY=.venv\Scripts\python.exe
if exist %VPY% goto run

echo [onekey] first run: creating virtual environment...
if exist bin\uv.exe (
  bin\uv.exe venv .venv
  goto check
)
where uv >nul 2>nul
if %errorlevel%==0 (
  uv venv .venv
  goto check
)
where py >nul 2>nul
if %errorlevel%==0 (
  py -m venv .venv
  goto check
)
where python >nul 2>nul
if %errorlevel%==0 (
  python -m venv .venv
  goto check
)

:check
if not exist %VPY% (
  echo [onekey] 无法创建虚拟环境。请先安装 Python 3.9+ 或 uv ^(https://astral.sh/uv^)。
  exit /b 1
)

:run
%VPY% onekey.py %*
