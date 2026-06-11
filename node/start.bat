@echo off
cd /d "%~dp0"
for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /v "^#" .env`) do set %%a=%%b
if not defined PORT set PORT=8000
python -m uvicorn main:app --host 0.0.0.0 --port %PORT%
pause
