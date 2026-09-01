"""Which proxy countries actually connect, and how fast?

Worth knowing before blaming the target site: a country whose residential pool
is slow or empty looks exactly like the page failing to load.
"""
import asyncio, os, pathlib, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import pricemap
pricemap.load_env()
from solari_browser import Solari

COUNTRIES = ["us", "ca", "gb", "de", "fr", "nl", "es", "it", "au", "jp", "sg", "in", "br", "mx"]


async def check(solari, gate, country):
    async with gate:
        t0 = time.time()
        browser = None
        try:
            browser = await solari.launch(stealth=True, proxy=country)
            page = await browser.new_page()
            await page.goto("https://api.ipify.org?format=json", timeout=40_000)
            ip = (await page.locator("pre").inner_text()).strip()
            return country, True, f"{time.time()-t0:.0f}s {ip}"
        except Exception as e:
            return country, False, f"{time.time()-t0:.0f}s {type(e).__name__}"
        finally:
            if browser:
                try: await browser.close()
                except Exception: pass


async def main():
    solari = Solari(api_key=os.environ["SOLARI_API_KEY"])
    gate = asyncio.Semaphore(7)
    rows = await asyncio.gather(*(check(solari, gate, c) for c in COUNTRIES))
    ok = [c for c, good, _ in rows if good]
    for c, good, detail in rows:
        print(f"  {c:>3} {'OK  ' if good else 'FAIL'} {detail}")
    print(f"\nusable: {' '.join(ok)}")


asyncio.run(main())
