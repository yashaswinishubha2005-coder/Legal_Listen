@echo off
REM Starts the LegalListen website on http://localhost:8000 (reads GEMINI_API_KEY etc. from .env if present)
set PYTHONUTF8=1
if exist .env (for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do if not "%%b"=="" set "%%a=%%b")
.venv\Scripts\python -m uvicorn legallisten.app:app --host 127.0.0.1 --port 8000
