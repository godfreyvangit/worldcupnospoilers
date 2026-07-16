"""End-to-end and unit tests for echa_classifications.py (stdlib unittest, no network)."""

import csv
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import echa_classifications as ec  # noqa: E402

FIX = os.path.join(HERE, "fixtures")
HARMONISED = os.path.join(FIX, "harmonised_sample.csv")
INDUSTRY = os.path.join(FIX, "industry_sample.csv")
CAS_LIST = os.path.join(FIX, "cas_list.txt")


class CasHelpers(unittest.TestCase):
    def test_canonical_strips_leading_zeros(self):
        self.assertEqual(ec.canonical_cas("0000050-00-0"), "50-00-0")
        self.assertEqual(ec.canonical_cas("  71-43-2  "), "71-43-2")
        self.assertEqual(ec.canonical_cas("CAS 71-43-2 (benzene)"), "71-43-2")

    def test_canonical_empty_when_absent(self):
        self.assertEqual(ec.canonical_cas("not a cas"), "")
        self.assertEqual(ec.canonical_cas(None), "")

    def test_all_cas_multiple(self):
        self.assertEqual(ec.all_cas("71-43-2, 50-00-0; 71-43-2"), ["71-43-2", "50-00-0"])

    def test_checksum(self):
        self.assertTrue(ec.cas_checksum_ok("71-43-2"))
        self.assertTrue(ec.cas_checksum_ok("50-00-0"))
        self.assertFalse(ec.cas_checksum_ok("71-43-3"))
        self.assertIsNone(ec.cas_checksum_ok("nope"))


class HeaderDetection(unittest.TestCase):
    def test_skips_title_rows(self):
        rows = ec.read_rows(HARMONISED)
        # Two title rows precede the real header in the fixture.
        self.assertEqual(ec.detect_header_row(rows), 2)

    def test_delimiter_sniffing(self):
        rows = ec.read_rows(INDUSTRY)  # semicolon-delimited
        self.assertEqual(rows[0][0], "Substance name")
        self.assertEqual(rows[0][2], "CAS no")


class HarmonisedIndexing(unittest.TestCase):
    def setUp(self):
        self.idx = ec.HarmonisedIndex(HARMONISED)

    def test_columns_mapped(self):
        self.assertEqual(self.idx.mapping["cas"], "CAS No")
        self.assertEqual(self.idx.mapping["hazard_class_category"], "Hazard Class and Category Code(s)")
        # First (classification) hazard-statement column, not the labelling one.
        self.assertEqual(self.idx.mapping["hazard_statements"], "Hazard statement code(s)")

    def test_lookup(self):
        rec = self.idx.get("71-43-2")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["name"], "benzene")
        self.assertIn("Carc. 1A", rec["hazard_class_category"])
        self.assertIn("H350", rec["hazard_statements"])
        self.assertIsNone(self.idx.get("64-17-5"))  # ethanol has no harmonised entry


class IndustryIndexing(unittest.TestCase):
    def setUp(self):
        self.idx = ec.IndustryIndex(INDUSTRY)

    def test_classification_columns_detected(self):
        self.assertIn("industry_Hazard Class and Category", self.idx.out_columns)
        self.assertIn("industry_Hazard statements", self.idx.out_columns)
        self.assertIn("industry_Number of notifiers", self.idx.out_columns)

    def test_lookup_and_dedup(self):
        rec = self.idx.get("71-43-2")
        self.assertIsNotNone(rec)
        # First row wins over the later duplicate notification-group row.
        self.assertEqual(rec["industry_Number of notifiers"], "1875")
        self.assertIn("71-43-2", self.idx.duplicate_cas)


class EndToEnd(unittest.TestCase):
    def test_full_run(self):
        out = os.path.join(tempfile.mkdtemp(), "out.csv")
        ec.main([
            "--cas-list", CAS_LIST,
            "--harmonised", HARMONISED,
            "--industry", INDUSTRY,
            "--output", out,
        ])
        with open(out, encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        by_input = {r["cas_input"]: r for r in rows}

        # Six input lines (one is a comment and excluded by the loader).
        self.assertEqual(len(rows), 6)

        benzene = by_input["71-43-2"]
        self.assertEqual(benzene["cas_number"], "71-43-2")
        self.assertEqual(benzene["cas_valid"], "yes")
        self.assertEqual(benzene["harmonised_found"], "yes")
        self.assertEqual(benzene["industry_found"], "yes")
        self.assertIn("H350", benzene["harmonised_hazard_statements"])
        self.assertEqual(benzene["industry_Number of notifiers"], "1875")

        formaldehyde = by_input["0000050-00-0"]
        self.assertEqual(formaldehyde["cas_number"], "50-00-0")
        self.assertEqual(formaldehyde["harmonised_found"], "yes")

        ethanol = by_input["64-17-5"]
        self.assertEqual(ethanol["harmonised_found"], "no")
        self.assertEqual(ethanol["industry_found"], "yes")

        missing = by_input["12345-99-9"]
        self.assertEqual(missing["harmonised_found"], "no")
        self.assertEqual(missing["industry_found"], "no")

        bad = by_input["71-43-3"]
        self.assertEqual(bad["cas_valid"], "no")

    def test_components_passthrough(self):
        # A "Component, CAS, Supplier" spreadsheet keeps its own columns in the output.
        out = os.path.join(tempfile.mkdtemp(), "out.csv")
        ec.main([
            "--cas-list", os.path.join(FIX, "components.csv"),
            "--harmonised", HARMONISED,
            "--industry", INDUSTRY,
            "--output", out,
        ])
        with open(out, encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        header = rows[0].keys()
        self.assertIn("Component", header)
        self.assertIn("Supplier", header)
        by_comp = {r["Component"]: r for r in rows}
        self.assertEqual(by_comp["Benzene solvent"]["cas_number"], "71-43-2")
        self.assertEqual(by_comp["Benzene solvent"]["harmonised_found"], "yes")
        self.assertEqual(by_comp["Benzene solvent"]["Supplier"], "Acme")
        self.assertEqual(by_comp["Ethanol denatured"]["industry_found"], "yes")

    def test_harmonised_only(self):
        out = os.path.join(tempfile.mkdtemp(), "out.csv")
        ec.main(["--cas", "71-43-2", "--harmonised", HARMONISED, "--output", out])
        with open(out, encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["harmonised_found"], "yes")
        self.assertNotIn("industry_found", rows[0])


class XlsxReading(unittest.TestCase):
    def test_reads_xlsx(self):
        try:
            from openpyxl import Workbook
        except ImportError:
            self.skipTest("openpyxl not installed")
        # Round-trip the CSV fixture into a real .xlsx and index it.
        ws_path = os.path.join(tempfile.mkdtemp(), "harmonised.xlsx")
        wb = Workbook()
        ws = wb.active
        with open(HARMONISED, encoding="utf-8-sig") as fh:
            for row in csv.reader(fh):
                ws.append(row)
        wb.save(ws_path)
        idx = ec.HarmonisedIndex(ws_path)
        rec = idx.get("71-43-2")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["name"], "benzene")


if __name__ == "__main__":
    unittest.main(verbosity=2)
