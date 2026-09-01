# Solari Cookbook

Short, runnable examples for [Solari](https://getsolari.com) — cloud browsers,
sandboxes, and desktops behind one API key.

This is a fork. Alongside the upstream examples it carries one thing built on
top of them:

---

## Fare Board — what this fork adds

**[`flight-price-map/`](flight-price-map)** prices one trip across every major
travel site, and every airport around your destination, at the same time.

Ask for any route on any date and it launches a browser per search, reads the
results pages, and tells you which flight to take and which site is selling it
for least. Twenty seconds for a straight answer; a minute more to widen it to
the nearby airports.

![The traveller's view](flight-price-map/shots/landing-dark.png)

### What it found

The tool exists to answer questions that are tedious by hand, so the point of
it is what it measured — including the times it disproved what we expected.

| Question | Answer |
|---|---|
| Does a nearby airport save money? | Gatwick was **$80** under Heathrow — but Google and Kayak both suggest that swap themselves. Against the best hint any single site gave, cross-site search won by **$12**. |
| Does the site you book on matter? | **$23** on JFK–LHR. **$141 (39%)** on Tampa–Barcelona. It is worth almost nothing on the corridors everyone benchmarks and a great deal on the routes nobody checks. |
| Do fares change by country? | Barely. Kayak quoted the **identical fare from all seven countries** it answered; the widest spread any site showed was $14, with prices forced to USD so this is pricing rather than exchange rates. |
| Are the "from $175" teasers real? | **8 of 8 held** — 5 to the dollar, 3 cheaper than advertised. Our first run said otherwise and that was our bug, not theirs. |
| Round trips? | They **invert** the one-way answer: the airport is worth $24 and the site $125. |

Three of those are negative results. They are in the README because a tool that
only reports the findings it hoped for is not measuring anything.

### Why cloud browsers, specifically

Each leg of this was tested rather than assumed:

- **No API exists.** Google Flights, Kayak and Momondo publish nothing. A
  browser is not a shortcut here, it is the only door.
- **The sites fight automation.** Skyscanner walls us, Expedia walls us
  intermittently. Stealth and residential egress are load-bearing.
- **Asking everything at once is the product.** Thirty searches in 113 seconds
  against about eight minutes one after another.

The honest ceiling is blocking rather than engineering: four sweeps by one
person was enough to lose Skyscanner for a day, which is why the live service
caches hard and throttles per site.

### Run it

```bash
cd flight-price-map
pip install -r requirements.txt
cp .env.example .env                 # paste your slr_live_ key in

python trip.py --live --out live.html
python server.py                     # -> http://localhost:8080
```

Then type any two airports and any date.

There is a full write-up in
**[flight-price-map/README.md](flight-price-map/README.md)** — the parser
faults it has had and how they were caught, why round trips were silently
wrong, what gets past an anti-bot wall and what does not, and the measurements
behind every number above.

---

Everything below is the upstream cookbook, unchanged.

## Examples

### Cloud browser

| Example | Language | What it shows |
| --- | --- | --- |
| [browser-quickstart-ts](examples/browser-quickstart-ts) | TypeScript | Launch a browser, open a page, read it |
| [browser-quickstart-py](examples/browser-quickstart-py) | Python | Launch a browser, open a page, read it |
| [browser-stealth-proxy-ts](examples/browser-stealth-proxy-ts) | TypeScript | Stealth mode + residential proxy egress |
| [browser-profiles-ts](examples/browser-profiles-ts) | TypeScript | Log in once, reuse the session forever |
| [browser-session-recording-py](examples/browser-session-recording-py) | Python | Record a session, download the replay |

### Sandbox

| Example | Language | What it shows |
| --- | --- | --- |
| [sandbox-quickstart-ts](examples/sandbox-quickstart-ts) | TypeScript | Run a command, write and read files |
| [sandbox-code-interpreter-py](examples/sandbox-code-interpreter-py) | Python | Stateful Python kernel for agent loops |
| [sandbox-port-preview-ts](examples/sandbox-port-preview-ts) | TypeScript | Expose a server in the VM on a public URL |

### Desktop

| Example | Language | What it shows |
| --- | --- | --- |
| [desktop-computer-use-py](examples/desktop-computer-use-py) | Python | Screenshot, click, and type on a Linux GUI |

## Running an example

Each directory is self-contained.

```bash
git clone https://github.com/solari-sdk/solari-cookbook.git
cd solari-cookbook/examples/browser-quickstart-ts

npm install                          # or: pip install -r requirements.txt
export SOLARI_API_KEY=slr_live_...   # grab one at console.getsolari.com
npm start                            # or: python main.py
```

One `slr_live_` key works across browsers, sandboxes, and desktops, and every
product bills to the same balance.

## Which product do I want?

- **Cloud browser** — you need a *web page*: scraping, testing, filling forms,
  anything Playwright or Puppeteer would do locally. Adds stealth, managed
  proxies, captcha solving, profiles, and session recording.
- **Sandbox** — you need to *run code*: an LLM's Python, an untrusted build, a
  data job. A headless microVM that boots from a snapshot in about a second.
- **Desktop** — you need a *screen*: computer-use agents, GUI apps, anything
  that has to be clicked. A sandbox plus X11 and a live VNC stream.

## Gotchas the examples encode

Things that cost you an afternoon if you meet them cold:

- **TypeScript: call `await solari.close()`.** The browser client keeps a
  loopback proxy open for connection retries. Skip the close and your script
  prints its output and then hangs forever instead of exiting.
- **Recording is per session, not per account.** Pass `recording: true` when you
  create the session; without it the replay endpoint 404s forever. The upload is
  async after release, so poll for ~30s before giving up.
- **Sandbox commands are not shell-interpreted.** `run("ls -la")` looks for a
  binary named `ls -la`. Put argv in `args`, or run `sh -c` explicitly.
- **`kill()`, not `close()`, ends a VM.** `close()` drops your local control
  channel; the VM keeps running until its idle timeout.
- **`timeoutMs` is a rolling idle window**, not a hard deadline — it resets on
  every use.

Two more the Fare Board added:

- **`proxy` and a plain string behave identically.** `proxy="gb"` and
  `ProxyRequest(country="gb")` are the same call. When every non-US country
  times out at once it is an outage, not an entitlement — a proxy failure and a
  missing feature look identical from the client, so re-test before concluding.
- **`launch(captcha=True)` and `proxy="smart"` are not magic.** Against a site
  that has decided about you, neither helps: six launch configurations, zero
  through. The lever is a cooldown.

## Links

- Docs — [docs.getsolari.com](https://docs.getsolari.com)
- Console — [console.getsolari.com](https://console.getsolari.com)
- Changelog — [changelog.getsolari.com](https://changelog.getsolari.com)
- Questions — [hello@getsolari.com](mailto:hello@getsolari.com)

## Contributing

New examples are welcome. Keep them small, make them run end-to-end against the
real API, and put anything surprising in a comment right where it bites.
