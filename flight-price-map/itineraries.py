"""Turn stored fares into flights a person can choose between.

The boards are for whoever is running the tool. This is for whoever is taking
the trip: one entry per actual flight, deduplicated across every site and
airport we searched, carrying the times and the carrier rather than the site
key and the status code.
"""

import re

import airlines

# "8:45 AM", "10:40 pm", "8:45am"
CLOCK = re.compile(r"^(\d{1,2}):(\d{2})\s*([ap])m(?:\s*\+(\d))?$", re.I)
# "6 hr 55 min", "7h 00m", "6 hours 55 minutes", "7 hr"
SPAN = re.compile(r"(\d+)\s*h(?:r|ours?)?(?:\s*(\d+)\s*m(?:in|inutes?)?)?", re.I)


def carrier(name: str | None) -> str | None:
    """The airline you would actually fly, without its codeshare tail.

    Google runs the operating carrier straight into its partners with no
    separator -- "British AirwaysAmerican, Iberia, Finnair" -- so the split is
    at the first lowercase-to-uppercase boundary, but only when what follows
    looks like a partner list. Without that guard "JetBlue" becomes "Jet".
    """
    if not name:
        return None
    # Ask the airline list first. Splitting on the case boundary alone cannot
    # tell "JetBlue, Delta" from "British AirwaysAmerican, Iberia": both are a
    # lowercase-to-uppercase run followed by a comma, and the guard below turned
    # the first into "Jet" for as long as it was the only rule. The list knows
    # where JetBlue ends.
    known = airlines.leading(name)
    if known:
        return known
    name = re.split(r"\s*Operated by\s*", name, flags=re.I)[0]
    for match in re.finditer(r"(?<=[a-z])(?=[A-Z])", name):
        head, tail = name[:match.start()], name[match.start():]
        if "," in tail:
            return head.strip()
    return name.strip()


def minutes(span: str | None) -> int | None:
    """'6 hr 55 min' -> 415. Used for sorting and the shortest-flight filter."""
    if not span:
        return None
    match = SPAN.search(span)
    if not match:
        return None
    return int(match.group(1)) * 60 + int(match.group(2) or 0)


def clock(value: str | None) -> int | None:
    """'8:45 PM' -> 1245, minutes past midnight, for sorting by departure."""
    if not value:
        return None
    match = CLOCK.match(value.strip())
    if not match:
        return None
    hour = int(match.group(1)) % 12
    if match.group(3).lower() == "p":
        hour += 12
    return hour * 60 + int(match.group(2))


def day_offset(value: str | None) -> int:
    """How many days later the flight lands, from a trailing '+1'."""
    match = CLOCK.match((value or "").strip())
    return int(match.group(4)) if match and match.group(4) else 0


def show_time(mins: int | None, fallback: str | None) -> str | None:
    """Render a time the same way every site's version of it.

    Sites print the same departure as "6:20 pm", "6:20 PM" and "6:20pm". Once
    parsed, print it once, our way, so a list of flights does not look like a
    list of typefaces.
    """
    if mins is None:
        return fallback
    hour, minute = divmod(mins, 60)
    suffix = "AM" if hour < 12 else "PM"
    hour = hour % 12 or 12
    return f"{hour}:{minute:02d} {suffix}"


def stop_count(stops: str | None) -> int | None:
    if not stops:
        return None
    if re.match(r"^(nonstop|direct)$", stops.strip(), re.I):
        return 0
    match = re.match(r"^(\d+)\s*stops?$", stops.strip(), re.I)
    if match:
        return int(match.group(1))
    if re.match(r"^one stop$", stops.strip(), re.I):
        return 1
    return None


def collect(runs: list[dict]) -> list[dict]:
    """Every distinct flight we saw, cheapest price first.

    The same flight turns up on several sites at several prices; that spread is
    the useful part, so each flight keeps the list of who quoted it and for how
    much rather than being flattened to one number.
    """
    flights: dict[tuple, dict] = {}
    for run in runs:
        names = run.get("site_names", {})
        when, back = run.get("date"), run.get("ret")
        for result in run.get("results", []):
            if not result.get("ok"):
                continue
            for fare in result.get("fares") or []:
                air = carrier(fare.get("airline"))
                dep = fare.get("depart")
                dur = minutes(fare.get("duration"))
                if not (air and dep and dur):
                    continue          # too thin to show a traveller
                # Airport, departure minute, duration and stop count identify
                # the flight; the airline name does not. Kayak sells the same
                # 6:20pm Norse departure under "Hahn Air" and "A.P.G." -- those
                # are ticketing agents, and listing them as separate flights is
                # the confusion this page exists to remove. Two distinct
                # carriers sharing an airport, minute, duration and stop count
                # would merge wrongly; on real timetables that does not happen.
                stops = stop_count(fare.get("stops"))
                # A round trip is only the same trip if both legs match, so
                # the return leg joins the key. Without it two trips sharing an
                # outbound but returning on different flights would merge, and
                # the cheaper one would quietly swallow the other.
                # The date and trip type are part of the identity: a one-way
                # and a round trip on the same outbound flight are different
                # products at different prices, and merging them would let the
                # cheaper one-way fare masquerade as a return fare.
                key = (when, back, result["destination"], clock(dep) or dep,
                       dur, stops, clock(fare.get("back_depart")),
                       fare.get("back_duration"))
                offer = {"site": names.get(result["site"], result["site"]),
                         "price": fare["price"], "country": result["country"]}
                entry = flights.get(key)
                if entry is None:
                    flights[key] = {
                        "names": {air: 1},
                        "origin": result["origin"],
                        "destination": result["destination"],
                        "date": when,
                        "ret": back,
                        "airline": air,
                        "depart": dep,
                        "depart_at": clock(dep),
                        "arrive": fare.get("arrive"),
                        "arrive_at": clock(fare.get("arrive")),
                        "arrive_next_day": day_offset(fare.get("arrive")),
                        "back_arrive_next_day": day_offset(fare.get("back_arrive")),
                        "duration": fare.get("duration"),
                        "minutes": dur,
                        "stops": stops,
                        "back_airline": carrier(fare.get("back_airline")),
                        "back_depart": show_time(clock(fare.get("back_depart")),
                                                 fare.get("back_depart")),
                        "back_arrive": show_time(clock(fare.get("back_arrive")),
                                                 fare.get("back_arrive")),
                        "back_duration": fare.get("back_duration"),
                        "back_minutes": minutes(fare.get("back_duration")),
                        "back_stops": stop_count(fare.get("back_stops")),
                        "price": fare["price"],
                        "offers": [offer],
                    }
                else:
                    entry["names"][air] = entry["names"].get(air, 0) + 1
                    entry["offers"].append(offer)
                    entry["price"] = min(entry["price"], fare["price"])
                    if entry["arrive"] is None:
                        entry["arrive"] = fare.get("arrive")

    out = []
    for flight in flights.values():
        # The name most sites agree on, which is the operating carrier rather
        # than whichever agency happens to be ticketing it.
        flight["airline"] = max(flight.pop("names").items(),
                                key=lambda kv: kv[1])[0]
        flight["depart"] = show_time(flight["depart_at"], flight["depart"])
        flight["arrive"] = show_time(clock(flight["arrive"]), flight["arrive"])
        best = {}
        for offer in flight["offers"]:
            if offer["site"] not in best or offer["price"] < best[offer["site"]]["price"]:
                best[offer["site"]] = offer
        flight["offers"] = sorted(best.values(), key=lambda o: o["price"])
        out.append(flight)
    return sorted(out, key=lambda f: f["price"])
