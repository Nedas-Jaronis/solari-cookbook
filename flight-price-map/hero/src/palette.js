/* The same two palettes the canvas hero uses, as linear-ish float triples.
 *
 * Kept here rather than read from the page so the headless stills show what
 * the browser will show. If sky.py's NIGHT/DAY change, change these with them.
 */
const rgb = (hex) => {
  const n = parseInt(hex.replace("#", ""), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
};

export const PALETTE = {
  day: {
    skyTop: rgb("#d7e7f8"),
    skyMid: rgb("#e9f2fb"),
    skyBot: rgb("#f6fafd"),
    smoke: rgb("#ffffff"),
    core: rgb("#08152c"),
    edge: rgb("#17376b"),
    body: rgb("#5d84ba"),
  },
  night: {
    skyTop: rgb("#070b16"),
    skyMid: rgb("#0b1428"),
    skyBot: rgb("#101d3b"),
    smoke: rgb("#e0ecff"),
    core: rgb("#f2f8ff"),
    edge: rgb("#bcd8ff"),
    body: rgb("#6f9fe8"),
  },
};
