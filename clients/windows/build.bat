@echo off
rem Builds dist\TailnetChat.exe (one-file, no console window).
cd /d "%~dp0"

python -m pip install -r requirements.txt pyinstaller || exit /b 1

python -m PyInstaller --noconfirm --clean --onefile --windowed --name TailnetChat ^
  --add-data "..\..\node;node" ^
  --hidden-import uvicorn.loops.asyncio ^
  --hidden-import uvicorn.protocols.http.h11_impl ^
  --hidden-import uvicorn.lifespan.on ^
  app.py || exit /b 1

if not exist ..\..\dist mkdir ..\..\dist
copy /y dist\TailnetChat.exe ..\..\dist\TailnetChat.exe >nul
echo.
echo Built: dist\TailnetChat.exe (also copied to repo dist\)
