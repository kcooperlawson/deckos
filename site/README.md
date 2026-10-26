# The DecKoOS website

A static site generated from this repo. The README's features and known limitations, the release notes What's New
shows, `docs/`, `SECURITY.md` and the newest ISO all come from the repo as it is, so the site never drifts from
it. No framework, no database, and nothing loaded from other sites (fonts included).

| File | What it is |
|---|---|
| `build.py` | Builds the site into `site/public/` (git-ignored) |
| `serve.py` | Serves it from this PC: resumable ISO downloads, security headers, no visitor addresses logged |
| `style.css`, `site.js` | The look (the DecKoOS design language) and the few things that need a script |
| `deckos-site.service` | A user service that serves the site at login |
| `Caddyfile` | The same site on a real server, with HTTPS |

`tests/test_site.py` builds the site and checks every internal link and anchor, that nothing loads from another
site, and that the server stays inside the site folder.

## Build it

```bash
python3 site/build.py
```

It offers the newest release ISO in `out/` (`deckos-X.Y.Z-x86_64.iso`, not dated test builds). Pick another with
`--iso FILE`, or `--no-iso` for none: the download page then explains how to build one. The ISO is linked, not
copied, and its SHA256 is worked out once and kept next to it.

To publish a signature with the ISO, sign it where the DecKoOS key is (`personal/`, never on a server) and put
the `.sig` beside the ISO before building:

```bash
gpg --local-user F67E15FABF95D2DA72BE5D3F6322881773088C41 --detach-sign --output out/deckos-X.Y.Z-x86_64.iso.sig out/deckos-X.Y.Z-x86_64.iso
```

Pass `--url https://your.domain` once the site has an address: it adds canonical links, a sitemap and link
previews.

## Serve it from this PC

```bash
python3 site/serve.py
```

Then open http://localhost:8080. To keep it running, as a user service that starts at login:

```bash
cp site/deckos-site.service ~/.config/systemd/user/ && systemctl --user enable --now deckos-site
```

It listens on this PC only. To share it with the home network, set `DECKOS_SITE_HOST=0.0.0.0` in the service
(`systemctl --user edit deckos-site`) and allow port 8080 in the firewall. Rebuilding updates the site straight
away; the service doesn't need a restart.

## Put it on the internet from this PC

Don't forward a port on the router to this PC. Use a tunnel instead, which keeps your home address private and
leaves nothing open:

- **Cloudflare Tunnel** (free, needs a domain on Cloudflare): `cloudflared tunnel --url http://localhost:8080`
  for a quick test address, or a named tunnel for your own domain.
- **Tailscale Funnel** (free): `tailscale funnel 8080`.

Either way, the 4 GB ISO is served from your home connection: every download uses your upload bandwidth. When
downloads grow, move the ISO first (below) and keep the pages here.

## Move it to a server

The site is plain files, so any web server works:

1. Copy it, following the ISO link: `rsync -aL --delete site/public/ server:/srv/deckos-site/`
2. On the server, install Caddy, put `site/Caddyfile` in `/etc/caddy/Caddyfile` with your domain, and reload.
   Caddy gets the HTTPS certificate by itself.
3. Point the domain's DNS at the server.

The ISO can also live somewhere built for big files (a GitHub release, object storage with a CDN) while the pages
stay put: upload the ISO and its `.sha256` and `.sig`, and change the download link in `build.py`.
