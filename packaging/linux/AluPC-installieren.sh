#!/bin/bash
# AluPC unter Kubuntu/Ubuntu installieren – auch wenn gerade Updates laufen.
#
# „Sperrung nicht möglich“ heißt: ein anderes Programm (Discover, automatische Updates …) installiert gerade.
# Dieses Skript wartet, bis die Paketverwaltung frei ist, und installiert dann die .deb-Datei, die daneben liegt
# (oder lädt die neueste von GitHub). Start: Rechtsklick → „Als Programm ausführen“ oder im Terminal
#   bash AluPC-installieren.sh
set -u
cd "$(dirname "$0")" || exit 1

deb=$(ls -t alupc_*_amd64.deb 2>/dev/null | head -1)
if [ -z "$deb" ]; then
    echo "Keine alupc_…_amd64.deb neben diesem Skript – lade die neueste von GitHub …"
    url=$(curl -fsSL https://api.github.com/repos/SG-Junior-FLL/AluPC/releases/latest \
          | grep -o '"browser_download_url": *"[^"]*_amd64\.deb"' | head -1 | cut -d'"' -f4)
    if [ -z "$url" ]; then echo "Download nicht gefunden – bitte die .deb von der Release-Seite laden."; exit 1; fi
    deb=$(basename "$url")
    curl -fL -o "$deb" "$url" || { echo "Download fehlgeschlagen."; exit 1; }
fi
echo "Installiere $deb"

# Root-Rechte holen (Passwort einmal)
if [ "$(id -u)" -ne 0 ]; then
    if command -v pkexec >/dev/null && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] && ! [ -t 0 ]; then
        exec pkexec bash "$(realpath "$0")"
    fi
    exec sudo bash "$(realpath "$0")"
fi

busy() {
    fuser /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock /var/lib/apt/lists/lock >/dev/null 2>&1
}
waited=0
while busy; do
    if [ $waited -eq 0 ]; then
        echo "Ein anderes Programm installiert gerade (Discover oder automatische Updates) – warte …"
        ps -o comm= -p "$(fuser /var/lib/dpkg/lock-frontend 2>/dev/null | awk '{print $1}')" 2>/dev/null \
            | sed 's/^/  läuft: /'
    fi
    sleep 5
    waited=$((waited + 5))
    if [ $waited -ge 900 ]; then
        echo "Nach 15 Minuten immer noch gesperrt. Bitte Discover schließen oder den PC neu starten und nochmal versuchen."
        exit 1
    fi
done
# abgebrochene frühere Installation reparieren (sonst bleibt apt hängen)
dpkg --configure -a >/dev/null 2>&1 || true
apt-get -o DPkg::Lock::Timeout=600 install -y "./$deb" && echo && echo "✔ AluPC ist installiert – im Startmenü unter „AluPC“."
status=$?
if ! [ -t 0 ]; then sleep 4; fi
exit $status
