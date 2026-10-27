# DecKoOS for Decky

DecKoOS's panel in Gaming Mode's quick access menu (the `...` button): the running game's profile (power, Do Not
Disturb), sound (output, a slider per kind, the equalizer) and what needs a look (Game Doctor, the self-test).

The work is done by `/usr/lib/deckos/decky/bridge.py` (tested in `tests/test_decky.py`); `main.py` runs it as the
player and `src/index.tsx` draws it with Decky's own components.

Build and copy into deckos-settings (the built plugin is committed there, like the other generated files):

    cd apps/deckos-decky && pnpm install && pnpm build
    cp plugin.json package.json main.py ../../pkg/deckos-settings/rootfs/usr/share/deckos/decky/DecKoOS/
    cp dist/index.js ../../pkg/deckos-settings/rootfs/usr/share/deckos/decky/DecKoOS/dist/

Install on a PC with Decky Loader: `deckos decky plugin`.
