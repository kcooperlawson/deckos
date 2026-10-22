#!/usr/bin/env bash
# Builds the DeckOS live/installer ISO from Arch's official "releng" profile plus DeckOS bits.
# Needs Arch Linux (real, WSL "archlinux", or the GitHub Actions container). Output: out/deckos-*.iso
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
OUT=${OUT:-$ROOT/out}
WORK=${WORK:-/var/tmp/deckos-build}

if [[ $EUID -ne 0 ]]; then exec sudo --preserve-env=OUT,WORK "$0" "$@"; fi
pacman -Q archiso >/dev/null 2>&1 || pacman -Sy --noconfirm --needed archiso

rm -rf "$WORK"
mkdir -p "$WORK" "$OUT"
P=$WORK/profile
cp -r /usr/share/archiso/configs/releng "$P"

# Identity and boot menu titles.
sed -i -e 's/^iso_name=.*/iso_name="deckos"/' \
       -e 's/^iso_label="ARCH_/iso_label="DECKOS_/' \
       -e 's|^iso_publisher=.*|iso_publisher="Decko clan"|' \
       -e 's|^iso_application=.*|iso_application="DeckOS live / installer"|' "$P/profiledef.sh"
grep -rlZ 'Arch Linux' "$P/grub" "$P/syslinux" "$P/efiboot" 2>/dev/null \
  | xargs -0 -r sed -i 's/Arch Linux install medium/DeckOS installer/g; s/Arch Linux/DeckOS/g'

# Extra live packages for the installer.
grep -vE '^\s*(#|$)' "$ROOT/iso/packages.extra" >> "$P/packages.x86_64"
sort -u -o "$P/packages.x86_64" "$P/packages.x86_64"

# Live environment files + the installer and everything it installs.
cp -a "$ROOT/iso/airootfs/." "$P/airootfs/"
install -Dm755 "$ROOT/installer/deckos-install" "$P/airootfs/usr/local/bin/deckos-install"
mkdir -p "$P/airootfs/opt/deckos"
cp -a "$ROOT/installer" "$ROOT/pkg" "$P/airootfs/opt/deckos/"
find "$P/airootfs/opt/deckos" -name __pycache__ -type d -prune -exec rm -rf {} +
sed -i '/^file_permissions=(/a\  ["/usr/local/bin/deckos-install"]="0:0:755"' "$P/profiledef.sh"

mkarchiso -v -r -w "$WORK/work" -o "$OUT" "$P"

[[ -n ${SUDO_USER:-} ]] && chown -R "$SUDO_USER:" "$OUT"
ls -lh "$OUT"/*.iso
