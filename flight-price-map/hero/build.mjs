/* Bundle the GPU hero to one file that sits next to the pages.
 *
 * Not inlined. Inlining it costs 46 KB gzipped on top of a 36 KB page -- more
 * than doubling it -- and every reader would pay that, including the ones on a
 * browser with no WebGPU who could never see the thing. The page asks for this
 * file only after it has checked that navigator.gpu exists, so the weight lands
 * on the machines that get the upgrade and on nobody else.
 *
 * The page still works with this file absent: the canvas scene is the fallback
 * and it ships inside the HTML as it always did. Nobody cloning this repo needs
 * Node to run the site, only to change the shader.
 */
import { build } from "esbuild";
import { statSync } from "node:fs";

await build({
  entryPoints: ["src/main.js"],
  bundle: true,
  format: "iife",
  target: ["chrome113", "edge113", "safari18"],   // where WebGPU actually is
  minify: true,
  legalComments: "none",
  outfile: "../hero.js",
});

const kb = statSync("../hero.js").size / 1024;
console.log(`hero.js  ${kb.toFixed(1)} KB`);
if (kb > 300) {
  console.error("the hero has outgrown being a decoration");
  process.exit(1);
}
