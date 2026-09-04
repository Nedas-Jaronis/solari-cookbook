# Evaluate: sticky egress, PerimeterX, and the international build

**Status: written, not run.** Everything below is a change that has been made
and reasoned about but never executed against the live API. It needs one
session with a working key before any claim in either README moves.

Written 2026-09-04. Read this before rerunning anything.

## Why it is not already done

The session that made these changes ran in a remote container with no
`SOLARI_API_KEY` and no `.env` (correctly gitignored, so it does not travel with
the clone). It also could not reach `getsolari.com` or `docs.rs` at all — the
container's egress proxy refused the CONNECT tunnel with a 403 — so neither the
live API nor the hosted docs were reachable. The findings below came from the
installed SDK source, the upstream cookbook, and PyPI.

So: nothing here is measured. The numbers in both READMEs are still the ones
from the last real run and stay that way until this file is worked through.

## Before you start

1. **The key.** It exists in a local shell, not in a remote session. Confirm
   inside whatever session you use, not on your laptop:

   ```sh
   env | grep -i solari        # expect SOLARI_API_KEY
   ```

   If it is missing, `cp .env.example .env` and fill it in — `common.load_env()`
   reads that file and `.env` is gitignored.

2. **Check the rest of the environment while you are in there.** The remote
   session had a surprising amount missing, and each one costs a run to
   discover:

   ```sh
   env | sort | grep -vi token          # what is actually set
   pip show solari-browser              # expect 0.1.3
   curl -sS -o /dev/null -w '%{http_code}\n' https://api.getsolari.com/
   ```

   That last one is the important check. A 403 at the CONNECT tunnel means the
   session's network policy blocks Solari and no amount of key will help.

3. **Install.** `pip install -r requirements.txt`.

## The hypothesis being tested

Every proxy call in this project used to pass a bare country string —
`launch(stealth=True, proxy="jp")` — which is Solari's **rotating** residential
tier. `ProxyRequest` has carried `session` and `session_duration` all along
(`solari_browser/types.py`) and we never passed them.

That matters here more than it would in most scrapers. These pages do not finish
with the document: `sites.py` sets `patience` of 55s for Skyscanner and 70s for
Kayak and Momondo because they keep polling for fares long after load. On a
rotating pool a single search can be served its page from one address and fetch
its fares from another. One visitor who teleports mid-search is a cleaner bot
signal than anything stealth mode is patching, and we were emitting it on every
search — including the 24-search country sweep whose failures we wrote up as an
egress reliability problem.

**Two things could follow, and they are independent.** Either could be true
without the other:

- Skyscanner's PerimeterX wall was partly our own doing.
- The non-US `ERR_TUNNEL_CONNECTION_FAILED` failures were rotation, not country.

Neither is established. Both are testable in about half an hour.

## Runbook

Cheapest first. Each step is worth doing even if the one before it disappoints.

### 1. Does a pinned session actually hold one IP? (~2 min)

```sh
python proxycheck.py --sticky --countries us gb de jp
```

Loads the IP echo twice through one pinned session, then twice unpinned as a
control. Everything downstream rests on this, so if it fails, stop and read the
output rather than moving on.

| Result | Meaning |
|---|---|
| pinned `HELD` on most countries | The mechanism works. Continue. |
| pinned `MOVED` everywhere | Either `session` is not honoured on this plan, or the id is being rejected. Check the raw spec with `python -c "import common; print(common.egress('us', session=common.sticky_id('x'), hold=55).to_wire())"` and ask Solari. **Everything below is void until this passes.** |
| loose pair also `same` | Not a failure. Rotating pools repeat addresses by chance; it just means the control was uninformative this run. |

### 2. Does it change anything for PerimeterX? (~5 min)

```sh
python bypass.py --site skyscanner --from JFK --to LHR --date 2026-10-15
```

`bypass.py` now runs sticky against rotating as a **controlled pair** on `us`
and `gb` — same flags either side — so a difference is attributable to the
egress rather than to a flag. Read three columns: the state, the `px` column,
and the `sticky N/N vs rotating N/N` summary line.

| Result | Meaning | What to update |
|---|---|---|
| sticky `READ` + `PX`, rotating `blocked` | The best case, and the one the hypothesis predicts. We were doing it to ourselves. | Every claim in the table below |
| all `READ` but `no PX` on all of them | We were never challenged this run. **Not evidence the wall is cleared** — the tool says so itself. Rerun later in the day, after a few sweeps have spent our welcome. | Nothing yet |
| sticky and rotating both `blocked` + `PX` | Rotation was not the cause. The wall is real and Solari's fix did not reach it. | Nothing; reopen with Solari, quoting app id `PXrf8vapwA` |
| `no egress` rows | Never reached the site — this is step 3's problem, not PerimeterX's | Nothing |

Worth knowing: the previous run's `gb` row died with
`ERR_TUNNEL_CONNECTION_FAILED` and got recorded in a table about PerimeterX, so
**GB egress has never actually been tested against the wall.** That row is the
single most informative one in the table now.

### 3. Does non-US egress survive parallel load? (~10 min)

This is the one that matters for the international build, and the one the
sticky change was really aimed at. The old result was 4 of 21 non-US searches
lost against 0 of 3 US.

Run the **same sweep shape** as the original or the comparison means nothing.
That was 24 searches: three sites (`google kayak momondo`, per `countries.json`)
across eight countries. Pass `--sites` explicitly — without it you get all
seven sites, and `--max-tasks` (default 40) would silently truncate the run.

```sh
python compare.py --from JFK --to LHR --date 2026-10-15 \
  --sites google kayak momondo \
  --countries us gb de jp au ca in sg \
  --out countries-rerun.json
```

Count failures by country and compare against the old 4-of-21 non-US, 0-of-3 US.
Then repeat on a thin route, where geographic pricing is actually expected to
show up and where the old sweep never went:

```sh
python compare.py --from TPA --to BCN --date 2026-10-17 \
  --sites google kayak momondo \
  --countries us gb de jp au ca in sg \
  --out countries-thin.json
```

Write to a new `--out` rather than over `countries.json`, so the old numbers
survive for comparison until you have decided the new ones are better.

`compare.py` now records `session` and `tier` per result, so a failure can be
traced to the exact egress that produced it.

## What to update, and only once measured

Do not touch these on the strength of a support ticket. Both READMEs are
deliberately written to report negative results, and that is worth more than a
green table.

| Claim | Where |
|---|---|
| "zero of six got through" | `flight-price-map/README.md:280` |
| "six launch configurations got through none of the time" | `flight-price-map/README.md:292` |
| The `0/6 got through` result block | `flight-price-map/README.md:521-544` |
| Site status: "no launch option gets past it" | `flight-price-map/README.md:630` |
| "four of the twenty-one non-US ones did not" | `flight-price-map/README.md:298`, `:516` |
| "six launch configurations, zero through" | `README.md:242` |
| Blocker 3, Skyscanner/PerimeterX | `README.md:151-153` |
| "Why it browses from the US only" — the whole section | `README.md:107-160` |
| Blocker 1, non-US egress under parallel load | `README.md:145-150` |

If step 3 improves materially, `README.md:107` ("Why it browses from the US
only") is the section that changes most, and the honest version still needs a
sweep bigger than 24 searches before it claims a rate.

## Open questions for Solari

1. **Is `session` honoured on our plan, and on every country?** Step 1 answers
   the observable half; they can confirm the intent.
2. **A proxy-countries endpoint.** There appears to be one that reports which
   countries have credentials configured, which would kill the
   "an outage and a missing entitlement are indistinguishable from the client
   side" limitation at `flight-price-map/README.md:509-512`. The Python SDK
   0.1.3 exposes only `sessions` and `profiles`, so no guessed REST path was
   shipped. Ask for the path, or for it to be added to the Python SDK.
3. **PerimeterX app `PXrf8vapwA` specifically.** Their page lists PerimeterX as
   cleared. If step 2 still shows `blocked` + `PX` on a pinned session, that is
   the concrete case to hand them.
4. **Non-US concurrency.** Twenty browsers at once is the normal case here, not
   a stress test. Worth asking what the expected failure rate is, so we know
   whether what we measure is a bug or the product.

## What changed already

Two commits on `claude/repo-scan-recent-fix-vzdpbq`, neither of them run:

- `243a222` — `bypass.py` tells a PerimeterX block apart from never reaching the
  site: transport failures get one retry then report `no egress` instead of
  counting as a block, and a `px` column records whether the wall was served at
  all. Adds the missing-key message instead of a raw `KeyError`.
- `2e79051` — `common.egress()` and `common.sticky_id()` build every proxy spec
  in one place, pinning one exit IP per search. Wired into `compare.py`,
  `verify.py`, `capture.py`. `probe.py` keeps the bare string on purpose: it is
  the first-contact script and its job is to show the simplest call that works.
  `bypass.py` gains the sticky/rotating A/B; `proxycheck.py` gains `--sticky`.

The pure logic is unit-tested — the session id contract (alnum and dash, <=32
chars, stable per search, different per retry, no cross-search collision), the
1-30 minute clamp, and the wire format. The network path is not tested at all.
