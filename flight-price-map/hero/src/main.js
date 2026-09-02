/* Boot the GPU hero, or say you could not.
 *
 * Exposed as one global that returns a promise for a boolean, because the page
 * has to be able to fall back: WebGPU is not everywhere, a laptop can refuse a
 * device under battery saver, and a headless browser has none at all. The
 * canvas scene stays in the page and runs whenever this answers false, so the
 * hero is never blank.
 */
import { clock, init, effect, frameLoop, surface } from "vgpu";
import { SHADER } from "./shader.js";
import { PALETTE } from "./palette.js";

const isDark = () => {
  const stamped = document.documentElement.getAttribute("data-theme");
  if (stamped) return stamped === "dark";
  return matchMedia("(prefers-color-scheme: dark)").matches;
};

async function boot(canvas) {
  if (!navigator.gpu) return false;

  let gpu;
  try {
    gpu = await init();
  } catch (err) {
    // An adapter can be refused for reasons that are none of our business.
    console.info("hero: no GPU device, using the canvas scene", err);
    return false;
  }

  const view = surface(gpu, canvas, { dpr: [1, 2] });
  const scene = effect(gpu, SHADER);
  const time = clock(gpu);

  const shape = () => ({
    aspect: Math.max(canvas.clientWidth, 1) / Math.max(canvas.clientHeight, 1),
    dpr: Math.min(devicePixelRatio || 1, 2),
  });
  const paint = () => scene.set({
    params: { ...shape(), night: isDark() ? 1 : 0,
              ...(isDark() ? PALETTE.night : PALETTE.day) },
  });

  paint();
  view.onResize(paint);

  // The palette is a page decision, not a GPU one, so follow the same two
  // signals the stylesheet follows.
  const dark = matchMedia("(prefers-color-scheme: dark)");
  dark.addEventListener("change", paint);
  new MutationObserver(paint).observe(document.documentElement,
    { attributes: true, attributeFilter: ["data-theme"] });

  const still = matchMedia("(prefers-reduced-motion: reduce)");
  if (still.matches) {
    // One composed frame, held. Picked mid-climb so it is a scene and not an
    // empty sky.
    scene.set({ params: { time: 0.58 * 17 } });
    scene.draw(view);
    still.addEventListener("change", () => location.reload());
    return true;
  }

  let stop = null;
  const run = () => {
    if (stop) return;
    stop = frameLoop(gpu, (frame) => {
      scene.set({ params: { time: time.time } });
      frame.pass(view, scene);
    });
  };
  const halt = () => {
    if (!stop) return;
    if (typeof stop === "function") stop();
    else if (stop && typeof stop.stop === "function") stop.stop();
    stop = null;
  };
  // A hidden tab should not be rendering a sky nobody is looking at.
  document.addEventListener("visibilitychange",
    () => (document.hidden ? halt() : run()));
  run();
  return true;
}

window.__heroGPU = (canvas) =>
  boot(canvas).catch((err) => {
    console.info("hero: GPU scene failed, using the canvas scene", err);
    return false;
  });
