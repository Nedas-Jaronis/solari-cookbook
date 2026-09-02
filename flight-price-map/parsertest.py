"""Guard the readers against the bugs they have already had.

    python parsertest.py

Every parser fault in this project has been silent: a count that looked right
while describing the wrong leg, a flight listed four times because three sites
spell one departure differently, a fare doubled because a one-date search
quietly returned round trips. None of them raised anything. Each check below
is a fault that actually shipped.

Fixtures are real captures, kept small and committed, so a reader can be
changed without spending a browser to find out what broke.
"""

import json
import sys

import itineraries
import sites
from common import HERE, Fare, ground, plausible
from sites import CARD

FIXTURES = HERE / "fixtures"


def load(name: str) -> str:
    path = FIXTURES / name
    if not path.exists():
        raise SystemExit(f"missing fixture {path}. Run capture.py, then "
                         f"python parsertest.py --record")
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures = []

    def check(label, got, want=None, at_least=None):
        ok = got >= at_least if at_least is not None else got == want
        print(f"  {'PASS' if ok else 'FAIL'}  {label}: {got!r}")
        if not ok:
            failures.append(label)

    print("\n-- one-way results --")
    one = sites.read_kayak(load("kayak-oneway.txt"))
    check("fares read", len(one), at_least=20)
    check("one leg each, not two", sum(1 for f in one if f.back_depart), 0)
    check("cheapest is the first Kayak lists", min(f.price for f in one), 286)
    check("carries an airline", sum(1 for f in one if f.airline), at_least=20)

    print("\n-- next-day arrivals are kept --")
    # A flight landing 10:35am+1 lands tomorrow. Dropping the marker tells a
    # traveller the wrong day, and nothing downstream can recover it.
    check("arrivals marked +1", sum(1 for f in one if "+" in str(f.arrive)),
          at_least=10)

    print("\n-- round trips are one fare with two legs --")
    both = sites.read_kayak(load("momondo-return.txt"))
    check("fares read", len(both), at_least=20)
    check("every fare has a return leg",
          sum(1 for f in both if f.back_depart), len(both))
    # The bug: the reader reported the return leg as the whole trip, so the
    # outbound airline vanished and the times were the way home.
    first = min(both, key=lambda f: f.price)
    check("outbound is the outbound", first.airline, "JetBlue")
    check("and the way back is separate", first.back_airline, "SWISS")
    check("one price for the pair", first.price, 747)

    print("\n-- a one-date Google search must not return round trips --")
    # Without "one way" in the query Google answers with return fares, roughly
    # double, and nothing flags it.
    gone = sites.read_google(load("google-oneway.txt"))
    check("fares read", len(gone), at_least=15)
    check("priced like a one-way, not a return",
          max(f.price for f in gone) < 500, True)

    print("\n-- the same flight is one flight --")
    # Three sites spell one departure "6:20 pm", "6:20 PM" and "6:20pm", and
    # Kayak sells it under two ticketing agents. That is one flight.
    runs = [json.loads((HERE / n).read_text(encoding="utf-8"))
            for n in ("results.json",) if (HERE / n).exists()]
    if runs:
        flights = itineraries.collect(runs)
        lgw = [f for f in flights if f["destination"] == "LGW"
               and f["depart_at"] == 18 * 60 + 20 and f["minutes"] == 420]
        check("one entry for the 6:20pm Gatwick nonstop", len(lgw), 1)
        if lgw:
            check("carrying every site that sells it",
                  len(lgw[0]["offers"]), at_least=3)
            check("named for the airline, not the ticketing agent",
                  lgw[0]["airline"], "Norse Atlantic UK")

    print("\n-- carrier names --")
    check("codeshare tail stripped",
          itineraries.carrier("British AirwaysAmerican, Iberia, Finnair"),
          "British Airways")
    check("but a real name is left alone", itineraries.carrier("JetBlue"),
          "JetBlue")
    check("operated-by stripped",
          itineraries.carrier("SWISSOperated by Helvetic"), "SWISS")

    print("\n-- buses and trains are not flights --")
    # A real Boston-area search: Kayak put a seven-hour, $44 Flix coach out of
    # Manchester above every flight, where being the lowest number on the page
    # wins the headline.
    coach = "\n".join([
        CARD, "6:30 am - 2:20 pm", "Flix", "7h 50m", "MHT", "$44", "Kayak",
        CARD, "9:35 am - 11:01 am", "JetBlue", "1h 26m", "Nonstop", "BOS",
        "$117", "Kayak",
        CARD, "7:15 am - 8:44 am", "Delta", "1h 29m", "Nonstop", "BOS",
        "$119", "Kayak",
    ])
    read = sites.read_kayak(coach)
    check("the coach is dropped", [f.airline for f in read],
          ["JetBlue", "Delta"])
    check("and the flights are not", [f.price for f in read], [117, 119])
    check("brand variants too",
          [ground(n) for n in ("Flix", "FlixBus", "Flixtrain", "Greyhound",
                               "Amtrak", "ALSA", "peter pan", "OuiGo")],
          [True] * 8)
    check("airlines pass through",
          [ground(n) for n in ("JetBlue", "Delta", "Air France", "Iberia",
                               "Aer Lingus", "Alaska", "Spirit", "Vueling",
                               "ITA Airways", "Norse Atlantic", "Play", None)],
          [False] * 12)
    check("a coach return leg disqualifies the trip too",
          plausible([Fare(price=88, airline="Delta", back_airline="Flix")]), [])

    print(f"\nfailures: {failures or 'none'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
