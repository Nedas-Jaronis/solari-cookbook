"""Price real routes on six continents and check we got flights, not buses.

    python server.py          # in one terminal
    python worldtest.py       # in another

`flowtest.py` drives the page and `parsertest.py` holds the readers to
committed fixtures. Neither one leaves the machine, so neither can answer the
question this does: does a route we have never priced, in a part of the world
we have no fixture for, come back as flights?

This costs Solari time -- four browsers per route, about twenty seconds each --
so it is not part of the ordinary loop. Run it when a reader changes, or before
showing the thing to anyone.

The routes are not a random spread. Half of them are corridors where a train or
a coach is the obvious way to travel, which is exactly where Kayak and Momondo
mix ground transport into flight results:

    LHR-CDG   Eurostar runs it in two and a half hours
    BCN-MAD   Renfe AVE, and ALSA coaches under it
    MUC-BER   Deutsche Bahn, and FlixBus under that

If a bus is going to win a fare anywhere, it wins there.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

from common import unrecognised

API = "http://localhost:8080"

# (origin, destination, what it is testing)
ROUTES = [
    ("LHR", "CDG", "Europe, and Eurostar competes"),
    ("BCN", "MAD", "Europe, and AVE plus coaches compete"),
    ("MUC", "BER", "Europe, and Deutsche Bahn plus FlixBus compete"),
    ("NRT", "ICN", "Asia"),
    ("SYD", "MEL", "Australia"),
    ("GRU", "EZE", "South America"),
    ("DXB", "BOM", "Middle East to India"),
    ("JNB", "CPT", "Africa"),
]

DATE = "2026-10-15"


def post(path: str, body: dict) -> dict:
    """A refusal is an answer, not a crash.

    The service rate-limits per IP, and a sweep of eight routes walks straight
    into that -- which is the limit doing its job. Report it against the route
    instead of taking the whole run down and wasting the browsers already
    spent on the routes that did answer.
    """
    req = urllib.request.Request(
        API + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as err:
        try:
            said = json.loads(err.read()).get("error", "")
        except Exception:
            said = ""
        return {"error": f"HTTP {err.code}: {said or err.reason}"}


def get(path: str) -> dict:
    with urllib.request.urlopen(API + path, timeout=30) as r:
        return json.loads(r.read())


def search(origin: str, dest: str, date: str, nearby: bool,
           fresh: bool = False, patience: int = 300) -> dict:
    """Ask, then wait. Returns the finished job however it finished.

    Not fresh by default. A route this has never priced is a cache miss and
    goes to the browsers anyway, so forcing it buys nothing and spends the
    re-check allowance -- a tighter limit than the ordinary one, and the reason
    five of eight routes came back refused on the first run of this sweep.
    """
    job = post("/api/search", {"from": origin, "to": dest, "date": date,
                               "nearby": nearby, "fresh": fresh})
    if "id" not in job:
        return {"phase": "error", "error": job.get("error", "no job id"),
                "trip": None, "answered": 0, "searched": 0, "seconds": 0}
    deadline = time.time() + patience
    while time.time() < deadline:
        time.sleep(4)
        job = get(f"/api/search/{job['id']}")
        if job["phase"] in ("done", "error", "failed"):
            return job
    return {**job, "phase": "timeout"}


def audit(job: dict) -> tuple[list[str], dict]:
    """What is wrong with this answer, and what it looked like."""
    faults = []
    flights = ((job.get("trip") or {}).get("flights")) or []
    seen = {"flights": len(flights), "cheapest": None, "carrier": None,
            "sites": 0, "buses": []}

    if job["phase"] != "done":
        faults.append(f"phase {job['phase']}: {job.get('error') or 'no error given'}")
        return faults, seen
    if not flights:
        faults.append("no flights at all")
        return faults, seen

    best = min(flights, key=lambda f: f["price"])
    seen["cheapest"] = best["price"]
    seen["carrier"] = best.get("airline")
    seen["sites"] = len({o["site"] for f in flights for o in f.get("offers", [])})

    # The whole point. Either leg being ground transport disqualifies it, and
    # the cheapest one matters most because it takes the headline.
    for f in flights:
        for leg in (f.get("airline"), f.get("back_airline")):
            if unrecognised(leg):
                seen["buses"].append(f"{leg} ${f['price']}")
    if seen["buses"]:
        faults.append(f"not-an-airline in the results: {seen['buses'][:3]}")

    if any(not f.get("airline") for f in flights):
        faults.append("a flight came back with no carrier")
    if not 20 <= best["price"] <= 20000:
        faults.append(f"cheapest ${best['price']} is not a plausible fare")
    if all(f.get("minutes") is None for f in flights):
        faults.append("no durations read")
    return faults, seen


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", default=DATE)
    ap.add_argument("--nearby", action="store_true",
                    help="also widen to nearby airports (three times the cost)")
    ap.add_argument("--route", action="append", metavar="FROM-TO",
                    help="test just this route; repeatable")
    ap.add_argument("--fresh", action="store_true",
                    help="ignore the cache; spends the tighter re-check budget")
    args = ap.parse_args()

    try:
        get("/api/health")
    except (urllib.error.URLError, OSError) as err:
        print(f"no server on {API} ({err}). Start it with: python server.py")
        return 2

    routes = ([(r.split("-")[0].upper(), r.split("-")[1].upper(), "asked for")
               for r in args.route] if args.route else ROUTES)

    # The limit lives in the server's environment, not this one, so there is
    # nothing here worth reading. Say what to do if it refuses instead.
    if len(routes) > 6:
        print(f"note: {len(routes)} searches. If the service starts refusing, "
              f"restart it with FARE_PER_IP_HOUR={len(routes) + 4}.\n")

    print(f"{len(routes)} routes, {args.date}, "
          f"{'with' if args.nearby else 'without'} nearby widening")
    print("egress is pinned to the US for every one of them "
          "(server.py builds every task with country 'us')\n")

    header = f"  {'route':<9} {'flights':>7} {'cheapest':>9} {'carrier':<20} {'sites':>5}  verdict"
    print(header)
    print("  " + "-" * (len(header) - 2))

    failures = []
    for origin, dest, why in routes:
        job = search(origin, dest, args.date, args.nearby, args.fresh)
        faults, seen = audit(job)
        verdict = "ok" if not faults else "; ".join(faults)
        print(f"  {origin}-{dest:<5} {seen['flights']:>7} "
              f"{('$' + str(seen['cheapest'])) if seen['cheapest'] else '-':>9} "
              f"{(seen['carrier'] or '-')[:20]:<20} {seen['sites']:>5}  {verdict}")
        if faults:
            failures.append((f"{origin}-{dest}", why, faults))

    print()
    if failures:
        print("failures:")
        for route, why, faults in failures:
            print(f"  {route} ({why})")
            for f in faults:
                print(f"      {f}")
        return 1
    print("every route returned flights, and not one bus or train among them")
    return 0


if __name__ == "__main__":
    sys.exit(main())
