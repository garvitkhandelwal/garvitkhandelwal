#!/usr/bin/env python3
"""Render the profile header and stats card, and refresh the writing list.

Usage:  METRICS_TOKEN=... python3 scripts/generate.py

Standard library only. The token needs `repo` + `read:user` so that pull
requests in private repos are counted.
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

    contributions = 0
    for year in range(since, this_year + 1):
        c = gql(
            "query($l:String!,$f:DateTime!,$t:DateTime!){user(login:$l){"
            "contributionsCollection(from:$f,to:$t){contributionCalendar{totalContributions}}}}",
            {"l": LOGIN, "f": f"{year}-01-01T00:00:00Z", "t": f"{year}-12-31T23:59:59Z"},
        )
        contributions += c["contributionsCollection"]["contributionCalendar"]["totalContributions"]

    prs = merged = closed = commits = prs_this_year = 0
    cursor = None
    while True:
        page = gql(
            "query($l:String!,$c:String){user(login:$l){pullRequests(first:100,after:$c){"
            "pageInfo{hasNextPage endCursor} nodes{state createdAt commits{totalCount}}}}}",
            {"l": LOGIN, "c": cursor},
        )["pullRequests"]
        for pr in page["nodes"]:
            prs += 1
            merged += pr["state"] == "MERGED"
            closed += pr["state"] != "OPEN"
            commits += pr["commits"]["totalCount"]
            prs_this_year += pr["createdAt"].startswith(str(this_year))
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    return {
        "prs": prs,
        "prs_this_year": prs_this_year,
        "this_year": this_year,
        "merged": merged,
        "merge_rate": round(100 * merged / max(1, closed)),
        "commits": commits,
        "contributions": contributions,
        "since": since,
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


# Octicons (16px), as used by github-readme-stats.
ICONS = {
    "pr": "M7.177 3.073L9.573.677A.25.25 0 0110 .854v4.792a.25.25 0 01-.427.177L7.177 3.427a.25.25 0 010-.354zM3.75 2.5a.75.75 0 100 1.5.75.75 0 000-1.5zm-2.25.75a2.25 2.25 0 113 2.122v5.256a2.251 2.251 0 11-1.5 0V5.372A2.25 2.25 0 011.5 3.25zM11 2.5h-1V4h1a1 1 0 011 1v5.628a2.251 2.251 0 101.5 0V5A2.5 2.5 0 0011 2.5zm1 10.25a.75.75 0 111.5 0 .75.75 0 01-1.5 0zM3.75 12a.75.75 0 100 1.5.75.75 0 000-1.5z",
    "merge": "M5.45 5.154A4.25 4.25 0 0 0 9.25 7.5h1.378a2.251 2.251 0 1 1 0 1.5H9.25A5.734 5.734 0 0 1 5 7.123v3.505a2.25 2.25 0 1 1-1.5 0V5.372a2.25 2.25 0 1 1 1.95-.218ZM4.25 13.5a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm8.5-4.5a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5ZM5 3.25a.75.75 0 1 0 0 .005V3.25Z",
    "commit": "M1.643 3.143L.427 1.927A.25.25 0 000 2.104V5.75c0 .138.112.25.25.25h3.646a.25.25 0 00.177-.427L2.715 4.215a6.5 6.5 0 11-1.18 4.458.75.75 0 10-1.493.154 8.001 8.001 0 101.6-5.684zM7.75 4a.75.75 0 01.75.75v2.992l2.028.812a.75.75 0 01-.557 1.392l-2.5-1A.75.75 0 017 8.25v-3.5A.75.75 0 017.75 4z",
    "grid": "M1 1h6v6H1zM9 1h6v6H9zM1 9h6v6H1zM9 9h6v6H9z",
}


def stats_card(s):
    """github-readme-stats layout: icon rows on the left, a ring on the right."""
    w, h = 440, 186
    rows = [
        ("pr", "Total PRs", f"{s['prs']:,}"),
        ("pr", f"PRs in {s['this_year']}", f"{s['prs_this_year']:,}"),
        ("merge", "Merged PRs", f"{s['merged']:,}"),
        ("commit", "Total commits", f"{s['commits']:,}"),
        ("grid", "Contributions", f"{s['contributions']:,}"),
    ]
    body = stars(h, 26, seed=3, twinkle=0.12, w=w)
    for i, (icon, label, value) in enumerate(rows):
        y = 30 + i * 30
        body += (
            f'<path transform="translate(24 {y - 12}) scale(.95)" d="{ICONS[icon]}" fill="{ACCENT}"'
            + (' fill-opacity=".9" transform-origin="0 0"' if icon == "grid" else "")
            + "/>"
            f'<text x="50" y="{y}" fill="{INK2}" font-size="14">{label}:</text>'
            f'<text x="206" y="{y}" fill="{INK}" font-size="14" font-weight="700">{value}</text>'
        )
    # merge-rate ring
    cx, cy, r = 352, 93, 46
    circ = 2 * 3.14159265 * r
    on = circ * s["merge_rate"] / 100
    body += (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{STROKE}" stroke-width="7"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{ACCENT}" stroke-width="7" stroke-linecap="round" '
        f'stroke-dasharray="{on:.1f} {circ:.1f}" transform="rotate(-90 {cx} {cy})"/>'
        f'<text x="{cx}" y="{cy + 4}" fill="{INK}" font-size="24" font-weight="700" text-anchor="middle">{s["merge_rate"]}%</text>'
        f'<text x="{cx}" y="{cy + 22}" fill="{MUTED}" font-size="11.5" text-anchor="middle">merged</text>'
    )
    label = (
        f"{s['prs']:,} pull requests, {s['merged']:,} merged ({s['merge_rate']}%), "
        f"{s['commits']:,} commits, {s['contributions']:,} contributions"
    )
    return svg(h, body, label, w)


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
