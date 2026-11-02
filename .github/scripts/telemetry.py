"""Render .assets/telemetry.svg: GitHub stats + a gold contribution heatmap.

Standard library only. Uses the public contributions page and REST API;
set GITHUB_TOKEN to avoid REST rate limits.
"""
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.request

USER = "abhijithwarrier"
OUT = os.path.join(os.path.dirname(__file__), "..", "..", ".assets", "telemetry.svg")

LEVELS = ["#132238", "#4A3D17", "#7D6421", "#B8912E", "#F2D26B"]


def fetch(url, accept="application/json"):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": USER})
    token = os.environ.get("GITHUB_TOKEN")
    if token and "api.github.com" in url:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()


def calendar():
    page = fetch(f"https://github.com/users/{USER}/contributions", "text/html")
    days = {}
    for m in re.finditer(r'data-date="([\d-]+)"\s+id="([^"]+)"\s+data-level="(\d)"', page):
        days[m.group(2)] = {"date": dt.date.fromisoformat(m.group(1)), "level": int(m.group(3)), "count": 0}
    for m in re.finditer(r'for="([^"]+)"[^>]*>([^<]*)</tool-tip>', page):
        if m.group(1) in days:
            n = re.match(r"([\d,]+) contribution", m.group(2))
            days[m.group(1)]["count"] = int(n.group(1).replace(",", "")) if n else 0
    out = sorted(days.values(), key=lambda d: d["date"])
    if not out:
        sys.exit("Could not parse the contributions calendar")
    return out


def repo_stats():
    stars, repos, page = 0, 0, 1
    while True:
        batch = json.loads(fetch(f"https://api.github.com/users/{USER}/repos?per_page=100&page={page}"))
        if not batch:
            break
        for r in batch:
            if not r["fork"]:
                repos += 1
                stars += r["stargazers_count"]
        page += 1
    followers = json.loads(fetch(f"https://api.github.com/users/{USER}"))["followers"]
    return stars, repos, followers


def streaks(days):
    longest = run = 0
    for d in days:
        run = run + 1 if d["count"] else 0
        longest = max(longest, run)
    current = 0
    tail = days[:-1] if days[-1]["count"] == 0 else days  # today may not have commits yet
    for d in reversed(tail):
        if not d["count"]:
            break
        current += 1
    return current, longest


def render(days, stars, repos, followers):
    total = sum(d["count"] for d in days)
    current, longest = streaks(days)
    tiles = [
        (f"{total:,}", "contributions · 1y"),
        (f"{current}d", "current streak"),
        (f"{longest}d", "longest streak"),
        (f"{stars:,}", "stars earned"),
        (f"{repos}", "public repos"),
        (f"{followers:,}", "followers"),
    ]

    W, cell, gap = 1200, 17, 4
    step = cell + gap
    x0, y0 = 44, 236
    first = days[0]["date"]
    offset = (first.weekday() + 1) % 7  # GitHub weeks start on Sunday

    parts = []
    for i, (value, label) in enumerate(tiles):
        tx = 44 + i * 188
        parts.append(
            f'<rect x="{tx}" y="72" width="172" height="96" rx="12" fill="#D4AF37" fill-opacity="0.05" stroke="#D4AF37" stroke-opacity="0.22"/>'
            f'<text x="{tx + 18}" y="120" class="sans" font-size="32" font-weight="800" fill="url(#gold)">{html.escape(value)}</text>'
            f'<text x="{tx + 18}" y="148" class="mono" font-size="12" fill="#8B9BB4">{html.escape(label)}</text>'
        )

    last_month = None
    for i, d in enumerate(days):
        col, row = divmod(i + offset, 7)
        x, y = x0 + col * step, y0 + row * step
        tip = f'{d["count"]} on {d["date"]:%b %-d, %Y}'
        parts.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="4" fill="{LEVELS[d["level"]]}"><title>{tip}</title></rect>')
        if row == 0 or i == 0:
            if d["date"].month != last_month and col < 52:
                parts.append(f'<text x="{x}" y="{y0 - 12}" class="mono" font-size="12" fill="#8B9BB4">{d["date"]:%b}</text>')
                last_month = d["date"].month

    ly = y0 + 7 * step + 22
    parts.append(f'<text x="{W - 44 - 5 * step - 44}" y="{ly + 13}" text-anchor="end" class="mono" font-size="12" fill="#8B9BB4">less</text>')
    for i, c in enumerate(LEVELS):
        parts.append(f'<rect x="{W - 44 - (5 - i) * step - 30}" y="{ly}" width="{cell}" height="{cell}" rx="4" fill="{c}"/>')
    parts.append(f'<text x="{W - 44}" y="{ly + 13}" text-anchor="end" class="mono" font-size="12" fill="#8B9BB4">more</text>')
    updated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    parts.append(f'<text x="44" y="{ly + 13}" class="mono" font-size="12" fill="#8B9BB4">last sync · {updated}</text>')

    H = ly + 48
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" fill="none">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="{W}" y2="{H}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#070D18"/><stop offset="0.6" stop-color="#0B1A2E"/><stop offset="1" stop-color="#003562"/>
    </linearGradient>
    <linearGradient id="gold" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#F5E6A8"/><stop offset="0.6" stop-color="#D4AF37"/><stop offset="1" stop-color="#B8892B"/>
    </linearGradient>
    <linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#D4AF37" stop-opacity="0"/><stop offset="0.5" stop-color="#D4AF37" stop-opacity="0.8"/><stop offset="1" stop-color="#D4AF37" stop-opacity="0"/>
    </linearGradient>
    <clipPath id="card"><rect width="{W}" height="{H}" rx="22"/></clipPath>
    <style>
      .mono {{ font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
      .sans {{ font-family: 'Inter', -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; }}
    </style>
  </defs>
  <g clip-path="url(#card)">
    <rect width="{W}" height="{H}" fill="url(#bg)"/>
    <rect width="{W}" height="44" fill="#050A13" fill-opacity="0.7"/>
    <circle cx="28" cy="22" r="6" fill="#FF5F57"/><circle cx="48" cy="22" r="6" fill="#FEBC2E"/><circle cx="68" cy="22" r="6" fill="#28C840"/>
    <text x="{W // 2}" y="27" text-anchor="middle" class="mono" font-size="13" fill="#8B9BB4">~/abhijithwarrier — telemetry --last 365d</text>
    {"".join(parts)}
    <rect x="0" y="44" width="{W}" height="2" fill="url(#sweep)" opacity="0.45">
      <animate attributeName="y" dur="7s" repeatCount="indefinite" values="44;{H};44"/>
    </rect>
  </g>
  <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="22" stroke="#D4AF37" stroke-opacity="0.25"/>
</svg>
'''


if __name__ == "__main__":
    days = calendar()
    svg = render(days, *repo_stats())
    with open(OUT, "w") as f:
        f.write(svg)
    print(f"wrote {os.path.normpath(OUT)} ({len(days)} days)")
