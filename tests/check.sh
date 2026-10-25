#!/usr/bin/env bash
# The checks every change has to pass, the same ones CI runs on a pull request. Run them before you push:
#   bash tests/check.sh            all of them
#   bash tests/check.sh lint       shell and Python syntax, shellcheck, data files
#   bash tests/check.sh tests      the unit and offscreen UI tests (needs PySide6)
#   bash tests/check.sh generated  generated files match their generators (needs PySide6 and fonttools)
set -Eeuo pipefail
cd "$(dirname "$0")/.."

failed=0
step() { printf '\n\033[1m// %s\033[0m\n' "$*"; }
fail() { printf '\033[31m✗ %s\033[0m\n' "$*"; failed=1; }
pass() { printf '\033[32m✔\033[0m %s\n' "$*"; }

BASH_SCRIPTS=(
  build.sh installer/deckos-install tests/install-test.sh tests/check.sh .github/publish-repo
  iso/airootfs/usr/local/bin/deckos-autoinstall
  pkg/deckos-settings/rootfs/usr/bin/deckos
  pkg/deckos-settings/rootfs/usr/lib/deckos/session-switch
  pkg/deckos-settings/rootfs/usr/lib/deckos/gaming-session
  pkg/deckos-settings/rootfs/usr/lib/deckos/gaming-service
  pkg/deckos-settings/rootfs/usr/lib/deckos/gaming-cleanup
  pkg/deckos-settings/rootfs/usr/lib/os-session-select
  pkg/deckos-installer/rootfs/usr/bin/deckos-installer
  pkg/deckos-settings/rootfs/usr/share/deckos/shell/snapshot-first.bash
  tests/vm/partition_harness.bash
)
SH_SCRIPTS=(
  pkg/deckos-settings/rootfs/usr/lib/deckos/brand-os-release
  pkg/deckos-settings/rootfs/etc/profile.d/deckos.sh
)

lint() {
  step "Shell"
  local f
  for f in "${BASH_SCRIPTS[@]}" "${SH_SCRIPTS[@]}"; do
    [[ -f $f ]] || { fail "$f is listed in tests/check.sh but doesn't exist"; continue; }
    bash -n "$f" || fail "$f: syntax"
  done
  if command -v shellcheck >/dev/null; then
    shellcheck -S warning -s bash "${BASH_SCRIPTS[@]}" || fail "shellcheck (bash)"
    shellcheck -S warning -s sh "${SH_SCRIPTS[@]}" || fail "shellcheck (sh)"
  else
    printf 'shellcheck isn'"'"'t installed: skipped here (CI runs it)\n'
  fi
  # PKGBUILDs and every other script in the packages at least parse
  while IFS= read -r f; do
    bash -n "$f" 2>/dev/null || fail "$f: syntax"
  done < <(find pkg -name PKGBUILD -o -name '*.install' | sort)
  pass "shell"

  step "Python"
  python3 -m py_compile pkg/deckos-settings/rootfs/usr/lib/deckos/*/*.py \
    pkg/deckos-installer/rootfs/usr/lib/deckos/installer/deckos_installer.py assets/*.py tests/*.py \
    || fail "python syntax"
  pass "python"

  step "Data files"
  python3 - <<'EOF' || fail "data files"
import json, sys, tomllib
from pathlib import Path
bad = 0
for p in Path("pkg").rglob("*.json"):
    try:
        json.loads(p.read_text())
    except ValueError as e:
        print(f"{p}: {e}"); bad += 1
for p in Path("pkg/deckos-settings/rootfs/usr/share/deckos/releases").glob("*.toml"):
    try:
        notes = tomllib.loads(p.read_text())
        assert notes.get("version") == p.stem, "version doesn't match the file name"
        for h in notes.get("highlights", []):
            assert h.get("title") and h.get("text"), "a highlight without a title or text"
    except (ValueError, AssertionError) as e:
        print(f"{p}: {e}"); bad += 1
for p in Path("pkg").rglob("*.theme"):
    if p.parent.name == "themes":  # KSyntaxHighlighting themes are JSON
        try:
            json.loads(p.read_text())
        except ValueError as e:
            print(f"{p}: {e}"); bad += 1
sys.exit(1 if bad else 0)
EOF
  pass "data files"

  step "Things that must never be committed"
  if git ls-files | grep -E '^personal/|\.(key|gpg|asc|pem)$|secret' | grep -v 'pkg/deckos-settings/rootfs/usr/share/pacman/keyrings/'; then
    fail "private files are tracked (personal/, keys): remove them from git"
  fi
  if git grep -nI -E 'BEGIN (PGP|RSA|OPENSSH) PRIVATE KEY' -- ':!tests/check.sh' >/dev/null; then
    fail "a private key is in the tree"
  fi
  pass "no private files"
}

unit_tests() {
  step "Unit and offscreen UI tests"
  # Anything a test records in the DecKoOS timeline goes to a throwaway folder, never the real timelines
  local pulse_dir; pulse_dir=$(mktemp -d)
  export DECKOS_PULSE_USER=$pulse_dir/user.jsonl DECKOS_PULSE_SYSTEM=$pulse_dir/system.jsonl
  QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -p 'test_*.py' || fail "unit tests"
}

generated() {
  step "Generated files match their generators"
  # Re-run the generators whose output is committed; the tree must come out unchanged. The Xcursor files
  # are pixels and differ between Qt versions, so they're left out of the comparison.
  python3 assets/icons.py >/dev/null && python3 assets/themes.py >/dev/null \
    && QT_QPA_PLATFORM=offscreen python3 assets/icon_theme.py >/dev/null \
    && QT_QPA_PLATFORM=offscreen python3 assets/cursors.py >/dev/null || { fail "a generator failed"; return; }
  if ! git diff --quiet -- . ':!pkg/deckos-settings/rootfs/usr/share/icons/DeckOS-cursors/cursors' \
      || [[ -n $(git ls-files --others --exclude-standard -- pkg apps) ]]; then
    git status --short -- pkg apps | head -20
    fail "generated files are out of date: run the generator and commit its output"
    git checkout -q -- pkg/deckos-settings/rootfs/usr/share/icons/DeckOS-cursors/cursors 2>/dev/null || true
  else
    git checkout -q -- pkg/deckos-settings/rootfs/usr/share/icons/DeckOS-cursors/cursors 2>/dev/null || true
    pass "generated files are current"
  fi
}

case ${1:-all} in
  lint) lint ;;
  tests) unit_tests ;;
  generated) generated ;;
  all) lint; unit_tests; generated ;;
  *) echo "usage: bash tests/check.sh [lint|tests|generated|all]" >&2; exit 2 ;;
esac
if ((failed)); then printf '\n\033[31mSome checks failed.\033[0m\n'; exit 1; fi
printf '\n\033[32mAll checks passed.\033[0m\n'
