"""Turn results.json into a departure board you can read at a glance.

    python compare.py --from JFK --to LHR --date 2026-10-15 --nearby to
    python dashboard.py            # -> dashboard.html

The page answers one question first -- what is the cheapest way to make this
trip, and how much does the obvious choice cost you -- and only then shows the
evidence behind it.
"""

import argparse
import html
import json
from collections import defaultdict

from common import HERE

FONTS = ("https://fonts.googleapis.com/css2?"
         "family=Saira+Condensed:wght@500;600;700&"
         "family=Public+Sans:ital,wght@0,400;0,500;0,600;1,400&"
         "family=IBM+Plex+Mono:wght@400;500;600&display=swap")


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def bar_rows(items, unit="$", wide=False) -> str:
    """Horizontal magnitude bars: one hue, cheapest emphasised.

    Bars encode one measure (price), so this is a single series -- no legend
    and no categorical palette needed. The scale starts at zero.

    `items` are (label, value, note); the note is shown, not just hovered.
    """
    if not items:
        return "<p class='empty'>Nothing read.</p>"
    values = [v for _, v, *_ in items]
    top, low = max(values), min(values)
    out = [f"<div class='bars{' wide' if wide else ''}'>"]
    for label, value, *rest in items:
        note = rest[0] if rest else ""
        best = value == low
        out.append(
            f"<div class='bar-row{' is-best' if best else ''}'>"
            f"<span class='bar-label'>{esc(label)}</span>"
            f"<span class='bar-track'>"
            f"<span class='bar-fill' style='width:{value / top * 100:.1f}%'></span>"
            f"</span>"
            f"<span class='bar-value'>{unit}{value:,}</span>"
            f"<span class='bar-note'>{esc(note)}</span>"
            f"</div>")
    out.append("</div>")
    return "\n".join(out)


def build(data: dict) -> str:
    results = data["results"]
    names = data.get("site_names", {})
    good = [r for r in results if r.get("ok")]
    asked = f"{data['origin']}-{data['destination']}"

    best = min(good, key=lambda r: r["cheapest"]) if good else None
    baseline_rows = [r for r in good if r["route"] == asked]
    baseline = min(baseline_rows, key=lambda r: r["cheapest"]) if baseline_rows else None
    saving = (baseline["cheapest"] - best["cheapest"]) if best and baseline else 0

    # Cheapest per destination airport, across every site.
    by_airport = defaultdict(list)
    for r in good:
        by_airport[r["destination"]].append(r)
    airport_items = sorted(
        ((code, min(rows, key=lambda r: r["cheapest"])["cheapest"],
          f"cheapest on {names.get(min(rows, key=lambda r: r['cheapest'])['site'], '')}")
         for code, rows in by_airport.items()),
        key=lambda t: t[1])

    # Cheapest per site, on the route actually asked for -- apples to apples.
    by_site = defaultdict(list)
    for r in baseline_rows:
        by_site[r["site"]].append(r)
    site_items = sorted(
        ((names.get(k, k), min(rows, key=lambda r: r["cheapest"])["cheapest"],
          f"{min(rows, key=lambda r: r['cheapest'])['count']} fares read")
         for k, rows in by_site.items()),
        key=lambda t: t[1])

    labels = {"ok": "read", "blocked": "blocked", "empty": "no flights",
              "unparsed": "no fares", "error": "error"}
    board = []
    for r in sorted(results, key=lambda r: (not r.get("ok"),
                                            r.get("cheapest") or 10**9)):
        state = r.get("status") or ("ok" if r.get("ok") else "unparsed")
        label = labels.get(state, state)
        cheapest = f"${r['cheapest']:,}" if r.get("cheapest") else "--"
        top = (r.get("fares") or [{}])[0]
        detail = " · ".join(x for x in [top.get("airline"), top.get("duration"),
                                        top.get("stops")] if x)
        board.append(
            f"<tr class='is-{state}'>"
            f"<td class='mono'>{esc(r['route'])}</td>"
            f"<td>{esc(names.get(r['site'], r['site']))}</td>"
            f"<td class='mono num'>{esc(cheapest)}</td>"
            f"<td class='mono num'>{esc(r.get('count') or '')}</td>"
            f"<td class='detail'>{esc(detail)}</td>"
            f"<td class='mono num'>{r['seconds']:.0f}s</td>"
            f"<td><span class='chip chip-{state}'>{esc(label)}</span></td>"
            f"</tr>")

    walltime = data.get("seconds", 0)
    serial = sum(r["seconds"] for r in results)
    trip = ("one way" if not data.get("ret")
            else f"returning {data['ret']}")

    headline = (f"${best['cheapest']:,}" if best else "no result")
    hero_route = esc(best["route"]) if best else "--"
    hero_via = esc(names.get(best["site"], "")) if best else ""

    if saving > 0 and baseline:
        verdict = (f"<strong>${saving:,} cheaper</strong> than the best "
                   f"{esc(asked)} fare anyone quoted "
                   f"(${baseline['cheapest']:,}), for an airport in the same "
                   f"metro area.")
    elif baseline:
        verdict = (f"The airport you asked for is also the cheapest. "
                   f"Every alternative in the metro area came back dearer.")
    else:
        verdict = "No fare was read for the route as asked."

    return TEMPLATE.format(
        fonts=FONTS,
        origin=esc(data["origin"]), destination=esc(data["destination"]),
        date=esc(data["date"]), trip=esc(trip),
        generated=esc(data.get("generated_at", "")),
        headline=esc(headline), hero_route=hero_route, hero_via=hero_via,
        verdict=verdict,
        searches=len(results), succeeded=len(good),
        walltime=f"{walltime:.0f}",
        serial=f"{serial / 60:.0f}",
        speedup=f"{serial / walltime:.0f}" if walltime else "--",
        airports=bar_rows(airport_items),
        sites=bar_rows(site_items, wide=True),
        asked=esc(asked),
        board="\n".join(board),
    )


TEMPLATE = """<title>Fare Board</title>
<link rel="stylesheet" href="{fonts}">
<style>
:root {{
  color-scheme: light;
  --ground:#e9ecf0; --panel:#ffffff; --raise:#f6f7f9;
  --ink:#0e141b; --ink-2:#4d5966; --ink-3:#7b8794;
  --rule:#d3d9e0; --rule-soft:#e4e8ed;
  --accent:#b45c07; --accent-soft:#f3e3cf;
  --bar:#c2670a; --bar-best:#0e141b;
  --ok:#0f7a4d; --ok-bg:#dff0e6;
  --warn:#9a5b00; --warn-bg:#f7e6cb;
  --bad:#a63232; --bad-bg:#f6dede;
  --shadow:0 1px 2px rgba(14,20,27,.06), 0 8px 24px rgba(14,20,27,.05);
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    color-scheme: dark;
    --ground:#0f1216; --panel:#171c22; --raise:#1d232a;
    --ink:#f1ede4; --ink-2:#a7b1bc; --ink-3:#7c8794;
    --rule:#29313a; --rule-soft:#212831;
    --accent:#f0a63c; --accent-soft:#3a2c17;
    --bar:#d98f2c; --bar-best:#f6d9a8;
    --ok:#5fcf95; --ok-bg:#12301f;
    --warn:#e0a44a; --warn-bg:#33260f;
    --bad:#f08a8a; --bad-bg:#361b1b;
    --shadow:0 1px 2px rgba(0,0,0,.4), 0 10px 30px rgba(0,0,0,.35);
  }}
}}
:root[data-theme="dark"] {{
  color-scheme: dark;
  --ground:#0f1216; --panel:#171c22; --raise:#1d232a;
  --ink:#f1ede4; --ink-2:#a7b1bc; --ink-3:#7c8794;
  --rule:#29313a; --rule-soft:#212831;
  --accent:#f0a63c; --accent-soft:#3a2c17;
  --bar:#d98f2c; --bar-best:#f6d9a8;
  --ok:#5fcf95; --ok-bg:#12301f;
  --warn:#e0a44a; --warn-bg:#33260f;
  --bad:#f08a8a; --bad-bg:#361b1b;
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 10px 30px rgba(0,0,0,.35);
}}

* {{ box-sizing:border-box; }}
body {{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:"Public Sans", ui-sans-serif, system-ui, sans-serif;
  font-size:15px; line-height:1.55;
  -webkit-font-smoothing:antialiased;
}}
.wrap {{ max-width:1020px; margin:0 auto; padding:32px 20px 72px; }}
.mono {{ font-family:"IBM Plex Mono", ui-monospace, monospace; }}
.num {{ font-variant-numeric:tabular-nums; text-align:right; }}

/* ---- masthead ---- */
.mast {{ display:flex; flex-wrap:wrap; gap:12px 24px; align-items:baseline;
        border-bottom:2px solid var(--ink); padding-bottom:14px; }}
.mast h1 {{
  font-family:"Saira Condensed", ui-sans-serif, sans-serif;
  font-weight:700; font-size:clamp(30px,5vw,44px); letter-spacing:.01em;
  margin:0; text-transform:uppercase; text-wrap:balance;
}}
.mast .sub {{ color:var(--ink-2); font-size:14px; margin-left:auto;
             font-variant-numeric:tabular-nums; }}
.eyebrow {{ font-family:"IBM Plex Mono", monospace; font-size:11px;
           letter-spacing:.16em; text-transform:uppercase; color:var(--ink-3); }}

/* ---- hero: one answer, board-style ---- */
.hero {{
  margin-top:20px; background:var(--panel); border:1px solid var(--rule);
  border-radius:6px; box-shadow:var(--shadow); overflow:hidden;
}}
.hero-top {{ display:flex; flex-wrap:wrap; align-items:center; gap:28px;
            padding:26px 28px; border-bottom:1px solid var(--rule-soft); }}
.price {{
  font-family:"IBM Plex Mono", monospace; font-weight:600;
  font-size:clamp(46px,8vw,72px); line-height:1; letter-spacing:-.02em;
  font-variant-numeric:tabular-nums; color:var(--accent);
}}
.flap {{ display:flex; gap:6px; }}
.flap span {{
  font-family:"IBM Plex Mono", monospace; font-weight:600; font-size:26px;
  background:var(--raise); border:1px solid var(--rule); border-radius:4px;
  padding:6px 10px; letter-spacing:.06em;
}}
.hero-note {{ padding:18px 28px; background:var(--raise); font-size:15px;
             color:var(--ink-2); }}
.hero-note strong {{ color:var(--ink); }}

/* ---- stats ---- */
.stats {{ display:grid; gap:12px; margin-top:20px;
         grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); }}
.stat {{ background:var(--panel); border:1px solid var(--rule);
        border-radius:6px; padding:14px 16px; }}
.stat b {{ display:block; font-family:"IBM Plex Mono", monospace;
          font-size:26px; font-weight:600; font-variant-numeric:tabular-nums; }}
.stat span {{ font-size:12.5px; color:var(--ink-2); }}

/* ---- sections ---- */
section {{ margin-top:38px; }}
section > h2 {{
  font-family:"Saira Condensed", sans-serif; text-transform:uppercase;
  font-size:19px; letter-spacing:.05em; margin:0 0 4px;
}}
section > p.lede {{ margin:0 0 16px; color:var(--ink-2); max-width:62ch; }}

/* ---- bars ---- */
.bars {{ background:var(--panel); border:1px solid var(--rule);
        border-radius:6px; padding:8px 16px; }}
.bar-row {{
  display:grid; grid-template-columns:58px 1fr 78px minmax(0,150px);
  align-items:center; gap:14px; padding:9px 0;
  border-bottom:1px solid var(--rule-soft);
}}
.bar-row:last-child {{ border-bottom:0; }}
.bars.wide .bar-row {{ grid-template-columns:118px 1fr 78px minmax(0,130px); }}
.bar-row:focus-visible {{ outline:2px solid var(--accent); outline-offset:3px;
                         border-radius:4px; }}
.bar-label {{ font-family:"IBM Plex Mono", monospace; font-size:13px;
             font-weight:500; white-space:nowrap; overflow:hidden;
             text-overflow:ellipsis; }}
.bar-track {{ background:var(--rule-soft); border-radius:4px; height:12px; }}
.bar-fill {{ display:block; height:100%; background:var(--bar);
            border-radius:0 4px 4px 0; min-width:3px; }}
.bar-row.is-best .bar-fill {{ background:var(--bar-best); }}
.bar-value {{ font-family:"IBM Plex Mono", monospace; font-weight:600;
             font-variant-numeric:tabular-nums; text-align:right; }}
.bar-note {{ font-size:12.5px; color:var(--ink-3); overflow:hidden;
            text-overflow:ellipsis; white-space:nowrap; }}
@media (max-width:640px) {{
  .bar-row, .bars.wide .bar-row {{ grid-template-columns:96px 1fr 72px; }}
  .bar-note {{ display:none; }}
}}

/* ---- board table ---- */
.scroll {{ overflow-x:auto; background:var(--panel);
          border:1px solid var(--rule); border-radius:6px; }}
table {{ border-collapse:collapse; width:100%; font-size:14px; }}
th {{
  font-family:"IBM Plex Mono", monospace; font-size:10.5px; font-weight:500;
  letter-spacing:.14em; text-transform:uppercase; color:var(--ink-3);
  text-align:left; padding:11px 14px; border-bottom:1px solid var(--rule);
  white-space:nowrap; background:var(--raise);
}}
th.num {{ text-align:right; }}
td {{ padding:9px 14px; border-bottom:1px solid var(--rule-soft);
     white-space:nowrap; }}
tr:last-child td {{ border-bottom:0; }}
tr.is-blocked td, tr.is-unparsed td, tr.is-empty td,
tr.is-error td {{ color:var(--ink-3); }}
.detail {{ color:var(--ink-2); font-size:13px; max-width:280px;
          overflow:hidden; text-overflow:ellipsis; }}
.chip {{
  display:inline-block; font-family:"IBM Plex Mono", monospace;
  font-size:10.5px; letter-spacing:.08em; text-transform:uppercase;
  padding:2px 8px; border-radius:999px; font-weight:500;
}}
.chip-ok {{ background:var(--ok-bg); color:var(--ok); }}
.chip-blocked {{ background:var(--warn-bg); color:var(--warn); }}
.chip-empty {{ background:var(--raise); color:var(--ink-3);
              border:1px solid var(--rule); }}
.chip-unparsed, .chip-error {{ background:var(--bad-bg); color:var(--bad); }}

footer {{ margin-top:40px; padding-top:18px; border-top:1px solid var(--rule);
         color:var(--ink-3); font-size:13px; }}
footer code {{ font-family:"IBM Plex Mono", monospace; font-size:12.5px;
              background:var(--raise); padding:1px 6px; border-radius:3px; }}
.empty {{ color:var(--ink-3); padding:12px 0; }}
</style>

<div class="wrap">
  <header class="mast">
    <h1>{origin} &rarr; {destination}</h1>
    <div class="sub">{date} &middot; {trip}<br><span class="eyebrow">read {generated}</span></div>
  </header>

  <div class="hero">
    <div class="hero-top">
      <div>
        <div class="eyebrow">cheapest found</div>
        <div class="price">{headline}</div>
      </div>
      <div>
        <div class="eyebrow">route &middot; source</div>
        <div class="flap"><span>{hero_route}</span></div>
        <div class="eyebrow" style="margin-top:8px">{hero_via}</div>
      </div>
    </div>
    <p class="hero-note">{verdict}</p>
  </div>

  <div class="stats">
    <div class="stat"><b>{searches}</b><span>searches run in parallel</span></div>
    <div class="stat"><b>{succeeded}</b><span>returned fares</span></div>
    <div class="stat"><b>{walltime}s</b><span>wall clock, start to finish</span></div>
    <div class="stat"><b>{speedup}&times;</b><span>faster than one at a time ({serial} min)</span></div>
  </div>

  <section>
    <h2>Which airport</h2>
    <p class="lede">Cheapest fare found at each airport in the destination metro
      area, across every site. Searching only the airport you first thought of
      is how people overpay.</p>
    {airports}
  </section>

  <section>
    <h2>Which site</h2>
    <p class="lede">Cheapest fare each site quoted for {asked} specifically, so
      the comparison is like for like. Same flight, same day, same currency.</p>
    {sites}
  </section>

  <section>
    <h2>Every search</h2>
    <p class="lede">One cloud browser per row, each on its own residential IP.
      Blocked rows hit an anti-bot wall and were retried once on a fresh
      address.</p>
    <div class="scroll">
      <table>
        <thead><tr>
          <th>Route</th><th>Site</th><th class="num">Cheapest</th>
          <th class="num">Fares</th><th>Best itinerary</th>
          <th class="num">Time</th><th>Status</th>
        </tr></thead>
        <tbody>{board}</tbody>
      </table>
    </div>
  </section>

  <footer>
    Fares are read from each site's own results page at the moment shown and
    move constantly &mdash; treat them as a direction to look, not a quote.
    Generated by <code>compare.py</code> on Solari cloud browsers.
  </footer>
</div>
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="src", default="results.json")
    ap.add_argument("--out", default="dashboard.html")
    ap.add_argument("--standalone", action="store_true",
                    help="wrap in <!doctype html> for opening straight off disk")
    args = ap.parse_args()

    data = json.loads((HERE / args.src).read_text(encoding="utf-8"))
    page = build(data)
    if args.standalone:
        page = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,'
                'initial-scale=1">' + page.replace("</style>", "</style></head>", 1)
                + "</body></html>")
    (HERE / args.out).write_text(page, encoding="utf-8")
    ok = sum(1 for r in data["results"] if r.get("ok"))
    print(f"{ok}/{len(data['results'])} searches -> {args.out}")


if __name__ == "__main__":
    main()
