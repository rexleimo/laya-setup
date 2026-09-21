@echo off
REM 一键启动 — 打开图形管理面板 (等价于 start.bat gui)
cd /d %~dp0
call start.bat gui %*
