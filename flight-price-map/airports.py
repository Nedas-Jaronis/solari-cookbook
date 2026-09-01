"""Nearby-airport groups.

Searching only the airport you first thought of is how people overpay. Gatwick
sits 25 miles from Heathrow and routinely prices a hundred dollars under it;
you never see that unless you ask both at once. Fanning out over a metro area
costs nothing extra in wall-clock time -- the browsers run in parallel.
"""

METROS: dict[str, list[str]] = {
    "NYC": ["JFK", "EWR", "LGA"],
    "LON": ["LHR", "LGW", "STN", "LTN", "LCY"],
    "PAR": ["CDG", "ORY", "BVA"],
    "MIL": ["MXP", "LIN", "BGY"],
    "TYO": ["NRT", "HND"],
    "CHI": ["ORD", "MDW"],
    "WAS": ["IAD", "DCA", "BWI"],
    "SFO": ["SFO", "OAK", "SJC"],
    "LAX": ["LAX", "BUR", "LGB", "SNA", "ONT"],
    "MIA": ["MIA", "FLL", "PBI"],
    "TPA": ["TPA", "PIE", "SRQ"],
    "BOS": ["BOS", "PVD", "MHT"],
    "ROM": ["FCO", "CIA"],
    "BER": ["BER"],
    "AMS": ["AMS", "RTM", "EIN"],
}

# Reverse lookup: which metro does this airport belong to?
_OF = {code: metro for metro, codes in METROS.items() for code in codes}


def expand(code: str) -> list[str]:
    """'LHR' -> every London airport. An unknown code expands to itself."""
    code = code.upper()
    if code in METROS:
        return METROS[code]
    metro = _OF.get(code)
    return METROS[metro] if metro else [code]


def metro_of(code: str) -> str | None:
    return _OF.get(code.upper())
