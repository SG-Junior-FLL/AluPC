#!/usr/bin/env bash
# AluPC wieder entfernen (Einstellungen in ~/.config/AluPC bleiben erhalten).
set -euo pipefail
rm -rf "${HOME}/.local/share/alupc"
rm -f "${HOME}/.local/bin/alupc" "${HOME}/.local/share/applications/alupc.desktop" \
      "${HOME}"/.local/share/icons/hicolor/*/apps/alupc.png "${HOME}/.local/share/icons/hicolor/scalable/apps/alupc.svg" \
      "${HOME}/.config/autostart/alupc.desktop" "${HOME}/.local/share/applications/alupc-link.desktop" \
      "${HOME}/.local/share/kio/servicemenus/alupc-monitor2.desktop" \
      "${HOME}/.local/share/kservices5/ServiceMenus/alupc-monitor2.desktop"
sed -i '/^x-scheme-handler\/alupc=/d' "${HOME}/.config/mimeapps.list" 2>/dev/null || true
echo "AluPC wurde entfernt. Einstellungen: ~/.config/AluPC (bei Bedarf selbst löschen)."
