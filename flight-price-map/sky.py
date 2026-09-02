"""The hero stage: an aircraft drawn as glowing pixel dots, trailing smoke.

Kept apart from `trip.py` because it is a self-contained piece of scenery with
its own palette, and because a page's copy and a page's atmosphere are easier
to edit when they are not in the same file.

The stage carries a full day palette and a full night one. Neither borrows the
other's ink: the CSS declares both, and the canvas reads the same choice the
CSS made, so the scene and the words over it always agree.
"""

CSS = """
/* ---------- landing stage ---------- */
/* The bleed has to be clipped on the page, not on the column: `overflow` on an
   ancestor of the full-bleed element clips the bleed itself back to that
   ancestor's box, which is exactly what it is escaping. */
body { overflow-x: clip; }
/* The shared theme gives every <section> a top margin; the two view
   sections are page regions rather than content blocks. */
#landing, #results { margin-top:0; }
/* Full-bleed: the hero is the page's opening, not a card sitting on it. The
   negative margin pulls it out of the centred column, and the inner div puts
   the copy back on that column's grid. */
.stage {
  /* A full screen, and dvh rather than vh so a phone's address bar sliding
     away does not leave the hero taller than the window. */
  min-height:100vh;
  min-height:100dvh;
  margin-top:-32px;                 /* cancel the column's top padding */
  display:flex; align-items:center;
  margin-left:calc(50% - 50vw); margin-right:calc(50% - 50vw);
  width:100vw; border-radius:0; border-left:0; border-right:0;
  padding:88px 0 96px;
  --stage-1:#d7e7f8; --stage-2:#f0f6fc; --stage-edge:#c2d5ea;
  --stage-ink:#0b1730; --stage-ink-2:#3f5474; --stage-kicker:#1d4ed8;
  --stage-em:#2563eb; --stage-shadow:0 14px 36px rgba(20,40,70,.16);
  /* No overflow:hidden -- the search form's calendar and suggestion lists
     hang out of the bottom of this and were being clipped by it. The canvas
     is inset:0 so it never escapes on its own.
     z-index because the sections after this one paint later: without it a
     panel is drawn behind them, and clicks meant for the panel land on the
     section instead, which reads as the calendar refusing to be clicked. */
  position:relative; z-index:2;
  background:var(--stage-1); border-top:0;
  border-bottom:1px solid var(--stage-edge);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .stage {
    --stage-1:#070b16; --stage-2:#101d3b; --stage-edge:#16203a;
    --stage-ink:#f4f7ff; --stage-ink-2:#a9b8d4; --stage-kicker:#8ab4ff;
    --stage-em:#5b9bff; --stage-shadow:0 20px 50px rgba(4,8,20,.45);
  }
}
:root[data-theme="dark"] .stage {
  --stage-1:#070b16; --stage-2:#101d3b; --stage-edge:#16203a;
  --stage-ink:#f4f7ff; --stage-ink-2:#a9b8d4; --stage-kicker:#8ab4ff;
  --stage-em:#5b9bff; --stage-shadow:0 20px 50px rgba(4,8,20,.45);
}
.stage canvas { position:absolute; inset:0; width:100%; height:100%;
                display:block; }
/* The form's popovers -- suggestion lists, the calendar -- live in here, so
   this has to outrank everything else the hero draws. It used to tie with the
   scroll cue at 1, and a tie is settled by document order, which put a
   decorative button on top of the controls people are trying to click. */
.stage .inner { position:relative; z-index:3; max-width:1020px; margin:0 auto;
                padding:0 20px; width:100%; }
.stage .copy { max-width:36rem; }
.scrollcue { position:absolute; left:50%; bottom:26px; transform:translateX(-50%);
             z-index:0; display:flex; flex-direction:column-reverse;
             align-items:center; gap:8px; color:var(--stage-ink-2);
             font-family:"IBM Plex Mono", monospace; font-size:10px;
             letter-spacing:.18em; text-transform:uppercase; background:none;
             border:0; cursor:pointer; padding:6px 10px; }
.scrollcue:hover { color:var(--stage-ink); }
/* And while a list or the calendar is open it gets out of the way entirely,
   so there is nothing behind the panel to read through it or reach for. */
.stage:has(.options:not([hidden])) .scrollcue,
.stage:has(.cal:not([hidden])) .scrollcue {
  opacity:0; pointer-events:none;
}
.scrollcue { transition:opacity .16s ease; }
@media (prefers-reduced-motion: reduce) { .scrollcue { transition:none; } }
.scrollcue:focus-visible { outline:2px solid var(--stage-em);
                           outline-offset:3px; border-radius:6px; }
.scrollcue i { width:1px; height:26px; background:currentColor; opacity:.5;
               animation:drop 2.4s ease-in-out infinite; }
@keyframes drop { 0%,100% { transform:scaleY(.35); transform-origin:top; }
                  50% { transform:scaleY(1); transform-origin:top; } }
@media (prefers-reduced-motion: reduce) { .scrollcue i { animation:none; } }
.kicker { display:flex; align-items:center; gap:12px;
          font-family:"IBM Plex Mono", monospace; font-size:11px;
          letter-spacing:.2em; text-transform:uppercase;
          color:var(--stage-kicker); }
.kicker::before { content:""; width:34px; height:2px;
                  background:var(--stage-em); }
.hero-h { font-family:"Saira Condensed", ui-sans-serif, sans-serif;
          font-weight:700; text-transform:uppercase; letter-spacing:.01em;
          font-size:clamp(44px,7.4vw,88px); line-height:.94; margin:18px 0 0;
          text-wrap:balance; color:var(--stage-ink); }
.hero-h em { font-style:normal; color:var(--stage-em); }
.hero-p { font-size:17.5px; color:var(--stage-ink-2); max-width:46ch;
          margin:22px 0 0; line-height:1.5; }
/* On a short screen the copy and the form together are taller than the window,
   which pushes the scroll cue below the fold -- the one element whose whole
   job is to be visible. Tighten rather than clip. */
@media (max-height:780px) and (min-width:641px) {
  .stage { padding:52px 0 74px; }
  .hero-h { font-size:clamp(36px,5.2vw,58px); margin-top:14px; }
  .hero-p { font-size:16px; margin-top:16px; }
  form.finder { margin-top:22px; }
}
@media (max-width:640px) {
  .stage { padding:64px 0 92px; }
  .hero-p { font-size:16px; }
}
"""

JS = """
(() => {
  const canvas = document.getElementById("sky");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  // The aircraft is a silhouette, not a picture: every filled cell becomes a
  // glowing dot, and cells on the outline burn brighter, which is what makes a
  // cloud of points read as a shape rather than a smudge.
  const MASK = [
    "....###...................",
    "....####..................",
    "....#####.................",
    "....######................",
    "..#########...............",
    ".######################...",
    "##########################",
    "##########################",
    ".######################...",
    "...##########.............",
    "....#######...............",
    ".....#####................",
  ];
  const lit = (r, c) => MASK[r] && MASK[r][c] === "#";
  const CELLS = [];
  for (let r = 0; r < MASK.length; r++) {
    for (let c = 0; c < MASK[r].length; c++) {
      if (!lit(r, c)) continue;
      CELLS.push({
        r, c,
        edge: !lit(r - 1, c) || !lit(r + 1, c) || !lit(r, c - 1) || !lit(r, c + 1),
        phase: Math.random() * Math.PI * 2,
      });
    }
  }

  // ---- the knobs ----------------------------------------------------
  const DOT = 7;            // spacing of the dots the aircraft is made of
  const CYCLE = 17000;      // ms for one climb, wall clock
  const TRAIL_FADE = 2.8;   // higher clears the smoke faster behind it
  const TRAIL_GROW = 2.6;   // how much a puff swells as it falls behind
  const TRAIL_LEN = 110;    // puffs per climb; fewer is a shorter trail
  const FAINT = 0.015;      // an alpha below this cannot be seen, so skip it
  // ---------------------------------------------------------------------

  const CX = MASK[0].length / 2, CY = MASK.length / 2;

  const NIGHT = {
    sky: ["#070b16", "#0b1428", "#101d3b"], stars: "#dbe9ff",
    core: "#f2f8ff", edge: "#bcd8ff", body: "#6f9fe8",
    smoke: "224,236,255", smokeMax: 0.34,
  };
  const DAY = {
    sky: ["#d7e7f8", "#e9f2fb", "#f6fafd"], stars: null,
    core: "#08152c", edge: "#17376b", body: "#5d84ba",
    smoke: "255,255,255", smokeMax: 0.95,
  };

  let W = 0, H = 0, dpr = 1, pal = DAY, puffs = [], t = 0, raf = null;
  let backdrop = null, puffSprite = null;
  const still = matchMedia("(prefers-reduced-motion: reduce)");
  const darkOS = matchMedia("(prefers-color-scheme: dark)");
  const isDark = () => {
    const stamped = document.documentElement.getAttribute("data-theme");
    return stamped ? stamped === "dark" : darkOS.matches;
  };

  // The climb enters bottom-centre and leaves through the top right, so it
  // never crosses the headline on the left.
  const path = u => {
    const ax = 0.30 * W, ay = H * 1.25;
    const bx = 0.80 * W, by = H * 0.80;
    const cx = 1.05 * W, cy = -0.20 * H;
    const k = 1 - u;
    return {x: k * k * ax + 2 * k * u * bx + u * u * cx,
            y: k * k * ay + 2 * k * u * by + u * u * cy};
  };

  const layer = (w, h) => {
    const c = document.createElement("canvas");
    c.width = Math.max(1, Math.round(w));
    c.height = Math.max(1, Math.round(h));
    return c;
  };

  // Everything that does not move is painted once. Rebuilding a full-canvas
  // gradient and a field of stars sixty times a second is most of the cost of
  // a scene where neither ever changes.
  function buildBackdrop() {
    backdrop = layer(W * dpr, H * dpr);
    const b = backdrop.getContext("2d");
    b.setTransform(dpr, 0, 0, dpr, 0, 0);
    const bg = b.createLinearGradient(0, 0, W * 0.7, H);
    bg.addColorStop(0, pal.sky[0]);
    bg.addColorStop(0.55, pal.sky[1]);
    bg.addColorStop(1, pal.sky[2]);
    b.fillStyle = bg;
    b.fillRect(0, 0, W, H);
    if (pal.stars) {
      b.fillStyle = pal.stars;
      for (let i = 0, n = Math.round(W * H / 5200); i < n; i++) {
        b.globalAlpha = 0.15 + Math.random() * 0.5;
        b.fillRect(Math.random() * W, Math.random() * H,
                   Math.random() < 0.15 ? 2 : 1, Math.random() < 0.15 ? 2 : 1);
      }
    }
  }

  // One soft blob, drawn once and stamped for every puff. A radial gradient per
  // puff per frame was the whole lag: the further the aircraft climbed the more
  // puffs were alive, so the page got heavier the higher it went.
  function buildSprites() {
    puffSprite = layer(64, 64);
    const s = puffSprite.getContext("2d");
    const g = s.createRadialGradient(32, 32, 0, 32, 32, 32);
    g.addColorStop(0, "rgba(" + pal.smoke + ",1)");
    g.addColorStop(1, "rgba(" + pal.smoke + ",0)");
    s.fillStyle = g;
    s.fillRect(0, 0, 64, 64);

  }

  function size() {
    // Scenery, so pixels are worth trading for smoothness. A full-height hero
    // on a large display is several times the area of a banner, and the cost
    // is per pixel: past a couple of megapixels, drop to 1:1.
    const area = canvas.clientWidth * canvas.clientHeight;
    dpr = Math.min(devicePixelRatio || 1, area > 1.7e6 ? 1 : 1.5);
    W = canvas.clientWidth; H = canvas.clientHeight;
    canvas.width = W * dpr; canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    puffs = Array.from({length: TRAIL_LEN}, (_, i) => ({
      u: i / TRAIL_LEN,
      off: (Math.random() - 0.5) * 30,
      rise: (Math.random() - 0.5) * 0.8,
      size: 5 + Math.random() * 15,
      a: 0.30 + Math.random() * 0.7,
    }));
    buildBackdrop();
    buildSprites();
  }

  const fade = u => Math.max(0, Math.min(1, u / 0.12, (1 - u) / 0.14));

  // Two climbs, half a cycle apart. One aircraft alone leaves the sky empty
  // for a second and a half between leaving the top and the next entering at
  // the bottom, which reads as a pause and a reset. Overlapping them means
  // something is always on the way up, and the wrap has nothing to give away.
  const PHASES = [0, 0.5];

  function flight(u) {
    const seam = fade(u);
    if (seam < 0.02) return;               // wholly invisible, so no work

    const nose = path(u);

    // Walk back from the newest puff and stop at the first invisible one.
    // They only fade with age, so everything beyond it is invisible too --
    // which is what keeps the cost flat however high the aircraft is.
    let last = 0;
    while (last < puffs.length && puffs[last].u <= u) last++;
    for (let i = last - 1; i >= 0; i--) {
      const puff = puffs[i];
      const age = (u - puff.u) / Math.max(u, 0.001);
      const alpha = puff.a * pal.smokeMax * Math.pow(1 - age, TRAIL_FADE) * seam;
      if (alpha < FAINT) break;
      const at = path(puff.u);
      const r = puff.size * (1 + age * TRAIL_GROW);
      ctx.globalAlpha = alpha;
      ctx.drawImage(puffSprite,
                    at.x + puff.off * (0.4 + age * 1.6) - r,
                    at.y + puff.off * 0.4 + puff.rise * age * 90 - r,
                    r * 2, r * 2);
    }

    // The aircraft, one dot per cell, rotated onto the tangent of the climb.
    const ahead = path(Math.min(u + 0.012, 1));
    const ang = Math.atan2(ahead.y - nose.y, ahead.x - nose.x);
    const cos = Math.cos(ang), sin = Math.sin(ang);
    for (const cell of CELLS) {
      const dx = (cell.c - CX) * DOT, dy = (cell.r - CY) * DOT;
      const x = nose.x + dx * cos - dy * sin;
      const y = nose.y + dx * sin + dy * cos;
      const twinkle = 0.62 + 0.38 * Math.sin(t / 260 + cell.phase);
      const d = cell.edge ? 3.4 : 2.4;
      ctx.globalAlpha = (cell.edge ? 0.95 : 0.5) * twinkle * seam;
      ctx.fillStyle = cell.edge ? pal.edge : pal.body;
      ctx.fillRect(x - d / 2, y - d / 2, d, d);
      if (cell.edge && twinkle > 0.92) {
        ctx.globalAlpha = 0.9 * seam;
        ctx.fillStyle = pal.core;
        ctx.fillRect(x - 1, y - 1, 2, 2);
      }
    }
  }

  function scene(u) {
    ctx.globalAlpha = 1;
    ctx.drawImage(backdrop, 0, 0, W, H);
    for (const phase of PHASES) flight((u + phase) % 1);
    ctx.globalAlpha = 1;
  }

  let slow = 0, lastAt = 0, startAt = 0;

  function frame(now) {
    const gap = lastAt ? now - lastAt : 16;
    lastAt = now;
    // Two seconds of missed frames means this device is not enjoying it.
    // A still sky is better than a page that stutters while you use it.
    slow = gap > 34 ? slow + 1 : 0;
    if (slow > 120) { cancelAnimationFrame(raf); raf = null; scene(0.58); return; }

    if (!startAt) startAt = now;
    t = now - startAt;
    scene(((now - startAt) / CYCLE) % 1);
    raf = requestAnimationFrame(frame);
  }

  function start() {
    if (raf) { cancelAnimationFrame(raf); raf = null; }
    pal = isDark() ? NIGHT : DAY;
    size();
    if (still.matches) { scene(0.58); return; }   // one composed frame
    slow = 0; lastAt = 0; startAt = 0;
    raf = requestAnimationFrame(frame);
  }

  addEventListener("resize", start);
  still.addEventListener("change", start);
  darkOS.addEventListener("change", start);
  new MutationObserver(start).observe(document.documentElement,
    {attributes: true, attributeFilter: ["data-theme"]});
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && raf) { cancelAnimationFrame(raf); raf = null; }
    else if (!document.hidden) start();
  });
  start();
})();
"""
