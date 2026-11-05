"""Render GitHub stats, top-languages and streak cards as self-contained SVGs."""
import json
import os
import sys
import urllib.request
from datetime import date, timedelta
from xml.sax.saxutils import escape

USER = os.environ.get("GH_USER", "AdeMaq")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = sys.argv[1] if len(sys.argv) > 1 else "dist"

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(ownerAffiliation: OWNER, isFork: false, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalRepositoriesWithContributedCommits
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

THEMES = {
    False: dict(bg="#ffffff", border="#d0d7de", title="#0969da", text="#1f2328", muted="#57606a", accent="#0969da"),
    True: dict(bg="#0d1117", border="#30363d", title="#58a6ff", text="#e6edf3", muted="#8b949e", accent="#58a6ff"),
}
FONT = "Segoe UI,Helvetica,Arial,sans-serif"


def fetch():
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=body,
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(payload["errors"])
    return payload["data"]["user"]


def streaks(days):
    counts = {d["date"]: d["contributionCount"] for d in days}
    today = date.today()
    cur, d = 0, today
    if not counts.get(str(d)):  # today may not have contributions yet
        d -= timedelta(days=1)
    while counts.get(str(d)):
        cur += 1
        d -= timedelta(days=1)
    longest = run = 0
    for day in sorted(counts):
        run = run + 1 if counts[day] else 0
        longest = max(longest, run)
    return cur, longest


def card(w, h, t, title, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'font-family="{FONT}">'
            f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="10" fill="{t["bg"]}" stroke="{t["border"]}"/>'
            + (f'<text x="25" y="35" fill="{t["title"]}" font-size="18" font-weight="600">{escape(title)}</text>'
               if title else "") + body + "</svg>")


def stats_card(u, t):
    c = u["contributionsCollection"]
    stars = sum(r["stargazerCount"] for r in u["repositories"]["nodes"])
    rows = [("Total Stars", stars), ("Commits (last year)", c["totalCommitContributions"]),
            ("Pull Requests", c["totalPullRequestContributions"]), ("Issues", c["totalIssueContributions"]),
            ("Contributed to", c["totalRepositoriesWithContributedCommits"]),
            ("Public Repos", u["repositories"]["totalCount"])]
    body = "".join(
        f'<text x="25" y="{70 + i * 28}" fill="{t["muted"]}" font-size="14">{escape(k)}</text>'
        f'<text x="300" y="{70 + i * 28}" fill="{t["text"]}" font-size="14" font-weight="600" text-anchor="end">{v}</text>'
        for i, (k, v) in enumerate(rows))
    return card(330, 90 + len(rows) * 28 - 14, t, f"{USER}'s GitHub Stats", body)


def langs_card(u, t):
    totals, colors = {}, {}
    for r in u["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            totals[n] = totals.get(n, 0) + e["size"]
            colors[n] = e["node"]["color"] or "#8b949e"
    top = sorted(totals.items(), key=lambda kv: -kv[1])[:6]
    whole = sum(v for _, v in top) or 1
    bar, x, legend = [], 25, []
    for i, (n, v) in enumerate(top):
        w = 280 * v / whole
        bar.append(f'<rect x="{x:.1f}" y="55" width="{w:.1f}" height="10" fill="{colors[n]}"/>')
        x += w
        cx, cy = 25 + (i % 2) * 145, 92 + (i // 2) * 24
        legend.append(f'<circle cx="{cx + 5}" cy="{cy - 4}" r="5" fill="{colors[n]}"/>'
                      f'<text x="{cx + 16}" y="{cy}" fill="{t["text"]}" font-size="12">{escape(n)} '
                      f'<tspan fill="{t["muted"]}">{100 * v / whole:.1f}%</tspan></text>')
    clip = f'<clipPath id="c"><rect x="25" y="55" width="280" height="10" rx="5"/></clipPath>'
    body = clip + f'<g clip-path="url(#c)">{"".join(bar)}</g>' + "".join(legend)
    return card(330, 92 + ((len(top) + 1) // 2) * 24 + 8, t, "Most Used Languages", body)


def streak_card(u, t):
    cal = u["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    cur, longest = streaks(days)
    cols = [(cal["totalContributions"], "Total Contributions", "last year"),
            (cur, "Current Streak", "days"), (longest, "Longest Streak", "days")]
    body = ""
    for i, (v, label, sub) in enumerate(cols):
        x = 70 + i * 140
        body += (f'<text x="{x}" y="62" fill="{t["accent"] if i == 1 else t["text"]}" font-size="28" '
                 f'font-weight="700" text-anchor="middle">{v}</text>'
                 f'<text x="{x}" y="86" fill="{t["text"]}" font-size="13" text-anchor="middle">{label}</text>'
                 f'<text x="{x}" y="104" fill="{t["muted"]}" font-size="11" text-anchor="middle">{sub}</text>')
    return card(490, 130, t, None, body)


if __name__ == "__main__":
    user = fetch()
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("stats", stats_card), ("top-langs", langs_card), ("streak", streak_card)):
        for dark in (False, True):
            with open(os.path.join(OUT, f"{name}{'-dark' if dark else ''}.svg"), "w") as f:
                f.write(fn(user, THEMES[dark]))
