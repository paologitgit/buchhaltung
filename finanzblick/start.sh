#!/bin/sh
# Startet Finanzblick auf http://localhost:8765 (macOS und Linux).
#
#   ./start.sh          -> Port 8765 (8000 gehoert der Buchhaltung)
#   ./start.sh 9000     -> anderer Port
#
# Der Server hört bewusst nur auf 127.0.0.1: erreichbar ist er damit
# ausschliesslich von diesem Rechner, nicht aus dem übrigen Netzwerk.

set -e
cd "$(dirname "$0")"

PORT="${1:-8765}"
URL="http://localhost:$PORT/index.html"

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "Kein Python gefunden."
  echo "Finanzblick braucht keinen Server – die Datei index.html lässt sich"
  echo "auch direkt im Browser öffnen:"
  echo "  $(pwd)/index.html"
  exit 1
fi

echo "Finanzblick läuft auf $URL"
echo "Beenden mit Strg+C."

# Browser öffnen, sobald der Server steht.
( sleep 1
  if command -v open >/dev/null 2>&1; then open "$URL"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL"
  fi ) >/dev/null 2>&1 &

exec "$PYTHON" -m http.server "$PORT" --bind 127.0.0.1
