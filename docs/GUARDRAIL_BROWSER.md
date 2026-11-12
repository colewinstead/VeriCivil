# Guardrail browser integration

VeriCivil's free `/calculators/guardrail` workspace uses the separately maintained
[Guardrail Calculator](https://github.com/colewinstead/Guardrail-Calculator).
The calculation engine and report modules are bundled unchanged from commit
`4fe8b323b35644ce1cf32888607effbe6ffec999` (V9.0.2). The exact source files,
bundled references, upstream characterization fixture, MIT license and SHA-256
checksums are recorded in `calculators/guardrail/upstream/source.json`.

## Ownership and updates

- Fix calculations, tables, parsing, validation and existing report behavior in
  **Guardrail-Calculator** first. Its Windows application remains independently maintained.
- Maintain browser controls, JSON project format and runtime adaptation in
  **VeriCivil**, principally `calculators/guardrail/service.py` and
  `web/app/GuardrailCalculator.tsx`.
- Never edit files under `calculators/guardrail/upstream/` directly. The browser
  staging step verifies their checksums and fails if they change.
  `.gitattributes` disables Git line-ending conversion for this imported directory
  so Windows checkouts retain the exact upstream bytes.

After the upstream change is reviewed and tested, create an issue-linked VeriCivil
branch from current `main`, check out the desired Guardrail commit locally, and run:

**Windows PowerShell: import the update**

Copy this entire block into PowerShell. These paths match the local workspace;
change them only if your repositories are elsewhere. The commit SHA is selected
automatically from the Guardrail checkout's current `HEAD`:

```powershell
Set-Location "C:\Coding Projects\VeriCivil"
$guardrailSource = "C:\Coding Projects\Guardrail-Calculator"
$guardrailRevision = git -C $guardrailSource rev-parse --verify HEAD
if ($LASTEXITCODE -ne 0) { throw "Could not read the Guardrail commit. Check the source path." }
python scripts/update_guardrail.py --source $guardrailSource --revision $guardrailRevision
if ($LASTEXITCODE -ne 0) { throw "Guardrail import failed. Stop here and review the error." }
```

This imports the committed version currently checked out locally. Update and review
that checkout first if you want a newer upstream commit. Successful import prints
`Verified Guardrail` followed by the imported version and full commit SHA.

**Windows PowerShell: validate the imported update**

Run this after the import succeeds. `PYTHONUTF8` enables consistent UTF-8 handling
for native/Pyodide comparisons in this terminal session:

```powershell
Set-Location "C:\Coding Projects\VeriCivil"
python -m pip install -r requirements-lock.txt
$env:PYTHONUTF8 = "1"
python -m unittest -v
Push-Location web
npm exec tsc -- --noEmit
npm run lint
npm test
Pop-Location
```

`python scripts/update_guardrail.py` without `--source` and `--revision` only checks
the already imported files. Use the import block above to bring in an update.

**macOS/Linux** (from the VeriCivil repository root):

```sh
python3 scripts/update_guardrail.py --source /path/to/Guardrail-Calculator --revision FULL_40_CHARACTER_COMMIT_SHA
python3 scripts/update_guardrail.py
python3 -m pip install -r requirements-lock.txt
python3 -m unittest -v
cd web
npm exec tsc -- --noEmit
npm run lint
npm test
```

The importer reads committed Git objects; uncommitted upstream edits are excluded.
Review the source and dependency changes, pin and checksums, upstream fixture changes,
browser/native parity and generated reports in the upgrade PR. A changed fixture is
evidence to investigate, not a reason to replace the expected digest automatically.
Update the integration documentation, manifest limits and application version as
needed. Rollback means a normal PR restoring the earlier imported revision, with
VeriCivil's required new application version.

No GitHub connection is needed by site visitors or by the normal source build.
Runtime dependencies load through VeriCivil's existing Pyodide worker. Initial
browser loading needs internet access; this is not an offline-availability guarantee.
The worker stages reference PDFs as binary assets into its local virtual filesystem.

## Included workflow

Both current facility types, near/opposing calculations, direct or table-selected
LA, custom clear zone, standard/custom transition and terminal lengths, supported
flare ratios and non-flared mode are retained. Divided-roadway opposing distances
can remain manually entered or be linked to the lane/median dimensions. Linked
values are resolved by upstream Python, without JavaScript engineering arithmetic.
The clear-zone criteria selector offers new-construction Table 9-2-A and 3R rural
non-freeway Table 12-2-B. Both resolve through upstream Python. The 3R lookup supports
30–65 mph and preserves upstream restrictions for recoverable fill slopes and
non-curbed facilities, including project review of the starred 15-ft allowance.

All three report styles reuse the upstream report layout. Optional appendices
include `gr manual.pdf` plus `GR-4.pdf` for divided highways or `GR-4a.pdf` for
two-lane/two-way highways. V9 renders searchable vector equations through the
unchanged upstream `guardrail_pdf_math.py` and Matplotlib. Summary, detailed and
combined reports have one, two and three pages respectively. The upstream report
rotates Figure 9-6-A to landscape while preserving the other reference page sizes.
Missing references fail
the requested export rather than silently producing an incomplete package.
For 3R projects, obtain the Table 12-2-B source page separately. The bundled
reference PDFs contain the existing Chapter 9 and GR-4/GR-4a material.

Version 1 `vericivil.guardrail` JSON files contain raw inputs, mode selections,
project metadata, PDF preferences, source commit and engine version. Imports are
limited to 64 KiB and validate supported fields, types, selections and active
engineering inputs before replacing current state. Saved results are never trusted:
reopening recalculates. The selected clear-zone criteria are saved with the inputs.
Older browser projects without that selection reopen using new construction.
A changed source revision is reported to the user. These
files do not establish Windows project-file interoperability. File downloads are
browser-managed; keep the downloaded JSON to reopen the project. There is no cloud
project storage or automatic session recovery.

Input edits immediately hide the old result and disable export until calculation
succeeds. Downloads use one captured set of inputs. Unsaved-change warnings cover
page unload, navigation links and project replacement, subject to browser limits
on unload prompts (especially on mobile). Saving a PDF does not save the project.

## Validation and engineering boundaries

Engineering and report regressions belong to the Guardrail repository's own test
suite. VeriCivil's `guardrail-upstream` CI job checks out the exact commit recorded
in `source.json` and runs that suite unchanged, including its report-layout fixtures.
Do not regenerate report fingerprints in VeriCivil to make an upgrade pass.

To run the original upstream suite locally, use the Guardrail checkout at that same
pinned commit:

```powershell
Push-Location "C:\Coding Projects\Guardrail-Calculator"
$env:PYTHONUTF8 = "1"
python -m unittest -v
Pop-Location
```

`test_guardrail_browser.py` covers VeriCivil's JSON boundary, saved projects,
adapter parity against the upstream 2,592-case numerical baseline, and PDF downloads
with both facility-specific appendix packages. These integration tests run natively
and through `web/tests/guardrail-parity.mjs` in Pyodide. They do not duplicate the
upstream report fingerprints. `web/tests/guardrail-smoke.mjs` tests the
rendered page, automatic calculation, stale-result protection, JSON download/reopen,
PDF downloads, malformed imports, responsive layouts and unsaved navigation.

Run the renderer smoke with the dev server running at `http://localhost:3001`
using `npm run test:guardrail:browser` from `web`. Set `GUARDRAIL_TEST_URL` to the
full calculator URL when using another port. On hosts inheriting
`ELECTRON_RUN_AS_NODE=1`, run `env -u ELECTRON_RUN_AS_NODE npm run test:guardrail:browser`.

In **Windows PowerShell**, start the server in one terminal from the VeriCivil
repository root and leave it running:

```powershell
npm --prefix web run dev -- --port 3001
```

In a second PowerShell terminal, also starting at the repository root, run:

```powershell
Set-Location web
Remove-Item Env:\ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue
npm run test:guardrail:browser
```

`Remove-Item` clears the inherited Electron flag for the current terminal session.
For another port, set the full URL before running the smoke test:

```powershell
$env:GUARDRAIL_TEST_URL = "http://localhost:3002/calculators/guardrail"
npm run test:guardrail:browser
```

To return to the default URL in that terminal, run
`Remove-Item Env:\GUARDRAIL_TEST_URL -ErrorAction SilentlyContinue`.

The renderer test writes local desktop/phone captures under the ignored
`.impeccable/review/guardrail/` and refreshes the catalog's authentic result crop.
When adopting a new crop, embed its screenshot origin with Impeccable's
`embed-prompt` command before committing.

These are software regression and integration checks, not independent engineering
approval. Preserve the upstream architecture's unresolved questions about clear-zone
interpretation, traffic direction/physical sides, terminal contributions, minimum
rail lengths, opposing-hazard geometry and ADT table boundaries. Reports preserve
the upstream contents, including the clear-zone criteria, slope and selection for
table-derived LA. Verify inputs, references, assumptions and applicability for the project.
The upstream license accompanies its source; included MDOT PDFs are reference
material, not a claim that the upstream MIT license licenses agency publications.

DXF and LandXML overlays remain in the separate Windows application. This browser
integration does not extend their support or change their engineering restrictions.
