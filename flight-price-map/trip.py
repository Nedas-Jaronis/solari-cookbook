"""The traveller's page: which flight to book, and where to book it.

    python trip.py            # -> trip.html

The boards are for whoever runs the tool. This is for whoever takes the trip.
It shows flights rather than searches, carriers rather than site keys, and
leads with the one decision that matters -- book this, here, for this much.
"""

import argparse
import json

import itineraries
import theme
from common import HERE

EXTRA_CSS = """
.search {
  display:flex; flex-wrap:wrap; align-items:stretch; gap:1px; margin-top:22px;
  background:var(--rule); border:1px solid var(--rule); border-radius:10px;
  overflow:hidden; box-shadow:var(--shadow);
}
.field { background:var(--panel); padding:12px 18px; flex:1 1 150px; }
.field .k { font-family:"IBM Plex Mono", monospace; font-size:10px;
            letter-spacing:.16em; text-transform:uppercase; color:var(--ink-3); }
.field .v { font-size:16px; font-weight:500; margin-top:3px; }
.snapshot { font-size:12.5px; color:var(--ink-3); margin:8px 2px 0; }

.pick { margin-top:26px; background:var(--panel); border:1px solid var(--rule);
        border-radius:10px; box-shadow:var(--shadow); overflow:hidden; }
.pick-top { display:flex; flex-wrap:wrap; gap:26px; align-items:center;
            padding:24px 26px; }
.pick-price { font-family:"IBM Plex Mono", monospace; font-weight:600;
              font-size:clamp(42px,7vw,64px); line-height:1; color:var(--accent);
              font-variant-numeric:tabular-nums; }
.pick-when { font-size:20px; font-weight:500; }
.pick-meta { color:var(--ink-2); font-size:14px; margin-top:4px; }
.pick-why { padding:16px 26px; background:var(--raise);
            border-top:1px solid var(--rule-soft); font-size:14.5px;
            color:var(--ink-2); }
.pick-why strong { color:var(--ink); }

.trust { display:flex; flex-wrap:wrap; gap:8px 22px; margin:16px 2px 0;
         font-size:13px; color:var(--ink-3); }
.trust b { color:var(--ink-2); font-weight:600; }

.controls { display:flex; flex-wrap:wrap; gap:10px 16px; align-items:center;
            margin:30px 0 16px; }
.group { display:flex; align-items:center; gap:7px; flex-wrap:wrap; }
.group .k { font-family:"IBM Plex Mono", monospace; font-size:10px;
            letter-spacing:.14em; text-transform:uppercase; color:var(--ink-3); }
.pill {
  font-size:13px; padding:5px 13px; border-radius:999px; cursor:pointer;
  border:1px solid var(--rule); background:var(--panel); color:var(--ink-2);
}
.pill:hover { border-color:var(--ink-3); color:var(--ink); }
.pill[aria-pressed="true"] { background:var(--ink); color:var(--ground);
                             border-color:var(--ink); }
.pill:focus-visible, .save:focus-visible { outline:2px solid var(--accent);
                                           outline-offset:2px; }
.tally { margin-left:auto; font-size:13px; color:var(--ink-3); }

.flights { display:flex; flex-direction:column; gap:10px; }
.flight {
  display:grid; grid-template-columns:1fr auto; gap:8px 22px;
  background:var(--panel); border:1px solid var(--rule); border-radius:8px;
  padding:16px 20px; align-items:center;
}
.flight:hover { border-color:var(--ink-3); }
.flight.best { border-color:var(--accent); }
.times { font-family:"IBM Plex Mono", monospace; font-size:19px;
         font-weight:500; font-variant-numeric:tabular-nums; }
.times .arrow { color:var(--ink-3); margin:0 7px; }
.leg { color:var(--ink-2); font-size:13.5px; margin-top:3px; }
.leg .dot { color:var(--ink-3); margin:0 7px; }
.tag { font-family:"IBM Plex Mono", monospace; font-size:10.5px;
       letter-spacing:.08em; text-transform:uppercase; padding:2px 7px;
       border-radius:4px; background:var(--raise); border:1px solid var(--rule);
       color:var(--ink-2); }
.tag.nonstop { background:var(--ok-bg); color:var(--ok); border-color:transparent; }
.buy { text-align:right; display:flex; flex-direction:column; align-items:flex-end;
       gap:4px; }
.buy .amount { font-family:"IBM Plex Mono", monospace; font-size:24px;
               font-weight:600; font-variant-numeric:tabular-nums; }
.buy .where { font-size:12.5px; color:var(--ink-2); }
.elsewhere { grid-column:1 / -1; border-top:1px solid var(--rule-soft);
             padding-top:10px; margin-top:4px; display:flex; flex-wrap:wrap;
             gap:6px 10px; align-items:center; font-size:12.5px;
             color:var(--ink-3); }
.elsewhere .o { font-family:"IBM Plex Mono", monospace; }
.elsewhere .over { color:var(--warn); }
.save { background:none; border:1px solid var(--rule); border-radius:6px;
        cursor:pointer; font-size:12px; padding:4px 10px; color:var(--ink-3); }
.save:hover { color:var(--ink); border-color:var(--ink-3); }
.save[aria-pressed="true"] { color:var(--accent); border-color:var(--accent); }
.none { background:var(--panel); border:1px dashed var(--rule);
        border-radius:8px; padding:30px; text-align:center; color:var(--ink-3); }
@media (max-width:560px) {
  .flight { grid-template-columns:1fr; }
  .buy { text-align:left; align-items:flex-start; }
}
"""

TEMPLATE = """__HEAD__
<style>__EXTRA__</style>

<div class="wrap">
  <header class="mast">
    <h1>__HEADLINE__</h1>
    <div class="sub"><span class="eyebrow">prices read __WHEN__</span></div>
  </header>

  <div class="search">
    <div class="field"><div class="k">From</div><div class="v">__FROM__</div></div>
    <div class="field"><div class="k">To</div><div class="v">__TO__</div></div>
    <div class="field"><div class="k">Depart</div><div class="v">__DATE__</div></div>
    <div class="field"><div class="k">Travellers</div><div class="v">1 adult, economy</div></div>
  </div>
  <p class="snapshot">A snapshot of real fares at the time shown, not a live
    search. Airlines move prices constantly &mdash; treat these as where to
    look, then book on the site named.</p>

  <div class="pick" id="pick"></div>
  <div class="trust" id="trust"></div>

  <div class="controls">
    <div class="group"><span class="k">Stops</span>
      <button class="pill" data-filter="stops" data-value="any" aria-pressed="true">Any</button>
      <button class="pill" data-filter="stops" data-value="0" aria-pressed="false">Nonstop</button>
    </div>
    <div class="group"><span class="k">Land at</span><span id="airports"></span></div>
    <div class="group"><span class="k">Sort</span>
      <button class="pill" data-filter="sort" data-value="price" aria-pressed="true">Cheapest</button>
      <button class="pill" data-filter="sort" data-value="minutes" aria-pressed="false">Fastest</button>
      <button class="pill" data-filter="sort" data-value="depart_at" aria-pressed="false">Earliest</button>
    </div>
    <button class="pill" data-filter="saved" data-value="1" aria-pressed="false"
      id="savedonly">Saved only</button>
    <span class="tally" id="tally"></span>
  </div>

  <div class="flights" id="flights"></div>

  <footer>
    Fares gathered from __SITES__ across __AIRPORTS__ airports. We do not sell
    tickets and take no commission &mdash; the price you see is the price the
    named site was showing, and you book there.
  </footer>
</div>

<script type="application/json" id="data">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById("data").textContent);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const money = n => "$" + Number(n).toLocaleString();
const dur = m => (m >= 60 ? Math.floor(m / 60) + "h " : "") + (m % 60) + "m";
const stopText = s => s === 0 ? "Nonstop" : s === 1 ? "1 stop" : s + " stops";

const SAVED_KEY = "fareboard.saved";
function loadSaved() {
  try { return new Set(JSON.parse(localStorage.getItem(SAVED_KEY)) || []); }
  catch (e) { return new Set(); }        // private window, blocked storage
}
function keepSaved(set) {
  try { localStorage.setItem(SAVED_KEY, JSON.stringify([...set])); }
  catch (e) { /* storing is a convenience, never a requirement */ }
}
let saved = loadSaved();

const PAGE = 20;
const state = {stops: "any", airport: "all", sort: "price", saved: false,
               shown: PAGE};
const idOf = f => `${f.destination}|${f.airline}|${f.depart_at}|${f.minutes}`;

function visible() {
  return D.flights.filter(f =>
    (state.stops === "any" || f.stops === 0) &&
    (state.airport === "all" || f.destination === state.airport) &&
    (!state.saved || saved.has(idOf(f)))
  ).sort((a, b) => (a[state.sort] ?? 1e9) - (b[state.sort] ?? 1e9));
}

function renderPick() {
  const best = D.flights[0];
  if (!best) return;
  const dearest = best.offers[best.offers.length - 1];
  const cheapest = best.offers[0];
  const bits = [];
  if (dearest.price > cheapest.price) {
    bits.push(`The identical flight is <strong>${money(dearest.price)} on
      ${esc(dearest.site)}</strong> &mdash; booking the first site you thought of
      could cost you ${money(dearest.price - cheapest.price)} more for the same seat.`);
  }
  if (D.airport_saving > 0) {
    bits.push(`Landing at ${esc(D.asked_airport)} instead would add
      <strong>${money(D.airport_saving)}</strong>.`);
  }
  document.getElementById("pick").innerHTML = `
    <div class="pick-top">
      <div><div class="eyebrow">best fare found</div>
        <div class="pick-price">${money(best.price)}</div></div>
      <div>
        <div class="pick-when">${esc(best.depart)}${best.arrive ?
          ' <span style="color:var(--ink-3)">&rarr;</span> ' + esc(best.arrive) : ""}</div>
        <div class="pick-meta">${esc(best.airline)} &middot; ${esc(best.duration)}
          &middot; ${stopText(best.stops)} &middot; lands
          ${esc(D.airport_names[best.destination] || best.destination)}</div>
        <div class="pick-meta">Book on <strong style="color:var(--ink)">${
          esc(cheapest.site)}</strong></div>
      </div>
    </div>
    ${bits.length ? `<p class="pick-why">${bits.join(" ")}</p>` : ""}`;

  document.getElementById("trust").innerHTML = `
    <span><b>${D.sites}</b> booking sites checked</span>
    <span><b>${D.airports}</b> airports around the destination</span>
    <span><b>${D.searches}</b> searches in <b>${D.seconds}s</b></span>`;
}

function renderAirports() {
  const codes = [...new Set(D.flights.map(f => f.destination))].sort();
  document.getElementById("airports").innerHTML =
    [["all", "Any"], ...codes.map(c => [c, c])].map(([v, label]) =>
      `<button class="pill" data-filter="airport" data-value="${v}"
        aria-pressed="${state.airport === v}">${esc(label)}</button>`).join(" ");
}

function renderFlights() {
  const all = visible();
  const rows = all.slice(0, state.shown);
  const cheapest = rows.length ? rows[0].price : null;
  document.getElementById("tally").textContent =
    `${all.length} of ${D.flights.length} flights`;
  document.getElementById("flights").innerHTML = rows.length ? rows.map(f => {
    const id = idOf(f);
    const best = f.offers[0];
    const others = f.offers.slice(1);
    return `<article class="flight${f.price === cheapest ? " best" : ""}">
      <div>
        <div class="times">${esc(f.depart)}${f.arrive ?
          `<span class="arrow">&rarr;</span>${esc(f.arrive)}` : ""}</div>
        <div class="leg">${esc(f.airline)}<span class="dot">&middot;</span>${
          esc(f.duration)}<span class="dot">&middot;</span>
          <span class="tag ${f.stops === 0 ? "nonstop" : ""}">${stopText(f.stops)}</span>
          <span class="dot">&middot;</span><span class="tag">${esc(f.destination)}</span>
        </div>
      </div>
      <div class="buy">
        <span class="amount">${money(f.price)}</span>
        <span class="where">on ${esc(best.site)}</span>
        <button class="save" data-id="${esc(id)}"
          aria-pressed="${saved.has(id)}">${saved.has(id) ? "Saved" : "Save"}</button>
      </div>
      ${others.length ? `<div class="elsewhere">Also
        ${others.map(o => `<span class="o${o.price > best.price ? " over" : ""}">${
          esc(o.site)} ${money(o.price)}</span>`).join(" ")}</div>` : ""}
    </article>`;
  }).join("") + (all.length > rows.length ?
    `<button class="pill" id="more" style="align-self:center;margin-top:6px">
       Show ${Math.min(PAGE, all.length - rows.length)} more
       of ${all.length - rows.length}</button>` : "")
    : `<div class="none">No flights match those filters.</div>`;
}

document.addEventListener("click", e => {
  if (e.target.id === "more") {
    state.shown += PAGE;
    renderFlights();
    return;
  }
  const pill = e.target.closest(".pill");
  if (pill) {
    if (pill.dataset.filter) state.shown = PAGE;   // new filter, back to page 1
    const {filter, value} = pill.dataset;
    if (filter === "saved") {
      state.saved = !state.saved;
      pill.setAttribute("aria-pressed", state.saved);
    } else {
      state[filter] = value;
      document.querySelectorAll(`.pill[data-filter="${filter}"]`).forEach(p =>
        p.setAttribute("aria-pressed", p.dataset.value === value));
    }
    renderFlights();
    return;
  }
  const save = e.target.closest(".save");
  if (save) {
    const id = save.dataset.id;
    if (saved.has(id)) saved.delete(id); else saved.add(id);
    keepSaved(saved);
    save.setAttribute("aria-pressed", saved.has(id));
    save.textContent = saved.has(id) ? "Saved" : "Save";
    if (state.saved) renderFlights();
  }
});

renderPick();
renderAirports();
renderFlights();
</script>
"""

# The metro area is what a traveller searched for; the airport is a detail of
# the answer. "New York -> London", never "New York -> Heathrow".
METRO_CITY = {"LON": "London", "NYC": "New York", "PAR": "Paris",
              "TYO": "Tokyo", "MIL": "Milan", "ROM": "Rome", "CHI": "Chicago",
              "WAS": "Washington", "BOS": "Boston", "MIA": "Miami",
              "LAX": "Los Angeles", "SFO": "San Francisco", "TPA": "Tampa",
              "AMS": "Amsterdam", "BER": "Berlin"}

CITY = {"LHR": "Heathrow", "LGW": "Gatwick", "STN": "Stansted",
        "LTN": "Luton", "LCY": "London City", "JFK": "New York JFK",
        "EWR": "Newark", "LGA": "LaGuardia"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", nargs="+",
                    default=["results.json", "countries.json"])
    ap.add_argument("--out", default="trip.html")
    ap.add_argument("--standalone", action="store_true")
    args = ap.parse_args()

    runs = []
    for name in args.runs:
        path = HERE / name
        if path.exists():
            runs.append(json.loads(path.read_text(encoding="utf-8")))
    if not runs:
        raise SystemExit("No run data. Run compare.py first.")

    flights = itineraries.collect(runs)
    if not flights:
        raise SystemExit("No itineraries with enough detail to show.")

    base = runs[0]
    asked = base["destination"]
    best = flights[0]
    at_asked = [f["price"] for f in flights if f["destination"] == asked]
    saving = (min(at_asked) - best["price"]) if at_asked else 0

    every = [r for run in runs for r in run.get("results", [])]
    data = {
        "flights": flights,
        "airport_names": CITY,
        "asked_airport": CITY.get(asked, asked),
        "airport_saving": max(saving, 0),
        "sites": len({r["site"] for r in every}),
        "airports": len({r["destination"] for r in every}),
        "searches": len(every),
        "seconds": round(sum(run.get("seconds", 0) for run in runs)),
    }

    import airports
    dest_city = METRO_CITY.get(airports.metro_of(asked) or "",
                               CITY.get(asked, asked))
    from_city = METRO_CITY.get(airports.metro_of(base["origin"]) or "",
                               CITY.get(base["origin"], base["origin"]))
    page = (TEMPLATE
            .replace("__HEAD__", theme.head("Cheapest Way There"))
            .replace("__EXTRA__", EXTRA_CSS)
            .replace("__HEADLINE__", f"{esc_city(from_city)} &rarr; {esc_city(dest_city)}")
            .replace("__WHEN__", base.get("generated_at", "")[:16])
            .replace("__FROM__", CITY.get(base["origin"], base["origin"]))
            .replace("__TO__", f"{esc_city(dest_city)}, any airport")
            .replace("__DATE__", pretty(base["date"]))
            .replace("__SITES__", str(data["sites"]))
            .replace("__AIRPORTS__", str(data["airports"]))
            .replace("__DATA__", json.dumps(data).replace("<", "\\u003c")))

    (HERE / args.out).write_text(
        theme.standalone(page) if args.standalone else page, encoding="utf-8")
    print(f"{len(flights)} flights, best ${best['price']:,} "
          f"({best['airline']}, {best['destination']}) -> {args.out}")


def esc_city(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;")


def pretty(iso: str) -> str:
    from datetime import date
    y, m, d = (int(x) for x in iso.split("-"))
    return date(y, m, d).strftime("%a %d %b %Y")


if __name__ == "__main__":
    main()
