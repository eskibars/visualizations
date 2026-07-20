#!/usr/bin/env python3
"""Build a static version of the visualization server for GitHub Pages."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path


TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class Visualization:
    category: str
    path: Path
    relative_path: Path
    title: str


def display_name(value: str) -> str:
    return value.replace("-", " ").replace("_", " ").title()


def page_title(path: Path) -> str:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return display_name(path.stem)

    match = TITLE_RE.search(source)
    if not match:
        return display_name(path.stem)

    title = html.unescape(re.sub(r"\s+", " ", match.group(1))).strip()
    return title or display_name(path.stem)


def discover(source: Path, output: Path) -> list[Visualization]:
    visualizations: list[Visualization] = []

    for category_dir in sorted(source.iterdir()):
        if (
            not category_dir.is_dir()
            or category_dir.name.startswith(".")
            or category_dir.resolve() == output
        ):
            continue

        for path in sorted(category_dir.rglob("*.html")):
            if path.name == "index.html" or any(part.startswith(".") for part in path.parts):
                continue
            relative_path = path.relative_to(source)
            visualizations.append(
                Visualization(category_dir.name, path, relative_path, page_title(path))
            )

    return visualizations


def render_index(
    title: str,
    visualizations: list[Visualization],
    *,
    path_prefix: str,
    home_path: str | None,
) -> str:
    items = [
        {
            "category": item.category,
            "categoryLabel": display_name(item.category),
            "title": item.title,
            "url": f"{path_prefix}{item.relative_path.as_posix()}",
        }
        for item in visualizations
    ]
    catalog = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    home_link = f'<a class="home" href="{home_path}?list">All categories</a>' if home_path else ""

    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <title>{html.escape(title)}</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; min-height: 100vh; color: #eef1ff; background: #070912;
      background-image: radial-gradient(circle at 15% 0%, #1c2852 0, transparent 35rem),
                        radial-gradient(circle at 90% 100%, #31194c 0, transparent 32rem); }}
    main {{ width: min(70rem, calc(100% - 2rem)); margin: 0 auto; padding: 4rem 0 6rem; }}
    header {{ display: flex; justify-content: space-between; gap: 2rem; align-items: end;
      border-bottom: 1px solid #ffffff20; padding-bottom: 2rem; }}
    .eyebrow {{ color: #98a8ff; font-size: .75rem; font-weight: 750; letter-spacing: .14em;
      text-transform: uppercase; }}
    h1 {{ margin: .35rem 0 0; font-size: clamp(2.3rem, 7vw, 5.8rem); line-height: .95;
      letter-spacing: -.065em; }}
    .actions {{ display: flex; align-items: center; gap: .8rem; flex-wrap: wrap; }}
    button, .home {{ border: 1px solid #ffffff24; border-radius: 999px; padding: .8rem 1.1rem;
      color: #f7f8ff; background: #ffffff0d; font: inherit; font-weight: 650; text-decoration: none;
      cursor: pointer; }}
    button:hover, button:focus-visible, .home:hover, .home:focus-visible {{ background: #ffffff1c;
      outline: 2px solid #aab5ff; outline-offset: 3px; }}
    #catalog {{ margin-top: 2.5rem; }}
    section {{ margin-top: 2.8rem; }}
    h2 {{ color: #aab5d8; font-size: .8rem; letter-spacing: .13em; text-transform: uppercase; }}
    ul {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr)); gap: .75rem;
      margin: 1rem 0 0; padding: 0; list-style: none; }}
    .card {{ display: block; min-height: 6.5rem; padding: 1.15rem; color: inherit; text-decoration: none;
      border: 1px solid #ffffff1a; border-radius: 1rem; background: #ffffff0a;
      transition: transform .15s ease, border-color .15s ease, background .15s ease; }}
    .card:hover, .card:focus-visible {{ transform: translateY(-2px); border-color: #9dacff88;
      background: #ffffff12; outline: none; }}
    .card strong {{ display: block; font-size: 1.05rem; }}
    .card span {{ display: block; margin-top: .5rem; color: #8d96b3; font-size: .8rem; }}
    .empty {{ color: #aab0c6; }}
    @media (max-width: 640px) {{ main {{ padding-top: 2.5rem; }} header {{ align-items: start;
      flex-direction: column; }} }}
    @media (prefers-reduced-motion: reduce) {{ .card {{ transition: none; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <div><div class="eyebrow">Ambient screens</div><h1>{html.escape(title)}</h1></div>
      <div class="actions">{home_link}<button id="random" type="button">Surprise me</button></div>
    </header>
    <div id="catalog"><p class="empty">Loading visualizations…</p></div>
  </main>
  <script>
    const visualizations = {catalog};
    const pick = () => {{
      if (!visualizations.length) return;
      const values = new Uint32Array(1);
      crypto.getRandomValues(values);
      location.replace(visualizations[values[0] % visualizations.length].url);
    }};

    document.querySelector('#random').addEventListener('click', pick);
    document.addEventListener('keydown', event => {{
      if (event.key.toLowerCase() === 'r' && !event.metaKey && !event.ctrlKey && !event.altKey) pick();
    }});

    if (!new URLSearchParams(location.search).has('list')) {{
      pick();
    }} else {{
      const groups = Object.groupBy
        ? Object.groupBy(visualizations, item => item.categoryLabel)
        : visualizations.reduce((all, item) => ((all[item.categoryLabel] ||= []).push(item), all), {{}});
      const catalog = document.querySelector('#catalog');
      catalog.replaceChildren();
      for (const [category, items] of Object.entries(groups)) {{
        const section = document.createElement('section');
        const heading = document.createElement('h2');
        const list = document.createElement('ul');
        heading.textContent = category;
        for (const item of items) {{
          const row = document.createElement('li');
          const link = document.createElement('a');
          const name = document.createElement('strong');
          const path = document.createElement('span');
          link.className = 'card';
          link.href = item.url;
          name.textContent = item.title;
          path.textContent = item.url.replace(/^\.\//, '');
          link.append(name, path);
          row.append(link);
          list.append(row);
        }}
        section.append(heading, list);
        catalog.append(section);
      }}
      if (!visualizations.length) catalog.innerHTML = '<p class="empty">No visualizations found.</p>';
    }}
  </script>
</body>
</html>
'''


def build(source: Path, output: Path) -> int:
    source = source.resolve()
    output = output.resolve()
    if output == source or output in source.parents:
        raise SystemExit("Output directory must be inside or separate from the source directory.")

    visualizations = discover(source, output)
    if not visualizations:
        raise SystemExit("No visualizations found.")

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    categories = sorted({item.category for item in visualizations})
    for category in categories:
        shutil.copytree(source / category, output / category)

    (output / "index.html").write_text(
        render_index("Visualizations", visualizations, path_prefix="./", home_path=None),
        encoding="utf-8",
    )

    for category in categories:
        category_items = [item for item in visualizations if item.category == category]
        (output / category / "index.html").write_text(
            render_index(
                display_name(category),
                category_items,
                path_prefix="../",
                home_path="../",
            ),
            encoding="utf-8",
        )

    (output / ".nojekyll").touch()
    return len(visualizations)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).parent)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "_site")
    args = parser.parse_args()
    count = build(args.source, args.output)
    print(f"Built {count} visualizations in {args.output.resolve()}")


if __name__ == "__main__":
    main()
