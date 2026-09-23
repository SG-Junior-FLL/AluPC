#!/usr/bin/env bash
# AluPC wieder entfernen (Einstellungen in ~/.config/AluPC bleiben erhalten).
set -euo pipefail
rm -rf "${HOME}/.local/share/alupc"
rm -f "${HOME}/.local/bin/alupc" "${HOME}/.local/share/applications/alupc.desktop" \
      "${HOME}/.local/share/icons/hicolor/256x256/apps/alupc.png" "${HOME}/.config/autostart/alupc.desktop"
echo "AluPC wurde entfernt. Einstellungen: ~/.config/AluPC (bei Bedarf selbst löschen)."
