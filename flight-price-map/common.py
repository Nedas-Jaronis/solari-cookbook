"""Shared plumbing: env loading, the Query/Fare types, money parsing."""

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


# Coach and rail operators. Kayak and Momondo run one engine and it mixes
# ground transport into flight results on short routes, so a search out of
# Boston answers with a seven-hour, forty-four-dollar Flix coach from
# Manchester sitting above every flight. It is not a cheap fare and it is not
# an outlier -- it is not a flight, and because it is the lowest number on the
# page it takes the headline, which is the one answer this whole thing exists
# to get right.
GROUND = (
    "flix", "greyhound", "megabus", "boltbus", "ourbus", "vamoose",
    "tripper bus", "peter pan", "c&j", "concord coach", "trailways",
    "jefferson lines", "redcoach", "amtrak", "brightline", "via rail",
    "eurostar", "thalys", "ouigo", "italo", "trenitalia", "renfe", "sncf",
    "deutsche bahn", "db fernverkehr", "obb", "öbb", "sbb", "westbahn",
    "regiojet", "leo express", "eurolines", "alsa", "blablacar",
    "national express",
)


def ground(carrier: str | None) -> bool:
    """Is this operator a bus or a train rather than an airline?

    Prefix rather than exact match: one brand ships as Flix, FlixBus and
    Flixtrain depending on which page you caught it on.
    """
    if not carrier:
        return False
    # Kayak tags the mode next to the operator -- a real cached search stored
    # "FlixBus, Bus" -- and that tag catches operators no list would have, so
    # it is worth more than the names below. The names stay as the backstop
    # for pages that give the operator and not the mode.
    parts = [w.strip().lower().rstrip(".") for w in carrier.split(",")]
    if any(w in ("bus", "train", "rail", "ferry") for w in parts):
        return True
    return any(parts[0].startswith(g) for g in GROUND)


def plausible(fares: list[Fare], floor: int = 40, ceiling: int = 20000) -> list[Fare]:
    """Drop prices that cannot be airfares.

    Results pages are full of other numbers -- '$12 baggage', '2,024' years,
    hotel upsells. A fare below the floor or above the ceiling is noise.

    A coach fare is noise of a more expensive kind: it is a real price for a
    real journey, so no price range excludes it. It has to go by operator.
    Either leg being a bus disqualifies the trip -- a flight out and a coach
    back is not a flight either.
    """
    return [f for f in fares
            if floor <= f.price <= ceiling
            and not ground(f.airline) and not ground(f.back_airline)]


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
