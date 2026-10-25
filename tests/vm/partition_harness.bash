# Runs the installer's list_free and make_partition (functions.bash: extracted from installer/deckos-install
# by partition_steps.py) as root, with the installer's messages stubbed. One case per call:
#   bash partition_harness.bash list | make FREE
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
  make)
    FREE=$2 ESP="" TARGET=""
    make_partition
    echo "TARGET=$TARGET ESP=$ESP PARTNO=$TARGET_PARTNO" ;;
esac
