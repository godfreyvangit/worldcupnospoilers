# ECHA classification extractor

Extract **harmonised** and **industry (self-/notified)** hazard classifications for a
list of CAS numbers, and merge them into one CSV.

The two classification types come from two different ECHA sources, and — importantly —
there is **no public API** for the industry data. As of 20 May 2025 the old C&L Inventory
database was retired and folded into the [ECHA CHEM](https://chem.echa.europa.eu/) portal,
which is a JavaScript app behind bot-protection (non-browser requests get an HTTP 403). So
rather than scrape a fragile, undocumented endpoint, this tool works from **two files you
download** and does the parsing, CAS-matching and merging for you:

| Column group in the output | Source file you provide | Where to get it |
|---|---|---|
| `harmonised_*` | **Annex VI, Table 3 to CLP** (Excel) — the legally-binding EU-harmonised classifications (~4,400 substances) | https://echa.europa.eu/information-on-chemicals/annex-vi-to-clp → download the Table 3 Excel |
| `industry_*` | An **export from the ECHA CHEM C&L Inventory** — the classifications companies submitted in CLP notifications / REACH registrations, aggregated per substance | https://chem.echa.europa.eu/ → search → **Export** (handles up to 9,999 results per export) |

You need at least one of the two files. Provide both to get the full merged picture.

> **Why not "all CAS numbers on the website" automatically?** The full inventory is
> ~350,000 substances behind the bot-protected portal — not something to scrape politely.
> The recommended workflow is to give the tool the CAS numbers you care about (or the CAS
> column of an ECHA CHEM export) and let it match against the two source files.

## Install

Pure Python 3.7+. The only dependency is [`openpyxl`](https://pypi.org/project/openpyxl/),
and **only if** your source files are `.xlsx`:

```bash
pip install -r requirements.txt      # installs openpyxl
```

If you'd rather not install anything, open each `.xlsx` in Excel/LibreOffice and
**Save As CSV** — the tool reads `.csv` with no dependencies.

## Get the source files

**Harmonised (Annex VI, Table 3):**
1. Go to https://echa.europa.eu/information-on-chemicals/annex-vi-to-clp
2. Download the Excel table of harmonised entries (ECHA publishes an "unofficial" convenience Excel).

**Industry (ECHA CHEM C&L export):**
1. Go to https://chem.echa.europa.eu/ and open the Classification & Labelling Inventory search.
2. Search / filter for the substances you want (e.g. paste or search your CAS numbers), or
   pull a broad set — the export supports up to 9,999 rows at a time.
3. Use the **Export** button to download the results (Excel).

## Usage

```bash
# CAS numbers from a file, both sources, merged to CSV
python echa_classifications.py \
    --cas-list my_cas.txt \
    --harmonised annex_vi_table3.xlsx \
    --industry echa_chem_export.xlsx \
    --output results.csv

# A few CAS numbers on the command line, harmonised only
python echa_classifications.py --cas 71-43-2 50-00-0 --harmonised annex_vi_table3.xlsx

# Industry only
python echa_classifications.py --cas-list my_cas.txt --industry echa_chem_export.xlsx
```

**CAS input** (`--cas` / `--cas-list`):
- `--cas 71-43-2 50-00-0 ...` — CAS numbers directly.
- `--cas-list FILE` — a `.txt` (one CAS per line; `#` comments allowed) **or** a
  `.csv`/`.xlsx` whose CAS column is auto-detected.
- **Component lists carry through.** If `--cas-list` is a spreadsheet like
  `Component, CAS Number, Supplier`, the CAS column is detected automatically and **all your
  other columns (component name, supplier, …) are kept as the leading columns of the output**,
  so each result row stays tied to its component.
- CAS numbers are normalised (`0000050-00-0` → `50-00-0`) and check-digit–validated;
  suspected typos are flagged in the `cas_valid` column but still looked up.

### Column auto-detection and overrides

ECHA changes its column headers between releases, so the tool **auto-detects** the CAS,
name, EC and classification columns in each file and **prints the mapping it inferred** to
the screen (stderr). Check that mapping — if a column was detected wrongly, override it:

```bash
--harmonised-cas-col N        # 0-based index of the CAS column in the harmonised file
--industry-cas-col N          # 0-based index of the CAS column in the industry export
--industry-cols "Hazard Class and Category,Hazard statements,Number of notifiers"
                              # exact header names (or 0-based indexes) to treat as the
                              # industry classification columns, instead of auto-detecting
```

## Output

A UTF-8 CSV (Excel-friendly, one row per input CAS). Columns:

- `cas_input`, `cas_number` (canonical), `cas_valid` (`yes`/`no`/`unknown`), `note`
- `harmonised_found` + `harmonised_index_no`, `harmonised_name`, `harmonised_ec_number`,
  `harmonised_hazard_class_and_category`, `harmonised_hazard_statements`,
  `harmonised_pictogram_signal_word`, `harmonised_spec_conc_limits_m_factors`,
  `harmonised_notes` *(present only if `--harmonised` was given)*
- `industry_found` + one `industry_<column>` per classification column found in your export
  *(present only if `--industry` was given)*

A run summary (how many matched each source, how many failed CAS checksum, etc.) is printed
at the end.

## Notes and caveats

- **Harmonised** classification (Annex VI, Table 3) is the legally-binding EU classification;
  only ~4,400 substances have one, so most CAS numbers will show `harmonised_found = no` —
  that's expected, not an error.
- **Industry** classification is aggregated from company notifications; a substance can have
  several differing self-classifications. The ECHA CHEM export gives a per-substance summary.
  If your export has more than one row for a CAS, the tool keeps the first and tells you.
- This tool does not access ECHA over the network — it only reads the files you download,
  so it can't be broken by ECHA's bot-protection and won't hammer their servers.

## Fully automated option: the scraper (`echa_scraper.py`)

If you'd rather not do the manual export, `echa_scraper.py` runs your CAS list against
the ECHA CHEM website directly by driving a **real Chromium browser** (Playwright) — the
only approach with a realistic chance against the portal's bot-protection, since ECHA
offers no public API.

Instead of parsing the rendered HTML (fragile), it **captures the JSON responses the
portal's own JavaScript fetches** while navigating each substance's search result,
harmonised section, and C&L Inventory section, and mines the classification fields out
of those payloads. It writes the CSV incrementally, supports `--resume`, and can dump
the raw captures per CAS for debugging.

```bash
pip install playwright
playwright install chromium

# trial run: first 3 substances, visible browser, raw dumps kept
python echa_scraper.py --cas-list components.csv --limit 3 --headed --dump-dir dumps -o scraped.csv

# full run
python echa_scraper.py --cas-list components.csv -o scraped.csv --resume
```

Useful flags: `--delay` (default 3 s between substances — stay polite), `--timeout`,
`--retries`, `--headed` (show the browser; also try this if headless gets blocked),
`--limit N` (trial run), `--resume` (skip CAS already scraped), `--dump-dir DIR`.

**Honest caveats:**
- This was developed and end-to-end tested against a *local mock* of an ECHA-CHEM-style
  site (see `tests/test_scraper.py`) because the development environment cannot reach
  ECHA. The navigation heuristics (search box, result links, section paths) are
  best-effort guesses at the live portal — expect to calibrate on first run.
- **First-run protocol:** run with `--limit 3 --headed --dump-dir dumps`. If a column is
  empty or wrong, look at `dumps/<cas>.json` (the raw JSON the portal returned) — the
  data is almost certainly in there, and the mining patterns in `MINE_FIELDS` /
  navigation constants at the top of the file are the knobs to adjust.
- Scraping can break whenever ECHA changes the portal. For anything compliance-critical,
  cross-check against the authoritative Annex VI table / the portal itself.
- Be polite: keep the default delay, run lists of hundreds (not the whole inventory),
  and prefer the export workflow when it's practical.

The scraper's output is one row per CAS with `harmonised_*` and `industry_*` columns
(plus your component-list columns carried through), so it plays the same role as the
merge tool's output.

## Tests

```bash
python tests/test_echa_classifications.py   # merge tool (offline fixtures)
python tests/test_scraper.py                # scraper: unit tests + mock-site e2e
```

The merge-tool tests run offline against small fixtures under `tests/fixtures/` that
mimic the real files' quirks (title rows above the header, duplicate "Hazard statement
code(s)" columns, semicolon-delimited European CSV, leading-zero CAS numbers). The
scraper test spins up a local mock ECHA-CHEM-style site and drives the full scraper
against it in a real Chromium (skipped if Playwright isn't installed).
