"""Pull the prices a results page advertises but has not yet delivered.

Travel sites are full of numbers you did not search for: a strip of nearby
dates, each with a fare; a banner offering a different airport for less; a
sidebar quoting a "from" price per airline. Every one is a promise about a
search you have not run.

This module finds those promises. `verify.py` then runs the searches they imply
and reports whether the number was still there when you clicked through.

Nothing here assumes bad faith. A teaser can be stale cache, a fare class the
results page filters out, or a seat that sold in the meantime. The interesting
part is simply how often the advertised number is not the number you get.
"""

import re
from dataclasses import dataclass

from common import Query

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


@dataclass
class Claim:
    """One advertised price, and the search that would test it."""
    site: str
    kind: str                       # "date" or "airport"
    advertised: int
    source: str                     # the page text it came from, verbatim
    date: str | None = None         # for kind == "date"
    destination: str | None = None  # for kind == "airport"
    metro_wide: bool = False        # the price covers a whole metro area

    def query(self, base: Query, origin: str | None = None) -> Query:
        """The search this claim promises something about.

        `origin` overrides the searched origin, which matters for metro-wide
        claims: a sidebar price covering all of New York should be tested
        against all of New York, not just the airport you happened to type.
        """
        return Query(
            origin=origin or base.origin,
            destination=self.destination or base.destination,
            date=self.date or base.date,
            ret=base.ret,
        )

    @property
    def label(self) -> str:
        if self.kind == "date":
            return f"{self.date}"
        return f"{self.destination}"


def _iso(month_name: str, day: int, base_date: str) -> str | None:
    """'Oct' + 12, anchored to the searched date, as YYYY-MM-DD.

    A strip around a December search can run into January, so a month earlier
    than the one searched means the following year.
    """
    month = MONTHS.get(month_name[:3].lower())
    if not month:
        return None
    year, base_month = int(base_date[:4]), int(base_date[5:7])
    if month < base_month - 6:
        year += 1
    elif month > base_month + 6:
        year -= 1
    try:
        return f"{year:04d}-{month:02d}-{day:02d}"
    except ValueError:
        return None


DATE_LABEL = re.compile(r"^([A-Z][a-z]{2})\s+(\d{1,2})$")
PRICE_ONLY = re.compile(r"^\$([\d,]{2,6})$")


def date_strip(text: str, base: Query, site: str) -> list[Claim]:
    """A row of nearby dates, each captioned with a fare.

    Skyscanner renders this as alternating lines -- 'Oct 12' then '$267' --
    above the results. Each pair is a promise about a different search.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out: list[Claim] = []
    seen: set[str] = set()
    for i, line in enumerate(lines[:-1]):
        label = DATE_LABEL.match(line)
        price = PRICE_ONLY.match(lines[i + 1])
        if not (label and price):
            continue
        iso = _iso(label.group(1), int(label.group(2)), base.date)
        if not iso or iso in seen:
            continue
        seen.add(iso)
        out.append(Claim(site=site, kind="date", date=iso,
                         advertised=int(price.group(1).replace(",", "")),
                         source=f"{line} {lines[i + 1]}"))
    return out


GOOGLE_SWAP = re.compile(r"Fly to ([A-Z]{3}) for \$([\d,]+)")
KAYAK_SWAP = re.compile(r"Fly (?:nonstop )?to ([A-Z]{3}) and save \$([\d,]+)")


def airport_swap(text: str, base: Query, site: str) -> list[Claim]:
    """A banner offering a different airport for less.

    Google states the alternative's price outright ("Fly to LGW for $204").
    Kayak states the saving instead ("save $111"), with the price on a
    following 'from / $175' pair -- so we read that rather than doing the
    arithmetic, which would assume what its baseline was.
    """
    out: list[Claim] = []
    for match in GOOGLE_SWAP.finditer(text):
        out.append(Claim(site=site, kind="airport", destination=match.group(1),
                         advertised=int(match.group(2).replace(",", "")),
                         source=match.group(0)))

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for i, line in enumerate(lines):
        swap = KAYAK_SWAP.search(line)
        if not swap:
            continue
        price = next((PRICE_ONLY.match(w) for w in lines[i + 1:i + 5]
                      if PRICE_ONLY.match(w)), None)
        if price:
            out.append(Claim(site=site, kind="airport",
                             destination=swap.group(1),
                             advertised=int(price.group(1).replace(",", "")),
                             source=f"{line} -> ${price.group(1)}"))
    return out


def extract(text: str, base: Query, site: str) -> list[Claim]:
    """Every testable advertised price on this page.

    Claims for the exact search we already ran are dropped -- there is nothing
    to click through to, so there is nothing to verify.
    """
    found = (date_strip(text, base, site)
             + airport_swap(text, base, site)
             + airport_facets(text, base, site))
    # A banner and the sidebar often advertise the same airport; keep the
    # cheaper claim, which is the one the site is really promising.
    best: dict[tuple, Claim] = {}
    for c in found:
        key = (c.kind, c.date, c.destination)
        if key not in best or c.advertised < best[key].advertised:
            best[key] = c
    found = list(best.values())
    return [c for c in found
            if not (c.kind == "date" and c.date == base.date)
            and not (c.kind == "airport" and c.destination == base.destination)]


FACET = re.compile(r"^([A-Z]{3}):\s+\S")


def airport_facets(text: str, base: Query, site: str) -> list[Claim]:
    """The sidebar list of airports, each with a "from" price.

    Kayak and Momondo render these as 'LGW: Gatwick' then '$175'. They are
    metro-wide prices -- the sidebar lists JFK, EWR and LGA too, so the search
    behind them covers the whole origin area, not just the airport you typed.
    `verify.py` tests them that way, which is the reading most favourable to
    the site.
    """
    import airports

    wanted = set(airports.expand(base.destination))
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out: list[Claim] = []
    seen: set[str] = set()
    for i, line in enumerate(lines[:-1]):
        code = FACET.match(line)
        price = PRICE_ONLY.match(lines[i + 1])
        if not (code and price) or code.group(1) not in wanted:
            continue
        if code.group(1) in seen:
            continue
        seen.add(code.group(1))
        out.append(Claim(site=site, kind="airport", destination=code.group(1),
                         advertised=int(price.group(1).replace(",", "")),
                         source=f"{line} {lines[i + 1]}", metro_wide=True))
    return out
