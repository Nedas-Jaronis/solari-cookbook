# Flight price map

Prices the same flight from several countries at once, using Solari's stealth
mode and residential proxy egress. Travel sites quote different fares depending
on where you appear to be browsing, and that is not testable from one machine.

Prices are forced to USD (`curr=USD`) so the comparison isolates *geographic*
pricing from exchange rates. Without that you are just watching currency
conversion.

## Status

Working end to end for the United States:

```
 country   cheapest  flights   secs  timezone
      us $      597       24   12.1  America/New_York
```

That is a real Google Flights result (JFK->LHR, 24 itineraries parsed, cheapest
$597) read through a residential US IP.

**Blocked: every non-US proxy country fails to connect.** Tested 14 countries
with a plain `api.ipify.org` load and a 40s timeout:

```
  us OK   3s
  ca gb de fr nl es it au jp sg in br mx   all FAIL ~32s
```

The failure is at the proxy, not the target site: it reproduces on a trivial
page, so it is not Google blocking us. Since the whole premise is comparing
countries, this needs resolving before the tool does what it is for. Likely
either a plan entitlement (the Starter plan may only include US egress) or a
pool availability problem -- worth asking Solari directly.

## The pivot if country egress stays unavailable

Compare **sites** rather than countries, all through US residential IPs, which
work fine: Google Flights against Kayak, Momondo, Expedia and others for the
same route. Still a genuine "find the cheapest" tool, still needs stealth and
proxies to avoid being blocked, and it uses the 20 concurrent browsers the plan
does allow.

## Files

```
parse.py        Google Flights results -> structured itineraries
pricemap.py     fan out across countries, collect and compare fares
proxycheck.py   which proxy countries actually connect
probe.py        first-contact script: does stealth + proxy work at all
```

## Run

```bash
pip install -r requirements.txt
cp .env.example .env          # then paste your slr_live_ key into it
python proxycheck.py          # confirm which countries are usable
python pricemap.py --from JFK --to LHR --date 2026-10-15 --countries us
```

## Notes

- **Parsing is done on the page's visible text, not its DOM.** Google's class
  names are obfuscated and rotate; the text layout ("9:35 AM - 9:40 PM",
  airline, duration, "Nonstop", "$793", "round trip") is what a human reads and
  is far more stable to parse.
- **Results stream in after page load.** Reading immediately gets "Loading
  results" and no prices; the fetch waits before reading.
- `browser.proxy` reports what the gateway resolved -- country, tier and
  timezone -- which is how the table above can show `America/New_York` and
  prove the egress was really where it claimed.
