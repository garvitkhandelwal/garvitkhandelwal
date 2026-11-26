#!/usr/bin/env python3
"""Refresh the stats line in README.md from live GitHub data.

Usage:  METRICS_TOKEN=... python3 scripts/generate.py

Standard library only. The token needs `repo` + `read:user` so that pull
requests in private repos are counted.
"""

import datetime as dt
import json
import os
import re
import urllib.request
from pathlib import Path

LOGIN = os.environ.get("PROFILE_LOGIN", "garvitkhandelwal")
README = Path(__file__).resolve().parent.parent / "README.md"


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
    user = gql("query($l:String!){user(login:$l){createdAt}}", {"l": LOGIN})
    since = int(user["createdAt"][:4])

    contributions = 0
    for year in range(since, dt.date.today().year + 1):
        c = gql(
            "query($l:String!,$f:DateTime!,$t:DateTime!){user(login:$l){"
            "contributionsCollection(from:$f,to:$t){contributionCalendar{totalContributions}}}}",
            {"l": LOGIN, "f": f"{year}-01-01T00:00:00Z", "t": f"{year}-12-31T23:59:59Z"},
        )
        contributions += c["contributionsCollection"]["contributionCalendar"]["totalContributions"]

    prs = merged = commits = 0
    cursor = None
    while True:
        page = gql(
            "query($l:String!,$c:String){user(login:$l){pullRequests(first:100,after:$c){"
            "pageInfo{hasNextPage endCursor} nodes{merged commits{totalCount}}}}}",
            {"l": LOGIN, "c": cursor},
        )["pullRequests"]
        for pr in page["nodes"]:
            prs += 1
            merged += pr["merged"]
            commits += pr["commits"]["totalCount"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    return prs, merged, commits, contributions, since


def main():
    prs, merged, commits, contributions, since = stats()
    line = (
        f"**{prs:,}** pull requests &nbsp;·&nbsp; **{merged:,}** merged &nbsp;·&nbsp; "
        f"**{commits:,}** commits &nbsp;·&nbsp; **{contributions:,}** contributions since {since}"
    )
    text = README.read_text()
    if "<!-- stats:start -->" not in text:
        raise SystemExit("stats markers not found in README.md")
    README.write_text(
        re.sub(
            r"<!-- stats:start -->.*?<!-- stats:end -->",
            lambda _: f"<!-- stats:start -->\n{line}\n<!-- stats:end -->",
            text,
            flags=re.S,
        )
    )
    print(line)


if __name__ == "__main__":
    main()
