"""Does the country you browse from change the price of the same seat?

    python compare.py --from DEL --to BOM --date 2026-10-15 \
        --countries us gb de jp au in br sg --sites kayak momondo --out round-a.json
    python compare.py ... --out round-b.json          # again, straight after
    python geodiff.py round-a.json round-b.json

The naive version of this question -- price the route from eight countries and
look for a country that differs -- produced a confident false positive here. One
sweep showed Delhi to Mumbai at $57 from seven countries and $69 from the US, on
two sites at once, which looked conclusive. Re-run twenty-three minutes later it
was $57 everywhere. The fare had moved, and the move happened to land on the US
search; both sites agreed because both were read in the same minute, so they
shared the artifact rather than confirming each other.

So a difference between countries means nothing until you know how much the
same country differs from itself. This reads two rounds of the same sweep and
reports both numbers:

  within a round   every country against a baseline country, same minute
  between rounds   every country against itself, minutes apart

A geographic price difference is only real if the first is bigger than the
second. Everything is matched on the individual flight -- carrier, departure,
arrival, stops -- because "the cheapest fare on the page" is a different seat in
different countries and comparing those measures nothing at all.
"""

import argparse
import collections
import json
import pathlib
import statistics
import sys


def flight_key(fare: dict) -> tuple:
    """One physical flight. Two pages agree on this or they are not comparable."""
    return (str(fare.get("airline")), fare.get("depart"), fare.get("arrive"),
            fare.get("stops"))


def load(path: str) -> dict:
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def prices(run: dict, site: str) -> dict[str, dict[tuple, int]]:
    """country -> {flight: price}, for the searches that came back."""
    out = {}
    for r in run.get("results") or []:
        if r.get("ok") and r["site"] == site:
            out[r["country"]] = {flight_key(f): f["price"] for f in r["fares"]}
    return out


def deltas(a: dict[tuple, int], b: dict[tuple, int]) -> list[int]:
    """b minus a, over the flights both pages actually listed."""
    return [b[k] - a[k] for k in set(a) & set(b)]


def describe(name: str, d: list[int]) -> str:
    if not d:
        return f"{name:>22}   no flight on both pages"
    moved = sum(1 for x in d if x != 0)
    return (f"{name:>22}   {len(d):>3} flights, {moved:>3} priced differently, "
            f"range {min(d):+d} to {max(d):+d}, median {statistics.median(d):+.0f}")


def egress_check(runs: list[dict]) -> None:
    """Did the browser actually come out where we asked it to?

    Worth proving rather than assuming: a proxy that quietly falls back to the
    nearest exit would make every country identical, and identical is exactly
    the result this is looking for.
    """
    print("== where the browsers actually egressed ==\n")
    seen = collections.defaultdict(collections.Counter)
    zones = collections.defaultdict(collections.Counter)
    for run in runs:
        for r in run.get("results") or []:
            if not r.get("ok"):
                continue
            seen[r["country"]][r.get("egress")] += 1
            zones[r["country"]][r.get("timezone")] += 1
    print(f"{'asked for':>10}  {'came out as':>28}  {'timezone reported'}")
    ok = True
    for c in sorted(seen):
        got = ", ".join(f"{k}x{v}" for k, v in seen[c].most_common())
        tz = ", ".join(f"{k}" for k, _ in zones[c].most_common(2))
        mark = "" if list(seen[c]) == [c] else "   <-- MISMATCH"
        if mark:
            ok = False
        print(f"{c:>10}  {got:>28}  {tz}{mark}")
    print("\nevery browser exited in the country it was asked for"
          if ok else "\nsome browsers did not exit where asked -- results are void")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rounds", nargs="+", help="two or more sweep files of the same route")
    ap.add_argument("--base", default="de", help="country everything is compared against")
    args = ap.parse_args()

    runs = [load(p) for p in args.rounds]
    egress_check(runs)

    sites = sorted({r["site"] for run in runs for r in run.get("results") or []
                    if r.get("ok")})

    for site in sites:
        per_round = [prices(run, site) for run in runs]
        print(f"== {site} ==")

        # The noise floor: the same country, minutes apart, nothing else changed.
        floor = []
        for i in range(len(per_round) - 1):
            for c in sorted(set(per_round[i]) & set(per_round[i + 1])):
                d = deltas(per_round[i][c], per_round[i + 1][c])
                floor += d
                print(describe(f"{c} round{i+1}->round{i+2}", d))
        moved = sum(1 for x in floor if x != 0)
        print(f"\n  noise floor: {len(floor)} same-country comparisons, "
              f"{moved} moved"
              + (f", largest move ${max(abs(x) for x in floor)}" if floor else ""))

        # The question: a different country, read in the same minute.
        print(f"\n  against {args.base}, within the same round:")
        biggest = 0
        for i, snap in enumerate(per_round):
            if args.base not in snap:
                continue
            for c in sorted(snap):
                if c == args.base:
                    continue
                d = deltas(snap[args.base], snap[c])
                if d:
                    biggest = max(biggest, max(abs(x) for x in d))
                print(describe(f"round{i+1} {args.base}->{c}", d))

        floor_max = max((abs(x) for x in floor), default=0)
        print()
        if biggest == 0:
            print(f"  VERDICT: no flight is priced differently in any country. "
                  f"(fare moved by up to ${floor_max} on its own)")
        elif biggest <= floor_max:
            print(f"  VERDICT: largest country difference ${biggest} is within the "
                  f"${floor_max} the fare moves by itself. Not a geographic effect.")
        else:
            print(f"  VERDICT: largest country difference ${biggest} exceeds the "
                  f"${floor_max} noise floor. Worth pursuing.")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
