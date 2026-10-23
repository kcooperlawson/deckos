#!/usr/bin/env bash
# Builds the DeckOS live USB: a KDE Plasma live desktop with the DeckOS installer, on top of
# Arch's official "releng" profile and the CachyOS kernel.
#
# Needs Arch Linux: a real install, WSL "archlinux", or the archlinux Docker image used by CI.
# Output: out/deckos-VERSION-x86_64.iso (VERSION is the file at the top of the repo)
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
VERSION=$(tr -d '[:space:]' < "$ROOT/VERSION")
OUT=${OUT:-$ROOT/out}
WORK=${WORK:-/var/tmp/deckos-build}
# Display blackout fix level 1 on the live USB only, so it never blacks out mid-install. The
# installer picks the level for the installed system from the GPU and monitors it finds.
LIVE_KERNEL_PARAMS="amdgpu.dcdebugmask=0x20000"

if [[ $EUID -ne 0 ]]; then exec sudo --preserve-env=OUT,WORK "$0" "$@"; fi
step() { printf '\n\e[1;34m==> %s\e[0m\n' "$*"; }
nocomments() { grep -vE '^\s*(#|$)' "$1"; }
# AUR apps shipped prebuilt in the on-USB [deckos] repo; the installer installs these copies.
mapfile -t AUR_PKGS < <(nocomments "$ROOT/pkg/deckos-settings/rootfs/usr/share/deckos/packages/aur.txt" | awk '{print $1}')

# ------------------------------------------------------------------ build host
step "Build host: archiso + CachyOS repo"
pacman-key --init >/dev/null 2>&1 || true
pacman-key --populate archlinux >/dev/null 2>&1 || true
if ! grep -q '^\[cachyos\]' /etc/pacman.conf; then
  pacman-key --recv-keys F3B607488DB35A47 --keyserver keyserver.ubuntu.com
  pacman-key --lsign-key F3B607488DB35A47
  grep -q '^\[multilib\]' /etc/pacman.conf || printf '\n[multilib]\nInclude = /etc/pacman.d/mirrorlist\n' >> /etc/pacman.conf
  printf '\n[cachyos]\nServer = https://mirror.cachyos.org/repo/$arch/$repo\n' >> /etc/pacman.conf
fi
pacman -Syu --noconfirm --needed archiso git base-devel librsvg grub papirus-icon-theme cachyos-keyring

id builder >/dev/null 2>&1 || useradd -m builder
echo 'builder ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/90-deckos-builder
chmod 440 /etc/sudoers.d/90-deckos-builder

rm -rf "$WORK"
REPO=$WORK/repo
BUILD=$WORK/build
mkdir -p "$REPO" "$BUILD" "$OUT"
cp -r "$ROOT/pkg" "$ROOT/VERSION" "$BUILD/"
chown -R builder: "$BUILD" "$REPO"
as_builder() { sudo -u builder -H env PKGDEST="$REPO" "$@"; }

# ------------------------------------------------------------------ packages
step "DeckOS packages"
for p in deckos-settings deckos-theme-tmpikes deckos-installer; do
  as_builder bash -c "cd '$BUILD/pkg/$p' && makepkg --nodeps --noconfirm --clean --force"
done

step "AUR apps for the on-USB repo"
for p in "${AUR_PKGS[@]}"; do
  as_builder git clone --depth 1 "https://aur.archlinux.org/$p.git" "$BUILD/aur/$p"
  as_builder bash -c "cd '$BUILD/aur/$p' && makepkg --syncdeps --noconfirm --clean --force"
done
repo-add -q "$REPO/deckos.db.tar.gz" "$REPO"/*.pkg.tar.zst
ls -lh "$REPO"

# ------------------------------------------------------------------ profile
step "Profile (releng + DeckOS)"
P=$WORK/profile
cp -r /usr/share/archiso/configs/releng "$P"

sed -i -e 's/^iso_name=.*/iso_name="deckos"/' \
       -e 's/^iso_label="ARCH_/iso_label="DECKOS_/' \
       -e 's|^iso_publisher=.*|iso_publisher="DeckOS"|' \
       -e 's|^iso_application=.*|iso_application="DeckOS live desktop and installer"|' \
       -e "s|^iso_version=.*|iso_version=\"$VERSION\"|" "$P/profiledef.sh"
sed -i '/^file_permissions=(/a\
  ["/etc/gshadow"]="0:0:400"\
  ["/etc/sudoers.d"]="0:0:750"\
  ["/etc/sudoers.d/00-live"]="0:0:440"\
  ["/home/liveuser/Desktop/deckos-install.desktop"]="1000:1000:755"\
  ["/home/liveuser/Desktop/deckos-hub.desktop"]="1000:1000:755"\
  ["/usr/local/bin/deckos-install"]="0:0:755"' "$P/profiledef.sh"

# Boot menus: DeckOS titles, the CachyOS kernel, the Samsung fix from the first boot.
boot_cfgs=("$P/efiboot" "$P/grub" "$P/syslinux")
rm -f "$P"/efiboot/loader/entries/*speech*
grep -rlZ 'Arch Linux' "${boot_cfgs[@]}" | xargs -0 -r sed -i 's/Arch Linux install medium/DeckOS live/g; s/Arch Linux/DeckOS/g'
grep -rlZ 'vmlinuz-linux\|initramfs-linux' "${boot_cfgs[@]}" \
  | xargs -0 -r sed -i 's/vmlinuz-linux\b/vmlinuz-linux-cachyos/g; s/initramfs-linux\.img/initramfs-linux-cachyos.img/g'
grep -rlZ 'archisobasedir=' "${boot_cfgs[@]}" | xargs -0 -r sed -i "/archisobasedir=/ s/[[:space:]]*\$/ $LIVE_KERNEL_PARAMS/"

# Packages: releng minus the rescue/server bits, plus the DeckOS desktop.
grep -vxF -f <(nocomments "$ROOT/iso/packages.drop") "$P/packages.x86_64" > "$P/packages.tmp" || true
nocomments "$ROOT/iso/packages.live" >> "$P/packages.tmp"
sort -u "$P/packages.tmp" > "$P/packages.x86_64"
rm "$P/packages.tmp"

cat >> "$P/pacman.conf" <<EOF

[multilib]
Include = /etc/pacman.d/mirrorlist

[cachyos]
Server = https://mirror.cachyos.org/repo/\$arch/\$repo

[deckos]
SigLevel = Optional TrustAll
Server = file://$REPO
EOF

# ------------------------------------------------------------------ live system files
step "Live session"
A=$P/airootfs
S=$A/etc/systemd/system
# releng services DeckOS doesn't want (NetworkManager replaces networkd/iwd; no sshd, VM tools).
rm -f "$S"/multi-user.target.wants/{iwd,systemd-networkd,sshd,choose-mirror,hv_fcopy_daemon,hv_kvp_daemon,hv_vss_daemon,vboxservice,vmtoolsd,vmware-vmblock-fuse,livecd-talk}.service \
      "$S"/sockets.target.wants/systemd-networkd.socket \
      "$S"/network-online.target.wants/systemd-networkd-wait-online.service \
      "$S"/sound.target.wants/livecd-alsa-unmuter.service \
      "$S"/livecd-talk.service "$S"/livecd-alsa-unmuter.service \
      "$S"/dbus-org.freedesktop.network1.service \
      "$A"/etc/mkinitcpio.d/linux.preset "$A"/root/.zlogin
rm -rf "$S"/cloud-init.target.wants "$S"/getty@tty1.service.d "$S"/systemd-networkd-wait-online.service.d \
       "$A"/etc/systemd/network "$A"/etc/systemd/networkd.conf.d

cp -a "$ROOT/iso/airootfs/." "$A/"

mkdir -p "$S/multi-user.target.wants" "$S/bluetooth.target.wants"
ln -sf /usr/lib/systemd/system/graphical.target "$S/default.target"
ln -sf /usr/lib/systemd/system/sddm.service "$S/display-manager.service"
ln -sf /usr/lib/systemd/system/NetworkManager.service "$S/multi-user.target.wants/NetworkManager.service"
ln -sf /usr/lib/systemd/system/NetworkManager-dispatcher.service "$S/dbus-org.freedesktop.nm-dispatcher.service"
ln -sf /usr/lib/systemd/system/bluetooth.service "$S/bluetooth.target.wants/bluetooth.service"
ln -sf /usr/lib/systemd/system/bluetooth.service "$S/dbus-org.bluez.service"
ln -sf /usr/lib/systemd/system/power-profiles-daemon.service "$S/multi-user.target.wants/power-profiles-daemon.service"
# DNS through systemd-resolved (NetworkManager feeds it); without this file nothing resolves.
ln -sf /run/systemd/resolve/stub-resolv.conf "$A/etc/resolv.conf"

# On-USB repo (installer Software page) + the text installer as a backup.
mkdir -p "$A/opt/deckos"
cp -a "$REPO" "$A/opt/deckos/repo"
cp -a "$ROOT/installer" "$ROOT/pkg" "$A/opt/deckos/"
install -Dm755 "$ROOT/installer/deckos-install" "$A/usr/local/bin/deckos-install"
find "$A/opt/deckos" -name __pycache__ -type d -prune -exec rm -rf {} +

# ------------------------------------------------------------------ build
step "mkarchiso"
mkarchiso -v -r -w "$WORK/work" -o "$OUT" "$P"

[[ -n ${SUDO_USER:-} ]] && chown -R "$SUDO_USER:" "$OUT"
ls -lh "$OUT"/*.iso
