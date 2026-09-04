"""Shared plumbing: env loading, the Query/Fare types, money parsing."""

import hashlib
import math
import os
import pathlib
import re
from dataclasses import dataclass, field

HERE = pathlib.Path(__file__).parent

CURRENCY = "$£€₹¥₩"


def load_env() -> None:
    env = HERE / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


@dataclass
class Query:
    """One search. `ret` is None for a one-way."""
    origin: str
    destination: str
    date: str            # YYYY-MM-DD
    ret: str | None = None

    @property
    def one_way(self) -> bool:
        return self.ret is None

    def us_date(self, which: str = "date") -> str:
        """MM/DD/YYYY, which several US sites want in the URL."""
        y, m, d = getattr(self, which).split("-")
        return f"{m}/{d}/{y}"

    def compact(self, which: str = "date") -> str:
        """YYMMDD, which Skyscanner wants."""
        y, m, d = getattr(self, which).split("-")
        return f"{y[2:]}{m}{d}"

    def label(self) -> str:
        trip = f"{self.origin}-{self.destination}"
        return f"{trip} {self.date}" + (f" ret {self.ret}" if self.ret else " one-way")


@dataclass
class Fare:
    """One priced itinerary as read off a results page.

    The unprefixed fields describe the outbound leg. A round trip is one fare
    with two legs, never two fares -- reading it as two would double the
    results and price the return journey at the whole trip's cost.
    """
    price: int
    currency: str = "$"
    airline: str | None = None
    depart: str | None = None
    arrive: str | None = None
    duration: str | None = None
    stops: str | None = None
    back_airline: str | None = None
    back_depart: str | None = None
    back_arrive: str | None = None
    back_duration: str | None = None
    back_stops: str | None = None


def money(line: str) -> tuple[str, int] | None:
    """'$597' or '1,204 $' -> ('$', 597). None if the line is not just a price."""
    m = re.match(rf"^([{CURRENCY}])\s?([\d,]{{2,7}})$", line.strip())
    if m:
        return m.group(1), int(m.group(2).replace(",", ""))
    return None


from airlines import is_airline


def unrecognised(carrier: str | None) -> bool:
    """Named as something, and that something is not an airline we know.

    The distinction matters. Priceline's reader does not capture a carrier at
    all, so twenty-three real fares carry no name -- judging those as "not an
    airline" would delete the site. An unnamed carrier is unjudged; only a
    named one can be rejected.
    """
    return bool(carrier) and not is_airline(carrier)


def plausible(fares: list[Fare], floor: int = 40, ceiling: int = 20000) -> list[Fare]:
    """Drop prices that cannot be airfares.

    Results pages are full of other numbers -- '$12 baggage', '2,024' years,
    hotel upsells. A fare below the floor or above the ceiling is noise.

    A coach fare is noise of a more expensive kind: it is a real price for a
    real journey, so no price range excludes it. It has to go by operator, and
    against a list of airlines rather than a list of buses -- blocking Flix
    only taught us about Flix, and the next search answered with a train.
    Either leg counts: a flight out and a coach back is not a flight either.
    """
    return [f for f in fares
            if floor <= f.price <= ceiling
            and not unrecognised(f.airline)
            and not unrecognised(f.back_airline)]


# --------------------------------------------------------------------------
# Proxy egress
# --------------------------------------------------------------------------

# Solari's residential tier rotates by default: consecutive requests from one
# browser can leave from different IPs. That is the right default for fetching a
# page, and the wrong one for us. These sites poll for fares for up to a minute
# after the document loads, so a search is a document plus a stream of XHRs that
# have to look like one person -- and an IP that changes underneath them is the
# cleanest bot signal there is. Pinning a session id holds one exit for the whole
# search.
STICKY_MINUTES = (1, 30)   # gateway's accepted range for session_duration


def sticky_id(slug: str, attempt: int = 1) -> str:
    """A proxy session id for one search: alphanumerics and dashes, <=32 chars.

    The attempt number is part of the id on purpose. A block earns one retry on
    a *fresh* IP, so the retry must not reuse the session that was just walled --
    the whole point of a sticky session is that it would hand back the same
    address.
    """
    stem = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")[:20].strip("-")
    digest = hashlib.sha1(f"{slug}#{attempt}".encode()).hexdigest()[:6]
    return "-".join(p for p in (stem, digest, str(attempt)) if p)[:32]


def hold_minutes(seconds: float) -> int:
    """How long to hold one exit IP, in the minutes the gateway accepts.

    Rounded up and given a minute of headroom: a session that expires while the
    page is still polling drops us back onto a rotating IP mid-search, which is
    exactly the failure this is here to prevent.
    """
    low, high = STICKY_MINUTES
    return max(low, min(high, math.ceil(seconds / 60) + 1))


def egress(country: str, *, tier: str = "residential", session: str | None = None,
           hold: float | None = None):
    """Build the `proxy=` argument for `launch()`.

    Returns the string untouched for the "smart" and "off" sentinels: smart is
    rotate-on-block by design, and pinning a session to it would be asking for
    two contradictory things.
    """
    from solari_browser import ProxyRequest

    if country in ("smart", "off"):
        return country
    return ProxyRequest(
        country=country, tier=tier, session=session,
        session_duration=hold_minutes(hold) if (session and hold) else None)


BLOCK_MARKERS = (
    "bot or not", "human or a bot", "show us your human side",
    "are you a robot", "verify you are human", "unusual traffic",
    "access denied", "pardon our interruption", "captcha", "request blocked",
    "checking your browser", "confirm that you are a real user",
    "person or a robot", "prove you're human",
)

EMPTY_MARKERS = (
    "can't find any flights", "cannot find any flights",
    "no flights found", "we couldn't find any flights",
    "no results found", "found no flights",
)


def blocked(text: str) -> bool:
    """Does this page look like an anti-bot wall rather than results?

    Worth distinguishing from 'loaded but empty': a block is worth retrying on
    a fresh IP, an empty results page is not.
    """
    head = text[:2000].lower()
    return any(marker in head for marker in BLOCK_MARKERS)


def no_results(text: str) -> bool:
    """Did the site run the search and honestly report nothing?

    Different from a parser miss: Luton really has no transatlantic service,
    and reporting that as a scraper failure would be a lie.
    """
    head = text[:2500].lower()
    return any(marker in head for marker in EMPTY_MARKERS)
