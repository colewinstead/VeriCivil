# Superelevation Calculator browser app

This interface runs the repository's shared Python calculation, LandXML, project, PDF, CSV, and DXF modules inside a Web Worker through Pyodide. Processing runs locally. Separate product analytics collect DOT standard, speed, radius, and PC/PT without account/session linkage. LandXML retention is enabled by default with a persistent opt-out control before selection; Do Not Track suppresses both engineering statistics and file retention.

Engineering analytics use the existing D1 binding and migration `0005_strong_polaris.sql`. Successful calculations contribute daily aggregate input combinations (90-day expiry, up to 10,000 rows). Successfully parsed LandXML up to 1 MiB can be retained (30-day expiry, up to 100 files). Limits or storage failures never prevent local import/calculation. Expired records are purged on the next engineering collection or admin report/download request; no scheduled purge is configured. Downloads and deletion require the existing configured product-admin authorization. Raw XML is served only as an attachment with `nosniff`; metadata from the raw file is never rendered as HTML. No account/session token, original filename, or IP address is stored with these records. Raw XML itself may still identify projects or people; removing account linkage does not anonymize it.

Both analytics endpoints exclude signed-in administrators using the existing `ADMIN_WORKOS_USER_IDS` allowlist. Analytics requests carry same-origin cookies for this check; identity is never stored with analytics. Skipped LandXML retention returns 204 and is shown as skipped in the calculator. Signed-out activity still counts. Earlier anonymous records cannot be selectively removed by account. Authentication failures skip storage and return 503 without affecting local calculations.

## Development

Requires Python 3.11+ and Node.js 22.13+.

```bash
# Run these commands inside VeriCivil/web.
npm ci --ignore-scripts
npm run dev
```

Open the local URL printed by the server and keep the terminal running. From the repository root, enter this directory with `cd web` on macOS/Linux or `Set-Location .\web` in Windows PowerShell.

The `predev` and `prebuild` hooks use `python3` on macOS/Linux and `python` on Windows to copy the authoritative shared Python modules from the repository root into the ignored `public/python` staging directory. The selected interpreter must be on PATH; npm cannot use interactive shell aliases. Native Python calculation dependencies are not needed just to start the browser app. Do not edit staged copies.

## Verification

```bash
npm exec tsc -- --noEmit
npm run lint
npm test
```

`npm test` creates a production build, checks the rendered application shell, runs the shared calculation engine in Pyodide, verifies an approved numeric result, and generates CSV, PDF, and DXF output.

## Production build

```bash
npm run build
```

The deployable package is written to `dist`. It requires no calculation API, database, account, or project-file storage service. The host only serves the application and its runtime assets.
