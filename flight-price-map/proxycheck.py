"""Which proxy egress actually connects, across countries and tiers.

Worth knowing before blaming the target site: a country whose pool is empty or
slow looks exactly like the page failing to load. This loads a trivial page
that echoes your IP, so anything that fails here failed at the proxy.

The tier matters as much as the country. `residential` is the default rotating
pool; `static` and `mobile` are separate pools with separate coverage, so a
country missing from one may be present in another.

    python proxycheck.py                        # default sweep
    python proxycheck.py --countries us gb jp --tiers residential mobile
    python proxycheck.py --smart                # just the auto-rotating option
    python proxycheck.py --sticky               # does a pinned session hold one IP?

`--sticky` is the one that matters for the search code. Everything else here
asks whether a country connects; that asks whether it stays put, which is the
property a search actually depends on -- a page that fetches its fares from a
different IP than it was served from is the bot signal we most want to avoid.
It loads the IP echo twice through one pinned session, then twice more with no
session as a control, and prints both. Rotating pools can repeat an address by
chance, so read the control as context and not as a failure.
"""

import argparse
import asyncio
import os
import time

from solari_browser import ProxyRequest, Solari

from common import load_env, sticky_id

TARGET = "https://api.ipify.org?format=json"


async def check(solari, gate, label: str, spec, timeout: int) -> tuple:
    """One launch, one trivial page load, one verdict."""
    async with gate:
        started = time.time()
        browser = None
        try:
            browser = await solari.launch(stealth=True, proxy=spec)
            page = await browser.new_page()
            await page.goto(TARGET, timeout=timeout * 1000)
            ip = (await page.locator("pre").inner_text()).strip()
            resolved = getattr(browser, "proxy", None)
            where = ""
            if resolved is not None:
                where = f"{getattr(resolved, 'country', '') or ''} " \
                        f"{getattr(resolved, 'timezone_id', '') or ''}".strip()
            return label, True, f"{time.time() - started:>4.0f}s  {ip}  {where}"
        except Exception as err:
            return (label, False,
                    f"{time.time() - started:>4.0f}s  {type(err).__name__}")
        finally:
            if browser is not None:
                try:
                    await browser.close()
                except Exception:
                    pass


async def ip_through(solari, spec, timeout: int) -> str:
    """The egress IP one launch is given, or a short error label."""
    browser = None
    try:
        browser = await solari.launch(stealth=True, proxy=spec)
        page = await browser.new_page()
        await page.goto(TARGET, timeout=timeout * 1000)
        return (await page.locator("pre").inner_text()).strip()
    except Exception as err:
        return f"<{type(err).__name__}>"
    finally:
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                pass


async def check_sticky(solari, gate, country: str, tier: str, timeout: int) -> tuple:
    """Twice through a pinned session, then twice unpinned as a control."""
    async with gate:
        session = sticky_id(f"stickycheck-{country}-{tier}")
        pinned = ProxyRequest(country=country, tier=tier, session=session,
                              session_duration=10)
        a = await ip_through(solari, pinned, timeout)
        b = await ip_through(solari, pinned, timeout)
        loose = ProxyRequest(country=country, tier=tier)
        c = await ip_through(solari, loose, timeout)
        d = await ip_through(solari, loose, timeout)
        return f"{country}/{tier}", (a, b), (c, d)


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--countries", nargs="+",
                    default=["us", "gb", "de", "jp"])
    ap.add_argument("--tiers", nargs="+",
                    default=["residential", "static", "mobile"],
                    choices=["residential", "static", "mobile"])
    ap.add_argument("--smart", action="store_true",
                    help="test only proxy='smart', which lets Solari pick and "
                         "rotate the egress when a site blocks it")
    ap.add_argument("--sticky", action="store_true",
                    help="check that a pinned session id holds one exit IP, "
                         "which is what the search code relies on")
    ap.add_argument("--timeout", type=int, default=45)
    ap.add_argument("--concurrency", type=int, default=8)
    args = ap.parse_args()

    load_env()
    solari = Solari(api_key=os.environ["SOLARI_API_KEY"])
    gate = asyncio.Semaphore(args.concurrency)

    if args.sticky:
        tier = args.tiers[0]
        print(f"sticky check on {tier}: two loads pinned, two loads loose\n")
        rows = await asyncio.gather(*(
            check_sticky(solari, gate, c, tier, args.timeout)
            for c in args.countries))
        width = max(len(label) for label, *_ in rows)
        held = 0
        for label, (a, b), (c, d) in rows:
            same = a == b and not a.startswith("<")
            held += same
            print(f"  {label:>{width}}  pinned {'HELD ' if same else 'MOVED'} "
                  f"{a} -> {b}")
            print(f"  {'':>{width}}  loose  {'same ' if c == d else 'moved'} "
                  f"{c} -> {d}")
        print(f"\n{held}/{len(rows)} held one IP across the pinned pair")
        return

    jobs = [("smart", "smart")]
    if not args.smart:
        jobs += [(f"{c}/{t}", ProxyRequest(country=c, tier=t))
                 for c in args.countries for t in args.tiers]

    print(f"{len(jobs)} egress options, {args.timeout}s timeout each\n")
    rows = await asyncio.gather(*(
        check(solari, gate, label, spec, args.timeout) for label, spec in jobs))

    width = max(len(label) for label, *_ in rows)
    for label, good, detail in rows:
        print(f"  {label:>{width}}  {'OK  ' if good else 'FAIL'} {detail}")

    usable = [label for label, good, _ in rows if good]
    print(f"\n{len(usable)}/{len(rows)} usable: {' '.join(usable) or 'none'}")


if __name__ == "__main__":
    asyncio.run(main())
