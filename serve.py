#!/usr/bin/env python3
import argparse
import html
import os
import random
import urllib.parse
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

def _is_safe_segment(seg: str) -> bool:
    """Check if a single path segment is safe (no traversal tricks)."""
    if not seg:
        return False
    if seg in (".", ".."):
        return False
    if "\\" in seg or "\x00" in seg:
        return False
    if seg.startswith(("/", "~")):
        return False
    return True


def parse_url(url_path: str) -> tuple[list[str], dict[str, str]]:
    """
    Parse a URL path into sanitized segments and query parameters.
    Returns (segments, query_dict).
    segments is a list of safe path parts, e.g. "/silly/forest" -> ["silly", "forest"]
    Returns (["__INVALID__"], {}) if any segment fails validation.
    """
    parsed = urllib.parse.urlparse(url_path)
    path = urllib.parse.unquote(parsed.path)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))

    # Also accept bare "?list" (no value) which parse_qsl misses
    if "list" not in query and "?list" in url_path:
        query["list"] = ""

    if path == "/":
        return [], query

    raw_segments = [s for s in path.strip("/").split("/") if s]
    if not raw_segments:
        return [], query

    for seg in raw_segments:
        if not _is_safe_segment(seg):
            return ["__INVALID__"], query

    return raw_segments, query


def list_html_files(base_dir: Path, only_dir: str | None) -> list[Path]:
    """
    Return a list of *.html files under base_dir.
    If only_dir is provided, only search under base_dir/only_dir.
    """
    root = base_dir if only_dir is None else (base_dir / only_dir)

    if not root.exists() or not root.is_dir():
        return []

    # Find *.html files recursively
    files: list[Path] = []
    for p in root.rglob("*.html"):
        if p.is_file():
            # Ensure it resolves inside base_dir
            try:
                rp = p.resolve(strict=True)
                rb = base_dir.resolve(strict=True)
                rp.relative_to(rb)
                files.append(rp)
            except Exception:
                # If it doesn't resolve or escapes base_dir, skip
                continue
    return files


def try_serve_exact(base_dir: Path, segments: list[str]) -> Path | None:
    """
    Try to resolve segments as an exact HTML file path.
    E.g. ["silly", "forest"] -> base_dir/silly/forest.html
    Returns the resolved Path if it exists and is safe, or None.
    """
    if len(segments) < 2:
        return None

    # Build relative path, auto-append .html
    rel = "/".join(segments)
    if not rel.endswith(".html"):
        rel += ".html"

    candidate = base_dir / rel

    # Resolve and ensure it stays within base_dir
    try:
        resolved = candidate.resolve(strict=True)
        resolved_base = base_dir.resolve(strict=True)
        resolved.relative_to(resolved_base)
    except Exception:
        return None

    if resolved.is_file() and resolved.suffix == ".html":
        return resolved

    return None


class RandomHTMLHandler(BaseHTTPRequestHandler):
    server_version = "RandomHTML/0.2"

    def do_GET(self):
        base_dir: Path = self.server.base_dir  # type: ignore[attr-defined]
        segments, query = parse_url(self.path)

        if segments == ["__INVALID__"]:
            self.send_error(400, "Invalid path")
            return

        # --- Mode 1: ?list --- show a clickable directory listing
        if "list" in query:
            only_dir = segments[0] if len(segments) == 1 else None
            self._serve_listing(base_dir, only_dir)
            return

        # --- Mode 2: exact file path (2+ segments, e.g. /silly/forest) ---
        if len(segments) >= 2:
            exact = try_serve_exact(base_dir, segments)
            if exact:
                self._serve_file(exact)
            else:
                self.send_error(404, "File not found")
            return

        # --- Mode 3: random (root or single directory segment) ---
        only_dir = segments[0] if len(segments) == 1 else None
        candidates = list_html_files(base_dir, only_dir)

        if not candidates:
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            msg = "No HTML files found"
            if only_dir:
                msg += f" in directory {html.escape(only_dir)}"
            self.wfile.write(f"<h1>{msg}</h1>".encode("utf-8"))
            return

        chosen = random.choice(candidates)
        self._serve_file(chosen)

    def _serve_file(self, path: Path):
        try:
            data = path.read_bytes()
        except OSError:
            self.send_error(500, "Failed to read file")
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_listing(self, base_dir: Path, only_dir: str | None):
        files = list_html_files(base_dir, only_dir)
        resolved_base = base_dir.resolve(strict=True)

        # Group files by directory
        groups: dict[str, list[tuple[str, str]]] = {}
        for f in sorted(files):
            try:
                rel = f.relative_to(resolved_base)
            except ValueError:
                continue
            parts = rel.parts
            if len(parts) < 2:
                continue
            directory = parts[0]
            name = rel.with_suffix("").as_posix()  # e.g. "silly/forest"
            display = parts[-1].removesuffix(".html")
            groups.setdefault(directory, []).append((name, display))

        # Build HTML
        title = f"Visualizations — {html.escape(only_dir)}" if only_dir else "Visualizations"
        lines = [
            "<!doctype html>",
            '<html lang="en"><head><meta charset="utf-8"/>',
            f"<title>{title}</title>",
            "<style>",
            "  body { font-family: system-ui, sans-serif; background: #0a0a12; color: #e0e0e8;",
            "         max-width: 720px; margin: 40px auto; padding: 0 20px; }",
            "  h1 { font-size: 22px; font-weight: 700; margin-bottom: 8px; }",
            "  h2 { font-size: 16px; font-weight: 600; color: #8090b0; margin: 28px 0 8px; }",
            "  ul { list-style: none; padding: 0; }",
            "  li { margin: 4px 0; }",
            "  a { color: #7ab8ff; text-decoration: none; padding: 6px 10px; display: inline-block;",
            "      border-radius: 8px; transition: background .15s; }",
            "  a:hover { background: rgba(122,184,255,.12); }",
            "  .hint { font-size: 13px; color: #667; margin-top: 4px; }",
            "</style>",
            "</head><body>",
            f"<h1>{title}</h1>",
            '<p class="hint">Click a name to view it directly, or visit a directory path for a random pick.</p>',
        ]

        for directory in sorted(groups):
            lines.append(f"<h2>{html.escape(directory)}/</h2><ul>")
            for name, display in sorted(groups[directory], key=lambda x: x[1]):
                safe_name = html.escape(name)
                safe_display = html.escape(display)
                lines.append(f'  <li><a href="/{safe_name}">{safe_display}</a></li>')
            lines.append("</ul>")

        lines.append("</body></html>")

        data = "\n".join(lines).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        # Keep logs concise
        print("%s - %s" % (self.address_string(), fmt % args))


def main():
    parser = argparse.ArgumentParser(description="Serve a random HTML file from directories.")
    parser.add_argument("--base", default=".", help="Base directory containing subdirectories (default: .)")
    parser.add_argument("--host", default="0.0.0.0", help="Host/interface to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    args = parser.parse_args()

    base_dir = Path(args.base).resolve()
    if not base_dir.is_dir():
        raise SystemExit(f"Base path is not a directory: {base_dir}")

    httpd = ThreadingHTTPServer((args.host, args.port), RandomHTMLHandler)
    httpd.base_dir = base_dir  # attach for handler access

    print(f"Serving random HTML from: {base_dir}")
    print(f"  Random from all:    http://{args.host}:{args.port}/")
    print(f"  Random from dir:    http://{args.host}:{args.port}/christmas")
    print(f"  Exact file:         http://{args.host}:{args.port}/silly/forest")
    print(f"  List all:           http://{args.host}:{args.port}/?list")
    print(f"  List dir:           http://{args.host}:{args.port}/silly?list")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()

