"""Turn teasers.json into a page about one question: is the advertised price real?

    python verify.py --from JFK --to LHR --date 2026-10-15
    python teaserboard.py          # -> teasers.html

Each row pairs what a site put on screen with what came back when the search
behind it was actually run. The bar between the two dots is the gap.
"""

import argparse
import html
import json

import theme
from common import HERE


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def dumbbells(checked: list[dict], names: dict) -> str:
    """One row per claim: advertised dot, delivered dot, gap between them.

    Two values per category is what a dumbbell is for. A bar chart here would
    force a choice of which number to plot, and the whole point is the pair.
    """
    tested = [c for c in checked if c.get("delivered") is not None]
    if not tested:
        return "<p class='empty'>Nothing could be verified.</p>"

    values = [v for c in tested for v in (c["advertised"], c["delivered"])]
    low, high = min(values), max(values)
    span = max(high - low, 1)
    pad = span * 0.08

    def pos(value: int) -> float:
        return (value - low + pad) / (span + 2 * pad) * 100

    rows = ["<div class='dumb'>"]
    for c in sorted(checked, key=lambda c: (c.get("delivered") is None,
                                            -(c.get("gap") or 0))):
        label = c.get("date") or c.get("destination") or ""
        verdict = c["verdict"]
        if c.get("delivered") is None:
            track = "<span class='dumb-track'></span>"
            price = (f"<span>${c['advertised']:,} advertised</span>")
        else:
            a, d = pos(c["advertised"]), pos(c["delivered"])
            left, width = min(a, d), abs(a - d)
            track = (
                f"<span class='dumb-track'>"
                f"<span class='dumb-seg' style='left:{left:.1f}%;"
                f"width:{width:.1f}%'></span>"
                f"<span class='dumb-dot dot-ad' style='left:{a:.1f}%'></span>"
                f"<span class='dumb-dot dot-got' style='left:{d:.1f}%'></span>"
                f"</span>")
            gap = c["gap"]
            price = (f"<b>${c['delivered']:,}</b> "
                     f"<span>({gap:+,})</span>" if gap
                     else f"<b>${c['delivered']:,}</b> <span>(exact)</span>")
        rows.append(
            f"<div class='dumb-row is-{verdict}'>"
            f"<span class='dumb-label'>{esc(label)}"
            f"<small>{esc(names.get(c['site'], c['site']))}</small></span>"
            f"{track}"
            f"<span class='dumb-price'>{price}</span>"
            f"<span class='chip-cell'>"
            f"<span class='chip chip-{verdict}'>{esc(verdict)}</span></span>"
            f"</div>")
    rows.append("</div>")
    return "\n".join(rows)


def build(data: dict) -> str:
    checked = data["checked"]
    names = data.get("site_names", {})
    tested = [c for c in checked if c.get("delivered") is not None]
    held = [c for c in tested if c["verdict"] == "holds"]
    over = [c for c in tested if c["verdict"] == "higher"]
    exact = [c for c in tested if c.get("gap") == 0]

    if tested:
        headline = f"{len(held)}/{len(tested)}"
        worst = max(over, key=lambda c: c["gap"]) if over else None
        if over:
            total = sum(c["gap"] for c in over)
            verdict = (
                f"<strong>{len(over)} of {len(tested)} advertised fares came "
                f"back higher</strong> when the search behind them was actually "
                f"run &mdash; ${total:,} more in total, worst ${worst['gap']:,} "
                f"on {esc(names.get(worst['site'], worst['site']))} "
                f"({esc(worst.get('date') or worst.get('destination'))}). "
                f"{len(exact)} came back to the dollar.")
        else:
            under = [c for c in tested if (c.get("gap") or 0) < 0]
            best = min(under, key=lambda c: c["gap"]) if under else None
            verdict = (
                f"<strong>All {len(tested)} advertised fares were still there</strong> "
                f"when the search behind them was run &mdash; "
                f"{len(exact)} to the dollar"
                + (f", and {len(under)} came back cheaper than advertised "
                   f"(best ${abs(best['gap']):,} under)." if under else "."))
    else:
        headline, verdict = "--", "No advertised price could be verified."

    rows = []
    for c in sorted(checked, key=lambda c: (c["site"],
                                            c.get("date") or c.get("destination") or "")):
        state = c["verdict"]
        delivered = (f"${c['delivered']:,}" if c.get("delivered") is not None
                     else "--")
        gap = f"{c['gap']:+,}" if c.get("gap") is not None else ""
        scope = "metro" if c.get("metro_wide") else "airport"
        rows.append(
            f"<tr class='is-{state}'>"
            f"<td>{esc(names.get(c['site'], c['site']))}</td>"
            f"<td class='detail'>{esc(c.get('source', ''))}</td>"
            f"<td class='mono num'>${c['advertised']:,}</td>"
            f"<td class='mono num'>{esc(delivered)}</td>"
            f"<td class='mono num'>{esc(gap)}</td>"
            f"<td class='mono'>{esc(c.get('tested_origin'))}&rarr;"
            f"{esc(c.get('destination') or data['destination'])}"
            f"{'' if c.get('kind') != 'date' else ' ' + esc(c.get('date'))}</td>"
            f"<td class='mono'>{esc(scope)}</td>"
            f"<td><span class='chip chip-{state}'>{esc(state)}</span></td>"
            f"</tr>")

    pages = data.get("pages", [])
    read_ok = [p for p in pages if p.get("ok")]

    return TEMPLATE.format(
        head=theme.head("Teaser Check"),
        origin=esc(data["origin"]), destination=esc(data["destination"]),
        date=esc(data["date"]),
        generated=esc(data.get("generated_at", "")),
        headline=esc(headline), verdict=verdict,
        claims=len(checked), tested=len(tested),
        pages_read=f"{len(read_ok)}/{len(pages)}",
        seconds=f"{data.get('seconds', 0):.0f}",
        chart=dumbbells(checked, names),
        rows="\n".join(rows),
    )


TEMPLATE = """{head}
<div class="wrap">
  <header class="mast">
    <h1>Is that price real?</h1>
    <div class="sub">{origin} &rarr; {destination} &middot; {date}<br>
      <span class="eyebrow">checked {generated}</span></div>
  </header>

  <div class="hero">
    <div class="hero-top">
      <div>
        <div class="eyebrow">advertised prices that held</div>
        <div class="price">{headline}</div>
      </div>
      <div>
        <div class="eyebrow">how</div>
        <div style="max-width:44ch;color:var(--ink-2);font-size:14px">
          Read what each site advertises for a search you have not run, then
          run every one of those searches at once and compare.
        </div>
      </div>
    </div>
    <p class="hero-note">{verdict}</p>
  </div>

  <div class="stats">
    <div class="stat"><b>{pages_read}</b><span>results pages read</span></div>
    <div class="stat"><b>{claims}</b><span>advertised prices found</span></div>
    <div class="stat"><b>{tested}</b><span>verified against a real search</span></div>
    <div class="stat"><b>{seconds}s</b><span>wall clock, both waves</span></div>
  </div>

  <section>
    <h2>Advertised against delivered</h2>
    <p class="lede">The grey dot is the price the site put on screen; the
      coloured dot is what the search behind it returned. The segment between
      them is the difference &mdash; and it runs in both directions, since a
      fare can come back cheaper than the teaser as easily as dearer.</p>
    <div class="legend">
      <span class="key"><i style="background:var(--ink-3)"></i>advertised</span>
      <span class="key"><i style="background:var(--ok)"></i>delivered, at or under</span>
      <span class="key"><i style="background:var(--warn)"></i>delivered, higher</span>
    </div>
    {chart}
  </section>

  <section>
    <h2>Every claim, and the search that tested it</h2>
    <p class="lede">A sidebar &ldquo;from&rdquo; price sits next to a list of
      every airport in the metro area, so it is a promise about all of New York
      rather than about JFK. Those rows are marked <code>metro</code> and were
      tested that way &mdash; the reading most favourable to the site.</p>
    <div class="scroll">
      <table>
        <thead><tr>
          <th>Site</th><th>What the page said</th>
          <th class="num">Advertised</th><th class="num">Delivered</th>
          <th class="num">Gap</th><th>Search run</th><th>Scope</th>
          <th>Verdict</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
  </section>

  <footer>
    A gap is not proof of bad faith. Teasers go stale, cheap seats sell between
    the two reads, and a &ldquo;from&rdquo; price may be a fare class the
    results page then filters out. What is worth knowing is simply how often
    the number on screen survives the click. Generated by <code>verify.py</code>
    on Solari cloud browsers.
  </footer>
</div>
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="src", default="teasers.json")
    ap.add_argument("--out", default="teasers.html")
    ap.add_argument("--standalone", action="store_true")
    args = ap.parse_args()

    data = json.loads((HERE / args.src).read_text(encoding="utf-8"))
    page = build(data)
    (HERE / args.out).write_text(
        theme.standalone(page) if args.standalone else page, encoding="utf-8")
    tested = [c for c in data["checked"] if c.get("delivered") is not None]
    held = [c for c in tested if c["verdict"] == "holds"]
    print(f"{len(held)}/{len(tested)} held -> {args.out}")


if __name__ == "__main__":
    main()
