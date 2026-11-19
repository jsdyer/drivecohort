# Drive Cohort

Look up an exact disk model, inspect the quarterly failures and exposure behind its annualized failure rate, and compare readings from two local SMART reports. [Open Drive Cohort](https://coolcode.ca/drivecohort/)

<!-- coolcode:guide -->
Look up ST12000NM0007 and compare Q1 and Q2 2025. Backblaze recorded 24 failures across 92,483 drive-days in Q1 and nine across 91,801 in Q2. Bring two smartctl JSON files from the same disk to see what changed on your own device.
<!-- /coolcode:guide -->

## Fleet records

The launch edition covers 34 exact models and 188 model-quarter observations from January 1, 2025 through June 30, 2026. Choose a quarter to see the published annualized failure rate (AFR), drive-days, failures and count at quarter end. Each table link opens the original Backblaze chart or HTML table. The data panel shows the source period, retrieval date and coverage independently. Missing models and missing quarters are marked explicitly. The comparisons retain variants such as MG08ACA16TE and MG08ACA16TEY.

Backblaze counts one drive-day per observed drive per day. AFR is failures divided by drive-days, multiplied by 365 and expressed as a percentage. The published quarterly tables cover qualifying production models. Fleet size, operating conditions and age can change between periods. The data describe fleet experience and cannot establish an individual disk’s chance of imminent failure.

Backblaze supplies the data. Its reuse terms require attribution, assign responsibility to anyone using the data, permit sale of derivative works, and prohibit selling the data itself. [Source data, methodology, and terms](https://www.backblaze.com/cloud-storage/resources/hard-drive-test-data)

## Local report comparison

Save a JSON report using the appropriate smartctl device path, for example `smartctl -a -j /dev/sda > earlier.json`. Select that file and, optionally, a second report. The page compares available power-on time, temperature, power cycles, selected ATA raw attributes, and selected NVMe fields. A dash means that a reading was absent. Vendor-specific ATA raw units and counter resets can complicate interpretation.

The browser matches the complete model after normalizing capitalization, whitespace and an optional separate manufacturer name. Device suffixes are preserved. Two reports with different models or different available serial numbers cannot generate a same-disk change. If either serial is missing, the page asks you to confirm the device identity. The interface never displays serials. It reads local files in memory, sends no report content to a server and stores nothing across page loads. Clear reports releases the parsed readings.

## Source updates

The four 2025 source tables were published as images. Their CSV transcriptions live in `sources/`. The manifest includes the official chart URLs and SHA-256 digests. Beginning in 2026, the importer reads the quarterly HTML table in its original section and checks the row sums against official totals. It validates the displayed AFR against each numerator and denominator. The first-day-of-period and last-day-of-period values describe the quarter. The retrieval date records the UTC date of a successful check.

`python3 scripts/refresh.py` discovers new quarterly articles through Backblaze’s [Drive Stats archive](https://www.backblaze.com/blog/category/hard-drive-stats/), checks every edition and builds compact public JSON. The scheduled workflow checks monthly for new quarterly releases. A changed historical chart, unrecognized table or failed reconciliation stops the refresh before it can replace the deployed snapshot. If Backblaze changes a chart, review the transcription and totals before updating its digest.

## Offline raw-data aggregation

Download a quarter ZIP from Backblaze. Run `python3 scripts/aggregate_raw.py 2025-Q2 data_Q2_2025.zip > raw-cohorts.csv`. This streams the daily CSVs and counts model observations, observed failures and drives present on the final day of the quarter. It requires every day, verifies dates and rejects duplicate exact-model/serial combinations within a day. It writes only per-model aggregates. The raw archive includes testing and low-exposure models. The website uses Backblaze’s reviewed production tables so the two populations remain separately identifiable.

## Development

Use Python 3.11+ and Node 20+. Run `node --test tests/*.test.mjs`, `python3 -m unittest discover -s tests -v` and `python3 scripts/build.py`. Serve the resulting directory with `python3 -m http.server --directory dist`. The standard library builds the site without network access. Install the test-only dependencies from `tests/browser-requirements.txt` and run `python3 -m playwright install chromium` followed by `python3 tests/browser_smoke.py` for the full browser check. Main builds publish to GitHub Pages after validation.
