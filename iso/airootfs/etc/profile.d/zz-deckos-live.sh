# Start the DeckOS installer automatically on the first console, once per boot.
# Cancel it any time to get a normal root shell; run deckos-install to start again.
if [ "$(tty)" = /dev/tty1 ] && [ ! -e /run/deckos-autostarted ]; then
  touch /run/deckos-autostarted
  deckos-install
fi
