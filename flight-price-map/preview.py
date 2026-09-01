"""Dev tool: screenshot the dashboard in both themes, so you look at it.

A stylesheet can pass review and still render with colliding labels or a
one-theme-only color. Rendering it is the check.

    python dashboard.py --standalone --out preview.html
    python preview.py
"""

import argparse
import pathlib

from patchright.sync_api import sync_playwright

from common import HERE


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--page", default="preview.html")
    ap.add_argument("--name", default="dashboard",
                    help="basename for the screenshots in shots/")
    ap.add_argument("--width", type=int, default=1100)
    ap.add_argument("--height", type=int, default=1400)
    args = ap.parse_args()

    url = (HERE / args.page).resolve().as_uri()
    shots = HERE / "shots"
    shots.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for theme in ("light", "dark"):
            page = browser.new_page(
                viewport={"width": args.width, "height": args.height},
                color_scheme=theme)
            page.goto(url)
            page.wait_for_timeout(1200)      # let the webfonts land
            out = shots / f"{args.name}-{theme}.png"
            page.screenshot(path=str(out), full_page=True)
            print(f"{theme:>5}  {out}")
            page.close()
        browser.close()


if __name__ == "__main__":
    main()
