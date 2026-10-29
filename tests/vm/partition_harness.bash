# Runs the installer's disk functions (functions.bash: extracted from installer/deckos-install, see
# partition_steps.py and erase_steps.py) as root, with the installer's messages stubbed. One case per call:
#   bash partition_harness.bash list | erase-list | contents DISK | make SPEC [yes|no]
set -Eeuo pipefail
LOG=/tmp/deckos-parttest.log
CHANGED=nothing
style() { :; }
section() { echo "== $*"; }
good() { echo "OK $*"; }
note() { echo "-- $*"; }
die() { echo "DIE $*"; exit 1; }
changed_note() { echo "[changed: $CHANGED]"; }
spin() { local t=$1; shift; "$@" >>"$LOG" 2>&1 || die "$t failed"; good "$t"; }
# shellcheck source=/dev/null
. /tmp/functions.bash

case $1 in
  list) list_free ;;
  erase-list) list_erase ;;
  contents) disk_contents "$2" ;;
  make)
    # A whole disk (empty or erased) gets its own EFI partition unless told no, as the installer does without one
    make_space "$2" "${3:-yes}"
    echo "TARGET=$MADE_PART ESP=$MADE_ESP PARTNO=$MADE_PARTNO" ;;
esac
