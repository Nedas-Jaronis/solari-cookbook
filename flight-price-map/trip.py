"""The traveller's site: ask where you're going, answer where to book.

    python trip.py            # -> trip.html

Two views in one page. The landing view takes a route; submitting it shows the
flights we priced for that route, cheapest first, each labelled with the site
selling it for that price. The URL carries the search, so a result is a link
you can send someone.

The boards are for whoever runs the tool. This is for whoever takes the trip:
flights rather than searches, carriers rather than site keys, and the decision
first.
"""

import argparse
import glob
import json
import pathlib
from collections import defaultdict

import airports
import itineraries
import sky
import trips as tripslib
import theme
from common import HERE


def discover() -> list[str]:
    """Every run file on disk, newest search last.

    Listing them by hand meant a new date was priced and then silently left
    out of the page, which is a worse failure than a missing file: the page
    looks complete and is not.
    """
    named = ["results.json", "countries.json", "roundtrip.json"]
    extra = sorted(pathlib.Path(p).name
                   for p in glob.glob(str(HERE / "run-*.json")))
    return [n for n in named if (HERE / n).exists()] + extra

CITY = {"LHR": "Heathrow", "LGW": "Gatwick", "STN": "Stansted",
        "LTN": "Luton", "LCY": "London City", "JFK": "New York JFK",
        "EWR": "Newark", "LGA": "LaGuardia"}

METRO_CITY = {"LON": "London", "NYC": "New York", "PAR": "Paris",
              "TYO": "Tokyo", "MIL": "Milan", "ROM": "Rome", "CHI": "Chicago",
              "WAS": "Washington", "BOS": "Boston", "MIA": "Miami",
              "LAX": "Los Angeles", "SFO": "San Francisco", "TPA": "Tampa",
              "AMS": "Amsterdam", "BER": "Berlin"}

EXTRA_CSS = """
__STAGE_CSS__

form.finder {
  display:flex; flex-wrap:wrap; align-items:stretch; gap:1px; margin-top:30px;
  background:var(--rule); border:1px solid var(--rule); border-radius:10px;
  overflow:hidden; box-shadow:var(--shadow);
}
.cell { background:var(--panel); padding:11px 16px; flex:1 1 170px;
        display:flex; flex-direction:column; justify-content:center; }
.cell.narrow { flex:0 1 138px; }
.cell label { font-family:"IBM Plex Mono", monospace; font-size:10px;
              letter-spacing:.16em; text-transform:uppercase;
              color:var(--ink-3); }
.cell input, .cell select {
  border:0; background:none; color:var(--ink); font-size:16px; font-weight:500;
  font-family:inherit; padding:3px 0 0; width:100%;
}
.cell input:focus, .cell select:focus { outline:none; }
/* Native select chrome is a different widget on every platform and none of
   them match this page, so the arrow is ours and drawn in the ink colour. */
select {
  appearance:none; -webkit-appearance:none; cursor:pointer;
  background-image:
    linear-gradient(45deg, transparent 50%, currentColor 50%),
    linear-gradient(135deg, currentColor 50%, transparent 50%);
  background-size:5px 5px, 5px 5px;
  background-position:calc(100% - 10px) center, calc(100% - 5px) center;
  background-repeat:no-repeat;
  padding-right:22px !important;
}
select::-ms-expand { display:none; }
select option { background:var(--panel); color:var(--ink); }
.cell:focus-within { background:var(--raise); }
.go {
  border:0; cursor:pointer; background:var(--ink); color:var(--ground);
  font-family:"Saira Condensed", sans-serif; text-transform:uppercase;
  letter-spacing:.07em; font-weight:700; font-size:16px; padding:0 30px;
  flex:0 0 auto;
}
.go:hover { background:var(--accent); }
.go:focus-visible { outline:3px solid var(--accent); outline-offset:-3px; }

.how { display:grid; gap:16px; margin-top:44px;
       grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); }
.how div { border-top:2px solid var(--ink); padding-top:12px; }
.how b { display:block; font-family:"Saira Condensed", sans-serif;
         text-transform:uppercase; letter-spacing:.05em; font-size:15px; }
.how span { font-size:13.5px; color:var(--ink-2); }
.proof { margin-top:38px; background:var(--panel); border:1px solid var(--rule);
         border-radius:10px; padding:20px 24px; box-shadow:var(--shadow); }
.proof .line { font-family:"IBM Plex Mono", monospace; font-size:14px;
               font-variant-numeric:tabular-nums; }
.proof .line b { color:var(--accent); font-size:19px; }
.proof p { margin:8px 0 0; color:var(--ink-2); font-size:14px; }

.progress { margin-top:16px; background:var(--panel); border:1px solid var(--rule);
            border-radius:10px; padding:16px 20px; box-shadow:var(--shadow);
            display:flex; align-items:center; gap:14px; }
.progress .spin { width:16px; height:16px; border-radius:50%; flex:0 0 auto;
                  border:2px solid var(--rule); border-top-color:var(--accent);
                  animation:turn .9s linear infinite; }
@keyframes turn { to { transform:rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .progress .spin { animation:none; } }
.widening { display:flex; align-items:center; gap:10px; margin-top:12px;
            background:var(--raise); border:1px solid var(--rule);
            border-radius:8px; padding:9px 14px; font-size:13px;
            color:var(--ink-2); }
.widening .spin { width:13px; height:13px; border-radius:50%; flex:0 0 auto;
                  border:2px solid var(--rule); border-top-color:var(--accent);
                  animation:turn .9s linear infinite; }
.finder.busy { opacity:.55; pointer-events:none; }
.progress b { font-weight:600; }
.progress small { display:block; color:var(--ink-3); font-size:12.5px;
                  margin-top:2px; }
.nope { background:var(--panel); border:1px solid var(--warn);
        border-radius:10px; padding:18px 22px; margin-top:18px;
        font-size:14.5px; color:var(--ink-2); }
.nope b { color:var(--ink); }
.offers { display:flex; flex-direction:column; align-items:flex-start;
          gap:6px; margin-top:12px; }
.linkish { background:none; border:1px solid var(--rule); border-radius:6px;
           padding:5px 11px; cursor:pointer; color:var(--accent);
           font:inherit; font-size:13.5px; text-align:left; }
.linkish:hover { border-color:var(--accent); }

/* ---------- results ---------- */
.crumb { background:none; border:0; padding:0; cursor:pointer; font:inherit;
         font-size:13.5px; color:var(--ink-2); }
.crumb:hover { color:var(--ink); }
.search {
  display:flex; flex-wrap:wrap; align-items:stretch; gap:1px; margin-top:20px;
  background:var(--rule); border:1px solid var(--rule); border-radius:10px;
  overflow:hidden;
}
.field { background:var(--panel); padding:12px 18px; flex:1 1 150px; }
.field .k { font-family:"IBM Plex Mono", monospace; font-size:10px;
            letter-spacing:.16em; text-transform:uppercase; color:var(--ink-3); }
.field .v { font-size:16px; font-weight:500; margin-top:3px; }
.snapshot { font-size:12.5px; color:var(--ink-3); margin:8px 2px 0; }

.pick { margin-top:24px; background:var(--panel); border:1px solid var(--rule);
        border-radius:10px; box-shadow:var(--shadow); overflow:hidden; }
.pick-top { display:flex; flex-wrap:wrap; gap:26px; align-items:center;
            padding:24px 26px; }
.pick-price { font-family:"IBM Plex Mono", monospace; font-weight:600;
              font-size:clamp(42px,7vw,64px); line-height:1; color:var(--accent);
              font-variant-numeric:tabular-nums; }
.pick-when { font-size:20px; font-weight:500; }
.pick-meta { color:var(--ink-2); font-size:14px; margin-top:4px; }
.pick-why { padding:16px 26px; background:var(--raise); margin:0;
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
.pill { font-size:13px; padding:5px 13px; border-radius:999px; cursor:pointer;
        border:1px solid var(--rule); background:var(--panel);
        color:var(--ink-2); }
.pill:hover { border-color:var(--ink-3); color:var(--ink); }
.pill[aria-pressed="true"] { background:var(--ink); color:var(--ground);
                             border-color:var(--ink); }
.pill:focus-visible, .save:focus-visible { outline:2px solid var(--accent);
                                           outline-offset:2px; }
.tally { margin-left:auto; font-size:13px; color:var(--ink-3); }
.controls.refine { margin-top:-4px; gap:10px 12px; }
.sel { display:inline-flex; flex-direction:column; gap:3px;
       background:var(--panel); border:1px solid var(--rule);
       border-radius:8px; padding:6px 12px 7px; }
.sel span { font-family:"IBM Plex Mono", monospace; font-size:9.5px;
            letter-spacing:.14em; text-transform:uppercase; color:var(--ink-3); }
.sel select { border:0; background-color:transparent; color:var(--ink);
              font:inherit; font-size:13.5px; padding:0 22px 0 0; }
.sel:focus-within { border-color:var(--accent); }
.plus { font-family:"IBM Plex Mono", monospace; font-size:10px;
        color:var(--warn); vertical-align:super; margin-left:2px;
        letter-spacing:.04em; }

.flights { display:flex; flex-direction:column; gap:10px; }
.flight { display:grid; grid-template-columns:1fr auto; gap:8px 22px;
          background:var(--panel); border:1px solid var(--rule);
          border-radius:8px; padding:16px 20px; align-items:center; }
.flight:hover { border-color:var(--ink-3); }
.flight.best { border-color:var(--accent); }
.legrow { display:flex; align-items:baseline; flex-wrap:wrap; gap:4px 10px; }
.legrow.back { margin-top:7px; padding-top:7px;
               border-top:1px dashed var(--rule-soft); }
.leg.missing { color:var(--ink-3); font-style:italic; }
.way { font-family:"IBM Plex Mono", monospace; font-size:10px;
       letter-spacing:.14em; text-transform:uppercase; color:var(--ink-3);
       width:30px; flex:0 0 auto; }
.times { font-family:"IBM Plex Mono", monospace; font-size:19px;
         font-weight:500; font-variant-numeric:tabular-nums; }
.times .arrow { color:var(--ink-3); margin:0 7px; }
.leg { color:var(--ink-2); font-size:13.5px; margin-top:3px; }
.leg .dot { color:var(--ink-3); margin:0 7px; }
.tag { font-family:"IBM Plex Mono", monospace; font-size:10.5px;
       letter-spacing:.08em; text-transform:uppercase; padding:2px 7px;
       border-radius:4px; background:var(--raise); border:1px solid var(--rule);
       color:var(--ink-2); }
.tag.nonstop { background:var(--ok-bg); color:var(--ok);
               border-color:transparent; }
.buy { text-align:right; display:flex; flex-direction:column;
       align-items:flex-end; gap:4px; }
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
  .go { width:100%; padding:14px; }
}
"""

TEMPLATE = """__HEAD__
<style>__EXTRA__</style>

<div class="wrap">

<!-- ============ landing ============ -->
<section id="landing">
  <div class="stage">
    <canvas id="sky" aria-hidden="true"></canvas>
    <div class="inner">
      <div class="copy">
        <div class="kicker">Fare Board</div>
        <h1 class="hero-h">The cheapest way there, <em>not the first way you
          find</em></h1>
        <p class="hero-p">One search checks every big booking site and every
          airport around your destination at once, then tells you which flight
          to take and which site is selling it for least.</p>
      </div>

      <form class="finder" id="finder" autocomplete="off">
        <div class="cell">
          <label for="from">From</label>
          <input id="from" name="from" list="places" placeholder="City or airport"
            value="__DEF_FROM__" required>
        </div>
        <div class="cell">
          <label for="to">To</label>
          <input id="to" name="to" list="places" placeholder="City or airport"
            value="__DEF_TO__" required>
        </div>
__WHEN_CELLS__
        <div class="cell narrow">
          <label for="trip">Trip</label>
          <select id="trip" name="trip">
            <option value="oneway">One way</option>
            <option value="return">Return</option>
          </select>
        </div>
        <div class="cell narrow">
          <label for="stops">Stops</label>
          <select id="stops" name="stops">
            <option value="any">Any</option>
            <option value="0">Nonstop only</option>
          </select>
        </div>
        <button class="go" type="submit">Find the fare</button>
      </form>
      <div id="nope"></div>
    </div>
    <div class="scrollcue" aria-hidden="true"><i></i>How it works</div>
  </div>

  <datalist id="places"></datalist>
  <div id="progress" class="progress" hidden></div>
  <div id="nope"></div>

  <div class="how">
    <div><b>Every site at once</b><span>Google Flights, Kayak, Momondo,
      Expedia, Priceline and Skyscanner, searched in parallel rather than one
      after another.</span></div>
    <div><b>Every nearby airport</b><span>The airport you had in mind and every
      other one in the same metro area, because that is where the money usually
      is.</span></div>
    <div><b>No commission</b><span>We do not sell tickets. You book on whichever
      site was cheapest, and we have no reason to prefer one.</span></div>
  </div>

  <div class="proof">
    <div class="line">Last run: <b>__PROOF_PRICE__</b> __PROOF_TEXT__</div>
    <p>__PROOF_SUB__</p>
  </div>
</section>

<!-- ============ results ============ -->
<section id="results" hidden>
  <button class="crumb" id="back">&larr; New search</button>
  <div id="widening" class="widening" hidden></div>
  <header class="mast" style="margin-top:12px">
    <h1 id="route-h"></h1>
    <div class="sub"><span class="eyebrow" id="read-at"></span></div>
  </header>

  <div class="search" id="summary"></div>
  <p class="snapshot" id="snapshot"></p>

  <div class="pick" id="pick"></div>
  <div class="trust" id="trust"></div>

  <div class="controls">
    <div class="group"><span class="k">Stops</span>
      <button class="pill" data-filter="stops" data-value="any" aria-pressed="true">Any</button>
      <button class="pill" data-filter="stops" data-value="1" aria-pressed="false">1 or fewer</button>
      <button class="pill" data-filter="stops" data-value="0" aria-pressed="false">Nonstop</button>
    </div>
    <div class="group"><span class="k">Land at</span><span id="airports"></span></div>
    <button class="pill" data-filter="saved" data-value="1" aria-pressed="false"
      id="savedonly">Saved only</button>
    <span class="tally" id="tally"></span>
  </div>

  <div class="controls refine">
    <label class="sel"><span>Take off</span>
      <select id="f-depart">
        <option value="any">Any time</option>
        <option value="0-6">Red-eye, before 6am</option>
        <option value="6-12">Morning, 6am to noon</option>
        <option value="12-18">Afternoon, noon to 6pm</option>
        <option value="18-24">Evening, after 6pm</option>
      </select></label>
    <label class="sel"><span>Land</span>
      <select id="f-arrive">
        <option value="any">Any time</option>
        <option value="0-6">Before 6am</option>
        <option value="6-12">Morning</option>
        <option value="12-18">Afternoon</option>
        <option value="18-24">Evening</option>
      </select></label>
    <label class="sel"><span>Airline</span>
      <select id="f-airline"><option value="any">Any airline</option></select></label>
    <label class="sel"><span>Journey under</span>
      <select id="f-max">
        <option value="any">Any length</option>
        <option value="480">8 hours</option>
        <option value="720">12 hours</option>
        <option value="1080">18 hours</option>
        <option value="1440">24 hours</option>
      </select></label>
    <label class="sel"><span>Sort by</span>
      <select id="f-sort">
        <option value="price">Cheapest</option>
        <option value="minutes">Shortest</option>
        <option value="depart_at">Earliest take-off</option>
        <option value="arrive_at">Earliest landing</option>
      </select></label>
    <button class="pill" id="reset">Clear</button>
  </div>

  <div class="flights" id="flights"></div>
</section>

  <footer>
    Fares are read from each site&rsquo;s own public results page and move
    constantly. We do not sell tickets and take no commission.__BOARD_LINK__
  </footer>
</div>

<script>__SKY_JS__</script>

<script type="application/json" id="data">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById("data").textContent);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const money = n => "$" + Number(n).toLocaleString();
const stopText = s => s === 0 ? "Nonstop" : s === 1 ? "1 stop" : s + " stops";
const norm = s => String(s || "").trim().toLowerCase();

/* ---------- which searches we hold ---------- */
function findTrip(from, to, when, kind) {
  const f = norm(from), t = norm(to);
  return D.trips.find(tr =>
    tr.from_keys.includes(f) && tr.to_keys.includes(t) &&
    (!when || tr.date === when) && (!kind || tr.kind === kind));
}

/* ---------- saved flights, per browser ---------- */
const SAVED_KEY = "fareboard.saved";
function loadSaved() {
  try { return new Set(JSON.parse(localStorage.getItem(SAVED_KEY)) || []); }
  catch (e) { return new Set(); }      // private window, or storage blocked
}
function keepSaved(set) {
  try { localStorage.setItem(SAVED_KEY, JSON.stringify([...set])); }
  catch (e) { /* saving is a convenience, never a requirement */ }
}
let saved = loadSaved();

const PAGE = 20;
const state = {trip: null, stops: "any", airport: "all", sort: "price",
               saved: false, shown: PAGE,
               depart: "any", arrive: "any", airline: "any", max: "any"};
const REFINE = {depart: "f-depart", arrive: "f-arrive", airline: "f-airline",
                max: "f-max", sort: "f-sort"};
const within = (mins, window) => {
  if (window === "any") return true;
  if (mins === null || mins === undefined) return false;
  const [from, to] = window.split("-").map(Number);
  const hour = mins / 60;
  return hour >= from && hour < to;
};
const idOf = f => `${f.destination}|${f.airline}|${f.depart_at}|${f.minutes}`;

/* ---------- landing ---------- */
if (D.live) {
  document.getElementById("places").innerHTML =
    D.places.map(p => `<option value="${esc(p.label)}">`).join("");
  const when = document.getElementById("when");
  const soon = new Date(Date.now() + 42 * 86400000);
  when.value = soon.toISOString().slice(0, 10);
  when.min = new Date().toISOString().slice(0, 10);
  const retcell = document.getElementById("retcell");
  document.getElementById("trip").addEventListener("change", e => {
    retcell.hidden = e.target.value !== "return";
    if (!retcell.hidden && !document.getElementById("retdate").value) {
      const back = new Date(Date.now() + 49 * 86400000);
      document.getElementById("retdate").value = back.toISOString().slice(0, 10);
    }
  });
} else {
  document.getElementById("places").innerHTML =
    D.places.map(p => `<option value="${esc(p)}">`).join("");
  document.getElementById("when").innerHTML =
    D.dates.map(d => `<option value="${esc(d.iso)}">${esc(d.label)}</option>`).join("");
}

const progress = document.getElementById("progress");

function working(headline, detail) {
  document.getElementById("finder").classList.add("busy");
  progress.hidden = false;
  progress.innerHTML = `<span class="spin"></span><div><b>${esc(headline)}</b>
    <small>${esc(detail || "")}</small></div>`;
}
function stopWorking() {
  progress.hidden = true;
  progress.innerHTML = "";
  document.getElementById("finder").classList.remove("busy");
  const strip = document.getElementById("widening");
  strip.hidden = true;
  strip.innerHTML = "";
}

function stillWidening(detail) {
  const strip = document.getElementById("widening");
  strip.hidden = false;
  strip.innerHTML = `<span class="spin"></span><span>${esc(detail)}</span>`;
}

const codeOf = value => {
  const inParens = String(value).match(/[(]([A-Za-z]{3})[)]\\s*$/);
  if (inParens) return inParens[1].toUpperCase();
  const bare = String(value).trim().toUpperCase();
  if (/^[A-Z]{3}$/.test(bare)) return bare;
  const needle = String(value).trim().toLowerCase();
  const hit = (D.places || []).find(p => p.label.toLowerCase().includes(needle));
  return hit ? hit.code : null;
};

function showJob(job) {
  if (!job.trip) return false;
  const arriving = document.getElementById("results").hidden;
  state.trip = job.trip;
  document.getElementById("landing").hidden = true;
  document.getElementById("results").hidden = false;
  renderTrip();
  if (arriving) {
    progress.hidden = true;                 // the spinner lived on the search
    window.scrollTo(0, 0);
  }
  return true;
}

async function liveSearch(from, to, date, ret) {
  const body = {from, to, date, ret: ret || null, nearby: true};
  working("Checking every site at once",
          `${from} to ${to}, ${date}. Four sites in parallel, about twenty seconds.`);
  progress.scrollIntoView({block: "center", behavior: "smooth"});
  let job;
  try {
    const res = await fetch("/api/search", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body)});
    job = await res.json();
    if (!res.ok) throw new Error(job.error || "the search was refused");
  } catch (err) {
    stopWorking();
    document.getElementById("nope").innerHTML =
      `<div class="nope">Could not reach the search service. Is
       <code>python server.py</code> running? <b>${esc(err.message)}</b></div>`;
    return;
  }

  if (job.from_cache && showJob(job)) {
    stopWorking();
    return;
  }

  const started = Date.now();
  const timer = setInterval(async () => {
    let now;
    try { now = await (await fetch("/api/search/" + job.id)).json(); }
    catch (err) { return; }                       // a dropped poll is not fatal

    if (now.phase === "failed" || (now.phase === "done" && !now.trip)) {
      clearInterval(timer); stopWorking();
      document.getElementById("nope").innerHTML =
        `<div class="nope">${esc(now.error || "No fares came back for that route.")}
         </div>`;
      return;
    }
    const onResults = !document.getElementById("results").hidden;
    if (now.trip) showJob(now);
    if (now.phase === "widening") {
      const also = (now.widening_to || []).join(", ");
      if (onResults || now.trip) {
        stillWidening(`Also checking ${also} — ${now.answered} searches answered so far.`);
      } else {
        working("Now trying the nearby airports",
                `Found ${now.answered} so far. Adding ${also}.`);
      }
    } else if (now.phase !== "done") {
      working("Checking every site at once",
              `${Math.round((Date.now() - started) / 1000)}s so far. Nothing to show until the first site answers.`);
    }
    if (now.phase === "done") { clearInterval(timer); stopWorking(); }
  }, 1500);
}

document.getElementById("finder").addEventListener("submit", e => {
  e.preventDefault();
  document.getElementById("nope").innerHTML = "";

  if (D.live) {
    const from = codeOf(document.getElementById("from").value);
    const to = codeOf(document.getElementById("to").value);
    const date = document.getElementById("when").value;
    const kind = document.getElementById("trip").value;
    const ret = kind === "return"
      ? document.getElementById("retdate").value : null;
    if (!from || !to) {
      document.getElementById("nope").innerHTML = `<div class="nope">
        Use an airport code or pick from the list &mdash; <b>JFK</b>,
        <b>LHR</b>, <b>Barcelona (BCN)</b>.</div>`;
      return;
    }
    if (kind === "return" && !ret) {
      document.getElementById("nope").innerHTML =
        `<div class="nope">A return trip needs a date to come back on.</div>`;
      return;
    }
    location.hash = `#/live?from=${from}&to=${to}&date=${date}` +
                    (ret ? `&ret=${ret}` : "");
    return;
  }

  const from = document.getElementById("from").value;
  const to = document.getElementById("to").value;
  const when = document.getElementById("when").value;
  const kind = document.getElementById("trip").value;
  const trip = findTrip(from, to, when, kind);
  if (!trip) {
    document.getElementById("nope").innerHTML = `<div class="nope">
      We have not priced <b>${esc(from)} &rarr; ${esc(to)}</b>${
        kind === "return" ? " as a return" : " one way"} yet. Every route
      here was gathered by actually running the searches, so the list is short
      and honest rather than long and made up.
      <div class="offers">${D.trips.map(t =>
        `<button class="linkish" data-go="${esc(t.id)}">${esc(t.from_label)}
         &rarr; ${esc(t.to_label)}, ${esc(t.date_label)}${
           t.kind === "return" ? ", back " + esc(t.ret_label) : ", one way"
         }</button>`).join("")}</div>
      </div>`;
    return;
  }
  const stops = document.getElementById("stops").value;
  // The choice rides in the URL, so a filtered result is still a link you can
  // send someone, and the results page can offer to widen it again.
  location.hash = "#/" + trip.id + (stops === "0" ? "?stops=0" : "");
});

document.addEventListener("click", e => {
  const go = e.target.closest("[data-go]");
  if (go) { location.hash = "#/" + go.dataset.go; return; }

  const pill = e.target.closest(".pill");
  if (pill && pill.dataset.filter) {
    const {filter, value} = pill.dataset;
    state.shown = PAGE;
    if (filter === "saved") {
      state.saved = !state.saved;
      pill.setAttribute("aria-pressed", state.saved);
    } else {
      state[filter] = value;
      document.querySelectorAll(`.pill[data-filter="${filter}"]`).forEach(p =>
        p.setAttribute("aria-pressed", p.dataset.value === value));
      if (filter === "stops" && state.trip) {
        history.replaceState(null, "", "#/" + state.trip.id +
          (value === "0" ? "?stops=0" : ""));   // no hashchange, no re-route
      }
    }
    renderFlights();
    return;
  }
  if (e.target.id === "more") { state.shown += PAGE; renderFlights(); return; }

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

document.getElementById("back").addEventListener("click", () => {
  location.hash = "";
});

for (const [key, id] of Object.entries(REFINE)) {
  document.getElementById(id).addEventListener("change", e => {
    state[key] = e.target.value;
    state.shown = PAGE;
    renderFlights();
  });
}

document.getElementById("reset").addEventListener("click", () => {
  Object.assign(state, {depart: "any", arrive: "any", airline: "any",
                        max: "any", sort: "price", stops: "any",
                        airport: "all", saved: false, shown: PAGE});
  for (const [key, id] of Object.entries(REFINE)) {
    document.getElementById(id).value = state[key];
  }
  document.querySelectorAll(".pill[data-filter]").forEach(p =>
    p.setAttribute("aria-pressed",
      (p.dataset.filter === "stops" && p.dataset.value === "any") ||
      (p.dataset.filter === "airport" && p.dataset.value === "all")));
  renderFlights();
});

/* ---------- results ---------- */
function visible() {
  return state.trip.flights.filter(f =>
    (state.stops === "any" || (f.stops !== null && f.stops <= +state.stops)) &&
    (state.airport === "all" || f.destination === state.airport) &&
    (state.airline === "any" || f.airline === state.airline) &&
    (state.max === "any" || (f.minutes || 0) <= +state.max) &&
    within(f.depart_at, state.depart) &&
    within(f.arrive_at, state.arrive) &&
    (!state.saved || saved.has(idOf(f)))
  ).sort((a, b) => (a[state.sort] ?? 1e9) - (b[state.sort] ?? 1e9));
}

const SNAPSHOT_LIVE =
  "Searched just now, across every site at once. Airlines move prices "
  + "constantly, so book on the site named while it is still there.";
const SNAPSHOT_STORED =
  "A snapshot of real fares at the time shown, not a live search — a "
  + "published page cannot drive cloud browsers. Treat these as where to "
  + "look, then book on the site named.";

function renderTrip() {
  const t = state.trip;
  document.getElementById("snapshot").textContent =
    D.live ? SNAPSHOT_LIVE : SNAPSHOT_STORED;
  document.getElementById("route-h").innerHTML =
    `${esc(t.from_label)} <span style="color:var(--ink-3)">&rarr;</span> ${esc(t.to_label)}`;
  document.getElementById("read-at").textContent = "prices read " + t.read_at;
  document.getElementById("summary").innerHTML = [
    ["From", t.from_full], ["To", t.to_label + ", any airport"],
    ["Depart", t.date_label],
    t.ret_label ? ["Return", t.ret_label] : ["Trip", "One way"],
    ["Travellers", "1 adult, economy"],
  ].map(([k, v]) => `<div class="field"><div class="k">${k}</div>
      <div class="v">${esc(v)}</div></div>`).join("");

  const best = t.flights[0];
  const cheapest = best.offers[0];
  const dearest = best.offers[best.offers.length - 1];
  const bits = [];
  if (dearest.price > cheapest.price) {
    bits.push(`The identical flight is <strong>${money(dearest.price)} on
      ${esc(dearest.site)}</strong> &mdash; booking the first site you thought
      of would cost ${money(dearest.price - cheapest.price)} more for the same
      seat.`);
  }
  if (t.airport_saving > 0) {
    bits.push(`Landing at ${esc(t.asked_airport)} instead would add
      <strong>${money(t.airport_saving)}</strong>.`);
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
        ${best.back_depart ? `<div class="pick-meta">Back ${esc(best.back_depart)}
          <span style="color:var(--ink-3)">&rarr;</span> ${esc(best.back_arrive || "")}
          &middot; ${esc(best.back_airline || "")} &middot; ${esc(best.back_duration || "")}
          &middot; ${stopText(best.back_stops)}</div>` : ""}
        <div class="pick-meta">Book on <strong style="color:var(--ink)">${
          esc(cheapest.site)}</strong></div>
      </div>
    </div>
    ${bits.length ? `<p class="pick-why">${bits.join(" ")}</p>` : ""}`;

  document.getElementById("trust").innerHTML = `
    <span><b>${t.sites}</b> booking site${t.sites === 1 ? "" : "s"} checked</span>
    <span><b>${t.airports}</b> airport${t.airports === 1 ? "" : "s"} around
      the destination</span>
    <span><b>${t.searches}</b> search${t.searches === 1 ? "" : "es"} in
      <b>${t.seconds}s</b></span>`;

  const airlines = [...new Set(t.flights.map(f => f.airline).filter(Boolean))].sort();
  document.getElementById("f-airline").innerHTML =
    `<option value="any">Any airline</option>` + airlines.map(a =>
      `<option value="${esc(a)}">${esc(a)}</option>`).join("");

  const codes = [...new Set(t.flights.map(f => f.destination))].sort();
  document.getElementById("airports").innerHTML =
    [["all", "Any"], ...codes.map(c => [c, c])].map(([v, label]) =>
      `<button class="pill" data-filter="airport" data-value="${v}"
        aria-pressed="${state.airport === v}">${esc(label)}</button>`).join(" ");
  renderFlights();
}

function legRow(f, back) {
  const dep = back ? f.back_depart : f.depart;
  const arr = back ? f.back_arrive : f.arrive;
  const air = back ? f.back_airline : f.airline;
  const dur = back ? f.back_duration : f.duration;
  const stp = back ? f.back_stops : f.stops;
  const where = back ? f.origin : f.destination;
  const over = back ? f.back_arrive_next_day : f.arrive_next_day;
  return `<div class="legrow${back ? " back" : ""}">
    ${f.back_depart ? `<span class="way">${back ? "Back" : "Out"}</span>` : ""}
    <span class="times">${esc(dep)}${arr ?
      `<span class="arrow">&rarr;</span>${esc(arr)}${over ?
        `<span class="plus" title="lands the next day">+${over}</span>` : ""}` : ""}</span>
    <span class="leg">${esc(air || "")}${dur ?
      `<span class="dot">&middot;</span>${esc(dur)}` : ""}
      ${stp === null || stp === undefined ? "" :
        `<span class="dot">&middot;</span><span class="tag ${
          stp === 0 ? "nonstop" : ""}">${stopText(stp)}</span>`}
      <span class="dot">&middot;</span><span class="tag">${esc(where)}</span>
    </span>
  </div>`;
}

function renderFlights() {
  const all = visible();
  const rows = all.slice(0, state.shown);
  const cheapest = rows.length ? Math.min(...all.map(f => f.price)) : null;
  document.getElementById("tally").textContent =
    `${all.length} of ${state.trip.flights.length} flights`;
  document.getElementById("flights").innerHTML = rows.length ? rows.map(f => {
    const id = idOf(f);
    const best = f.offers[0];
    const others = f.offers.slice(1);
    return `<article class="flight${f.price === cheapest ? " best" : ""}">
      <div>
        ${legRow(f, false)}
        ${f.back_depart ? legRow(f, true)
          : state.trip.kind === "return"
          ? `<div class="legrow back"><span class="way">Back</span>
             <span class="leg missing">return leg not listed by ${
               esc(f.offers[0].site)} &mdash; the price is for the whole
               trip</span></div>` : ""}
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
       Show ${Math.min(PAGE, all.length - rows.length)} more of ${
       all.length - rows.length}</button>` : "")
    : `<div class="none">No flights match those filters.</div>`;
}

/* ---------- routing ---------- */
function route() {
  const raw = location.hash.replace(/^#\\/?/, "");
  const [id, query] = raw.split("?");
  const params = new URLSearchParams(query || "");

  // A live search is a link too: the route rides in the hash, so a result can
  // be sent to someone and the service answers it again from cache.
  if (D.live && id === "live" && params.get("from")) {
    state.stops = "any"; state.airport = "all"; state.sort = "price";
    state.saved = false; state.shown = PAGE;
    state.depart = "any"; state.arrive = "any";
    state.airline = "any"; state.max = "any";
    liveSearch(params.get("from"), params.get("to"),
               params.get("date"), params.get("ret"));
    return;
  }

  const trip = D.trips.find(t => t.id === id);
  const onResults = Boolean(trip);
  document.getElementById("landing").hidden = onResults;
  document.getElementById("results").hidden = !onResults;
  if (onResults) {
    state.trip = trip;
    state.stops = params.get("stops") === "0" ? "0" : "any";
    state.airport = "all"; state.sort = "price";
    state.saved = false; state.shown = PAGE;
    state.depart = "any"; state.arrive = "any";
    state.airline = "any"; state.max = "any";
    for (const [key, id] of Object.entries(REFINE)) {
      const el = document.getElementById(id);
      if (el) el.value = state[key];
    }
    document.querySelectorAll(".pill[data-filter]").forEach(p =>
      p.setAttribute("aria-pressed",
        (p.dataset.filter === "stops" && p.dataset.value === state.stops) ||
        (p.dataset.filter === "sort" && p.dataset.value === "price")));
    renderTrip();
    window.scrollTo(0, 0);
  } else {
    document.getElementById("nope").innerHTML = "";
  }
}
addEventListener("hashchange", route);
route();
</script>
"""


WHEN_STORED = """        <div class="cell">
          <label for="when">Depart</label>
          <select id="when" name="when"></select>
        </div>"""

WHEN_LIVE = """        <div class="cell">
          <label for="when">Depart</label>
          <input type="date" id="when" name="when" required>
        </div>
        <div class="cell narrow" id="retcell" hidden>
          <label for="retdate">Back</label>
          <input type="date" id="retdate" name="retdate">
        </div>"""


def pretty(iso: str) -> str:
    from datetime import date
    y, m, d = (int(x) for x in iso.split("-"))
    return date(y, m, d).strftime("%a %d %b %Y")


def label_for(code: str) -> str:
    metro = airports.metro_of(code)
    return METRO_CITY.get(metro or "", CITY.get(code, code))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", nargs="+", default=None,
                    help="run files to read; defaults to every one on disk")
    ap.add_argument("--out", default="trip.html")
    ap.add_argument("--board-url", default="",
                    help="link to the operator's board, if it is published")
    ap.add_argument("--live", action="store_true",
                    help="search any route through server.py instead of only "
                         "the ones already priced")
    ap.add_argument("--standalone", action="store_true")
    args = ap.parse_args()
    args.runs = args.runs or discover()

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

    # One trip per (origin, destination metro, date) we actually priced. The
    # landing page offers only these, because a route we have not run is a
    # route we cannot answer.
    grouped = defaultdict(list)
    for flight in flights:
        metro = airports.metro_of(flight["destination"]) or flight["destination"]
        grouped[(flight["origin"], metro, flight["date"],
                 flight["ret"] or "")].append(flight)

    trips = []
    for (origin, metro, when, back), group in grouped.items():
        base = next((r for r in runs
                     if r["date"] == when and (r.get("ret") or "") == back),
                    runs[0])
        asked = base["destination"]
        at_asked = [f["price"] for f in group if f["destination"] == asked]
        every = [r for run in runs if run["date"] == when
                 and (run.get("ret") or "") == back
                 for r in run.get("results", []) if r["origin"] == origin]
        from_label, to_label = label_for(origin), METRO_CITY.get(metro, metro)
        trips.append({
            "id": f"{origin}-{metro}-{when}-{'rt' if back else 'ow'}".lower(),
            "kind": "return" if back else "oneway",
            "ret": back or None,
            "ret_label": pretty(back) if back else None,
            "from_label": from_label,
            "from_full": CITY.get(origin, origin),
            "to_label": to_label,
            # Everything a person might type that should find this trip.
            "from_keys": sorted({origin.lower(), from_label.lower(),
                                 CITY.get(origin, origin).lower()}),
            "to_keys": sorted({metro.lower(), to_label.lower()}
                              | {c.lower() for c in airports.expand(metro)}
                              | {CITY.get(c, c).lower()
                                 for c in airports.expand(metro)}),
            "date": when,
            "date_label": pretty(when),
            "read_at": base.get("generated_at", "")[:16].replace("T", " "),
            "flights": group,
            "asked_airport": CITY.get(asked, asked),
            "airport_saving": max(min(at_asked) - group[0]["price"], 0)
                              if at_asked else 0,
            "sites": len({r["site"] for r in every}),
            "airports": len({r["destination"] for r in every}),
            "searches": len(every),
            "seconds": round(sum(run.get("seconds", 0) for run in runs
                                 if run["date"] == when
                                 and (run.get("ret") or "") == back)),
        })
    trips.sort(key=lambda t: (t["kind"] != "oneway", t["date"]))

    lead = trips[0]
    if args.live:
        # Every airport we know how to name, so the box can suggest rather than
        # demand that someone remember a three-letter code.
        seen = {}
        for metro, codes in airports.METROS.items():
            for code in codes:
                seen[code] = f"{CITY.get(code, code)} ({code})"
        for code, name in CITY.items():
            seen.setdefault(code, f"{name} ({code})")
        places = [{"code": c, "label": seen[c]} for c in sorted(seen)]
    else:
        places = sorted({t["from_full"] for t in trips}
                        | {t["to_label"] for t in trips})
    data = {
        "live": bool(args.live),
        "trips": trips,
        "places": places,
        # One entry per date, not per trip: a date priced both one way and
        # return would otherwise appear twice in the same dropdown.
        "dates": [{"iso": iso, "label": label} for iso, label in
                  sorted({(t["date"], t["date_label"]) for t in trips})],
        "airport_names": CITY,
    }

    best = lead["flights"][0]
    proof_text = (f"{best['airline']} to "
                  f"{CITY.get(best['destination'], best['destination'])}, "
                  f"{lead['from_label']} to {lead['to_label']}")
    proof_sub = (f"Found by checking {lead['sites']} sites across "
                 f"{lead['airports']} airports &mdash; {lead['searches']} "
                 f"searches in {lead['seconds']} seconds. The same seat was "
                 f"{money_str(best['offers'][-1]['price'])} on "
                 f"{best['offers'][-1]['site']}.")

    board_link = (f' <a href="{args.board_url}" style="color:var(--accent)">'
                  f'See every search behind these prices</a>.'
                  if args.board_url else "")

    page = (TEMPLATE
            .replace("__HEAD__", theme.head("Fare Board"))
            .replace("__EXTRA__", EXTRA_CSS.replace("__STAGE_CSS__", sky.CSS))
            .replace("__SKY_JS__", sky.JS)
            .replace("__WHEN_CELLS__", WHEN_LIVE if args.live else WHEN_STORED)
            .replace("__DEF_FROM__",
                     "New York JFK (JFK)" if args.live else lead["from_full"])
            .replace("__DEF_TO__",
                     "Barcelona (BCN)" if args.live else lead["to_label"])
            .replace("__PROOF_PRICE__", money_str(best["price"]))
            .replace("__PROOF_TEXT__", proof_text)
            .replace("__PROOF_SUB__", proof_sub)
            .replace("__BOARD_LINK__", board_link)
            .replace("__DATA__", json.dumps(data).replace("<", "\\u003c")))

    (HERE / args.out).write_text(
        theme.standalone(page) if args.standalone else page, encoding="utf-8")
    print(f"{len(trips)} trip(s), {len(flights)} flights, "
          f"best ${best['price']:,} -> {args.out}"
          + (" (live)" if args.live else ""))


def money_str(value: int) -> str:
    return f"${value:,}"


if __name__ == "__main__":
    main()
