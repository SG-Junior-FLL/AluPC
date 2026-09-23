#!/usr/bin/env bash
# AluPC unter Kubuntu installieren (für den aktuellen Benutzer, ohne root – nur apt braucht sudo).
set -euo pipefail

cd "$(dirname "$0")/../.."
SRC="$(pwd)"
PREFIX="${HOME}/.local/share/alupc"
BIN="${HOME}/.local/bin"
APPS="${HOME}/.local/share/applications"
ICONS="${HOME}/.local/share/icons/hicolor/256x256/apps"

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
mkdir -p "${BIN}" "${APPS}" "${ICONS}"
ln -sf "${PREFIX}/venv/bin/alupc" "${BIN}/alupc"
install -m 644 "${SRC}/packaging/linux/alupc.desktop" "${APPS}/alupc.desktop"
sed -i "s|^Exec=alupc|Exec=${BIN}/alupc|" "${APPS}/alupc.desktop"
install -m 644 "${SRC}/alupc/resources/alupc.png" "${ICONS}/alupc.png"
update-desktop-database "${APPS}" 2>/dev/null || true

echo
echo "Fertig! AluPC steht jetzt im Startmenü."
echo "Auf der Kommandozeile: ${BIN}/alupc   (evtl. neu anmelden, damit ~/.local/bin im PATH ist)"
