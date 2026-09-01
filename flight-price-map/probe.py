"""First contact: does stealth + residential proxy work, and what do we see?"""
import asyncio, os, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
for line in pathlib.Path(__file__).with_name(".env").read_text().splitlines():
    if line.strip() and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

from solari_browser import Solari

SHOTS = pathlib.Path(__file__).parent / "shots"
ROUTE = "https://www.google.com/travel/flights?q=flights%20from%20JFK%20to%20LHR%20on%202026-10-15"


async def check(solari, country: str):
    browser = await solari.launch(stealth=True, proxy=country)
    try:
        page = await browser.new_page()
        # Confirm the egress IP is really in that country before trusting prices.
        await page.goto("https://api.ipify.org?format=json", timeout=45000)
        ip = await page.locator("pre").inner_text()
        print(f"[{country}] egress {ip.strip()}  proxy={getattr(browser, 'proxy', None)}")

        await page.goto(ROUTE, timeout=60000)
        await asyncio.sleep(6)
        title = await page.title()
        body = await page.locator("body").inner_text()
        SHOTS.mkdir(exist_ok=True)
        (SHOTS / f"gflights_{country}.png").write_bytes(await page.screenshot(full_page=False))
        (SHOTS / f"gflights_{country}.txt").write_text(body[:6000], encoding="utf-8")
        # Look for currency-shaped strings to see whether prices are even present.
        import re
        prices = re.findall(r"[$£€₹¥]\s?\d[\d,]*", body)
        print(f"[{country}] title={title[:60]!r} textlen={len(body)} price-like={prices[:8]}")
    finally:
        await browser.close()


async def main():
    solari = Solari(api_key=os.environ["SOLARI_API_KEY"])
    for country in ("us", "gb"):
        try:
            await check(solari, country)
        except Exception as e:
            print(f"[{country}] FAILED {type(e).__name__}: {str(e)[:200]}")


asyncio.run(main())
