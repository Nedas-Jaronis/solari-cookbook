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
"""

import argparse
import asyncio
import os
import time

from solari_browser import ProxyRequest, Solari

from common import load_env

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
    ap.add_argument("--timeout", type=int, default=45)
    ap.add_argument("--concurrency", type=int, default=8)
    args = ap.parse_args()

    load_env()
    solari = Solari(api_key=os.environ["SOLARI_API_KEY"])
    gate = asyncio.Semaphore(args.concurrency)

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
