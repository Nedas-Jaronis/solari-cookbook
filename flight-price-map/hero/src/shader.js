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
const BARREL_R: f32 = 0.052;   // radius of the helix, in uv

fn roll_phase(u: f32) -> f32 {
  return clamp((u - ROLL_A) / (ROLL_B - ROLL_A), 0.0, 1.0);
}

fn roll_of(u: f32) -> f32 {
  return smoothstep(0.0, 1.0, roll_phase(u)) * 6.2831853;
}

/* A barrel roll is a corkscrew flown around the original flight path, not a
   spin on the spot -- that is an aileron roll, and it was what this did first.
   The aircraft goes all the way round a circle whose axis is the direction of
   travel, so from here the part of that circle that runs across the path shows
   as a swing to one side, and the part that runs toward and away from us shows
   as the aircraft getting nearer and then smaller.

   Returned as (offset.x, offset.y, nearness). The envelope opens the radius
   from nothing and closes it back to nothing, so the aircraft leaves the line
   and rejoins it rather than jumping onto a circle already in progress. */
fn barrel(u: f32) -> vec3f {
  let t = roll_phase(u);
  if (t <= 0.0 || t >= 1.0) { return vec3f(0.0); }
  let r = roll_of(u);
  let env = sin(3.14159265 * t);
  let hd = heading(u);
  let across = vec2f(-hd.y, hd.x);
  return vec3f(across * (BARREL_R * env * sin(r)), env * cos(r));
}

/* Where the aircraft actually is: the climb, plus whatever the barrel is
   doing. Everything that needs a position asks this rather than path(), which
   is why the contrail corkscrews without being told about the manoeuvre. */
fn flight(u: f32) -> vec2f {
  return path(u) + barrel(u).xy;
}

fn flight_heading(u: f32) -> vec2f {
  let a = flight(min(u + 0.010, 1.0));
  let b = flight(u);
  let d = a - b;
  // On the exit the two samples can land on top of each other; fall back to
  // the climb rather than normalising a zero.
  if (length(d) < 1e-6) { return heading(u); }
  return normalize(d);
}

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
fn aircraft(q: vec2f, cs: f32, sn: f32) -> Plane {
  let qw = vec2f(q.x, q.y / cs);
  let tail = vec2f(-0.078, 0.0);
  let nose = vec2f(0.092, 0.0);
  let ba = nose - tail;
  let h = clamp(dot(q - tail, ba) / dot(ba, ba), 0.0, 1.0);
  let r = body_radius(h);
  let across = abs(q.y);
  let fuse = seg(q, tail, nose) - r;

  //                 root x  root chord  tip chord  sweep  span
  let wing  = panel(qw, 0.006,     0.056,     0.013,  0.44, 0.086);
  let hstab = panel(qw - vec2f(-0.064, 0.0), 0.0, 0.026, 0.008, 0.48, 0.030);
  // In plan view a fin is a sliver on the centreline, so it is the same panel
  // with the span squeezed almost to nothing.
  let fs = select(min(sn, -0.085), max(sn, 0.085), sn >= 0.0);
  let qf = vec2f(q.x, (q.y - 0.017 * sn) / fs);
  let fin   = panel(qf - vec2f(-0.058, 0.0), 0.0, 0.038, 0.016, 0.55, 0.017);

  // Podded engines hang ahead of and below the leading edge, on the fuselage
  // axis -- not across it, which is what made them look like barrels.
  let nac = vec2f(q.x - 0.024, abs(q.y) - 0.033 * abs(cs));
  let engine = seg(nac, vec2f(-0.017, 0.0), vec2f(0.017, 0.0)) - 0.0068;

  var d = fuse;
  var mat = 0.0;
  var round = 1.0 - clamp(across / max(r, 0.0001), 0.0, 1.0);

  let span_scale = max(abs(cs), 0.001);
  if (wing * span_scale < d) {
    d = wing * span_scale; mat = 1.0;
    // A wing is not flat to the eye: it is brightest inboard and falls away.
    round = 0.75 - 0.45 * clamp(abs(qw.y) / 0.086, 0.0, 1.0);
  }
  if (hstab * span_scale < d) { d = hstab * span_scale; mat = 3.0; round = 0.62; }
  let fin_scale = max(abs(fs), 0.001);
  if (fin * fin_scale < d) { d = fin * fin_scale; mat = 3.0; round = 0.92; }
  if (engine < 0.0 || engine < d) {
    d = min(d, engine);
    mat = 2.0;
    round = 1.0 - clamp(abs(nac.y) / 0.0068, 0.0, 1.0);
  }
  return Plane(d, mat, round);
}

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
    var c = flight(s);
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

/* Draw the aircraft at u, returning premultiplied colour and coverage.
   Shaded rather than stamped: the fuselage and nacelles are lit as tubes, the
   wings catch a highlight along the leading edge, and the whole thing sits on
   a soft shadow so it reads as an object in air rather than a decal. */
fn aircraft_at(p: vec2f, u: f32) -> vec4f {
  let bar = barrel(u);
  var c = flight(u);
  c.x *= params.aspect;
  let hd = flight_heading(u);
  let h = normalize(vec2f(hd.x * params.aspect, hd.y));
  let rel = p - c;
  let raw = vec2f(dot(rel, h), dot(rel, vec2f(-h.y, h.x)));

  // Round the near side of the barrel it is closer to the eye, so it is
  // bigger. Without this the corkscrew reads as a weave along the ground.
  let scale = 1.0 + 0.16 * bar.z;
  let q = raw / scale;

  let roll = roll_of(u);
  let facing = cos(roll);      // how much of the span still faces us
  // Never exactly zero: at knife-edge the aircraft is a sliver, not a
  // division by nothing.
  let cs = select(min(facing, -0.085), max(facing, 0.085), facing >= 0.0);
  let a = aircraft(q, cs, sin(roll));
  let belly = facing < 0.0;
  // Distances came back in the scaled frame, so they have to come out of it.
  let d = a.d * scale;
  // Antialias against the pixel, not against a fixed number, so the aircraft
  // stays crisp on a phone and on a 4K display alike.
  let px = fwidth(raw.x) * 1.1 + 0.00002;
  let cover = 1.0 - smoothstep(-px, px, d);
  if (cover <= 0.001) {
    // Still worth a breath of glow, which is what keeps it from looking cut out.
    let glow = exp(-max(d, 0.0) * 240.0) * 0.13;
    return vec4f(params.edge * glow, glow * 0.55);
  }

  // Sunlight from over the left shoulder, in aircraft space.
  let sun = normalize(vec2f(-0.35, -0.94));
  let lift = pow(clamp(a.round, 0.0, 1.0), 0.65);          // tube shading
  let side = clamp(0.5 + 0.5 * dot(normalize(vec2f(0.0001, q.y)), sun), 0.0, 1.0);
  var shade = 0.42 + 0.58 * lift * mix(0.55, 1.0, side);

  var col = params.body;
  if (a.mat < 0.5) {
    // Fuselage: a lighter crown, and a cabin window line down the side.
    col = mix(params.body, params.core, 0.30 * lift);
    let along = q.x;
    // No windows on the underside, and the belly is the shadowed side.
    let win = step(0.55, fract(along * 118.0)) *
              step(abs(abs(q.y) - 0.0052), 0.0022) *
              step(-0.038, along) * step(along, 0.060) *
              select(1.0, 0.0, belly);
    col = mix(col, params.core, win * 0.85);
    if (belly) { col *= 0.72; }
  } else if (a.mat < 1.5) {
    // Wing: darker than the body, with the leading edge picked out.
    col = mix(params.body, params.edge, 0.35);
    if (belly) { col *= 0.70; }
    let ledge = 1.0 - smoothstep(0.0, 0.010, abs(d));
    col = mix(col, params.core, ledge * 0.18);
    shade *= 0.94;
  } else if (a.mat < 2.5) {
    // Engine: darker than the wing it hangs under, or it reads as a pipe
    // lying on top of one. A bright fan face at the intake, and a shadow
    // where the pod meets the surface behind it.
    col = mix(params.body, params.edge, 0.55) * 0.72;
    let intake = 1.0 - smoothstep(0.0, 0.006, q.x - 0.036);
    col = mix(col, params.core * 0.55, intake * 0.55);
    let lip = 1.0 - smoothstep(0.0, 0.0035, abs(q.x - 0.040));
    col = mix(col, params.core, lip * 0.30);
  } else {
    col = mix(params.body, params.edge, 0.5);
  }

  col *= shade;
  // Rim light along the silhouette, which is what separates it from the sky.
  let rim = 1.0 - smoothstep(0.0, 0.0055, abs(d));
  col = mix(col, params.core, rim * 0.22);

  // Navigation lights: red to port, green to starboard, and a strobe that
  // fires twice a second the way a real anti-collision beacon does.
  let tipL = 1.0 - smoothstep(0.0, 0.007, length(q - vec2f(-0.008, -0.084)));
  let tipR = 1.0 - smoothstep(0.0, 0.007, length(q - vec2f(-0.008, 0.084)));
  let beat = fract(params.time * 1.1);
  let strobe = smoothstep(0.06, 0.0, beat) + smoothstep(0.14, 0.09, beat) * 0.7;
  col += vec3f(1.0, 0.22, 0.22) * tipL * 0.9;
  col += vec3f(0.25, 1.0, 0.45) * tipR * 0.9;
  col += vec3f(1.0) * (tipL + tipR) * strobe * 0.55;

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
