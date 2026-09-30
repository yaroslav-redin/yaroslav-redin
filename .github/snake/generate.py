#!/usr/bin/env python3
"""
Генератор анимированной змейки по графику контрибьюций GitHub.
Змейка обходит сетку «змейкой» (сверху вниз, снизу вверх), съедает
закрашенные клетки и растёт на один сегмент за каждую съеденную клетку.

Переменные окружения:
  GH_USER          — логин GitHub (обязательно, если не DEMO)
  GITHUB_TOKEN     — токен для GraphQL API (в Actions берётся автоматически)
  OUT_DIR          — куда сохранять SVG (по умолчанию dist)
  SNAKE_INIT_LEN   — начальная длина змейки (по умолчанию 3)
  SNAKE_MAX_LEN    — максимальная длина (по умолчанию 40)
  SNAKE_STEP       — время на одну клетку в секундах (по умолчанию 0.07)
  DEMO=1           — сгенерировать на случайных данных без запроса к API
"""
import json
import os
import random
import sys
import urllib.request

USER = os.environ.get("GH_USER", "")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT_DIR = os.environ.get("OUT_DIR", "dist")
INIT_LEN = int(os.environ.get("SNAKE_INIT_LEN", 3))
MAX_LEN = max(INIT_LEN, int(os.environ.get("SNAKE_MAX_LEN", 40)))
STEP = float(os.environ.get("SNAKE_STEP", 0.07))

CELL, PITCH, MARGIN = 11, 14, 2
EPS = 0.0001

THEMES = {
    "github-snake.svg": {
        "empty": "#ebedf0",
        "levels": ["#ddd6fe", "#c4b5fd", "#a78bfa", "#7c3aed"],
        "head": "#4c1d95",
        "tail": "#a78bfa",
    },
    "github-snake-dark.svg": {
        "empty": "#161b22",
        "levels": ["#3b2a6b", "#5b3fb0", "#7c3aed", "#a78bfa"],
        "head": "#f3e8ff",
        "tail": "#9333ea",
    },
}

LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
          "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}

QUERY = """query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks { contributionDays { weekday contributionLevel } }
      }
    }
  }
}"""


def fetch_grid():
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=body,
        headers={"Authorization": f"bearer {TOKEN}",
                 "Content-Type": "application/json",
                 "User-Agent": "growing-snake"})
    data = json.load(urllib.request.urlopen(req))
    if data.get("errors"):
        sys.exit(f"GraphQL error: {data['errors']}")
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    grid = {}
    for x, week in enumerate(weeks):
        for day in week["contributionDays"]:
            grid[(x, day["weekday"])] = LEVELS[day["contributionLevel"]]
    return grid, len(weeks)


def demo_grid(width=53):
    rnd = random.Random(42)
    grid = {(x, y): rnd.choice([0, 0, 0, 1, 1, 2, 3, 4])
            for x in range(width) for y in range(7)}
    return grid, width


def build_path(width):
    """Вход слева за экраном → обход колонок зигзагом → выход справа."""
    pad = MAX_LEN + 1
    path = [(-i, 0) for i in range(pad, 0, -1)]
    for x in range(width):
        rows = range(7) if x % 2 == 0 else range(6, -1, -1)
        path += [(x, y) for y in rows]
    last_y = path[-1][1]
    path += [(width - 1 + i, last_y) for i in range(1, pad + 1)]
    return path


def px(v):
    return MARGIN + v * PITCH


def pct(i, n):
    return f"{min(100.0, i / n * 100):.4f}".rstrip("0").rstrip(".")


def lerp_color(a, b, t):
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def render(grid, width, theme):
    path = build_path(width)
    n = len(path) - 1                      # число шагов за цикл
    dur = n * STEP

    eats = [i for i, cell in enumerate(path) if grid.get(cell, 0) > 0]
    seg_count = min(MAX_LEN, INIT_LEN + len(eats))

    w = MARGIN * 2 + width * PITCH - (PITCH - CELL)
    h = MARGIN * 2 + 7 * PITCH - (PITCH - CELL)
    css, body = [], []

    # --- движение головы: ключевые кадры только в точках поворота ---
    corners = [0]
    for i in range(1, n):
        d1 = (path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1])
        d2 = (path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1])
        if d1 != d2:
            corners.append(i)
    corners.append(n)
    frames = "".join(
        f"{pct(i, n)}%{{transform:translate({px(path[i][0])}px,{px(path[i][1])}px)}}"
        for i in corners)
    css.append(f"@keyframes mv{{{frames}}}")
    css.append(f".m{{animation:mv {dur:.3f}s linear infinite both}}")

    # --- клетки графика ---
    eat_at = {path[i]: i for i in eats}
    for (x, y), lvl in sorted(grid.items()):
        body.append(f'<rect x="{px(x)}" y="{px(y)}" width="{CELL}" height="{CELL}" '
                    f'rx="2" fill="{theme["empty"]}"/>')
        if lvl > 0:
            i = eat_at[(x, y)]
            css.append(f"@keyframes d{x}_{y}{{0%,{pct(i, n)}%{{opacity:1}}"
                       f"{float(pct(i, n)) + EPS:.4f}%,100%{{opacity:0}}}}")
            body.append(f'<rect x="{px(x)}" y="{px(y)}" width="{CELL}" height="{CELL}" '
                        f'rx="2" fill="{theme["levels"][lvl - 1]}" '
                        f'style="animation:d{x}_{y} {dur:.3f}s linear infinite"/>')

    # --- сегменты змейки (от хвоста к голове, чтобы голова была сверху) ---
    for k in range(seg_count - 1, -1, -1):
        t = k / max(1, seg_count - 1)
        size = CELL - round(4 * t)         # хвост слегка сужается
        off = (CELL - size) / 2
        color = lerp_color(theme["head"], theme["tail"], t)
        rect = (f'<rect class="m" x="{off}" y="{off}" width="{size}" height="{size}" '
                f'rx="{3 if k else 4}" fill="{color}" '
                f'style="animation-delay:{k * STEP:.3f}s"/>')
        if k < INIT_LEN:
            body.append(rect)
        else:
            appear = eats[k - INIT_LEN]    # сегмент появляется при поедании клетки
            css.append(f"@keyframes g{k}{{0%,{pct(appear, n)}%{{opacity:0}}"
                       f"{float(pct(appear, n)) + EPS:.4f}%,100%{{opacity:1}}}}")
            body.append(f'<g style="animation:g{k} {dur:.3f}s linear infinite">{rect}</g>')

    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="{w}" height="{h}"><style>{"".join(css)}</style>'
            f'{"".join(body)}</svg>')


def main():
    if os.environ.get("DEMO"):
        grid, width = demo_grid()
    else:
        if not USER or not TOKEN:
            sys.exit("Нужны переменные GH_USER и GITHUB_TOKEN")
        grid, width = fetch_grid()
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, theme in THEMES.items():
        with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as f:
            f.write(render(grid, width, theme))
        print(f"✓ {name}")


if __name__ == "__main__":
    main()
