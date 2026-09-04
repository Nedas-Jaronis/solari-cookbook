"""Price any route, live, on request.

    python server.py                 # -> http://localhost:8080

Everything before this priced a fixed list of routes and baked the answer into
a page. This takes a route it has never seen and goes and finds out, which is
the whole point of having cloud browsers.

Three things shape the design, and all three came from measurement rather than
taste:

  A search is slow but not that slow. Six sites on one route is six browsers
  and about twenty seconds -- an acceptable wait. Adding every nearby airport
  is thirty browsers and about two minutes, which is not. So the quick answer
  comes back first and the nearby airports arrive after it, into the same
  result, while the traveller is already reading.

  Repeating a search is the expensive mistake. Fares do not move minute to
  minute, so an identical route and date inside the cache window is answered
  from store. Without that, ten people asking the same question on the same
  morning costs ten times what it should and gets the sites blocking us ten
  times faster.

  The sites push back. A global limit keeps us inside the plan's concurrency
  whatever arrives, and compare.py's per-site throttle still applies. Four
  sweeps by one person was enough to lose Skyscanner for a day; an open
  endpoint without these would lose everything.

No web framework: the standard library serves this shape of thing perfectly
well, and a cookbook example is more useful when it runs on a bare Python.
"""

import argparse
import asyncio
import json
import mimetypes
import os
import pathlib
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import airports
import compare
import sites as siteslib
import trips as tripslib
from common import HERE, Query, load_env

DB = pathlib.Path(os.environ.get("FARE_DB", HERE / "cache.db"))
QUICK_SITES = ["google", "kayak", "momondo", "expedia"]
CACHE_TTL = int(os.environ.get("FARE_CACHE_TTL", 45 * 60))

# On a public URL the limit is not the code, it is other people. One search is
# four to thirty browsers against sites that push back; left open, a handful of
# visitors would spend a month's credit in an afternoon and get us blocked
# besides. These are deliberately generous for one person planning one trip and
# mean for anyone else.
PER_IP_HOUR = int(os.environ.get("FARE_PER_IP_HOUR", 10))
FRESH_PER_IP_HOUR = int(os.environ.get("FARE_FRESH_PER_IP_HOUR", 3))
GLOBAL_PER_DAY = int(os.environ.get("FARE_GLOBAL_PER_DAY", 200))

# Widening to every nearby airport is five times the work of the plain search:
# four browsers becomes twenty. Worth it on your own machine, and not worth
# handing to the internet -- so a public deploy turns it off and the quick
# answer is what visitors get.
ALLOW_NEARBY = os.environ.get("FARE_ALLOW_NEARBY", "1") not in ("0", "false", "")

# Where the browsers come out. This was hard-coded to "us" because non-US
# exits kept dropping searches under load -- four of twenty-one, which for a
# price comparison means quietly reporting the cheapest fare it managed to
# read. That is fixed: re-tested across eight countries, every browser exited
# where it was asked and every search came back.
#
# US stays the default because we measured what changing it buys, and the
# answer is nothing: across ~1,400 matched per-flight comparisons on two
# routes, not one flight was priced differently in any country. Reach for a
# different exit when you want the page a local is shown, not because you
# expect a cheaper number.
EGRESS = os.environ.get("FARE_EGRESS", "us").lower()
# Only countries this project has actually watched a browser come out of.
EGRESS_OK = frozenset({"au", "br", "ca", "de", "gb", "in", "jp", "sg", "us"})


# --------------------------------------------------------------------------
# The store: finished runs, so the same question is not paid for twice
# --------------------------------------------------------------------------

def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB, check_same_thread=False)
    db.execute("""CREATE TABLE IF NOT EXISTS runs (
        key TEXT PRIMARY KEY, made_at REAL NOT NULL, payload TEXT NOT NULL)""")
    db.commit()
    return db


def cache_key(q: Query, nearby: bool, country: str = EGRESS) -> str:
    # The country belongs in the key. Without it a search from Tokyo is
    # answered with the page London was shown, which is the one thing this
    # tool must never do quietly.
    return (f"{q.origin}-{q.destination}-{q.date}-{q.ret or 'ow'}"
            f"-{int(nearby)}-{country}")


def remember(db, key: str, payload: dict) -> None:
    with LOCK:
        db.execute("REPLACE INTO runs VALUES (?,?,?)",
                   (key, time.time(), json.dumps(payload)))
        db.commit()


def recall(db, key: str) -> tuple[dict | None, float]:
    with LOCK:
        row = db.execute("SELECT made_at, payload FROM runs WHERE key=?",
                         (key,)).fetchone()
    if not row or time.time() - row[0] > CACHE_TTL:
        return None, 0.0
    return json.loads(row[1]), time.time() - row[0]


LOCK = threading.Lock()
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()

SEEN: dict[str, list[float]] = {}
SPENT: dict[str, object] = {}
BUDGET_LOCK = threading.Lock()


def budget(who: str, fresh: bool) -> str | None:
    """Book one search against the limits. Returns why not, or None to go.

    A cached answer never reaches here, so these counters measure the only
    thing that actually costs anything: browsers launched.
    """
    now = time.time()
    today = time.strftime("%Y-%m-%d")
    with BUDGET_LOCK:
        if SPENT.get("day") != today:
            SPENT.clear()
            SPENT["day"] = today
            SPENT["count"] = 0
        if SPENT["count"] >= GLOBAL_PER_DAY:
            return ("This has used its searches for today. Anything already "
                    "looked up is still here; new routes come back tomorrow.")

        recent = [t for t in SEEN.get(who, []) if now - t < 3600]
        if len(recent) >= PER_IP_HOUR:
            return (f"That is {PER_IP_HOUR} searches in an hour from here, "
                    f"which is the limit. Try again shortly.")

        again = [t for t in SEEN.get(who + " fresh", []) if now - t < 3600]
        if fresh and len(again) >= FRESH_PER_IP_HOUR:
            return ("Re-checking is limited to a few an hour. The prices on "
                    "screen are still the ones we read.")

        SEEN[who] = recent + [now]
        if fresh:
            SEEN[who + " fresh"] = again + [now]
        SPENT["count"] = SPENT["count"] + 1
    return None


# --------------------------------------------------------------------------
# The work
# --------------------------------------------------------------------------

def as_run(q: Query, results: list[dict], seconds: float) -> dict:
    """Shape a set of results the way a compare.py run file looks."""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "origin": q.origin, "destination": q.destination,
        "date": q.date, "ret": q.ret, "seconds": round(seconds, 1),
        "site_names": {s.key: s.name for s in siteslib.SITES},
        "results": results,
    }


def publish(job_id: str, q: Query, results: list[dict], seconds: float,
            phase: str, cached_age: float = 0.0) -> dict:
    """Turn raw results into the trip the page renders, and store it on the job."""
    run = as_run(q, results, seconds)
    built = tripslib.build([run])
    with JOBS_LOCK:
        job = JOBS[job_id]
        job["phase"] = phase
        job["run"] = run
        job["trip"] = built[0] if built else None
        job["searched"] = len(results)
        job["answered"] = sum(1 for r in results if r.get("ok"))
        job["seconds"] = round(seconds, 1)
        job["cached_age"] = round(cached_age)
        if not built:
            job["error"] = ("No fares could be read for that route. It may not "
                            "be flown, or every site refused us at once.")
    return run


async def stream(job_id: str, q: Query, started: float, results: list[dict],
                 coros: list, phase: str) -> None:
    """Wait on all of them, but publish after each one lands.

    Gathering the whole batch and publishing once meant the page saw nothing
    until the *slowest* site finished -- four sites in parallel, and a wait as
    long as the worst of them, staring at a spinner with fares already sitting
    in memory. Widening was worse: twenty searches, one publish at the end.

    `as_completed` yields them in the order they answer, so the first site to
    come back puts fares on the screen and every one after it adds to them.
    """
    for landed in asyncio.as_completed(coros):
        results.append(await landed)
        publish(job_id, q, results, time.time() - started, phase)


async def hunt(job_id: str, q: Query, nearby: bool, gate: asyncio.Semaphore,
               db, country: str = EGRESS) -> None:
    """Quick answer first, then widen to the nearby airports."""
    started = time.time()
    site_gates = {k: asyncio.Semaphore(2) for k in QUICK_SITES}

    def task(site, dest):
        return compare.Task(site, q.origin, dest, country)

    def go(t):
        return compare.run(SOLARI, gate, site_gates[t.site], t, q.date, q.ret,
                           False)

    try:
        results: list[dict] = []
        quick = [task(s, q.destination) for s in QUICK_SITES]
        await stream(job_id, q, started, results, [go(t) for t in quick],
                     "quick")

        others = [a for a in airports.expand(q.destination)
                  if a != q.destination]
        if nearby and others:
            with JOBS_LOCK:
                JOBS[job_id]["phase"] = "widening"
                JOBS[job_id]["widening_to"] = others
            wide = [task(s, d) for d in others for s in QUICK_SITES]
            await stream(job_id, q, started, results, [go(t) for t in wide],
                         "widening")

        run = publish(job_id, q, results, time.time() - started, "done")
        remember(db, cache_key(q, nearby, country), run)
    except Exception as err:                      # a job must never hang
        with JOBS_LOCK:
            JOBS[job_id]["phase"] = "failed"
            JOBS[job_id]["error"] = f"{type(err).__name__}: {err}"[:200]


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):            # one tidy line per request
        print(f"  {self.command} {self.path} -> {args[1] if len(args) > 1 else ''}")

    def send_json(self, code: int, body: dict) -> None:
        blob = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(blob)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(blob)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path.startswith("/api/search/"):
            job_id = path.rsplit("/", 1)[-1]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            if not job:
                return self.send_json(404, {"error": "no such search"})
            return self.send_json(200, {k: v for k, v in job.items()
                                        if k != "run"})
        if path == "/api/health":
            with JOBS_LOCK:
                running = sum(1 for j in JOBS.values()
                              if j["phase"] not in ("done", "failed"))
            with BUDGET_LOCK:
                spent = SPENT.get("count", 0)
            return self.send_json(200, {
                "ok": True, "running": running, "jobs": len(JOBS),
                "searches_today": spent, "daily_limit": GLOBAL_PER_DAY})
        return self.serve_file(path)

    def serve_file(self, path: str) -> None:
        name = "live.html" if path in ("/", "") else path.lstrip("/")
        target = (HERE / name).resolve()
        if HERE.resolve() not in target.parents or not target.is_file():
            return self.send_json(404, {"error": "not found"})
        blob = target.read_bytes()
        self.send_response(200)
        # Everything this serves is written as UTF-8, and guess_type says only
        # "text/html". A browser handed text with no encoding guesses, and
        # Chrome guesses windows-1252, which turned every em dash on the
        # results page into mojibake. Say it rather than let it guess.
        kind = mimetypes.guess_type(str(target))[0] or "text/plain"
        if kind.startswith("text/") or kind == "application/javascript":
            kind += "; charset=utf-8"
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(blob)))
        self.end_headers()
        self.wfile.write(blob)

    def caller(self) -> str:
        """Who is asking, through whatever proxy sits in front of us."""
        forwarded = self.headers.get("X-Forwarded-For", "")
        return (forwarded.split(",")[0].strip()
                or self.client_address[0] or "unknown")

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/search":
            return self.send_json(404, {"error": "not found"})
        size = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(size) or b"{}")
        except json.JSONDecodeError:
            return self.send_json(400, {"error": "expected JSON"})

        try:
            q = Query(str(body["from"]).upper()[:3], str(body["to"]).upper()[:3],
                      str(body["date"])[:10], (body.get("ret") or None))
            datetime.strptime(q.date, "%Y-%m-%d")
            if q.ret:
                datetime.strptime(q.ret, "%Y-%m-%d")
        except (KeyError, ValueError, TypeError):
            return self.send_json(400, {
                "error": "need from, to and date (YYYY-MM-DD)"})
        if not (q.origin.isalpha() and q.destination.isalpha()):
            return self.send_json(400, {"error": "airports are three letters"})

        # Which country to look from. Refused rather than silently ignored if
        # it is one we have never watched a browser come out of -- answering a
        # request for Tokyo with a page read from New York is worse than
        # saying no.
        country = str(body.get("country") or EGRESS).lower()[:2]
        if country not in EGRESS_OK:
            return self.send_json(400, {
                "error": f"Cannot browse from {country!r}. Verified exits: "
                         + ", ".join(sorted(EGRESS_OK))})

        nearby = bool(body.get("nearby", True)) and ALLOW_NEARBY
        # A stored answer is the right default and the wrong one when somebody
        # is about to book: fares move, and asking again is the point of having
        # browsers. The result still goes back into the cache for the next
        # person, so one person refreshing does not cost the next one a wait.
        fresh = bool(body.get("fresh"))
        job_id = uuid.uuid4().hex[:12]
        base = {"id": job_id, "phase": "queued", "trip": None, "error": None,
                "searched": 0, "answered": 0, "seconds": 0, "cached_age": 0,
                "asked": {"from": q.origin, "to": q.destination,
                          "date": q.date, "ret": q.ret, "nearby": nearby,
                          "country": country}}

        stored, age = (None, 0.0) if fresh else recall(
            DB_CONN, cache_key(q, nearby, country))
        if stored:
            built = tripslib.build([stored])
            base.update(phase="done", trip=built[0] if built else None,
                        searched=len(stored["results"]),
                        answered=sum(1 for r in stored["results"] if r.get("ok")),
                        seconds=stored.get("seconds", 0), cached_age=round(age))
            with JOBS_LOCK:
                JOBS[job_id] = base
            return self.send_json(200, {**base, "from_cache": True})

        refused = budget(self.caller(), fresh)
        if refused:
            return self.send_json(429, {**base, "phase": "failed",
                                        "error": refused, "from_cache": False})

        with JOBS_LOCK:
            JOBS[job_id] = base
        asyncio.run_coroutine_threadsafe(
            hunt(job_id, q, nearby, GATE, DB_CONN, country), LOOP)
        return self.send_json(202, {**base, "from_cache": False})


def spin(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int,
                    default=int(os.environ.get("PORT", 8080)))
    ap.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"),
                    help="0.0.0.0 to accept connections from outside")
    ap.add_argument("--browsers", type=int, default=16,
                    help="most browsers at once; keep under the plan's limit")
    args = ap.parse_args()

    load_env()
    if not os.environ.get("SOLARI_API_KEY"):
        raise SystemExit("SOLARI_API_KEY missing. Copy .env.example to .env.")

    from solari_browser import Solari

    global SOLARI, GATE, LOOP, DB_CONN
    DB_CONN = connect()
    LOOP = asyncio.new_event_loop()
    threading.Thread(target=spin, args=(LOOP,), daemon=True).start()
    SOLARI = Solari(api_key=os.environ["SOLARI_API_KEY"])
    GATE = asyncio.Semaphore(args.browsers)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Fare Board on http://localhost:{args.port}")
    print(f"  {len(QUICK_SITES)} sites a search, {args.browsers} browsers at "
          f"once, {CACHE_TTL // 60} minute cache")
    print(f"  limits: {PER_IP_HOUR} searches an hour per visitor, "
          f"{FRESH_PER_IP_HOUR} of them re-checks, {GLOBAL_PER_DAY} a day")
    print(f"  nearby airports: {'on' if ALLOW_NEARBY else 'off'} "
          f"({'~6' if ALLOW_NEARBY else '~1.2'} browser-minutes a search)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")


if __name__ == "__main__":
    main()
