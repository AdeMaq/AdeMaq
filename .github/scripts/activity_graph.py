"""Render the last 30 days of GitHub contributions as a self-contained SVG."""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

USER = os.environ.get("GH_USER", "AdeMaq")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = sys.argv[1] if len(sys.argv) > 1 else "dist"
DAYS = 30

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch():
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=DAYS + 1)
    body = json.dumps({"query": QUERY, "variables": {
        "login": USER, "from": start.isoformat(), "to": now.isoformat()}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=body,
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = {d["date"]: d["contributionCount"] for w in weeks for d in w["contributionDays"]}
    today = now.date()
    return [(today - timedelta(days=i), days.get(str(today - timedelta(days=i)), 0))
            for i in range(DAYS - 1, -1, -1)]


def render(points, dark):
    bg, fg, grid, line, fill = (("#0d1117", "#9ca3af", "#21262d", "#58a6ff", "#58a6ff")
                                if dark else
                                ("#ffffff", "#57606a", "#eaeef2", "#0969da", "#0969da"))
    w, h, l, r, t, b = 850, 280, 48, 24, 48, 40
    pw, ph = w - l - r, h - t - b
    peak = max(1, max(c for _, c in points))
    top = max(4, -(-peak // 4) * 4)
    xs = [l + pw * i / (len(points) - 1) for i in range(len(points))]
    ys = [t + ph * (1 - c / top) for _, c in points]
    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(zip(xs, ys)))
    area = f"{path} L{xs[-1]:.1f},{t + ph} L{xs[0]:.1f},{t + ph} Z"
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
         f'font-family="Segoe UI,Helvetica,Arial,sans-serif">',
         f'<rect width="{w}" height="{h}" rx="12" fill="{bg}"/>',
         f'<text x="{l}" y="28" fill="{fg}" font-size="15" font-weight="600">'
         f'Contributions · last {DAYS} days · {sum(c for _, c in points)} total</text>']
    for i in range(5):
        y = t + ph * i / 4
        s.append(f'<line x1="{l}" x2="{w - r}" y1="{y:.1f}" y2="{y:.1f}" stroke="{grid}"/>')
        s.append(f'<text x="{l - 8}" y="{y + 4:.1f}" fill="{fg}" font-size="11" text-anchor="end">'
                 f'{int(top * (1 - i / 4))}</text>')
    for i in range(0, len(points), 5):
        s.append(f'<text x="{xs[i]:.1f}" y="{h - 14}" fill="{fg}" font-size="11" text-anchor="middle">'
                 f'{points[i][0].strftime("%b %d")}</text>')
    s.append(f'<path d="{area}" fill="{fill}" fill-opacity="0.15"/>')
    s.append(f'<path d="{path}" fill="none" stroke="{line}" stroke-width="2.5" stroke-linejoin="round"/>')
    for x, y, (_, c) in zip(xs, ys, points):
        if c:
            s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{line}"/>')
    s.append("</svg>")
    return "\n".join(s)


if __name__ == "__main__":
    pts = fetch()
    os.makedirs(OUT, exist_ok=True)
    for name, dark in (("activity-graph.svg", False), ("activity-graph-dark.svg", True)):
        with open(os.path.join(OUT, name), "w") as f:
            f.write(render(pts, dark))
