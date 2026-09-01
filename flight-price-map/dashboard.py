"""Turn results.json into a departure board you can read at a glance.

    python compare.py --from JFK --to LHR --date 2026-10-15 --nearby to
    python dashboard.py            # -> dashboard.html

The page answers one question first -- what is the cheapest way to make this
trip, and what does the obvious choice cost you -- and only then shows the
evidence behind it.
"""

import argparse
import html
import json
from collections import defaultdict

import theme
from common import HERE


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
        out.append(
            f"<div class='bar-row{' is-best' if value == low else ''}'>"
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
    baseline = (min(baseline_rows, key=lambda r: r["cheapest"])
                if baseline_rows else None)
    saving = (baseline["cheapest"] - best["cheapest"]) if best and baseline else 0

    # Cheapest per destination airport, across every site.
    by_airport = defaultdict(list)
    for r in good:
        by_airport[r["destination"]].append(r)
    airport_items = sorted(
        ((code, min(rows, key=lambda r: r["cheapest"])["cheapest"],
          "cheapest on "
          + names.get(min(rows, key=lambda r: r["cheapest"])["site"], ""))
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
            f"<td><span class='chip chip-{state}'>"
            f"{esc(labels.get(state, state))}</span></td>"
            f"</tr>")

    walltime = data.get("seconds", 0)
    serial = sum(r["seconds"] for r in results)

    if saving > 0 and baseline:
        verdict = (f"<strong>${saving:,} under</strong> the best "
                   f"{esc(asked)} fare anyone quoted (${baseline['cheapest']:,}), "
                   f"for an airport in the same metro area.")
    elif baseline:
        verdict = ("The airport you asked for is also the cheapest. Every "
                   "alternative in the metro area came back dearer.")
    else:
        verdict = "No fare was read for the route as asked."

    return TEMPLATE.format(
        head=theme.head("Fare Board"),
        origin=esc(data["origin"]), destination=esc(data["destination"]),
        date=esc(data["date"]),
        trip=esc("one way" if not data.get("ret")
                 else f"returning {data['ret']}"),
        generated=esc(data.get("generated_at", "")),
        headline=esc(f"${best['cheapest']:,}" if best else "no result"),
        hero_route=esc(best["route"]) if best else "--",
        hero_via=esc(names.get(best["site"], "")) if best else "",
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


TEMPLATE = """{head}
<div class="wrap">
  <header class="mast">
    <h1>{origin} &rarr; {destination}</h1>
    <div class="sub">{date} &middot; {trip}<br>
      <span class="eyebrow">read {generated}</span></div>
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
    <div class="stat"><b>{speedup}&times;</b>
      <span>faster than one at a time ({serial} min)</span></div>
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
      address; they stay listed rather than being quietly dropped.</p>
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
    (HERE / args.out).write_text(
        theme.standalone(page) if args.standalone else page, encoding="utf-8")
    ok = sum(1 for r in data["results"] if r.get("ok"))
    print(f"{ok}/{len(data['results'])} searches -> {args.out}")


if __name__ == "__main__":
    main()
