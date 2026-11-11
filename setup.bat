@echo off
REM One-time setup on Windows: creates .venv with Python 3.11 and installs everything.
set PYTHONUTF8=1
py -3.11 -m venv .venv || (echo Python 3.11 not found. Install it from https://www.python.org/downloads/ & exit /b 1)
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pip install -e .
if not exist .env copy .env.example .env
echo.
echo Setup done. Start the website with:  run.bat   (then open http://localhost:8000)
