#!/usr/bin/env python3
"""Render the profile header and stats card, and refresh the writing list.

Usage:  GITHUB_TOKEN=... python3 scripts/generate.py

Standard library only. Contribution totals are public
(private work is included as anonymous counts), so the default Actions token
is enough.
"""

import datetime as dt
import html
import json
import os
import random
import re
import urllib.request
from pathlib import Path

LOGIN = os.environ.get("PROFILE_LOGIN", "garvitkhandelwal")
NAME = "Garvit Khandelwal"
ROLE = "Founding Engineer at Wavelength (YC W24)"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
README = ROOT / "README.md"
SITE = "https://garvitkhandelwal.com"

W = 840
BG0, BG1 = "#070A14", "#0D1330"
TILE, STROKE = "#0B1022", "#1C2442"
INK, INK2, MUTED = "#E8ECF8", "#A3AECB", "#7884A6"
STAR, ACCENT = "#C4CCFF", "#8B9CFF"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"


# ── data ───────────────────────────────────────────────────────────────────
def gql(query, variables):
    token = os.environ.get("METRICS_TOKEN") or os.environ["GITHUB_TOKEN"]
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-stats"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        body = json.load(r)
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body["data"]["user"]


def stats():
    since = int(gql("query($l:String!){user(login:$l){createdAt}}", {"l": LOGIN})["createdAt"][:4])
    this_year = dt.date.today().year

    by_year, days = {}, {}
    for year in range(since, this_year + 1):
        cal = gql(
            "query($l:String!,$f:DateTime!,$t:DateTime!){user(login:$l){contributionsCollection(from:$f,to:$t){"
            "contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}",
            {"l": LOGIN, "f": f"{year}-01-01T00:00:00Z", "t": f"{year}-12-31T23:59:59Z"},
        )["contributionsCollection"]["contributionCalendar"]
        by_year[year] = cal["totalContributions"]
        for week in cal["weeks"]:
            for d in week["contributionDays"]:
                days[d["date"]] = d["contributionCount"]

    big_years = [y for y, v in by_year.items() if v >= 1000]

    best_date, best = max(days.items(), key=lambda kv: (kv[1], kv[0]))
    return {
        "contributions": sum(by_year.values()),
        "this_year_contributions": by_year[this_year],
        "this_year": this_year,
        "since": since,
        "years_on_github": this_year - since,
        "active_days": sum(1 for v in days.values() if v > 0),
        "big_years": big_years,
        "best_day": best,
        "best_date": best_date,
        "by_year": by_year,
    }


# ── svg ────────────────────────────────────────────────────────────────────
def svg(h, body, label, w=W):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{label}"><title>{label}</title>'
        f'<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{BG0}"/><stop offset="1" stop-color="{BG1}"/></linearGradient></defs>'
        f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="14" fill="url(#bg)" stroke="{STROKE}"/>'
        f'<g font-family="{SANS}">{body}</g></svg>'
    )


def stars(h, n, seed, twinkle, w=W):
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        x, y = rnd.uniform(6, w - 6), rnd.uniform(6, h - 6)
        r = rnd.choice([0.5, 0.6, 0.7, 0.8, 1.0, 1.2, 1.5])
        op = rnd.uniform(0.25, 0.85)
        anim = ""
        if rnd.random() < twinkle:
            anim = (
                f'<animate attributeName="opacity" values="{op:.2f};0.1;{op:.2f}" '
                f'dur="{rnd.uniform(2.5, 6):.1f}s" begin="{rnd.uniform(0, 4):.1f}s" repeatCount="indefinite"/>'
            )
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="#fff" opacity="{op:.2f}">{anim}</circle>')
    return "".join(out)


def header():
    h = 190
    pts = [(600, 58), (648, 40), (700, 72), (742, 54), (770, 108), (716, 138), (668, 120)]
    lines = "".join(
        f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}" stroke="{ACCENT}" stroke-opacity=".35"/>'
        for a, b in zip(pts, pts[1:] + [pts[2]])
    )
    nodes = "".join(
        f'<circle cx="{x}" cy="{y}" r="{2.4 if i % 3 == 0 else 1.7}" fill="{STAR}">'
        f'<animate attributeName="opacity" values="1;.45;1" dur="{3 + i * 0.7:.1f}s" repeatCount="indefinite"/></circle>'
        for i, (x, y) in enumerate(pts)
    )
    meteor = (
        '<linearGradient id="tail" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff"/></linearGradient>'
        '<g opacity="0"><rect x="-90" y="-.8" width="90" height="1.6" rx=".8" fill="url(#tail)"/><circle r="1.8" fill="#fff"/>'
        '<animateTransform id="meteor" attributeName="transform" type="translate" values="420,16;640,100" dur="1.4s" begin="2s;meteor.end+8s"/>'
        '<animate attributeName="opacity" values="0;1;0" dur="1.4s" begin="2s;meteor.end+8s"/></g>'
    )
    body = (
        stars(h, 120, seed=11, twinkle=0.25) + lines + nodes + meteor
        + f'<text x="40" y="100" fill="{INK}" font-size="44" font-weight="700" letter-spacing="-1">{NAME}</text>'
        + f'<text x="41" y="134" fill="{INK2}" font-size="17">{ROLE}</text>'
    )
    return svg(h, body, f"{NAME}, {ROLE}")


def tiles_card(tiles, label, w=440, cols=2):
    pad, gap, th = 16, 10, 100
    rows = -(-len(tiles) // cols)
    h = 2 * pad + rows * th + (rows - 1) * gap
    tw = (w - 2 * pad - (cols - 1) * gap) / cols
    body = stars(h, 34, seed=3, twinkle=0.12, w=w)
    for i, (name, value, note) in enumerate(tiles):
        x, y = pad + (i % cols) * (tw + gap), pad + (i // cols) * (th + gap)
        body += (
            f'<rect x="{x:.1f}" y="{y}" width="{tw:.1f}" height="{th}" rx="10" fill="{TILE}" fill-opacity=".85" stroke="{STROKE}"/>'
            f'<text x="{x + 18:.1f}" y="{y + 30}" fill="{MUTED}" font-size="14">{name}</text>'
            f'<text x="{x + 17:.1f}" y="{y + 68}" fill="{INK}" font-size="32" font-weight="700" letter-spacing="-.5">{value}</text>'
            f'<text x="{x + 18:.1f}" y="{y + 89}" fill="{MUTED}" font-size="13">{note}</text>'
        )
    return svg(h, body, label, w)


def stats_card(s):
    big = s["big_years"]
    span = s["this_year"] - min(big) + 1 if big else 0
    best_on = dt.date.fromisoformat(s["best_date"]).strftime("%-d %b %Y")
    tiles = [
        ("Total contributions", f"{s['contributions']:,}", "all time"),
        (f"Contributions in {s['this_year']}", f"{s['this_year_contributions']:,}", "and counting"),
        ("Active days", f"{s['active_days']:,}", "days with a contribution"),
        ("1,000+ contributions", f"{len(big)} years", f"out of the last {span}" if big else "in a year"),
        ("Best day", f"{s['best_day']:,}", f"on {best_on}"),
        ("On GitHub", f"{s['years_on_github']} years", f"since {s['since']}"),
    ]
    label = (
        f"{s['contributions']:,} contributions since {s['since']}, {s['this_year_contributions']:,} in {s['this_year']}, "
        f"{s['active_days']:,} active days, best day {s['best_day']} contributions"
    )
    return tiles_card(tiles, label)


def years_card(s):
    w, h = W, 236
    years = [y for y in sorted(s["by_year"]) if s["by_year"][y] > 0]
    years = years[next(i for i, y in enumerate(years) if s["by_year"][y] >= 10):]
    vals = [s["by_year"][y] for y in years]
    top = max(vals)
    left, right, base, ph = 32, 32, 196, 120
    slot = (w - left - right) / len(years)
    bw = min(44, slot * 0.56)
    body = stars(h, 40, seed=5, twinkle=0.12)
    body += f'<text x="{left}" y="36" fill="{INK}" font-size="15" font-weight="600">Contributions by year</text>'
    body += f'<line x1="{left}" x2="{w - right}" y1="{base}" y2="{base}" stroke="{STROKE}"/>'
    for i, (y, v) in enumerate(zip(years, vals)):
        cx = left + slot * i + slot / 2
        bh = max(2, ph * v / top)
        x0, y0, r = cx - bw / 2, base - bh, min(4, bh / 2)
        path = (
            f"M{x0:.1f},{base} V{y0 + r:.1f} Q{x0:.1f},{y0:.1f} {x0 + r:.1f},{y0:.1f} "
            f"H{x0 + bw - r:.1f} Q{x0 + bw:.1f},{y0:.1f} {x0 + bw:.1f},{y0 + r:.1f} V{base} Z"
        )
        fill = STAR if y == s["this_year"] else ACCENT
        body += (
            f'<path d="{path}" fill="{fill}" fill-opacity=".85"/>'
            f'<text x="{cx:.1f}" y="{y0 - 8:.1f}" fill="{INK2}" font-size="12" text-anchor="middle">{v:,}</text>'
            f'<text x="{cx:.1f}" y="{base + 20}" fill="{MUTED}" font-size="12" text-anchor="middle">{y}</text>'
        )
    label = "Contributions by year: " + ", ".join(f"{y}: {v:,}" for y, v in zip(years, vals))
    return svg(h, body, label)


# ── writing, from the site's sitemap ───────────────────────────────────────
def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "profile-stats"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def writing(limit=5):
    urls = re.findall(r"<loc>([^<]+/blog/[^<]+)</loc>", fetch(f"{SITE}/sitemap.xml"))
    posts = []
    for url in urls:
        page = fetch(url)
        title = re.search(r"<title>(.*?)</title>", page, re.S)
        date = re.search(r'article:published_time" content="([0-9-]+)', page)
        if title:
            name = html.unescape(title.group(1)).split(" | ")[0].strip()
            posts.append((date.group(1) if date else "", name, url))
    posts.sort(reverse=True)
    return [
        f"- [{name}]({url})" + (f" · {dt.date.fromisoformat(d):%b %Y}" if d else "")
        for d, name, url in posts[:limit]
    ]


def update_readme(lines):
    text = README.read_text()
    block = "<!-- writing:start -->\n" + "\n".join(lines) + "\n<!-- writing:end -->"
    README.write_text(re.sub(r"<!-- writing:start -->.*?<!-- writing:end -->", lambda _: block, text, flags=re.S))


def main():
    s = stats()
    OUT.mkdir(exist_ok=True)
    (OUT / "header.svg").write_text(header())
    (OUT / "stats.svg").write_text(stats_card(s))
    (OUT / "years.svg").write_text(years_card(s))
    try:
        posts = writing()
    except Exception as e:  # the site being down shouldn't block the stats refresh
        print(f"skipping writing list: {e}")
    else:
        if posts:
            update_readme(posts)
    print(json.dumps(s))


if __name__ == "__main__":
    main()
