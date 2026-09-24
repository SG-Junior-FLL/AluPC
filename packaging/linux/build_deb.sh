#!/usr/bin/env bash
# Baut aus dem PyInstaller-Ordner dist/AluPC ein .deb-Paket für Kubuntu/Ubuntu.
# Aufruf: packaging/linux/build_deb.sh <version>
set -euo pipefail
VERSION="${1:?Version fehlt}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PKG="$ROOT/build/deb/alupc_${VERSION}_amd64"
rm -rf "$PKG"
mkdir -p "$PKG/DEBIAN" "$PKG/opt" "$PKG/usr/bin" "$PKG/usr/share" "$PKG/etc/apparmor.d"

cp -a "$ROOT/dist/AluPC" "$PKG/opt/alupc"
ln -s /opt/alupc/AluPC "$PKG/usr/bin/alupc"
# Menüeintrag (Exec mit vollem Pfad – nötig für die KWin-Aufnahme ohne Nachfrage) und Symbole in allen Größen
PYTHONPATH="$ROOT" python3 -m alupc.platform.linux_desktop "$PKG/usr/share" /opt/alupc/AluPC
chmod -R u+rwX,go+rX "$PKG/usr/share"
install -m 644 "$ROOT/packaging/linux/apparmor-alupc" "$PKG/etc/apparmor.d/alupc"

SIZE=$(du -sk "$PKG" | cut -f1)
cat > "$PKG/DEBIAN/control" <<CTRL
Package: alupc
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: amd64
Installed-Size: ${SIZE}
Maintainer: AluPC <alupc@users.noreply.github.com>
Depends: libc6 (>= 2.35), libegl1, libgl1, libxkbcommon0, libxkbcommon-x11-0, libfontconfig1, libdbus-1-3, libnss3, libxcb-cursor0, libxcomposite1, libxdamage1, libxrandr2, libxtst6, libxkbfile1, libpulse0, libasound2t64 | libasound2
Recommends: fprintd, libpam-fprintd, wmctrl, pipewire, xdg-desktop-portal
Description: AluPC – zweiten Monitor steuern
 Spiegeln, Erweitern, Kamera, Programme, Websites, eigene Szenen, Standbild,
 Sichtschutz, Bild-in-Bild, Bildschirmschoner und Anmelden per Fingerabdruck.
CTRL

cat > "$PKG/DEBIAN/conffiles" <<'CONF'
/etc/apparmor.d/alupc
CONF

# AppArmor-Profil laden: Ubuntu 24.04 erlaubt Chromium (Websites) sonst keine Sandbox
cat > "$PKG/DEBIAN/postinst" <<'POST'
#!/bin/sh
set -e
if [ -x /sbin/apparmor_parser ] && [ -d /sys/kernel/security/apparmor ]; then
    apparmor_parser -r -W /etc/apparmor.d/alupc || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then update-desktop-database -q || true; fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then gtk-update-icon-cache -q /usr/share/icons/hicolor || true; fi
exit 0
POST
cat > "$PKG/DEBIAN/postrm" <<'POSTRM'
#!/bin/sh
set -e
if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    if [ -x /sbin/apparmor_parser ] && [ -d /sys/kernel/security/apparmor ]; then
        apparmor_parser -R /etc/apparmor.d/alupc 2>/dev/null || true
    fi
    # leere Ordner, die zur Laufzeit entstanden sind, mit entfernen
    rm -rf /opt/alupc
fi
exit 0
POSTRM
chmod 755 "$PKG/DEBIAN/postinst" "$PKG/DEBIAN/postrm"

dpkg-deb --root-owner-group --build "$PKG" "$ROOT/dist/alupc_${VERSION}_amd64.deb"
echo "Fertig: dist/alupc_${VERSION}_amd64.deb"
