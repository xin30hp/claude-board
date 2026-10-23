#!/bin/sh
# Runs one of the plugin's scripts (scripts/<name>.py) with whichever Python works (python3 on macOS/Linux; on
# Windows python3 is often the Microsoft Store stub, which fails, so fall back to python).
script="$(dirname "$0")/../scripts/$1.py"
if python3 -c "" >/dev/null 2>&1; then
  exec python3 "$script"
fi
exec python "$script"
