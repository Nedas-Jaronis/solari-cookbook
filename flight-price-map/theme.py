"""The look, shared by every generated page.

Solari made the split-flap boards that hung in airport concourses, so the
pages read as departure boards: condensed signage type for headings, a
monospace face for anything numeric, warm amber against a cool slate ground.

Colours are defined once as tokens on `:root` and redefined for dark under
both the OS media query and an explicit `data-theme` stamp, so the page holds
up in all three viewer states (light, dark, and no preference at all).
"""

FONTS = ("https://fonts.googleapis.com/css2?"
         "family=Saira+Condensed:wght@500;600;700&"
         "family=Public+Sans:ital,wght@0,400;0,500;0,600;1,400&"
         "family=IBM+Plex+Mono:wght@400;500;600&display=swap")

DARK = """
  color-scheme: dark;
  --ground:#0f1216; --panel:#171c22; --raise:#1d232a;
  --ink:#f1ede4; --ink-2:#a7b1bc; --ink-3:#7c8794;
  --rule:#29313a; --rule-soft:#212831;
  --accent:#f0a63c;
  --bar:#d98f2c; --bar-best:#f6d9a8;
  --ok:#5fcf95; --ok-bg:#12301f;
  --warn:#e0a44a; --warn-bg:#33260f;
  --bad:#f08a8a; --bad-bg:#361b1b;
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 10px 30px rgba(0,0,0,.35);
"""

CSS = """
:root {
  color-scheme: light;
  --ground:#e9ecf0; --panel:#ffffff; --raise:#f6f7f9;
  --ink:#0e141b; --ink-2:#4d5966; --ink-3:#7b8794;
  --rule:#d3d9e0; --rule-soft:#e4e8ed;
  --accent:#b45c07;
  --bar:#c2670a; --bar-best:#0e141b;
  --ok:#0f7a4d; --ok-bg:#dff0e6;
  --warn:#9a5b00; --warn-bg:#f7e6cb;
  --bad:#a63232; --bad-bg:#f6dede;
  --shadow:0 1px 2px rgba(14,20,27,.06), 0 8px 24px rgba(14,20,27,.05);
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {__DARK__} }
:root[data-theme="dark"] {__DARK__}

* { box-sizing:border-box; }
body {
  margin:0; background:var(--ground); color:var(--ink);
  font-family:"Public Sans", ui-sans-serif, system-ui, sans-serif;
  font-size:15px; line-height:1.55; -webkit-font-smoothing:antialiased;
}
.wrap { max-width:1020px; margin:0 auto; padding:32px 20px 72px; }
.mono { font-family:"IBM Plex Mono", ui-monospace, monospace; }
.num { font-variant-numeric:tabular-nums; text-align:right; }

.mast { display:flex; flex-wrap:wrap; gap:12px 24px; align-items:baseline;
        border-bottom:2px solid var(--ink); padding-bottom:14px; }
.mast h1 {
  font-family:"Saira Condensed", ui-sans-serif, sans-serif;
  font-weight:700; font-size:clamp(30px,5vw,44px); letter-spacing:.01em;
  margin:0; text-transform:uppercase; text-wrap:balance;
}
.mast .sub { color:var(--ink-2); font-size:14px; margin-left:auto;
             font-variant-numeric:tabular-nums; }
.eyebrow { font-family:"IBM Plex Mono", monospace; font-size:11px;
           letter-spacing:.16em; text-transform:uppercase; color:var(--ink-3); }

.hero { margin-top:20px; background:var(--panel); border:1px solid var(--rule);
        border-radius:6px; box-shadow:var(--shadow); overflow:hidden; }
.hero-top { display:flex; flex-wrap:wrap; align-items:center; gap:28px;
            padding:26px 28px; border-bottom:1px solid var(--rule-soft); }
.price {
  font-family:"IBM Plex Mono", monospace; font-weight:600;
  font-size:clamp(46px,8vw,72px); line-height:1; letter-spacing:-.02em;
  font-variant-numeric:tabular-nums; color:var(--accent);
}
.flap { display:flex; gap:6px; }
.flap span {
  font-family:"IBM Plex Mono", monospace; font-weight:600; font-size:26px;
  background:var(--raise); border:1px solid var(--rule); border-radius:4px;
  padding:6px 10px; letter-spacing:.06em;
}
.hero-note { padding:18px 28px; background:var(--raise); font-size:15px;
             color:var(--ink-2); margin:0; }
.hero-note strong { color:var(--ink); }

.stats { display:grid; gap:12px; margin-top:20px;
         grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); }
.stat { background:var(--panel); border:1px solid var(--rule);
        border-radius:6px; padding:14px 16px; }
.stat b { display:block; font-family:"IBM Plex Mono", monospace;
          font-size:26px; font-weight:600; font-variant-numeric:tabular-nums; }
.stat span { font-size:12.5px; color:var(--ink-2); }

section { margin-top:38px; }
section > h2 {
  font-family:"Saira Condensed", sans-serif; text-transform:uppercase;
  font-size:19px; letter-spacing:.05em; margin:0 0 4px;
}
section > p.lede { margin:0 0 16px; color:var(--ink-2); max-width:62ch; }

.bars { background:var(--panel); border:1px solid var(--rule);
        border-radius:6px; padding:8px 16px; }
.bar-row {
  display:grid; grid-template-columns:58px 1fr 78px minmax(0,150px);
  align-items:center; gap:14px; padding:9px 0;
  border-bottom:1px solid var(--rule-soft);
}
.bar-row:last-child { border-bottom:0; }
.bars.wide .bar-row { grid-template-columns:118px 1fr 78px minmax(0,130px); }
.bar-label { font-family:"IBM Plex Mono", monospace; font-size:13px;
             font-weight:500; white-space:nowrap; overflow:hidden;
             text-overflow:ellipsis; }
.bar-track { background:var(--rule-soft); border-radius:4px; height:12px; }
.bar-fill { display:block; height:100%; background:var(--bar);
            border-radius:0 4px 4px 0; min-width:3px; }
.bar-row.is-best .bar-fill { background:var(--bar-best); }
.bar-value { font-family:"IBM Plex Mono", monospace; font-weight:600;
             font-variant-numeric:tabular-nums; text-align:right; }
.bar-note { font-size:12.5px; color:var(--ink-3); overflow:hidden;
            text-overflow:ellipsis; white-space:nowrap; }
@media (max-width:640px) {
  .bar-row, .bars.wide .bar-row { grid-template-columns:96px 1fr 72px; }
  .bar-note { display:none; }
}

/* Advertised vs delivered: two values per claim, so a dumbbell rather than a
   bar. The connecting segment is the gap, which is the thing worth seeing. */
.dumb { background:var(--panel); border:1px solid var(--rule);
        border-radius:6px; padding:10px 18px; }
.dumb-row {
  display:grid; grid-template-columns:104px 1fr 92px 78px;
  align-items:center; gap:14px; padding:10px 0;
  border-bottom:1px solid var(--rule-soft);
}
.dumb-row:last-child { border-bottom:0; }
.dumb-label { font-family:"IBM Plex Mono", monospace; font-size:12.5px;
              white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.dumb-label small { display:block; color:var(--ink-3); font-size:10.5px;
                    letter-spacing:.08em; text-transform:uppercase; }
.dumb-track { position:relative; height:18px; }
.dumb-track::before {
  content:""; position:absolute; left:0; right:0; top:8px; height:2px;
  background:var(--rule-soft);
}
.dumb-seg { position:absolute; top:8px; height:2px; background:var(--warn); }
.dumb-dot { position:absolute; top:4px; width:10px; height:10px;
            border-radius:50%; margin-left:-5px;
            box-shadow:0 0 0 2px var(--panel); }
.dot-ad { background:var(--ink-3); }
.dot-got { background:var(--warn); }
.dumb-row.is-holds .dumb-seg, .dumb-row.is-holds .dot-got { background:var(--ok); }
.dumb-row.is-unverified .dot-got { display:none; }
.dumb-price { font-family:"IBM Plex Mono", monospace; font-size:13px;
              font-variant-numeric:tabular-nums; text-align:right;
              white-space:nowrap; }
.dumb-price b { font-weight:600; }
.dumb-price span { color:var(--ink-3); }
.legend { display:flex; gap:18px; align-items:center; margin:0 0 12px;
          font-size:12.5px; color:var(--ink-2); flex-wrap:wrap; }
.key { display:inline-flex; align-items:center; gap:7px; }
.key i { width:10px; height:10px; border-radius:50%; display:inline-block; }
@media (max-width:640px) {
  .dumb-row { grid-template-columns:88px 1fr 84px; }
  .dumb-row > .chip-cell { display:none; }
}

.scroll { overflow-x:auto; background:var(--panel);
          border:1px solid var(--rule); border-radius:6px; }
table { border-collapse:collapse; width:100%; font-size:14px; }
th {
  font-family:"IBM Plex Mono", monospace; font-size:10.5px; font-weight:500;
  letter-spacing:.14em; text-transform:uppercase; color:var(--ink-3);
  text-align:left; padding:11px 14px; border-bottom:1px solid var(--rule);
  white-space:nowrap; background:var(--raise);
}
th.num { text-align:right; }
td { padding:9px 14px; border-bottom:1px solid var(--rule-soft);
     white-space:nowrap; }
tr:last-child td { border-bottom:0; }
tr.is-blocked td, tr.is-unparsed td, tr.is-empty td, tr.is-error td,
tr.is-unverified td { color:var(--ink-3); }
.detail { color:var(--ink-2); font-size:13px; max-width:280px;
          overflow:hidden; text-overflow:ellipsis; }
.chip {
  display:inline-block; font-family:"IBM Plex Mono", monospace;
  font-size:10.5px; letter-spacing:.08em; text-transform:uppercase;
  padding:2px 8px; border-radius:999px; font-weight:500;
}
.chip-ok, .chip-holds { background:var(--ok-bg); color:var(--ok); }
.chip-blocked, .chip-higher { background:var(--warn-bg); color:var(--warn); }
.chip-empty, .chip-unverified { background:var(--raise); color:var(--ink-3);
                                border:1px solid var(--rule); }
.chip-unparsed, .chip-error { background:var(--bad-bg); color:var(--bad); }

footer { margin-top:40px; padding-top:18px; border-top:1px solid var(--rule);
         color:var(--ink-3); font-size:13px; }
footer code { font-family:"IBM Plex Mono", monospace; font-size:12.5px;
              background:var(--raise); padding:1px 6px; border-radius:3px; }
.empty { color:var(--ink-3); padding:12px 0; }
""".replace("__DARK__", DARK)


def head(title: str) -> str:
    """The opening of every page: name it, load the faces, paint the tokens."""
    return f"<title>{title}</title>\n" \
           f'<link rel="stylesheet" href="{FONTS}">\n' \
           f"<style>{CSS}</style>\n"


def standalone(page: str) -> str:
    """Wrap for opening straight off disk; the Artifact host supplies its own."""
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            + page.replace("</style>", "</style></head><body>", 1)
            + "</body></html>")
