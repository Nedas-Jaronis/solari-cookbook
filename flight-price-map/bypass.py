"""Dev tool: which launch options actually get past a site that walls us?

Solari's browser has more anti-bot machinery than `stealth=True`: a `captcha`
flag, and `proxy="smart"`, which picks the egress and rotates it when a site
blocks. Both are off by default and neither is guessable from the failure -- a
wall looks identical whichever option would have cleared it.

So try them side by side against the site that is actually blocking.

    python bypass.py --site skyscanner --from JFK --to LHR --date 2026-10-15

Two things this reports that a bare pass/fail does not, both learned the hard
way from a run whose table could not be interpreted afterwards:

*Whether the wall was even there.* Skyscanner serves PerimeterX from
`client.px-cloud.net/PXrf8vapwA/main.min.js`. A page that reads fares with that
script present means the vendor cleared a live wall; a page that reads fares
with no script at all means we were never challenged, and proves nothing about
whether we can be. They are different results and the `px` column keeps them
apart.

*Whether we reached the site at all.* A proxy tunnel that never opens is an
egress problem wearing an anti-bot costume. Those get one retry and, if they
fail again, are reported as `no egress` rather than counted as a block -- the
last run recorded a `gb` tunnel failure in a table about PerimeterX, which left
GB egress looking tested when it had never been reached.
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
#
# `stealth + gb` earns its place by being the only row that puts non-US egress
# against the wall itself: the captcha variant below it has never got far
# enough to say anything about PerimeterX.
VARIANTS = [
    ("stealth + us", dict(stealth=True, proxy="us")),
    ("stealth + captcha + us", dict(stealth=True, captcha=True, proxy="us")),
    ("stealth + smart", dict(stealth=True, proxy="smart")),
    ("stealth + captcha + smart",
     dict(stealth=True, captcha=True, proxy="smart")),
    ("stealth + gb", dict(stealth=True, proxy="gb")),
    ("stealth + captcha + gb", dict(stealth=True, captcha=True, proxy="gb")),
    ("stealth + web_bot_auth + us",
     dict(stealth=True, web_bot_auth=True, proxy="us")),
]

# The vendor's script, and the global it installs. Either one means the wall was
# served to us, whether or not it decided to stop us.
PX_MARKERS = ("px-cloud.net", "pxappid", "/pxrf8vapwa/")

# Transport-level failures: the browser never reached the site, so whatever the
# site would have done to us is still unknown. Worth one retry on a fresh IP.
EGRESS_MARKERS = ("err_tunnel_connection_failed", "err_proxy_connection_failed",
                  "err_connection_closed", "err_connection_reset",
                  "err_empty_response", "err_socks_connection_failed")


def egress_failure(detail: str) -> bool:
    low = detail.lower()
    return any(marker in low for marker in EGRESS_MARKERS)


async def px_served(page) -> bool | None:
    """Was PerimeterX on the page? None if we could not tell."""
    try:
        html = (await page.content()).lower()
    except Exception:
        return None
    return any(marker in html for marker in PX_MARKERS)


async def probe_once(solari, site, url: str, label: str, kwargs: dict) -> dict:
    """One browser, one load. States are kept distinct on purpose."""
    started = time.time()

    def row(state: str, detail: str = "", px: bool | None = None) -> dict:
        return {"label": label, "state": state, "detail": detail, "px": px,
                "seconds": round(time.time() - started, 1)}

    try:
        browser = await solari.launch(**kwargs)
    except Exception as err:
        return row("launch failed", f"{type(err).__name__}: {err}"[:90])
    try:
        async with browser:
            page = await browser.new_page()
            await page.goto(url, timeout=90_000, wait_until="domcontentloaded")
            text, fares = await read_when_ready(page, site)
            px = await px_served(page)
            PAGES.mkdir(exist_ok=True)
            (PAGES / f"bypass-{label.replace(' ', '')}.txt").write_text(
                text, encoding="utf-8")
            if fares:
                return row("READ", f"{len(fares)} fares, cheapest "
                                   f"${min(f.price for f in fares):,}", px)
            if blocked(text):
                head = text.strip().splitlines()
                return row("blocked", head[0][:60] if head else "", px)
            if no_results(text):
                return row("no flights", "", px)
            return row("no fares", f"{len(text)} chars", px)
    except Exception as err:
        return row("error", f"{type(err).__name__}: {err}"[:90])


async def try_one(solari, gate, site, url: str, label: str, kwargs: dict) -> dict:
    """Probe, and give a failed tunnel a second chance before believing it.

    Only the transport gets the retry. A block is a real answer from the site
    and re-asking it immediately would be the rate-limiting behaviour this whole
    tool exists to avoid.
    """
    async with gate:
        row = await probe_once(solari, site, url, label, kwargs)
        if row["state"] in ("launch failed", "error") and egress_failure(row["detail"]):
            await asyncio.sleep(3)
            retry = await probe_once(solari, site, url, label, kwargs)
            if retry["state"] in ("launch failed", "error") and egress_failure(retry["detail"]):
                retry["state"] = "no egress"
            return retry
        return row


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
    if not os.environ.get("SOLARI_API_KEY"):
        raise SystemExit(
            "SOLARI_API_KEY is not set. Copy .env.example to .env and fill it "
            "in, or export the key -- see https://console.getsolari.com")
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
        px = {True: "PX", False: "no PX", None: "?"}[r["px"]]
        print(f"  {r['label']:>{width}}  {r['state']:>12}  {px:>5}  "
              f"{r['seconds']:>5}s  {r['detail']}")

    won = [r for r in rows if r["state"] == "READ"]
    unreached = [r for r in rows if r["state"] == "no egress"]
    print(f"\n{len(won)}/{len(rows)} got through"
          + (f": {', '.join(r['label'] for r in won)}" if won else ""))
    # Reading fares off a page that never served the wall says nothing about
    # whether the wall can be cleared, so do not let it read as a win.
    if won and all(r["px"] is False for r in won):
        print("  ...but PerimeterX was not served to any of them: "
              "not yet evidence the wall is cleared.")
    if unreached:
        print(f"{len(unreached)} never reached the site "
              f"({', '.join(r['label'] for r in unreached)}) -- egress, not anti-bot.")


if __name__ == "__main__":
    asyncio.run(main())
