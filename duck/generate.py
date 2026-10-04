#!/usr/bin/env python3
"""Draw the GitHub contribution graph as blueberries a rubber duck eats.

Each day is a cell. Days with contributions are blueberries, darker on
busier days. A rubber duck walks the grid column by column, up and down,
and eats each blueberry as it reaches it. Then the pie refills and the
loop starts again.

Writes two animated SVGs: duck.svg (lemon custard, for light mode) and
duck-dark.svg (blueberry pie, for dark mode).

Usage:
    GITHUB_TOKEN=... python duck/generate.py --user stanislavamv --out dist
    python duck/generate.py --sample --out dist     # fake data, no token

Standard library only, so the workflow needs no pip install.
"""
import argparse
import json
import os
import random
import sys
import urllib.request
from datetime import date, timedelta

CELL = 11       # cell size, same as GitHub's graph
GAP = 3
PAD_X = 16
PAD_TOP = 34    # room for the caption
PAD_BOTTOM = 14
LOOP_SECONDS = 36
WALK_SHARE = 0.86   # share of the loop the duck spends walking

THEMES = {
    "light": {
        "bg": "#fff6d6",      # lemon custard
        "crumb": "#d9a35b",   # pie crust, empty days
        "berries": ["#b9b3e6", "#8c83e0", "#5a50c4", "#2f2880"],
        "text": "#2b2650",
        "duck": "#ffd84d", "duck_line": "#221e4a", "beak": "#e8892b",
    },
    "dark": {
        "bg": "#221e4a",      # blueberry filling
        "crumb": "#d9a35b",
        "berries": ["#4b448f", "#6e63d9", "#9d94f0", "#cfc9ff"],
        "text": "#fff6d6",
        "duck": "#ffe58a", "duck_line": "#120f2e", "beak": "#e8892b",
    },
}

LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
          "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date weekday contributionLevel } }
      }
    }
  }
}"""


def fetch(user, token):
    """Return (weeks, total). weeks is a list of columns of (weekday, level)."""
    body = json.dumps({"query": QUERY, "variables": {"login": user}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "duck-graph"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        sys.exit(f"GitHub API error: {data['errors']}")
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = [[(d["weekday"], LEVELS[d["contributionLevel"]]) for d in w["contributionDays"]]
             for w in cal["weeks"]]
    return weeks, cal["totalContributions"]


def sample():
    """A plausible year of fake data for previews."""
    rnd = random.Random(7)
    start = date.today() - timedelta(days=364)
    start -= timedelta(days=(start.weekday() + 1) % 7)  # back to Sunday
    weeks, week, total = [], [], 0
    d = start
    while d <= date.today():
        wd = (d.weekday() + 1) % 7
        busy = 0.15 + 0.6 * (d > date.today() - timedelta(days=60))
        level = 0 if rnd.random() > busy else rnd.choice([1, 1, 2, 2, 3, 4])
        total += [0, 1, 3, 6, 10][level]
        week.append((wd, level))
        if wd == 6:
            weeks.append(week)
            week = []
        d += timedelta(days=1)
    if week:
        weeks.append(week)
    return weeks, total


def cell_xy(col, row):
    return PAD_X + col * (CELL + GAP), PAD_TOP + row * (CELL + GAP)


def duck_svg(t):
    """A small rubber duck facing right, drawn around (0,0), about 16px wide."""
    return f"""
    <g stroke="{t['duck_line']}" stroke-width="1.1" stroke-linejoin="round">
      <path d="M-8,1 C-8,-4 -3,-5 1,-3 C2,-7 7,-8 8,-4 C9,-2 8,0 7,1 C8,5 4,7 -1,7 C-6,7 -8,4 -8,1 Z" fill="{t['duck']}"/>
      <path d="M8,-3.5 L12,-2.6 L8,-1.2 Z" fill="{t['beak']}"/>
      <path d="M-5,2 C-3,4 0,4 2,2" fill="none"/>
    </g>
    <circle cx="5" cy="-4.2" r="0.95" fill="{t['duck_line']}"/>"""


def render(weeks, total, theme, label):
    t = THEMES[theme]
    cols = len(weeks)
    width = PAD_X * 2 + cols * (CELL + GAP) - GAP
    height = PAD_TOP + 7 * (CELL + GAP) - GAP + PAD_BOTTOM

    # Serpentine walk: down even columns, up odd ones. Every cell is a step,
    # so the duck moves at a steady pace whether a day had a berry or not.
    order = []
    for c, week in enumerate(weeks):
        rows = sorted(week)
        if c % 2:
            rows = rows[::-1]
        order.extend((c, wd, lvl) for wd, lvl in rows)
    steps = max(len(order) - 1, 1)

    def pct(i):
        return 100 * WALK_SHARE * i / steps

    # Duck keyframes only at the ends of each column, plus start and finish.
    frames = []
    for i, (c, wd, _) in enumerate(order):
        nxt = order[i + 1] if i + 1 < len(order) else None
        prv = order[i - 1] if i else None
        if prv is None or nxt is None or nxt[0] != c or prv[0] != c:
            x, y = cell_xy(c, wd)
            frames.append(f"{pct(i):.3f}%{{transform:translate({x + CELL / 2:.1f}px,{y + CELL / 2 - 2:.1f}px)}}")
    lx, ly = cell_xy(order[-1][0], order[-1][1])
    frames.append(f"100%{{transform:translate({lx + CELL / 2:.1f}px,{ly + CELL / 2 - 2:.1f}px)}}")

    css = [f"""
      .duck{{animation:walk {LOOP_SECONDS}s linear infinite}}
      @keyframes walk{{{''.join(frames)}}}
      .b{{animation-duration:{LOOP_SECONDS}s;animation-iteration-count:infinite;animation-timing-function:step-end}}
      @media (prefers-reduced-motion: reduce){{.duck,.b{{animation:none}}}}"""]

    shapes = []
    for i, (c, wd, lvl) in enumerate(order):
        x, y = cell_xy(c, wd)
        cx, cy = x + CELL / 2, y + CELL / 2
        if lvl == 0:
            shapes.append(f'<circle cx="{cx}" cy="{cy}" r="1.3" fill="{t["crumb"]}" opacity=".45"/>')
            continue
        # A crumb stays where the berry was, so the grid keeps its shape.
        shapes.append(f'<circle cx="{cx}" cy="{cy}" r="1.3" fill="{t["crumb"]}" opacity=".45"/>')
        p = pct(i)
        # Visible until the duck arrives, gone until the refill near the end.
        css.append(f"@keyframes e{i}{{0%{{opacity:1}}{p:.3f}%{{opacity:0}}{100 * (WALK_SHARE + 0.06):.1f}%{{opacity:1}}}}"
                   f".e{i}{{animation-name:e{i}}}")
        r = 2.6 + 0.55 * lvl
        shapes.append(
            f'<g class="b e{i}"><circle cx="{cx}" cy="{cy}" r="{r:.2f}" fill="{t["berries"][lvl - 1]}"/>'
            f'<circle cx="{cx - r / 3:.2f}" cy="{cy - r / 3:.2f}" r="{r / 4:.2f}" fill="#fff" opacity=".35"/></g>')

    caption = f"{total} contributions in the last year, {label}"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="GitHub contributions: {total} in the last year, drawn as blueberries a rubber duck eats">
  <style>{''.join(css)}</style>
  <rect width="100%" height="100%" rx="10" fill="{t['bg']}"/>
  <text x="{PAD_X}" y="21" fill="{t['text']}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="11" opacity=".75">{caption}</text>
  {''.join(shapes)}
  <g class="duck">{duck_svg(t)}</g>
</svg>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user")
    ap.add_argument("--out", default="dist")
    ap.add_argument("--sample", action="store_true", help="fake data, no token needed")
    a = ap.parse_args()

    if a.sample:
        weeks, total = sample()
        label = "sample data"
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not (a.user and token):
            sys.exit("Need --user and GITHUB_TOKEN, or --sample.")
        weeks, total = fetch(a.user, token)
        label = f"@{a.user}"

    os.makedirs(a.out, exist_ok=True)
    for theme, name in (("light", "duck.svg"), ("dark", "duck-dark.svg")):
        with open(os.path.join(a.out, name), "w", encoding="utf-8") as f:
            f.write(render(weeks, total, theme, label))
    print(f"Wrote {a.out}/duck.svg and {a.out}/duck-dark.svg ({total} contributions)")


if __name__ == "__main__":
    main()
