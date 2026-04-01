#!/usr/bin/env python3
from __future__ import annotations

import base64
import struct
import subprocess
import tempfile
import textwrap
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DIR = REPO_ROOT / "frontend" / "public"
ICONS_DIR = PUBLIC_DIR / "icons"
STANDARD_SOURCE = ICONS_DIR / "cartrap-icon.svg"
FAVICON_SOURCE = ICONS_DIR / "cartrap-favicon.svg"
MASKABLE_SOURCE = ICONS_DIR / "cartrap-icon-maskable.svg"
CHROME_BINARY = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def build_render_page(source: Path, size: int, page_path: Path) -> None:
    svg_base64 = base64.b64encode(source.read_bytes()).decode("ascii")
    html = textwrap.dedent(
        f"""\
        <!doctype html>
        <html lang="en">
          <head>
            <meta charset="utf-8" />
            <style>
              html,
              body {{
                margin: 0;
                width: {size}px;
                height: {size}px;
                overflow: hidden;
                background: transparent;
              }}

              body {{
                display: grid;
                place-items: stretch;
              }}

              canvas {{
                width: {size}px;
                height: {size}px;
                display: block;
              }}
            </style>
          </head>
          <body>
            <canvas id="icon" width="{size}" height="{size}"></canvas>
            <script>
              window.addEventListener("load", async () => {{
                const image = new Image();
                image.decoding = "sync";
                image.src = "data:image/svg+xml;base64,{svg_base64}";
                await image.decode();
                const canvas = document.getElementById("icon");
                const context = canvas.getContext("2d");
                context.clearRect(0, 0, canvas.width, canvas.height);
                context.drawImage(image, 0, 0, canvas.width, canvas.height);
                document.body.dataset.ready = "1";
              }});
            </script>
          </body>
        </html>
        """
    )
    page_path.write_text(html, encoding="utf-8")


def render_png(source: Path, destination: Path, size: int, profile_dir: Path, temp_root: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()

    page_path = temp_root / f"render-{destination.stem}.html"
    build_render_page(source, size, page_path)

    command = [
        str(CHROME_BINARY),
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        "--force-device-scale-factor=1",
        "--allow-file-access-from-files",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=1500",
        "--default-background-color=00000000",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-sync",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-features=DialMediaRouteProvider,OptimizationHints,PaintHolding,Translate",
        f"--user-data-dir={profile_dir}",
        f"--window-size={size},{size}",
        f"--screenshot={destination}",
        page_path.resolve().as_uri(),
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 30
    observed_size = -1
    stable_polls = 0

    while time.monotonic() < deadline:
        if destination.exists():
            current_size = destination.stat().st_size
            if current_size > 0 and current_size == observed_size:
                stable_polls += 1
            else:
                stable_polls = 0
                observed_size = current_size

            if current_size > 0 and stable_polls >= 2:
                time.sleep(0.2)
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
                return

        exit_code = process.poll()
        if exit_code is not None:
            stdout, stderr = process.communicate()
            if exit_code != 0:
                raise subprocess.CalledProcessError(exit_code, command, output=stdout, stderr=stderr)
            if destination.exists() and destination.stat().st_size > 0:
                return
            raise RuntimeError(f"Chrome exited without producing {destination.name}")

        time.sleep(0.2)

    process.kill()
    stdout, stderr = process.communicate(timeout=3)
    raise TimeoutError(f"Timed out while rendering {destination.name}: {stderr or stdout}")


def build_ico(icon_sizes: list[tuple[int, Path]], destination: Path) -> None:
    images = [(size, path.read_bytes()) for size, path in icon_sizes]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + (16 * len(images))
    entries: list[bytes] = []
    payload: list[bytes] = []

    for size, data in images:
        width = 0 if size >= 256 else size
        height = 0 if size >= 256 else size
        entries.append(
            struct.pack(
                "<BBBBHHII",
                width,
                height,
                0,
                0,
                1,
                32,
                len(data),
                offset,
            )
        )
        payload.append(data)
        offset += len(data)

    destination.write_bytes(header + b"".join(entries) + b"".join(payload))


def main() -> None:
    if not CHROME_BINARY.exists():
        raise SystemExit(f"Missing required tool: {CHROME_BINARY}")

    favicon_outputs = {
        PUBLIC_DIR / "favicon-16x16.png": 16,
        PUBLIC_DIR / "favicon-32x32.png": 32,
    }
    standard_outputs = {
        ICONS_DIR / "icon-192.png": 192,
        ICONS_DIR / "icon-512.png": 512,
    }
    maskable_outputs = {
        PUBLIC_DIR / "apple-touch-icon.png": 180,
        ICONS_DIR / "icon-maskable-192.png": 192,
        ICONS_DIR / "icon-maskable-512.png": 512,
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)

        for destination, size in favicon_outputs.items():
            render_png(
                FAVICON_SOURCE,
                destination,
                size,
                temp_root / f"profile-{destination.stem}",
                temp_root,
            )

        for destination, size in standard_outputs.items():
            render_png(
                STANDARD_SOURCE,
                destination,
                size,
                temp_root / f"profile-{destination.stem}",
                temp_root,
            )

        for destination, size in maskable_outputs.items():
            render_png(
                MASKABLE_SOURCE,
                destination,
                size,
                temp_root / f"profile-{destination.stem}",
                temp_root,
            )

        favicon48 = temp_root / "favicon-48x48.png"
        render_png(FAVICON_SOURCE, favicon48, 48, temp_root / "profile-favicon-48x48", temp_root)
        build_ico(
            [
                (16, PUBLIC_DIR / "favicon-16x16.png"),
                (32, PUBLIC_DIR / "favicon-32x32.png"),
                (48, favicon48),
            ],
            PUBLIC_DIR / "favicon.ico",
        )


if __name__ == "__main__":
    main()
