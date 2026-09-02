"""Record the real thing searching a route it has never seen.

    python server.py                     # in one terminal
    python demo.py --from TPA --to BCN --date 2026-12-08

Produces three files in demo/:

    demo.webm   the session exactly as it happened, unedited
    demo.mp4    the same frames as H.264, because that is what the places
                people post video actually accept -- webm is not one of them
    demo.gif    the same run, paced for somebody scrolling past

Nothing here is staged. It drives the live page against the live service, so
whatever the sites do during the recording is what ends up in the file. The gif
only changes how long each moment is held: the twenty seconds of waiting play
back in about two, because a viewer needs to know the wait exists, not to sit
through it.
"""

import argparse
import io
import shutil
import subprocess
import time
from pathlib import Path

from PIL import Image
from patchright.sync_api import sync_playwright

from common import HERE

OUT = HERE / "demo"


class Reel:
    """Frames plus how long each should be held on playback."""

    def __init__(self, page, width: int):
        self.page, self.width = page, width
        self.frames: list[tuple[Image.Image, int]] = []

    def shoot(self, hold: int = 110) -> None:
        raw = Image.open(io.BytesIO(self.page.screenshot())).convert("RGB")
        if raw.width != self.width:
            scale = self.width / raw.width
            raw = raw.resize((self.width, int(raw.height * scale)),
                             Image.LANCZOS)
        self.frames.append((raw, hold))

    def hold(self, seconds: float, fps: int = 8, playback: int = 110) -> None:
        """Film for real seconds; `playback` sets how fast it plays back."""
        deadline = time.time() + seconds
        while time.time() < deadline:
            self.shoot(playback)
            time.sleep(1 / fps)

    def save(self, path: Path, colors: int = 96) -> None:
        # A screenshot is a few flat colours and some type, so quantising to a
        # small palette costs almost nothing visually and is the difference
        # between a file that can be posted and one that cannot.
        images = [f.convert("P", palette=Image.ADAPTIVE, colors=colors)
                  for f, _ in self.frames]
        images[0].save(path, save_all=True, append_images=images[1:],
                       duration=[d for _, d in self.frames], loop=0,
                       optimize=True, disposal=2)


def encode(webm: Path, mp4: Path) -> Path | None:
    """Re-container the recording as H.264, same frames, no edit.

    Playwright records webm, which is the one format neither X nor LinkedIn
    will take. yuv420p and +faststart are the two flags that decide whether a
    phone plays it inline or shows a black rectangle.
    """
    if not shutil.which("ffmpeg"):
        print("no ffmpeg on PATH -- skipping the mp4 (webm and gif still written)")
        return None
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm),
         "-c:v", "libx264", "-preset", "slow", "-crf", "20",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart",
         "-r", "30", "-an", str(mp4)],
        check=True)
    return mp4


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="origin", default="TPA")
    ap.add_argument("--to", dest="destination", default="BCN")
    ap.add_argument("--date", default="2026-12-08")
    ap.add_argument("--url", default="http://127.0.0.1:8080/")
    ap.add_argument("--theme", default="dark", choices=["dark", "light"])
    ap.add_argument("--fresh", action="store_true", default=True,
                    help="drop this route from the cache first, so the "
                         "recording shows a real search")
    ap.add_argument("--colors", type=int, default=96)
    ap.add_argument("--width", type=int, default=900,
                    help="width of the gif; the webm keeps the full size")
    args = ap.parse_args()

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()

    if args.fresh:
        # A cached answer returns in 30ms, which makes a demo of a live search
        # look like a demo of a lookup table.
        import sqlite3
        db_path = HERE / "cache.db"
        if db_path.exists():
            db = sqlite3.connect(db_path)
            db.execute("DELETE FROM runs WHERE key LIKE ?",
                       (f"{args.origin.upper()}-{args.destination.upper()}-%",))
            db.commit(); db.close()
            print(f"cleared any cached {args.origin} -> {args.destination}")

    with sync_playwright() as play:
        browser = play.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            color_scheme=args.theme,
            record_video_dir=str(OUT),
            record_video_size={"width": 1280, "height": 800})
        page = context.new_page()
        reel = Reel(page, args.width)

        page.goto(args.url)
        page.wait_for_timeout(2600)          # let the aircraft get airborne
        reel.hold(1.6)

        # Type it out, so it is plainly a search and not a stored answer.
        page.click("#from"); page.fill("#from", "")
        page.type("#from", args.origin, delay=110)
        reel.shoot(240)
        page.click("#to"); page.fill("#to", "")
        page.type("#to", args.destination, delay=110)
        reel.shoot(240)
        page.fill("#when", args.date)
        reel.shoot(420)

        started = time.time()
        page.click(".go")
        reel.hold(1.2, playback=110)

        # The wait is the point -- browsers are out working -- but nobody wants
        # to sit through it. Film a fixed handful of moments however long it
        # takes, so a slow search does not turn into a hundred frames of
        # spinner and a file too large to post.
        WAIT_FRAMES = 14
        shots = 0
        while page.query_selector(".flight") is None:
            if shots < WAIT_FRAMES:
                reel.shoot(90)
                shots += 1
            page.wait_for_timeout(900)
            if time.time() - started > 240:
                break
        waited = time.time() - started

        reel.hold(2.2, playback=110)          # the answer, held long enough to read
        page.mouse.wheel(0, 420); page.wait_for_timeout(500)
        reel.hold(1.4, playback=110)
        page.mouse.wheel(0, 420); page.wait_for_timeout(500)
        reel.hold(1.2, playback=110)
        page.mouse.wheel(0, -840); page.wait_for_timeout(500)

        # Show a filter working, but never end on an empty list: on a thin
        # route "nonstop" is often nothing at all, which reads as broken.
        for choice in ("1", "0"):
            pill = page.query_selector(f'.pill[data-value="{choice}"]')
            if not pill:
                continue
            pill.click()
            page.wait_for_timeout(700)
            left = page.eval_on_selector_all(".flight", "e=>e.length")
            if left:
                reel.hold(1.8, playback=110)
                break
            page.click('.pill[data-value="any"]')
            page.wait_for_timeout(400)

        # Clear the filter before the last shot. The headline is the best fare
        # overall, so leaving a filter on ends the demo with a headline price
        # that is not the card underneath it -- true, but it reads as a bug.
        clear = page.query_selector("#reset")
        if clear:
            clear.click()
            page.wait_for_timeout(700)

        # End on the cheapest fare with the other sites' prices beside it.
        page.mouse.wheel(0, -900)
        page.wait_for_timeout(600)
        reel.hold(2.6, playback=110)

        # Read the values now: an element handle is dead once the browser is.
        best = page.eval_on_selector(".pick-price", "e=>e.textContent.trim()")             if page.query_selector(".pick-price") else None
        tally = page.eval_on_selector("#tally", "e=>e.textContent.trim()")             if page.query_selector("#tally") else ""
        cards = len(page.query_selector_all(".flight"))
        page.close()
        context.close()
        browser.close()

    video = next(OUT.glob("*.webm"), None)
    if video:
        video.rename(OUT / "demo.webm")
        mp4 = encode(OUT / "demo.webm", OUT / "demo.mp4")
    reel.save(OUT / "demo.gif", colors=args.colors)

    gif = (OUT / "demo.gif").stat().st_size / 1e6
    print(f"{args.origin} -> {args.destination} on {args.date}")
    print(f"  answered in {waited:.0f}s, {cards} flights on screen")
    if best:
        print(f"  best {best}   {tally}")
    print(f"  demo/demo.webm   the run, unedited")
    if video and mp4:
        print(f"  demo/demo.mp4    {mp4.stat().st_size / 1e6:.1f} MB, postable")
    print(f"  demo/demo.gif    {len(reel.frames)} frames, {gif:.1f} MB")


if __name__ == "__main__":
    main()
