@echo off
rem Startet Finanzblick auf http://localhost:8765 (Windows).
rem
rem   start.cmd          -> Port 8765 (8000 gehoert der Buchhaltung)
rem   start.cmd 9000     -> anderer Port
rem
rem Der Server hoert bewusst nur auf 127.0.0.1: erreichbar ist er damit
rem ausschliesslich von diesem Rechner, nicht aus dem uebrigen Netzwerk.

cd /d "%~dp0"

set PORT=%1
if "%PORT%"=="" set PORT=8765

where python >nul 2>&1
if errorlevel 1 (
  echo Kein Python gefunden.
  echo Finanzblick braucht keinen Server - die Datei index.html laesst sich
  echo auch per Doppelklick im Browser oeffnen:
  echo   %~dp0index.html
  pause
  exit /b 1
)

echo Finanzblick laeuft auf http://localhost:%PORT%/index.html
echo Beenden mit Strg+C.

start "" "http://localhost:%PORT%/index.html"
python -m http.server %PORT% --bind 127.0.0.1
