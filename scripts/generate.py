#!/usr/bin/env python3
"""Generate the profile README's SVG cards from live GitHub data.

Usage:  GITHUB_TOKEN=... python3 scripts/generate.py

Uses only the standard library. The token must be able to see the private
repos you want counted (a classic PAT with `repo` + `read:user`), otherwise
private pull requests are left out of the totals.
"""

import datetime as dt
import json
import os
import random
import urllib.request
from collections import Counter
from html import escape
from pathlib import Path

LOGIN = os.environ.get("PROFILE_LOGIN", "garvitkhandelwal")
TZ_OFFSET_MIN = int(os.environ.get("TZ_OFFSET_MIN", "330"))  # IST
OUT = Path(__file__).resolve().parent.parent / "assets"

# ── palette (space / terminal) ─────────────────────────────────────────────
BG0, BG1 = "#070A14", "#0D1330"
CARD = "#0B1022"
STROKE = "#1C2442"
INK = "#E8ECF8"
INK2 = "#A3AECB"
MUTED = "#6B7799"
ACCENT = "#8B9CFF"  # periwinkle: the one data hue
ACCENT_HI = "#C4CCFF"
GLOW = "#FFD27A"  # star / highlight

STYLE = f"""<style>
.sans{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif}}
.mono{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace}}
.ink{{fill:{INK}}} .ink2{{fill:{INK2}}} .muted{{fill:{MUTED}}} .acc{{fill:{ACCENT}}}
.fade{{animation:fade .8s ease-out both}}
@keyframes fade{{from{{opacity:0}}}}
.grow{{transform-box:fill-box;transform-origin:bottom;animation:grow .9s cubic-bezier(.2,.8,.2,1) both}}
@keyframes grow{{from{{transform:scaleY(0)}}}}
.growx{{transform-box:fill-box;transform-origin:left;animation:growx .9s cubic-bezier(.2,.8,.2,1) both}}
@keyframes growx{{from{{transform:scaleX(0)}}}}
@media (prefers-reduced-motion:reduce){{.fade,.grow,.growx{{animation:none}}}}
</style>"""


# ── data ───────────────────────────────────────────────────────────────────
def gql(query, variables=None):
    token = os.environ.get("METRICS_TOKEN") or os.environ["GITHUB_TOKEN"]
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-metrics"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        body = json.load(r)
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body["data"]


def fetch():
    u = gql(
        "query($l:String!){user(login:$l){name company createdAt "
        "followers{totalCount} repositories(ownerAffiliations:OWNER,isFork:false){totalCount}}}",
        {"l": LOGIN},
    )["user"]
    first_year = int(u["createdAt"][:4])
    now = dt.datetime.now(dt.timezone.utc)
    years, days = {}, {}
    for y in range(first_year, now.year + 1):
        c = gql(
            "query($l:String!,$f:DateTime!,$t:DateTime!){user(login:$l){contributionsCollection(from:$f,to:$t){"
            "totalCommitContributions restrictedContributionsCount totalPullRequestReviewContributions "
            "contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}",
            {"l": LOGIN, "f": f"{y}-01-01T00:00:00Z", "t": f"{y}-12-31T23:59:59Z"},
        )["user"]["contributionsCollection"]
        years[y] = c["contributionCalendar"]["totalContributions"]
        for w in c["contributionCalendar"]["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = d["contributionCount"]
    prs, cursor = [], None
    while True:
        page = gql(
            "query($l:String!,$c:String){user(login:$l){pullRequests(first:100,after:$c){"
            "pageInfo{hasNextPage endCursor} nodes{state createdAt mergedAt additions deletions "
            "commits{totalCount} repository{nameWithOwner}}}}}",
            {"l": LOGIN, "c": cursor},
        )["user"]["pullRequests"]
        prs += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    return u, years, days, prs


def compute(u, years, days, prs):
    today = dt.datetime.now(dt.timezone(dt.timedelta(minutes=TZ_OFFSET_MIN))).date()
    keys = sorted(k for k in days if k <= today.isoformat())
    longest = run = 0
    for k in keys:
        run = run + 1 if days[k] > 0 else 0
        longest = max(longest, run)
    d, current = today, 0
    if days.get(d.isoformat(), 0) == 0:
        d -= dt.timedelta(days=1)
    while days.get(d.isoformat(), 0) > 0:
        current += 1
        d -= dt.timedelta(days=1)

    def parse(s):
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))

    merged = [p for p in prs if p["state"] == "MERGED"]
    hours = sorted(
        (parse(p["mergedAt"]) - parse(p["createdAt"])).total_seconds() / 3600 for p in merged
    )
    tz = dt.timezone(dt.timedelta(minutes=TZ_OFFSET_MIN))
    by_hour = Counter(parse(p["createdAt"]).astimezone(tz).hour for p in prs)
    weekday = Counter()
    for k, v in days.items():
        weekday[dt.date.fromisoformat(k).weekday()] += v
    this_year = str(today.year)
    best_day = max(days.items(), key=lambda kv: kv[1]) if days else ("", 0)
    return {
        "name": u["name"] or LOGIN,
        "since": u["createdAt"][:4],
        "updated": today.isoformat(),
        "prs": len(prs),
        "merged": len(merged),
        "merge_rate": round(100 * len(merged) / max(1, len(prs) - sum(p["state"] == "OPEN" for p in prs))),
        "commits": sum(p["commits"]["totalCount"] for p in prs),
        "additions": sum(p["additions"] for p in prs),
        "deletions": sum(p["deletions"] for p in prs),
        "median_merge_h": hours[len(hours) // 2] if hours else 0,
        "contributions": sum(years.values()),
        "years": {y: v for y, v in years.items() if v > 0 or y >= int(this_year)},
        "active_days": sum(1 for k in keys if days[k] > 0),
        "longest": longest,
        "current": current,
        "best_day": best_day,
        "prs_this_year": sum(p["createdAt"].startswith(this_year) for p in prs),
        "this_year": this_year,
        "by_hour": [by_hour.get(h, 0) for h in range(24)],
        "weekday": [weekday.get(i, 0) for i in range(7)],
    }


# ── helpers ────────────────────────────────────────────────────────────────
def fmt(n):
    return f"{n:,}"


def short(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{round(n / 1000)}K"
    if n >= 1_000:
        return f"{n / 1000:.1f}K"
    return str(n)


def frame(w, h, body, title):
    if os.environ.get("NO_ANIM"):
        import re
        body = re.sub(r"<animate[^>]*/>", "", body)
        body = body.replace('class="grow"', "").replace('class="growx"', "").replace(" fade", "").replace(' class="fade"', "")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{escape(title)}"><title>{escape(title)}</title>{STYLE}'
        f'<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{BG0}"/><stop offset="1" stop-color="{BG1}"/></linearGradient></defs>'
        f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="14" fill="url(#bg)" stroke="{STROKE}"/>'
        f"{body}</svg>"
    )


def stars(w, h, n, seed, twinkle=0.25):
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


def header(x, y, cmd, right=""):
    s = (
        f'<text x="{x}" y="{y}" class="mono" font-size="13"><tspan fill="{ACCENT}">~</tspan>'
        f'<tspan class="muted"> % </tspan><tspan class="ink">{escape(cmd)}</tspan></text>'
    )
    if right:
        s += f'<text x="{840 - x}" y="{y}" class="mono muted" font-size="11" text-anchor="end">{escape(right)}</text>'
    return s


# ── cards ──────────────────────────────────────────────────────────────────
def banner(s):
    w, h = 840, 250
    body = stars(w, h, 140, seed=11)
    # constellation on the right
    pts = [(600, 70), (648, 52), (700, 84), (742, 66), (770, 120), (716, 150), (668, 132)]
    lines = "".join(
        f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}" stroke="{ACCENT}" stroke-opacity=".35" stroke-width="1"/>'
        for a, b in zip(pts, pts[1:] + [pts[2]])
    )
    nodes = "".join(
        f'<circle cx="{x}" cy="{y}" r="{2.6 if i % 3 == 0 else 1.8}" fill="{GLOW if i == 3 else ACCENT_HI}">'
        f'<animate attributeName="r" values="{2.2 if i % 3 else 2.8};{1.4 if i % 3 else 3.6};{2.2 if i % 3 else 2.8}" '
        f'dur="{3 + i * 0.7:.1f}s" repeatCount="indefinite"/></circle>'
        for i, (x, y) in enumerate(pts)
    )
    # shooting star
    meteor = (
        '<defs><linearGradient id="tail" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff"/></linearGradient></defs>'
        '<g opacity="0"><rect x="-90" y="-1" width="90" height="1.6" rx=".8" fill="url(#tail)"/>'
        '<circle r="1.8" fill="#fff"/>'
        '<animateTransform attributeName="transform" type="translate" values="420,20;640,110" dur="1.4s" begin="2s;meteor.end+7s" id="meteor"/>'
        '<animate attributeName="opacity" values="0;1;0" dur="1.4s" begin="2s;meteor.end+7s"/></g>'
    )
    # moon
    moon = (
        f'<g transform="translate(770 200)" opacity=".9"><circle r="18" fill="{GLOW}" opacity=".12"/>'
        f'<circle r="12" fill="{GLOW}" opacity=".9"/><circle cx="5" cy="-4" r="10.5" fill="{BG1}"/></g>'
    )
    cmd = "whoami"
    out = "builds products from zero · ships after midnight"
    cw = 8.4  # mono char width @14px
    typed = (
        f'<clipPath id="type"><rect x="40" y="168" height="26" width="{len(out) * cw + 4:.0f}">'
        f'<animate attributeName="width" from="0" to="{len(out) * cw + 4:.0f}" dur="2.2s" begin="0.4s" '
        f'fill="freeze" calcMode="discrete" keyTimes="{";".join(f"{i / len(out):.3f}" for i in range(len(out)))}" '
        f'values="{";".join(f"{i * cw:.1f}" for i in range(len(out)))}"/></rect></clipPath>'
        f'<text x="40" y="186" class="mono ink2" font-size="14" clip-path="url(#type)">{escape(out)}</text>'
        f'<rect x="{40 + len(out) * cw + 2:.0f}" y="173" width="8" height="16" fill="{ACCENT}">'
        f'<animate attributeName="x" from="40" to="{40 + len(out) * cw + 2:.0f}" dur="2.2s" begin="0.4s" fill="freeze"/>'
        f'<animate attributeName="opacity" values="1;1;0;0" dur="1s" repeatCount="indefinite"/></rect>'
    )
    body += lines + nodes + meteor + moon
    body += (
        f'<text x="40" y="56" class="mono" font-size="14"><tspan fill="{ACCENT}">garvit@os</tspan>'
        f'<tspan class="muted"> ~ % </tspan><tspan class="ink">{cmd}</tspan></text>'
        f'<text x="38" y="112" class="sans ink fade" font-size="46" font-weight="700" letter-spacing="-1">{escape(s["name"])}</text>'
        f'<text x="40" y="142" class="sans ink2 fade" font-size="16" style="animation-delay:.3s">'
        f'Founding Engineer @ Wavelength <tspan class="muted">(YC W24)</tspan>'
        f'<tspan class="muted">  ·  India  ·  shipping since {s["since"]}</tspan></text>'
        f"{typed}"
        f'<text x="40" y="224" class="mono muted" font-size="11">{fmt(s["contributions"])} contributions  ·  '
        f'{fmt(s["prs"])} pull requests  ·  {fmt(s["active_days"])} days at the keyboard</text>'
    )
    return frame(w, h, body, f"{s['name']} — founding engineer, builder, night owl")


def stats_card(s):
    w, h = 840, 290
    tiles = [
        ("PULL REQUESTS", fmt(s["prs"]), f"{s['prs_this_year']} opened in {s['this_year']}"),
        ("MERGED", fmt(s["merged"]), f"{s['merge_rate']}% of closed PRs landed"),
        ("COMMITS IN PRS", fmt(s["commits"]), "pushed, reviewed, shipped"),
        ("CONTRIBUTIONS", fmt(s["contributions"]), f"since {s['since']}"),
        ("LINES ADDED", "+" + short(s["additions"]), f"−{short(s['deletions'])} deleted, no regrets"),
        ("TIME TO MERGE", f"{s['median_merge_h']:.1f}h", "median, open → merged"),
        ("ACTIVE DAYS", fmt(s["active_days"]), f"longest streak: {s['longest']} days"),
        ("BEST DAY", fmt(s["best_day"][1]), "contributions on " + dt.date.fromisoformat(s["best_day"][0]).strftime("%-d %b %Y") if s["best_day"][0] else ""),
    ]
    body = stars(w, h, 40, seed=3, twinkle=0.15) + header(28, 36, "gh stats --all-time", f"updated {s['updated']}")
    tw, th, gx, gy, x0, y0 = 186, 104, 14, 14, 28, 58
    for i, (label, value, cap) in enumerate(tiles):
        x, y = x0 + (i % 4) * (tw + gx), y0 + (i // 4) * (th + gy)
        d = f"animation-delay:{0.08 * i:.2f}s"
        body += (
            f'<g class="fade" style="{d}"><rect x="{x}" y="{y}" width="{tw}" height="{th}" rx="10" fill="{CARD}" fill-opacity=".85" stroke="{STROKE}"/>'
            f'<rect x="{x + 16}" y="{y + 16}" width="14" height="3" rx="1.5" fill="{GLOW if i == 0 else ACCENT}"/>'
            f'<text x="{x + 16}" y="{y + 36}" class="mono muted" font-size="10.5" letter-spacing=".8">{label}</text>'
            f'<text x="{x + 15}" y="{y + 70}" class="sans ink" font-size="30" font-weight="700" letter-spacing="-.5">{escape(value)}</text>'
            f'<text x="{x + 16}" y="{y + 90}" class="sans muted" font-size="11.5">{escape(cap)}</text></g>'
        )
    return frame(w, h, body, f"GitHub stats: {s['prs']} pull requests, {s['merged']} merged, {s['commits']} commits")


def years_card(s):
    w, h = 840, 300
    ys = sorted(s["years"])
    ys = [y for y in ys if y >= min(y for y in ys if s["years"][y] > 5)]
    vals = [s["years"][y] for y in ys]
    top = max(vals) or 1
    left, right, base, ph = 40, 40, 232, 150
    n = len(ys)
    slot = (w - left - right) / n
    bw = min(46, slot * 0.58)
    body = stars(w, h, 36, seed=5, twinkle=0.15) + header(28, 36, "git log --contributions --by-year", f"{fmt(s['contributions'])} total")
    # recessive baseline + gridlines
    for frac in (0.5, 1.0):
        gy = base - ph * frac
        body += f'<line x1="{left}" x2="{w - right}" y1="{gy:.1f}" y2="{gy:.1f}" stroke="{STROKE}" stroke-dasharray="2 4"/>'
    body += f'<line x1="{left}" x2="{w - right}" y1="{base}" y2="{base}" stroke="{STROKE}"/>'
    for i, (y, v) in enumerate(zip(ys, vals)):
        cx = left + slot * i + slot / 2
        bh = max(2, ph * v / top)
        fill = ACCENT_HI if y == int(s["this_year"]) else ACCENT
        r = min(4, bw / 2)
        x0, y0 = cx - bw / 2, base - bh
        # rounded top, square at baseline
        path = (
            f"M{x0:.1f},{base} V{y0 + r:.1f} Q{x0:.1f},{y0:.1f} {x0 + r:.1f},{y0:.1f} "
            f"H{x0 + bw - r:.1f} Q{x0 + bw:.1f},{y0:.1f} {x0 + bw:.1f},{y0 + r:.1f} V{base} Z"
        )
        body += f'<path d="{path}" fill="{fill}" fill-opacity=".85" class="grow" style="animation-delay:{0.06 * i:.2f}s"/>'
        body += f'<text x="{cx:.1f}" y="{y0 - 8:.1f}" class="mono ink2 fade" font-size="11" text-anchor="middle" style="animation-delay:{0.6 + 0.04 * i:.2f}s">{fmt(v)}</text>'
        body += f'<text x="{cx:.1f}" y="{base + 18}" class="mono muted" font-size="11" text-anchor="middle">{y}</text>'
    # era brackets
    def era(a, b, label):
        if a not in ys or b not in ys:
            return ""
        xa = left + slot * ys.index(a) + slot / 2 - bw / 2
        xb = left + slot * ys.index(b) + slot / 2 + bw / 2
        yb = base + 34
        return (
            f'<path d="M{xa:.1f},{yb - 4} V{yb} H{xb:.1f} V{yb - 4}" fill="none" stroke="{MUTED}" stroke-opacity=".6"/>'
            f'<text x="{(xa + xb) / 2:.1f}" y="{yb + 15}" class="mono muted" font-size="10.5" text-anchor="middle">{label}</text>'
        )
    body += era(2017, 2019, "open source era")
    body += era(2021, ys[-1], "startup era — building products from zero")
    return frame(w, h, body, "Contributions per year")


def rhythm_card(s):
    w, h = 840, 320
    body = stars(w, h, 36, seed=9, twinkle=0.15) + header(28, 36, "when --do-i-ship", f"times in IST")
    # radial 24h clock
    import math

    cx, cy, r0, rmax = 180, 186, 30, 78
    hours = s["by_hour"]
    top = max(hours) or 1
    body += f'<circle cx="{cx}" cy="{cy}" r="{r0 + rmax + 6}" fill="none" stroke="{STROKE}" stroke-dasharray="2 4"/>'
    body += f'<circle cx="{cx}" cy="{cy}" r="{r0 - 6}" fill="{CARD}" stroke="{STROKE}"/>'
    for hr in range(24):
        a = math.radians(hr * 15 - 90)
        L = rmax * hours[hr] / top
        x1, y1 = cx + r0 * math.cos(a), cy + r0 * math.sin(a)
        x2, y2 = cx + (r0 + max(L, 1.5)) * math.cos(a), cy + (r0 + max(L, 1.5)) * math.sin(a)
        night = hr >= 22 or hr < 5
        col = ACCENT_HI if night else ACCENT
        body += (
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{col}" stroke-width="7" '
            f'stroke-linecap="round" stroke-opacity="{0.95 if night else 0.7}" class="fade" style="animation-delay:{0.03 * hr:.2f}s"/>'
        )
    for hr, lab in ((0, "00"), (6, "06"), (12, "12"), (18, "18")):
        a = math.radians(hr * 15 - 90)
        lx, ly = cx + (r0 + rmax + 18) * math.cos(a), cy + (r0 + rmax + 18) * math.sin(a) + 4
        body += f'<text x="{lx:.1f}" y="{ly:.1f}" class="mono muted" font-size="10.5" text-anchor="middle">{lab}</text>'
    body += f'<circle cx="{cx}" cy="{cy}" r="9" fill="{GLOW}"/><circle cx="{cx + 4}" cy="{cy - 3}" r="7.8" fill="{CARD}"/>'

    total = sum(hours) or 1
    night_share = round(100 * sum(hours[h] for h in list(range(22, 24)) + list(range(0, 5))) / total)
    peak = max(range(24), key=lambda h: hours[h])
    pk = dt.time(peak).strftime("%-I %p")
    # text column
    tx = 345
    body += (
        f'<text x="{tx}" y="132" class="mono muted" font-size="10.5" letter-spacing=".8">PRS OPENED BY HOUR</text>'
        f'<text x="{tx}" y="168" class="sans ink" font-size="30" font-weight="700">{night_share}%</text>'
        f'<text x="{tx}" y="190" class="sans ink2" font-size="12.5">between 10 PM and 5 AM</text>'
        f'<text x="{tx}" y="206" class="sans muted" font-size="12.5">peak hour: {pk}</text>'
    )
    # weekday bars
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    wd = s["weekday"]
    wtop = max(wd) or 1
    bx, by0, bwmax, bh, gap = 520, 84, 205, 14, 14
    body += f'<text x="{bx}" y="76" class="mono muted" font-size="10.5" letter-spacing=".8">CONTRIBUTIONS BY WEEKDAY</text>'
    best = max(range(7), key=lambda i: wd[i])
    for i, (nm, v) in enumerate(zip(names, wd)):
        y = by0 + i * (bh + gap) + 8
        L = max(3, bwmax * v / wtop)
        fill = ACCENT_HI if i == best else ACCENT
        body += (
            f'<text x="{bx}" y="{y + 11}" class="mono ink2" font-size="11.5">{nm}</text>'
            f'<rect x="{bx + 40}" y="{y}" width="{L:.1f}" height="{bh}" rx="4" fill="{fill}" fill-opacity="{0.95 if i == best else 0.75}" class="growx" style="animation-delay:{0.06 * i:.2f}s"/>'
            f'<text x="{bx + 48 + L:.1f}" y="{y + 11}" class="mono muted" font-size="11">{fmt(v)}</text>'
        )
    return frame(w, h, body, f"Shipping rhythm: {night_share}% of PRs opened between 10 PM and 5 AM")


def main():
    s = compute(*fetch())
    OUT.mkdir(exist_ok=True)
    cards = {"banner.svg": banner, "stats.svg": stats_card, "years.svg": years_card, "rhythm.svg": rhythm_card}
    for name, fn in cards.items():
        (OUT / name).write_text(fn(s))
    snap = {k: v for k, v in s.items() if k not in ("by_hour", "weekday")}
    snap["years"] = {str(k): v for k, v in s["years"].items()}
    (OUT / "stats.json").write_text(json.dumps(snap, indent=2) + "\n")
    print(json.dumps(snap, indent=2))


if __name__ == "__main__":
    main()
