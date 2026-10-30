# Security

DecKoOS runs things as root (the installer, updates, `pkexec` steps) and signs the packages every DecKoOS PC
installs. If you find a way to break any of that, please report it privately through
[GitHub's security advisories](https://github.com/kcooperlawson/deckos/security/advisories/new), not in an issue.

Things that count: running something as root without the password prompt, a way to make the installer touch
a disk or partition other than the one picked, a way to get unsigned packages onto a DecKoOS PC, or a page,
file or game that makes DecKoOS Assistant (the chat box or its workspace) run a command without asking.
