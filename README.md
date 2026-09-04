# Fare Board

Ask for any flight, on any date. It launches a browser per search, reads
Google Flights, Kayak, Momondo, Expedia and Priceline at the same time, adds
every airport around your destination, and tells you which flight to take and
which site is selling it for least. It can run that search from any of nine
countries, so you see the page a local is shown rather than the page shown to
an American.

Built on [Solari](https://getsolari.com) cloud browsers, on a fork of their
[cookbook](https://github.com/solari-sdk/solari-cookbook).

**The problem.** Every booking site shows a different price for the same seat,
and none of them tell you the airport an hour up the road is cheaper. Checking
properly is a dozen tabs and twenty minutes, so almost nobody does it — which
means almost nobody knows what that check is actually worth. This measures it.

[![Fare Board — click to watch it price MCO to DEN across every site at once](flight-price-map/demo/thumbnail.png)](https://nedas-jaronis.github.io/solari-cookbook/flight-price-map/demo/watch.html)

**[▶ Watch the run (1 min)](https://nedas-jaronis.github.io/solari-cookbook/flight-price-map/demo/watch.html)** — Orlando to
Denver and back, MCO–DEN, 1 to 7 January 2027, round trip, stops unrestricted.

It ends on **$368 on Frontier, booked through Expedia**: three booking sites,
one airport, eighteen flights, twenty-three seconds. The outbound is a 4h 23m
nonstop — the search never asked for a nonstop, that was simply the cheapest
thing any site had.

Nothing in the recording is staged, and the parts that went badly are still in
it. Fares appear as each site answers rather than when the slowest one
finishes, which is why the list fills in while you watch. The first search got
**one** site back out of the four it asked, and the page said so — "1 booking
site checked" — before a re-check got three. That matters more than it looks:
a price comparison that quietly drops a site that refused it is not reporting
the cheapest fare, it is reporting the cheapest fare *it managed to read*, and
it never tells you which one it missed.

## What it found

The tool exists to answer questions that are tedious by hand, so what matters
is what it measured — including the times it disproved what we expected.

| What we found | The number, and what it cost us to believe it |
|---|---|
| **The site you book on is worth $141 on a thin route** | 39% on Tampa–Barcelona. On JFK–London it is $23. The tool is nearly worthless on the corridors everyone benchmarks and worth a lot on the routes nobody checks. |
| **A nearby airport saved $80** | Gatwick under Heathrow. But Google and Kayak *both suggest that swap themselves* — against the best hint any single site gave, cross-site search won by **$12**. That is the honest number. |
| **Where you browse from does not matter at all** | ~1,400 comparisons of *the same physical flight* — same carrier, departure, arrival, stops — across eight countries, two sites and two rounds. Not one flight is priced differently. This began as a $12 gap we believed for twenty-three minutes; see [below](#browsing-from-somewhere-else). |
| **The "from $175" teasers are real** | 8 of 8 held — 5 to the dollar, 3 *cheaper* than advertised. Our first run said otherwise, and that was our bug, not theirs. |
| **Round trips invert all of it** | The airport is worth $24 and the site $125. |

Three of those are negative results. They are here because a tool that only
reports the findings it hoped for is not measuring anything.

## Run it

```bash
cd flight-price-map
pip install -r requirements.txt
cp .env.example .env                 # paste your slr_live_ key in

python trip.py --live --out live.html
python server.py                     # -> http://localhost:8080
```

Type any two airports and any date. A straight answer takes about twenty
seconds; the nearby airports fill in underneath it over the next minute.

To look from somewhere else, pass a country — `au`, `br`, `ca`, `de`, `gb`,
`in`, `jp`, `sg` or `us`, the exits we have actually watched a browser come out
of. Anything else is refused rather than quietly swapped for a US one, and the
country is part of the cache key, so a search from Tokyo is never answered with
the page London was shown.

```bash
curl -s localhost:8080/api/search -H 'content-type: application/json'   -d '{"from":"DEL","to":"BOM","date":"2026-10-15","country":"in"}'

FARE_EGRESS=jp python server.py     # or set the default for every search
```

Measured on routes that had never been searched:

```
BOS -> LIS   22s   4/4 sites   11 flights   $299
MIA -> MAD   40s   4/4 sites    9 flights   $329
SAN -> LIS   25s   4/4 sites    9 flights   $320
BOS -> LHR   24s   quick answer, Heathrow only
            110s   widened to all 5 London airports, 43 flights
the same search again    0.03s, from cache
```

The live search runs locally, on your own key. It is deliberately not on a
public URL: a search is about 1.2 browser-minutes, and a search button open to
the internet spends a metered credit on strangers' behalf — which the recording
above demonstrates for nothing. `Dockerfile` and `fly.toml` are in the repo for
anyone who wants to host it anyway, with limits sized for that.

There are also committed boards you can open straight from a clone, no key
needed: [`trip.html`](flight-price-map/trip.html) for a traveller,
[`board.html`](flight-price-map/board.html) for whoever ran it,
[`teasers.html`](flight-price-map/teasers.html) for the advertised-price check.

## Where Solari is used

Every price on the screen was read by a real Chromium in Solari's cloud. There
is no scraping library here and no HTTP client pretending to be a browser —
five of these six sites publish no API at all, so a browser is not a shortcut,
it is the only door.

In the recording above, "3 searches in 23s" is three cloud browsers launched at
once, one per booking site, each loading that site's own results page and
having its fares read off it. That is the whole engine. A search that also
widens to the airports around your destination is the same thing multiplied:
six sites times five airports is thirty browsers, which is a hundred and
thirteen seconds instead of the eight minutes it would take one at a time.

| Where | The call | Why it has to be a cloud browser |
|---|---|---|
| **Every fare read** | `launch(stealth=True, proxy=...)`, then ordinary Playwright | No API exists. Without stealth there is no project — Expedia and Skyscanner wall us even with it. |
| **Reading as a local** | `proxy=ProxyRequest(country=…, tier="residential")` | The only way to ask whether a fare is different in Tokyo than in Ohio. The live service takes a country per search. |
| **Proving where we stood** | `browser.proxy` → country, tier, timezone | Turns *"we searched from Japan"* from a claim into a fact. It is what proved every browser exited where it was asked, checked against the timezone the page itself reported — without which "the price is the same everywhere" could just mean the proxy never moved. |
| **Thirty searches at once** | many `launch()` calls in parallel | 113 seconds instead of eight minutes. This one is the product, not an optimisation. |
| **Getting through walls** | `captcha`, `web_bot_auth`, `proxy="smart"`, all three tiers | Tested side by side in `bypass.py`, and reported even where the answer was no. |

Deliberately **not** used: sandboxes, desktops, session recording, profiles.
This is a read-the-page problem, not a run-code or drive-a-GUI one, and reaching
for them to touch more of the SDK would be padding.

The honest ceiling is blocking rather than engineering. Four sweeps by one
person was enough to lose Skyscanner for a day, which is why the service caches
hard and throttles per site.

## Browsing from somewhere else

This section used to say the tool was US-only, and why. That is no longer true,
so here is what changed and what it turned out to be worth.

**The blocker is gone.** We shipped US-only because non-US exits dropped
searches under load: four of twenty-one, two of them
`ERR_TUNNEL_CONNECTION_FAILED` from Germany and Japan. For a price comparison
that is disqualifying — a search that quietly loses a site reports the cheapest
fare *it managed to read*, and never says which one it missed. Re-tested since:
**42 of 42 non-US searches came back**, across two routes and eight countries,
plus every search in the geography tests below. Every browser exited in the
country it was asked for, confirmed against the timezone the page itself
reported:

```
asked for      came out as    timezone the page saw
      in             in       Asia/Kolkata
      jp             jp       Asia/Tokyo
      br             br       America/Sao_Paulo
      de             de       Europe/Berlin      ...and so on for au, gb, sg, us
```

So `server.py` no longer hard-codes the exit. Pass `country` on a search, or set
`FARE_EGRESS`; anything outside the list of exits we have actually watched a
browser come out of is refused rather than silently swapped for a US one.

**And the price is the same everywhere.** The interesting part is that having
built it, the answer is no. Delhi–Mumbai and Johannesburg–Cape Town, eight
countries, two sites, two rounds: about 1,400 comparisons of *the same physical
flight* — same carrier, same departure, same arrival, same stops — and not one
of them is priced differently by the country you look from.

Getting that right needed a control we did not have at first. One sweep showed
Delhi–Mumbai at $57 from seven countries and $69 from the US, on two sites at
once, which looked conclusive enough that we believed it. Twenty-three minutes
later it was $57 everywhere. The fare had simply moved, the move landed on the
US search, and both sites agreed because both were read in the same minute —
sharing an artifact rather than confirming each other. `geodiff.py` exists so
that cannot happen twice: it runs the sweep twice and measures how much the
same country differs *from itself* between rounds, and refuses to call a
country difference real unless it beats that noise floor. On Johannesburg it
caught exactly this — a $16 US gap in round one, gone in round two, and the
same page moving $16 against itself in between.

```
python compare.py --from DEL --to BOM --date 2026-10-15     --countries us gb de jp au in br sg --sites kayak momondo --out geo/a.json
python compare.py ... --out geo/b.json        # again, straight after
python geodiff.py geo/a.json geo/b.json
```

This is the negative result the project is most confident in, and it is worth
more than the positive one would have been: it says the expensive thing —
pricing every route from every country — is not where the money is. The money
is in the site you book on, which is worth $141 on a thin route.

## Where this goes next

One item on this list got answered while the project was being written, which
is the reason the list is worth keeping.

**Blocked on Solari.**

- **Skyscanner.** It runs PerimeterX — the page loads
  `client.px-cloud.net/PXrf8vapwA/main.min.js` — and six launch configurations
  get through none of the time: stealth alone, `+captcha`, `+web_bot_auth`,
  `proxy="smart"`, on both US and GB egress, at low concurrency hours after the
  last attempt. Re-tested today, still 0 of 6. It is not the egress and it is
  not a rate limit. Outside the US it is one of the sites people actually book
  on, so an international build is missing a wall rather than a nice-to-have.
- ~~**Non-US egress that survives being used.**~~ **Answered.** This was the
  blocker that made the tool US-only: four of twenty-one non-US searches
  dropped, two of them `ERR_TUNNEL_CONNECTION_FAILED`. Now 42 of 42 return, and
  the tool browses from nine countries.

**Blocked on browser time, not on Solari.**

- **Thin routes at volume.** The best finding here — $141 of spread on
  Tampa–Barcelona against $23 on JFK–London — rests on one search. It is the
  strongest claim on this page and the least verified one. Whether it holds is
  a question about hundreds of routes, and hundreds of routes is thousands of
  browsers. `worldtest.py` is most of the harness already.
- **Geography at real scale.** Two routes and eight countries say the country
  you browse from changes nothing. Two routes is not the world; the interesting
  version asks which markets, if any, price locally at all.

**Ours to fix, nobody else's.**

- **Session recording.** `recording=True` is in the SDK and this project does
  not use it for the fare reads. Every claim on this page is empirical and a
  reader currently has to take our word for it — a replay turns "the browser in
  Delhi and the browser in New York were both shown $57" into something you can
  watch. It would also have caught, in seconds, the geographic price gap we
  believed for twenty-three minutes.
- **Currency.** Prices are forced to USD so a comparison is a comparison. A
  real international build shows local currency with the conversion explicit.
- **The sites we read badly.** Priceline gives prices but no itinerary detail;
  Kiwi wants place slugs rather than IATA codes. Parser work, not platform work.

## What is in here

```
flight-price-map/
  server.py       the live service: any route, on request
  compare.py      the fan-out: sites x airports x countries, in parallel
  sites.py        per-site URL builders and result parsers
  trip.py         the traveller's page       board.py    the operator's board
  verify.py       does the advertised price exist?
  demo.py         records the real thing searching, unstaged
  flowtest.py     drives the page in a browser
  parsertest.py   holds the readers to committed fixtures
```

The **[full write-up](flight-price-map/README.md)** is worth more than this
page: the parser faults it has had and how each was caught, why round trips
were silently wrong for a day, what gets past an anti-bot wall and what does
not, and the measurement behind every number above.

A taste of it — each of these shipped, and none of them raised anything:

- Google answers a one-date search with **round-trip fares** unless you say
  "one way", roughly double, and nothing flags it.
- A round-trip card read as two flights, with the return leg wearing the whole
  trip's price. The *count* was right, which is why it looked fine.
- One flight listed four times because three sites spell `6:20 pm` differently
  and Kayak sells it under two ticketing agents.
- Next-day arrival markers dropped, so a flight landing 6:20 AM *tomorrow*
  read as landing this morning.

## The Solari examples this is built on

The upstream cookbook is still here in [`examples/`](examples) — small,
runnable programs for cloud browsers, sandboxes and desktops. The ones this
project leans on:

| Example | What it shows |
| --- | --- |
| [browser-quickstart-py](examples/browser-quickstart-py) | Launch a browser, open a page, read it |
| [browser-stealth-proxy-ts](examples/browser-stealth-proxy-ts) | Stealth mode + residential proxy egress |
| [browser-session-recording-py](examples/browser-session-recording-py) | Record a session, download the replay |

Two gotchas this project paid for, on top of the ones upstream documents:

- **A proxy string and a `ProxyRequest` are the same call.** When every non-US
  country times out at once it is an outage, not an entitlement — the two look
  identical from the client, so re-test before concluding. Ours came back on
  its own after a day.
- **`captcha=True` and `proxy="smart"` are not magic.** Against a site that has
  decided about you, neither helps: six launch configurations, zero through.
  The lever is a cooldown.

## A note on what this is

Fares are read from each site's own public results page, at the rate a person
might plausibly run them. It answers the question you would have answered by
hand, faster. It sells nothing, takes no commission, and does not touch
anyone's account — the price you see is the price the named site was showing,
and you book there.

- Solari — [docs](https://docs.getsolari.com) ·
  [console](https://console.getsolari.com)
- Upstream cookbook —
  [solari-sdk/solari-cookbook](https://github.com/solari-sdk/solari-cookbook)
