# DecKoOS Builder

DecKoOS Builder comes with DecKoOS (`deckos-builder`, in the app menu); its code is in
`pkg/deckos-settings/rootfs/usr/lib/deckos/builder/`. This folder has the launchers for running it straight
from a checkout, on DecKoOS or Windows.

Everyone signs in with their own GitHub account (Sign in with GitHub runs `gh auth login --web`), and Builder
shows what that account can do on the repo:

- **The maintainer** (admin or maintain on the repo): release (to testing), promote (to stable), start ISO
  builds on GitHub, and review pull requests in **Contributions** (Approve and merge once the checks pass).
- **Everyone else**: watch builds and contributions, download ISOs, build an ISO on their PC, copy it to a Ventoy
  USB, and **Contribute**: Builder forks DecKoOS to their account, they change things on a branch, run the
  checks, and open a pull request for the maintainer to review.

GitHub enforces the same rules: the buttons only follow them.

- **Windows:** double-click `DecKoOS Builder.bat`. The first run sets up its own Python environment in `.venv`.
- **DecKoOS, from a checkout:** run `./deckos-builder`, or add it to the app menu with `./deckos-builder --install`.
