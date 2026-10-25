#!/usr/bin/env bash
# install-test.sh ISO [DIR] - CI's install test. Installs DecKoOS from ISO onto a blank virtual disk
# in QEMU (OVMF, KVM when the machine has it), then boots the installed system and waits for its
# desktop target. Both serial consoles are saved in DIR (default install-test/): install.log, boot.log.
#
# The live USB installs only when booted with deckos.autoinstall, inside a VM, with answers from
# QEMU's fw_cfg and a disk with the serial deckos-autotest (iso/airootfs/usr/local/bin/deckos-autoinstall).
# Needs: qemu-system-x86_64, OVMF, sfdisk, mkfs.fat (dosfstools 4.2+), bsdtar, jq.
set -Eeuo pipefail

ISO=$(readlink -f "${1:?usage: install-test.sh ISO [DIR]}")
W=${2:-install-test}
mkdir -p "$W" && W=$(cd "$W" && pwd)
INSTALL_MIN=${INSTALL_MIN:-100}
BOOT_MIN=${BOOT_MIN:-15}
# Optional software groups to install (comma-separated); none keeps the test quick.
GROUPS_=${DECKOS_TEST_GROUPS:-}
# partition: an EFI partition + an empty one, next to "Windows"; empty: a blank disk DecKoOS gets whole;
# free: an EFI partition + a file system to keep, and free space after them that DecKoOS goes into.
LAYOUT=${DECKOS_TEST_LAYOUT:-partition}

step() { printf '\n\e[1;34m==> %s\e[0m\n' "$*"; }
summary() { [[ -n ${GITHUB_STEP_SUMMARY:-} ]] && printf '%s\n' "$*" >> "$GITHUB_STEP_SUMMARY"; return 0; }
fail() {  # fail MESSAGE LOG - the reason, then the end of that serial console
  echo "::error::$1"
  summary "**Install test failed:** $1" "" '```' "$(tail -n 60 "$2" 2>/dev/null)" '```'
  printf '\n\e[1;31m[FAIL] %s\e[0m\nLast 120 lines of %s:\n' "$1" "$2"
  tail -n 120 "$2" 2>/dev/null | sed 's/^/  | /'
  exit 1
}

# ------------------------------------------------------------------ machine
CODE="" VARS=""
for c in /usr/share/OVMF/OVMF_CODE_4M.fd /usr/share/OVMF/OVMF_CODE.fd \
         /usr/share/edk2/x64/OVMF_CODE.4m.fd /usr/share/edk2-ovmf/x64/OVMF_CODE.fd; do
  v=${c/CODE/VARS}
  if [[ -f $c && -f $v ]]; then CODE=$c VARS=$v; break; fi
done
[[ -n $CODE ]] || { echo "OVMF not found (install ovmf / edk2-ovmf)"; exit 1; }
if [[ -w /dev/kvm ]]; then
  accel=(-accel kvm -cpu host)
else
  # Software emulation works but is many times slower.
  echo "::warning::No KVM here: emulating the CPU, the test will be slow"
  accel=(-accel tcg -cpu max)
  INSTALL_MIN=$((INSTALL_MIN * 4)) BOOT_MIN=$((BOOT_MIN * 4))
fi
cp "$VARS" "$W/vars.fd"  # the installed system's boot entry lands here, for the second boot

# ------------------------------------------------------------------ blank disk
# An EFI partition and an empty partition for DecKoOS: the installer installs onto a partition, next
# to whatever shares the disk, and reuses the EFI partition it finds.
rm -f "$W/disk.img"
if [[ $LAYOUT == empty ]]; then
  # 80 GB (sparse): the installer offers empty disks of 64 GB and up
  step "Blank 80 GB disk, no partitions: DecKoOS gets the whole disk"
  truncate -s 80G "$W/disk.img"
elif [[ $LAYOUT == free ]]; then
  # 100 GB (sparse): 20 GB stands in for another system, the rest is free space (DecKoOS needs 64 GB)
  truncate -s 100G "$W/disk.img"
  step "100 GB disk: EFI partition + a 20 GB file system to keep + free space"
  printf 'label: gpt\nsize=300MiB, type=U, name="EFI system partition"\nsize=20GiB, type=L, name="Keep me"\n' \
    | sfdisk -q "$W/disk.img"
  read -r keep_start keep_sectors < <(sfdisk -J "$W/disk.img" | jq -r '.partitiontable.partitions[1] | "\(.start) \(.size)"')
  mkfs.ext4 -q -L keepme -E offset=$((keep_start * 512)) "$W/disk.img" $((keep_sectors / 2))k
else
  truncate -s 40G "$W/disk.img"
  step "Blank 40 GB disk: EFI partition + empty partition"
  printf 'label: gpt\nsize=300MiB, type=U, name="EFI system partition"\ntype=L, name="DeckOS"\n' \
    | sfdisk -q "$W/disk.img"
fi
if [[ $LAYOUT != empty ]]; then
  read -r esp_start esp_sectors < <(sfdisk -J "$W/disk.img" | jq -r '.partitiontable.partitions[0] | "\(.start) \(.size)"')
  # Cluster size explicitly: mkfs.fat sizes it for the whole 40 GB image, which leaves this partition too
  # few clusters for FAT32. Linux mounts that anyway; UEFI firmware counts clusters and can't read it.
  mkfs.fat -F 32 -S 512 -s 1 -n EFI --offset "$esp_start" "$W/disk.img" $((esp_sectors / 2)) >/dev/null
  sfdisk -l "$W/disk.img"
fi
# What was on the disk before: the install may add to it, never change it (Installer safety, CLAUDE.md)
kept_parts() {  # the EFI partition, and in free space the file system next to it (partition 2 is DecKoOS's otherwise)
  sfdisk -d "$W/disk.img" | grep -E "^\\S+img$([[ $LAYOUT == free ]] && echo '[12]' || echo 1) :" || true
}
kept_fs() { [[ $LAYOUT != free ]] || blkid -p -o value -s UUID -O $((keep_start * 512)) "$W/disk.img"; }
parts_before=$(kept_parts) fs_before=$(kept_fs)

# ------------------------------------------------------------------ live kernel
# Booting the ISO's kernel directly is how the test adds deckos.autoinstall: no boot menu entry has it.
step "Live kernel from $(basename "$ISO")"
mkdir -p "$W/live"
kernel=$(bsdtar -tf "$ISO" | grep -m1 -E '^arch/boot/x86_64/vmlinuz-' || true)
initrd=$(bsdtar -tf "$ISO" | grep -m1 -E '^arch/boot/x86_64/initramfs-.*\.img$' || true)
[[ -n $kernel && -n $initrd ]] || { echo "No kernel/initramfs under arch/boot/x86_64 in $ISO"; exit 1; }
bsdtar -xf "$ISO" -C "$W/live" "$kernel" "$initrd"
uuid=$(blkid -o value -s UUID "$ISO" || true)
label=$(blkid -o value -s LABEL "$ISO" || true)
if [[ -n $uuid ]]; then find_iso="archisosearchuuid=$uuid"; else find_iso="archisolabel=$label"; fi
echo "$kernel, $initrd, $find_iso"

# The answers, read by the live USB as DECKOS_* data (never as code). Test-only password.
cat > "$W/answers" <<EOF
DECKOS_HOSTNAME=deckos-test
DECKOS_USER=tester
DECKOS_PASSWORD=deckos-test
DECKOS_TZ=Etc/UTC
DECKOS_LOCALE=en_US.UTF-8
DECKOS_KEYMAP=us
DECKOS_GROUPS=$GROUPS_
DECKOS_DISPLAY_LEVEL=0
EOF

# vm LOG MINUTES DONE_REGEX [qemu args...] - runs the VM with its serial console in LOG (shown live)
# until it powers off, LOG matches DONE_REGEX, or MINUTES pass. Returns 0, or 124 on timeout.
vm() {
  local log=$1 minutes=$2 done_re=$3; shift 3
  : > "$log"
  qemu-system-x86_64 -machine q35 "${accel[@]}" -smp "$(nproc)" -m 6G \
    -display none -monitor none -no-reboot -serial "file:$log" \
    -drive "if=pflash,format=raw,readonly=on,file=$CODE" -drive "if=pflash,format=raw,file=$W/vars.fd" \
    -drive "file=$W/disk.img,format=raw,if=none,id=disk,cache=unsafe" \
    -device virtio-blk-pci,drive=disk,serial=deckos-autotest \
    -nic user,model=virtio-net-pci "$@" &
  local qemu=$! deadline=$((SECONDS + minutes * 60)) rc=0
  tail -F -n +1 --pid="$qemu" "$log" 2>/dev/null &
  local tailer=$!
  while kill -0 "$qemu" 2>/dev/null; do
    if grep -qaE "$done_re" "$log"; then sleep 5; break; fi
    if (( SECONDS > deadline )); then rc=124; break; fi
    sleep 5
  done
  kill "$qemu" 2>/dev/null || true
  wait "$qemu" 2>/dev/null || true
  kill "$tailer" 2>/dev/null || true
  wait "$tailer" 2>/dev/null || true
  return "$rc"
}

# ------------------------------------------------------------------ install
step "Installing (up to $INSTALL_MIN minutes)"
rc=0
# The live USB powers off after PASS or FAIL (so the disk is complete); stop early only if it refused.
vm "$W/install.log" "$INSTALL_MIN" 'DECKOS-AUTOINSTALL: not starting' \
  -drive "file=$ISO,media=cdrom,readonly=on" \
  -kernel "$W/live/$kernel" -initrd "$W/live/$initrd" \
  -append "archisobasedir=arch $find_iso deckos.autoinstall console=tty0 console=ttyS0,115200" \
  -fw_cfg "name=opt/deckos/autoinstall,file=$W/answers" || rc=$?
result=$(grep -aoE 'DECKOS-AUTOINSTALL: (not starting.*|PASS|FAIL.*)' "$W/install.log" | tail -n1 | tr -d '\r' || true)
case $result in
  *PASS) echo "Install finished: $result"; summary "Install: passed" ;;
  *FAIL*|*"not starting"*) fail "${result#DECKOS-AUTOINSTALL: }" "$W/install.log" ;;
  *) [[ $rc == 124 ]] && fail "The install didn't finish within $INSTALL_MIN minutes" "$W/install.log"
     fail "The live USB stopped before the install reported a result (no DECKOS-AUTOINSTALL line)" "$W/install.log" ;;
esac
[[ $(kept_parts) == "$parts_before" ]] || fail "The install changed a partition it should only have added next to:
$parts_before
is now
$(kept_parts)" "$W/install.log"
[[ $(kept_fs) == "$fs_before" ]] || fail "The install changed the file system it was meant to leave alone" "$W/install.log"
[[ $LAYOUT != free ]] || { echo "Existing partitions untouched: yes"; summary "Existing partitions untouched: yes"; }

# ------------------------------------------------------------------ first boot
step "Booting the installed system (up to $BOOT_MIN minutes)"
rc=0
vm "$W/boot.log" "$BOOT_MIN" 'DECKOS-AUTOTEST: graphical.target reached' || rc=$?
reached=$(grep -aoE 'DECKOS-AUTOTEST: graphical.target reached.*' "$W/boot.log" | tail -n1 | tr -d '\r' || true)
failed_units=$(grep -aoE 'DECKOS-AUTOTEST: failed unit: .*' "$W/boot.log" | sed 's/^DECKOS-AUTOTEST: failed unit: //' | tr -d '\r' || true)
[[ -n $failed_units ]] && { echo "::warning::Failed units on first boot: $(echo "$failed_units" | awk '{print $1}' | tr '\n' ' ')"; printf '%s\n' "$failed_units"; }
if [[ -z $reached ]]; then
  [[ $rc == 124 ]] && fail "The installed system didn't reach graphical.target within $BOOT_MIN minutes" "$W/boot.log"
  fail "The installed system stopped before reaching graphical.target" "$W/boot.log"
fi
[[ $reached == *"sddm active"* ]] || fail "Reached graphical.target but the login screen isn't running (${reached#*, })" "$W/boot.log"
grep -qa 'deckos-test login:' "$W/boot.log" && echo "Serial login prompt: yes"
echo "Installed system: $reached"
summary "First boot: ${reached#DECKOS-AUTOTEST: }"
