# DeckOS "Snapshot first": before a command that deletes a lot, bash offers a snapshot to undo it with.
# Sourced from /etc/bash.bashrc (deckos-settings adds the line) in interactive shells, so it works in
# DeckOS Terminal, Konsole or any other terminal. It asks before:
#   - rm -r of your home folder, a folder right inside it (~/Documents, ~/.config) or a whole git
#     repository: a /home snapshot, undone with `deckos restore N` (no restart);
#   - sudo rm -r of system files: a / snapshot, undone with `sudo deckos undo N` and a restart.
# pacman needs nothing: snap-pac snapshots every transaction already (deckos undo).
# Off for one user: `deckos snapshot-first off` (~/.config/deckos/shell.conf), or DECKOS_SNAPSHOT_FIRST=0.

[[ $- == *i* && -z ${__deckos_sf_loaded:-} ]] || return 0
__deckos_sf_loaded=1

# __deckos_sf_kind LINE: "home" or "root" when LINE deletes something worth a snapshot, else nothing.
__deckos_sf_kind() {
  local line=$1 seg words i w prog sudo recursive kind="" target t
  local -a parts
  # One check per simple command: a; b && c || d | e
  IFS=$'\n' read -r -d '' -a parts < <(sed -E 's/(\|\||&&|;|\|)/\n/g' <<<"$line"; printf '\0') || true
  for seg in "${parts[@]}"; do
    read -ra words <<<"$seg" || continue
    i=0 sudo=0
    while [[ ${words[i]:-} == *=* && ${words[i]} != -* ]]; do i=$((i + 1)); done  # FOO=1 rm ...
    if [[ ${words[i]:-} == sudo ]]; then
      sudo=1; i=$((i + 1))
      while [[ ${words[i]:-} == -* ]]; do
        case ${words[i]} in -[ugpCDhrtU]) i=$((i + 1)) ;; esac  # options that take a value: sudo -u alice rm
        i=$((i + 1))
      done
    fi
    prog=${words[i]:-}; prog=${prog##*/}
    [[ $prog == rm ]] || continue
    recursive=0
    for w in "${words[@]:i+1}"; do
      [[ $w == --recursive || ( $w == -[!-]* && $w == *[rR]* ) ]] && recursive=1
    done
    (( recursive )) || continue
    for target in "${words[@]:i+1}"; do
      [[ $target == -* ]] && continue
      target=${target%/}
      t=${target/#\~/$HOME}; t=${t/#\$HOME/$HOME}; t=${t/#\$\{HOME\}/$HOME}
      t=${t//\"/}; t=${t//\'/}
      [[ $t == /* ]] || t=$PWD/$t
      # under /home: big targets only, so rm -rf build/ in a project doesn't ask every time
      if [[ $t == "$HOME" || $t == /home || ( $t == "$HOME"/* && ${t#"$HOME"/} != */* ) || -d $t/.git ]]; then
        kind=home
      elif [[ $t == /home/* ]]; then
        # someone's home folder or a folder right inside it
        (( sudo )) && [[ ${t#/home/} != */*/* ]] && kind=home
      elif (( sudo )) && [[ $t != /tmp/* && $t != /run/* && $t != /mnt/* && $t != /media/* && $t != /run/media/* ]]; then
        [[ $kind == home ]] || kind=root
      fi
    done
  done
  [[ -n $kind ]] && echo "$kind"
  return 0
}

__deckos_sf_enabled() {
  [[ ${DECKOS_SNAPSHOT_FIRST:-1} != 0 ]] || return 1
  ! grep -qs '^SNAPSHOT_FIRST=0' "${XDG_CONFIG_HOME:-$HOME/.config}/deckos/shell.conf"
}

__deckos_sf_debug() {
  [[ -n ${__deckos_sf_ready:-} ]] || return 0
  __deckos_sf_ready=
  local line kind config answer n
  line=$(HISTTIMEFORMAT='' builtin history 1 2>/dev/null)
  line=${line#"${line%%[![:space:]]*}"}; line=${line#*[0-9] }; line=${line#"${line%%[![:space:]]*}"}
  [[ -n $line ]] || line=$BASH_COMMAND  # a line starting with a space isn't in history
  kind=$(__deckos_sf_kind "$line")
  [[ -n $kind ]] && __deckos_sf_enabled || return 0
  config=$kind; [[ $kind == home ]] || config=root
  [[ -f /etc/snapper/configs/$config ]] || return 0
  printf '\e[38;2;76;141;255mDeckOS:\e[0m take a snapshot first, so you can undo this? [Y]es / [n]o, just run it / [c]ancel ' >/dev/tty
  read -r -n1 answer </dev/tty; printf '\n' >/dev/tty
  case $answer in
    c|C) printf 'Cancelled.\n' >/dev/tty; kill -INT $$; return 0 ;;
    n|N) return 0 ;;
  esac
  if n=$(snapper -c "$config" create --type pre --cleanup-algorithm number --print-number \
           --description "$line" --userdata deckos=snapshot-first 2>/dev/null); then
    __deckos_sf_pending="$config $n" __deckos_sf_line=$line
  else
    printf "DeckOS: couldn't take a snapshot (snapper -c %s). Run it anyway? [y/N] " "$config" >/dev/tty
    read -r -n1 answer </dev/tty; printf '\n' >/dev/tty
    [[ $answer == [yY] ]] || { kill -INT $$; return 0; }
  fi
  return 0
}

__deckos_sf_prompt() {
  if [[ -n ${__deckos_sf_pending:-} ]]; then
    local config=${__deckos_sf_pending% *} n=${__deckos_sf_pending#* }
    __deckos_sf_pending=
    snapper -c "$config" create --type post --pre-number "$n" --cleanup-algorithm number \
      --description "$__deckos_sf_line" --userdata deckos=snapshot-first >/dev/null 2>&1 || true
    # DeckOS Terminal shows an Undo bar for this (other terminals ignore an OSC they don't know, but
    # only DeckOS Terminal gets it anyway)
    [[ ${TERM_PROGRAM:-} != deckos-terminal ]] || printf '\e]7766;deckos-snapshot=%s:%s\a' "$config" "$n"
    if [[ $config == home ]]; then
      printf '\e[38;2;76;141;255mDeckOS:\e[0m snapshot #%s is from before that. Undo it: deckos restore %s\n' "$n" "$n"
    else
      printf '\e[38;2;76;141;255mDeckOS:\e[0m snapshot #%s is from before that. Undo it: sudo deckos undo %s (then restart)\n' "$n" "$n"
    fi
  fi
  __deckos_sf_ready=1
}

# Someone else's DEBUG trap (bash-preexec, a prompt tool) wins: don't fight over it.
if [[ -z $(trap -p DEBUG) ]]; then
  trap '__deckos_sf_debug' DEBUG
  PROMPT_COMMAND+=('__deckos_sf_prompt')
fi
