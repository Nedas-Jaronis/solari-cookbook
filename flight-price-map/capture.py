"""Dev tool: load each site once and dump what it actually shows.

Parsers are written against these dumps rather than guessed at. Run it whenever
a site changes its layout and the reader stops finding fares.

    python capture.py --from JFK --to LHR --date 2026-10-15
"""

import argparse
import asyncio
import os
import time

from common import HERE, Query, load_env
import sites as siteslib

PAGES = HERE / "pages"


async def grab(solari, gate, site, q, country: str, shot: bool) -> dict:
    url = site.build(q)
    async with gate:
        started = time.time()
        try:
            browser = await solari.launch(stealth=True, proxy=country)
        except Exception as err:
            return {"site": site.key, "ok": False, "stage": "launch",
                    "error": f"{type(err).__name__}: {err}"[:200], "secs": 0}
        try:
            async with browser:
                page = await browser.new_page()
                await page.goto(url, timeout=90_000, wait_until="domcontentloaded")
                await asyncio.sleep(site.patience)
                text = await page.locator("body").inner_text()
                PAGES.mkdir(exist_ok=True)
                (PAGES / f"{site.key}.txt").write_text(text, encoding="utf-8")
                if shot:
                    await page.screenshot(path=str(PAGES / f"{site.key}.png"),
                                          full_page=False)
                fares = site.read(text)
                return {"site": site.key, "ok": True, "chars": len(text),
                        "fares": len(fares),
                        "cheapest": min((f.price for f in fares), default=None),
                        "title": (await page.title())[:60],
                        "secs": round(time.time() - started, 1)}
        except Exception as err:
            return {"site": site.key, "ok": False, "stage": "load",
                    "error": f"{type(err).__name__}: {err}"[:200],
                    "secs": round(time.time() - started, 1)}


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from", dest="origin", default="JFK")
    ap.add_argument("--to", dest="destination", default="LHR")
    ap.add_argument("--date", default="2026-10-15")
    ap.add_argument("--return", dest="ret", default=None)
    ap.add_argument("--sites", nargs="+", default=[s.key for s in siteslib.SITES])
    ap.add_argument("--country", default="us")
    ap.add_argument("--concurrency", type=int, default=7)
    ap.add_argument("--no-shot", action="store_true")
    args = ap.parse_args()

    load_env()
    from solari_browser import Solari

    q = Query(args.origin, args.destination, args.date, args.ret)
    chosen = [siteslib.BY_KEY[k] for k in args.sites]
    print(f"{q.label()} via {args.country}, {len(chosen)} sites\n")

    solari = Solari(api_key=os.environ["SOLARI_API_KEY"])
    gate = asyncio.Semaphore(args.concurrency)
    started = time.time()
    results = await asyncio.gather(*(
        grab(solari, gate, s, q, args.country, not args.no_shot) for s in chosen))

    print(f"{'site':>12} {'chars':>7} {'fares':>6} {'cheapest':>9} {'secs':>6}  title")
    for r in results:
        if r["ok"]:
            print(f"{r['site']:>12} {r['chars']:>7} {r['fares']:>6} "
                  f"{str(r['cheapest'] or '-'):>9} {r['secs']:>6}  {r['title']}")
        else:
            print(f"{r['site']:>12} {'FAILED':>7} {'':>6} {'':>9} {r['secs']:>6}  "
                  f"[{r['stage']}] {r['error'][:70]}")
    print(f"\n{time.time()-started:.0f}s -> {PAGES}")


if __name__ == "__main__":
    asyncio.run(main())
