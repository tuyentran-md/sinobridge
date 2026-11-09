@echo off
setlocal
cd /d "%~dp0.."
echo SinoBridge - doc va dich tai lieu tren may cua ban.
if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv || goto :no_python
)
if not exist ".venv\.sinobridge-ready" (
    ".venv\Scripts\python.exe" -m pip install -e ".[all]" || goto :fail
    type nul > ".venv\.sinobridge-ready"
)
".venv\Scripts\python.exe" -m sinobridge.webapp --open
exit /b %errorlevel%
:no_python
echo Can cai Python 3.10+ tu python.org truoc.
goto :fail
:fail
echo Khong khoi dong duoc. Kiem tra Python va thu lai.
pause
exit /b 1
