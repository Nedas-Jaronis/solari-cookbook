"""Check whether the prices a travel site advertises are the prices you get.

Two waves of browsers:

  1. Load each site's results page and collect every price it advertises for a
     search you did not run -- a cheaper nearby date, a cheaper airport.
  2. Run all of those searches at once and read what actually comes back.

No comparison site will answer this about itself, and answering it by hand
means running a dozen searches and remembering a dozen numbers. It is the same
fan-out as compare.py pointed at a better question.

    python verify.py --from JFK --to LHR --date 2026-10-15

A gap is not proof of bad faith. Teasers go stale, cheap seats sell, and a
"from" price may be a fare class the results page then filters out. What is
worth knowing is how often the advertised number survives the click.
"""

import argparse
import asyncio
import json
import os
import random
import time
from dataclasses import asdict
from datetime import datetime, timezone

import airports
import claims as claimslib
import sites as siteslib
from common import HERE, Query, blocked, egress, load_env, no_results, sticky_id
from compare import read_when_ready

PAGES = HERE / "pages"


async def load(solari, gate, site_gate, site, url: str, country: str) -> dict:
    """Open one page through a residential IP and read it.

    One pinned exit for the whole read: these pages fetch their fares after the
    document, and the rotating default can serve those follow-ups from a
    different address than the page itself.
    """
    async with gate, site_gate:
        await asyncio.sleep(random.uniform(0, 2.0))
        started = time.time()
        session = sticky_id(f"{site.key}-{country}-{abs(hash(url)) % 10**6}")
        try:
            browser = await solari.launch(
                stealth=True,
                proxy=egress(country, session=session, hold=site.patience))
        except Exception as err:
            return {"ok": False, "error": f"{type(err).__name__}: {err}"[:160],
                    "seconds": 0.0, "text": "", "fares": []}
        try:
            async with browser:
                page = await browser.new_page()
                await page.goto(url, timeout=90_000, wait_until="domcontentloaded")
                text, fares = await read_when_ready(page, site)
                return {
                    "ok": bool(fares), "text": text, "fares": fares,
                    "blocked": blocked(text), "empty": no_results(text),
                    "cheapest": min((f.price for f in fares), default=None),
                    "seconds": round(time.time() - started, 1),
                    "error": None if fares else
                             ("anti-bot wall" if blocked(text) else
                              "no flights" if no_results(text) else
                              "no fares parsed"),
                }
        except Exception as err:
            return {"ok": False, "error": f"{type(err).__name__}: {err}"[:160],
                    "seconds": round(time.time() - started, 1),
                    "text": "", "fares": []}


async def discover(solari, gate, site_gates, site, base: Query,
                   country: str) -> dict:
    """Wave one: what does this site's results page advertise?"""
    url = site.build(base)
    got = await load(solari, gate, site_gates[site.key], site, url, country)
    found = (claimslib.extract(got["text"], base, site.key)
             if got.get("text") else [])
    if got.get("text"):
        PAGES.mkdir(exist_ok=True)
        (PAGES / f"claims-{site.key}.txt").write_text(got["text"],
                                                      encoding="utf-8")
    return {
        "site": site.key, "url": url, "ok": got["ok"],
        "baseline": got.get("cheapest"), "seconds": got["seconds"],
        "error": got.get("error"), "claims": found,
    }


async def check(solari, gate, site_gates, claim, base: Query,
                country: str) -> dict:
    """Wave two: run the search this claim promises something about."""
    site = siteslib.BY_KEY[claim.site]

    # Test the claim the way most favourable to the site. A sidebar "from"
    # price sits beside a list that includes every origin airport in the metro
    # area, so it is a promise about all of New York, not about JFK. Holding it
    # to JFK alone would manufacture a gap that is not really there.
    origin = base.origin
    if claim.kind == "airport" and claim.metro_wide and site.metro:
        origin = airports.metro_of(base.origin) or base.origin

    query = claim.query(base, origin)
    url = site.build(query)
    got = await load(solari, gate, site_gates[site.key], site, url, country)

    delivered = got.get("cheapest")
    if delivered is None:
        verdict = "unverified"
    elif delivered <= claim.advertised:
        verdict = "holds"
    else:
        verdict = "higher"

    return {
        **{k: v for k, v in asdict(claim).items()},
        "url": url,
        "tested_origin": origin,
        "delivered": delivered,
        "gap": (delivered - claim.advertised) if delivered is not None else None,
        "verdict": verdict,
        "seconds": got["seconds"],
        "error": got.get("error"),
    }


def report(discovered: list[dict], checked: list[dict], elapsed: float) -> None:
    print(f"\n{'site':>11} {'advertises':>11} {'you get':>9} {'gap':>7}  verdict")
    for c in sorted(checked, key=lambda c: (c["site"],
                                            c.get("date") or c.get("destination") or "")):
        label = c.get("date") or c.get("destination") or ""
        got = f"${c['delivered']:,}" if c["delivered"] is not None else "--"
        gap = (f"{c['gap']:+,}" if c["gap"] is not None else "")
        note = c["verdict"] if c["delivered"] is not None else (
            c.get("error") or "unverified")
        print(f"{c['site']:>11} {label:>11} ${c['advertised']:>6,} -> {got:>8} "
              f"{gap:>7}  {note}")

    tested = [c for c in checked if c["delivered"] is not None]
    if not tested:
        print("\nNothing could be verified.")
        return
    held = [c for c in tested if c["verdict"] == "holds"]
    over = [c for c in tested if c["verdict"] == "higher"]
    print(f"\n{len(held)}/{len(tested)} advertised prices held.")
    if over:
        worst = max(over, key=lambda c: c["gap"])
        total = sum(c["gap"] for c in over)
        print(f"{len(over)} came back higher, by ${total:,} in total; "
              f"worst ${worst['gap']:,} "
              f"({worst['site']} {worst.get('date') or worst.get('destination')})")
    print(f"\n{len(discovered)} pages read, {len(checked)} claims tested, "
          f"{elapsed:.0f}s")


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="origin", default="JFK")
    ap.add_argument("--to", dest="destination", default="LHR")
    ap.add_argument("--date", default="2026-10-15")
    ap.add_argument("--return", dest="ret", default=None)
    ap.add_argument("--sites", nargs="+",
                    default=["google", "kayak", "momondo", "skyscanner"])
    ap.add_argument("--country", default="us")
    ap.add_argument("--concurrency", type=int, default=12)
    ap.add_argument("--per-site", type=int, default=2)
    ap.add_argument("--max-claims", type=int, default=16)
    ap.add_argument("--out", default="teasers.json")
    args = ap.parse_args()

    load_env()
    from solari_browser import Solari

    base = Query(args.origin.upper(), args.destination.upper(), args.date,
                 args.ret)
    chosen = [siteslib.BY_KEY[k] for k in args.sites]
    solari = Solari(api_key=os.environ["SOLARI_API_KEY"])
    gate = asyncio.Semaphore(args.concurrency)
    site_gates = {k: asyncio.Semaphore(args.per_site) for k in args.sites}
    started = time.time()

    print(f"{base.label()} -- reading what {len(chosen)} sites advertise")
    discovered = await asyncio.gather(*(
        discover(solari, gate, site_gates, s, base, args.country)
        for s in chosen))

    every = [c for d in discovered for c in d["claims"]]
    for d in discovered:
        state = (f"{len(d['claims'])} claims" if d["ok"]
                 else f"FAILED {d.get('error') or ''}")
        base_price = f"${d['baseline']:,}" if d.get("baseline") else "--"
        print(f"  {d['site']:>11}  baseline {base_price:>8}  {state}")

    if not every:
        print("\nNo advertised prices found to test.")
        return
    if len(every) > args.max_claims:
        print(f"\n{len(every)} claims found, testing the first "
              f"{args.max_claims} (--max-claims to raise)")
        every = every[:args.max_claims]

    print(f"\ntesting {len(every)} advertised prices in parallel")
    checked = await asyncio.gather(*(
        check(solari, gate, site_gates, c, base, args.country) for c in every))
    elapsed = time.time() - started

    report(discovered, checked, elapsed)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "origin": base.origin, "destination": base.destination,
        "date": base.date, "ret": base.ret, "seconds": round(elapsed, 1),
        "site_names": {s.key: s.name for s in siteslib.SITES},
        "pages": [{k: v for k, v in d.items() if k != "claims"}
                  | {"claims": [asdict(c) for c in d["claims"]]}
                  for d in discovered],
        "checked": checked,
    }
    (HERE / args.out).write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"-> {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
