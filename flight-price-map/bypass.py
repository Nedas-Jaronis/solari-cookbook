"""Dev tool: which launch options actually get past a site that walls us?

Solari's browser has more anti-bot machinery than `stealth=True`: a `captcha`
flag, and `proxy="smart"`, which picks the egress and rotates it when a site
blocks. Both are off by default and neither is guessable from the failure --
a wall looks identical whichever option would have cleared it.

So try them side by side against the site that is actually blocking.

    python bypass.py --site skyscanner --from JFK --to LHR --date 2026-10-15
"""

import argparse
import asyncio
import os
import time

import sites as siteslib
from common import HERE, Query, blocked, load_env, no_results
from compare import read_when_ready

PAGES = HERE / "pages"

# (label, launch kwargs) -- one row per combination worth trying.
VARIANTS = [
    ("stealth + us", dict(stealth=True, proxy="us")),
    ("stealth + captcha + us", dict(stealth=True, captcha=True, proxy="us")),
    ("stealth + smart", dict(stealth=True, proxy="smart")),
    ("stealth + captcha + smart",
     dict(stealth=True, captcha=True, proxy="smart")),
    ("stealth + captcha + gb", dict(stealth=True, captcha=True, proxy="gb")),
    ("stealth + web_bot_auth + us",
     dict(stealth=True, web_bot_auth=True, proxy="us")),
]


async def try_one(solari, gate, site, url: str, label: str, kwargs: dict) -> dict:
    async with gate:
        started = time.time()
        try:
            browser = await solari.launch(**kwargs)
        except Exception as err:
            return {"label": label, "state": "launch failed",
                    "detail": f"{type(err).__name__}: {err}"[:90],
                    "seconds": round(time.time() - started, 1)}
        try:
            async with browser:
                page = await browser.new_page()
                await page.goto(url, timeout=90_000,
                                wait_until="domcontentloaded")
                text, fares = await read_when_ready(page, site)
                PAGES.mkdir(exist_ok=True)
                (PAGES / f"bypass-{label.replace(' ', '')}.txt").write_text(
                    text, encoding="utf-8")
                if fares:
                    state, detail = "READ", f"{len(fares)} fares, cheapest ${min(f.price for f in fares):,}"
                elif blocked(text):
                    state, detail = "blocked", text.strip().splitlines()[0][:60] if text.strip() else ""
                elif no_results(text):
                    state, detail = "no flights", ""
                else:
                    state, detail = "no fares", f"{len(text)} chars"
                return {"label": label, "state": state, "detail": detail,
                        "seconds": round(time.time() - started, 1)}
        except Exception as err:
            return {"label": label, "state": "error",
                    "detail": f"{type(err).__name__}: {err}"[:90],
                    "seconds": round(time.time() - started, 1)}


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", default="skyscanner")
    ap.add_argument("--from", dest="origin", default="JFK")
    ap.add_argument("--to", dest="destination", default="LHR")
    ap.add_argument("--date", default="2026-10-15")
    ap.add_argument("--concurrency", type=int, default=3,
                    help="keep this low: the point is to look like few users")
    args = ap.parse_args()

    load_env()
    from solari_browser import Solari

    site = siteslib.BY_KEY[args.site]
    url = site.build(Query(args.origin.upper(), args.destination.upper(),
                           args.date))
    print(f"{site.name}: {url}\n{len(VARIANTS)} launch options\n")

    solari = Solari(api_key=os.environ["SOLARI_API_KEY"])
    gate = asyncio.Semaphore(args.concurrency)
    rows = await asyncio.gather(*(
        try_one(solari, gate, site, url, label, kwargs)
        for label, kwargs in VARIANTS))

    width = max(len(r["label"]) for r in rows)
    for r in rows:
        print(f"  {r['label']:>{width}}  {r['state']:>12}  "
              f"{r['seconds']:>5}s  {r['detail']}")
    won = [r for r in rows if r["state"] == "READ"]
    print(f"\n{len(won)}/{len(rows)} got through"
          + (f": {', '.join(r['label'] for r in won)}" if won else ""))


if __name__ == "__main__":
    asyncio.run(main())
