/* The hero sky as one fullscreen fragment shader.
 *
 * The canvas version draws the contrail as 110 sprites, which is why it reads
 * as a row of blurry stamps rather than as air being disturbed. On the GPU
 * every pixel can ask the curve directly how far behind the aircraft it sits
 * and how long ago it was passed, so the trail is a field: it billows, it
 * spreads with age, and it costs the same whether the aircraft has just taken
 * off or is leaving the top of the frame.
 *
 * The aircraft is an actual aircraft. The canvas draws a twelve-row bitmap
 * silhouette stamped into a grid of dots, which is all a 2D context can afford
 * at this size; here it is built from signed distance fields -- a tapered
 * fuselage, swept and tapered wings, podded engines, tailplane and fin -- so it
 * has a cabin window line, lit surfaces, a bright fan face in each intake and
 * red and green lights on the tips. Distance fields have no resolution, so it
 * is exactly as sharp on a phone as on a 4K display.
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
  for (var i = 0; i < 3; i++) {
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

/* One slow aileron roll, begun once the aircraft is clear of the search form
   and finished before it leaves the frame. Eased at both ends, because a roll
   that starts at full rate looks like a dropped frame rather than a manoeuvre.
   0.60 to 0.80 of the climb puts it in the upper third of the hero, above the
   copy and above the form. */
const ROLL_A: f32 = 0.58;
const ROLL_B: f32 = 0.84;

fn roll_phase(u: f32) -> f32 {
  return clamp((u - ROLL_A) / (ROLL_B - ROLL_A), 0.0, 1.0);
}

fn roll_of(u: f32) -> f32 {
  let t = roll_phase(u);
  /* Eased in, flown at a constant rate, eased out. This is the integral of a
     trapezoidal rate, written out in full because getting it wrong is silent:
     an expression that merely looks right here overshoots the full turn and
     leaves the aircraft sitting at an angle it never rolled to. At t = 1 this
     is exactly 1 - e, which is why it is divided by 1 - e. */
  let e = 0.14;
  var f = t - e * 0.5;                       // the constant-rate middle
  if (t < e) { f = t * t / (2.0 * e); }      // easing in
  if (t > 1.0 - e) { f = (1.0 - e) - (1.0 - t) * (1.0 - t) / (2.0 * e); }
  return (f / (1.0 - e)) * 6.2831853;
}


/* The roll is flown on the line. Pushing the aircraft round a helix as well
   was a barrel roll on paper and looked staged on screen: at this size the
   displacement reads as the aeroplane being shoved sideways rather than as a
   manoeuvre. What sells a roll is the airframe turning over cleanly, so that
   is all it does. */

/* Fade in at the bottom, out at the top, so neither end of the climb pops. */
fn seam(u: f32) -> f32 {
  return clamp(min(u / 0.12, (1.0 - u) / 0.14), 0.0, 1.0);
}

/* ---- the aircraft ------------------------------------------------------
   A plan view of an airliner, built from signed distance fields so it stays
   sharp at any size and every part can be shaded and coloured separately:
   fuselage, swept wings, engines, tailplane and fin. Local space has the nose
   at +x and the span along y, both in aspect-corrected uv. */

struct Plane {
  d: f32,          // distance to the silhouette, negative inside
  mat: f32,        // 0 fuselage, 1 wing, 2 engine, 3 tail surfaces
  round: f32,      // 1 on the spine of a rounded body, 0 at its edge
  lie: f32,        // +1 this face is the aircraft's back, -1 its belly
}

fn seg(p: vec2f, a: vec2f, b: vec2f) -> f32 {
  let pa = p - a;
  let ba = b - a;
  let h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
  return length(pa - ba * h);
}

/* A lifting surface: swept, and tapered from root to tip. The taper is what
   was missing when this first read as a plank -- an airliner loses most of its
   chord by the time it reaches the tip, and a constant-chord panel looks like
   a door no matter how far you sweep it. */
fn panel(q: vec2f, xRoot: f32, chordRoot: f32, chordTip: f32,
         sweep: f32, span: f32) -> f32 {
  let a = abs(q.y);
  let t = clamp(a / span, 0.0, 1.0);
  let chord = mix(chordRoot, chordTip, t * t * 0.55 + t * 0.45);
  let le = xRoot + chordRoot * 0.5 - sweep * a;
  let mid = le - chord * 0.5;
  let dx = abs(q.x - mid) - chord * 0.5;
  let dy = a - span;
  return min(max(dx, dy), 0.0) + length(max(vec2f(dx, dy), vec2f(0.0)));
}

fn body_radius(h: f32) -> f32 {
  // Cone at the tail, parallel through the cabin, tapering to the nose.
  return 0.0122 * smoothstep(0.0, 0.18, h) * (1.0 - 0.60 * smoothstep(0.76, 1.0, h));
}

/* cs is the cosine of the roll: how much of the span still faces us, signed,
   so it goes negative once the aircraft is past knife-edge and showing its
   belly. The lifting surfaces are flat, so they foreshorten by it; the
   fuselage and the nacelles are tubes and look the same however far round they
   are, which is why they keep the unsquashed coordinate. */
/* How much trail sits at p, for the aircraft currently at u. Walking the curve
   backwards is what a sprite trail cannot do: each sample knows its own age,
   so the plume widens and thins behind the aircraft instead of being a row of
   equally-sized stamps. */
fn trail_at(p: vec2f, u: f32) -> f32 {
  var acc = 0.0;
  let steps = 52;
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
    let width = 0.0078 + age * 0.082;
    let fall = pow(1.0 - age, 2.4);
    acc += fall * exp(-(d * d) / (width * width)) * 0.23;
  }
  return acc;
}

/* The aircraft as a solid object being turned over.
 *
 * Every part of it lives somewhere in the airframe's own frame -- x along the
 * fuselage, y across the span, z up -- and rolling by phi turns that frame
 * about x. Seen from above, a point at (y, z) lands at
 *
 *     screen y = y * cos(phi) - z * sin(phi)
 *
 * so flat surfaces foreshorten by the cosine, anything standing up swings out
 * on the sine, and skin at angle a around the fuselage tube arrives at
 * r * sin(a - phi) and faces us while cos(a - phi) is positive.
 *
 * Doing it that way is what stops the windows blinking. They are not switched
 * off when the aircraft passes inverted; they are at a fixed place on the hull
 * and they travel round the far side and back like everything else.
 */

const WING_SPAN: f32 = 0.086;
const FIN_H: f32 = 0.027;      // how far the fin stands above the spine
const POD_Y: f32 = 0.033;      // engines out along the span
const POD_Z: f32 = 0.017;      // and slung under it
const WIN_A: f32 = 0.95;       // window rows, radians up from the waist

fn aircraft(q: vec2f, phi: f32) -> Plane {
  let cf = cos(phi);
  let sf = sin(phi);
  // Flat surfaces vanish edge-on, so they are never given exactly zero width.
  let cs = select(min(cf, -0.075), max(cf, 0.075), cf >= 0.0);
  let fs = select(min(sf, -0.075), max(sf, 0.075), sf >= 0.0);

  let tail = vec2f(-0.078, 0.0);
  let nose = vec2f(0.092, 0.0);
  let ba = nose - tail;
  let h = clamp(dot(q - tail, ba) / dot(ba, ba), 0.0, 1.0);
  let r = body_radius(h);
  let fuse = seg(q, tail, nose) - r;

  // Wings and tailplane are one flat plate at z = 0.
  let qw = vec2f(q.x, q.y / cs);
  let wing  = panel(qw, 0.006, 0.056, 0.013, 0.44, WING_SPAN);
  let hstab = panel(qw - vec2f(-0.064, 0.0), 0.0, 0.026, 0.008, 0.48, 0.030);

  // The fin stands on the spine, so it sweeps to -sin and its area is the
  // sine: broadside exactly when the wings are edge-on.
  let qf = vec2f(q.x, (q.y + FIN_H * 0.5 * sf) / fs);
  let fin = panel(qf - vec2f(-0.056, 0.0), 0.0, 0.046, 0.011, 0.95, FIN_H * 0.5);

  // Pods hang below the wing, so they orbit rather than staying symmetric:
  // both slide with the sine while their separation closes with the cosine.
  let podMid = q.y + POD_Z * sf;
  let nac = vec2f(q.x - 0.024, abs(podMid) - POD_Y * abs(cf));
  let engine = seg(nac, vec2f(-0.017, 0.0), vec2f(0.017, 0.0)) - 0.0068;

  var d = fuse;
  var mat = 0.0;
  // Which piece of skin is facing us, measured round the hull from the top.
  var lie = 0.0;
  var round = 1.0 - clamp(abs(q.y) / max(r, 0.0001), 0.0, 1.0);
  if (d < 0.004) {
    let beta = asin(clamp(q.y / max(r, 0.0001), -1.0, 1.0));
    lie = cos(beta + phi);          // +1 looking at its back, -1 at its belly
  }

  let sc = max(abs(cs), 0.001);
  let sfc = max(abs(fs), 0.001);
  if (wing * sc < d) {
    d = wing * sc; mat = 1.0;
    round = 0.75 - 0.45 * clamp(abs(qw.y) / WING_SPAN, 0.0, 1.0);
    lie = cf;                        // the plate's own upward face
  }
  if (hstab * sc < d) { d = hstab * sc; mat = 3.0; round = 0.62; lie = cf; }
  if (fin * sfc < d) { d = fin * sfc; mat = 3.0; round = 0.92; lie = abs(sf); }
  if (engine < 0.0 || engine < d) {
    d = min(d, engine);
    mat = 2.0;
    round = 1.0 - clamp(abs(nac.y) / 0.0068, 0.0, 1.0);
    lie = 0.45;
  }
  return Plane(d, mat, round, lie);
}

/* Draw the aircraft at u. */
fn aircraft_at(p: vec2f, u: f32) -> vec4f {
  var c = path(u);
  c.x *= params.aspect;
  let hd = heading(u);
  let hv = normalize(vec2f(hd.x * params.aspect, hd.y));
  let rel = p - c;
  let q = vec2f(dot(rel, hv), dot(rel, vec2f(-hv.y, hv.x)));

  let phi = roll_of(u);
  let a = aircraft(q, phi);
  let px = fwidth(q.x) * 1.1 + 0.00002;
  let cover = 1.0 - smoothstep(-px, px, a.d);
  if (cover <= 0.001) {
    let glow = exp(-max(a.d, 0.0) * 240.0) * 0.13;
    return vec4f(params.edge * glow, glow * 0.55);
  }

  // Livery: pale on top, darker underneath, and the change between them is the
  // cosine of where that skin is -- so the aircraft turns over rather than
  // switching costume.
  let top = smoothstep(-0.55, 0.55, a.lie);
  let lift = pow(clamp(a.round, 0.0, 1.0), 0.65);
  var shade = 0.42 + 0.58 * lift;
  shade *= mix(0.62, 1.0, top);

  var col = params.body;
  if (a.mat < 0.5) {
    col = mix(params.body, params.core, 0.30 * lift * top);
    // Two window rows, at fixed places on the hull. A row is on screen at
    // r*sin(a - phi) and faces us while cos(a - phi) > 0, so it slides across
    // the fuselage, goes round the back and comes again -- no switch anywhere.
    let beta = asin(clamp(q.y / max(body_radius(
      clamp((q.x + 0.078) / 0.170, 0.0, 1.0)), 0.0001), -1.0, 1.0));
    let ang = beta + phi;
    let row = min(abs(ang - WIN_A), abs(ang + WIN_A));
    let onRow = 1.0 - smoothstep(0.13, 0.30, row);
    let dashes = step(0.55, fract(q.x * 118.0));
    let cabin = step(-0.038, q.x) * step(q.x, 0.060);
    col = mix(col, params.core, onRow * dashes * cabin * 0.9);
  } else if (a.mat < 1.5) {
    col = mix(params.body, params.edge, 0.35);
    col = mix(col * 0.68, col, top);     // underside of the wing
    let ledge = 1.0 - smoothstep(0.0, 0.010, abs(a.d));
    col = mix(col, params.core, ledge * 0.18 * top);
  } else if (a.mat < 2.5) {
    col = mix(params.body, params.edge, 0.55) * 0.90;
    let intake = 1.0 - smoothstep(0.0, 0.006, q.x - 0.036);
    col = mix(col, params.core * 0.55, intake * 0.55);
    let lip = 1.0 - smoothstep(0.0, 0.0035, abs(q.x - 0.040));
    col = mix(col, params.core, lip * 0.30);
  } else {
    col = mix(params.body, params.edge, 0.5);
    col = mix(col * 0.75, col, top);
  }

  col *= shade;
  let rim = 1.0 - smoothstep(0.0, 0.0055, abs(a.d));
  col = mix(col, params.core, rim * 0.22);

  // Tip lights ride the wings, so they foreshorten with them and never leave
  // the aircraft. Red to port, green to starboard; both are lenses that show
  // from above and below, so they do not fade with the roll.
  let tipY = WING_SPAN * cos(phi);
  let tipL = 1.0 - smoothstep(0.0, 0.007, length(q - vec2f(-0.008, -tipY)));
  let tipR = 1.0 - smoothstep(0.0, 0.007, length(q - vec2f(-0.008, tipY)));
  col += vec3f(1.0, 0.22, 0.22) * tipL * 0.9;
  col += vec3f(0.25, 1.0, 0.45) * tipR * 0.9;

  // The anti-collision beacon is on the spine, so it is hidden while the
  // aircraft is on its back -- which is a cleaner way to read the roll than
  // anything switching off.
  let beat = fract(params.time * 1.1);
  let strobe = smoothstep(0.06, 0.0, beat) + smoothstep(0.14, 0.09, beat) * 0.7;
  let beacon = 1.0 - smoothstep(0.0, 0.010, length(q - vec2f(-0.020, -0.5 * FIN_H * sin(phi))));
  col += vec3f(1.0) * beacon * strobe * 0.8 * clamp(cos(phi), 0.0, 1.0);

  return vec4f(col, cover);
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
  var plane = vec4f(0.0);
  // Two climbs, half a cycle apart, so the sky is never empty between them.
  for (var k = 0; k < 2; k++) {
    let u = fract(base + f32(k) * 0.5);
    let s = seam(u);
    if (s < 0.02) { continue; }
    smoke += trail_at(p, u) * s;
    let a = aircraft_at(p, u) * s;
    // Whichever is nearer the viewer wins; they never overlap in practice.
    plane = select(plane, a, a.w > plane.w);
  }

  let smokeMax = select(0.95, 0.40, params.night > 0.5);
  col = mix(col, params.smoke, clamp(smoke, 0.0, 1.0) * smokeMax);
  col = mix(col, plane.rgb / max(plane.w, 0.0001), clamp(plane.w, 0.0, 1.0));

  return vec4f(col, 1.0);
}
`;
