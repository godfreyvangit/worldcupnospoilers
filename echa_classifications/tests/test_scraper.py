"""Tests for echa_scraper.py.

Unit tests cover the pure JSON-mining functions. The end-to-end test spins up a local
mock of an ECHA-CHEM-style SPA (search box -> JSON fetch -> substance page -> harmonised
and C&L sections that fetch JSON) and runs the real scraper against it in a real
Chromium, verifying the whole pipeline except ECHA's exact live markup. It is skipped
automatically if Playwright or a Chromium binary is unavailable.
"""

import csv
import http.server
import json
import os
import sys
import tempfile
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import echa_scraper as es  # noqa: E402


class MinePayloads(unittest.TestCase):
    def test_mines_harmonised_like_payload(self):
        payload = {
            "substanceName": "benzene",
            "ecNumber": "200-753-7",
            "harmonisedEntry": {
                "indexNumber": "601-020-00-8",
                "hazardClassAndCategory": [
                    {"code": "Flam. Liq. 2"}, {"code": "Carc. 1A"}],
                "hazardStatementCodes": ["H225", "H350"],
                "pictograms": [{"value": "GHS02"}, {"value": "GHS08"}],
                "signalWord": "Dgr",
            },
        }
        mined = es.mine_payloads([payload])
        self.assertEqual(mined["name"], "benzene")
        self.assertEqual(mined["index_number"], "601-020-00-8")
        self.assertIn("Carc. 1A", mined["hazard_class"])
        self.assertIn("H350", mined["hazard_statements"])
        self.assertIn("GHS08", mined["pictograms"])
        self.assertEqual(mined["signal_word"], "Dgr")

    def test_mines_notified_summary(self):
        payload = {
            "notifiedClassification": [
                {"hazardClass": "Flam. Liq. 2", "hazardStatement": "H225",
                 "numberOfNotifiers": 1875},
            ],
            "totalNotifiers": 2000,
        }
        mined = es.mine_payloads([payload])
        self.assertIn("1875", mined["notifiers"])
        self.assertIn("2000", mined["notifiers"])
        self.assertIn("Flam. Liq. 2", mined["hazard_class"])

    def test_dedupes_values(self):
        mined = es.mine_payloads([
            {"hazardStatement": "H225"}, {"hazardStatements": ["H225", "H319"]},
        ])
        self.assertEqual(mined["hazard_statements"], "H225; H319")


class PickEchaId(unittest.TestCase):
    def test_prefers_payload_matching_cas(self):
        payloads = [
            {"results": [{"casNumber": "50-00-0", "id": "100.000.002"}]},
            {"results": [{"casNumber": "71-43-2", "id": "100.001.939"}]},
        ]
        hrefs = ["/100.000.002"]
        self.assertEqual(es.pick_echa_id(hrefs, payloads, "71-43-2"), "100.001.939")

    def test_falls_back_to_hrefs(self):
        self.assertEqual(es.pick_echa_id(["/100.001.939"], [], "71-43-2"), "100.001.939")

    def test_none_when_nothing(self):
        self.assertIsNone(es.pick_echa_id([], [{"foo": "bar"}], "71-43-2"))


# --------------------------------------------------------------------------------------
# Mock ECHA-CHEM-style SPA for the end-to-end test
# --------------------------------------------------------------------------------------

SEARCH_PAGE = """<!doctype html><html><body>
<h1>Mock ECHA CHEM</h1>
<input type="search" id="q" placeholder="Search substances">
<div id="results"></div>
<script>
document.getElementById('q').addEventListener('keydown', function (e) {
  if (e.key !== 'Enter') return;
  fetch('/api/search?q=' + encodeURIComponent(e.target.value))
    .then(r => r.json())
    .then(d => {
      document.getElementById('results').innerHTML = d.results
        .map(r => '<a href="/' + r.echaId + '">' + r.substanceName + '</a>').join('');
    });
});
</script></body></html>"""

OVERVIEW_PAGE = """<!doctype html><html><body>
<h1>benzene</h1>
<a href="/100.001.939/cl-inventory">Classification &amp; Labelling Inventory</a>
<a href="/100.001.939/harmonised">Harmonised classification</a>
</body></html>"""

SECTION_PAGE = """<!doctype html><html><body>
<h1>Section</h1><div id="c">loading</div>
<script>
fetch('%s').then(r => r.json()).then(d => {
  document.getElementById('c').textContent = JSON.stringify(d);
});
</script></body></html>"""

API = {
    "/api/search": {"results": [
        {"substanceName": "benzene", "casNumber": "71-43-2", "echaId": "100.001.939"}]},
    "/api/harmonised": {
        "substanceName": "benzene",
        "indexNumber": "601-020-00-8",
        "hazardClassAndCategory": [{"code": "Flam. Liq. 2"}, {"code": "Carc. 1A"}],
        "hazardStatementCodes": ["H225", "H350"],
        "signalWord": "Dgr",
    },
    "/api/cl": {
        "notifiedClassification": [
            {"hazardClass": "Flam. Liq. 2", "hazardStatement": "H225"}],
        "numberOfNotifiers": 1875,
        "signalWord": "Danger",
    },
}


class MockEchaHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]
        if path.startswith("/api/"):
            body = json.dumps(API.get(path, {})).encode()
            self._send(body, "application/json")
        elif path == "/substance-search":
            self._send(SEARCH_PAGE.encode(), "text/html")
        elif path == "/100.001.939":
            self._send(OVERVIEW_PAGE.encode(), "text/html")
        elif path == "/100.001.939/harmonised":
            self._send((SECTION_PAGE % "/api/harmonised").encode(), "text/html")
        elif path == "/100.001.939/cl-inventory":
            self._send((SECTION_PAGE % "/api/cl").encode(), "text/html")
        else:
            self.send_error(404, "page not found")

    def _send(self, body, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def chromium_path():
    for candidate in ("/opt/pw-browsers/chromium", None):
        if candidate and os.path.exists(candidate):
            return candidate
    return None


class EndToEndMockSite(unittest.TestCase):
    def test_scrape_against_mock_spa(self):
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
        except ImportError:
            self.skipTest("playwright not installed")

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), MockEchaHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        old_base, old_search = es.BASE, es.SEARCH_URL
        es.BASE = "http://127.0.0.1:{}".format(port)
        es.SEARCH_URL = es.BASE + "/substance-search"
        out = os.path.join(tempfile.mkdtemp(), "scraped.csv")
        dump_dir = os.path.join(tempfile.mkdtemp(), "dumps")
        argv = ["--cas", "71-43-2", "--output", out, "--dump-dir", dump_dir,
                "--delay", "0.2", "--timeout", "15"]
        bp = chromium_path()
        if bp:
            argv += ["--browser-path", bp]
        try:
            es.main(argv)
        except SystemExit as e:
            self.fail("scraper exited: {}".format(e))
        finally:
            es.BASE, es.SEARCH_URL = old_base, old_search
            server.shutdown()

        with open(out, encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["cas_number"], "71-43-2")
        self.assertEqual(row["echa_id"], "100.001.939")
        self.assertEqual(row["status"], "ok")
        self.assertIn("Carc. 1A", row["harmonised_hazard_class"])
        self.assertIn("H350", row["harmonised_hazard_statements"])
        self.assertIn("1875", row["industry_notifiers"])
        self.assertIn("Flam. Liq. 2", row["industry_hazard_class"])
        # Raw captures were dumped for debugging.
        self.assertTrue(os.path.exists(os.path.join(dump_dir, "71-43-2.json")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
