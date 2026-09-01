"""One dashboard over every run: cheapest fares, countries, advertised prices.

    python board.py            # -> board.html

The three studies answer different questions off the same machinery, and
flipping between three static pages to compare them is worse than one page
that holds all of it. Data is embedded and rendered in the browser, so
filtering by site or sorting the log is instant and needs no server.
"""

import argparse
import json

import theme
from common import HERE

EXTRA_CSS = """
.toolbar { display:flex; flex-wrap:wrap; gap:10px 14px; align-items:center;
           margin:22px 0 6px; }
.tabs { display:flex; gap:2px; background:var(--raise); padding:3px;
        border-radius:8px; border:1px solid var(--rule); }
.tab {
  font-family:"Saira Condensed", sans-serif; text-transform:uppercase;
  letter-spacing:.06em; font-size:13px; font-weight:600; color:var(--ink-2);
  background:none; border:0; padding:7px 14px; border-radius:6px;
  cursor:pointer; white-space:nowrap;
}
.tab:hover { color:var(--ink); }
.tab[aria-selected="true"] { background:var(--panel); color:var(--ink);
                             box-shadow:0 1px 2px rgba(0,0,0,.08); }
.tab:focus-visible, .chipbtn:focus-visible, th.sortable:focus-visible {
  outline:2px solid var(--accent); outline-offset:2px; }

.filters { display:flex; flex-wrap:wrap; gap:8px; align-items:center;
           margin:14px 0 18px; }
.filters .flabel { font-family:"IBM Plex Mono", monospace; font-size:10.5px;
                   letter-spacing:.14em; text-transform:uppercase;
                   color:var(--ink-3); margin-right:2px; }
.chipbtn {
  font-family:"IBM Plex Mono", monospace; font-size:11.5px;
  padding:4px 11px; border-radius:999px; cursor:pointer;
  border:1px solid var(--rule); background:var(--panel); color:var(--ink-2);
}
.chipbtn:hover { border-color:var(--ink-3); color:var(--ink); }
.chipbtn[aria-pressed="true"] { background:var(--ink); color:var(--ground);
                                border-color:var(--ink); }
input[type="search"] {
  font-family:"IBM Plex Mono", monospace; font-size:12.5px;
  padding:6px 11px; border-radius:6px; border:1px solid var(--rule);
  background:var(--panel); color:var(--ink); min-width:180px;
}
input[type="search"]:focus { outline:2px solid var(--accent);
                             outline-offset:1px; }
.count { font-size:12.5px; color:var(--ink-3); margin-left:auto; }

th.sortable { cursor:pointer; user-select:none; }
th.sortable:hover { color:var(--ink); }
th .arrow { opacity:.45; font-size:9px; margin-left:3px; }
th[aria-sort] .arrow { opacity:1; }
.panel[hidden] { display:none; }
.note { font-size:13px; color:var(--ink-3); margin:14px 0 0; }
.missing { background:var(--panel); border:1px dashed var(--rule);
           border-radius:6px; padding:26px; color:var(--ink-3);
           text-align:center; }
"""

TEMPLATE = """__HEAD__
<style>__EXTRA__</style>

<div class="wrap">
  <header class="mast">
    <h1>Fare Board</h1>
    <div class="sub">__ROUTE__<br>
      <span class="eyebrow">__WHEN__</span></div>
  </header>

  <div class="stats" id="tiles"></div>

  <div class="toolbar">
    <div class="tabs" role="tablist" aria-label="Views">
      <button class="tab" role="tab" data-panel="cheapest" aria-selected="true">Cheapest</button>
      <button class="tab" role="tab" data-panel="countries" aria-selected="false">Countries</button>
      <button class="tab" role="tab" data-panel="teasers" aria-selected="false">Advertised</button>
      <button class="tab" role="tab" data-panel="log" aria-selected="false">Every search</button>
    </div>
  </div>

  <div class="filters" id="filters">
    <span class="flabel">Site</span>
    <span id="sitechips"></span>
    <input type="search" id="q" placeholder="filter rows..." aria-label="Filter rows">
    <span class="count" id="count"></span>
  </div>

  <section class="panel" id="panel-cheapest">
    <h2>Which airport</h2>
    <p class="lede">Cheapest fare found at each airport in the destination
      metro area, across every site. Searching only the airport you first
      thought of is how people overpay.</p>
    <div id="airports"></div>
    <h2 style="margin-top:32px">Which site</h2>
    <p class="lede">Cheapest fare each site quoted for the route as asked, so
      the comparison is like for like.</p>
    <div id="sites"></div>
  </section>

  <section class="panel" id="panel-countries" hidden>
    <h2>Which country</h2>
    <p class="lede">The same search from residential IPs in several countries,
      every price forced to USD so this is pricing and not exchange rates.
      Highlighted cells differ from that site&rsquo;s cheapest.</p>
    <div id="countries"></div>
  </section>

  <section class="panel" id="panel-teasers" hidden>
    <h2>Advertised against delivered</h2>
    <p class="lede">The grey dot is the price a site put on screen for a search
      you had not run; the coloured dot is what that search actually returned.</p>
    <div class="legend">
      <span class="key"><i style="background:var(--ink-3)"></i>advertised</span>
      <span class="key"><i style="background:var(--ok)"></i>delivered, at or under</span>
      <span class="key"><i style="background:var(--warn)"></i>delivered, higher</span>
    </div>
    <div id="teasers"></div>
  </section>

  <section class="panel" id="panel-log" hidden>
    <h2>Every search</h2>
    <p class="lede">One cloud browser per row, each on its own residential IP.
      Click a column to sort. Blocked rows hit an anti-bot wall and stay listed
      rather than being quietly dropped.</p>
    <div class="scroll" id="log"></div>
  </section>

  <footer>
    Fares are read from each site&rsquo;s own results page at the moment shown
    and move constantly &mdash; a direction to look, not a quote. Built with
    <code>compare.py</code>, <code>verify.py</code> and <code>board.py</code>
    on Solari cloud browsers.
  </footer>
</div>

<script type="application/json" id="data">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById("data").textContent);
const NAMES = DATA.site_names || {};
const esc = s => String(s ?? "").replace(/[&<>"]/g, c =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const money = n => "$" + Number(n).toLocaleString();
const name = k => NAMES[k] || k;

const state = {
  panel: "cheapest",
  sites: new Set(),          // empty means "all"
  q: "",
  sort: "cheapest",
  dir: 1,
};

const allRows = [...(DATA.compare || []), ...(DATA.countries || [])];
const allSites = [...new Set(allRows.map(r => r.site))].sort();

/* ---------- filtering ---------- */
function keep(r) {
  if (state.sites.size && !state.sites.has(r.site)) return false;
  if (!state.q) return true;
  const hay = [r.route, r.site, name(r.site), r.country, r.status,
               (r.fares && r.fares[0] && r.fares[0].airline) || ""]
              .join(" ").toLowerCase();
  return hay.includes(state.q);
}

/* ---------- bars ---------- */
function bars(items, wide) {
  if (!items.length) return "<p class='empty'>Nothing matches.</p>";
  const top = Math.max(...items.map(i => i[1]));
  const low = Math.min(...items.map(i => i[1]));
  return `<div class="bars${wide ? " wide" : ""}">` + items.map(([label, v, note]) => `
    <div class="bar-row${v === low ? " is-best" : ""}">
      <span class="bar-label">${esc(label)}</span>
      <span class="bar-track"><span class="bar-fill"
        style="width:${(v / top * 100).toFixed(1)}%"></span></span>
      <span class="bar-value">${money(v)}</span>
      <span class="bar-note">${esc(note || "")}</span>
    </div>`).join("") + "</div>";
}

function cheapestBy(rows, key) {
  const best = new Map();
  for (const r of rows) {
    if (!r.ok) continue;
    const k = r[key];
    if (!best.has(k) || r.cheapest < best.get(k).cheapest) best.set(k, r);
  }
  return best;
}

function renderCheapest() {
  const rows = (DATA.compare || []).filter(keep);
  const byAirport = cheapestBy(rows, "destination");
  const airports = [...byAirport.entries()]
    .map(([code, r]) => [code, r.cheapest, "cheapest on " + name(r.site)])
    .sort((a, b) => a[1] - b[1]);

  const asked = DATA.asked;
  const bySite = cheapestBy(rows.filter(r => r.route === asked), "site");
  const sites = [...bySite.entries()]
    .map(([k, r]) => [name(k), r.cheapest, r.count + " fares read"])
    .sort((a, b) => a[1] - b[1]);

  document.getElementById("airports").innerHTML =
    airports.length > 1 ? bars(airports)
    : "<p class='empty'>Only one airport in this run.</p>";
  document.getElementById("sites").innerHTML = bars(sites, true);
}

/* ---------- country matrix ---------- */
function renderCountries() {
  const rows = (DATA.countries || []).filter(r => r.ok && keep(r));
  const el = document.getElementById("countries");
  if (!rows.length) {
    el.innerHTML = "<div class='missing'>No country sweep in this build.</div>";
    return;
  }
  const countries = [...new Set(rows.map(r => r.country))].sort();
  const sites = [...new Set(rows.map(r => r.site))].sort();
  const head = countries.map(c => `<th class="num">${esc(c)}</th>`).join("");
  const body = sites.map(s => {
    const q = new Map(rows.filter(r => r.site === s).map(r => [r.country, r.cheapest]));
    if (!q.size) return "";
    const low = Math.min(...q.values()), high = Math.max(...q.values());
    const cells = countries.map(c => {
      const v = q.get(c);
      return v === undefined
        ? "<td class='mono num gone'>--</td>"
        : `<td class="mono num ${v === low ? "same" : "diff"}">${money(v)}</td>`;
    }).join("");
    return `<tr><td>${esc(name(s))}</td>${cells}<td class="mono num">` +
           (high > low ? money(high - low) : "&mdash;") + "</td></tr>";
  }).join("");
  el.innerHTML = `<div class="scroll"><table><thead><tr><th>Site</th>${head}
    <th class="num">Spread</th></tr></thead><tbody>${body}</tbody></table></div>`;
}

/* ---------- dumbbells ---------- */
function renderTeasers() {
  const all = (DATA.teasers || []).filter(c =>
    !state.sites.size || state.sites.has(c.site));
  const el = document.getElementById("teasers");
  const tested = all.filter(c => c.delivered != null);
  if (!tested.length) {
    el.innerHTML = "<div class='missing'>No advertised prices verified yet.</div>";
    return;
  }
  const vals = tested.flatMap(c => [c.advertised, c.delivered]);
  const low = Math.min(...vals), high = Math.max(...vals);
  const span = Math.max(high - low, 1), pad = span * 0.08;
  const pos = v => (v - low + pad) / (span + 2 * pad) * 100;

  el.innerHTML = "<div class='dumb'>" + all
    .sort((a, b) => (a.delivered == null) - (b.delivered == null)
                    || (b.gap || 0) - (a.gap || 0))
    .map(c => {
      const label = c.date || c.destination || "";
      let track = "<span class='dumb-track'></span>";
      let price = `<span>${money(c.advertised)} advertised</span>`;
      if (c.delivered != null) {
        const a = pos(c.advertised), d = pos(c.delivered);
        track = `<span class="dumb-track">
          <span class="dumb-seg" style="left:${Math.min(a, d).toFixed(1)}%;
            width:${Math.abs(a - d).toFixed(1)}%"></span>
          <span class="dumb-dot dot-ad" style="left:${a.toFixed(1)}%"></span>
          <span class="dumb-dot dot-got" style="left:${d.toFixed(1)}%"></span>
        </span>`;
        price = `<b>${money(c.delivered)}</b> <span>(${
          c.gap ? (c.gap > 0 ? "+" : "") + c.gap.toLocaleString() : "exact"})</span>`;
      }
      return `<div class="dumb-row is-${c.verdict}">
        <span class="dumb-label">${esc(label)}<small>${esc(name(c.site))}</small></span>
        ${track}<span class="dumb-price">${price}</span>
        <span class="chip-cell"><span class="chip chip-${c.verdict}">${esc(c.verdict)}</span></span>
      </div>`;
    }).join("") + "</div>";
}

/* ---------- sortable log ---------- */
const COLS = [
  {key: "route", label: "Route", cls: "mono"},
  {key: "country", label: "From", cls: "mono"},
  {key: "site", label: "Site", get: r => name(r.site)},
  {key: "cheapest", label: "Cheapest", cls: "mono num", num: true,
   get: r => r.cheapest == null ? "--" : money(r.cheapest)},
  {key: "count", label: "Fares", cls: "mono num", num: true},
  {key: "airline", label: "Best itinerary", cls: "detail",
   get: r => [r.fares?.[0]?.airline, r.fares?.[0]?.duration, r.fares?.[0]?.stops]
             .filter(Boolean).join(" \\u00b7 ")},
  {key: "seconds", label: "Time", cls: "mono num", num: true,
   get: r => Math.round(r.seconds) + "s"},
  {key: "status", label: "Status",
   get: r => `<span class="chip chip-${r.status || "ok"}">${
     esc({ok: "read", blocked: "blocked", empty: "no flights",
          unparsed: "no fares", error: "error"}[r.status] || r.status || "read")}</span>`},
];

function renderLog() {
  const rows = allRows.filter(keep).sort((a, b) => {
    const k = state.sort;
    let x = a[k], y = b[k];
    if (k === "airline") { x = a.fares?.[0]?.airline; y = b.fares?.[0]?.airline; }
    if (x == null) return 1;
    if (y == null) return -1;
    return (typeof x === "number" ? x - y : String(x).localeCompare(String(y))) * state.dir;
  });
  const head = COLS.map(c => `<th class="sortable ${c.num ? "num" : ""}"
      tabindex="0" data-key="${c.key}"
      ${state.sort === c.key ? `aria-sort="${state.dir > 0 ? "ascending" : "descending"}"` : ""}
    >${c.label}<span class="arrow">${
      state.sort === c.key ? (state.dir > 0 ? "\\u25b2" : "\\u25bc") : "\\u25c6"}</span></th>`).join("");
  const body = rows.map(r => "<tr class='is-" + (r.status || "ok") + "'>" +
    COLS.map(c => `<td class="${c.cls || ""}">${
      c.get ? c.get(r) : esc(r[c.key] ?? "")}</td>`).join("") + "</tr>").join("");
  document.getElementById("log").innerHTML =
    `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  document.getElementById("count").textContent =
    `${rows.length} of ${allRows.length} searches`;
}

/* ---------- tiles ---------- */
function renderTiles() {
  const rows = allRows.filter(keep);
  const ok = rows.filter(r => r.ok);
  const best = ok.length ? Math.min(...ok.map(r => r.cheapest)) : null;
  const tested = (DATA.teasers || []).filter(c => c.delivered != null);
  const held = tested.filter(c => c.verdict === "holds").length;
  const tiles = [
    [best == null ? "--" : money(best), "cheapest fare found"],
    [`${ok.length}/${rows.length}`, "searches that returned fares"],
    [`${DATA.seconds}s`, "wall clock across every run"],
    [tested.length ? `${held}/${tested.length}` : "--", "advertised prices that held"],
  ];
  document.getElementById("tiles").innerHTML = tiles.map(([b, s]) =>
    `<div class="stat"><b>${b}</b><span>${s}</span></div>`).join("");
}

/* ---------- wiring ---------- */
function renderAll() {
  renderTiles();
  renderCheapest();
  renderCountries();
  renderTeasers();
  renderLog();
}

document.getElementById("sitechips").innerHTML = allSites.map(s =>
  `<button class="chipbtn" data-site="${esc(s)}" aria-pressed="false">${esc(name(s))}</button>`
).join(" ");

document.getElementById("sitechips").addEventListener("click", e => {
  const btn = e.target.closest(".chipbtn");
  if (!btn) return;
  const site = btn.dataset.site;
  if (state.sites.has(site)) state.sites.delete(site); else state.sites.add(site);
  btn.setAttribute("aria-pressed", state.sites.has(site));
  renderAll();
});

document.getElementById("q").addEventListener("input", e => {
  state.q = e.target.value.trim().toLowerCase();
  renderAll();
});

document.querySelector(".tabs").addEventListener("click", e => {
  const tab = e.target.closest(".tab");
  if (!tab) return;
  state.panel = tab.dataset.panel;
  document.querySelectorAll(".tab").forEach(t =>
    t.setAttribute("aria-selected", t === tab));
  document.querySelectorAll(".panel").forEach(p =>
    p.hidden = p.id !== "panel-" + state.panel);
});

document.getElementById("log").addEventListener("click", sortFromEvent);
document.getElementById("log").addEventListener("keydown", e => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); sortFromEvent(e); }
});
function sortFromEvent(e) {
  const th = e.target.closest("th.sortable");
  if (!th) return;
  const key = th.dataset.key;
  state.dir = state.sort === key ? -state.dir : 1;
  state.sort = key;
  renderLog();
}

renderAll();
</script>
"""


def payload(name: str) -> dict:
    path = HERE / name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--compare", default="results.json")
    ap.add_argument("--countries", default="countries.json")
    ap.add_argument("--teasers", default="teasers.json")
    ap.add_argument("--out", default="board.html")
    ap.add_argument("--standalone", action="store_true")
    args = ap.parse_args()

    comp, ctry, teas = (payload(args.compare), payload(args.countries),
                        payload(args.teasers))
    base = comp or ctry or teas
    if not base:
        raise SystemExit("No run data found. Run compare.py first.")

    names = {}
    for src in (comp, ctry, teas):
        names.update(src.get("site_names", {}))

    data = {
        "asked": f"{base.get('origin')}-{base.get('destination')}",
        "site_names": names,
        "seconds": round(sum(s.get("seconds", 0) for s in (comp, ctry, teas)
                             if s)),
        "compare": comp.get("results", []),
        "countries": ctry.get("results", []),
        "teasers": teas.get("checked", []),
    }

    when = " · ".join(filter(None, [
        f"fares read {comp['generated_at'][:16]}" if comp else "",
        f"countries {ctry['generated_at'][:16]}" if ctry else "",
        f"teasers {teas['generated_at'][:16]}" if teas else "",
    ]))
    route = (f"{base.get('origin')} &rarr; {base.get('destination')} &middot; "
             f"{base.get('date')} &middot; "
             + ("one way" if not base.get("ret") else f"returning {base['ret']}"))

    page = (TEMPLATE
            .replace("__HEAD__", theme.head("Fare Board"))
            .replace("__EXTRA__", EXTRA_CSS)
            .replace("__ROUTE__", route)
            .replace("__WHEN__", when)
            .replace("__DATA__", json.dumps(data).replace("<", "\\u003c")))

    (HERE / args.out).write_text(
        theme.standalone(page) if args.standalone else page, encoding="utf-8")
    print(f"{len(data['compare'])} + {len(data['countries'])} searches, "
          f"{len(data['teasers'])} claims -> {args.out}")


if __name__ == "__main__":
    main()
