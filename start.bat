@echo off
REM Startet das Telegram Panel unter Windows.
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo   Python wurde nicht gefunden.
  echo   Hol es dir auf https://www.python.org/downloads/
  echo   Beim Installieren "Add Python to PATH" ankreuzen, dann neu versuchen.
  echo.
  pause
  exit /b 1
)

if not exist ".venv" (
  echo   Richte die Umgebung ein, das dauert einmalig ein bis zwei Minuten...
  python -m venv .venv
  if errorlevel 1 goto fehler
)

call ".venv\Scripts\activate.bat"

REM Neu installieren, wenn Pakete fehlen ODER sich die Liste seit dem letzten
REM Mal geaendert hat - sonst faehrt ein Update mit alten Paketen los.
set NEUINSTALL=0
python -c "import fastapi, telethon" >nul 2>nul
if errorlevel 1 set NEUINSTALL=1
fc /b requirements.txt ".venv\.requirements-stand" >nul 2>nul
if errorlevel 1 set NEUINSTALL=1

if "%NEUINSTALL%"=="1" (
  echo   Lade die benoetigten Pakete...
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet -r requirements.txt
  if errorlevel 1 goto fehler
  copy /y requirements.txt ".venv\.requirements-stand" >nul
)

if not exist ".env" copy ".env.example" ".env" >nul

echo.
echo   Panel startet. Zum Beenden dieses Fenster schliessen oder Strg+C.
echo.
python run.py
goto ende

:fehler
echo.
echo   Das hat nicht geklappt. Schick die Meldung oben weiter.
echo.
pause
exit /b 1

:ende
pause
