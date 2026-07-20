# Visualizations

A collection of fullscreen, self-contained HTML visualizations for use as ambient backgrounds or screensavers.

## Run locally

The Python server keeps the convenient development routes:

```sh
python3 serve.py
```

- `/` — a random visualization
- `/scenic` — a random visualization from a category
- `/silly/the-matrix` — a specific visualization
- `/?list` or `/scenic?list` — browse the catalog

## Build the static site

GitHub Pages cannot choose a random file on the server, so the generated indexes do that in the browser while keeping the same root, category, and `?list` behavior.

```sh
python3 build_site.py
python3 -m http.server --directory _site
```

The build copies the visualization categories into `_site`, creates a root index and one index per category, and adds `.nojekyll`. The Pages workflow runs this build and deploys only `_site` whenever `main` changes.

To add a visualization, put an HTML file in a category directory. Its `<title>` is used in the generated catalog; the filename is used as a fallback.
