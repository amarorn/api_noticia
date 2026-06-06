#!/usr/bin/env bash
# Corrige import dos CLIs (sync-gcp, daily-sync, etc.) no macOS + Python 3.13.
# Arquivos .pth em site-packages ganham UF_HIDDEN (iCloud/Documents) e o site.py os ignora.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ACTIVATE="${ROOT}/.venv/bin/activate"
if [[ ! -f "$ACTIVATE" ]]; then
  echo "venv não encontrado em ${ROOT}/.venv — rode: python -m venv .venv && pip install -e \".[dev]\""
  exit 1
fi
MARKER="# api-noticia: PYTHONPATH para editable install (macOS)"
if grep -qF "$MARKER" "$ACTIVATE"; then
  echo "venv já corrigido — rode: source .venv/bin/activate && sync-gcp --help"
  exit 0
fi
TMP="$(mktemp)"
awk -v marker="$MARKER" -v root="$ROOT" '
BEGIN { done_deact = 0; done_act = 0 }
{
  if (!done_deact && $0 ~ /^    unset VIRTUAL_ENV$/) {
    print "    if [ -n \"${_OLD_VIRTUAL_PYTHONPATH+x}\" ] ; then"
    print "        PYTHONPATH=\"${_OLD_VIRTUAL_PYTHONPATH:-}\""
    print "        if [ -z \"${_OLD_VIRTUAL_PYTHONPATH:-}\" ] ; then"
    print "            unset PYTHONPATH"
    print "        else"
    print "            export PYTHONPATH"
    print "        fi"
    print "        unset _OLD_VIRTUAL_PYTHONPATH"
    print "    fi"
    print ""
    done_deact = 1
  }
  print
}
END {
  if (!done_deact) exit 1
  print ""
  print marker
  print "_API_NOTICIA_ROOT=\"" root "\""
  print "_OLD_VIRTUAL_PYTHONPATH=\"${PYTHONPATH:-}\""
  print "PYTHONPATH=\"${_API_NOTICIA_ROOT}${PYTHONPATH:+:}${PYTHONPATH:-}\""
  print "export PYTHONPATH"
}
' "$ACTIVATE" > "$TMP"
mv "$TMP" "$ACTIVATE"
echo "venv corrigido — rode: source .venv/bin/activate && sync-gcp --help"
