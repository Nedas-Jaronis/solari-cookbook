/* The hero sky as one fullscreen fragment shader.
 *
 * The canvas version draws the contrail as 110 sprites, which is why it reads
 * as a row of blurry stamps rather than as air being disturbed. On the GPU
 * every pixel can ask the curve directly how far behind the aircraft it sits
 * and how long ago it was passed, so the trail is a field: it billows, it
 * spreads with age, and it costs the same whether the aircraft has just taken
 * off or is leaving the top of the frame.
 *
 * The aircraft keeps its identity. It is still a silhouette punched into a
 * grid of dots -- that is the departure-board idiom the rest of the page is
 * built on -- but the silhouette is an SDF now, so it stays sharp at any size
 * and the dots can glow rather than just being drawn brighter.
 */
export const SHADER = /* wgsl */ `
struct Params {
  time: f32,
  aspect: f32,
  night: f32,
  dpr: f32,
  skyTop: vec3f,
  skyMid: vec3f,
  skyBot: vec3f,
  smoke: vec3f,
  core: vec3f,
  edge: vec3f,
  body: vec3f,
}
@group(0) @binding(0) var<uniform> params: Params;

const CYCLE: f32 = 17.0;      // seconds for one climb, matching the canvas
const TRAIL: f32 = 0.62;      // how far back along the curve the trail reaches
const TAILGAP: f32 = 0.026;   // the trail leaves the tail, not the fuselage
const DOT: f32 = 0.0092;      // dot pitch, in aspect-corrected uv

fn hash21(p: vec2f) -> f32 {
  var q = fract(p * vec2f(123.34, 345.45));
  q += dot(q, q + 34.345);
  return fract(q.x * q.y);
}

fn vnoise(p: vec2f) -> f32 {
  let i = floor(p);
  let f = fract(p);
  let u = f * f * (3.0 - 2.0 * f);
  let a = hash21(i);
  let b = hash21(i + vec2f(1.0, 0.0));
  let c = hash21(i + vec2f(0.0, 1.0));
  let d = hash21(i + vec2f(1.0, 1.0));
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

fn fbm(p: vec2f) -> f32 {
  var v = 0.0;
  var amp = 0.5;
  var q = p;
  for (var i = 0; i < 4; i++) {
    v += amp * vnoise(q);
    q = q * 2.02 + vec2f(11.3, 7.7);
    amp *= 0.5;
  }
  return v;
}

/* The same climb the canvas flies: in at the bottom centre, out through the
   top right, so it never crosses the headline on the left. */
fn path(u: f32) -> vec2f {
  let a = vec2f(0.30, 1.25);
  let b = vec2f(0.80, 0.80);
  let c = vec2f(1.05, -0.20);
  let k = 1.0 - u;
  return k * k * a + 2.0 * k * u * b + u * u * c;
}

fn heading(u: f32) -> vec2f {
  let ahead = path(min(u + 0.012, 1.0));
  return normalize(ahead - path(u));
}

/* Fade in at the bottom, out at the top, so neither end of the climb pops. */
fn seam(u: f32) -> f32 {
  return clamp(min(u / 0.12, (1.0 - u) / 0.14), 0.0, 1.0);
}

/* Distance from p to the aircraft silhouette, in local aircraft space:
   a fuselage, a swept wing, and a tailplane. Negative inside. */
fn ellipse(p: vec2f, r: vec2f) -> f32 {
  let k = length(p / r);
  return (k - 1.0) * min(r.x, r.y);
}

fn plane_sdf(q: vec2f) -> f32 {
  let fuse = ellipse(q, vec2f(0.064, 0.0104));
  // Wings sweep back, so they are an ellipse pushed behind the mid-point and
  // sheared -- cheaper than a polygon and it reads the same at this size.
  let w = vec2f(q.x + abs(q.y) * 0.85 + 0.014, q.y);
  let wing = ellipse(w, vec2f(0.022, 0.047));
  let t = vec2f(q.x + abs(q.y) * 0.9 + 0.052, q.y);
  let tail = ellipse(t, vec2f(0.011, 0.022));
  return min(fuse, min(wing, tail));
}

/* How much trail sits at p, for the aircraft currently at u. Walking the curve
   backwards is what a sprite trail cannot do: each sample knows its own age,
   so the plume widens and thins behind the aircraft instead of being a row of
   equally-sized stamps. */
fn trail_at(p: vec2f, u: f32) -> f32 {
  var acc = 0.0;
  let steps = 40;
  for (var i = 0; i < steps; i++) {
    let t = f32(i) / f32(steps - 1);
    // Started clear of the aircraft: sampling from u puts the freshest smoke
    // under the wings, which reads as the thing smoking rather than flying.
    let back = TAILGAP + t * TRAIL;
    let s = u - back;
    if (s < 0.0) { break; }
    let age = clamp(back / TRAIL, 0.0, 1.0);
    var c = path(s);
    c.x *= params.aspect;
    // Billow: the older the air, the further the noise is allowed to push it.
    let n = fbm(c * 9.0 + vec2f(params.time * 0.05, -params.time * 0.08));
    let drift = (n - 0.5) * (0.006 + age * 0.055);
    let d = length(p - c - vec2f(drift * 0.6, drift));
    let width = 0.0055 + age * 0.085;
    let fall = pow(1.0 - age, 2.4);
    acc += fall * exp(-(d * d) / (width * width)) * 0.23;
  }
  return acc;
}

fn aircraft_at(p: vec2f, u: f32) -> vec2f {
  var c = path(u);
  c.x *= params.aspect;
  let h = normalize(vec2f(heading(u).x * params.aspect, heading(u).y));
  let rel = p - c;
  // Into aircraft space: x along the heading, y across it.
  let q = vec2f(dot(rel, h), dot(rel, vec2f(-h.y, h.x)));
  let d = plane_sdf(q);

  // The silhouette, punched into a grid of dots so it still reads as a board.
  let cell = fract(p / DOT) - 0.5;
  let dot_mask = 1.0 - smoothstep(0.16, 0.40, length(cell));
  let solid = 1.0 - smoothstep(0.0, 0.0022, d);
  let rim = 1.0 - smoothstep(0.0, 0.0055, abs(d + 0.0016));
  // A dot that lands on the outline burns brighter, and every dot breathes.
  let twinkle = 0.66 + 0.34 * sin(params.time * 3.4 + hash21(floor(p / DOT)) * 28.0);

  let lit = solid * dot_mask * twinkle;
  let glow = exp(-max(d, 0.0) * 210.0) * 0.5;
  return vec2f(lit, rim * dot_mask * twinkle + glow * 0.35);
}

@fragment fn fs_main(@location(0) uv: vec2f) -> @location(0) vec4f {
  let p = vec2f(uv.x * params.aspect, uv.y);

  // Sky: the page's own three stops, on the same diagonal the CSS uses.
  let g = clamp(uv.x * 0.35 + uv.y * 0.8, 0.0, 1.0);
  var col = mix(mix(params.skyTop, params.skyMid, smoothstep(0.0, 0.55, g)),
                params.skyBot, smoothstep(0.55, 1.0, g));

  // Stars, at night only, and never so dense they read as noise.
  if (params.night > 0.5) {
    let cell = floor(p * 130.0);
    let r = hash21(cell);
    if (r > 0.9955) {
      let f = fract(p * 130.0) - 0.5;
      let tw = 0.45 + 0.55 * sin(params.time * 1.7 + r * 40.0);
      col += vec3f(0.86, 0.92, 1.0) *
             (1.0 - smoothstep(0.0, 0.36, length(f))) * tw * 0.85;
    }
  }

  let base = params.time / CYCLE;
  var smoke = 0.0;
  var lit = 0.0;
  var rim = 0.0;
  // Two climbs, half a cycle apart, so the sky is never empty between them.
  for (var k = 0; k < 2; k++) {
    let u = fract(base + f32(k) * 0.5);
    let s = seam(u);
    if (s < 0.02) { continue; }
    smoke += trail_at(p, u) * s;
    let a = aircraft_at(p, u);
    lit = max(lit, a.x * s);
    rim = max(rim, a.y * s);
  }

  let smokeMax = select(0.95, 0.40, params.night > 0.5);
  col = mix(col, params.smoke, clamp(smoke, 0.0, 1.0) * smokeMax);
  col = mix(col, params.body, clamp(lit, 0.0, 1.0));
  col = mix(col, params.edge, clamp(rim, 0.0, 1.0) * 0.9);
  col += params.core * clamp(lit, 0.0, 1.0) * 0.28;

  return vec4f(col, 1.0);
}
`;
