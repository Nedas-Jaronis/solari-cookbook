"""Price one trip across every site, every nearby airport, at once.

Three dimensions, all fanned out in parallel because the browsers are:

  sites      Google Flights, Kayak, Momondo, Expedia, Skyscanner...
  airports   every airport in the origin and destination metro areas
  countries  where you appear to be browsing from

The point of doing it in parallel is that the answer arrives in about the time
one search takes. Twenty concurrent browsers is twenty searches for the price
of the slowest.

    python compare.py --from JFK --to LHR --date 2026-10-15
    python compare.py --from JFK --to LHR --date 2026-10-15 --nearby
"""

import argparse
import asyncio
import json
import os
import random
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from itertools import product

import airports
import sites as siteslib
from common import HERE, Query, blocked, load_env, no_results

PAGES = HERE / "pages"


@dataclass
class Task:
    site: str
    origin: str
    destination: str
    country: str

    @property
    def route(self) -> str:
        return f"{self.origin}-{self.destination}"

    @property
    def slug(self) -> str:
        return f"{self.site}-{self.route}-{self.country}"


async def read_when_ready(page, site, grace: float = 6.0) -> tuple[str, list]:
    """Poll the page until it has fares, rather than sleeping a fixed guess.

    A fixed sleep is wrong in both directions: too short and Google is still
    showing "Loading results", too long and every fast site pays for the
    slowest one. Once fares do appear we wait out `grace` and read again, so a
    page that is still streaming rows in does not get cut off at the first one.
    """
    deadline = time.time() + site.patience
    text, fares = "", []
    while True:
        text = await page.locator("body").inner_text()
        fares = site.read(text)
        if fares:
            await asyncio.sleep(grace)
            text = await page.locator("body").inner_text()
            return text, site.read(text)
        if blocked(text) or no_results(text) or time.time() >= deadline:
            return text, fares
        await asyncio.sleep(2.5)


async def attempt(solari, task: Task, site, url: str, base: dict,
                  dump: bool) -> dict:
    """One browser, one load. Reports a block distinctly from an empty page."""
    started = time.time()
    try:
        browser = await solari.launch(stealth=True, proxy=task.country)
    except Exception as err:
        return {**base, "ok": False, "stage": "launch", "blocked": False, "status": "error",
                "error": f"{type(err).__name__}: {err}"[:200], "seconds": 0.0}
    try:
        async with browser:
            page = await browser.new_page()
            await page.goto(url, timeout=90_000, wait_until="domcontentloaded")
            text, fares = await read_when_ready(page, site)
            wall = blocked(text)
            empty = no_results(text)
            resolved = getattr(browser, "proxy", None)

            if dump or not fares:
                PAGES.mkdir(exist_ok=True)
                (PAGES / f"{task.slug}.txt").write_text(text, encoding="utf-8")

            return {
                **base,
                "ok": bool(fares),
                "blocked": wall,
                "status": ("ok" if fares else "blocked" if wall
                           else "empty" if empty else "unparsed"),
                "count": len(fares),
                "cheapest": min((f.price for f in fares), default=None),
                "median": sorted(f.price for f in fares)[len(fares) // 2]
                          if fares else None,
                "fares": [asdict(f) for f in sorted(
                    fares, key=lambda f: f.price)[:6]],
                "timezone": getattr(resolved, "timezone_id", None),
                "egress": getattr(resolved, "country", None),
                "seconds": round(time.time() - started, 1),
                "error": None if fares else
                         ("anti-bot wall" if wall else
                          "site reports no flights on this route" if empty else
                          "loaded but no fares parsed"),
            }
    except Exception as err:
        return {**base, "ok": False, "stage": "load", "blocked": False, "status": "error",
                "error": f"{type(err).__name__}: {err}"[:200],
                "seconds": round(time.time() - started, 1)}


async def run(solari, gate, site_gate, task: Task, date: str, ret: str | None,
              dump: bool, retries: int = 1) -> dict:
    """One search, throttled per site and retried once on an anti-bot wall.

    `site_gate` is the important one. Firing every airport at a single site
    simultaneously is what gets you walled -- five identical searches landing
    together looks like nothing a person does, and Skyscanner blocked all five
    when we tried it. A couple at a time, arriving on different residential
    IPs a moment apart, gets read.

    A wall is worth one more go on a fresh IP after a pause. An unblocked page
    with no fares is not retried: that is a parser gap or a genuinely empty
    search, and repeating it would only add load.
    """
    site = siteslib.BY_KEY[task.site]
    q = Query(task.origin, task.destination, date, ret)
    url = site.build(q)
    base = {**asdict(task), "route": task.route, "url": url}

    async with gate, site_gate:
        await asyncio.sleep(random.uniform(0, 2.5))    # de-synchronise arrivals
        for tries_left in range(retries, -1, -1):
            result = await attempt(solari, task, site, url, base, dump)
            if result["ok"] or not result.get("blocked") or not tries_left:
                result["attempts"] = retries - tries_left + 1
                return result
            await asyncio.sleep(random.uniform(10, 18))


def report(results: list[dict], elapsed: float, asked: str) -> None:
    good = [r for r in results if r.get("ok")]

    print(f"\n{'site':>11} {'route':>9} {'cc':>3} {'fares':>6} {'cheapest':>9} "
          f"{'secs':>6}  note")
    for r in sorted(results, key=lambda r: (not r.get("ok"),
                                            r.get("cheapest") or 10**9)):
        if r.get("ok"):
            print(f"{r['site']:>11} {r['route']:>9} {r['country']:>3} "
                  f"{r['count']:>6} ${r['cheapest']:>8,} {r['seconds']:>6}  "
                  f"{r.get('timezone') or ''}")
        else:
            print(f"{r['site']:>11} {r['route']:>9} {r['country']:>3} "
                  f"{'-':>6} {'FAILED':>9} {r['seconds']:>6}  "
                  f"{(r.get('error') or '')[:52]}")

    if not good:
        print("\nNothing parsed. Check pages/ for what the sites actually showed.")
        return

    best = min(good, key=lambda r: r["cheapest"])
    worst = max(good, key=lambda r: r["cheapest"])
    print(f"\nbest  ${best['cheapest']:,}  {best['site']} {best['route']}")

    routes = sorted({r["route"] for r in good})
    if len(routes) > 1:
        print("\ncheapest by route (across all sites):")
        for route in sorted(routes, key=lambda rt: min(
                r["cheapest"] for r in good if r["route"] == rt)):
            rows = [r for r in good if r["route"] == route]
            win = min(rows, key=lambda r: r["cheapest"])
            gap = win["cheapest"] - best["cheapest"]
            flag = "  <- cheapest" if gap == 0 else f"  +${gap:,}"
            print(f"  {route:>9} ${win['cheapest']:>7,}  {win['site']:<11}{flag}")

    # Compare sites on the route actually asked for, not on whichever route
    # happened to win -- otherwise this table quietly answers a different
    # question from the one its heading claims.
    rows = sorted([r for r in good if r["route"] == asked],
                  key=lambda r: r["cheapest"])
    if len(rows) > 1:
        print(f"\ncheapest by site for {asked} (apples to apples):")
        for r in rows:
            gap = r["cheapest"] - rows[0]["cheapest"]
            print(f"  {r['site']:>11} ${r['cheapest']:>7,}"
                  + (f"  +${gap:,}" if gap else "  <- cheapest"))

    spread = worst["cheapest"] - best["cheapest"]
    print(f"\nspread ${spread:,} "
          f"({spread / best['cheapest'] * 100:.0f}% over the cheapest) "
          f"across {len(good)}/{len(results)} successful searches in "
          f"{elapsed:.0f}s")


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="origin", default="JFK")
    ap.add_argument("--to", dest="destination", default="LHR")
    ap.add_argument("--date", default="2026-10-15")
    ap.add_argument("--return", dest="ret", default=None)
    ap.add_argument("--sites", nargs="+",
                    default=["google", "kayak", "momondo", "expedia",
                             "skyscanner", "priceline"])
    ap.add_argument("--countries", nargs="+", default=["us"],
                    help="proxy egress; non-US needs a plan that includes it")
    ap.add_argument("--nearby", nargs="?", const="both",
                    choices=["both", "from", "to"], default=None,
                    help="also price other airports in the metro area: "
                         "'to' (default useful case), 'from', or 'both'")
    ap.add_argument("--concurrency", type=int, default=10,
                    help="browsers at once; the Starter plan allows 20")
    ap.add_argument("--max-tasks", type=int, default=40)
    ap.add_argument("--per-site", type=int, default=2,
                    help="simultaneous searches against any one site")
    ap.add_argument("--dump", action="store_true",
                    help="save every page's text to pages/ (failures always are)")
    ap.add_argument("--out", default="results.json")
    args = ap.parse_args()

    spread_from = args.nearby in ("both", "from")
    spread_to = args.nearby in ("both", "to")
    origins = airports.expand(args.origin) if spread_from else [args.origin.upper()]
    dests = airports.expand(args.destination) if spread_to else [args.destination.upper()]

    tasks = [Task(s, o, d, c) for s, o, d, c
             in product(args.sites, origins, dests, args.countries)]
    if len(tasks) > args.max_tasks:
        print(f"{len(tasks)} searches exceeds --max-tasks {args.max_tasks}; "
              f"trimming. Raise it, or drop --nearby.")
        tasks = tasks[:args.max_tasks]

    load_env()
    from solari_browser import Solari

    print(f"{args.origin} -> {args.destination} on {args.date}"
          + (f", returning {args.ret}" if args.ret else " (one way)"))
    print(f"{len(args.sites)} sites x {len(origins)}x{len(dests)} airports "
          f"x {len(args.countries)} countries = {len(tasks)} searches, "
          f"{args.concurrency} at a time")

    solari = Solari(api_key=os.environ["SOLARI_API_KEY"])
    gate = asyncio.Semaphore(args.concurrency)
    site_gates = {key: asyncio.Semaphore(args.per_site) for key in args.sites}
    started = time.time()
    results = await asyncio.gather(*(
        run(solari, gate, site_gates[t.site], t, args.date, args.ret, args.dump)
        for t in tasks))
    elapsed = time.time() - started

    report(results, elapsed,
           f"{args.origin.upper()}-{args.destination.upper()}")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "origin": args.origin.upper(), "destination": args.destination.upper(),
        "date": args.date, "ret": args.ret, "nearby": args.nearby,
        "seconds": round(elapsed, 1),
        "site_names": {s.key: s.name for s in siteslib.SITES},
        "results": results,
    }
    (HERE / args.out).write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"-> {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
