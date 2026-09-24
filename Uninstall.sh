#!/usr/bin/env bash
set -u
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec python3 "$HERE/installer.py" uninstall
