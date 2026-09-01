"""Which sites we price, how to reach them, and how to read them.

Every site is one `Site`: build a URL for a search, wait for results to settle,
then turn the page's visible text into `Fare`s. Parsers work on text rather
than the DOM -- travel sites obfuscate and rotate their class names, but the
words a human reads stay put. Where a site ships screen-reader summary lines
("Select Aer Lingus flight, departing at ...") we parse those: they are the
most stable thing on the page.
"""

import re
import urllib.parse
from dataclasses import dataclass
from typing import Callable

from common import Fare, Query, money, plausible

DURATION = re.compile(r"^\d+\s*h(r|ours?)?(\s*\d+\s*m(in)?)?$", re.I)
STOPS = re.compile(r"^(nonstop|direct|\d+\s*stops?)$", re.I)


@dataclass
class Site:
    key: str
    name: str
    build: Callable[[Query], str]
    read: Callable[[str], list[Fare]]
    patience: int = 15        # seconds to keep waiting for results to appear
    metro: bool = False       # accepts metro codes (NYC, LON) as an origin
    note: str = ""


# --------------------------------------------------------------------------
# URL builders
# --------------------------------------------------------------------------

def google_url(q: Query) -> str:
    # "one way" is load-bearing: left off, Google answers a one-date search with
    # round-trip fares, and we would be comparing them against everyone else's
    # one-way fares -- roughly double, and wrong in a way nothing flags.
    trip = "round trip" if q.ret else "one way"
    query = f"{trip} flights from {q.origin} to {q.destination} on {q.date}"
    if q.ret:
        query += f" through {q.ret}"
    return ("https://www.google.com/travel/flights?curr=USD&hl=en&q="
            + urllib.parse.quote(query))


def kayak_url(q: Query) -> str:
    legs = f"{q.origin}-{q.destination}/{q.date}" + (f"/{q.ret}" if q.ret else "")
    return f"https://www.kayak.com/flights/{legs}?sort=price_a&currency=USD"


def momondo_url(q: Query) -> str:
    legs = f"{q.origin}-{q.destination}/{q.date}" + (f"/{q.ret}" if q.ret else "")
    return f"https://www.momondo.com/flight-search/{legs}?sort=price_a&currency=USD"


def expedia_url(q: Query) -> str:
    leg1 = f"from:{q.origin},to:{q.destination},departure:{q.us_date('date')}TANYT"
    parts = [f"trip={'roundtrip' if q.ret else 'oneway'}", f"leg1={leg1}"]
    if q.ret:
        parts.append(f"leg2=from:{q.destination},to:{q.origin},"
                     f"departure:{q.us_date('ret')}TANYT")
    parts += ["passengers=adults:1", "options=cabinclass:economy",
              "mode=search", "sort=PRICE_INCREASING"]
    return "https://www.expedia.com/Flights-Search?" + "&".join(parts)


def kiwi_url(q: Query) -> str:
    # Kiwi needs the return leg spelled out; without it the search never runs.
    legs = f"{q.origin}/{q.destination}/{q.date}/" + (q.ret if q.ret else "no-return")
    return f"https://www.kiwi.com/en/search/results/{legs}?sortBy=price"


def skyscanner_url(q: Query) -> str:
    legs = (f"{q.origin.lower()}/{q.destination.lower()}/{q.compact('date')}"
            + (f"/{q.compact('ret')}" if q.ret else ""))
    return f"https://www.skyscanner.com/transport/flights/{legs}/?currency=USD&adults=1"


def priceline_url(q: Query) -> str:
    legs = f"{q.origin}-{q.destination}-{q.date.replace('-', '')}"
    if q.ret:
        legs += f"/{q.destination}-{q.origin}-{q.ret.replace('-', '')}"
    return f"https://www.priceline.com/m/fly/search/{legs}/?cabin-class=ECO&num-adults=1"


# --------------------------------------------------------------------------
# Readers
# --------------------------------------------------------------------------

def generic_read(text: str) -> list[Fare]:
    """Every standalone price on the page, with no itinerary detail.

    Enough to prove a site loaded and is quoting fares, nothing more.
    """
    out = []
    for line in text.splitlines():
        m = money(line)
        if m:
            out.append(Fare(price=m[1], currency=m[0]))
    return plausible(out)


def read_google(text: str) -> list[Fare]:
    """Google Flights: a price line anchors each result, details sit above it."""
    import parse
    return plausible([
        Fare(price=f["price"], currency=f["currency"], airline=f["airline"],
             depart=f["depart"], arrive=f["arrive"], duration=f["duration"],
             stops=f["stops"])
        for f in parse.summarise(text)["flights"]])


KAYAK_TIMES = re.compile(
    r"^(\d{1,2}:\d{2}\s?[ap]m)\s*[–-]\s*(\d{1,2}:\d{2}\s?[ap]m)(\+\d)?$", re.I)


def read_kayak(text: str) -> list[Fare]:
    """Kayak and Momondo (same engine): a time range opens each result card.

    Anchoring on the time range skips the sponsored blocks, which carry a
    price but no itinerary line.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out = []
    for i, line in enumerate(lines):
        times = KAYAK_TIMES.match(line)
        if not times:
            continue
        window = lines[i + 1:i + 16]
        price = next((money(w) for w in window if money(w)), None)
        if not price:
            continue
        out.append(Fare(
            price=price[1], currency=price[0],
            airline=window[0] if window else None,
            depart=times.group(1), arrive=times.group(2),
            duration=next((w for w in window if DURATION.match(w)), None),
            stops=next((w for w in window if STOPS.match(w)), None),
        ))
    return plausible(out)


EXPEDIA_CARD = re.compile(
    r"Select (?P<airline>.+?) flight, departing at (?P<dep>\d{1,2}:\d{2}\s?[ap]m), "
    r"arriving at (?P<arr>\d{1,2}:\d{2}\s?[ap]m).*?priced at \$(?P<price>[\d,]+)", re.I)


def read_expedia(text: str) -> list[Fare]:
    """Expedia: the 'Select ... flight' line is a screen-reader summary.

    One line carries airline, both times, the price and the stop count, and it
    changes far less often than the visual markup around it.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out = []
    for i, line in enumerate(lines):
        m = EXPEDIA_CARD.search(line)
        if not m:
            continue
        stops = re.search(r"(Nonstop|One stop|\d+ stops?)", line, re.I)
        duration = None
        for w in lines[i + 1:i + 12]:
            head = w.split("•")[0].strip()
            if "•" in w and DURATION.match(head):
                duration = head
                break
        out.append(Fare(
            price=int(m.group("price").replace(",", "")),
            airline=m.group("airline"), depart=m.group("dep"),
            arrive=m.group("arr"), duration=duration,
            stops=stops.group(1) if stops else None,
        ))
    return plausible(out)


SKY_OPTION = re.compile(
    r"^Flight option \d+:(?P<ad> Ad by .+?\.)? Total cost \$(?P<price>[\d,]+)\.")
SKY_TIMES = re.compile(r"Departing from .+? at (?P<dep>\d{1,2}:\d{2}\s?[AP]M), "
                       r"arriving in .+? at (?P<arr>\d{1,2}:\d{2}\s?[AP]M)")
SKY_LEG = re.compile(r"^(?P<stops>Direct|\d+ stops?) flight taking (?P<dur>[^.]+)\.",
                     re.M)


def read_skyscanner(text: str) -> list[Fare]:
    """Skyscanner: each card opens with a 'Flight option N' summary line.

    Sponsored cards say 'Ad by <airline>' and are skipped -- a paid placement
    is not the cheapest fare its position implies.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out = []
    for i, line in enumerate(lines):
        m = SKY_OPTION.match(line)
        if not m or m.group("ad"):
            continue
        window = "\n".join(lines[i + 1:i + 6])
        airline = re.search(r"^Flight with (.+?)\.", window, re.M)
        times = SKY_TIMES.search(window)
        leg = SKY_LEG.search(window)
        out.append(Fare(
            price=int(m.group("price").replace(",", "")),
            airline=airline.group(1) if airline else None,
            depart=times.group("dep") if times else None,
            arrive=times.group("arr") if times else None,
            duration=leg.group("dur") if leg else None,
            stops=leg.group("stops") if leg else None,
        ))
    return plausible(out)


SITES: list[Site] = [
    Site("google", "Google Flights", google_url, read_google, patience=30, metro=True),
    Site("kayak", "Kayak", kayak_url, read_kayak, patience=70, metro=True,
         note="search polls; under ~35s the page is still filling in"),
    Site("momondo", "Momondo", momondo_url, read_kayak, patience=70, metro=True,
         note="same engine as Kayak"),
    Site("expedia", "Expedia", expedia_url, read_expedia, patience=60),
    Site("skyscanner", "Skyscanner", skyscanner_url, read_skyscanner, patience=55),
    Site("kiwi", "Kiwi", kiwi_url, generic_read, patience=40),
    Site("priceline", "Priceline", priceline_url, generic_read, patience=45),
]

BY_KEY = {s.key: s for s in SITES}
