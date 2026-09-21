@echo off
REM One-click Laya - Windows entry point. All logic lives in onekey.py.
REM   start.bat            first run: create venv, install deps, download weights, start API
REM   start.bat server     start the API directly
REM   start.bat gpu        CUDA torch
REM   start.bat stop       stop the service
REM   start.bat status     show status + health
REM   start.bat gui        open the GUI panel
REM   start.bat detach     start in the background
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
  echo [onekey] Could not create the virtual environment.
  echo [onekey] Please install Python 3.9+ or uv ^(https://astral.sh/uv^) first.
  exit /b 1
)

:run
%VPY% onekey.py %*
