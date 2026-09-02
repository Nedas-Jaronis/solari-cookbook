"""Who counts as an airline.

Blocking buses by name does not work. We blocked Flix and the next search
answered with `iryo`, a Spanish high-speed train, priced under every flight and
carrying nothing that marks it as rail. A blocklist only ever knows the modes
of transport that have already embarrassed us.

So this is the other way round: a fare counts as a flight when its operator is
on the list below, and does not otherwise. The failure mode inverts with it --
instead of an unknown train slipping in and winning the headline, an unknown
airline gets left out. That is the better way to be wrong, but it is still
wrong, so every rejected name is recorded in `unknown` for the callers that
want to show them.

Matching is on the leading operator, at a word boundary. Sites run the
operating carrier into its partners -- "British AirwaysAmerican, Iberia" -- so
what we test is the front of the string, and the boundary is what stops "ITA"
from also accepting "Italo".
"""

import re
from collections import Counter

# Names that were rejected, and how often. An airline missing from the list is
# a silent loss of real fares, so somebody has to be able to see it: compare.py
# prints this at the end of a run.
unknown: Counter = Counter()

# Not an operator, but the label Google uses when a trip has several. It has
# to pass or every mixed-carrier itinerary disappears.
LABELS = ("multiple airlines",)

AIRLINES = {
    # --- seen in this project's own runs, which is the list that matters most
    "jetblue", "british airways", "american", "american airlines", "virgin atlantic",
    "southwest", "swiss", "swiss international air lines", "icelandair",
    "turkish airlines", "norse atlantic", "delta", "aer lingus", "klm", "iberia",
    "iberia express", "air france", "tap", "tap air portugal", "tap portugal",
    "united", "united airlines", "sun country", "hahn air", "frontier", "level",
    "ryanair", "wizz air", "vueling", "a.p.g.", "apg", "breeze", "breeze airways",
    "royal air maroc", "alaska", "alaska airlines", "air canada", "air europa",
    "air europa express", "easyjet", "finnair", "austrian airlines", "austrian",
    "lufthansa", "ita", "ita airways", "brussels airlines", "scandinavian airlines",
    "sas", "air algerie", "air dolomiti", "helvetic", "edelweiss", "german airways",
    "klm cityhopper", "ba cityflyer", "air nostrum", "republic airways",
    "psa airlines", "piedmont airlines", "envoy air", "skywest", "air canada rouge",
    "jetblue airways",
    # --- North America
    "spirit", "spirit airlines", "allegiant", "hawaiian", "hawaiian airlines",
    "avelo", "silver airways", "cape air", "sun country airlines", "westjet",
    "flair", "flair airlines", "porter", "porter airlines", "air transat",
    "sunwing", "aeromexico", "volaris", "viva aerobus", "viva", "mesa airlines",
    "horizon air", "endeavor air", "gojet", "commuteair", "air wisconsin",
    "contour", "boutique air", "southern airways", "jsx", "bahamasair",
    "caribbean airlines", "copa", "copa airlines", "interjet",
    # --- Europe
    "norwegian", "norwegian air shuttle", "play", "wideroe", "widerøe",
    "eurowings", "condor", "discover airlines", "transavia", "corendon",
    "tui", "tui fly", "jet2", "loganair", "aurigny", "blue islands", "iberojet",
    "binter", "binter canarias", "canaryfly", "volotea", "buzz", "lauda",
    "malta air", "air malta", "km malta", "pegasus", "ajet", "sunexpress",
    "aegean", "aegean airlines", "olympic", "olympic air", "tarom",
    "bulgaria air", "croatia airlines", "air baltic", "airbaltic", "lot",
    "lot polish airlines", "czech airlines", "smartwings", "air serbia",
    "montenegro airlines", "air albania", "wizz air uk", "ryanair uk",
    "british airways cityflyer", "eastern airways", "sky express", "luxair",
    "brussels", "swiss air lines", "chair airlines", "marabu", "norse atlantic uk",
    "norse atlantic airways", "french bee", "la compagnie", "corsair",
    "air corsica", "asl airlines", "hi fly", "sata", "azores airlines",
    "sky alps", "aeroitalia", "neos", "albastar", "electra airways",
    # --- Middle East and Africa
    "emirates", "etihad", "etihad airways", "qatar airways", "flydubai",
    "air arabia", "gulf air", "kuwait airways", "jazeera airways", "oman air",
    "salamair", "saudia", "flynas", "flyadeal", "middle east airlines",
    "royal jordanian", "el al", "arkia", "israir", "egyptair", "air cairo",
    "nesma airlines", "ethiopian", "ethiopian airlines", "kenya airways",
    "rwandair", "south african airways", "flysafair", "kulula", "airlink",
    "lift", "cemair", "air mauritius", "air seychelles", "tunisair",
    "air algerie express", "asky", "air peace", "arik air", "ibom air",
    "fastjet", "mango", "safair",
    # --- Asia and the Pacific
    "ana", "all nippon airways", "japan airlines", "jal", "peach", "zipair",
    "jetstar", "jetstar japan", "jetstar asia", "skymark", "solaseed air",
    "starflyer", "air do", "ibex airlines", "korean air", "asiana",
    "asiana airlines", "jeju air", "t'way", "tway air", "air busan", "air seoul",
    "air premia", "eastar jet", "china airlines", "eva air", "starlux",
    "tigerair taiwan", "uni air", "air china", "china eastern", "china southern",
    "hainan airlines", "shenzhen airlines", "xiamen air", "juneyao airlines",
    "spring airlines", "cathay pacific", "cathay", "hong kong airlines",
    "hk express", "greater bay airlines", "macau air", "air macau",
    "singapore airlines", "scoot", "malaysia airlines", "airasia", "air asia",
    "batik air", "firefly", "thai airways", "thai airasia", "thai vietjet",
    "bangkok airways", "nok air", "vietnam airlines", "vietjet", "bamboo airways",
    "pacific airlines", "cebu pacific", "philippine airlines", "philippines airasia",
    "garuda", "garuda indonesia", "lion air", "citilink", "super air jet",
    "sriwijaya air", "myanmar airways", "cambodia angkor air", "lao airlines",
    "druk air", "bhutan airlines", "himalaya airlines", "nepal airlines",
    "indigo", "air india", "air india express", "spicejet", "akasa air",
    "vistara", "alliance air", "sri lankan", "srilankan airlines",
    "maldivian", "biman", "us-bangla", "novoair", "pakistan international",
    "airblue", "serene air", "uzbekistan airways", "air astana", "fly arystan",
    "scat airlines", "azerbaijan airlines", "azal", "georgian airways",
    "armenia airways", "qanot sharq", "somon air", "turkmenistan airlines",
    "aeroflot", "s7", "s7 airlines", "ural airlines", "pobeda", "rossiya",
    "utair", "nordwind", "smartavia", "red wings", "yakutia", "aurora",
    "qantas", "virgin australia", "rex", "regional express", "bonza",
    "air new zealand", "fiji airways", "air vanuatu", "air niugini",
    "aircalin", "air tahiti nui", "nauru airlines", "solomon airlines",
    # --- Latin America
    "latam", "latam airlines", "gol", "azul", "aerolineas argentinas",
    "aerolíneas argentinas", "avianca", "sky airline", "jetsmart",
    "flybondi", "wingo", "arajet", "boliviana de aviacion", "amaszonas",
    "paranair", "conviasa", "estelar", "satena", "easyfly", "clic",
    "aeromar", "tag airlines", "volaris costa rica", "sansa", "winair",
    "liat", "inselair", "surinam airways", "fly allways",
}


def head(raw: str | None) -> str:
    """The operator at the front of a carrier string, original case kept.

    Only the "Operated by" tail is cut. The case matters: it is the one thing
    separating a partner running onto the end of a name from a longer name.
    """
    if not raw:
        return ""
    cut = re.split(r"\s*operated by\s*", raw, flags=re.I)[0]
    return re.sub(r"\s+", " ", cut).strip()


# Longest first, so "american airlines" is tried before "american".
KNOWN = sorted((*AIRLINES, *LABELS), key=len, reverse=True)


def leading(raw: str | None) -> str | None:
    """The known airline at the front of a carrier string, as written.

    Three ways a known name can legitimately end:

        "Delta"                     the whole string
        "TAP AIR PORTUGAL"          a space or punctuation follows
        "Virgin AtlanticAir France" a partner runs straight onto the end

    That third one is why this cannot just lowercase and compare. Sites join
    the operating carrier to its codeshare partners with no separator at all,
    and 83 real fares in this project's own history are written that way.

    The boundary is what keeps the short names safe. A partner starts either
    after a lowercase letter ("Vueling" + "Iberia") or, when the operator is
    written in caps, as a Titlecase word ("SWISS" + "United"). Neither is true
    of "ITALO", which is how a three-letter airline can sit in the list without
    also admitting an Italian train.
    """
    name = head(raw)
    if not name:
        return None
    low = name.lower()
    for known in KNOWN:
        if not low.startswith(known):
            continue
        matched, rest = name[:len(known)], name[len(known):]
        if not rest or not rest[0].isalnum():
            return matched
        if rest[0].isupper() and (matched[-1].islower()
                                  or (len(rest) > 1 and rest[1].islower())):
            return matched
    return None


def is_airline(raw: str | None) -> bool:
    """Is the operator at the front of this string an airline we know?"""
    if leading(raw) is not None:
        return True
    unknown[raw] += 1
    return False
