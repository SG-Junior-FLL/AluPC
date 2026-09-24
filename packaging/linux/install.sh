#!/usr/bin/env bash
# AluPC unter Kubuntu installieren (für den aktuellen Benutzer, ohne root – nur apt braucht sudo).
set -euo pipefail

cd "$(dirname "$0")/../.."
SRC="$(pwd)"
PREFIX="${HOME}/.local/share/alupc"
BIN="${HOME}/.local/bin"
APPS="${HOME}/.local/share/applications"

echo "==> Systempakete installieren (sudo-Passwort nötig)"
sudo apt-get update
# python3-venv: eigene Python-Umgebung · fprintd/libpam-fprintd: Fingerabdruck
# wmctrl: Fensterliste unter X11 · libxcb-cursor0: wird von Qt unter X11 gebraucht
# kscreen: stellt kscreen-doctor bereit (bei Kubuntu normalerweise schon da)
sudo apt-get install -y python3-venv python3-pip fprintd libpam-fprintd wmctrl libxcb-cursor0 \
    pipewire xdg-desktop-portal-kde || true
command -v kscreen-doctor >/dev/null || sudo apt-get install -y kscreen || true

echo "==> Python-Umgebung in ${PREFIX}"
python3 -m venv "${PREFIX}/venv"
"${PREFIX}/venv/bin/pip" install --upgrade pip
"${PREFIX}/venv/bin/pip" install "${SRC}"

echo "==> Startbefehl, Menüeintrag und Symbol"
mkdir -p "${BIN}" "${APPS}"
ln -sf "${PREFIX}/venv/bin/alupc" "${BIN}/alupc"
"${PREFIX}/venv/bin/python" -m alupc.platform.linux_desktop "${HOME}/.local/share" "${BIN}/alupc"
update-desktop-database "${APPS}" 2>/dev/null || true
command -v kbuildsycoca6 >/dev/null && kbuildsycoca6 >/dev/null 2>&1 || true

echo
echo "Fertig! AluPC steht jetzt im Startmenü."
echo "Auf der Kommandozeile: ${BIN}/alupc   (evtl. neu anmelden, damit ~/.local/bin im PATH ist)"
