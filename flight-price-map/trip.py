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
import json
from collections import defaultdict

import airports
import itineraries
import theme
from common import HERE

CITY = {"LHR": "Heathrow", "LGW": "Gatwick", "STN": "Stansted",
        "LTN": "Luton", "LCY": "London City", "JFK": "New York JFK",
        "EWR": "Newark", "LGA": "LaGuardia"}

METRO_CITY = {"LON": "London", "NYC": "New York", "PAR": "Paris",
              "TYO": "Tokyo", "MIL": "Milan", "ROM": "Rome", "CHI": "Chicago",
              "WAS": "Washington", "BOS": "Boston", "MIA": "Miami",
              "LAX": "Los Angeles", "SFO": "San Francisco", "TPA": "Tampa",
              "AMS": "Amsterdam", "BER": "Berlin"}

EXTRA_CSS = """
/* ---------- landing ---------- */
.hero-wrap { padding:56px 0 20px; }
.kicker { font-family:"IBM Plex Mono", monospace; font-size:11px;
          letter-spacing:.2em; text-transform:uppercase; color:var(--accent); }
.hero-h { font-family:"Saira Condensed", ui-sans-serif, sans-serif;
          font-weight:700; text-transform:uppercase; letter-spacing:.01em;
          font-size:clamp(38px,7vw,68px); line-height:.98; margin:14px 0 0;
          text-wrap:balance; max-width:16ch; }
.hero-p { font-size:17px; color:var(--ink-2); max-width:52ch; margin:18px 0 0; }
/* The sky band. Canvas rather than SVG because it is a sprite blitter, and
   pixelated rendering so the chunky pixels stay chunky on retina screens. */
.sky { display:block; width:100%; height:132px; margin-top:26px;
       image-rendering:pixelated; }

form.finder {
  display:flex; flex-wrap:wrap; align-items:stretch; gap:1px; margin-top:30px;
  background:var(--rule); border:1px solid var(--rule); border-radius:10px;
  overflow:hidden; box-shadow:var(--shadow);
}
.cell { background:var(--panel); padding:11px 16px; flex:1 1 170px;
        display:flex; flex-direction:column; justify-content:center; }
.cell label { font-family:"IBM Plex Mono", monospace; font-size:10px;
              letter-spacing:.16em; text-transform:uppercase;
              color:var(--ink-3); }
.cell input, .cell select {
  border:0; background:none; color:var(--ink); font-size:16px; font-weight:500;
  font-family:inherit; padding:3px 0 0; width:100%;
}
.cell input:focus, .cell select:focus { outline:none; }
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

.nope { background:var(--panel); border:1px solid var(--warn);
        border-radius:10px; padding:18px 22px; margin-top:18px;
        font-size:14.5px; color:var(--ink-2); }
.nope b { color:var(--ink); }
.linkish { background:none; border:0; padding:0; cursor:pointer;
           color:var(--accent); font:inherit; text-decoration:underline; }

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

.flights { display:flex; flex-direction:column; gap:10px; }
.flight { display:grid; grid-template-columns:1fr auto; gap:8px 22px;
          background:var(--panel); border:1px solid var(--rule);
          border-radius:8px; padding:16px 20px; align-items:center; }
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
  <div class="hero-wrap">
    <div class="kicker">Fare Board</div>
    <h1 class="hero-h">The cheapest way there, not the first way you find</h1>
    <p class="hero-p">One search checks every big booking site and every airport
      around your destination at the same time, then tells you which flight to
      take and which site is selling it for least.</p>
  </div>

  <canvas class="sky" id="sky" aria-hidden="true"></canvas>

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
    <div class="cell">
      <label for="when">Depart</label>
      <select id="when" name="when"></select>
    </div>
    <button class="go" type="submit">Find the fare</button>
  </form>
  <datalist id="places"></datalist>
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
  <header class="mast" style="margin-top:12px">
    <h1 id="route-h"></h1>
    <div class="sub"><span class="eyebrow" id="read-at"></span></div>
  </header>

  <div class="search" id="summary"></div>
  <p class="snapshot">A snapshot of real fares at the time shown, not a live
    search &mdash; a published page cannot drive cloud browsers. Airlines move
    prices constantly, so treat these as where to look, then book on the site
    named.</p>

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
</section>

  <footer>
    Fares are read from each site&rsquo;s own public results page and move
    constantly. We do not sell tickets and take no commission.__BOARD_LINK__
  </footer>
</div>

<script>
/* ---------- the sky ---------- */
(() => {
  const canvas = document.getElementById("sky");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  // '.' transparent, B body, A accent, W window.
  const PLANE = [
    "...BB...................",
    "...BBB..................",
    "...BBBB.................",
    "...BBBBB................",
    ".BBBBBBBBBBBBBBBBBBA....",
    "BBBWBBWBBWBBWBBBBBBBAA..",
    ".BBBBBBBBBBBBBBBBBBA....",
    "...BBBBB................",
    "...BBBB.................",
    "....BB..................",
  ];
  const CLOUD = ["..CCC...", ".CCCCCC.", "CCCCCCCC"];

  const PX = 5;
  let W = 0, H = 0, colors = {}, clouds = [], t = 0, raf = null;
  const still = matchMedia("(prefers-reduced-motion: reduce)");

  function readColors() {
    const css = getComputedStyle(document.documentElement);
    const v = n => css.getPropertyValue(n).trim();
    colors = {B: v("--ink"), A: v("--accent"), W: v("--ground"),
              C: v("--rule"), dot: v("--rule")};
  }

  function blit(rows, x, y, px) {
    for (let r = 0; r < rows.length; r++) {
      for (let c = 0; c < rows[r].length; c++) {
        const ch = rows[r][c];
        if (ch === ".") continue;
        ctx.fillStyle = colors[ch] || colors.B;
        ctx.fillRect(Math.round(x + c * px), Math.round(y + r * px), px, px);
      }
    }
  }

  function size() {
    const dpr = Math.min(devicePixelRatio || 1, 2);
    W = canvas.clientWidth; H = canvas.clientHeight;
    canvas.width = W * dpr; canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.imageSmoothingEnabled = false;
    clouds = [0.08, 0.34, 0.58, 0.82].map((frac, i) => ({
      x: frac * W,
      y: 14 + ((i * 37) % 46),
      px: i % 2 ? 3 : 4,
      speed: i % 2 ? 0.18 : 0.32,
    }));
  }

  function frame() {
    ctx.clearRect(0, 0, W, H);
    const lane = H * 0.55;

    // The route the plane is flying: a dotted line, like a boarding pass map.
    ctx.fillStyle = colors.dot;
    for (let x = 0; x < W; x += PX * 4) ctx.fillRect(x, lane + PX * 5, PX * 2, PX);

    for (const cloud of clouds) {
      blit(CLOUD, cloud.x, cloud.y, cloud.px);
      cloud.x -= cloud.speed;
      if (cloud.x < -CLOUD[0].length * cloud.px) cloud.x = W + 20;
    }

    const span = W + PLANE[0].length * PX + 80;
    const x = ((t * 1.5) % span) - PLANE[0].length * PX - 40;
    const bob = Math.sin(t / 42) * PX;
    const top = lane - PLANE.length * PX / 2 + bob;

    // Contrail: a few squares off the tail, thinning out behind it.
    for (let i = 1; i <= 7; i++) {
      ctx.globalAlpha = 0.30 - i * 0.035;
      ctx.fillStyle = colors.B;
      ctx.fillRect(Math.round(x - i * PX * 2.2), Math.round(top + PX * 5),
                   PX * 1.4, PX);
    }
    ctx.globalAlpha = 1;
    blit(PLANE, x, top, PX);

    t += 1;
    raf = requestAnimationFrame(frame);
  }

  function start() {
    if (raf) cancelAnimationFrame(raf);
    readColors(); size();
    if (still.matches) {                 // one composed frame, no motion
      t = 260; ctx.clearRect(0, 0, W, H);
      const lane = H * 0.55;
      ctx.fillStyle = colors.dot;
      for (let x = 0; x < W; x += PX * 4) ctx.fillRect(x, lane + PX * 5, PX * 2, PX);
      clouds.forEach(c => blit(CLOUD, c.x, c.y, c.px));
      blit(PLANE, W * 0.42, lane - PLANE.length * PX / 2, PX);
      return;
    }
    raf = requestAnimationFrame(frame);
  }

  addEventListener("resize", start);
  still.addEventListener("change", start);
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", start);
  // Nothing to animate for a hidden tab, and nothing to animate on the
  // results view either -- the canvas only exists on the landing page.
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && raf) { cancelAnimationFrame(raf); raf = null; }
    else if (!document.hidden && !still.matches) start();
  });
  start();
})();
</script>

<script type="application/json" id="data">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById("data").textContent);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const money = n => "$" + Number(n).toLocaleString();
const stopText = s => s === 0 ? "Nonstop" : s === 1 ? "1 stop" : s + " stops";
const norm = s => String(s || "").trim().toLowerCase();

/* ---------- which searches we hold ---------- */
function findTrip(from, to, when) {
  const f = norm(from), t = norm(to);
  return D.trips.find(tr =>
    tr.from_keys.includes(f) && tr.to_keys.includes(t) &&
    (!when || tr.date === when));
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
               saved: false, shown: PAGE};
const idOf = f => `${f.destination}|${f.airline}|${f.depart_at}|${f.minutes}`;

/* ---------- landing ---------- */
document.getElementById("places").innerHTML =
  D.places.map(p => `<option value="${esc(p)}">`).join("");
document.getElementById("when").innerHTML =
  D.dates.map(d => `<option value="${esc(d.iso)}">${esc(d.label)}</option>`).join("");

document.getElementById("finder").addEventListener("submit", e => {
  e.preventDefault();
  const from = document.getElementById("from").value;
  const to = document.getElementById("to").value;
  const when = document.getElementById("when").value;
  const trip = findTrip(from, to, when);
  if (!trip) {
    document.getElementById("nope").innerHTML = `<div class="nope">
      We have not priced <b>${esc(from)} &rarr; ${esc(to)}</b> yet. Every route
      here was gathered by actually running the searches, so the list is short
      and honest rather than long and made up.
      ${D.trips.map(t => `<button class="linkish" data-go="${esc(t.id)}">Show
        ${esc(t.from_label)} &rarr; ${esc(t.to_label)}</button>`).join(" ")}
      </div>`;
    return;
  }
  location.hash = "#/" + trip.id;
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

/* ---------- results ---------- */
function visible() {
  return state.trip.flights.filter(f =>
    (state.stops === "any" || f.stops === 0) &&
    (state.airport === "all" || f.destination === state.airport) &&
    (!state.saved || saved.has(idOf(f)))
  ).sort((a, b) => (a[state.sort] ?? 1e9) - (b[state.sort] ?? 1e9));
}

function renderTrip() {
  const t = state.trip;
  document.getElementById("route-h").innerHTML =
    `${esc(t.from_label)} <span style="color:var(--ink-3)">&rarr;</span> ${esc(t.to_label)}`;
  document.getElementById("read-at").textContent = "prices read " + t.read_at;
  document.getElementById("summary").innerHTML = [
    ["From", t.from_full], ["To", t.to_label + ", any airport"],
    ["Depart", t.date_label], ["Travellers", "1 adult, economy"],
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
        <div class="pick-meta">Book on <strong style="color:var(--ink)">${
          esc(cheapest.site)}</strong></div>
      </div>
    </div>
    ${bits.length ? `<p class="pick-why">${bits.join(" ")}</p>` : ""}`;

  document.getElementById("trust").innerHTML = `
    <span><b>${t.sites}</b> booking sites checked</span>
    <span><b>${t.airports}</b> airports around the destination</span>
    <span><b>${t.searches}</b> searches in <b>${t.seconds}s</b></span>`;

  const codes = [...new Set(t.flights.map(f => f.destination))].sort();
  document.getElementById("airports").innerHTML =
    [["all", "Any"], ...codes.map(c => [c, c])].map(([v, label]) =>
      `<button class="pill" data-filter="airport" data-value="${v}"
        aria-pressed="${state.airport === v}">${esc(label)}</button>`).join(" ");
  renderFlights();
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
       Show ${Math.min(PAGE, all.length - rows.length)} more of ${
       all.length - rows.length}</button>` : "")
    : `<div class="none">No flights match those filters.</div>`;
}

/* ---------- routing ---------- */
function route() {
  const id = location.hash.replace(/^#\\/?/, "");
  const trip = D.trips.find(t => t.id === id);
  const onResults = Boolean(trip);
  document.getElementById("landing").hidden = onResults;
  document.getElementById("results").hidden = !onResults;
  if (onResults) {
    state.trip = trip;
    state.stops = "any"; state.airport = "all"; state.sort = "price";
    state.saved = false; state.shown = PAGE;
    document.querySelectorAll(".pill[data-filter]").forEach(p =>
      p.setAttribute("aria-pressed",
        (p.dataset.filter === "stops" && p.dataset.value === "any") ||
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


def pretty(iso: str) -> str:
    from datetime import date
    y, m, d = (int(x) for x in iso.split("-"))
    return date(y, m, d).strftime("%a %d %b %Y")


def label_for(code: str) -> str:
    metro = airports.metro_of(code)
    return METRO_CITY.get(metro or "", CITY.get(code, code))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", nargs="+",
                    default=["results.json", "countries.json"])
    ap.add_argument("--out", default="trip.html")
    ap.add_argument("--board-url", default="",
                    help="link to the operator's board, if it is published")
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

    # One trip per (origin, destination metro, date) we actually priced. The
    # landing page offers only these, because a route we have not run is a
    # route we cannot answer.
    grouped = defaultdict(list)
    for flight in flights:
        metro = airports.metro_of(flight["destination"]) or flight["destination"]
        grouped[(flight["origin"], metro)].append(flight)

    trips = []
    for (origin, metro), group in grouped.items():
        base = runs[0]
        asked = base["destination"]
        at_asked = [f["price"] for f in group if f["destination"] == asked]
        every = [r for run in runs for r in run.get("results", [])
                 if r["origin"] == origin]
        from_label, to_label = label_for(origin), METRO_CITY.get(metro, metro)
        trips.append({
            "id": f"{origin}-{metro}-{base['date']}".lower(),
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
            "date": base["date"],
            "date_label": pretty(base["date"]),
            "read_at": base.get("generated_at", "")[:16].replace("T", " "),
            "flights": group,
            "asked_airport": CITY.get(asked, asked),
            "airport_saving": max(min(at_asked) - group[0]["price"], 0)
                              if at_asked else 0,
            "sites": len({r["site"] for r in every}),
            "airports": len({r["destination"] for r in every}),
            "searches": len(every),
            "seconds": round(sum(run.get("seconds", 0) for run in runs)),
        })

    lead = trips[0]
    places = sorted({t["from_full"] for t in trips} | {t["to_label"] for t in trips})
    data = {
        "trips": trips,
        "places": places,
        "dates": [{"iso": t["date"], "label": t["date_label"]} for t in trips],
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
            .replace("__EXTRA__", EXTRA_CSS)
            .replace("__DEF_FROM__", lead["from_full"])
            .replace("__DEF_TO__", lead["to_label"])
            .replace("__PROOF_PRICE__", money_str(best["price"]))
            .replace("__PROOF_TEXT__", proof_text)
            .replace("__PROOF_SUB__", proof_sub)
            .replace("__BOARD_LINK__", board_link)
            .replace("__DATA__", json.dumps(data).replace("<", "\\u003c")))

    (HERE / args.out).write_text(
        theme.standalone(page) if args.standalone else page, encoding="utf-8")
    print(f"{len(trips)} trip(s), {len(flights)} flights, "
          f"best ${best['price']:,} -> {args.out}")


def money_str(value: int) -> str:
    return f"${value:,}"


if __name__ == "__main__":
    main()
