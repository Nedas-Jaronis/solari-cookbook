"""Walk the traveller flow the way a person would, and fail loudly if it breaks.

    python trip.py --standalone --out preview.html
    python flowtest.py

Screenshots prove a page renders; they do not prove the search works, the
filters filter, or the saved flight survives a reload. This drives the real
page in a real browser and checks what a user would notice.

Counts are derived from the data rather than hard-coded, so the test keeps
telling the truth when the underlying run changes.
"""

import argparse
import json
import sys

from patchright.sync_api import sync_playwright

import itineraries
from common import HERE


def expected(runs: list[str]) -> dict:
    loaded = [json.loads((HERE / r).read_text(encoding="utf-8"))
              for r in runs if (HERE / r).exists()]
    flights = itineraries.collect(loaded)
    oneway = [f for f in flights if not f["ret"]]
    ret = [f for f in flights if f["ret"]]
    return {
        "total": len(oneway),
        "nonstop": sum(1 for f in oneway if f["stops"] == 0),
        "lhr": sum(1 for f in oneway if f["destination"] == "LHR"),
        "best": f"${min(f['price'] for f in oneway):,}",
        "return_total": len(ret),
        "return_best": f"${min((f['price'] for f in ret), default=0):,}",
    }


# The trip id spells out the trip type, so a one-way link can never open a
# return search by accident.
ONEWAY = "#/jfk-lon-2026-10-15-ow"
RETURN = "#/jfk-lon-2026-10-15-rt"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--page", default="preview.html")
    ap.add_argument("--runs", nargs="+",
                    default=["results.json", "countries.json",
                             "roundtrip.json"])
    args = ap.parse_args()

    want = expected(args.runs)
    url = (HERE / args.page).resolve().as_uri()
    errors, failures = [], []

    def check(label, got, target=None, truthy=False):
        ok = bool(got) if truthy else (got == target)
        print(f"  {'PASS' if ok else 'FAIL'}  {label}: {got!r}")
        if not ok:
            failures.append(f"{label} (wanted {target!r})")

    with sync_playwright() as play:
        browser = play.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 900})
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console",
                lambda m: errors.append(m.text) if m.type == "error" else None)

        print("\n-- landing --")
        page.goto(url); page.wait_for_timeout(900)
        check("landing shown", page.eval_on_selector("#landing", "e=>!e.hidden"), True)
        check("results hidden", page.eval_on_selector("#results", "e=>e.hidden"), True)

        print("\n-- what a person might actually type --")
        for frm, to in [("New York JFK", "London"), ("JFK", "LHR"),
                        ("new york", "gatwick"), ("JFK", "lon"),
                        ("New York", "Stansted")]:
            page.goto(url); page.wait_for_timeout(350)
            page.fill("#from", frm); page.fill("#to", to)
            page.click(".go"); page.wait_for_timeout(450)
            check(f"{frm!r} -> {to!r}",
                  page.eval_on_selector("#results", "e=>!e.hidden"), True)

        print("\n-- the answer --")
        page.goto(url); page.wait_for_timeout(350)
        page.fill("#from", "New York JFK"); page.fill("#to", "London")
        page.click(".go"); page.wait_for_timeout(600)
        check("url carries the search", page.evaluate("location.hash"),
              ONEWAY)
        check("best fare", page.eval_on_selector(".pick-price", "e=>e.textContent.trim()"),
              want["best"])
        check("names a site to book on",
              page.eval_on_selector("#pick", "e=>/Book on \\w/.test(e.textContent)"), True)
        check("all flights offered",
              page.eval_on_selector("#tally", "e=>e.textContent"),
              f"{want['total']} of {want['total']} flights")
        check("same flight priced elsewhere too",
              page.eval_on_selector(".flight .elsewhere", "e=>e.textContent.trim()"),
              truthy=True)

        print("\n-- reveal every flight --")
        while page.query_selector("#more"):
            page.click("#more"); page.wait_for_timeout(220)
        check("every flight rendered",
              page.eval_on_selector_all(".flight", "e=>e.length"), want["total"])

        print("\n-- filters and sorting --")
        page.click('.pill[data-value="0"]'); page.wait_for_timeout(250)
        check("nonstop only", page.eval_on_selector("#tally", "e=>e.textContent"),
              f"{want['nonstop']} of {want['total']} flights")
        page.click('.pill[data-value="any"]'); page.wait_for_timeout(200)
        page.click('.pill[data-value="LHR"]'); page.wait_for_timeout(250)
        check("Heathrow only", page.eval_on_selector("#tally", "e=>e.textContent"),
              f"{want['lhr']} of {want['total']} flights")
        check("and every card really is LHR", page.eval_on_selector_all(
            ".flight .tag:last-child",
            "els=>[...new Set(els.map(e=>e.textContent))].join()"), "LHR")
        page.click('.pill[data-value="all"]'); page.wait_for_timeout(200)
        page.click('.pill[data-value="price"]'); page.wait_for_timeout(250)
        prices = page.eval_on_selector_all(
            ".flight .amount",
            "els=>els.map(e=>+e.textContent.replace(/[^0-9]/g,''))")
        check("cheapest first", prices == sorted(prices), True)

        print("\n-- saving --")
        page.click(".flight .save"); page.wait_for_timeout(200)
        check("save sticks", page.eval_on_selector(".flight .save", "e=>e.textContent"),
              "Saved")
        page.click("#savedonly"); page.wait_for_timeout(250)
        check("saved only", page.eval_on_selector("#tally", "e=>e.textContent"),
              f"1 of {want['total']} flights")
        page.reload(); page.wait_for_timeout(900)
        check("survives a reload",
              page.eval_on_selector(".flight .save", "e=>e.textContent"), "Saved")

        print("\n-- choosing nonstop before searching --")
        page.goto(url); page.wait_for_timeout(350)
        page.fill("#from", "New York JFK"); page.fill("#to", "London")
        page.select_option("#stops", "0")
        page.click(".go"); page.wait_for_timeout(600)
        check("pre-filtered to nonstop",
              page.eval_on_selector("#tally", "e=>e.textContent"),
              f"{want['nonstop']} of {want['total']} flights")
        check("the choice rides in the link", page.evaluate("location.hash"),
              ONEWAY + "?stops=0")
        check("and the pill agrees", page.eval_on_selector(
            '.pill[data-value="0"]', "e=>e.getAttribute('aria-pressed')"), "true")
        page.click('.pill[data-value="any"]'); page.wait_for_timeout(250)
        check("widening drops it from the link",
              page.evaluate("location.hash"), ONEWAY)
        check("and shows everything again",
              page.eval_on_selector("#tally", "e=>e.textContent"),
              f"{want['total']} of {want['total']} flights")

        print("\n-- a nonstop deep link --")
        page.goto(url + ONEWAY + "?stops=0"); page.wait_for_timeout(800)
        check("opens already filtered",
              page.eval_on_selector("#tally", "e=>e.textContent"),
              f"{want['nonstop']} of {want['total']} flights")

        print("\n-- a return trip --")
        page.goto(url); page.wait_for_timeout(350)
        page.fill("#from", "New York JFK"); page.fill("#to", "London")
        page.select_option("#trip", "return")
        page.click(".go"); page.wait_for_timeout(700)
        check("opens the return search", page.evaluate("location.hash"),
              RETURN)
        check("its own flights, not the one-way ones",
              page.eval_on_selector("#tally", "e=>e.textContent"),
              f"{want['return_total']} of {want['return_total']} flights")
        check("best return fare",
              page.eval_on_selector(".pick-price", "e=>e.textContent.trim()"),
              want["return_best"])
        check("the pick names the way back",
              page.eval_on_selector("#pick", "e=>e.textContent.includes('Back')"), True)
        check("summary shows a return date", page.eval_on_selector_all(
            "#summary .k", "els=>els.some(e=>e.textContent==='Return')"), True)
        check("every card carries two legs", page.eval_on_selector_all(
            ".flight:first-child .way", "els=>els.map(e=>e.textContent).join()"),
            "Out,Back")
        page.click("#back"); page.wait_for_timeout(300)
        page.select_option("#trip", "oneway"); page.click(".go")
        page.wait_for_timeout(600)
        check("and one way is untouched by it",
              page.eval_on_selector_all(".flight:first-child .legrow", "e=>e.length"), 1)

        print("\n-- deep link and back --")
        page.goto(url + ONEWAY); page.wait_for_timeout(800)
        check("deep link opens results",
              page.eval_on_selector("#results", "e=>!e.hidden"), True)
        page.click("#back"); page.wait_for_timeout(350)
        check("back to search",
              page.eval_on_selector("#landing", "e=>!e.hidden"), True)

        print("\n-- a route we have not priced --")
        # Reload rather than trusting the last section's state: navigating to
        # the same URL with a different hash does not reload, so form controls
        # keep whatever they were last set to.
        page.reload(); page.wait_for_timeout(700)
        page.fill("#from", "New York JFK"); page.fill("#to", "Paris")
        page.click(".go"); page.wait_for_timeout(350)
        check("says so rather than inventing one", page.eval_on_selector(
            ".nope", "e=>e.textContent.includes('not priced')"), True)
        check("stays on the search",
              page.eval_on_selector("#results", "e=>e.hidden"), True)
        page.click(".nope .linkish"); page.wait_for_timeout(450)
        check("and the route it offers works",
              page.eval_on_selector("#results", "e=>!e.hidden"), True)

        browser.close()

    print(f"\nconsole errors: {errors or 'none'}")
    if errors:
        failures.append(f"{len(errors)} console error(s)")
    print(f"failures: {failures or 'none'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
