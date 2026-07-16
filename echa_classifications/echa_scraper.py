#!/usr/bin/env python3
"""Scrape harmonised + industry (C&L) classifications from ECHA CHEM for a CAS list.

ECHA CHEM (https://chem.echa.europa.eu/) has no public API and rejects plain HTTP
clients, so this tool drives a real Chromium browser via Playwright. Rather than
parsing the rendered HTML (fragile), it primarily *captures the JSON responses the
portal's own JavaScript fetches* while navigating, and mines classification fields
out of them. Raw captures can be dumped per CAS (--dump-dir) so extraction can be
tightened against the real payloads if a field comes out wrong.

Flow per CAS number:
  1. Open the substance search, type the CAS, submit.
  2. Pick the matching substance from the results (link + captured search JSON).
  3. Visit the substance's "harmonised" section and its C&L Inventory section.
  4. Mine hazard classes, H-statements, signal words, pictograms, notifier counts
     etc. from every JSON payload captured in each section.
  5. Append a row to the output CSV (written incrementally; --resume skips CAS
     numbers already done).

Setup (on a machine with normal internet access):
    pip install playwright
    playwright install chromium
    python echa_scraper.py --cas-list components.csv --output scraped.csv

Be polite: this hits ECHA's public site. Keep the default --delay (3s) or raise it,
and prefer running lists of hundreds, not hundreds of thousands.
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from collections import OrderedDict

from echa_classifications import canonical_cas, load_cas_list

BASE = "https://chem.echa.europa.eu"
SEARCH_URL = BASE + "/substance-search"

# ECHA infocard identifiers look like "100.000.621".
ECHA_ID_RE = re.compile(r"\b(100\.\d{3}\.\d{3})\b")

# Candidate substance-section paths for the C&L Inventory (tried in order after any
# link found on the substance page itself). The harmonised path is known-good.
HARMONISED_PATH = "harmonised"
CL_PATH_CANDIDATES = ["cl-inventory", "classification-labelling", "clp", "cl"]

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


# --------------------------------------------------------------------------------------
# JSON mining (pure functions — unit-tested offline)
# --------------------------------------------------------------------------------------

def _norm_key(key):
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


# Output field -> key substrings that identify it in captured JSON (normalised form).
MINE_FIELDS = OrderedDict([
    ("name", ["substancename", "publicname", "chemicalname"]),
    ("ec_number", ["ecnumber", "eclistnumber"]),
    ("index_number", ["indexnumber"]),
    ("hazard_class", ["hazardclass", "hazardcategory"]),
    ("hazard_statements", ["hazardstatement"]),
    ("signal_word", ["signalword"]),
    ("pictograms", ["pictogram"]),
    ("notifiers", ["notifier"]),
    ("conc_limits_m_factors", ["conclimit", "concentrationlimit", "mfactor", "specificconc"]),
    ("notes", ["notes"]),
    ("classification", ["classification"]),
])


def _value_strings(value):
    """Flatten a JSON value into displayable strings."""
    out = []
    if value is None:
        return out
    if isinstance(value, (str, int, float, bool)):
        s = str(value).strip()
        if s and s.lower() not in ("none", "null", "true", "false"):
            out.append(s)
        elif s.lower() in ("true", "false"):
            out.append(s.lower())
        return out
    if isinstance(value, list):
        for item in value:
            out.extend(_value_strings(item))
        return out
    if isinstance(value, dict):
        # Prefer human-readable subkeys when a dict is itself the value.
        for pref in ("value", "code", "description", "name", "label", "text"):
            if pref in value:
                out.extend(_value_strings(value[pref]))
        if not out:
            for v in value.values():
                out.extend(_value_strings(v))
        return out
    return out


def mine_payloads(payloads):
    """Extract classification-ish fields from a list of parsed JSON payloads.

    Returns {field: "v1; v2; ..."} with distinct values in first-seen order.
    """
    found = OrderedDict((f, []) for f in MINE_FIELDS)

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                nk = _norm_key(key)
                for field, needles in MINE_FIELDS.items():
                    if any(n in nk for n in needles):
                        for s in _value_strings(value):
                            if s not in found[field]:
                                found[field].append(s)
                        break
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for payload in payloads:
        walk(payload)
    return OrderedDict((f, "; ".join(v)) for f, v in found.items() if v)


def payload_mentions_cas(payload, cas):
    """True if a JSON payload contains the CAS number anywhere."""
    try:
        blob = json.dumps(payload)
    except (TypeError, ValueError):
        return False
    return cas in blob


def pick_echa_id(hrefs, payloads, cas):
    """Choose the substance's ECHA infocard id.

    Prefer an id found in a captured payload that also mentions the CAS (so a search
    returning several hits picks the right one); otherwise the first id in the page's
    result links; otherwise any id seen in payloads.
    """
    for payload in payloads:
        if payload_mentions_cas(payload, cas):
            m = ECHA_ID_RE.search(json.dumps(payload))
            if m:
                return m.group(1)
    for href in hrefs:
        m = ECHA_ID_RE.search(href or "")
        if m:
            return m.group(1)
    for payload in payloads:
        m = ECHA_ID_RE.search(json.dumps(payload))
        if m:
            return m.group(1)
    return None


# --------------------------------------------------------------------------------------
# Browser driving
# --------------------------------------------------------------------------------------

class Capture:
    """Collects JSON responses on a page, bucketed by a named phase."""

    def __init__(self, page):
        self.page = page
        self.phase = "init"
        self.buckets = {}
        page.on("response", self._on_response)

    def set_phase(self, phase):
        self.phase = phase
        self.buckets.setdefault(phase, [])

    def reset(self):
        """Clear everything captured so far (call between CAS numbers)."""
        self.buckets = {}
        self.phase = "init"

    def _on_response(self, response):
        try:
            ctype = response.headers.get("content-type", "")
            if "json" not in ctype:
                return
            body = response.json()
        except Exception:
            return
        self.buckets.setdefault(self.phase, []).append(
            {"url": response.url, "json": body}
        )

    def payloads(self, phase):
        return [entry["json"] for entry in self.buckets.get(phase, [])]


def dismiss_cookie_banner(page):
    """Best-effort acceptance of a cookie/consent banner, if one appears."""
    for selector in (
        "button:has-text('Accept all')",
        "button:has-text('Accept')",
        "button:has-text('I agree')",
        "[id*='cookie'] button",
    ):
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=1500):
                btn.click(timeout=2000)
                page.wait_for_timeout(500)
                return
        except Exception:
            continue


def settle(page, timeout_ms):
    """Wait for the SPA to finish its network activity, tolerantly."""
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception:
        pass
    page.wait_for_timeout(750)


def run_search(page, cas, timeout_ms):
    """Open the search page and search for the CAS via the page's own search box."""
    page.goto(SEARCH_URL, timeout=timeout_ms)
    settle(page, timeout_ms)
    dismiss_cookie_banner(page)
    box = None
    for selector in ("input[type='search']", "input[type='text']", "input"):
        loc = page.locator(selector).first
        try:
            if loc.is_visible(timeout=2000):
                box = loc
                break
        except Exception:
            continue
    if box is None:
        raise RuntimeError("could not find the search input on {}".format(SEARCH_URL))
    box.fill(cas)
    box.press("Enter")
    settle(page, timeout_ms)


def collect_result_hrefs(page):
    hrefs = []
    try:
        for a in page.locator("a[href*='100.']").all():
            href = a.get_attribute("href")
            if href:
                hrefs.append(href)
    except Exception:
        pass
    return hrefs


def visit_section(page, echa_id, path, timeout_ms):
    """Navigate to a substance section; True if it loaded something real."""
    url = "{}/{}/{}".format(BASE, echa_id, path)
    try:
        resp = page.goto(url, timeout=timeout_ms)
    except Exception:
        return False
    settle(page, timeout_ms)
    if resp is not None and resp.status >= 400:
        return False
    try:
        text = page.inner_text("body", timeout=3000)
    except Exception:
        return True
    lowered = text.lower()
    return not ("page not found" in lowered or "404" in lowered[:400])


def find_cl_link(page):
    """Look on the current substance page for a link into its C&L section."""
    try:
        for a in page.locator("a").all():
            label = ((a.inner_text() or "") + " " + (a.get_attribute("href") or "")).lower()
            if "classification" in label or "c&l" in label or "cl-inventory" in label:
                href = a.get_attribute("href")
                if href:
                    return href
    except Exception:
        pass
    return None


def scrape_one(page, capture, cas, timeout_ms, dump_dir):
    """Scrape one CAS number. Returns an OrderedDict result row (without passthrough)."""
    row = OrderedDict()
    row["cas_number"] = cas

    capture.reset()  # payloads from a previous CAS must not leak into this row
    capture.set_phase("search")
    run_search(page, cas, timeout_ms)
    hrefs = collect_result_hrefs(page)
    echa_id = pick_echa_id(hrefs, capture.payloads("search"), cas)
    row["echa_id"] = echa_id or ""
    if not echa_id:
        row["status"] = "not-found"
        return row

    # Substance overview (also lets us find the portal's own C&L link).
    capture.set_phase("overview")
    page.goto("{}/{}".format(BASE, echa_id), timeout=timeout_ms)
    settle(page, timeout_ms)
    cl_link = find_cl_link(page)

    # Harmonised section.
    capture.set_phase("harmonised")
    if visit_section(page, echa_id, HARMONISED_PATH, timeout_ms):
        mined = mine_payloads(capture.payloads("harmonised"))
        for field, value in mined.items():
            row["harmonised_" + field] = value

    # C&L Inventory section: the link found on the page first, then candidates.
    capture.set_phase("industry")
    loaded = False
    if cl_link:
        try:
            page.goto(cl_link if cl_link.startswith("http") else BASE + cl_link,
                      timeout=timeout_ms)
            settle(page, timeout_ms)
            loaded = True
        except Exception:
            loaded = False
    if not loaded:
        for path in CL_PATH_CANDIDATES:
            if visit_section(page, echa_id, path, timeout_ms):
                loaded = True
                break
    if loaded:
        mined = mine_payloads(capture.payloads("industry"))
        for field, value in mined.items():
            row["industry_" + field] = value

    got_any = any(k.startswith(("harmonised_", "industry_")) for k in row)
    row["status"] = "ok" if got_any else "no-data-extracted"

    if dump_dir:
        os.makedirs(dump_dir, exist_ok=True)
        dump = {
            "cas": cas,
            "echa_id": echa_id,
            "result_hrefs": hrefs,
            "captures": capture.buckets,
        }
        path = os.path.join(dump_dir, "{}.json".format(cas.replace("/", "_")))
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(dump, fh, indent=1, default=str)
        try:  # page text snapshot helps debugging when JSON mining finds nothing
            with open(os.path.join(dump_dir, "{}.txt".format(cas)), "w", encoding="utf-8") as fh:
                fh.write(page.inner_text("body"))
        except Exception:
            pass

    return row


# --------------------------------------------------------------------------------------
# CSV output (incremental, resumable)
# --------------------------------------------------------------------------------------

# Stable superset of columns so every row aligns even though mining is best-effort.
BASE_COLUMNS = ["cas_input", "cas_number", "echa_id", "status", "error"]
MINED_COLUMNS = (["harmonised_" + f for f in MINE_FIELDS]
                 + ["industry_" + f for f in MINE_FIELDS])


def load_done(path):
    done = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                if row.get("status") == "ok" and row.get("cas_number"):
                    done.add(row["cas_number"])
    return done


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Scrape ECHA CHEM classifications for a list of CAS numbers "
                    "(drives a real Chromium via Playwright).",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--cas", nargs="+", metavar="CAS", help="CAS numbers to scrape.")
    ap.add_argument("--cas-list", metavar="FILE",
                    help=".txt/.csv/.xlsx of CAS numbers; extra spreadsheet columns "
                         "(component names etc.) are carried through to the output.")
    ap.add_argument("--output", "-o", default="echa_scraped.csv", metavar="FILE")
    ap.add_argument("--dump-dir", metavar="DIR",
                    help="Save raw captured JSON + page text per CAS (for debugging "
                         "extraction against the real site).")
    ap.add_argument("--delay", type=float, default=3.0, metavar="SECONDS",
                    help="Pause between CAS numbers (default 3s — be polite).")
    ap.add_argument("--timeout", type=float, default=30.0, metavar="SECONDS",
                    help="Per-navigation timeout (default 30s).")
    ap.add_argument("--retries", type=int, default=2,
                    help="Attempts per CAS before recording an error (default 2).")
    ap.add_argument("--headed", action="store_true",
                    help="Show the browser window (useful if bot-protection blocks "
                         "headless mode, and for watching what it does).")
    ap.add_argument("--browser-path", metavar="PATH",
                    help="Explicit Chromium executable, if Playwright's default "
                         "download isn't installed.")
    ap.add_argument("--resume", action="store_true",
                    help="Skip CAS numbers already marked ok in the output file.")
    ap.add_argument("--limit", type=int, metavar="N",
                    help="Stop after N CAS numbers (for a trial run).")
    args = ap.parse_args(argv if argv is not None else sys.argv[1:])

    if not args.cas and not args.cas_list:
        raise SystemExit("ERROR: provide CAS numbers via --cas or --cas-list.")

    items = []
    if args.cas:
        items.extend((c, OrderedDict()) for c in args.cas)
    if args.cas_list:
        items.extend(load_cas_list(args.cas_list))
    if not items:
        raise SystemExit("ERROR: no CAS numbers found in the provided input.")

    passthrough_columns = []
    for _, pt in items:
        for key in pt:
            if key not in passthrough_columns:
                passthrough_columns.append(key)
    columns = passthrough_columns + BASE_COLUMNS + MINED_COLUMNS

    done = load_done(args.output) if args.resume else set()
    mode = "a" if (args.resume and os.path.exists(args.output)) else "w"

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit("ERROR: Playwright is not installed. Run:\n"
                         "    pip install playwright && playwright install chromium")

    timeout_ms = int(args.timeout * 1000)
    processed = 0

    with sync_playwright() as pw, \
            open(args.output, mode, newline="", encoding="utf-8-sig") as out:
        writer = csv.DictWriter(out, fieldnames=columns, extrasaction="ignore")
        if mode == "w":
            writer.writeheader()

        launch_kwargs = {"headless": not args.headed}
        if args.browser_path:
            launch_kwargs["executable_path"] = args.browser_path
        browser = pw.chromium.launch(**launch_kwargs)
        context = browser.new_context(user_agent=USER_AGENT,
                                      viewport={"width": 1400, "height": 900},
                                      locale="en-GB")
        page = context.new_page()
        capture = Capture(page)

        for raw, passthrough in items:
            if args.limit is not None and processed >= args.limit:
                break
            cas = canonical_cas(raw)
            row = OrderedDict((c, passthrough.get(c, "")) for c in passthrough_columns)
            row["cas_input"] = raw
            row["cas_number"] = cas
            if not cas:
                row["status"] = "no-cas-in-input"
            elif cas in done:
                print("skip (already done): {}".format(cas), file=sys.stderr)
                continue
            else:
                last_err = None
                for attempt in range(1, args.retries + 1):
                    try:
                        result = scrape_one(page, capture, cas, timeout_ms, args.dump_dir)
                        row.update(result)
                        last_err = None
                        break
                    except Exception as e:  # keep going; one CAS must not kill the run
                        last_err = "{}: {}".format(type(e).__name__, e)
                        print("  attempt {}/{} failed for {}: {}".format(
                            attempt, args.retries, cas, last_err), file=sys.stderr)
                        time.sleep(args.delay)
                if last_err:
                    row["status"] = "error"
                    row["error"] = last_err
                print("{:<14} -> {}".format(cas, row.get("status", "?")), file=sys.stderr)

            writer.writerow(row)
            out.flush()
            processed += 1
            time.sleep(args.delay)

        browser.close()

    print("\nDone: {} CAS processed -> {}".format(processed, args.output), file=sys.stderr)
    if args.dump_dir:
        print("Raw captures in {} — if a field is wrong/missing, inspect (or share) the "
              "dump for one CAS so extraction can be tightened.".format(args.dump_dir),
              file=sys.stderr)


if __name__ == "__main__":
    main()
