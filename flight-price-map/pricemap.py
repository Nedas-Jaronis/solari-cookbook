"""Price the same flight from many countries at once.

Airlines and travel sites quote different fares depending on where you appear
to be browsing. You cannot test that from one machine: it needs real
residential IPs in real countries, which is what stealth mode plus managed
proxy egress is for.

Prices are forced to USD (`curr=USD`) so the comparison isolates *geographic*
pricing from mere exchange rates -- otherwise you are just watching currency
conversion and learning nothing.

    python pricemap.py --from JFK --to LHR --date 2026-10-15 \
        --countries us gb de in br jp
"""

import argparse
import asyncio
import json
import os
import pathlib
import re
import sys
import time
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import parse

HERE = pathlib.Path(__file__).parent


def load_env() -> None:
    env = HERE / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def flight_url(origin: str, destination: str, date: str, ret: str | None) -> str:
    query = f"flights from {origin} to {destination} on {date}"
    if ret:
        query += f" through {ret}"
    return ("https://www.google.com/travel/flights?curr=USD&hl=en&q="
            + urllib.parse.quote(query))


async def price_from(solari, gate, country: str, url: str, shots: pathlib.Path) -> dict:
    """One country: launch a proxied browser, read the board, report the fare."""
    async with gate:
        started = time.time()
        browser = None
        try:
            browser = await solari.launch(stealth=True, proxy=country)
            page = await browser.new_page()
            await page.goto(url, timeout=90_000)
            # Results stream in after load; without this the page is still
            # showing "Loading results" and every price is missing.
            await asyncio.sleep(7)
            text = await page.locator("body").inner_text()

            shots.mkdir(exist_ok=True)
            (shots / f"{country}.txt").write_text(text[:20000], encoding="utf-8")

            summary = parse.summarise(text)
            resolved = getattr(browser, "proxy", None)
            return {
                "country": country,
                "ok": summary["cheapest"] is not None,
                "cheapest": summary["cheapest"],
                "headline": summary["headline_cheapest"],
                "currency": summary["currency"],
                "count": summary["count"],
                "flights": summary["flights"][:5],
                "timezone": getattr(resolved, "timezone_id", None),
                "seconds": round(time.time() - started, 1),
            }
        except Exception as err:
            return {"country": country, "ok": False, "error": f"{type(err).__name__}: {err}"[:160],
                    "seconds": round(time.time() - started, 1)}
        finally:
            if browser is not None:
                try:
                    await browser.close()
                except Exception:
                    pass


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="origin", default="JFK")
    parser.add_argument("--to", dest="destination", default="LHR")
    parser.add_argument("--date", default="2026-10-15")
    parser.add_argument("--return", dest="ret", default=None)
    parser.add_argument("--countries", nargs="+",
                        default=["us", "gb", "de", "in", "br", "jp"])
    parser.add_argument("--concurrency", type=int, default=6,
                        help="browsers at once; the Starter plan allows 20")
    parser.add_argument("--out", default="prices.json")
    args = parser.parse_args()

    load_env()
    from solari_browser import Solari

    url = flight_url(args.origin, args.destination, args.date, args.ret)
    print(f"{args.origin} -> {args.destination} on {args.date}, priced in USD")
    print(f"{len(args.countries)} countries, {args.concurrency} browsers at a time\n")

    solari = Solari(api_key=os.environ["SOLARI_API_KEY"])
    gate = asyncio.Semaphore(args.concurrency)
    shots = HERE / "pages"
    started = time.time()
    results = await asyncio.gather(
        *(price_from(solari, gate, c, url, shots) for c in args.countries)
    )

    good = [r for r in results if r.get("ok")]
    print(f"{'country':>8} {'cheapest':>10} {'flights':>8}  {'secs':>5}  timezone")
    for r in sorted(results, key=lambda r: (not r.get("ok"), r.get("cheapest") or 1e9)):
        if r.get("ok"):
            print(f"{r['country']:>8} {r['currency']}{r['cheapest']:>9,} {r['count']:>8}  "
                  f"{r['seconds']:>5}  {r.get('timezone') or ''}")
        else:
            print(f"{r['country']:>8} {'FAILED':>10} {'':>8}  {r['seconds']:>5}  "
                  f"{r.get('error','')[:60]}")

    if len(good) > 1:
        lo = min(good, key=lambda r: r["cheapest"])
        hi = max(good, key=lambda r: r["cheapest"])
        spread = hi["cheapest"] - lo["cheapest"]
        pct = spread / lo["cheapest"] * 100
        print(f"\ncheapest {lo['country'].upper()} ${lo['cheapest']:,} | "
              f"dearest {hi['country'].upper()} ${hi['cheapest']:,} | "
              f"spread ${spread:,} ({pct:.1f}%)")
    print(f"\n{time.time()-started:.0f}s total -> {args.out}")
    (HERE / args.out).write_text(json.dumps(
        {"route": f"{args.origin}-{args.destination}", "date": args.date,
         "url": url, "results": results}, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
