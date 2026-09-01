"""Turn raw runs into the trips a traveller chooses between.

Shared by the static page and the live service so both describe a search the
same way. When the server answers a route nobody has priced before, it hands
back exactly the shape the page already knows how to render -- which is why
"any route" needed no new rendering code at all.
"""

from collections import defaultdict

import airports
import itineraries

# What each airport is called. Where a metro area has several, this is the
# airport's own name; the city goes in front when a label is built, so someone
# typing "london" is offered all five and not only London City.
CITY = {
    "LHR": "Heathrow", "LGW": "Gatwick", "STN": "Stansted", "LTN": "Luton",
    "LCY": "City", "JFK": "JFK", "EWR": "Newark", "LGA": "LaGuardia",
    "CDG": "Charles de Gaulle", "ORY": "Orly", "BVA": "Beauvais",
    "NRT": "Narita", "HND": "Haneda", "FCO": "Fiumicino", "CIA": "Ciampino",
    "MXP": "Malpensa", "LIN": "Linate", "BGY": "Bergamo", "ORD": "O'Hare",
    "MDW": "Midway", "IAD": "Dulles", "DCA": "Reagan", "BWI": "BWI",
    "OAK": "Oakland", "SJC": "San Jose", "BUR": "Burbank",
    "LGB": "Long Beach", "SNA": "John Wayne", "ONT": "Ontario",
    "FLL": "Fort Lauderdale", "PBI": "Palm Beach", "PIE": "St Pete",
    "SRQ": "Sarasota", "PVD": "Providence", "MHT": "Manchester NH",
    "RTM": "Rotterdam", "EIN": "Eindhoven",
    # Cities with one airport worth naming: the city is the name.
    "BCN": "Barcelona", "MAD": "Madrid", "LIS": "Lisbon", "OPO": "Porto",
    "CPH": "Copenhagen", "DUB": "Dublin", "ATH": "Athens", "IST": "Istanbul",
    "ZRH": "Zurich", "VIE": "Vienna", "PRG": "Prague", "BUD": "Budapest",
    "WAW": "Warsaw", "OSL": "Oslo", "ARN": "Stockholm", "HEL": "Helsinki",
    "KEF": "Reykjavik", "EDI": "Edinburgh", "MAN": "Manchester",
    "GLA": "Glasgow", "BHX": "Birmingham", "SEA": "Seattle",
    "PDX": "Portland", "DEN": "Denver", "AUS": "Austin", "DFW": "Dallas",
    "IAH": "Houston", "ATL": "Atlanta", "MCO": "Orlando", "RDU": "Raleigh",
    "PHL": "Philadelphia", "DTW": "Detroit", "MSP": "Minneapolis",
    "SLC": "Salt Lake City", "PHX": "Phoenix", "LAS": "Las Vegas",
    "SAN": "San Diego", "STL": "St Louis", "CLT": "Charlotte",
    "NAS": "Nassau", "SJU": "San Juan", "YYZ": "Toronto", "YUL": "Montreal",
    "YVR": "Vancouver", "MEX": "Mexico City", "CUN": "Cancun",
    "GRU": "Sao Paulo", "EZE": "Buenos Aires", "BOG": "Bogota",
    "LIM": "Lima", "SCL": "Santiago", "DXB": "Dubai", "DOH": "Doha",
    "SIN": "Singapore", "HKG": "Hong Kong", "ICN": "Seoul", "BKK": "Bangkok",
    "DEL": "Delhi", "BOM": "Mumbai", "KUL": "Kuala Lumpur", "TPE": "Taipei",
    "SYD": "Sydney", "MEL": "Melbourne", "AKL": "Auckland",
    "JNB": "Johannesburg", "CPT": "Cape Town", "CAI": "Cairo",
    "TLV": "Tel Aviv", "BER": "Berlin", "MUC": "Munich", "FRA": "Frankfurt",
    "DUS": "Dusseldorf", "HAM": "Hamburg", "BRU": "Brussels",
    "GVA": "Geneva", "NCE": "Nice", "MRS": "Marseille", "TLS": "Toulouse",
    "VCE": "Venice", "NAP": "Naples", "PMI": "Palma", "AGP": "Malaga",
    "VLC": "Valencia", "SVQ": "Seville", "BOS": "Boston", "MIA": "Miami",
    "TPA": "Tampa", "SFO": "San Francisco", "LAX": "Los Angeles",
    "AMS": "Amsterdam", "CHI": "Chicago", "NYC": "New York",
}


def place_label(code: str) -> str:
    """How the search box names an airport: city first, then the airport.

    "London Heathrow (LHR)" rather than "Heathrow (LHR)", because someone
    typing "london" should be offered all five, not only the one whose own
    name happens to contain the word.
    """
    name = CITY.get(code, code)
    city = METRO_CITY.get(airports.metro_of(code) or "", "")
    if city and city.lower() not in name.lower():
        name = f"{city} {name}"
    return f"{name} ({code})"

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
        # "New York JFK" -- the search-box label without its bracketed code.
        from_full = place_label(origin).rsplit(" (", 1)[0]
        out.append({
            "id": f"{origin}-{metro}-{when}-{'rt' if back else 'ow'}".lower(),
            "kind": "return" if back else "oneway",
            "ret": back or None,
            "ret_label": pretty(back) if back else None,
            "from_label": from_label,
            "from_full": from_full,
            "to_label": to_label,
            # Everything a person might type that should find this trip.
            # Everything a person might type for this origin: the code, the
            # city, the airport's own name, and the full label they would have
            # picked out of the suggestion list.
            "from_keys": sorted({origin.lower(), from_label.lower(),
                                 CITY.get(origin, origin).lower(),
                                 from_full.lower(),
                                 place_label(origin).lower()}),
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
