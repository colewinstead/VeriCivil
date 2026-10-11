# Superelevation Calculator browser app

This interface runs the repository's shared Python calculation, LandXML, project, PDF, CSV, and DXF modules inside a Web Worker through Pyodide. Calculation inputs and project files are processed locally in the tab and are not uploaded.

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
