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
.stage {
  --stage-1:#d7e7f8; --stage-2:#f0f6fc; --stage-edge:#c2d5ea;
  --stage-ink:#0b1730; --stage-ink-2:#3f5474; --stage-kicker:#1d4ed8;
  --stage-em:#2563eb; --stage-shadow:0 14px 36px rgba(20,40,70,.16);
  position:relative; overflow:hidden; border-radius:14px; margin-top:10px;
  background:var(--stage-1); border:1px solid var(--stage-edge);
  box-shadow:var(--stage-shadow);
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
.stage .copy { position:relative; z-index:1; padding:64px 44px 76px;
               max-width:34rem; }
.kicker { display:flex; align-items:center; gap:12px;
          font-family:"IBM Plex Mono", monospace; font-size:11px;
          letter-spacing:.2em; text-transform:uppercase;
          color:var(--stage-kicker); }
.kicker::before { content:""; width:34px; height:2px;
                  background:var(--stage-em); }
.hero-h { font-family:"Saira Condensed", ui-sans-serif, sans-serif;
          font-weight:700; text-transform:uppercase; letter-spacing:.01em;
          font-size:clamp(38px,6.4vw,66px); line-height:.96; margin:16px 0 0;
          text-wrap:balance; color:var(--stage-ink); }
.hero-h em { font-style:normal; color:var(--stage-em); }
.hero-p { font-size:16.5px; color:var(--stage-ink-2); max-width:44ch;
          margin:20px 0 0; }
@media (max-width:640px) { .stage .copy { padding:40px 24px 52px; } }
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

  const DOT = 7;
  const CX = MASK[0].length / 2, CY = MASK.length / 2;

  const NIGHT = {
    sky: ["#070b16", "#0b1428", "#101d3b"], stars: "#dbe9ff",
    halo: "91,155,255", core: "#f2f8ff", edge: "#bcd8ff", body: "#6f9fe8",
    smoke: "224,236,255", smokeMax: 0.34,
  };
  const DAY = {
    sky: ["#d7e7f8", "#e9f2fb", "#f6fafd"], stars: null,
    halo: "120,170,235", core: "#08152c", edge: "#17376b", body: "#5d84ba",
    smoke: "255,255,255", smokeMax: 0.95,
  };

  let W = 0, H = 0, pal = DAY, stars = [], puffs = [], t = 0, raf = null;
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

  function size() {
    const dpr = Math.min(devicePixelRatio || 1, 2);
    W = canvas.clientWidth; H = canvas.clientHeight;
    canvas.width = W * dpr; canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    stars = Array.from({length: Math.round(W * H / 5200)}, () => ({
      x: Math.random() * W, y: Math.random() * H,
      r: Math.random() < 0.15 ? 2 : 1, a: 0.15 + Math.random() * 0.5,
    }));
    puffs = Array.from({length: 240}, (_, i) => ({
      u: i / 240,
      off: (Math.random() - 0.5) * 30,
      rise: (Math.random() - 0.5) * 0.8,
      size: 5 + Math.random() * 15,
      a: 0.30 + Math.random() * 0.7,
    }));
  }

  function scene(u) {
    const bg = ctx.createLinearGradient(0, 0, W * 0.7, H);
    bg.addColorStop(0, pal.sky[0]);
    bg.addColorStop(0.55, pal.sky[1]);
    bg.addColorStop(1, pal.sky[2]);
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, W, H);

    const nose = path(u);
    const halo = ctx.createRadialGradient(nose.x, nose.y, 0,
                                          nose.x, nose.y, Math.max(W, H) * 0.45);
    halo.addColorStop(0, "rgba(" + pal.halo + ",.22)");
    halo.addColorStop(1, "rgba(" + pal.halo + ",0)");
    ctx.fillStyle = halo;
    ctx.fillRect(0, 0, W, H);

    if (pal.stars) {
      ctx.fillStyle = pal.stars;
      for (const s of stars) { ctx.globalAlpha = s.a; ctx.fillRect(s.x, s.y, s.r, s.r); }
    }

    // Smoke: soft, swelling, thickest just behind the aircraft and gone by the
    // bottom of the climb, so the eye is pulled forward along it.
    for (const puff of puffs) {
      if (puff.u > u) continue;
      const age = (u - puff.u) / Math.max(u, 0.001);
      const at = path(puff.u);
      const px = at.x + puff.off * (0.4 + age * 1.6);
      const py = at.y + puff.off * 0.4 + puff.rise * age * 90;
      const r = puff.size * (1 + age * 3.2);
      ctx.globalAlpha = puff.a * pal.smokeMax * Math.pow(1 - age, 1.5);
      const g = ctx.createRadialGradient(px, py, 0, px, py, r);
      g.addColorStop(0, "rgba(" + pal.smoke + ",1)");
      g.addColorStop(1, "rgba(" + pal.smoke + ",0)");
      ctx.fillStyle = g;
      ctx.fillRect(px - r, py - r, r * 2, r * 2);
    }
    ctx.globalAlpha = 1;

    // The aircraft, one dot per cell, rotated onto the tangent of the climb.
    const ahead = path(Math.min(u + 0.012, 1));
    const ang = Math.atan2(ahead.y - nose.y, ahead.x - nose.x);
    const cos = Math.cos(ang), sin = Math.sin(ang);
    for (const cell of CELLS) {
      const dx = (cell.c - CX) * DOT, dy = (cell.r - CY) * DOT;
      const x = nose.x + dx * cos - dy * sin;
      const y = nose.y + dx * sin + dy * cos;
      const twinkle = 0.62 + 0.38 * Math.sin(t / 15 + cell.phase);
      const d = cell.edge ? 3.4 : 2.4;
      ctx.globalAlpha = (cell.edge ? 0.95 : 0.5) * twinkle;
      ctx.fillStyle = cell.edge ? pal.edge : pal.body;
      ctx.fillRect(x - d / 2, y - d / 2, d, d);
      if (cell.edge && twinkle > 0.92) {
        ctx.globalAlpha = 0.9;
        ctx.fillStyle = pal.core;
        ctx.fillRect(x - 1, y - 1, 2, 2);
      }
    }
    ctx.globalAlpha = 1;
  }

  function frame() { t += 1; scene(Math.min((t / 780) % 1.15, 1)); raf = requestAnimationFrame(frame); }

  function start() {
    if (raf) { cancelAnimationFrame(raf); raf = null; }
    pal = isDark() ? NIGHT : DAY;
    size();
    if (still.matches) { scene(0.58); return; }   // one composed frame
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
