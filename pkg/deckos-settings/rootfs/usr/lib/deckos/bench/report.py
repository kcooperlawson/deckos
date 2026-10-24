"""DeckOS Bench reports: one self-contained HTML page per run, and one per comparison.

No scripts or downloads: charts are inline SVG, so a report opens anywhere, offline, and can be
attached to a bug report or a forum post as one file.
"""
import html
import time

ACCENT, VIOLET = "#4C8DFF", "#8A5CFF"
SENSOR_NAMES = {"cpu_busy": ("CPU load", "%"), "cpu_mhz": ("CPU clock", "MHz"), "cpu_temp": ("CPU temperature", "°C"),
                "gpu_busy": ("GPU load", "%"), "gpu_mhz": ("GPU clock", "MHz"), "vram_mhz": ("VRAM clock", "MHz"),
                "gpu_temp": ("GPU temperature", "°C"), "gpu_watts": ("GPU power", "W"),
                "vram_gb": ("Graphics memory used", "GB"), "ram_gb": ("RAM used", "GB")}
ENV_NAMES = {"cpu": "CPU", "cores": "Threads", "gpu": "Graphics", "ram_gb": "RAM (GB)", "kernel": "Kernel",
             "mesa": "Mesa", "deckos": "DeckOS", "scheduler": "CPU scheduler", "power_profile": "Power profile",
             "governor": "CPU governor", "display_fix": "Display fix", "gpu_power_cap_w": "GPU power limit (W)"}
GROUP_NAMES = {"cpu": "CPU", "memory": "Memory", "disk": "Disk", "gpu": "Graphics", "ai": "Local AI", "game": "Games"}

CSS = f"""
:root {{ color-scheme: dark; --bg:#0F1115; --surface:#171A21; --raised:#1D212A; --border:#262B36;
  --text:#E8EAF0; --sub:#8C94A6; --muted:#5A6172; --good:#3DD68C; --bad:#FF6B6B; --warn:#F5B84B; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.5 Inter, "Noto Sans", system-ui, sans-serif; }}
main {{ max-width: 1080px; margin: 0 auto; padding: 32px 16px 64px; }}
h1 {{ font-size: 26px; margin: 0 0 4px; letter-spacing: -0.01em; }}
h2 {{ font-size: 17px; margin: 32px 0 10px; }}
h3 {{ font-size: 14px; margin: 0 0 8px; }}
.sub {{ color: var(--sub); }} .muted {{ color: var(--muted); font-size: 12px; }}
.card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 16px; margin: 12px 0; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; }}
.tile {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 14px 16px; }}
.tile .big {{ font-size: 24px; font-weight: 600; font-variant-numeric: tabular-nums; }}
.kicker {{ font-size: 11px; font-weight: 600; letter-spacing: .06em; color: var(--sub); text-transform: uppercase; }}
table {{ width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }}
th, td {{ text-align: left; padding: 7px 8px; border-bottom: 1px solid var(--border); vertical-align: middle; }}
th {{ color: var(--sub); font-weight: 500; font-size: 12px; }}
td.num, th.num {{ text-align: right; }}
.pill {{ display: inline-block; padding: 1px 8px; border-radius: 99px; font-size: 12px; font-weight: 600; }}
.better {{ background: rgba(61,214,140,.15); color: var(--good); }}
.worse {{ background: rgba(255,107,107,.15); color: var(--bad); }}
.same {{ background: var(--raised); color: var(--sub); }}
.unsure {{ background: rgba(245,184,75,.12); color: var(--warn); }}
.error {{ color: var(--bad); }}
.brand {{ display: flex; align-items: center; gap: 10px; margin-bottom: 18px; color: var(--sub); font-weight: 600; }}
.tilelogo {{ width: 28px; height: 28px; border-radius: 8px; background: linear-gradient(135deg, {ACCENT}, {VIOLET}); }}
svg text {{ fill: var(--sub); font: 11px Inter, system-ui, sans-serif; }}
.wrap {{ overflow-x: auto; }}
"""


def esc(x):
    return html.escape(str(x))


def fmt(v, unit=""):
    if v is None:
        return "–"
    v = float(v)
    s = f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.1f}" if abs(v) >= 10 else f"{v:,.2f}"
    return f"{s} {unit}".strip()


def page(title, body):
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' "
            f"content='width=device-width, initial-scale=1'><title>{esc(title)}</title><style>{CSS}</style></head>"
            f"<body><main><div class='brand'><div class='tilelogo'></div>DeckOS Bench</div>{body}</main></body></html>")


def spark(values, w=300, h=56, color=ACCENT):
    """A small line chart with its min and max labelled."""
    v = [x for x in values if x is not None]
    if len(v) < 2:
        return ""
    lo, hi = min(v), max(v)
    span = (hi - lo) or 1
    pts = " ".join(f"{i * (w - 4) / (len(v) - 1) + 2:.1f},{h - 14 - (x - lo) / span * (h - 22):.1f}" for i, x in enumerate(v))
    return (f"<svg width='100%' viewBox='0 0 {w} {h}' preserveAspectRatio='none' role='img'>"
            f"<polyline points='{pts}' fill='none' stroke='{color}' stroke-width='1.6' vector-effect='non-scaling-stroke'/>"
            f"<text x='2' y='{h - 2}'>{fmt(lo)}</text><text x='{w - 2}' y='{h - 2}' text-anchor='end'>max {fmt(hi)}</text></svg>")


def range_bar(stats, w=160, h=14):
    """Each run as a dot, the 95% range of the mean as a band: how repeatable a result is, at a glance."""
    if not stats or stats.get("n", 0) < 2:
        return ""
    lo, hi = stats["min"], stats["max"]
    pad = (hi - lo) * 0.25 or abs(stats["mean"]) * 0.02 or 1
    lo, hi = lo - pad, hi + pad

    def x(v):
        return 4 + (v - lo) / (hi - lo) * (w - 8)
    band = (f"<rect x='{x(stats['ci_low']):.1f}' y='3' width='{max(2, x(stats['ci_high']) - x(stats['ci_low'])):.1f}' "
            f"height='{h - 6}' rx='3' fill='{ACCENT}' opacity='.25'/>")
    mean = f"<line x1='{x(stats['mean']):.1f}' x2='{x(stats['mean']):.1f}' y1='1' y2='{h - 1}' stroke='{ACCENT}' stroke-width='2'/>"
    return f"<svg width='{w}' height='{h}' role='img' aria-label='spread of the runs'>{band}{mean}</svg>"


def run_dots(values, stats, w=160, h=14):
    if not values or len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    pad = (hi - lo) * 0.25 or abs(stats["mean"]) * 0.02 or 1
    lo, hi = lo - pad, hi + pad
    return "".join(f"<circle cx='{4 + (v - lo) / (hi - lo) * (w - 8):.1f}' cy='{h / 2}' r='2.6' fill='#E8EAF0'/>" for v in values)


def metric_rows(result):
    from bench_core import describe
    rows = []
    for m in result["metrics"].values():
        st = describe(m["values"])
        spread = range_bar(st)
        if spread:
            spread = spread.replace("</svg>", run_dots(m["values"], st) + "</svg>")
        rng = f"{fmt(st['ci_low'])} – {fmt(st['ci_high'])}" if st["n"] > 1 else "one run"
        cv = f"{st['cv']:.1f}%" if st["n"] > 1 else "–"
        arrow = "higher is better" if m["higher_better"] else "lower is better"
        rows.append(f"<tr><td>{esc(m['name'])}<div class='muted'>{arrow}</div></td>"
                    f"<td class='num'><b>{fmt(st['mean'], m['unit'])}</b></td><td class='num sub'>{rng}</td>"
                    f"<td class='num sub'>{cv}</td><td>{spread}</td></tr>")
    return ("<div class='wrap'><table><tr><th>Measure</th><th class='num'>Average</th><th class='num'>95% range</th>"
            "<th class='num'>Run-to-run</th><th>Runs</th></tr>" + "".join(rows) + "</table></div>")


def sensor_cards(result):
    cards = []
    for key, (name, unit) in SENSOR_NAMES.items():
        trace = result.get("trace", {}).get(key)
        summ = result.get("sensors", {}).get(key)
        if not trace or not summ:
            continue
        hot = key.endswith("temp")
        cards.append(f"<div class='tile'><div class='kicker'>{esc(name)}</div>"
                     f"<div class='sub'>average {fmt(summ['avg'], unit)} · peak {fmt(summ['max'], unit)}</div>"
                     f"{spark(trace, color='#F5B84B' if hot else ACCENT)}</div>")
    return "<div class='grid'>" + "".join(cards) + "</div>" if cards else ""


def env_table(env, highlight=()):
    rows = "".join(f"<tr><th>{esc(ENV_NAMES.get(k, k))}</th><td{' class=\"unsure\"' if k in highlight else ''}>"
                   f"{esc(v)}</td></tr>" for k, v in env.items() if v not in (None, ""))
    return f"<table>{rows}</table>"


def headline(results):
    """The tiles at the top: one key number per group."""
    pick = {"cpu-7z": ("multi", "CPU, all cores"), "memory": ("triad", "Memory bandwidth"),
            "disk": ("seq_read", "Disk, sequential read"), "gpu-vkmark": ("score", "Graphics"),
            "ai-ollama": ("generate", "Local AI"), "game-beamng": ("pickup_throughput", "BeamNG physics")}
    from bench_core import describe
    tiles = []
    for r in results:
        key, label = pick.get(r["runner"], (None, None))
        m = r["metrics"].get(key) if key else None
        if not m:
            continue
        st = describe(m["values"])
        tiles.append(f"<div class='tile'><div class='kicker'>{esc(label)}</div><div class='big'>{fmt(st['mean'])}</div>"
                     f"<div class='sub'>{esc(m['unit'])}{' · ±%.1f%%' % st['cv'] if st['n'] > 1 else ''}</div></div>")
    return "<div class='grid'>" + "".join(tiles) + "</div>" if tiles else ""


def run_report(run):
    when = time.strftime("%A %d %B %Y, %H:%M", time.localtime(run["started"]))
    title = run.get("label") or ("System benchmark" if run.get("kind") == "system" else "Benchmark")
    body = [f"<h1>{esc(title)}</h1><div class='sub'>{esc(when)} · {run['repeat']} runs of each · "
            f"{fmt(run['seconds'] / 60)} min</div>", headline(run["results"])]
    for r in run["results"]:
        body.append(f"<h2>{esc(r['title'])}</h2>")
        if r.get("error"):
            body.append(f"<div class='card error'>Didn't run: {esc(r['error'])}</div>")
            if not r["metrics"]:
                continue
        body.append(f"<div class='card'>{metric_rows(r)}"
                    + "".join(f"<div class='muted'>{esc(n)}</div>" for n in r.get("notes", [])) + "</div>")
        body.append(sensor_cards(r))
    body.append(f"<h2>This PC</h2><div class='card'>{env_table(run['environment'])}</div>")
    body.append("<p class='muted'>Average: the mean of the runs. 95% range: a percentile bootstrap confidence interval "
                "estimated from these samples. Run-to-run: how much single runs differ (coefficient of variation); under 2% is steady.</p>")
    return page(title, "".join(body))


def compare_report(a, b, title=None, names=("A", "B")):
    from bench_core import compare
    diffs = [k for k in set(a["environment"]) | set(b["environment"])
             if a["environment"].get(k) != b["environment"].get(k)]
    title = title or f"{a.get('label') or a['id']}  vs  {b.get('label') or b['id']}"
    rows = []
    for rb in b["results"]:
        ra = next((r for r in a["results"] if r["runner"] == rb["runner"]), None)
        if not ra or ra.get("error") or rb.get("error"):
            continue
        for key, mb in rb["metrics"].items():
            ma = ra["metrics"].get(key)
            if not ma or not ma["values"] or not mb["values"] or sum(ma["values"]) == 0:
                continue
            if any(ma[k] != mb[k] for k in ("name", "unit", "higher_better")):
                continue
            c = compare(ma["values"], mb["values"], mb["higher_better"])
            mean_a, mean_b = sum(ma["values"]) / len(ma["values"]), sum(mb["values"]) / len(mb["values"])
            rng = f"{c['low']:+.1f}% … {c['high']:+.1f}%" if c["low"] is not None else "need 3+ runs a side"
            label = {"better": f"{names[1]} is better", "worse": f"{names[1]} is worse", "same": "within noise",
                     "unsure": "too few runs"}[c["verdict"]]
            rows.append(f"<tr><td>{esc(rb['title'])}<div class='muted'>{esc(mb['name'])}</div></td>"
                        f"<td class='num'>{fmt(mean_a, ma['unit'])}</td><td class='num'>{fmt(mean_b, mb['unit'])}</td>"
                        f"<td class='num'><b>{c['diff']:+.1f}%</b></td><td class='num sub'>{rng}</td>"
                        f"<td><span class='pill {c['verdict']}'>{label}</span></td></tr>")
    changed = ("<p>What differs between the two: " + ", ".join(f"<b>{esc(ENV_NAMES.get(k, k))}</b> "
               f"({esc(a['environment'].get(k))} → {esc(b['environment'].get(k))})" for k in diffs) + "</p>") if diffs \
        else "<p class='sub'>The recorded environment settings match. Unrecorded settings may differ.</p>"
    body = (f"<h1>{esc(title)}</h1>{changed}<div class='card wrap'><table><tr><th>Measure</th>"
            f"<th class='num'>{esc(names[0])}</th><th class='num'>{esc(names[1])}</th><th class='num'>Change</th>"
            f"<th class='num'>95% range</th><th></th></tr>{''.join(rows)}</table></div>"
            "<p class='muted'>A change counts only when its whole 95% range is on one side of zero; otherwise it's "
            "within the run-to-run noise and these runs do not establish a difference.</p>"
            f"<h2>{esc(names[0])}</h2><div class='card'>{env_table(a['environment'], diffs)}</div>"
            f"<h2>{esc(names[1])}</h2><div class='card'>{env_table(b['environment'], diffs)}</div>")
    return page(title, body)
