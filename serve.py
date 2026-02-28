#!/usr/bin/env python3
import argparse
import html
import os
import random
import urllib.parse
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

def safe_subdir_from_url_path(url_path: str) -> str | None:
    """
    Returns a sanitized single directory name, or None for "no directory".
    Accepts:
      - "/" -> None
      - "/christmas/" or "/christmas" -> "christmas"
    Rejects anything with path traversal or multiple segments.
    """
    path = urllib.parse.urlparse(url_path).path
    # Decode %xx and normalize
    path = urllib.parse.unquote(path)

    # Must be either "/" or "/name" or "/name/"
    if path == "/":
        return None

    # Strip leading/trailing slashes, then ensure it's a single segment
    seg = path.strip("/")
    if not seg:
        return None

    # Reject multiple segments like "/a/b/"
    if "/" in seg:
        return "__INVALID__"

    # Basic traversal / weird path checks
    if seg in (".", ".."):
        return "__INVALID__"
    if "\\" in seg:
        return "__INVALID__"
    if seg.startswith(("/", "~")):
        return "__INVALID__"

    # Extra hardening: disallow NUL and path separators
    if "\x00" in seg:
        return "__INVALID__"

    return seg


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


class RandomHTMLHandler(BaseHTTPRequestHandler):
    server_version = "RandomHTML/0.1"

    def do_GET(self):
        base_dir: Path = self.server.base_dir  # type: ignore[attr-defined]
        only_dir = safe_subdir_from_url_path(self.path)

        if only_dir == "__INVALID__":
            self.send_error(400, "Invalid directory path")
            return

        candidates = list_html_files(base_dir, only_dir)

        if not candidates:
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            msg = f"No HTML files found"
            if only_dir:
                msg += f" in directory {html.escape(only_dir)}"
            self.wfile.write(f"<h1>{msg}</h1>".encode("utf-8"))
            return

        chosen = random.choice(candidates)
        try:
            data = chosen.read_bytes()
        except OSError:
            self.send_error(500, "Failed to read file")
            return

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
    print(f"Open: http://{args.host}:{args.port}/  (any dir)")
    print(f"Or:   http://{args.host}:{args.port}/christmas/  (only that dir)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()

