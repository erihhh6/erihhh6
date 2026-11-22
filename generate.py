"""Generates the SVG panels used in the profile README.

Run locally:  python generate.py
In CI it runs daily (see .github/workflows/update-readme.yml) so the stats stay live.
Only uses the Python standard library.
"""

import json
import math
import os
import random
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ----------------------------------------------------------------------------- config
USER = "erihhh6"
NAME = "Oprea Eric"
TITLE = "Computer Engineering Student"
EXTRA_TECH = ["CUDA", "Flask", "Arduino"]  # tools that don't show up as repo languages
MAX_LANGS = 4

PINNED = [
    {"repo": "crypto-auction", "tags": ["zk-proofs", "sha256", "flask"]},
    {"repo": "crypto-visualizer", "tags": ["aes", "ecdh", "customtkinter"]},
    {"repo": "zk-gpu-accelerator", "tags": ["cuda", "ntt", "msm", "groth16"]},
]

OUT = Path(__file__).parent / "assets"

# ----------------------------------------------------------------------------- theme
MONO = "'JetBrains Mono','Fira Code','Cascadia Code',Consolas,'DejaVu Sans Mono',monospace"
ACCENT = "#ededed"   # near-white accents
GRAY = "#8a8a8a"
TEXT = "#f5f5f5"
MUTED = "#a3a3a3"
DIM = "#5f5f5f"
IGNORED_LANGS = {"CMake", "Shell", "Makefile", "Dockerfile"}


# ----------------------------------------------------------------------------- data
def http(url, data=None, headers=None):
    h = {"User-Agent": "profile-readme-generator", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and "api.github.com" in url:
        h["Authorization"] = f"Bearer {token}"
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def api(path):
    return json.loads(http(f"https://api.github.com{path}"))


def contributions_last_year():
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        try:
            q = {"query": 'query{user(login:"%s"){contributionsCollection{contributionCalendar{totalContributions}}}}' % USER}
            res = json.loads(http("https://api.github.com/graphql", json.dumps(q).encode()))
            return res["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
        except Exception as e:  # fall back to the public calendar page
            print("graphql failed, scraping calendar:", e)
    page = http(f"https://github.com/users/{USER}/contributions")
    return sum(int(n) for n in re.findall(r"(\d+) contributions? on", page))


def fetch():
    user = api(f"/users/{USER}")
    repos = [r for r in api(f"/users/{USER}/repos?per_page=100") if not r["fork"]]
    lang_bytes, repo_langs = {}, {}
    for r in repos:
        langs = api(f"/repos/{USER}/{r['name']}/languages")
        repo_langs[r["name"]] = langs
        for k, v in langs.items():
            lang_bytes[k] = lang_bytes.get(k, 0) + v
    top_langs = [k for k, _ in sorted(lang_bytes.items(), key=lambda kv: -kv[1]) if k not in IGNORED_LANGS]
    return {
        "repos": user["public_repos"],
        "followers": user["followers"],
        "stars": sum(r["stargazers_count"] for r in repos),
        "contributions": contributions_last_year(),
        "langs": top_langs[:MAX_LANGS],
        "repo_info": {r["name"]: r for r in repos},
        "repo_langs": repo_langs,
    }


# ----------------------------------------------------------------------------- helpers
def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def text_w(s, size):
    return len(s) * size * 0.6  # monospace estimate


def chip(x, y, label, dot=None, size=11.5, h=24):
    w = text_w(label, size) + (30 if dot else 20)
    out = [f'<rect x="{x}" y="{y}" width="{w:.1f}" height="{h}" rx="{h/2}" fill="#ffffff" fill-opacity=".06" stroke="#ffffff" stroke-opacity=".16"/>']
    tx = x + 10
    if dot:
        out.append(f'<circle cx="{x+12}" cy="{y+h/2}" r="4" fill="{dot}"/>')
        tx = x + 21
    out.append(f'<text x="{tx}" y="{y+h/2+4}" font-size="{size}" fill="#e5e5e5">{esc(label)}</text>')
    return "".join(out), w


def flow_chips(x0, y0, items, max_w, gap=8, row_h=32, max_rows=2, size=11.5):
    out, x, y, rows = [], x0, y0, 1
    for label, dot in items:
        w = text_w(label, size) + (30 if dot else 20)
        if x + w > x0 + max_w and x > x0:
            rows += 1
            if rows > max_rows:
                break
            x, y = x0, y + row_h
        svg, w = chip(x, y, label, dot, size)
        out.append(svg)
        x += w + gap
    return "".join(out)


def ago(iso):
    d = datetime.now(timezone.utc) - datetime.fromisoformat(iso.replace("Z", "+00:00"))
    s = d.total_seconds()
    if s < 3600:
        return "just now"
    if s < 86400:
        return f"{int(s // 3600)}h ago"
    if s < 86400 * 30:
        return f"{int(s // 86400)}d ago"
    if s < 86400 * 365:
        return f"{int(s // (86400 * 30))}mo ago"
    return f"{int(s // (86400 * 365))}y ago"


def wrap(s, width, max_lines):
    words, lines, cur = s.split(), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) <= width:
            cur = f"{cur} {w}" if cur else w
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: width - 1].rstrip() + "…"
    return lines


ICONS = {
    "repo": '<path d="M3 2.5h9.5v11H4.2A1.2 1.2 0 0 1 3 12.3z M3 12.3a1.2 1.2 0 0 1 1.2-1.2h8.3"/>',
    "star": '<polygon points="8,1.6 10,6 14.6,6.4 11.1,9.4 12.2,14 8,11.5 3.8,14 4.9,9.4 1.4,6.4 6,6"/>',
    "pulse": '<polyline points="1,8.5 4,8.5 6,3.5 9,13 11,6.5 12.6,8.5 15,8.5"/>',
    "user": '<circle cx="8" cy="5.2" r="2.9"/><path d="M2.6 14.4c.8-3 3-4.6 5.4-4.6s4.6 1.6 5.4 4.6"/>',
    "clock": '<circle cx="8" cy="8" r="6.2"/><path d="M8 4.6V8l2.4 1.6"/>',
}


def icon(name, x, y, scale=1.15, color=ACCENT):
    return (f'<g transform="translate({x},{y}) scale({scale})" fill="none" stroke="{color}" '
            f'stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</g>')


def defs_common():
    return f"""
  <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#ffffff"/><stop offset=".6" stop-color="#cfcfcf"/><stop offset="1" stop-color="#7a7a7a"/>
  </linearGradient>
  <linearGradient id="icy" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#eef4ff" stop-opacity=".16"/>
    <stop offset=".5" stop-color="#ffffff" stop-opacity=".07"/>
    <stop offset="1" stop-color="#dfe8f5" stop-opacity=".045"/>
  </linearGradient>
  <linearGradient id="sheen" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#ffffff" stop-opacity=".10"/><stop offset=".35" stop-color="#ffffff" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="scan" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#ffffff" stop-opacity="0"/><stop offset=".9" stop-color="#ffffff" stop-opacity=".045"/>
    <stop offset="1" stop-color="#ffffff" stop-opacity=".22"/>
  </linearGradient>
  <filter id="frost" x="-5%" y="-5%" width="110%" height="110%"><feGaussianBlur stdDeviation="1.6"/></filter>
  <filter id="grain" x="0" y="0" width="100%" height="100%">
    <feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="3" stitchTiles="stitch"/>
    <feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .075 0"/>
  </filter>
  <filter id="neon" x="-20%" y="-60%" width="140%" height="220%">
    <feGaussianBlur in="SourceAlpha" stdDeviation="7" result="b1"/>
    <feFlood flood-color="#ffffff" flood-opacity=".55"/><feComposite in2="b1" operator="in" result="g1"/>
    <feGaussianBlur in="SourceAlpha" stdDeviation="2" result="b2"/>
    <feFlood flood-color="#ffffff" flood-opacity=".9"/><feComposite in2="b2" operator="in" result="g2"/>
    <feMerge><feMergeNode in="g1"/><feMergeNode in="g2"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>"""


BASE_CSS = """
  text{font-family:%s}
  .cursor{animation:blink 1.1s step-end infinite}
  @keyframes blink{50%%{opacity:0}}
  .flick{animation:flick 3.2s steps(2) infinite}
  @keyframes flick{50%%{opacity:.35}}
""" % MONO


# ----------------------------------------------------------------------------- background + glass
def ascii_rain(x0, y0, w, h, seed=6, op_scale=1.0):
    rnd = random.Random(seed)
    chars = "01{}<>#$%&*/\\=+~"
    out = []
    for gy in range(int(y0) + 16, int(y0 + h) - 2, 16):
        for gx in range(int(x0) + 8, int(x0 + w) - 6, 13):
            if rnd.random() < 0.55:
                ch = rnd.choice(chars)
                op = rnd.choice([0.07, 0.11, 0.17]) * op_scale
                cls = ' class="flick"' if rnd.random() < 0.18 else ""
                delay = f' style="animation-delay:{rnd.random()*3:.2f}s"' if cls else ""
                out.append(f'<text x="{gx}" y="{gy}" font-size="11" fill="#d4d4d4" opacity="{op:.3f}"{cls}{delay}>{esc(ch)}</text>')
    return "".join(out)


def glass(W, H, rx, seed=0, frosted=True, scan=False, op_scale=1.0, rain=True):
    """Icy frosted-glass card: dark base, (blurred) ASCII rain, milky tint, grain, sheen, white rim."""
    rain = ascii_rain(0, 0, W, H, seed, op_scale) if rain else ""
    if rain and frosted:
        rain = f'<g filter="url(#frost)">{rain}</g>'
    scan_svg = ""
    if scan:
        scan_svg = (f'<rect x="0" y="-60" width="{W}" height="60" fill="url(#scan)">'
                    f'<animate attributeName="y" from="-60" to="{H}" dur="5s" repeatCount="indefinite"/></rect>')
    return f"""<clipPath id="card"><rect x="1" y="1" width="{W-2}" height="{H-2}" rx="{rx}"/></clipPath>
<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="{rx}" fill="#060606"/>
<g clip-path="url(#card)">
  {rain}
  <rect width="{W}" height="{H}" fill="url(#icy)"/>
  <rect width="{W}" height="{H}" filter="url(#grain)"/>
  <rect width="{W}" height="{H}" fill="url(#sheen)"/>
  {scan_svg}
</g>
<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="{rx}" fill="none" stroke="#ffffff" stroke-opacity=".17" stroke-width="1.2"/>
<path d="M{rx+2},1.6 H{W-rx-2}" stroke="#ffffff" stroke-opacity=".45" stroke-width="1"/>"""


# ----------------------------------------------------------------------------- eye icon
# "eye" (pixelarticons 2.4.2) and "eye-closed" (pixelarticons 1.8.1) from Pixelarticons,
# https://github.com/halfmage/pixelarticons -- MIT License, Copyright (c) 2019 Gerrit Halfmann.
# Full license text: THIRD_PARTY_NOTICES.md
EYE_OPEN = ("M16 20H8v-2h8v2Zm-8-2H4v-2h4v2Zm12 0h-4v-2h4v2ZM4 16H2v-2h2v2Zm10-6h-2v2h2v-2h2v4h-2v2h-4v-2H8v-4h2V8h4v2Zm8 6h-2v-2h2v2Z"
            "M2 14H0v-4h2v4Zm22 0h-2v-4h2v4ZM4 10H2V8h2v2Zm18 0h-2V8h2v2ZM8 8H4V6h4v2Zm12 0h-4V6h4v2Zm-4-2H8V4h8v2Z")
EYE_CLOSED = ("M0 7h2v2H0V7zm4 4H2V9h2v2zm4 2v-2H4v2H2v2h2v-2h4zm8 0H8v2H6v2h2v-2h8v2h2v-2h-2v-2zm4-2h-4v2h4v2h2v-2h-2v-2z"
              "m2-2v2h-2V9h2zm0 0V7h2v2h-2z")
EYE_SCALE = 7  # 24px icon -> 168px


def eye_icon(cx, cy):
    """White Pixelarticons eye with neon glow; it blinks by swapping to the closed-eye icon."""
    tf = f"translate({cx - 12 * EYE_SCALE},{cy - 12 * EYE_SCALE}) scale({EYE_SCALE})"
    return (f'<!-- eye icon: Pixelarticons (MIT, (c) 2019 Gerrit Halfmann) -->'
            f'<g filter="url(#neon)" fill="#ffffff" shape-rendering="crispEdges">'
            f'<g class="eye-open" transform="{tf}"><path d="{EYE_OPEN}"/></g>'
            f'<g class="eye-closed" transform="{tf}"><path d="{EYE_CLOSED}"/></g>'
            f'</g>')


# ----------------------------------------------------------------------------- panels
def header_svg(d):
    W, H = 840, 330
    langs = [(l, ACCENT) for l in d["langs"]]
    tech = [(t, GRAY) for t in EXTRA_TECH]
    stats = [
        ("repo", d["repos"], "Repositories"),
        ("star", d["stars"], "Stars"),
        ("pulse", d["contributions"], "Contributions"),
        ("user", d["followers"], "Followers"),
    ]
    stat_svg = []
    for i, (ic, val, label) in enumerate(stats):
        y = 112 + i * 46
        stat_svg.append(
            f'<g>{icon(ic, 410, y - 14, color=MUTED)}'
            f'<text x="440" y="{y}" font-size="15" fill="{TEXT}"><tspan font-weight="700">{val}</tspan>'
            f'<tspan fill="{MUTED}"> {label}</tspan></text></g>')

    ecx, ecy = 716, H // 2  # eye centre: right of the stats, same gap to the top and bottom edge

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>{defs_common()}
  <radialGradient id="eyeglow"><stop offset="0" stop-color="#ffffff" stop-opacity=".13"/><stop offset="1" stop-color="#ffffff" stop-opacity="0"/></radialGradient>
</defs>
<style>{BASE_CSS}
  .neon{{animation:neon 6s infinite}}
  @keyframes neon{{0%,100%{{opacity:1}}61%{{opacity:1}}62%{{opacity:.55}}63%{{opacity:1}}66%{{opacity:.7}}67%{{opacity:1}}}}
  .eye-open{{animation:eye-open 5s infinite}}
  .eye-closed{{opacity:0;animation:eye-closed 5s infinite}}
  @keyframes eye-open{{0%,91.9%{{opacity:1}}92%,95.9%{{opacity:0}}96%,100%{{opacity:1}}}}
  @keyframes eye-closed{{0%,91.9%{{opacity:0}}92%,95.9%{{opacity:1}}96%,100%{{opacity:0}}}}
</style>
{glass(W, H, 16, seed=6, frosted=False, scan=True, op_scale=1.15)}

<circle cx="24" cy="21" r="5.5" fill="#e5e5e5"/><circle cx="42" cy="21" r="5.5" fill="#8a8a8a"/><circle cx="60" cy="21" r="5.5" fill="#5c5c5c"/>
<text x="82" y="25" font-size="12" fill="{MUTED}">~/{USER}/README.md</text>
<line x1="1" y1="40" x2="{W-1}" y2="40" stroke="#ffffff" stroke-opacity=".1"/>

<text x="36" y="86" font-size="15" fill="{MUTED}">@{USER}</text>
<text class="neon" x="34" y="142" font-size="42" font-weight="800" fill="#ffffff" filter="url(#neon)">{esc(NAME)}</text>
<text x="36" y="178" font-size="15" fill="{MUTED}"><tspan fill="{TEXT}">&gt;</tspan> {esc(TITLE)}<tspan class="cursor" fill="{TEXT}"> ▌</tspan></text>
{flow_chips(36, 206, langs + tech, max_w=340, max_rows=2)}

<line x1="388" y1="76" x2="388" y2="276" stroke="#ffffff" stroke-opacity=".12" stroke-dasharray="3 5"/>
{"".join(stat_svg)}

<ellipse cx="{ecx}" cy="{ecy}" rx="130" ry="100" fill="url(#eyeglow)"/>
{eye_icon(ecx, ecy)}
</svg>"""


def projects_header_svg():
    W, H = 840, 58
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>{defs_common()}</defs>
<style>{BASE_CSS}</style>
{glass(W, H, 14, rain=False)}
<text x="28" y="36" font-size="19" font-weight="800" fill="{TEXT}">Projects<tspan fill="{GRAY}">.list</tspan></text>
<text x="{W-28}" y="35" font-size="13" fill="{MUTED}" text-anchor="end">&gt; ./projects.sh --pinned<tspan class="cursor">▌</tspan></text>
</svg>"""


# The three cards sit side by side and together span the same 840px as the header cards.
# Each card SVG carries its share of the gap as transparent padding, so the outer edges line up.
CARD_W, CARD_GAP = 272, 12            # 3 * 272 + 2 * 12 = 840


def card_svg(cfg, d, pad_l=0, pad_r=0):
    W, H = CARD_W, 250
    info = d["repo_info"][cfg["repo"]]
    langs = d["repo_langs"].get(cfg["repo"], {})
    total = sum(langs.values()) or 1
    main_lang = max(langs, key=langs.get) if langs else "—"
    pct = round(100 * langs.get(main_lang, 0) / total)
    desc = cfg.get("description") or info.get("description") or ""
    tags = cfg.get("tags") or [t for t in info.get("topics", []) if t != "portfolio"][:3]

    r = 21
    circ = 2 * math.pi * r
    off = circ * (1 - pct / 100)
    lines = wrap(desc, 31, 4)
    desc_svg = "".join(
        f'<text x="18" y="{96 + i*18}" font-size="12" fill="#c4c4c4">{esc(l)}</text>' for i, l in enumerate(lines))
    tag_items = [(t, None) for t in tags]

    TW = W + pad_l + pad_r
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{TW}" height="{H}" viewBox="0 0 {TW} {H}">
<defs>{defs_common()}</defs>
<style>{BASE_CSS}</style>
<g transform="translate({pad_l},0)">
{glass(W, H, 14, rain=False)}

{icon("repo", 18, 22, 1.1, MUTED)}
<text x="40" y="35" font-size="14" font-weight="700" fill="{TEXT}">{esc(cfg["repo"])}</text>
<circle cx="45" cy="55" r="4" fill="{ACCENT}"/>
<text x="54" y="59" font-size="11" fill="{MUTED}">{esc(main_lang)}</text>

<g transform="rotate(-90 {W-38} 44)">
  <circle cx="{W-38}" cy="44" r="{r}" fill="none" stroke="#ffffff" stroke-opacity=".1" stroke-width="5"/>
  <circle cx="{W-38}" cy="44" r="{r}" fill="none" stroke="url(#accent)" stroke-width="5"
    stroke-linecap="round" stroke-dasharray="{circ:.2f}" stroke-dashoffset="{off:.2f}"/>
</g>
<text x="{W-38}" y="48" font-size="11" font-weight="700" fill="{TEXT}" text-anchor="middle">{pct}%</text>

{desc_svg}
{flow_chips(18, 172, tag_items, max_w=236, gap=6, row_h=28, max_rows=1, size=10.5)}

<line x1="18" y1="212" x2="{W-18}" y2="212" stroke="#ffffff" stroke-opacity=".12"/>
{icon("star", 18, 222, 0.95, MUTED)}
<text x="38" y="234" font-size="11.5" fill="{MUTED}">{info["stargazers_count"]}</text>
{icon("clock", 78, 222, 0.95, MUTED)}
<text x="98" y="234" font-size="11.5" fill="{MUTED}">updated {ago(info["pushed_at"])}</text>
</g>
</svg>"""


# ----------------------------------------------------------------------------- main
def main():
    d = fetch()
    OUT.mkdir(exist_ok=True)
    (OUT / "header.svg").write_text(header_svg(d), encoding="utf-8")
    (OUT / "projects-header.svg").write_text(projects_header_svg(), encoding="utf-8")
    half = CARD_GAP // 2
    for i, cfg in enumerate(PINNED):
        pad_l = 0 if i == 0 else half
        pad_r = 0 if i == len(PINNED) - 1 else half
        (OUT / f"card-{cfg['repo']}.svg").write_text(card_svg(cfg, d, pad_l, pad_r), encoding="utf-8")
    print("stats:", {k: d[k] for k in ("repos", "stars", "contributions", "followers", "langs")})


if __name__ == "__main__":
    main()
