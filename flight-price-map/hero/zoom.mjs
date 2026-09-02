/* Render one frame large and crop to the aircraft, so the geometry can be
 * judged instead of guessed at. The plane is about 0.15 of the frame wide, so
 * at a normal hero size it is 150 pixels of a 960-pixel still -- too small to
 * tell a tailplane from a second wing, which is exactly the mistake this is
 * here to catch.
 *
 *   node zoom.mjs [u] [theme]
 */
import { writeFileSync, mkdirSync } from "node:fs";
import { PNG } from "pngjs";
import { init, effect, target } from "vgpu/node";
import { SHADER } from "./src/shader.js";
import { PALETTE } from "./src/palette.js";

const u = Number(process.argv[2] ?? 0.52);
const theme = process.argv[3] ?? "night";
const W = 3200;
const H = 2000;
const CROP = 620;

// Where the aircraft is, in the same curve the shader flies.
const path = (t) => {
  const a = [0.30, 1.25], b = [0.80, 0.80], c = [1.05, -0.20];
  const k = 1 - t;
  return [k * k * a[0] + 2 * k * t * b[0] + t * t * c[0],
          k * k * a[1] + 2 * k * t * b[1] + t * t * c[1]];
};

mkdirSync("stills", { recursive: true });
const gpu = await init();
const scene = effect(gpu, SHADER);
scene.set({
  params: { time: u * 17, aspect: W / H, night: theme === "night" ? 1 : 0,
            dpr: 1, ...PALETTE[theme] },
});
const colour = target(gpu, { size: [W, H] });
scene.draw(colour);
const pixels = await colour.read();

const [px, py] = path(u);
const cx = Math.round(px * W);
const cy = Math.round(py * H);
const x0 = Math.min(Math.max(cx - CROP / 2, 0), W - CROP);
const y0 = Math.min(Math.max(cy - CROP / 2, 0), H - CROP);

const png = new PNG({ width: CROP, height: CROP });
for (let y = 0; y < CROP; y++) {
  const from = ((y0 + y) * W + x0) * 4;
  png.data.set(pixels.subarray(from, from + CROP * 4), y * CROP * 4);
}
const name = `stills/zoom-${theme}-${Math.round(u * 100)}.png`;
writeFileSync(name, PNG.sync.write(png));
console.log(`${name}  centred on the aircraft at u=${u}`);
gpu.dispose();
