# DecKoOS login environment.

# Composite on the 9070 XT only. Guarded, so a different GPU can't leave you at a black screen.
if [ -e /dev/dri/deckos-dgpu ]; then
  export KWIN_DRM_DEVICES=/dev/dri/deckos-dgpu
fi

# Claude Code, uv and pip --user install into ~/.local/bin.
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) [ -d "$HOME/.local/bin" ] && PATH="$HOME/.local/bin:$PATH" ;;
esac
export PATH
