"""Turn a Google Flights results page into structured itineraries.

Parsed from the page's visible TEXT rather than its DOM. Google's class names
are obfuscated and rotate; the text layout ("9:35 AM – 9:40 PM", airline,
duration, "Nonstop", "$793", "round trip") is what a human reads and is far
more stable.
"""

import re
from dataclasses import dataclass, asdict

PRICE = re.compile(r"^([$£€₹¥₩])\s?([\d,]+)$")
TIME_RANGE = re.compile(r"^\d{1,2}:\d{2}\s?(AM|PM)(\+\d)?$", re.I)
DURATION = re.compile(r"^\d+\s*hr(\s*\d+\s*min)?$", re.I)
ROUTE = re.compile(r"^[A-Z]{3}[–-][A-Z]{3}$")


@dataclass
class Itinerary:
    price: int
    currency: str
    depart: str | None
    arrive: str | None
    airline: str | None
    duration: str | None
    route: str | None
    stops: str | None


def cheapest_headline(text: str) -> int | None:
    """The 'Cheapest from $597' banner, when Google shows one."""
    match = re.search(r"Cheapest\s*\n?\s*from\s*[$£€₹¥₩]\s?([\d,]+)", text)
    return int(match.group(1).replace(",", "")) if match else None


def itineraries(text: str) -> list[Itinerary]:
    """Every priced flight block on the page.

    A price line is the anchor: prices are followed by 'round trip' or 'one
    way', and the itinerary details sit in the ~12 lines above it.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out: list[Itinerary] = []

    for i, line in enumerate(lines):
        money = PRICE.match(line)
        if not money:
            continue

        window = lines[max(0, i - 12):i]
        times = [w for w in window if TIME_RANGE.match(w)]
        duration = next((w for w in window if DURATION.match(w)), None)
        route = next((w for w in window if ROUTE.match(w)), None)

        # Round-trip results label the price 'round trip'/'one way' on the next
        # line; one-way results label nothing at all. Either the label or a
        # 'JFK-LHR' route line above marks this as a real itinerary rather than
        # a filter-sidebar price.
        following = lines[i + 1] if i + 1 < len(lines) else ""
        labelled = re.match(r"^(round trip|one way)$", following, re.I)
        if not labelled and not route:
            continue
        stops = next((w for w in window
                      if re.match(r"^(Nonstop|\d+ stops?)$", w, re.I)), None)
        # The airline line sits between the times and the duration.
        airline = None
        if duration in window:
            idx = window.index(duration)
            for w in reversed(window[:idx]):
                if not TIME_RANGE.match(w) and w != "–" and len(w) > 2:
                    airline = w
                    break

        out.append(Itinerary(
            price=int(money.group(2).replace(",", "")),
            currency=money.group(1),
            depart=times[0] if times else None,
            arrive=times[1] if len(times) > 1 else None,
            airline=airline,
            duration=duration,
            route=route,
            stops=stops,
        ))
    return out


def summarise(text: str) -> dict:
    flights = itineraries(text)
    return {
        "headline_cheapest": cheapest_headline(text),
        "count": len(flights),
        "cheapest": min((f.price for f in flights), default=None),
        "currency": flights[0].currency if flights else None,
        "flights": [asdict(f) for f in flights],
    }
