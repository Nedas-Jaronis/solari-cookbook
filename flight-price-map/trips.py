"""Turn raw runs into the trips a traveller chooses between.

Shared by the static page and the live service so both describe a search the
same way. When the server answers a route nobody has priced before, it hands
back exactly the shape the page already knows how to render -- which is why
"any route" needed no new rendering code at all.
"""

from collections import defaultdict

import airports
import itineraries

CITY = {"LHR": "Heathrow", "LGW": "Gatwick", "STN": "Stansted",
        "LTN": "Luton", "LCY": "London City", "JFK": "New York JFK",
        "EWR": "Newark", "LGA": "LaGuardia", "TPA": "Tampa",
        "BCN": "Barcelona", "MAD": "Madrid", "CDG": "Paris CDG",
        "ORY": "Paris Orly", "FCO": "Rome Fiumicino", "AMS": "Amsterdam",
        "NRT": "Tokyo Narita", "HND": "Tokyo Haneda"}

METRO_CITY = {"LON": "London", "NYC": "New York", "PAR": "Paris",
              "TYO": "Tokyo", "MIL": "Milan", "ROM": "Rome", "CHI": "Chicago",
              "WAS": "Washington", "BOS": "Boston", "MIA": "Miami",
              "LAX": "Los Angeles", "SFO": "San Francisco", "TPA": "Tampa",
              "AMS": "Amsterdam", "BER": "Berlin"}


def pretty(iso: str) -> str:
    from datetime import date
    y, m, d = (int(x) for x in iso.split("-"))
    return date(y, m, d).strftime("%a %d %b %Y")


def label_for(code: str) -> str:
    """What a person calls this place: the city if we know it, else the code."""
    metro = airports.metro_of(code)
    return METRO_CITY.get(metro or "", CITY.get(code, code))


def build(runs: list[dict]) -> list[dict]:
    """One trip per origin, destination area, date and trip type we priced."""
    flights = itineraries.collect(runs)
    if not flights:
        return []

    grouped = defaultdict(list)
    for flight in flights:
        metro = airports.metro_of(flight["destination"]) or flight["destination"]
        grouped[(flight["origin"], metro, flight["date"],
                 flight["ret"] or "")].append(flight)

    out = []
    for (origin, metro, when, back), group in grouped.items():
        base = next((r for r in runs if r.get("date") == when
                     and (r.get("ret") or "") == back), runs[0])
        asked = base["destination"]
        at_asked = [f["price"] for f in group if f["destination"] == asked]
        every = [r for run in runs if run.get("date") == when
                 and (run.get("ret") or "") == back
                 for r in run.get("results", []) if r["origin"] == origin]
        from_label = label_for(origin)
        to_label = METRO_CITY.get(metro, CITY.get(metro, metro))
        nearby = airports.expand(metro)
        out.append({
            "id": f"{origin}-{metro}-{when}-{'rt' if back else 'ow'}".lower(),
            "kind": "return" if back else "oneway",
            "ret": back or None,
            "ret_label": pretty(back) if back else None,
            "from_label": from_label,
            "from_full": CITY.get(origin, origin),
            "to_label": to_label,
            # Everything a person might type that should find this trip.
            "from_keys": sorted({origin.lower(), from_label.lower(),
                                 CITY.get(origin, origin).lower()}),
            "to_keys": sorted({metro.lower(), to_label.lower()}
                              | {c.lower() for c in nearby}
                              | {CITY.get(c, c).lower() for c in nearby}),
            "date": when,
            "date_label": pretty(when),
            "read_at": base.get("generated_at", "")[:16].replace("T", " "),
            "flights": group,
            "asked_airport": CITY.get(asked, asked),
            "airport_saving": max(min(at_asked) - group[0]["price"], 0)
                              if at_asked else 0,
            "sites": len({r["site"] for r in every}),
            "airports": len({r["destination"] for r in every}),
            "searches": len(every),
            "seconds": round(sum(run.get("seconds", 0) for run in runs
                                 if run.get("date") == when
                                 and (run.get("ret") or "") == back)),
        })
    out.sort(key=lambda t: (t["kind"] != "oneway", t["date"]))
    return out
