@echo off
for /f "usebackq tokens=1,2 delims==" %%a in (`findstr /v "^#" .env`) do set %%a=%%b
python agent.py
pause
