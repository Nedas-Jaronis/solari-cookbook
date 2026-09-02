/* Render the hero shader headless and write PNGs, so it can be judged on
 * pixels instead of on hope. There is no WebGPU in the headless browser this
 * project screenshots with, so this is the only way to see the thing before it
 * ships.
 *
 *   node still.mjs            a few frames of both palettes
 *   node still.mjs 0.42       one frame, at that point in the cycle
 */
import { writeFileSync, mkdirSync } from "node:fs";
import { PNG } from "pngjs";
import { init, effect, target } from "vgpu/node";
import { SHADER } from "./src/shader.js";
import { PALETTE } from "./src/palette.js";

const W = 960;
const H = 600;
const CYCLE = 17.0;
const OUT = "stills";

const at = Number(process.argv[2]);
const frames = Number.isFinite(at)
  ? [at]
  : [0.10, 0.30, 0.52, 0.78];

mkdirSync(OUT, { recursive: true });

const gpu = await init();
const scene = effect(gpu, SHADER);

for (const theme of ["day", "night"]) {
  const pal = PALETTE[theme];
  for (const u of frames) {
    const colour = target(gpu, { size: [W, H] });
    scene.set({
      params: {
        time: u * CYCLE,
        aspect: W / H,
        night: theme === "night" ? 1 : 0,
        dpr: 1,
        ...pal,
      },
    });
    scene.draw(colour);
    const pixels = await colour.read();

    const png = new PNG({ width: W, height: H });
    png.data.set(pixels);
    const name = `${OUT}/${theme}-${String(Math.round(u * 100)).padStart(3, "0")}.png`;
    writeFileSync(name, PNG.sync.write(png));

    // A frame that is one flat colour means the shader ran and drew nothing,
    // which looks identical to "it worked" in a file listing.
    let lo = 255;
    let hi = 0;
    for (let i = 0; i < pixels.length; i += 4) {
      lo = Math.min(lo, pixels[i]);
      hi = Math.max(hi, pixels[i]);
    }
    console.log(`${name}  red ${lo}..${hi}${hi - lo < 6 ? "   <-- FLAT" : ""}`);
  }
}

gpu.dispose();
